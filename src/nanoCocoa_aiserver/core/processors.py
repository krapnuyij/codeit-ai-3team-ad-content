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
from helper_dev_utils import get_auto_logger
from PIL import Image, ImageDraw, ImageFont
from utils import get_system_metrics
from models.llm_text import LLMTexttoHTML
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
# LLM 기반 텍스트 생성 사용 여부 (True: LLM, False: SDXL)
USE_LLM_TEXT = True

# 단순 이미지 생성이 아닌 FLUX 대체 모드에서 SDXL Step 1 사용 여부
USE_FLUX_SDXL_STEP1 = False


def process_step1_background(
    engine, input_data: dict, shared_state: dict, stop_event
) -> Image.Image:
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
        Image.Image: 특성이 주입된 최종 이미지
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

    # 1. 누끼 (Segmentation)
    shared_state["sub_step"] = "segmentation"
    shared_state["system_metrics"] = get_system_metrics()

    # 2. 배경 생성 (Flux 또는 SDXL Text-to-Image)
    shared_state["sub_step"] = "background_generation"
    shared_state["system_metrics"] = get_system_metrics()
    bg_prompt = input_data.get("bg_prompt")
    bg_negative_prompt = input_data.get("bg_negative_prompt")
    guidance_scale = input_data.get("guidance_scale", 3.5)
    seed = input_data.get("seed")
    bg_model = input_data.get("bg_model", "flux")

    if USE_FLUX_SDXL_STEP1:
        # 입력 이미지가 없거나 stop_step=1인 경우, 배경 이미지만 반환
        if not product_img_b64 or input_data.get("stop_step") == 1:
            bg_img = engine.run_sdxl_bg_gen(
                prompt=bg_prompt,
                negative_prompt=bg_negative_prompt,
                guidance_scale=guidance_scale,
                seed=seed,
                auto_unload=False,
            )
        else:
            shared_state["sub_step"] = "sdxl_feature_injection"
            bg_img = engine.run_sdxl_inpaint_injection(
                user_bg=raw_img,
                prompt=bg_prompt,
                negative_prompt=bg_negative_prompt,
                guidance_scale=guidance_scale,
                seed=seed,
                auto_unload=False,
            )
        return bg_img

    else:

        # 모델별 guidance_scale 조정
        if bg_model == "sdxl":
            # SDXL 사용
            bg_img = engine.run_sdxl_base_bg_gen(
                prompt=bg_prompt,
                negative_prompt=bg_negative_prompt,
                guidance_scale=guidance_scale,
                seed=seed,
                auto_unload=False,
            )
        else:
            # Flux 사용 (기본값)
            bg_img = engine.run_flux_bg_gen(
                prompt=bg_prompt,
                negative_prompt=bg_negative_prompt,
                guidance_scale=guidance_scale,
                seed=seed,
                auto_unload=True,
            )
        # 입력 이미지가 없거나 stop_step=1인 경우, 배경 이미지만 반환
        if not product_img_b64 or input_data.get("stop_step") == 1:
            logger.info(
                f"[Step 1] Skipping Inpainting - product_image: {bool(product_img_b64)}, stop_step: {input_data.get('stop_step')}"
            )
            return bg_img

        # 3. 이미지 특성 주입 (Feature Injection via Inpainting)
        shared_state["sub_step"] = "flux_feature_injection"
        shared_state["system_metrics"] = get_system_metrics()

        # 3-1. 상품 배치 계산
        bg_w, bg_h = bg_img.size
        scale = 0.4

        # 상품 이미지에서 전경 및 마스크 추출
        product_fg, mask = engine.run_segmentation(raw_img)

        fg_resized = product_fg.resize(
            (int(product_fg.width * scale), int(product_fg.height * scale)),
            Image.LANCZOS,
        )
        x = (bg_w - fg_resized.width) // 2
        y = int(bg_h * 0.55)

        # 3-2. 상품 마스크 생성 (inpainting 영역)
        product_mask_placed = Image.new("L", bg_img.size, 0)
        mask_resized = mask.resize(fg_resized.size, Image.LANCZOS)
        product_mask_placed.paste(mask_resized, (x, y))

        # 3-3. Inpainting으로 특성 주입
        composition_prompt = input_data.get("bg_composition_prompt") or (
            "A photorealistic object integration. "
            "Heavy contact shadows, ambient occlusion, realistic texture and lighting, "
            "8k, extremely detailed, cinematic."
        )
        composition_negative_prompt = input_data.get(
            "bg_composition_negative_prompt"
        ) or (
            "floating, disconnected, unrealistic shadows, artificial lighting, cut out, sticker effect"
        )
        strength = input_data.get("strength", 0.5)

        result_img = engine.run_flux_inpaint_injection(
            background=bg_img,
            product_foreground=fg_resized,
            product_mask=product_mask_placed,
            position=(x, y),
            prompt=composition_prompt,
            negative_prompt=composition_negative_prompt,
            strength=strength,
            guidance_scale=guidance_scale,
            seed=seed,
        )

        return result_img


