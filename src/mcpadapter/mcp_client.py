"""
MCP HTTP 클라이언트
HTTP/SSE transport를 통해 MCP 서버와 통신
"""

import asyncio
import httpx
import sys
from pathlib import Path

project_root = Path(__file__).resolve()
sys.path.insert(0, str(project_root))

import logging
from helper_dev_utils import get_auto_logger

logger = get_auto_logger()

from typing import Any, Dict, Optional, List
from contextlib import asynccontextmanager


class MCPClientError(Exception):
    """MCP 클라이언트 에러"""

    pass


class MCPClient:
    """
    nanoCocoa MCP 서버와 HTTP로 통신하는 클라이언트

    사용 예:
        async with MCPClient("http://mcpserver:3000") as client:
            result = await client.call_tool("generate_ad_image", {...})
    """

    def __init__(
        self,
        base_url: str = "http://localhost:3000",
        timeout: int = 900,
    ):
        """
        Args:
            base_url: MCP 서버 URL (기본값: http://localhost:3000)
            timeout: 요청 타임아웃 (초)
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

        logger.info(f"MCPClient 초기화: base_url={self.base_url}")

    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        await self.close()

    async def _ensure_client(self):
        """HTTP 클라이언트 초기화"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
            )

    async def close(self):
        """HTTP 클라이언트 종료"""
        if self._client:
            try:
                await self._client.aclose()
            except RuntimeError as e:
                # 이벤트 루프가 이미 닫혔을 경우 무시
                if "Event loop is closed" not in str(e):
                    raise
            finally:
                self._client = None

    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        max_retries: int = 3,
        initial_delay: float = 1.0,
    ) -> Any:
        """
        MCP 도구 호출 (지수 백오프 재시도 포함)

        Args:
            tool_name: 도구 이름 (예: "generate_ad_image")
            arguments: 도구 인자 딕셔너리
            max_retries: 최대 재시도 횟수 (기본값: 3)
            initial_delay: 초기 대기 시간 (기본값: 1.0초)

        Returns:
            도구 실행 결과

        Raises:
            MCPClientError: MCP 서버 에러
        """
        await self._ensure_client()

        last_error = None
        delay = initial_delay

        for attempt in range(max_retries):
            try:
                response = await self._client.post(
                    f"{self.base_url}/tools/{tool_name}",
                    json=arguments,
                )
                response.raise_for_status()

                data = response.json()

                if data.get("error"):
                    raise MCPClientError(data["error"])

                return data.get("result")

            except httpx.HTTPStatusError as e:
                raise MCPClientError(
                    f"HTTP {e.response.status_code}: {e.response.text}"
                )
            except httpx.RequestError as e:
                last_error = e
                if attempt < max_retries - 1:
                    logger.warning(
                        f"연결 실패 (시도 {attempt + 1}/{max_retries}), "
                        f"{delay:.1f}초 후 재시도: {e}"
                    )
                    await asyncio.sleep(delay)
                    delay *= 2  # 지수 백오프
                else:
                    raise MCPClientError(f"연결 에러 (최대 재시도 초과): {e}")

    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        사용 가능한 도구 목록 조회

        Returns:
            도구 정보 리스트
        """
        await self._ensure_client()

        try:
            response = await self._client.get(f"{self.base_url}/tools")
            response.raise_for_status()
            data = response.json()
            # 서버가 {"tools": [...]} 형식으로 반환하면 tools 리스트만 추출
            if isinstance(data, dict) and "tools" in data:
                return data["tools"]
            return data

        except httpx.HTTPStatusError as e:
            raise MCPClientError(f"HTTP {e.response.status_code}: {e.response.text}")
        except httpx.RequestError as e:
            raise MCPClientError(f"연결 에러: {e}")

    async def health_check(self) -> Dict[str, Any]:
        """
        MCP 서버 헬스체크

        Returns:
            서버 상태 정보
        """
        await self._ensure_client()

        try:
            response = await self._client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            raise MCPClientError(f"HTTP {e.response.status_code}: {e.response.text}")
        except httpx.RequestError as e:
            raise MCPClientError(f"연결 에러: {e}")

    async def server_reset(self) -> Dict[str, Any]:
        """
        서버 상태 초기화 (개발 전용)

        모든 실행 중인 작업 강제 중단, 작업 기록 삭제, GPU 메모리 정리

        Returns:
            초기화 결과 통계 (stopped_jobs, deleted_jobs, terminated_processes 등)

        Raises:
            MCPClientError: 서버 초기화 실패
        """
        await self._ensure_client()

        try:
            response = await self._client.post(f"{self.base_url}/server-reset")
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            raise MCPClientError(f"HTTP {e.response.status_code}: {e.response.text}")
        except httpx.RequestError as e:
            raise MCPClientError(f"연결 에러: {e}")
