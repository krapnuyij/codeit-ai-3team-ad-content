"""
nanoCocoa_aiserver REST API 클라이언트
비동기 HTTP 클라이언트를 사용하여 AI 서버와 통신
"""

import asyncio
import logging
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from typing import Optional, Callable, Any
from contextlib import asynccontextmanager

import httpx

try:
    from ..config import (
        AISERVER_BASE_URL,
        AISERVER_TIMEOUT,
        AISERVER_CONNECT_TIMEOUT,
        STATUS_POLL_INTERVAL,
        MAX_POLL_RETRIES,
        RETRY_BACKOFF_FACTOR,
        MAX_RETRY_DELAY,
        RETRY_STATUS_CODES,
        MAX_RETRIES_ON_503,
        HTTP_MAX_CONNECTIONS,
        HTTP_MAX_KEEPALIVE_CONNECTIONS,
        HTTP_KEEPALIVE_EXPIRY,
        APIEndpoints,
    )
    from ..schemas.api_models import (
        GenerateRequest,
        GenerateResponse,
        StatusResponse,
        StopResponse,
        JobListResponse,
        HealthResponse,
        FontListResponse,
        ErrorResponse,
    )
except ImportError:
    from config import (
        AISERVER_BASE_URL,
        AISERVER_TIMEOUT,
        AISERVER_CONNECT_TIMEOUT,
        STATUS_POLL_INTERVAL,
        MAX_POLL_RETRIES,
        RETRY_BACKOFF_FACTOR,
        MAX_RETRY_DELAY,
        RETRY_STATUS_CODES,
        MAX_RETRIES_ON_503,
        HTTP_MAX_CONNECTIONS,
        HTTP_MAX_KEEPALIVE_CONNECTIONS,
        HTTP_KEEPALIVE_EXPIRY,
        APIEndpoints,
    )
    from schemas.api_models import (
        GenerateRequest,
        GenerateResponse,
        StatusResponse,
        StopResponse,
        JobListResponse,
        HealthResponse,
        FontListResponse,
        ErrorResponse,
    )


logger = logging.getLogger(__name__)


class AIServerError(Exception):
    """AI 서버 API 에러"""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        retry_after: Optional[int] = None,
        detail: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.retry_after = retry_after
        self.detail = detail


