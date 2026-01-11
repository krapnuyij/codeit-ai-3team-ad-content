"""
nanoCocoa MCP Server (FastAPI REST API)
REST API를 통해 nanoCocoa_aiserver를 제어하는 서버
LLM Adapter와 HTTP 통신
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# 프로젝트 루트 경로 추가 (직접 실행 시에도 임포트 가능하도록)
project_root = Path(__file__).resolve()
sys.path.insert(0, str(project_root))

from config import (
    MCP_SERVER_NAME,
    MCP_SERVER_VERSION,
    MCP_SERVER_DESCRIPTION,
)
from client.api_client import AIServerClient, AIServerError
from schemas.api_models import GenerateRequest
from utils.image_utils import (
    image_file_to_base64,
    base64_to_image_file,
    ImageProcessingError,
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# FastAPI 서버 초기화
app = FastAPI(
    title=MCP_SERVER_NAME,
    version=MCP_SERVER_VERSION,
    description=MCP_SERVER_DESCRIPTION,
)

# API 클라이언트 전역 인스턴스 (상태 유지)
_api_client: Optional[AIServerClient] = None


async def get_api_client() -> AIServerClient:
    """API 클라이언트 싱글톤 인스턴스 반환"""
    global _api_client
    if _api_client is None:
        _api_client = AIServerClient()
        await _api_client._ensure_client()
    return _api_client


# =============================================================================
# Tool 함수 정의 (비즈니스 로직)
# =============================================================================


async def generate_ad_image(
    product_image_path: str,
    background_prompt: str,
    text_content: str,
    text_style_prompt: str,
    font_name: Optional[str] = None,
    composition_mode: str = "overlay",
    text_position: str = "auto",
    seed: Optional[int] = None,
    test_mode: bool = False,
    wait_for_completion: bool = True,
    save_output_path: Optional[str] = None,
) -> str:
    """
    제품 이미지를 기반으로 AI가 전문적인 광고 이미지를 생성합니다.

    이 도구는 3단계 파이프라인을 자동으로 실행합니다:
    1. 제품 이미지에 AI가 배경을 합성 (배경 생성)
    2. 광고 텍스트를 3D 스타일로 생성 (3D 텍스트 생성)
    3. 배경과 3D 텍스트를 자연스럽게 합성 (최종 합성)

    사용 시나리오:
    - 신제품 출시 광고 (예: "NEW ARRIVAL" 텍스트 + 화려한 배경)
    - 할인 프로모션 광고 (예: "SALE 50%" + 축제 분위기 배경)
    - 계절/이벤트 광고 (예: "SUMMER SALE" + 여름 느낌 배경)
    - 시장/오프라인 판매용 광고 (예: "특가 2500원" + 시장 분위기)

    Args:
        product_image_path: 제품 이미지 파일의 절대 경로
            - 지원 형식: PNG, JPG, JPEG, WEBP
            - 권장 크기: 512x512 ~ 1024x1024 픽셀
            - 예시: "/home/user/product.png" 또는 "./images/product.jpg"

        background_prompt: 생성할 배경에 대한 영문 설명 (프롬프트)
            - 영문으로 작성 (한글 프롬프트는 자동 번역되지 않음)
            - 구체적이고 상세할수록 좋은 결과
            - 예시: "Colorful party balloons and confetti, festive atmosphere, vibrant colors"
            - 예시: "Traditional Korean market scene, warm lighting, busy street vendor"
            - 예시: "Luxury gold background, elegant style, studio lighting"

        text_content: 광고에 표시할 텍스트 내용
            - 한글, 영문, 숫자, 특수문자 지원
            - 짧고 임팩트 있는 문구 권장 (1~10단어)
            - 예시: "SALE", "NEW", "50% OFF", "특가 2500원", "신제품 출시"

        text_style_prompt: 3D 텍스트의 시각적 스타일 설명 (영문)
            - 3D 렌더링 스타일, 재질, 조명 등을 구체적으로 기술
            - 예시: "3D render of gold foil balloon text, shiny metallic texture, floating"
            - 예시: "Bold 3D text with neon glow effect, cyberpunk style, dark background"
            - 예시: "Wooden carved text, rustic style, natural lighting"

        font_name: 텍스트 렌더링에 사용할 폰트 파일명 (선택사항)
            - list_available_fonts 도구로 사용 가능한 폰트 목록 확인 가능
            - 한글 텍스트는 한글 폰트 필수 (예: "NanumGothic.ttf")
            - 생략 시 기본 폰트 사용

        composition_mode: 배경과 텍스트 합성 방식 (기본값: "overlay")
            - "overlay": 텍스트를 배경 위에 자연스럽게 오버레이 (가장 일반적)
            - "blend": 텍스트와 배경을 부드럽게 블렌딩 (은은한 느낌)
            - "behind": 텍스트가 배경 뒤에 있는 것처럼 합성 (입체감)

        text_position: 텍스트 배치 위치 (기본값: "auto")
            - "auto": AI가 자동으로 최적 위치 결정 (권장)
            - "top": 이미지 상단에 배치
            - "center": 이미지 중앙에 배치
            - "bottom": 이미지 하단에 배치

        seed: 재현성을 위한 랜덤 시드 (선택사항)
            - 동일한 seed를 사용하면 동일한 결과 생성
            - 생략 시 매번 다른 결과 생성
            - 예시: 42, 12345

        test_mode: 더미 데이터 테스트 모드 (기본값: False)
            - True: AI 모델 없이 더미 이미지로 파이프라인만 테스트 (빠름, GPU 불필요)
            - False: 실제 AI 모델로 고품질 이미지 생성 (느림, GPU 필요)
            - 개발/테스트 시에는 True, 실제 사용 시에는 False

        wait_for_completion: 생성 완료까지 대기 여부 (기본값: True)
            - True: 생성이 완료될 때까지 대기 후 결과 반환 (동기 방식)
            - False: 즉시 job_id만 반환하고 백그라운드에서 생성 (비동기 방식)
            - True 권장 (사용자가 바로 결과를 볼 수 있음)

        save_output_path: 생성된 이미지를 저장할 파일 경로 (선택사항)
            - 생략 시 이미지를 저장하지 않고 Base64로만 반환
            - 절대 경로 또는 상대 경로 사용 가능
            - 예시: "/home/user/output/ad_result.png", "./result.png"

    Returns:
        생성 결과 메시지 (작업 ID, 상태, 소요 시간, 진행률 등)

    실행 시간:
        - test_mode=True: 약 1~3초
        - test_mode=False: 약 30~120초 (GPU 사양에 따라 다름)

    오류 처리:
        - 이미지 파일을 찾을 수 없으면 에러 반환
        - AI 서버가 응답하지 않으면 연결 에러 반환
        - GPU 메모리 부족 시 에러 반환
    """
    try:
        client = await get_api_client()

        # 이미지 로드 및 Base64 변환
        logger.info(f"제품 이미지 로드: {product_image_path}")
        product_image_b64 = image_file_to_base64(product_image_path)

        # 요청 파라미터 구성
        params = GenerateRequest(
            start_step=1,
            input_image=product_image_b64,
            bg_prompt=background_prompt,
            text_content=text_content,
            text_model_prompt=text_style_prompt,
            font_name=font_name,
            composition_mode=composition_mode,
            text_position=text_position,
            seed=seed,
            test_mode=test_mode,
        )

        if wait_for_completion:
            # 완료까지 대기
            logger.info("광고 이미지 생성 시작 (완료까지 대기)")
            result = await client.generate_and_wait(
                params,
                progress_callback=lambda s: logger.info(
                    f"진행: {s.progress_percent}% - {s.current_step} - {s.message}"
                ),
            )

            # 결과 저장 (선택사항)
            if save_output_path and result.final_result:
                output_path = base64_to_image_file(
                    result.final_result, save_output_path, overwrite=True
                )
                logger.info(f"결과 저장: {output_path}")

            # 응답 구성
            response = (
                f"광고 이미지 생성 완료!\n\n"
                f"작업 ID: {result.job_id}\n"
                f"소요 시간: {result.elapsed_sec:.1f}초\n"
                f"진행률: {result.progress_percent}%\n"
                f"상태: {result.status}\n"
            )

            if save_output_path:
                response += f"\n저장 경로: {save_output_path}"

            return response
        else:
            # 비동기 시작만
            logger.info("광고 이미지 생성 시작 (비동기)")
            response = await client.start_generation(params)
            return (
                f"작업 시작됨\n"
                f"작업 ID: {response.job_id}\n"
                f"상태: {response.status}\n\n"
                f"진행 상태 확인: check_generation_status(job_id='{response.job_id}')"
            )

    except ImageProcessingError as e:
        logger.error(f"이미지 처리 에러: {e}")
        return f"이미지 처리 에러: {str(e)}"

    except AIServerError as e:
        logger.error(f"AI 서버 에러: {e}")
        error_msg = f"AI 서버 에러: {str(e)}"
        if e.detail:
            error_msg += f"\n상세: {e.detail}"
        if e.retry_after:
            error_msg += f"\n{e.retry_after}초 후 재시도하세요."
        return error_msg

    except Exception as e:
        logger.exception(f"예상치 못한 에러: {e}")
        return f"에러 발생: {str(e)}"


async def check_generation_status(
    job_id: str, save_result_path: Optional[str] = None
) -> str:
    """
    비동기로 시작된 광고 생성 작업의 현재 진행 상태를 확인합니다.

    사용 시나리오:
    - generate_ad_image를 wait_for_completion=False로 호출한 경우
    - 장시간 실행되는 작업의 진행 상황을 주기적으로 체크
    - 작업 완료 후 결과 이미지를 저장하고 싶을 때

    반환 정보:
    - 작업 상태 (대기중/실행중/완료/실패)
    - 진행률 (0~100%)
    - 현재 실행 중인 단계 (Step 1: 배경 생성 / Step 2: 텍스트 생성 / Step 3: 합성)
    - 경과 시간 및 예상 남은 시간
    - 시스템 리소스 사용량 (CPU, RAM, GPU)

    Args:
        job_id: 확인할 작업의 고유 ID
            - generate_ad_image 호출 시 반환된 ID 사용
            - 예시: "job-20260107-abc123"

        save_result_path: 작업이 완료된 경우 결과 이미지를 저장할 파일 경로 (선택사항)
            - 작업이 완료 상태일 때만 저장됨
            - 예시: "./completed_ad.png", "/home/user/results/final.png"

    Returns:
        작업 상태 정보 텍스트 (상태, 진행률, 현재 단계, 예상 시간, 시스템 메트릭 등)

    사용 예시:
        1. job_id = generate_ad_image(..., wait_for_completion=False)
        2. 10초 대기
        3. status = check_generation_status(job_id)
        4. "completed"가 나올 때까지 반복
    """
    try:
        client = await get_api_client()
        status = await client.get_status(job_id)

        # 결과 저장 (완료된 경우)
        if save_result_path and status.status == "completed" and status.final_result:
            output_path = base64_to_image_file(
                status.final_result, save_result_path, overwrite=True
            )
            logger.info(f"결과 저장: {output_path}")

        # 응답 구성
        response = (
            f"작업 상태: {status.status}\n"
            f"진행률: {status.progress_percent}%\n"
            f"현재 단계: {status.current_step}\n"
            f"메시지: {status.message}\n"
            f"경과 시간: {status.elapsed_sec:.1f}초\n"
        )

        if status.eta_seconds is not None:
            if status.eta_seconds > 0:
                response += f"예상 남은 시간: {status.eta_seconds}초\n"
            else:
                response += f"예상 시간 초과: {abs(status.eta_seconds)}초\n"

        if status.system_metrics:
            metrics = status.system_metrics
            response += (
                f"\n시스템 메트릭:\n"
                f"  CPU: {metrics.cpu_percent:.1f}%\n"
                f"  RAM: {metrics.ram_used_gb:.1f}/{metrics.ram_total_gb:.1f} GB "
                f"({metrics.ram_percent:.1f}%)\n"
            )
            if metrics.gpu_info:
                for gpu in metrics.gpu_info:
                    response += (
                        f"  GPU {gpu.index} ({gpu.name}): {gpu.gpu_util}%, "
                        f"VRAM: {gpu.vram_used_gb:.1f}/{gpu.vram_total_gb:.1f} GB\n"
                    )

        if status.status == "completed":
            response += "\n작업 완료!"
            if save_result_path:
                response += f"\n저장 경로: {save_result_path}"

        elif status.status == "failed":
            response += f"\n❌ 작업 실패: {status.message}"

        return response

    except AIServerError as e:
        logger.error(f"AI 서버 에러: {e}")
        return f"AI 서버 에러: {str(e)}"


async def stop_generation(job_id: str) -> str:
    """
    현재 실행 중이거나 대기 중인 광고 생성 작업을 강제로 중단합니다.

    사용 시나리오:
    - 잘못된 파라미터로 실행한 작업을 취소
    - 시간이 너무 오래 걸리는 작업을 중단
    - 사용자가 다른 작업을 실행하고 싶을 때 기존 작업 취소
    - GPU 리소스를 즉시 해제해야 할 때

    주의사항:
    - 이미 완료된 작업은 중단할 수 없음
    - 중단된 작업은 재개할 수 없음 (처음부터 다시 실행 필요)
    - 중단 후에도 job_id로 상태 조회는 가능 (status="stopped")

    Args:
        job_id: 중단할 작업의 고유 ID
            - generate_ad_image 또는 기타 생성 도구에서 반환된 ID
            - 예시: "job-20260107-abc123"

    Returns:
        중단 결과 메시지 (작업 ID, 최종 상태)
    """
    try:
        client = await get_api_client()
        result = await client.stop_job(job_id)
        return f"작업 중단 요청 완료\n작업 ID: {result.job_id}\n상태: {result.status}"

    except AIServerError as e:
        return f"AI 서버 에러: {str(e)}"


async def list_available_fonts() -> str:
    """
    AI 서버에 설치되어 있어 3D 텍스트 생성에 사용 가능한 폰트 목록을 조회합니다.

    사용 시나리오:
    - generate_ad_image를 호출하기 전에 사용 가능한 폰트 확인
    - 한글 텍스트를 사용할 경우 한글 폰트 존재 여부 확인
    - 특정 스타일(손글씨, 고딕, 명조 등)의 폰트 검색

    폰트 선택 가이드:
    - 한글 텍스트: 한글을 지원하는 폰트 필수 (예: NanumGothic, NanumMyeongjo)
    - 영문 텍스트: 모든 폰트 사용 가능
    - 광고 스타일별 권장:
      * 프로모션/세일: 굵고 임팩트 있는 폰트 (예: Gothic, Bold)
      * 고급/럭셔리: 얇고 우아한 폰트 (예: Serif, Light)
      * 친근한/캐주얼: 손글씨 스타일 폰트

    Returns:
        사용 가능한 폰트 목록 (폰트명 리스트)

    사용 예시:
        1. fonts = list_available_fonts()
        2. 원하는 폰트명 선택 (예: "NanumGothicBold.ttf")
        3. generate_ad_image(..., font_name="NanumGothicBold.ttf")
    """
    try:
        client = await get_api_client()
        fonts = await client.get_fonts()

        response = f"사용 가능한 폰트 ({len(fonts)}개):\n\n"
        for font in fonts:
            response += f"  - {font}\n"

        return response

    except AIServerError as e:
        return f"AI 서버 에러: {str(e)}"


async def get_fonts_metadata() -> str:
    """
    AI 서버에서 사용 가능한 폰트의 상세 메타데이터를 조회합니다.

    각 폰트의 스타일, 굵기, 적합한 용도, 톤앤매너 정보를 포함하여
    LLM이 광고 콘텐츠에 적합한 폰트를 자동으로 선택할 수 있도록 합니다.

    반환 정보:
    - name: 폰트 파일 경로
    - style: 폰트 스타일 (gothic/serif/handwriting/mono)
    - weight: 굵기 (light/regular/bold/extrabold/heavy)
    - usage: 적합한 용도 (title/body/promotion/sale/premium/accent/casual/code/technical)
    - tone: 톤앤매너 (modern/clean/professional/energetic/elegant/traditional/sophisticated/friendly/warm/personal/tech)

    사용 시나리오:
    - 광고 텍스트와 브랜드 톤에 맞는 폰트 자동 선택
    - "세일 광고에 어울리는 굵고 임팩트 있는 폰트"처럼 조건에 맞는 폰트 추천
    - "우아하고 고급스러운 느낌의 폰트"같은 톤앤매너 기반 선택
    - 한글 텍스트 사용 시 한글 지원 폰트 필터링

    Returns:
        폰트 메타데이터 목록 (JSON 형식 문자열)

    사용 예시:
        1. metadata = get_fonts_metadata()
        2. 조건에 맞는 폰트 선택 (예: style="gothic", weight="bold", "sale" in usage)
        3. generate_ad_image(..., font_name=selected_font)
    """
    try:
        client = await get_api_client()
        metadata = await client.get_fonts_metadata()

        import json

        return json.dumps(metadata, ensure_ascii=False, indent=2)

    except AIServerError as e:
        return f"AI 서버 에러: {str(e)}"


async def recommend_font_for_ad(
    text_content: str,
    ad_type: str = "general",
    tone: Optional[str] = None,
    weight_preference: Optional[str] = None,
) -> str:
    """
    광고 콘텐츠에 적합한 폰트를 자동으로 추천합니다.

    광고 텍스트, 광고 유형, 원하는 톤앤매너를 기반으로
    가장 적합한 폰트를 선택하여 반환합니다.

    Args:
        text_content: 광고에 사용할 텍스트 (한글/영문 구분용)
        ad_type: 광고 유형
            - "sale": 세일/할인 (굵고 임팩트 있는 폰트)
            - "premium": 프리미엄/고급 (우아하고 세련된 폰트)
            - "casual": 캐주얼/친근 (손글씨 스타일)
            - "promotion": 일반 프로모션 (깔끔한 고딕체)
            - "general": 일반 광고 (기본 폰트)
        tone: 원하는 톤앤매너 (선택사항)
            - "energetic": 활동적/역동적
            - "elegant": 우아한/고급스러운
            - "friendly": 친근한/따뜻한
            - "modern": 현대적/깔끔한
            - "traditional": 전통적/클래식
        weight_preference: 선호하는 굵기 (선택사항)
            - "light": 얇은 폰트
            - "bold": 굵은 폰트
            - "heavy": 매우 굵은 폰트

    Returns:
        추천 폰트 이름과 선택 이유

    사용 예시:
        1. font = recommend_font_for_ad("50% 할인", ad_type="sale", weight_preference="bold")
        2. generate_ad_image(..., font_name=font)
    """
    try:
        client = await get_api_client()
        metadata = await client.get_fonts_metadata()

        if not metadata:
            return "폰트 메타데이터를 가져올 수 없습니다."

        # 한글 텍스트 판별
        has_korean = any("\uac00" <= char <= "\ud7a3" for char in text_content)

        # 필터링: 영문 전용 폰트 제외 (한글 텍스트인 경우)
        if has_korean:
            # 코딩 폰트(D2Coding) 제외
            candidates = [f for f in metadata if "d2coding" not in f["name"].lower()]
        else:
            candidates = metadata

        if not candidates:
            return "조건에 맞는 폰트를 찾을 수 없습니다."

        # 광고 유형별 필터링
        if ad_type == "sale":
            # 세일: 굵고 임팩트 있는 gothic
            candidates = [
                f
                for f in candidates
                if f["style"] == "gothic"
                and f["weight"] in ["bold", "extrabold", "heavy"]
                and "sale" in f["usage"]
            ]
        elif ad_type == "premium":
            # 프리미엄: 세리프 또는 가벼운 폰트
            candidates = [
                f
                for f in candidates
                if (f["style"] == "serif" or f["weight"] in ["light", "regular"])
                and "premium" in f["usage"]
            ]
        elif ad_type == "casual":
            # 캐주얼: 손글씨
            candidates = [f for f in candidates if f["style"] == "handwriting"]
        elif ad_type == "promotion":
            # 프로모션: 깔끔한 고딕
            candidates = [
                f
                for f in candidates
                if f["style"] == "gothic" and "promotion" in f["usage"]
            ]

        # 톤앤매너 필터링
        if tone and candidates:
            tone_filtered = [f for f in candidates if tone in f["tone"]]
            if tone_filtered:
                candidates = tone_filtered

        # 굵기 선호도 필터링
        if weight_preference and candidates:
            weight_filtered = [
                f for f in candidates if f["weight"] == weight_preference
            ]
            if weight_filtered:
                candidates = weight_filtered

        # 최종 선택
        if not candidates:
            # 필터 조건에 맞는 폰트가 없으면 기본 추천
            if has_korean:
                default_fonts = [
                    f
                    for f in metadata
                    if "gothic" in f["name"].lower() or "고딕" in f["name"]
                ]
                if default_fonts:
                    selected = default_fonts[0]
                else:
                    selected = metadata[0]
            else:
                selected = metadata[0]
            reason = "조건에 정확히 맞는 폰트가 없어 기본 폰트를 선택했습니다."
        else:
            # 첫 번째 후보 선택
            selected = candidates[0]
            reason = f"광고 유형({ad_type}), 스타일({selected['style']}), 굵기({selected['weight']})를 고려하여 선택했습니다."

        return (
            f"추천 폰트: {selected['name']}\n"
            f"스타일: {selected['style']}\n"
            f"굵기: {selected['weight']}\n"
            f"용도: {', '.join(selected['usage'])}\n"
            f"톤: {', '.join(selected['tone'])}\n"
            f"선택 이유: {reason}"
        )

    except AIServerError as e:
        return f"AI 서버 에러: {str(e)}"
    except Exception as e:
        logger.exception(f"폰트 추천 중 에러: {e}")
        return f"폰트 추천 중 에러 발생: {str(e)}"


async def get_all_jobs() -> str:
    """
    AI 서버에 등록된 모든 작업 목록을 조회합니다.

    사용 시나리오:
    - 현재 실행 중인 작업 확인
    - 대기 중인 작업 확인
    - 완료/실패한 작업 이력 조회
    - 작업 정리 전 확인

    Returns:
        전체 작업 목록 및 각 작업의 상태 (pending/running/completed/failed)
    """
    try:
        client = await get_api_client()
        jobs = await client.list_jobs()

        if not jobs.jobs:
            return "등록된 작업이 없습니다."

        response = f"전체 작업 수: {len(jobs.jobs)}개\n\n"
        for job in jobs.jobs:
            response += (
                f"작업 ID: {job.job_id}\n"
                f"  상태: {job.status}\n"
                f"  진행률: {job.progress}%\n"
                f"  생성 시각: {job.created_at}\n"
            )
            if job.completed_at:
                response += f"  완료 시각: {job.completed_at}\n"
            if job.error:
                response += f"  에러: {job.error}\n"
            response += "\n"

        return response

    except AIServerError as e:
        return f"AI 서버 에러: {str(e)}"
    except Exception as e:
        logger.exception(f"작업 목록 조회 중 에러: {e}")
        return f"작업 목록 조회 중 에러 발생: {str(e)}"


async def delete_all_jobs() -> str:
    """
    완료되었거나 실패한 모든 작업을 삭제합니다.
    실행 중(running)이거나 대기 중(pending)인 작업은 삭제하지 않습니다.

    사용 시나리오:
    - 테스트 후 작업 이력 정리
    - 완료된 작업 목록 초기화
    - 서버 메모리 정리

    주의사항:
    - 실행/대기 중인 작업은 자동으로 건너뜁니다
    - 삭제된 작업은 복구할 수 없습니다
    - 이미지 파일은 삭제되지 않고 작업 기록만 삭제됩니다

    Returns:
        삭제된 작업 수 및 건너뛴 작업 정보
    """
    try:
        client = await get_api_client()
        jobs = await client.list_jobs()

        if not jobs.jobs:
            return "삭제할 작업이 없습니다."

        deleted_count = 0
        skipped_count = 0
        errors = []

        for job in jobs.jobs:
            # 실행/대기 중인 작업은 건너뛰기
            if job.status in ["pending", "running"]:
                skipped_count += 1
                logger.info(
                    f"실행/대기 중인 작업 건너뜀: {job.job_id} (상태: {job.status})"
                )
                continue

            try:
                await client.delete_job(job.job_id)
                deleted_count += 1
                logger.info(f"작업 삭제 완료: {job.job_id}")
            except Exception as e:
                errors.append(f"{job.job_id}: {str(e)}")
                logger.error(f"작업 삭제 실패: {job.job_id}, 에러: {e}")

        response = f"작업 정리 완료\n"
        response += f"  삭제됨: {deleted_count}개\n"
        response += f"  건너뜀 (실행/대기 중): {skipped_count}개\n"

        if errors:
            response += f"\n삭제 실패:\n"
            for error in errors:
                response += f"  - {error}\n"

        return response

    except AIServerError as e:
        return f"AI 서버 에러: {str(e)}"
    except Exception as e:
        logger.exception(f"작업 삭제 중 에러: {e}")
        return f"작업 삭제 중 에러 발생: {str(e)}"


async def delete_job(job_id: str) -> str:
    """
    특정 작업을 삭제합니다.

    완료되었거나 실패한 작업만 삭제할 수 있습니다.
    실행 중이거나 대기 중인 작업은 먼저 중단해야 합니다.

    사용 시나리오:
    - 특정 작업의 결과를 다운로드한 후 메모리 정리
    - 실패한 작업 기록 제거
    - 불필요한 작업 개별 삭제

    주의사항:
    - 실행/대기 중인 작업은 삭제할 수 없습니다
    - 삭제된 작업은 복구할 수 없습니다

    Args:
        job_id: 삭제할 작업의 고유 ID

    Returns:
        삭제 결과 메시지
    """
    try:
        client = await get_api_client()
        result = await client.delete_job(job_id)
        return f"작업 삭제 완료\n작업 ID: {job_id}\n상태: {result.get('status', 'deleted')}"

    except AIServerError as e:
        return f"AI 서버 에러: {str(e)}"
    except Exception as e:
        logger.exception(f"작업 삭제 중 에러: {e}")
        return f"작업 삭제 중 에러 발생: {str(e)}"


async def check_server_health() -> str:
    """
    AI 서버가 정상적으로 실행 중인지 확인하고 시스템 리소스 사용 현황을 조회합니다.

    사용 시나리오:
    - 광고 생성 전 AI 서버 연결 상태 확인
    - GPU 메모리가 충분한지 사전 체크
    - 서버 과부하 상태 확인 (여러 작업 동시 실행 중인지)
    - 에러 발생 시 서버 문제인지 디버깅

    반환 정보:
    - 서버 상태 (healthy/unhealthy)
    - 전체 작업 수 및 현재 실행 중인 작업 수
    - CPU 사용률 (%)
    - RAM 사용량 (GB) 및 사용률 (%)
    - GPU 사용률 (%) 및 VRAM 사용량 (GB) - GPU가 있는 경우

    정상 상태 기준:
    - status: "healthy"
    - active_jobs: 0~2개 (동시 작업이 많으면 느려질 수 있음)
    - GPU VRAM: 12GB 이상 여유 (Flux 모델 실행에 필요)

    Returns:
        서버 상태 및 시스템 리소스 정보 텍스트

    사용 예시:
        작업 전에 항상 check_server_health()를 호출하여 서버가 준비되었는지 확인하세요.
    """
    try:
        client = await get_api_client()
        health = await client.check_health()

        response = (
            f"서버 상태: {health.status}\n"
            f"전체 작업: {health.total_jobs}개\n"
            f"활성 작업: {health.active_jobs}개\n"
        )

        if health.system_metrics:
            metrics = health.system_metrics
            response += (
                f"\n시스템 리소스:\n"
                f"  CPU: {metrics.cpu_percent:.1f}%\n"
                f"  RAM: {metrics.ram_used_gb:.1f}/{metrics.ram_total_gb:.1f} GB "
                f"({metrics.ram_percent:.1f}%)\n"
            )
            if metrics.gpu_info:
                for gpu in metrics.gpu_info:
                    response += (
                        f"  GPU {gpu.index} ({gpu.name}): {gpu.gpu_util}%, "
                        f"VRAM: {gpu.vram_used_gb:.1f}/{gpu.vram_total_gb:.1f} GB\n"
                    )

        return response

    except AIServerError as e:
        return f"AI 서버 에러: {str(e)}"


async def generate_background_only(
    product_image_path: str,
    background_prompt: str,
    background_negative_prompt: Optional[str] = None,
    strength: float = 0.6,
    guidance_scale: float = 3.5,
    seed: Optional[int] = None,
    wait_for_completion: bool = True,
    save_output_path: Optional[str] = None,
) -> str:
    """
    [고급 기능] Step 1만 실행 - 제품 이미지와 배경을 AI로 합성합니다.

    이 도구는 텍스트 없이 배경만 생성하거나, 3단계 파이프라인을 단계별로 제어하고 싶을 때 사용합니다.
    일반적인 광고 생성에는 generate_ad_image를 사용하세요.

    사용 시나리오:
    - 텍스트 없이 제품 이미지 + 배경만 조합하고 싶을 때
    - 배경 생성 결과를 먼저 확인하고 Step 2, 3를 별도로 실행
    - 배경 파라미터 (strength, guidance_scale)를 세밀하게 튜닝
    - A/B 테스트를 위해 다양한 배경 스타일 비교

    Args:
        product_image_path: 제품 이미지 파일의 절대 경로
            - generate_ad_image의 product_image_path와 동일

        background_prompt: 배경에 대한 영문 설명 (프롬프트)
            - generate_ad_image의 background_prompt와 동일
            - 예시: "Luxury studio background, soft lighting, golden hour"

        background_negative_prompt: 배경에서 제외하고 싶은 요소 설명 (선택사항)
            - 원하지 않는 요소를 명시하여 품질 향상
            - 예시: "text, watermark, low quality, blurry, distorted"
            - 예시: "people, faces, logos"

        strength: 제품 이미지를 변환하는 강도 (0.0 ~ 1.0, 기본값: 0.6)
            - 0.0: 원본 이미지를 거의 유지 (배경 변화 최소)
            - 0.5: 균형있는 합성 (권장)
            - 1.0: 원본 이미지를 크게 변형 (배경 변화 최대)

        guidance_scale: 프롬프트 가이던스 강도 (1.0 ~ 20.0, 기본값: 3.5)
            - 낮을수록: 더 자연스럽고 창의적인 결과 (1.0 ~ 3.0)
            - 높을수록: 프롬프트에 더 충실한 결과 (5.0 ~ 10.0)
            - 너무 높으면 부자연스러운 결과 발생 가능 (10.0+)

        seed: 랜덤 시드 (재현성 보장)
            - generate_ad_image의 seed와 동일

        wait_for_completion: 완료까지 대기 여부
            - generate_ad_image의 wait_for_completion과 동일

        save_output_path: 결과 배경 이미지 저장 경로 (선택사항)
            - 이 파일을 generate_text_asset_only의 step1_image_path로 사용 가능

    Returns:
        배경 생성 결과 메시지 (job_id, 소요 시간 등)

    다음 단계:
        이 도구로 Step 1을 완료한 후:
        1. generate_text_asset_only로 Step 2 실행 (3D 텍스트 생성)
        2. compose_final_image로 Step 3 실행 (최종 합성)
    """
    try:
        client = await get_api_client()
        product_image_b64 = image_file_to_base64(product_image_path)

        params = GenerateRequest(
            start_step=1,
            input_image=product_image_b64,
            bg_prompt=background_prompt,
            bg_negative_prompt=background_negative_prompt or "",
            text_content=None,  # 텍스트 없음
            strength=strength,
            guidance_scale=guidance_scale,
            seed=seed,
        )

        if wait_for_completion:
            result = await client.generate_and_wait(params)

            if save_output_path and result.step1_result:
                output_path = base64_to_image_file(
                    result.step1_result, save_output_path, overwrite=True
                )
                logger.info(f"배경 이미지 저장: {output_path}")

            response = (
                f"배경 생성 완료!\n"
                f"작업 ID: {result.job_id}\n"
                f"소요 시간: {result.elapsed_sec:.1f}초\n"
            )
            if save_output_path:
                response += f"\n저장 경로: {save_output_path}"

            return response
        else:
            response = await client.start_generation(params)
            return f"배경 생성 시작\n작업 ID: {response.job_id}"

    except Exception as e:
        logger.exception(f"에러: {e}")
        return f"에러 발생: {str(e)}"


async def generate_text_asset_only(
    step1_image_base64: Optional[str] = None,
    step1_image_path: Optional[str] = None,
    text_content: str = "",
    text_style_prompt: str = "",
    font_name: Optional[str] = None,
    negative_prompt: Optional[str] = None,
    seed: Optional[int] = None,
    wait_for_completion: bool = True,
    save_output_path: Optional[str] = None,
) -> str:
    """
    [고급 기능] Step 2만 실행 - 배경 이미지 위에 3D 텍스트 에셋을 AI로 생성합니다.

    이 도구는 이미 배경이 준비된 상태에서 텍스트만 생성하거나,
    3단계 파이프라인을 단계별로 제어하고 싶을 때 사용합니다.
    일반적인 광고 생성에는 generate_ad_image를 사용하세요.

    사용 시나리오:
    - generate_background_only로 생성한 배경에 텍스트를 추가
    - 다양한 텍스트 스타일을 동일한 배경에 적용하여 A/B 테스트
    - 텍스트 생성 파라미터 (text_style_prompt, font_name)를 세밀하게 튜닝
    - 외부에서 제작한 배경 이미지에 AI 텍스트 추가

    Args:
        step1_image_base64: Step 1에서 생성된 배경 이미지 (Base64 문자열)
            - generate_background_only의 반환 결과에서 추출
            - 또는 외부에서 Base64로 인코딩한 이미지
            - step1_image_path와 둘 중 하나는 필수

        step1_image_path: 또는 Step 1 배경 이미지 파일 경로
            - generate_background_only의 save_output_path로 저장한 파일 경로
            - 또는 외부에서 준비한 배경 이미지 파일 경로
            - step1_image_base64와 둘 중 하나는 필수

        text_content: 렌더링할 텍스트 내용
            - generate_ad_image의 text_content와 동일
            - 예시: "SALE", "NEW", "특가 2500원"

        text_style_prompt: 3D 텍스트의 시각적 스타일 설명 (영문)
            - generate_ad_image의 text_style_prompt와 동일
            - 예시: "3D gold foil balloon text, shiny metallic surface"

        font_name: 텍스트 렌더링에 사용할 폰트 파일명 (선택사항)
            - list_available_fonts로 확인 가능

        negative_prompt: 텍스트 생성에서 제외할 요소 설명 (선택사항)
            - 예시: "flat, 2D, low quality, distorted letters"

        seed: 랜덤 시드 (재현성 보장)

        wait_for_completion: 완료까지 대기 여부

        save_output_path: 생성된 3D 텍스트 이미지 저장 경로 (선택사항)
            - 이 파일을 compose_final_image의 step2_image_path로 사용 가능

    Returns:
        3D 텍스트 생성 결과 메시지 (job_id, 소요 시간 등)

    주의사항:
        - step1_image_base64와 step1_image_path 중 하나는 반드시 제공해야 함
        - 둘 다 제공하면 step1_image_base64가 우선

    다음 단계:
        이 도구로 Step 2를 완료한 후:
        compose_final_image로 Step 3 실행 (배경 + 텍스트 최종 합성)
    """
    try:
        client = await get_api_client()

        # step1_image 획득
        step1_img_b64 = step1_image_base64
        if not step1_img_b64 and step1_image_path:
            step1_img_b64 = image_file_to_base64(step1_image_path)

        if not step1_img_b64:
            return (
                "에러: step1_image_base64 또는 step1_image_path 중 하나는 필수입니다."
            )

        params = GenerateRequest(
            start_step=2,
            step1_image=step1_img_b64,
            text_content=text_content,
            text_model_prompt=text_style_prompt,
            font_name=font_name,
            negative_prompt=negative_prompt or "",
            seed=seed,
        )

        if wait_for_completion:
            result = await client.generate_and_wait(params)

            if save_output_path and result.step2_result:
                output_path = base64_to_image_file(
                    result.step2_result, save_output_path, overwrite=True
                )
                logger.info(f"3D 텍스트 저장: {output_path}")

            response = (
                f"3D 텍스트 생성 완료!\n"
                f"작업 ID: {result.job_id}\n"
                f"소요 시간: {result.elapsed_sec:.1f}초\n"
            )
            if save_output_path:
                response += f"\n저장 경로: {save_output_path}"

            return response
        else:
            response = await client.start_generation(params)
            return f"3D 텍스트 생성 시작\n작업 ID: {response.job_id}"

    except Exception as e:
        logger.exception(f"에러: {e}")
        return f"에러 발생: {str(e)}"


async def compose_final_image(
    step1_image_base64: Optional[str] = None,
    step1_image_path: Optional[str] = None,
    step2_image_base64: Optional[str] = None,
    step2_image_path: Optional[str] = None,
    composition_mode: str = "overlay",
    text_position: str = "auto",
    composition_strength: float = 0.4,
    composition_steps: int = 28,
    composition_guidance_scale: float = 3.5,
    wait_for_completion: bool = True,
    save_output_path: Optional[str] = None,
) -> str:
    """
    [고급 기능] Step 3만 실행 - 배경 이미지와 3D 텍스트를 AI로 자연스럽게 합성합니다.

    이 도구는 Step 1 (배경)과 Step 2 (3D 텍스트)가 이미 완료된 상태에서
    최종 합성만 수행하거나, 3단계 파이프라인을 단계별로 제어하고 싶을 때 사용합니다.
    일반적인 광고 생성에는 generate_ad_image를 사용하세요.

    사용 시나리오:
    - generate_background_only와 generate_text_asset_only로 생성한 이미지를 최종 합성
    - 다양한 합성 모드를 비교하여 A/B 테스트
    - 합성 파라미터를 세밀하게 튜닝하여 최적의 결과 도출
    - 외부에서 제작한 배경과 텍스트를 AI로 합성

    Args:
        step1_image_base64: 배경 이미지 (Base64 문자열)
            - generate_background_only의 결과
            - step1_image_path와 둘 중 하나는 필수

        step1_image_path: 또는 배경 이미지 파일 경로
            - generate_background_only의 save_output_path
            - step1_image_base64와 둘 중 하나는 필수

        step2_image_base64: 3D 텍스트 이미지 (Base64 문자열)
            - generate_text_asset_only의 결과
            - step2_image_path와 둘 중 하나는 필수

        step2_image_path: 또는 3D 텍스트 이미지 파일 경로
            - generate_text_asset_only의 save_output_path
            - step2_image_base64와 둘 중 하나는 필수

        composition_mode: 합성 방식 (기본값: "overlay")
            - "overlay": 텍스트를 배경 위에 오버레이 (가장 일반적, 권장)
                * 텍스트가 배경 위에 명확하게 표시됨
                * 세일, 프로모션 광고에 적합
            - "blend": 텍스트와 배경을 부드럽게 블렌딩
                * 자연스럽고 예술적인 분위기
                * 명품, 럭셔리 광고에 적합
            - "behind": 텍스트가 배경 뒤에 있는 것처럼 합성
                * 깊이감과 입체감 연출
                * 창의적이고 독특한 디자인에 적합

        text_position: 텍스트 배치 위치 (기본값: "auto")
            - "auto": AI가 자동으로 최적 위치 결정 (권장)
            - "top": 이미지 상단
            - "center": 이미지 중앙
            - "bottom": 이미지 하단

        composition_strength: 합성 변환 강도 (0.0 ~ 1.0, 기본값: 0.4)
            - 0.0 ~ 0.3: 원본을 거의 유지한 채 가볍게 합성 (자연스러움)
            - 0.3 ~ 0.5: 균형있는 합성 (권장 범위)
            - 0.5 ~ 1.0: 강한 합성 효과 (예술적, 주의 필요)

        composition_steps: 합성 AI 추론 스텝 수 (10 ~ 50, 기본값: 28)
            - 10 ~ 20: 빠르지만 품질이 낮을 수 있음
            - 20 ~ 35: 균형있는 품질과 속도 (권장)
            - 35 ~ 50: 고품질이지만 느림

        composition_guidance_scale: 합성 가이던스 강도 (1.0 ~ 7.0, 기본값: 3.5)
            - 1.0 ~ 3.0: 자연스럽고 부드러운 합성
            - 3.0 ~ 5.0: 균형있는 합성 (권장)
            - 5.0 ~ 7.0: 명확하고 선명한 합성

        wait_for_completion: 완료까지 대기 여부

        save_output_path: 최종 광고 이미지 저장 경로 (선택사항)
            - 이것이 최종 산출물입니다

    Returns:
        최종 합성 결과 메시지 (job_id, 소요 시간 등)

    주의사항:
        - step1_image와 step2_image를 모두 제공해야 함
        - Base64와 파일 경로를 혼용하여 사용 가능
        - 각 이미지의 Base64가 우선

    튜닝 팁:
        1. 먼저 기본값으로 테스트
        2. composition_mode를 변경하여 비교 (overlay/blend/behind)
        3. composition_strength로 합성 강도 조정
        4. composition_guidance_scale로 선명도 조정
    """
    try:
        client = await get_api_client()

        # step1_image 획득
        step1_img_b64 = step1_image_base64
        if not step1_img_b64 and step1_image_path:
            step1_img_b64 = image_file_to_base64(step1_image_path)

        # step2_image 획득
        step2_img_b64 = step2_image_base64
        if not step2_img_b64 and step2_image_path:
            step2_img_b64 = image_file_to_base64(step2_image_path)

        if not step1_img_b64 or not step2_img_b64:
            return "에러: step1_image와 step2_image가 모두 필요합니다."

        params = GenerateRequest(
            start_step=3,
            step1_image=step1_img_b64,
            step2_image=step2_img_b64,
            composition_mode=composition_mode,
            text_position=text_position,
            composition_strength=composition_strength,
            composition_steps=composition_steps,
            composition_guidance_scale=composition_guidance_scale,
        )

        if wait_for_completion:
            result = await client.generate_and_wait(params)

            if save_output_path and result.final_result:
                output_path = base64_to_image_file(
                    result.final_result, save_output_path, overwrite=True
                )
                logger.info(f"최종 이미지 저장: {output_path}")

            response = (
                f"최종 합성 완료!\n"
                f"작업 ID: {result.job_id}\n"
                f"소요 시간: {result.elapsed_sec:.1f}초\n"
            )
            if save_output_path:
                response += f"\n저장 경로: {save_output_path}"

            return response
        else:
            response = await client.start_generation(params)
            return f"최종 합성 시작\n작업 ID: {response.job_id}"

    except Exception as e:
        logger.exception(f"에러: {e}")
        return f"에러 발생: {str(e)}"


# =============================================================================
# OpenAI Function Calling Schema 정의
# =============================================================================

TOOL_SCHEMAS = [
    {
        "name": "generate_ad_image",
        "description": "제품 이미지를 기반으로 AI가 전문적인 광고 이미지를 생성합니다. 3단계 파이프라인(배경 생성 → 3D 텍스트 생성 → 최종 합성)을 자동으로 실행합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_image_path": {
                    "type": "string",
                    "description": "제품 이미지 파일의 절대 경로 (PNG, JPG, JPEG, WEBP 지원)",
                },
                "background_prompt": {
                    "type": "string",
                    "description": "생성할 배경에 대한 영문 설명 (예: 'Colorful party balloons and confetti, festive atmosphere')",
                },
                "text_content": {
                    "type": "string",
                    "description": "광고에 표시할 텍스트 내용 (예: 'SALE', '50% OFF', '특가 2500원')",
                },
                "text_style_prompt": {
                    "type": "string",
                    "description": "3D 텍스트의 시각적 스타일 설명 (예: '3D render of gold foil balloon text, shiny metallic texture')",
                },
                "font_name": {
                    "type": "string",
                    "description": "텍스트 렌더링에 사용할 폰트 파일명 (선택사항, list_available_fonts로 확인 가능)",
                },
                "composition_mode": {
                    "type": "string",
                    "description": "배경과 텍스트 합성 방식 ('overlay', 'blend', 'behind' 중 선택, 기본값: 'overlay')",
                    "default": "overlay",
                },
                "text_position": {
                    "type": "string",
                    "description": "텍스트 배치 위치 ('auto', 'top', 'center', 'bottom' 중 선택, 기본값: 'auto')",
                    "default": "auto",
                },
                "seed": {
                    "type": "integer",
                    "description": "재현성을 위한 랜덤 시드 (선택사항)",
                },
                "test_mode": {
                    "type": "boolean",
                    "description": "더미 데이터 테스트 모드 (기본값: false)",
                    "default": False,
                },
                "wait_for_completion": {
                    "type": "boolean",
                    "description": "생성 완료까지 대기 여부 (기본값: true)",
                    "default": True,
                },
                "save_output_path": {
                    "type": "string",
                    "description": "생성된 이미지를 저장할 파일 경로 (선택사항)",
                },
            },
            "required": [
                "product_image_path",
                "background_prompt",
                "text_content",
                "text_style_prompt",
            ],
        },
    },
    {
        "name": "check_generation_status",
        "description": "비동기로 시작된 광고 생성 작업의 현재 진행 상태를 확인합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "확인할 작업의 고유 ID (generate_ad_image 호출 시 반환된 ID)",
                },
                "save_result_path": {
                    "type": "string",
                    "description": "작업이 완료된 경우 결과 이미지를 저장할 파일 경로 (선택사항)",
                },
            },
            "required": ["job_id"],
        },
    },
    {
        "name": "stop_generation",
        "description": "실행 중인 광고 생성 작업을 강제로 중단합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "중단할 작업의 고유 ID",
                }
            },
            "required": ["job_id"],
        },
    },
    {
        "name": "list_available_fonts",
        "description": "텍스트 렌더링에 사용할 수 있는 폰트 목록을 반환합니다.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_fonts_metadata",
        "description": "폰트별 상세 메타데이터(스타일, 굵기, 용도, 톤앤매너)를 조회하여 광고 콘텐츠에 적합한 폰트를 선택할 수 있습니다.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "recommend_font_for_ad",
        "description": "광고 콘텐츠와 유형에 따라 적합한 폰트를 자동으로 추천합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "text_content": {
                    "type": "string",
                    "description": "광고에 사용할 텍스트 (한글/영문 구분용)",
                },
                "ad_type": {
                    "type": "string",
                    "description": "광고 유형 (sale/premium/casual/promotion/general)",
                    "default": "general",
                },
                "tone": {
                    "type": "string",
                    "description": "원하는 톤앤매너 (energetic/elegant/friendly/modern/traditional)",
                },
                "weight_preference": {
                    "type": "string",
                    "description": "선호하는 굵기 (light/bold/heavy)",
                },
            },
            "required": ["text_content"],
        },
    },
    {
        "name": "check_server_health",
        "description": "AI 서버의 현재 상태와 시스템 리소스 사용량을 확인합니다.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_all_jobs",
        "description": "AI 서버에 등록된 모든 작업 목록을 조회합니다.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "delete_all_jobs",
        "description": "완료되었거나 실패한 모든 작업을 삭제합니다. 실행/대기 중인 작업은 건너뜁니다.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "delete_job",
        "description": "특정 작업을 삭제합니다. 완료/실패한 작업만 삭제 가능합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "삭제할 작업의 고유 ID",
                }
            },
            "required": ["job_id"],
        },
    },
    {
        "name": "generate_background_only",
        "description": "제품 이미지에 AI 배경만 생성합니다 (Step 1만 실행).",
        "parameters": {
            "type": "object",
            "properties": {
                "product_image_path": {
                    "type": "string",
                    "description": "제품 이미지 파일의 절대 경로",
                },
                "background_prompt": {
                    "type": "string",
                    "description": "생성할 배경에 대한 영문 설명",
                },
                "seed": {
                    "type": "integer",
                    "description": "재현성을 위한 랜덤 시드 (선택사항)",
                },
                "test_mode": {
                    "type": "boolean",
                    "description": "더미 데이터 테스트 모드",
                    "default": False,
                },
                "save_output_path": {
                    "type": "string",
                    "description": "결과 이미지를 저장할 파일 경로 (선택사항)",
                },
            },
            "required": ["product_image_path", "background_prompt"],
        },
    },
    {
        "name": "generate_text_asset_only",
        "description": "3D 텍스트 에셋만 생성합니다 (Step 2만 실행).",
        "parameters": {
            "type": "object",
            "properties": {
                "text_content": {
                    "type": "string",
                    "description": "생성할 텍스트 내용",
                },
                "text_style_prompt": {
                    "type": "string",
                    "description": "3D 텍스트의 시각적 스타일 설명",
                },
                "font_name": {
                    "type": "string",
                    "description": "텍스트 렌더링에 사용할 폰트 파일명 (선택사항)",
                },
                "seed": {
                    "type": "integer",
                    "description": "재현성을 위한 랜덤 시드 (선택사항)",
                },
                "test_mode": {
                    "type": "boolean",
                    "description": "더미 데이터 테스트 모드",
                    "default": False,
                },
                "save_output_path": {
                    "type": "string",
                    "description": "결과 이미지를 저장할 파일 경로 (선택사항)",
                },
            },
            "required": ["text_content", "text_style_prompt"],
        },
    },
    {
        "name": "compose_final_image",
        "description": "배경 이미지와 텍스트 에셋을 합성하여 최종 광고 이미지를 생성합니다 (Step 3만 실행).",
        "parameters": {
            "type": "object",
            "properties": {
                "step1_image": {
                    "type": "string",
                    "description": "배경 이미지 Base64 문자열 (step1_image_path와 둘 중 하나 필수)",
                },
                "step1_image_path": {
                    "type": "string",
                    "description": "배경 이미지 파일 경로 (step1_image와 둘 중 하나 필수)",
                },
                "step2_image": {
                    "type": "string",
                    "description": "텍스트 에셋 Base64 문자열 (step2_image_path와 둘 중 하나 필수)",
                },
                "step2_image_path": {
                    "type": "string",
                    "description": "텍스트 에셋 파일 경로 (step2_image와 둘 중 하나 필수)",
                },
                "composition_mode": {
                    "type": "string",
                    "description": "합성 방식 ('overlay', 'blend', 'behind' 중 선택)",
                    "default": "overlay",
                },
                "text_position": {
                    "type": "string",
                    "description": "텍스트 배치 위치 ('auto', 'top', 'center', 'bottom' 중 선택)",
                    "default": "auto",
                },
                "composition_strength": {
                    "type": "number",
                    "description": "합성 강도 (0.0~1.0, 기본값: 0.8)",
                    "default": 0.8,
                },
                "composition_steps": {
                    "type": "integer",
                    "description": "합성 반복 횟수 (기본값: 30)",
                    "default": 30,
                },
                "composition_guidance_scale": {
                    "type": "number",
                    "description": "합성 가이던스 스케일 (기본값: 7.5)",
                    "default": 7.5,
                },
                "save_output_path": {
                    "type": "string",
                    "description": "결과 이미지를 저장할 파일 경로 (선택사항)",
                },
            },
            "required": [],
        },
    },
]

# Tool name → function mapping
TOOL_FUNCTIONS = {
    "generate_ad_image": generate_ad_image,
    "check_generation_status": check_generation_status,
    "stop_generation": stop_generation,
    "list_available_fonts": list_available_fonts,
    "get_fonts_metadata": get_fonts_metadata,
    "recommend_font_for_ad": recommend_font_for_ad,
    "check_server_health": check_server_health,
    "get_all_jobs": get_all_jobs,
    "delete_all_jobs": delete_all_jobs,
    "delete_job": delete_job,
    "generate_background_only": generate_background_only,
    "generate_text_asset_only": generate_text_asset_only,
    "compose_final_image": compose_final_image,
}


# =============================================================================
# REST API 엔드포인트
# =============================================================================


@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    return {
        "status": "healthy",
        "server": MCP_SERVER_NAME,
        "version": MCP_SERVER_VERSION,
        "description": MCP_SERVER_DESCRIPTION,
    }


@app.get("/tools")
async def list_tools():
    """사용 가능한 도구 목록 반환 (OpenAI Function Calling 스키마 형식)"""
    return {"tools": TOOL_SCHEMAS}


@app.post("/tools/{tool_name}")
async def call_tool(tool_name: str, request: Dict[str, Any]):
    """특정 도구 실행"""
    if tool_name not in TOOL_FUNCTIONS:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")

    try:
        tool_func = TOOL_FUNCTIONS[tool_name]
        result = await tool_func(**request)
        return {"result": result}
    except TypeError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid parameters for {tool_name}: {str(e)}"
        )
    except Exception as e:
        logger.exception(f"Error executing tool {tool_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Tool execution failed: {str(e)}")


# =============================================================================
# 서버 실행
# =============================================================================


def main():
    """메인 진입점"""
    import os
    import uvicorn

    logger.info(f"{MCP_SERVER_NAME} v{MCP_SERVER_VERSION} 시작")
    logger.info(f"설명: {MCP_SERVER_DESCRIPTION}")

    port = int(os.getenv("MCP_PORT", "3000"))
    host = os.getenv("MCP_HOST", "0.0.0.0")
    logger.info(f"REST API 모드로 실행: {host}:{port}")

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
