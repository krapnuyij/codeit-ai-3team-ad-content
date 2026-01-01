"""
step_processors.py
각 단계(Step) 처리 로직을 담당하는 모듈
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from PIL import Image, ImageDraw, ImageFont
from config import logger
from utils import pil_to_base64, base64_to_pil, pil_canny_edge, get_available_fonts, get_font_path


def process_step1_background(engine, input_data: dict, shared_state: dict, stop_event) -> Image.Image:
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

    shared_state['current_step'] = 'step1_background'
    shared_state['message'] = 'Step 1: Generating Background... (배경 이미지 생성 중)'
    
    # 입력 확인
    input_img_b64 = input_data.get('input_image')
    if not input_img_b64:
        raise ValueError("[Step 1 Error] 'input_image' is required to start from Step 1.")
    
    # 더미 데이터 체크
    if input_img_b64 == "DUMMY_IMAGE_DATA":
        # 더미 모드: 간단한 테스트 이미지 생성
        raw_img = Image.new("RGB", (512, 512), "white")
    else:
        raw_img = base64_to_pil(input_img_b64)
    
    # 1. 누끼 (Segmentation)
    shared_state['sub_step'] = 'segmentation'
    from utils import get_system_metrics
    shared_state['system_metrics'] = get_system_metrics()
    product_fg, mask = engine.run_segmentation(raw_img)
    
    # 2. 배경 생성 (Flux Text-to-Image)
    shared_state['sub_step'] = 'flux_background_generation'
    shared_state['system_metrics'] = get_system_metrics()
    bg_prompt = input_data.get('bg_prompt')
    bg_negative_prompt = input_data.get('bg_negative_prompt')
    guidance_scale = input_data.get('guidance_scale', 3.5)
    seed = input_data.get('seed')
    bg_img = engine.run_flux_bg_gen(
        prompt=bg_prompt, 
        negative_prompt=bg_negative_prompt, 
        guidance_scale=guidance_scale, 
        seed=seed
    )
    
    # 3. 이미지 특성 주입 (Feature Injection via Inpainting)
    shared_state['sub_step'] = 'flux_feature_injection'
    shared_state['system_metrics'] = get_system_metrics()
    
    # 3-1. 상품 배치 계산
    bg_w, bg_h = bg_img.size
    scale = 0.4
    fg_resized = product_fg.resize(
        (int(product_fg.width * scale), int(product_fg.height * scale)), 
        Image.LANCZOS
    )
    x = (bg_w - fg_resized.width) // 2
    y = int(bg_h * 0.55)
    
    # 3-2. 상품 마스크 생성 (inpainting 영역)
    product_mask_placed = Image.new("L", bg_img.size, 0)
    mask_resized = mask.resize(fg_resized.size, Image.LANCZOS)
    product_mask_placed.paste(mask_resized, (x, y))
    
    # 3-3. Inpainting으로 특성 주입
    composition_prompt = input_data.get('bg_composition_prompt') or (
        "A photorealistic product lying naturally on the surface. "
        "Heavy contact shadows, ambient occlusion, realistic texture and lighting, "
        "8k, extremely detailed, cinematic."
    )
    composition_negative_prompt = input_data.get('bg_composition_negative_prompt') or (
        "floating, disconnected, unrealistic shadows, artificial lighting, cut out, sticker effect"
    )
    strength = input_data.get('strength', 0.5)
    
    result_img = engine.run_flux_inpaint_injection(
        background=bg_img,
        product_foreground=fg_resized,
        product_mask=product_mask_placed,
        position=(x, y),
        prompt=composition_prompt,
        negative_prompt=composition_negative_prompt,
        strength=strength,
        guidance_scale=guidance_scale,
        seed=seed
    )
    
    return result_img


def process_step2_text(engine, input_data: dict, shared_state: dict, stop_event) -> Image.Image:
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

    shared_state['current_step'] = 'step2_text'
    shared_state['message'] = 'Step 2: Generating 3D Text... (3D 텍스트 생성 중)'
    
    # 1. 폰트 및 캔버스 준비
    shared_state['sub_step'] = 'preparing_text_canvas'
    from utils import get_system_metrics
    shared_state['system_metrics'] = get_system_metrics()
    
    W, H = 1024, 1024  # 기본 캔버스 크기
    text_content = input_data.get('text_content', "맛있는 바나나")
    
    font_name = input_data.get('font_name')
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
        raise ValueError(f"폰트 로딩 실패: {font_name}. 파일 경로 또는 인코딩 문제를 확인하세요. 원본 오류: {str(e)}")
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
    
    # 2. SDXL ControlNet
    shared_state['sub_step'] = 'sdxl_text_generation'
    shared_state['system_metrics'] = get_system_metrics()
    text_model_prompt = input_data.get('text_model_prompt')
    negative_prompt = input_data.get('negative_prompt')
    raw_3d_text = engine.run_sdxl_text_gen(
        canny_map, 
        prompt=text_model_prompt,
        negative_prompt=negative_prompt
    )
    
    # 3. 배경 제거 (Text Segmentation)
    shared_state['sub_step'] = 'text_segmentation'
    shared_state['system_metrics'] = get_system_metrics()
    transparent_text, _ = engine.run_segmentation(raw_3d_text)
    
    return transparent_text


def process_step3_composite(
    engine,  # AIModelEngine 인스턴스 필요
    step1_result: Image.Image, 
    step2_result: Image.Image,
    input_data: dict,  # 합성 파라미터 필요
    shared_state: dict, 
    stop_event
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

    shared_state['current_step'] = 'step3_composite'
    shared_state['message'] = 'Step 3: Intelligent Compositing... (지능형 합성 중)'
    shared_state['sub_step'] = 'intelligent_composite'
    from utils import get_system_metrics
    shared_state['system_metrics'] = get_system_metrics()
    
    if not step1_result:
        raise ValueError("[Step 3 Error] Missing 'step1_result'. Cannot composite.")
    if not step2_result:
        raise ValueError("[Step 3 Error] Missing 'step2_result'. Cannot composite.")
    
    # 합성 파라미터 추출
    composition_mode = input_data.get('composition_mode', 'overlay')  # overlay/blend/behind
    text_position = input_data.get('text_position', 'top')  # top/center/bottom
    user_prompt = input_data.get('composition_prompt')  # 사용자 커스텀 프롬프트 (옵션)
    negative_prompt = input_data.get('composition_negative_prompt')  # 네거티브 프롬프트 (옵션)
    strength = input_data.get('composition_strength', 0.4)  # 변환 강도
    num_steps = input_data.get('composition_steps', 28)  # 추론 스텝 (품질 우선)
    guidance_scale = input_data.get('composition_guidance_scale', 3.5)  # 가이던스 스케일
    seed = input_data.get('seed')
    
    logger.info(f"[Step 3] Composition parameters: mode={composition_mode}, position={text_position}, strength={strength}, steps={num_steps}, guidance={guidance_scale}")
    
    try:
        # 지능형 합성 실행
        final_result = engine.run_intelligent_composite(
            background=step1_result,
            text_asset=step2_result,
            composition_mode=composition_mode,
            text_position=text_position,
            user_prompt=user_prompt,
            strength=strength,
            num_inference_steps=num_steps,
            seed=seed
        )
        
        logger.info("[Step 3] ✅ Intelligent composition completed")
        return final_result
        
    except Exception as e:
        logger.error(f"[Step 3] Intelligent composition failed: {e}", exc_info=True)
        logger.warning("[Step 3] Falling back to simple alpha composite")
        
        # Fallback: 단순 합성
        if hasattr(engine, 'compositor'):
            final_result = engine.compositor.compose_simple(step1_result, step2_result)
        else:
            base_comp = step1_result.convert("RGBA")
            text_asset = step2_result.convert("RGBA")
            if base_comp.size != text_asset.size:
                text_asset = text_asset.resize(base_comp.size, Image.LANCZOS)
            final_comp = Image.alpha_composite(base_comp, text_asset)
            final_result = final_comp.convert("RGB")
        
        return final_result
