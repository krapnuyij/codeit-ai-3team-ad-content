
import multiprocessing
import uuid
import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Response, status
from PIL import Image, ImageDraw, ImageFont

# 모듈화된 파일들에서 import
from .config import logger, TOTAL_ESTIMATED_TIME
from .utils import pil_to_base64, base64_to_pil, flush_gpu, get_system_metrics, pil_canny_edge, get_available_fonts, get_font_path
from .schemas import GenerateRequest, ResumeRequest
from .AIModelEngine import AIModelEngine

# ==========================================
# 🔄 백그라운드 워커 (Background Worker)
# ==========================================
def worker_process(job_id: str, input_data: dict, shared_state: dict, stop_event: multiprocessing.Event):
    """
    Step 기반(1->2->3) 순차 실행 워커 프로세스.
    """
    
    # 파라미터 추출
    test_mode = input_data.get('test_mode', False)
    
    engine = AIModelEngine(dummy_mode=test_mode)
    
    try:
        shared_state['status'] = 'running'
        shared_state['start_time'] = time.time()
        
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
            product_fg, mask = engine.run_segmentation(raw_img)
            
            # 2. 배경 생성 (Flux Text-to-Image)
            bg_img = engine.run_flux_bg_gen(prompt=bg_prompt, guidance_scale=guidance_scale, seed=seed)
            
            # 3. 초안 합성 (Composite Draft)
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
            raw_3d_text = engine.run_sdxl_text_gen(
                canny_map, 
                prompt=text_model_prompt,
                negative_prompt=negative_prompt
            )
            
            # 3. 배경 제거 (Text Segmentation)
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

# ==========================================
# 🌐 FastAPI App & MCP Schemas
# ==========================================
app = FastAPI(
    title="L4 Optimized AI Ad Generator (Step-based)",
    description="""
    # L4 최적화 AI 광고 생성 서버 (AI Ad Generator Server)
    
    이 서버는 상품 이미지를 입력받아 배경을 생성하고, 3D 텍스트 효과를 합성하여 완성된 광고 이미지를 제작하는 파이프라인을 제공합니다.
    Nvidia L4 GPU에 최적화된 모델(BiRefNet, FLUX-schnell, SDXL ControlNet)을 사용하여 고품질 이미지를 생성합니다.

    ## 주요 기능
    - **동시성 제어**: 리소스 과부하 방지를 위해 한 번에 하나의 작업(Job)만 처리합니다.
    - **Step-based 실행**: 배경 생성(Step 1), 텍스트 생성(Step 2), 최종 합성(Step 3)을 단계별로 제어 가능합니다.
    - **중간 결과 재사용**: 각 단계의 결과물을 활용하여 중간부터 다시 시도하거나 수정할 수 있습니다.
    """,
    version="2.0.0",
    contact={
        "name": "AI Team",
        "email": "support@codeit-ai.com",
    },
)

manager = multiprocessing.Manager()
JOBS = manager.dict()
PROCESSES = {}
STOP_EVENTS = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    metrics = get_system_metrics()
    logger.info(f"System Check: {metrics}")
    yield
    for pid, proc in PROCESSES.items():
        if proc.is_alive():
            proc.terminate()
    manager.shutdown()

app.router.lifespan_context = lifespan

@app.get(
    "/fonts", 
    summary="사용 가능한 폰트 목록 조회 (Get Font List)",
    response_description="서버에 저장된 TTF/OTF 폰트 파일 목록"
)
async def get_fonts():
    """
    서버의 `fonts` 디렉토리에서 사용 가능한 모든 폰트 목록을 조회합니다.
    
    - **fonts**: 폰트 파일 경로 리스트 (예: `["NanumGothic/NanumGothic.ttf", ...]`)
    
    이 목록의 값을 `/generate` 요청의 `font_name` 필드에 입력하여 사용할 수 있습니다.
    """
    return {"fonts": get_available_fonts()}