class AIServerClient:
    """
    nanoCocoa_aiserver REST API 비동기 클라이언트

    사용 예:
        async with AIServerClient() as client:
            response = await client.start_generation(params)
            job_id = response.job_id
            result = await client.wait_for_completion(job_id)
    """

    def __init__(
        self,
        base_url: str = AISERVER_BASE_URL,
        timeout: int = AISERVER_TIMEOUT,
        connect_timeout: int = AISERVER_CONNECT_TIMEOUT,
    ):
        """
        Args:
            base_url: AI 서버 기본 URL
            timeout: 요청 타임아웃 (초)
            connect_timeout: 연결 타임아웃 (초)
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.connect_timeout = connect_timeout
        self._client: Optional[httpx.AsyncClient] = None

        logger.info(f"AIServerClient 초기화: base_url={self.base_url}")

    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        await self.close()

    async def _ensure_client(self):
        """HTTP 클라이언트 초기화 (필요시)"""
        if self._client is None:
            limits = httpx.Limits(
                max_connections=HTTP_MAX_CONNECTIONS,
                max_keepalive_connections=HTTP_MAX_KEEPALIVE_CONNECTIONS,
                keepalive_expiry=HTTP_KEEPALIVE_EXPIRY,
            )

            timeout_config = httpx.Timeout(
                timeout=self.timeout,
                connect=self.connect_timeout,
            )

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=timeout_config,
                limits=limits,
                follow_redirects=True,
            )
            logger.debug("HTTP 클라이언트 생성 완료")

    async def close(self):
        """HTTP 클라이언트 종료"""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.debug("HTTP 클라이언트 종료")

    async def _request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """
        HTTP 요청 실행 (재시도 로직 포함)

        Args:
            method: HTTP 메서드 (GET, POST, DELETE 등)
            endpoint: API 엔드포인트 경로
            **kwargs: httpx 요청 파라미터

        Returns:
            httpx.Response 객체

        Raises:
            AIServerError: API 요청 실패
        """
        await self._ensure_client()

        retry_count = 0
        last_error = None

        while retry_count <= MAX_RETRIES_ON_503:
            try:
                logger.debug(
                    f"{method} {endpoint} 요청 (시도 {retry_count + 1}/{MAX_RETRIES_ON_503 + 1})"
                )

                response = await self._client.request(method, endpoint, **kwargs)

                # 503 에러 처리 (서버 사용 중)
                if response.status_code in RETRY_STATUS_CODES:
                    retry_after = int(response.headers.get("Retry-After", 5))

                    if retry_count < MAX_RETRIES_ON_503:
                        delay = min(
                            retry_after * (RETRY_BACKOFF_FACTOR**retry_count),
                            MAX_RETRY_DELAY,
                        )
                        logger.warning(
                            f"서버 사용 중 (503). {delay:.1f}초 후 재시도... "
                            f"({retry_count + 1}/{MAX_RETRIES_ON_503})"
                        )
                        await asyncio.sleep(delay)
                        retry_count += 1
                        continue
                    else:
                        raise AIServerError(
                            f"서버가 계속 사용 중입니다. 나중에 다시 시도하세요.",
                            status_code=503,
                            retry_after=retry_after,
                        )

                # 기타 에러 처리
                if not response.is_success:
                    error_detail = None
                    try:
                        error_data = response.json()
                        error_detail = error_data.get("detail") or error_data.get(
                            "message"
                        )
                    except Exception:
                        error_detail = response.text

                    raise AIServerError(
                        f"API 요청 실패: {response.status_code}",
                        status_code=response.status_code,
                        detail=error_detail,
                    )

                return response

            except httpx.TimeoutException as e:
                last_error = e
                logger.error(f"요청 타임아웃: {endpoint}")
                raise AIServerError(f"요청 타임아웃: {endpoint}", detail=str(e))

            except httpx.NetworkError as e:
                last_error = e
                logger.error(f"네트워크 에러: {endpoint} - {e}")
                raise AIServerError(
                    f"AI 서버에 연결할 수 없습니다: {self.base_url}", detail=str(e)
                )

            except AIServerError:
                raise

            except Exception as e:
                last_error = e
                logger.error(f"예상치 못한 에러: {endpoint} - {e}")
                raise AIServerError(f"요청 중 에러 발생: {str(e)}", detail=str(e))

        # 최대 재시도 초과
        if last_error:
            raise AIServerError(f"최대 재시도 횟수 초과", detail=str(last_error))

    # =========================================================================
    # 헬스 & 리소스 API
    # =========================================================================

    async def check_health(self) -> HealthResponse:
        """
        서버 헬스체크 및 상태 확인

        Returns:
            HealthResponse: 서버 상태 정보
        """
        response = await self._request("GET", APIEndpoints.HEALTH)
        data = response.json()
        return HealthResponse(**data)

    async def get_fonts(self) -> list[str]:
        """
        사용 가능한 폰트 목록 조회

        Returns:
            폰트 파일 경로 리스트
        """
        response = await self._request("GET", APIEndpoints.FONTS)
        data = response.json()
        font_response = FontListResponse(**data)
        return font_response.fonts

    async def get_fonts_metadata(self) -> list[dict]:
        """
        폰트 메타데이터 조회 (스타일, 굵기, 용도, 톤앤매너 포함)

        Returns:
            폰트 메타데이터 딕셔너리 리스트
        """
        response = await self._request("GET", "/fonts/metadata")
        data = response.json()
        return data.get("fonts", [])

    # =========================================================================
    # 생성 API
    # =========================================================================

    async def start_generation(self, params: GenerateRequest) -> GenerateResponse:
        """
        광고 이미지 생성 시작 (비동기)

        Args:
            params: 생성 요청 파라미터

        Returns:
            GenerateResponse: job_id 포함
        """
        logger.info(
            f"생성 시작: start_step={params.start_step}, text={params.text_content}"
        )

        response = await self._request(
            "POST", APIEndpoints.GENERATE, json=params.model_dump(exclude_none=True)
        )

        data = response.json()
        return GenerateResponse(**data)

    async def get_status(self, job_id: str) -> StatusResponse:
        """
        작업 상태 조회

        Args:
            job_id: 작업 ID

        Returns:
            StatusResponse: 작업 상태 정보
        """
        endpoint = APIEndpoints.STATUS.format(job_id=job_id)
        response = await self._request("GET", endpoint)
        data = response.json()
        return StatusResponse(**data)

    async def stop_job(self, job_id: str) -> StopResponse:
        """
        실행 중인 작업 중단

        Args:
            job_id: 작업 ID

        Returns:
            StopResponse: 중단 결과
        """
        logger.info(f"작업 중단 요청: job_id={job_id}")

        endpoint = APIEndpoints.STOP.format(job_id=job_id)
        response = await self._request("POST", endpoint)
        data = response.json()
        return StopResponse(**data)

    async def list_jobs(self) -> JobListResponse:
        """
        전체 작업 목록 조회

        Returns:
            JobListResponse: 작업 목록 및 통계
        """
        response = await self._request("GET", APIEndpoints.JOBS)
        data = response.json()
        return JobListResponse(**data)

    async def delete_job(self, job_id: str) -> dict:
        """
        완료/실패한 작업 삭제

        Args:
            job_id: 작업 ID

        Returns:
            삭제 결과 딕셔너리
        """
        logger.info(f"작업 삭제: job_id={job_id}")

        endpoint = APIEndpoints.DELETE_JOB.format(job_id=job_id)
        response = await self._request("DELETE", endpoint)
        return response.json()

    # =========================================================================
    # 고수준 헬퍼 메서드
    # =========================================================================

    async def wait_for_completion(
        self,
        job_id: str,
        poll_interval: float = STATUS_POLL_INTERVAL,
        max_retries: int = MAX_POLL_RETRIES,
        progress_callback: Optional[Callable[[StatusResponse], Any]] = None,
    ) -> StatusResponse:
        """
        작업이 완료될 때까지 폴링하며 대기

        Args:
            job_id: 작업 ID
            poll_interval: 폴링 간격 (초)
            max_retries: 최대 폴링 횟수
            progress_callback: 진행 상태 콜백 함수 (선택사항)

        Returns:
            StatusResponse: 최종 상태

        Raises:
            AIServerError: 작업 실패 또는 타임아웃
        """
        logger.info(f"작업 완료 대기 시작: job_id={job_id}")

        retry_count = 0

        while retry_count < max_retries:
            try:
                status = await self.get_status(job_id)

                # 진행 상태 콜백 호출
                if progress_callback:
                    try:
                        if asyncio.iscoroutinefunction(progress_callback):
                            await progress_callback(status)
                        else:
                            progress_callback(status)
                    except Exception as e:
                        logger.warning(f"진행 상태 콜백 에러: {e}")

                # 완료 상태 확인
                if status.status == "completed":
                    logger.info(
                        f"작업 완료: job_id={job_id}, 소요 시간={status.elapsed_sec:.1f}초"
                    )
                    return status

                # 실패 상태 확인
                if status.status == "failed":
                    logger.error(f"작업 실패: job_id={job_id}, 메시지={status.message}")
                    raise AIServerError(
                        f"작업 실패: {status.message}", detail=status.message
                    )

                # 중단 상태 확인
                if status.status == "stopped":
                    logger.warning(f"작업 중단됨: job_id={job_id}")
                    raise AIServerError(f"작업이 중단되었습니다", detail=status.message)

                # 진행 중 - 다음 폴링 대기
                logger.debug(
                    f"진행 중: {status.progress_percent}% - {status.current_step} - {status.message}"
                )
                await asyncio.sleep(poll_interval)
                retry_count += 1

            except AIServerError:
                raise
            except Exception as e:
                logger.error(f"상태 조회 중 에러: {e}")
                retry_count += 1
                await asyncio.sleep(poll_interval)

        # 최대 폴링 횟수 초과
        raise AIServerError(
            f"작업 완료 대기 시간 초과 (최대 {max_retries * poll_interval:.0f}초)",
            detail=f"job_id: {job_id}",
        )

    async def generate_and_wait(
        self,
        params: GenerateRequest,
        progress_callback: Optional[Callable[[StatusResponse], Any]] = None,
    ) -> StatusResponse:
        """
        생성 시작 후 완료까지 대기 (원스톱 메서드)

        Args:
            params: 생성 요청 파라미터
            progress_callback: 진행 상태 콜백 함수

        Returns:
            StatusResponse: 최종 완료 상태
        """
        # 생성 시작
        response = await self.start_generation(params)
        job_id = response.job_id

        # 완료 대기
        return await self.wait_for_completion(
            job_id, progress_callback=progress_callback
        )
