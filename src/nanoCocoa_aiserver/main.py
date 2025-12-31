import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

import multiprocessing
import uuid
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Response, status
from fastapi.responses import HTMLResponse
import os

# 모듈화된 파일들에서 import
from config import logger, TOTAL_ESTIMATED_TIME
from utils import get_system_metrics, get_available_fonts
from schemas import GenerateRequest, StatusResponse, SystemMetrics, GPUMetric
from worker import worker_process

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
        "email": "c0z0c.dev@gmail.com",
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

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Static files mount
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")
app.mount("/fonts", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "fonts")), name="fonts")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "favicon.ico"))

@app.get("/test", response_class=HTMLResponse)
async def test_dashboard():
    """
    개발 및 테스트를 위한 대시보드 페이지를 반환합니다.
    """
    with open(os.path.join(os.path.dirname(__file__), "templates", "test_dashboard.html"), "r", encoding="utf-8") as f:
        return f.read()

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
    response_model=StatusResponse,
    summary="작업 상태 및 결과 조회 (Get Job Status)",
    response_description="진행률, 현재 단계, 생성된 이미지(Base64), 시스템 메트릭 및 파라미터"
)
async def get_status(job_id: str):
    """
    특정 작업(Job)의 현재 진행 상황과 중간/최종 결과물을 조회합니다.
    실시간 CPU/GPU 사용률 및 서브스텝 정보를 포함합니다.
    
    ### 반환 필드 설명
    - **status**: `pending`, `running`, `completed`, `failed`, `stopped`
    - **progress_percent**: 0 ~ 100 진행률
    - **current_step**: 현재 수행 중인 단계 (`step1_background` 등)
    - **sub_step**: 현재 수행 중인 서브 단계 (`segmentation`, `flux_background_generation` 등)
    - **system_metrics**: 실시간 CPU/RAM/GPU 사용률
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
    
    # 실시간 시스템 메트릭 가져오기
    current_metrics = get_system_metrics()
    system_metrics_model = SystemMetrics(
        cpu_percent=current_metrics['cpu_percent'],
        ram_used_gb=current_metrics['ram_used_gb'],
        ram_total_gb=current_metrics['ram_total_gb'],
        ram_percent=current_metrics['ram_percent'],
        gpu_info=[GPUMetric(**gpu) for gpu in current_metrics['gpu_info']]
    )
    
    return StatusResponse(
        job_id=job_id,
        status=state['status'],
        progress_percent=state['progress_percent'],
        current_step=state['current_step'],
        sub_step=state.get('sub_step'),
        message=state['message'],
        elapsed_sec=round(elapsed, 1),
        system_metrics=system_metrics_model,
        parameters=state.get('parameters', {}),
        step1_result=images_snapshot.get('step1_result'),
        step2_result=images_snapshot.get('step2_result'),
        final_result=images_snapshot.get('final_result')
    )

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