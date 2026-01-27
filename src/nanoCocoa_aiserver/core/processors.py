"""
step_processors.py
각 단계(Step) 처리 로직을 담당하는 모듈
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

import asyncio
import gc
import os
import time
import torch
from typing import Optional
from helper_dev_utils import get_auto_logger
from PIL import Image, ImageDraw, ImageFont
from utils import get_system_metrics
from utils.images import reposition_text_asset

logger = get_auto_logger()

from utils import (
    base64_to_pil,
    get_available_fonts,
    get_font_path,
    pil_canny_edge,
    pil_to_base64,
)

# ==========================================
# 설정 (Configuration)
# ==========================================


def process_step1_background(
    engine, input_data: dict, shared_state: dict, stop_event
) -> Optional[Image.Image]:
    """
    Step 1: 이미지 특성 추출 및 주입 (Feature Extraction & Injection)

    프로세스:
    1. 누끼 (Segmentation): 상품 이미지에서 특성 추출
    2. 배경 생성 (Background Generation): 프롬프트 기반 배경 생성
    3. 특성 주입 (Feature Injection): Inpainting으로 상품 특성을 배경에 주입

    Args:
        engine: AIModelEngine 인스턴스
        input_data: 입력 데이터
        shared_state: 공유 상태 딕셔너리
        stop_event: 중단 이벤트

    Returns:
        Optional[Image.Image]: 특성이 주입된 최종 이미지 또는 None (중단 시)
    """
    if stop_event.is_set():
        return None

    shared_state["current_step"] = "step1_background"
    shared_state["message"] = "Step 1: Generating Background... (배경 이미지 생성 중)"

    # 입력 이미지 확인 및 전처리
    product_img_b64 = input_data.get("product_image")

    if product_img_b64 == "DUMMY_IMAGE_DATA":
        # 더미 모드: 테스트용 흰색 이미지 생성
        raw_img = Image.new("RGB", (512, 512), "white")
        logger.info("[Step 1] Using dummy white image for testing")
    elif product_img_b64 and len(product_img_b64) > 100:
        # Base64 디코딩하여 PIL 이미지로 변환 (최소 길이 검증)
        raw_img = base64_to_pil(product_img_b64)
        logger.info(f"[Step 1] Input image loaded: {raw_img.size}")
    else:
        # 입력 이미지 없음: 배경 생성 전용 모드 (상품 없이 배경만 생성)
        raw_img = Image.new("RGB", (512, 512), "white")
        logger.info("[Step 1] No input image provided. Generating background only.")

    # 1. 누끼 (Segmentation) 사용안함
    # 2. 배경 생성 (Flux)
    shared_state["sub_step"] = "background_generation"
    shared_state["system_metrics"] = get_system_metrics()
    bg_prompt = input_data.get("bg_prompt")
    bg_negative_prompt = input_data.get("bg_negative_prompt")
    guidance_scale = input_data.get("guidance_scale", 3.5)
    seed = input_data.get("seed")

    # 사용안함 flux 고정
    bg_model = input_data.get("bg_model", "flux")

    if not product_img_b64:
        # 프롬프트 배경
        bg_img = engine.run_text2image(
            prompt=bg_prompt,
            negative_prompt=bg_negative_prompt,
            guidance_scale=guidance_scale,
            seed=seed,
            auto_unload=True,
        )
    else:
        # 이미지 합성 배경
        bg_img = engine.run_image2image(
            draft_image=raw_img,
            prompt=bg_prompt,
            negative_prompt=bg_negative_prompt,
            guidance_scale=guidance_scale,
            seed=seed,
            auto_unload=True,
        )

    return bg_img


def process_step2_text(
    engine, input_data: dict, shared_state: dict, stop_event
) -> Optional[Image.Image]:
    """
    Step 2: 텍스트 에셋 생성 (Text Asset Generation)

    Args:
        engine: AIModelEngine 인스턴스
        input_data: 입력 데이터
        shared_state: 공유 상태 딕셔너리
        stop_event: 중단 이벤트

    Returns:
        Optional[Image.Image]: 생성된 3D 텍스트 이미지 또는 None (사용안함)
    """
    if stop_event.is_set():
        return None

    # 사용안함
    return None


def process_step2_llm_text(
    engine, input_data: dict, shared_state: dict, stop_event
) -> Optional[Image.Image]:
    """
    Step 2 (LLM): LLM 기반 텍스트 합성 (배경+텍스트 통합 생성)

    LLMTexttoHTML을 사용하여 Step 1 배경 이미지에 광고 문구를 합성합니다.
    이 함수는 Step 2와 Step 3를 통합하여 최종 이미지를 직접 생성합니다.

    Args:
        engine: AIModelEngine 인스턴스 (미사용, 인터페이스 호환성 유지)
        input_data: 입력 데이터
        shared_state: 공유 상태 딕셔너리
        stop_event: 중단 이벤트

    Returns:
        Optional[Image.Image]: 배경+텍스트가 합성된 최종 이미지 (1024x1024) 또는 None (중단 시)

    Raises:
        ValueError: OPENAI_API_KEY 미설정, LLM 생성 실패, 렌더링 실패 시
    """
    if stop_event.is_set():
        return None

    shared_state["current_step"] = "step2_llm_text"
    shared_state["message"] = "Step 2: Generating LLM Text... (LLM 텍스트 합성 중)"

    # OpenAI API 키 검증
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        error_msg = (
            "OPENAI_API_KEY not found in environment variables. "
            "Please set it in your .env file or system environment."
        )
        logger.error(f"[Step2 LLM] {error_msg}")
        raise ValueError(error_msg)

    # 2. Step 1 배경 이미지 로드
    step1_result_b64 = shared_state.get("images", {}).get("step1_result")
    if not step1_result_b64:
        error_msg = "Step 1 result image not found in shared_state"
        logger.error(f"[Step2 LLM] {error_msg}")
        raise ValueError(error_msg)

    try:
        step1_image = base64_to_pil(step1_result_b64)
        logger.info(f"[Step2 LLM] Step 1 image loaded: {step1_image.size}")
    except Exception as e:
        error_msg = f"Failed to decode step1_result from base64: {str(e)}"
        logger.error(f"[Step2 LLM] {error_msg}", exc_info=True)
        raise ValueError(error_msg)

    # 3. 입력 파라미터 추출
    ad_text = input_data.get("text_content", "맛있는 바나나")
    text_prompt = input_data.get("text_prompt")
    composition_prompt = input_data.get("composition_prompt")

    logger.info(
        f"[Step2 LLM] Parameters - ad_text: '{ad_text}', "
        f"text_prompt: '{text_prompt}', composition_prompt: '{composition_prompt}'"
    )

    result_image = engine.run_composite(
        step1_image, ad_text, text_prompt, composition_prompt
    )

    logger.info("[Step2 LLM] LLM text composition completed successfully")
    return result_image


def process_step3_composite(
    engine,  # AIModelEngine 인스턴스 필요
    step1_result: Image.Image,
    step2_result: Image.Image,
    input_data: dict,  # 합성 파라미터 필요
    shared_state: dict,
    stop_event,
) -> Optional[Image.Image]:
    """사용안함"""

    return None