def process_step2_text(
    engine, input_data: dict, shared_state: dict, stop_event
) -> Image.Image:
    """
    Step 2: 텍스트 에셋 생성 (Text Asset Generation)

    Args:
        engine: AIModelEngine 인스턴스
        input_data: 입력 데이터
        shared_state: 공유 상태 딕셔너리
        stop_event: 중단 이벤트

    Returns:
        Image.Image: 생성된 3D 텍스트 이미지
    """
    if stop_event.is_set():
        return None

    shared_state["current_step"] = "step2_text"
    shared_state["message"] = "Step 2: Generating 3D Text... (3D 텍스트 생성 중)"

    # 1. 폰트 및 캔버스 준비
    shared_state["sub_step"] = "preparing_text_canvas"

    shared_state["system_metrics"] = get_system_metrics()

    W, H = 1024, 1024  # 기본 캔버스 크기
    text_content = input_data.get("text_content", "맛있는 바나나")

    font_name = input_data.get("font_name")
    if not font_name:
        avail_fonts = get_available_fonts()
        font_name = avail_fonts[0] if avail_fonts else None

    try:
        font_path = get_font_path(font_name) if font_name else None
        if not font_path:
            raise ValueError(f"폰트를 찾을 수 없습니다: {font_name}")
        font = ImageFont.truetype(font_path, 160)
    except (OSError, FileNotFoundError) as e:
        logger.error(f"Font load failed: {font_name} - {e}", exc_info=True)
        raise ValueError(
            f"폰트 로딩 실패: {font_name}. 파일 경로 또는 인코딩 문제를 확인하세요. 원본 오류: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected font error: {e}", exc_info=True)
        raise ValueError(f"폰트 로딩 중 예상치 못한 오류: {str(e)}")

    text_guide = Image.new("RGB", (W, H), "black")
    draw = ImageDraw.Draw(text_guide)

    bbox = draw.textbbox((0, 0), text_content, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    text_x, text_y = (W - tw) // 2, 100

    draw.text((text_x, text_y), text_content, font=font, fill="white")
    canny_map = pil_canny_edge(text_guide)

    # Step 2 시작 전 Step 1 모델 언로드 (auto_unload 활성화 시)
    if hasattr(engine, "auto_unload") and engine.auto_unload:
        logger.info("[Step2] Step 1 모델 언로드 시작")
        engine.unload_step1_models()

        time.sleep(0.5)
        gc.collect()
        torch.cuda.synchronize()
        torch.cuda.empty_cache()
        if hasattr(torch.cuda, "ipc_collect"):
            torch.cuda.ipc_collect()
        logger.info("[Step2] Step 1 모델 언로드 완료")

    # 2. SDXL ControlNet
    shared_state["sub_step"] = "sdxl_text_generation"
    shared_state["system_metrics"] = get_system_metrics()
    text_prompt = input_data.get("text_prompt")
    negative_prompt = input_data.get("text_negative_prompt")
    seed = input_data.get("seed")
    raw_3d_text = engine.run_sdxl_text_gen(
        canny_map, prompt=text_prompt, negative_prompt=negative_prompt, seed=seed
    )

    # 3. 배경 제거 (Text Segmentation)
    shared_state["sub_step"] = "text_segmentation"
    shared_state["system_metrics"] = get_system_metrics()
    transparent_text, _ = engine.run_segmentation(raw_3d_text)

    return transparent_text


def process_step2_llm_text(
    engine, input_data: dict, shared_state: dict, stop_event
) -> Image.Image:
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
        Image.Image: 배경+텍스트가 합성된 최종 이미지 (1024x1024)

    Raises:
        ValueError: OPENAI_API_KEY 미설정, LLM 생성 실패, 렌더링 실패 시
    """
    if stop_event.is_set():
        return None

    shared_state["current_step"] = "step2_llm_text"
    shared_state["message"] = "Step 2: Generating LLM Text... (LLM 텍스트 합성 중)"

    # Step 1 모델 언로드 (auto_unload 활성화 시)
    if hasattr(engine, "auto_unload") and engine.auto_unload:
        logger.info("[Step2 LLM] Step 1 모델 언로드 시작")
        engine.unload_step1_models()

        time.sleep(0.5)
        gc.collect()
        torch.cuda.synchronize()
        torch.cuda.empty_cache()
        if hasattr(torch.cuda, "ipc_collect"):
            torch.cuda.ipc_collect()
        logger.info("[Step2 LLM] Step 1 모델 언로드 완료")

    # 1. LLM 초기화
    shared_state["sub_step"] = "llm_initialization"
    from utils import get_system_metrics

    shared_state["system_metrics"] = get_system_metrics()

    # OpenAI API 키 검증
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        error_msg = (
            "OPENAI_API_KEY not found in environment variables. "
            "Please set it in your .env file or system environment."
        )
        logger.error(f"[Step2 LLM] {error_msg}")
        raise ValueError(error_msg)

    logger.info("[Step2 LLM] OPENAI_API_KEY found, initializing LLMTexttoHTML...")

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

    # 4. LLMTexttoHTML 인스턴스 생성
    try:
        llm_generator = LLMTexttoHTML(
            api_key=api_key,
            model="gpt-5-mini",
            temperature=1.0,
            max_completion_tokens=128000,
        )
        logger.info("[Step2 LLM] LLMTexttoHTML initialized successfully")
    except Exception as e:
        error_msg = f"Failed to initialize LLMTexttoHTML: {str(e)}"
        logger.error(f"[Step2 LLM] {error_msg}", exc_info=True)
        raise ValueError(error_msg)

    # 5. HTML 생성 및 렌더링
    shared_state["sub_step"] = "llm_html_generation"
    shared_state["system_metrics"] = get_system_metrics()
    shared_state["message"] = (
        "Step 2: LLM HTML Generation... (LLM HTML 생성 중, ~5-10초 소요)"
    )

    try:
        logger.info("[Step2 LLM] Starting generate_prompt_png (HTML + Playwright)...")
        logger.info(
            "[Step2 LLM] Note: First run may take 10-15 seconds for Playwright initialization"
        )

        # 비동기 함수를 동기적으로 실행
        result_image = asyncio.run(
            llm_generator.generate_prompt_png(
                image=step1_image,
                ad_text=ad_text,
                text_prompt=text_prompt,
                composition_prompt=composition_prompt,
            )
        )

        logger.info(
            f"[Step2 LLM] LLM PNG generation completed: {result_image.size}, mode={result_image.mode}"
        )

    except Exception as e:
        error_msg = f"LLM PNG generation failed: {str(e)}"
        logger.error(f"[Step2 LLM] {error_msg}", exc_info=True)
        raise ValueError(error_msg)

    # 6. 최종 이미지 검증
    if not result_image or result_image.size != (1024, 1024):
        logger.warning(
            f"[Step2 LLM] Unexpected result image size: {result_image.size if result_image else 'None'}"
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
) -> Image.Image:
    """
    Step 3: 프롬프트 기반 지능형 합성 (Intelligent Composition)

    Args:
        engine: AIModelEngine 인스턴스
        step1_result: Step 1 배경 이미지
        step2_result: Step 2 텍스트 이미지
        input_data: 입력 파라미터 (composition_mode, text_position 등)
        shared_state: 공유 상태 딕셔너리
        stop_event: 중단 이벤트

    Returns:
        Image.Image: 프롬프트 기반으로 합성된 최종 이미지
    """
    if stop_event.is_set():
        return None

    shared_state["current_step"] = "step3_composite"
    shared_state["message"] = "Step 3: Intelligent Compositing... (지능형 합성 중)"
    shared_state["sub_step"] = "intelligent_composite"
    from utils import get_system_metrics

    shared_state["system_metrics"] = get_system_metrics()

    # Step 3 시작 전 이전 단계 모델 언로드 (auto_unload 활성화 시)
    if hasattr(engine, "auto_unload") and engine.auto_unload:
        engine.unload_step1_models()
        engine.unload_step2_models()

    # Step 3 시작 전 강제 GPU 메모리 동기화 및 정리
    torch.cuda.synchronize()  # GPU 작업 완료 대기
    gc.collect()
    torch.cuda.empty_cache()
    if hasattr(torch.cuda, "ipc_collect"):
        torch.cuda.ipc_collect()  # IPC 메모리 정리

    if not step1_result:
        raise ValueError("[Step 3 Error] Missing 'step1_result'. Cannot composite.")
    if not step2_result:
        raise ValueError("[Step 3 Error] Missing 'step2_result'. Cannot composite.")

    # 합성 파라미터 추출
    composition_mode = input_data.get(
        "composition_mode", "overlay"
    )  # overlay/blend/behind
    text_position = input_data.get("text_position", "top")  # top/center/bottom/auto
    user_prompt = input_data.get("composition_prompt")  # 사용자 커스텀 프롬프트 (옵션)
    negative_prompt = input_data.get(
        "composition_negative_prompt"
    )  # 네거티브 프롬프트 (옵션)
    strength = input_data.get("composition_strength", 0.4)  # 변환 강도
    num_steps = input_data.get("composition_steps", 28)  # 추론 스텝 (품질 우선)
    guidance_scale = input_data.get(
        "composition_guidance_scale", 3.5
    )  # 가이던스 스케일
    seed = input_data.get("seed")

    # [Auto Position Logic]
    final_text_asset = step2_result

    if text_position == "auto":
        from utils.images import reposition_text_asset
        from utils.MaskGenerator import MaskGenerator

        # 1. 최적 위치 자동 감지
        recommended_pos = MaskGenerator.recommend_position(step1_result)
        logger.info(
            f"[Step 3] Auto-positioning selected. Recommended: '{recommended_pos}'"
        )

        # 2. 위치 결정
        text_position = recommended_pos

        # 3. 텍스트 에셋 재배치 (Step 2는 기본적으로 Top에 생성됨)
        # 만약 Step 2가 이미 해당 위치에 있다면 생략 가능하지만, 명시적으로 이동
        final_text_asset = reposition_text_asset(step2_result, text_position)
        logger.info(f"[Step 3] Text asset repositioned to '{text_position}'")
    else:
        # 수동 위치 선택 시에도, Step 2 결과가 Top에 있다면 이동 필요할 수 있음
        # 하지만 현재 UX상 Step 2 생성 시 위치를 지정하지 않으므로(기본 Top),
        # 합성 단계에서 위치를 바꿀 때 reposition을 해주는 것이 좋음
        final_text_asset = reposition_text_asset(step2_result, text_position)

    logger.info(
        f"[Step 3] Composition parameters: mode={composition_mode}, position={text_position}, strength={strength}, steps={num_steps}, guidance={guidance_scale}"
    )

    logger.info(f"prompt={user_prompt}")
    logger.info(f"negative_prompt={negative_prompt}")

    try:
        # 지능형 합성 실행
        final_result = engine.run_intelligent_composite(
            background=step1_result,
            text_asset=final_text_asset,  # 재배치된 텍스트 에셋 사용
            composition_mode=composition_mode,
            text_position=text_position,  # 결정된 위치("auto" 아님)
            user_prompt=user_prompt,
            negative_prompt=negative_prompt,
            strength=strength,
            num_inference_steps=num_steps,
            seed=seed,
        )

        logger.info("[Step 3] Intelligent composition completed")
        return final_result

    except Exception as e:
        logger.error(f"[Step 3] Intelligent composition failed: {e}", exc_info=True)
        logger.warning("[Step 3] Falling back to simple alpha composite")

        # Fallback: 단순 합성
        if hasattr(engine, "compositor"):
            final_result = engine.compositor.compose_simple(
                step1_result, final_text_asset
            )
        else:
            base_comp = step1_result.convert("RGBA")
            text_asset = final_text_asset.convert("RGBA")
            if base_comp.size != text_asset.size:
                text_asset = text_asset.resize(base_comp.size, Image.LANCZOS)
            final_comp = Image.alpha_composite(base_comp, text_asset)
            final_result = final_comp.convert("RGB")

        return final_result
