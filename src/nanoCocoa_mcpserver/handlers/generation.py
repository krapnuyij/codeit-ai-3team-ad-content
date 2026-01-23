"""
광고 생성 관련 핸들러 함수
"""

import logging
import base64
import io
import json
import asyncio
import httpx
from typing import Optional, Dict, Any, Literal
from PIL import Image

from client.api_client import AIServerClient, AIServerError
from schemas.api_models import GenerateRequest
from utils.image_utils import (
    image_file_to_base64,
    base64_to_image_file,
    resize_and_encode_for_clip,
    ImageProcessingError,
)
from utils.text_utils import (
    detect_language,
    summarize_prompt,
)
from config import AISERVER_BASE_URL

from helper_dev_utils import get_auto_logger

logger = get_auto_logger()

# API 클라이언트 전역 인스턴스
_api_client: Optional[AIServerClient] = None


async def get_api_client() -> AIServerClient:
    """API 클라이언트 싱글톤 인스턴스 반환"""
    global _api_client
    if _api_client is None:
        _api_client = AIServerClient()
        await _api_client._ensure_client()
    return _api_client


async def generate_ad_image(
    product_image_path: Optional[str] = None,
    text_content: str = "",
    font_name: Optional[str] = None,
    background_prompt: Optional[str] = None,
    bg_model: str = "flux",
    background_negative_prompt: Optional[str] = None,
    bg_composition_prompt: Optional[str] = None,
    bg_composition_negative_prompt: Optional[str] = None,
    text_prompt: Optional[str] = None,
    text_negative_prompt: Optional[str] = None,
    composition_prompt: Optional[str] = None,
    composition_negative_prompt: Optional[str] = None,
    composition_mode: str = "overlay",
    text_position: str = "auto",
    strength: float = 0.6,
    guidance_scale: float = 3.5,
    composition_strength: float = 0.4,
    composition_steps: int = 28,
    composition_guidance_scale: float = 3.5,
    auto_unload: bool = True,
    seed: Optional[int] = None,
    test_mode: bool = False,
    wait_for_completion: bool = False,
    save_output_path: Optional[str] = None,
    stop_step: Optional[int] = None,
) -> str:
    """
    제품 이미지를 기반으로 AI가 전문적인 광고 이미지를 생성합니다.

    stop_step 파라미터로 파이프라인 제어:
    - None/생략: 전체 실행 (배경→텍스트→합성)
    - 1: 배경만 생성
    - 2: 배경+텍스트 생성 (합성 전)
    - 3: 전체 실행
    """
    try:
        # [디버그] MCP 핸들러가 받은 bg_model 로깅
        logger.info(f"[MCP Handler] bg_model 수신: {bg_model}")

        client = await get_api_client()

        # 제품 이미지 처리
        if product_image_path:
            logger.info(f"제품 이미지 로드: {product_image_path}")
            product_image_b64 = image_file_to_base64(product_image_path)
        else:
            logger.info("제품 이미지 없음 - 배경만 생성")
            product_image_b64 = None

        # 프롬프트 기본값 처리
        if not background_prompt:
            background_prompt = "Clean white background, studio lighting, minimal style"
        if not text_prompt:
            text_prompt = "3D render of bold text, modern style, clean design"

        # 요청 파라미터 구성
        params = GenerateRequest(
            start_step=1,
            stop_step=stop_step,
            text_content=text_content,
            product_image=product_image_b64,
            step1_image=None,
            step2_image=None,
            bg_model=bg_model,
            bg_prompt=background_prompt,
            bg_negative_prompt=background_negative_prompt or "",
            bg_composition_prompt=bg_composition_prompt,
            bg_composition_negative_prompt=bg_composition_negative_prompt,
            text_prompt=text_prompt,
            text_negative_prompt=text_negative_prompt or "",
            font_name=font_name,
            composition_mode=composition_mode,
            text_position=text_position,
            composition_prompt=composition_prompt,
            composition_negative_prompt=composition_negative_prompt or "",
            composition_strength=composition_strength,
            composition_steps=composition_steps,
            composition_guidance_scale=composition_guidance_scale,
            strength=strength,
            guidance_scale=guidance_scale,
            seed=seed,
            test_mode=test_mode,
            auto_unload=auto_unload,
        )

        if wait_for_completion:
            logger.info("광고 이미지 생성 시작 (완료까지 대기)")
            result = await client.generate_and_wait(
                params,
                progress_callback=lambda s: logger.info(
                    f"진행: {s.progress_percent}% - {s.current_step} - {s.message}"
                ),
            )

            if save_output_path and result.final_result:
                output_path = base64_to_image_file(
                    result.final_result, save_output_path, overwrite=True
                )
                logger.info(f"결과 저장: {output_path}")

            import json

            response_data = {
                "status": "completed",
                "job_id": result.job_id,
                "elapsed_sec": round(result.elapsed_sec, 1),
                "progress_percent": result.progress_percent,
                "message": "Ad image generation completed successfully",
            }

            if save_output_path:
                response_data["saved_path"] = save_output_path

            return json.dumps(response_data, ensure_ascii=False)
        else:
            logger.info("광고 이미지 생성 시작 (비동기)")
            response = await client.start_generation(params)
            import json

            return json.dumps(
                {
                    "status": "started",
                    "job_id": response.job_id,
                    "message": "Ad generation started. Use check_generation_status to monitor progress.",
                },
                ensure_ascii=False,
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
    """작업 상태를 확인합니다."""
    try:
        client = await get_api_client()
        status = await client.get_status(job_id)

        import json
        import base64
        from pathlib import Path
        from config import AISERVER_BASE_URL

        response_data = {
            "job_id": status.job_id,
            "status": status.status,
            "progress_percent": status.progress_percent,
            "current_step": status.current_step,
            "message": status.message,
            "elapsed_sec": round(status.elapsed_sec, 1),
        }

        # 완료된 경우 이미지 처리
        if status.status == "completed":
            # step1, step2, final 중 가장 최신 결과 선택
            result_image = None
            result_name = None

            if status.final_result:
                result_image = status.final_result
                result_name = "final"
            elif status.step2_result:
                result_image = status.step2_result
                result_name = "step2"
            elif status.step1_result:
                result_image = status.step1_result
                result_name = "step1"

            # Base64 이미지 직접 반환 (임시 파일 저장 제거)
            if result_image:
                response_data["image_base64"] = result_image
                response_data["result_type"] = result_name
                logger.info(f"이미지 Base64 반환: result_type={result_name}")

                # save_result_path가 지정된 경우에만 파일 저장
                if save_result_path:
                    output_path = base64_to_image_file(
                        result_image, save_result_path, overwrite=True
                    )
                    response_data["saved_path"] = str(output_path)
                    logger.info(f"이미지 저장: {output_path}")

        return json.dumps(response_data, ensure_ascii=False)

    except AIServerError as e:
        logger.error(f"상태 조회 에러: {e}")
        return f"에러: {str(e)}"


async def stop_generation(job_id: str) -> str:
    """실행 중인 작업을 중단합니다."""
    try:
        client = await get_api_client()
        result = await client.stop_job(job_id)
        import json

        return json.dumps(
            {
                "status": result.status,
                "job_id": result.job_id,
                "message": "Job stop requested",
            },
            ensure_ascii=False,
        )

    except AIServerError as e:
        import json

        return json.dumps({"error": str(e)}, ensure_ascii=False)


async def evaluate_image_clip(
    image_path: str,
    prompt: str,
    model_type: Literal["auto", "koclip", "openai"] = "auto",
) -> str:
    """
    이미지와 프롬프트의 CLIP 유사도 평가

    Args:
        image_path: 평가할 이미지 파일 경로
        prompt: 비교할 텍스트 프롬프트
        model_type: CLIP 모델 타입
            - "auto": 한글 포함 시 koclip, 영문만 있으면 openai (기본값)
            - "koclip": KoCLIP 모델 강제 사용
            - "openai": OpenAI CLIP 모델 강제 사용

    Returns:
        JSON 문자열: {"clip_score": float, "interpretation": str, "model_type": str, "prompt": str}

    Raises:
        ImageProcessingError: 이미지 처리 실패
        httpx.HTTPError: CLIP API 호출 실패
    """
    try:
        # 1. 이미지 리사이즈 및 Base64 인코딩 (224x224)
        logger.info(f"CLIP 평가 시작: image_path={image_path}")
        image_base64 = resize_and_encode_for_clip(image_path)

        # 2. 프롬프트 전처리 (긴 프롬프트 요약)
        original_prompt = prompt
        if len(prompt.split()) > 77:
            prompt = summarize_prompt(prompt, max_words=50)
            logger.info(
                f"프롬프트 요약: {len(original_prompt.split())}단어 -> {len(prompt.split())}단어"
            )

        # 3. 모델 타입 자동 선택
        if model_type == "auto":
            model_type = detect_language(prompt)
            logger.info(f"자동 모델 선택: {model_type} (프롬프트: {prompt[:50]}...)")

        # 4. CLIP Score API 호출 (재시도 로직 포함)
        clip_api_url = f"{AISERVER_BASE_URL}/clip-score"
        request_payload = {
            "image_base64": image_base64,
            "prompt": prompt,
            "model_type": model_type,
        }

        max_retries = 3
        retry_delay = 1.0

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(clip_api_url, json=request_payload)
                    response.raise_for_status()
                    result = response.json()

                    # 성공 시 결과 반환
                    logger.info(
                        f"CLIP 평가 완료: score={result['clip_score']:.3f}, "
                        f"model={result['model_type']}"
                    )
                    return json.dumps(
                        {
                            "clip_score": result["clip_score"],
                            "interpretation": result["interpretation"],
                            "model_type": result["model_type"],
                            "prompt": prompt,
                        },
                        ensure_ascii=False,
                    )

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 503 and attempt < max_retries - 1:
                    # 503 Service Unavailable 시 재시도
                    logger.warning(
                        f"CLIP API 503 에러 (시도 {attempt + 1}/{max_retries}), "
                        f"{retry_delay:.1f}초 후 재시도"
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise

            except httpx.RequestError as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"CLIP API 연결 실패 (시도 {attempt + 1}/{max_retries}), "
                        f"{retry_delay:.1f}초 후 재시도: {e}"
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise

        # 최대 재시도 초과
        raise httpx.RequestError(
            f"CLIP API 호출 실패 (최대 재시도 {max_retries}회 초과)"
        )

    except ImageProcessingError as e:
        logger.error(f"이미지 처리 에러: {e}")
        return json.dumps({"error": f"이미지 처리 실패: {str(e)}"}, ensure_ascii=False)

    except httpx.HTTPError as e:
        logger.error(f"CLIP API 호출 에러: {e}")
        return json.dumps(
            {"error": f"CLIP API 호출 실패: {str(e)}"}, ensure_ascii=False
        )

    except Exception as e:
        logger.error(f"CLIP 평가 중 예외 발생: {e}")
        return json.dumps({"error": f"CLIP 평가 실패: {str(e)}"}, ensure_ascii=False)