@app.post(
    "/generate", 
    summary="AI 광고 생성 작업 시작 (Start Generation Job)",
    response_description="생성된 작업의 ID와 상태",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "작업이 성공적으로 큐에 등록되고 시작됨",
            "content": {
                "application/json": {
                    "example": {"job_id": "550e8400-e29b-41d4-a716-446655440000", "status": "started"}
                }
            }
        },
        503: {
            "description": "서버가 다른 작업을 처리 중임 (Busy)",
            "content": {
                "application/json": {
                    "example": {
                        "status": "busy",
                        "message": "현재 다른 작업이 진행 중입니다. 약 25초 후에 다시 시도해주세요.",
                        "retry_after": 25
                    }
                }
            }
        }
    }
)
async def generate_ad(req: GenerateRequest, response: Response):
    """
     **새로운 생성 파이프라인을 시작합니다.** (Non-blocking)
    
    클라이언트는 `job_id`를 반환받은 후, `/status/{job_id}`를 폴링하여 진행 상황과 결과를 확인해야 합니다.
    
    ### Step 구조 및 실행 방법
    1. **Step 1 (Background)**:
       - `start_step=1` (기본값)
       - `input_image` (누끼 딸 상품 이미지) 필수
    2. **Step 2 (Text Asset)**:
       - `start_step=2`
       - `step1_image` (배경 합성된 이미지) 필수
       - 텍스트만 다시 생성하고 싶을 때 사용
    3. **Step 3 (Composition)**:
       - `start_step=3`
       - `step1_image` (배경), `step2_image` (텍스트) 필수
       - 단순히 두 이미지를 합성만 다시 하고 싶을 때 사용
       
    ### 동시성 정책
    - 이 서버는 **단일 작업(Single Job)**만 처리합니다.
    - 이미 작업이 돌고 있을 경우 **503 Service Unavailable** 응답과 함께 `Retry-After` 헤더를 반환합니다.
    """
    
    # 동시성 제어
    active_jobs = [j for j, s in JOBS.items() if s['status'] in ('running', 'pending')]
    if active_jobs:
        curr = JOBS[active_jobs[0]]
        elapsed = time.time() - (curr['start_time'] or time.time())
        remain = max(0, TOTAL_ESTIMATED_TIME - elapsed)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        response.headers["Retry-After"] = str(int(remain))
        return {"status": "busy", "message": f"Busy. Retry after {int(remain)}s", "retry_after": int(remain)}

    job_id = str(uuid.uuid4())
    stop_event = multiprocessing.Event()
    input_data = req.model_dump()
    
    JOBS[job_id] = manager.dict({
        "status": "pending",
        "progress_percent": 0,
        "current_step": "init",
        "message": "Initializing...",
        "error": None,
        "images": manager.dict(), 
        "start_time": None,
        "parameters": input_data
    })
    
    p = multiprocessing.Process(
        target=worker_process,
        args=(job_id, input_data, JOBS[job_id], stop_event)
    )
    p.start()
    PROCESSES[job_id] = p
    STOP_EVENTS[job_id] = stop_event
    
    return {"job_id": job_id, "status": "started"}

@app.get(
    "/status/{job_id}", 
    summary="작업 상태 및 결과 조회 (Get Job Status)",
    response_description="진행률, 현재 단계, 생성된 이미지(Base64) 및 파라미터"
)
async def get_status(job_id: str):
    """
    특정 작업(Job)의 현재 진행 상황과 중간/최종 결과물을 조회합니다.
    
    ### 반환 필드 설명
    - **status**: `pending`, `running`, `completed`, `failed`, `stopped`
    - **progress_percent**: 0 ~ 100 진행률
    - **current_step**: 현재 수행 중인 단계 (`step1_background` 등)
    - **parameters**: 작업 생성 시 사용된 모든 입력 파라미터 (재시도 시 유용)
    - **step1_result**: [Optional] 1단계 결과 (Base64 이미지)
    - **step2_result**: [Optional] 2단계 결과 (Base64 이미지)
    - **final_result**: [Optional] 최종 결과 (Base64 이미지)
    """
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
    
    state = JOBS[job_id]
    elapsed = time.time() - state['start_time'] if state['start_time'] else 0
    
    # ManagerDict -> dict copy needed before serializing
    images_snapshot = dict(state['images'])
    
    return {
        "job_id": job_id,
        "status": state['status'],
        "progress_percent": state['progress_percent'],
        "current_step": state['current_step'],
        "message": state['message'],
        "elapsed_sec": round(elapsed, 1),
        "parameters": state.get('parameters', {}),
        "step1_result": images_snapshot.get('step1_result'), # Base64 Data
        "step2_result": images_snapshot.get('step2_result'),
        "final_result": images_snapshot.get('final_result'),
        # "full_images" key removed as specific keys are now provided
    }

@app.post(
    "/stop/{job_id}", 
    summary="작업 강제 중단 (Stop Job)",
    response_description="중단 요청 결과"
)
async def stop_job(job_id: str):
    """
    실행 중인 작업을 즉시 중단합니다.
    GPU 리소스를 해제하고 작업을 `stopped` 상태로 변경합니다.
    """
    if job_id in STOP_EVENTS:
        STOP_EVENTS[job_id].set()
    
    if job_id in PROCESSES:
        p = PROCESSES[job_id]
        if p.is_alive():
            p.join(timeout=3)
            if p.is_alive(): p.terminate()
        
        if job_id in JOBS: JOBS[job_id]['status'] = 'stopped'
        return {"job_id": job_id, "status": "stopped"}
        
    raise HTTPException(status_code=404, detail="Job not found")