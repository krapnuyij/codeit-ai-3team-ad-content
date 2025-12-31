import multiprocessing
import time
from PIL import Image, ImageDraw, ImageFont

from config import logger
from utils import pil_to_base64, base64_to_pil, flush_gpu, pil_canny_edge, get_available_fonts, get_font_path
from AIModelEngine import AIModelEngine

# ==========================================
# 🔄 백그라운드 워커 (Background Worker)
# ==========================================
def worker_process(job_id: str, input_data: dict, shared_state: dict, stop_event: multiprocessing.Event):
    """
    Step 기반(1->2->3) 순차 실행 워커 프로세스.
    """
    
    # 파라미터 추출
    test_mode = input_data.get('test_mode', False)
    
    # 진행률 업데이트 콜백 함수
    def update_progress(step_num, total_steps, sub_step_name):
        """
        모델 파이프라인 내부의 진행률을 shared_state에 반영합니다.
        
        Args:
            step_num: 현재 스텝 (1-based)
            total_steps: 전체 스텝 수
            sub_step_name: 서브 스텝 이름
        """
        # 현재 메인 스텝 확인
        current_main_step = shared_state.get('current_step', 'step1_background')
        
        # 메인 스텝별 진행률 범위 정의
        # Step 1: 0-33%, Step 2: 33-66%, Step 3: 66-100%
        if 'step1' in current_main_step:
            base_progress = 0
            step_range = 33
        elif 'step2' in current_main_step:
            base_progress = 33
            step_range = 33
        elif 'step3' in current_main_step:
            base_progress = 66
            step_range = 34
        else:
            base_progress = 0
            step_range = 33
        
        # 서브 스텝 내 진행률 계산 (0.0 ~ 1.0)
        sub_progress = step_num / total_steps
        
        # 최종 진행률 = 베이스 + (서브 진행률 * 스텝 범위)
        final_progress = int(base_progress + (sub_progress * step_range))
        final_progress = min(100, max(0, final_progress))
        
        shared_state['progress_percent'] = final_progress
        shared_state['sub_step'] = f"{sub_step_name} ({step_num}/{total_steps})"
        from utils import get_system_metrics
        shared_state['system_metrics'] = get_system_metrics()
    
    engine = AIModelEngine(dummy_mode=test_mode, progress_callback=update_progress)
    
    try:
        shared_state['status'] = 'running'
        shared_state['start_time'] = time.time()
        shared_state['sub_step'] = None
        
        # 파라미터 추출 (계속)
        start_step = input_data.get('start_step', 1)
        
        bg_prompt = input_data.get('bg_prompt')
        text_model_prompt = input_data.get('text_model_prompt')
        negative_prompt = input_data.get('negative_prompt')
        text_content = input_data.get('text_content', "Special Sale")
        
        strength = input_data.get('strength', 0.6)
        guidance_scale = input_data.get('guidance_scale', 3.5)
        seed = input_data.get('seed') 

        # 단계별 결과물 변수 (PIL Image)
        step1_result = None
        step2_result = None
        final_result = None

        # ==========================================
        # Step 1: 배경 생성 (Background Generation)
        # ==========================================
        if start_step <= 1:
            if stop_event.is_set(): return

            shared_state['current_step'] = 'step1_background'
            shared_state['message'] = 'Step 1: Generating Background... (배경 이미지 생성 중)'
            
            # 입력 확인
            input_img_b64 = input_data.get('input_image')
            if not input_img_b64:
                raise ValueError("[Step 1 Error] 'input_image' is required to start from Step 1.")
            raw_img = base64_to_pil(input_img_b64)
            
            # [Logic]
            # 1. 누끼 (Segmentation)
            shared_state['sub_step'] = 'segmentation'
            from utils import get_system_metrics
            shared_state['system_metrics'] = get_system_metrics()
            product_fg, mask = engine.run_segmentation(raw_img)
            
            # 2. 배경 생성 (Flux Text-to-Image)
            shared_state['sub_step'] = 'flux_background_generation'
            shared_state['system_metrics'] = get_system_metrics()
            bg_negative_prompt = input_data.get('bg_negative_prompt')
            bg_img = engine.run_flux_bg_gen(prompt=bg_prompt, negative_prompt=bg_negative_prompt, guidance_scale=guidance_scale, seed=seed)
            
            # 3. 초안 합성 (Composite Draft)
            shared_state['sub_step'] = 'compositing_draft'
            shared_state['system_metrics'] = get_system_metrics()
            bg_w, bg_h = bg_img.size
            scale = 0.4
            fg_resized = product_fg.resize((int(product_fg.width*scale), int(product_fg.height*scale)), Image.LANCZOS)
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
            refined_base = engine.run_flux_refinement(
                draft_final, 
                strength=strength, 
                guidance_scale=guidance_scale, 
                seed=seed
            )
            
            step1_result = refined_base
            shared_state['images']['step1_result'] = pil_to_base64(step1_result)
            shared_state['progress_percent'] = 33
            
        else:
            # Step 1을 건너뛸 경우, 입력받은 step1_image 사용
            img_s1_b64 = input_data.get('step1_image')
            if img_s1_b64:
                # shared_state['message'] = 'Step 1 Skipped. Using provided image.'
                step1_result = base64_to_pil(img_s1_b64)
                shared_state['images']['step1_result'] = img_s1_b64
            else:
                # 2단계 이상부터 시작하는데 1단계 결과물이 없으면 치명적일 수 있음(3단계에서 필요 시)
                # 단, 2단계만 테스트 하는 경우 등에는 없을 수도 있음.
                pass

        # ==========================================
        # Step 2: 텍스트 에셋 생성 (Text Asset Gen)
        # ==========================================
        if start_step <= 2:
            if stop_event.is_set(): return

            shared_state['current_step'] = 'step2_text'
            shared_state['message'] = 'Step 2: Generating 3D Text... (3D 텍스트 생성 중)'
            
            # [Logic]
            # 1. 폰트 및 캔버스 준비
            shared_state['sub_step'] = 'preparing_text_canvas'
            shared_state['system_metrics'] = get_system_metrics()
            W, H = 1024, 1024 # 기본 캔버스 크기
            
            font_name = input_data.get('font_name')
            if not font_name:
                avail_fonts = get_available_fonts()
                font_name = avail_fonts[0] if avail_fonts else None
            
            try:
                font_path = get_font_path(font_name) if font_name else None
                font = ImageFont.truetype(font_path, 160) if font_path else ImageFont.load_default()
            except Exception as e:
                logger.warning(f"Font load failed: {e}")
                font = ImageFont.load_default()
            
            text_guide = Image.new("RGB", (W, H), "black")
            draw = ImageDraw.Draw(text_guide)
            
            bbox = draw.textbbox((0,0), text_content, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            text_x, text_y = (W - tw) // 2, 100
            
            draw.text((text_x, text_y), text_content, font=font, fill="white")
            canny_map = pil_canny_edge(text_guide)
            
            # 2. SDXL ControlNet
            shared_state['sub_step'] = 'sdxl_text_generation'
            shared_state['system_metrics'] = get_system_metrics()
            raw_3d_text = engine.run_sdxl_text_gen(
                canny_map, 
                prompt=text_model_prompt,
                negative_prompt=negative_prompt
            )
            
            # 3. 배경 제거 (Text Segmentation)
            shared_state['sub_step'] = 'text_segmentation'
            shared_state['system_metrics'] = get_system_metrics()
            transparent_text, _ = engine.run_segmentation(raw_3d_text)
            
            step2_result = transparent_text
            shared_state['images']['step2_result'] = pil_to_base64(step2_result)
            shared_state['progress_percent'] = 66
            
        else:
             # Step 2 건너뛸 경우
            img_s2_b64 = input_data.get('step2_image')
            if img_s2_b64:
                step2_result = base64_to_pil(img_s2_b64)
                shared_state['images']['step2_result'] = img_s2_b64

        # ==========================================
        # Step 3: 최종 합성 (Final Composite)
        # ==========================================
        if start_step <= 3:
            if stop_event.is_set(): return

            shared_state['current_step'] = 'step3_composite'
            shared_state['message'] = 'Step 3: Final Compositing... (최종 합성 중)'
            shared_state['sub_step'] = 'final_composite'
            shared_state['system_metrics'] = get_system_metrics()
            
            # Step 1, Step 2 결과물 확보 확인
            if not step1_result and shared_state['images'].get('step1_result'):
                step1_result = base64_to_pil(shared_state['images']['step1_result'])
                
            if not step2_result and shared_state['images'].get('step2_result'):
                step2_result = base64_to_pil(shared_state['images']['step2_result'])
                
            if not step1_result:
                raise ValueError("[Step 3 Error] Missing 'step1_result'. Cannot composite.")
            if not step2_result:
                raise ValueError("[Step 3 Error] Missing 'step2_result'. Cannot composite.")
            
            # [Logic] 합성
            base_comp = step1_result.convert("RGBA")
            text_asset = step2_result.convert("RGBA")
            
            # 텍스트 위치 등은 현재 고정 (추후 파라미터화 가능)
            # text_asset은 1024x1024 전체 캔버스 기준이므로 그대로 겹치면 됨 (위치 조정은 Step 2에서 이미 결정됨)
            if base_comp.size != text_asset.size:
                text_asset = text_asset.resize(base_comp.size, Image.LANCZOS)
                
            final_comp = Image.alpha_composite(base_comp, text_asset)
            final_result = final_comp.convert("RGB")
            
            shared_state['images']['final_result'] = pil_to_base64(final_result)
            shared_state['progress_percent'] = 100

        # 완료 처리
        if stop_event.is_set():
            shared_state['status'] = 'stopped'
            shared_state['message'] = 'Job stopped by user.'
        else:
            shared_state['status'] = 'completed'
            shared_state['message'] = 'All steps completed successfully.'

    finally:
        flush_gpu()
