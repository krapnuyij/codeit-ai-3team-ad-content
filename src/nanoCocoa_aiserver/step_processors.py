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
    Step 1: 배경 생성 (Background Generation)
    
    Args:
        engine: AIModelEngine 인스턴스
        input_data: 입력 데이터
        shared_state: 공유 상태 딕셔너리
        stop_event: 중단 이벤트
        
    Returns:
        Image.Image: 생성된 배경 이미지
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
    
    # 3. 초안 합성 (Composite Draft)
    shared_state['sub_step'] = 'compositing_draft'
    shared_state['system_metrics'] = get_system_metrics()
    bg_w, bg_h = bg_img.size
    scale = 0.4
    fg_resized = product_fg.resize(
        (int(product_fg.width * scale), int(product_fg.height * scale)), 
        Image.LANCZOS
    )
    x = (bg_w - fg_resized.width) // 2
    y = int(bg_h * 0.55)
    
    base_comp = bg_img.convert("RGBA")
    fg_layer = Image.new("RGBA", bg_img.size)
    fg_layer.paste(fg_resized, (x, y))
    base_comp = Image.alpha_composite(base_comp, fg_layer)
    draft_final = base_comp.convert("RGB")
    
    # 4. 리파인 (Flux Img-to-Img)
    shared_state['sub_step'] = 'flux_refinement'
    shared_state['system_metrics'] = get_system_metrics()
    strength = input_data.get('strength', 0.6)
    refined_base = engine.run_flux_refinement(
        draft_final, 
        strength=strength, 
        guidance_scale=guidance_scale, 
        seed=seed
    )
    
    return refined_base


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


def process_step3_composite(step1_result: Image.Image, step2_result: Image.Image, 
                            shared_state: dict, stop_event) -> Image.Image:
    """
    Step 3: 최종 합성 (Final Composite)
    
    Args:
        step1_result: Step 1 배경 이미지
        step2_result: Step 2 텍스트 이미지
        shared_state: 공유 상태 딕셔너리
        stop_event: 중단 이벤트
        
    Returns:
        Image.Image: 최종 합성 이미지
    """
    if stop_event.is_set():
        return None

    shared_state['current_step'] = 'step3_composite'
    shared_state['message'] = 'Step 3: Final Compositing... (최종 합성 중)'
    shared_state['sub_step'] = 'final_composite'
    from utils import get_system_metrics
    shared_state['system_metrics'] = get_system_metrics()
    
    if not step1_result:
        raise ValueError("[Step 3 Error] Missing 'step1_result'. Cannot composite.")
    if not step2_result:
        raise ValueError("[Step 3 Error] Missing 'step2_result'. Cannot composite.")
    
    # 합성
    base_comp = step1_result.convert("RGBA")
    text_asset = step2_result.convert("RGBA")
    
    # 크기 맞추기
    if base_comp.size != text_asset.size:
        text_asset = text_asset.resize(base_comp.size, Image.LANCZOS)
        
    final_comp = Image.alpha_composite(base_comp, text_asset)
    final_result = final_comp.convert("RGB")
    
    return final_result
