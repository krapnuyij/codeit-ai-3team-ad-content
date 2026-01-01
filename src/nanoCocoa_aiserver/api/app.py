"""
app.py
FastAPI 애플리케이션 초기화 및 설정
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import multiprocessing
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from config import logger
from utils import get_system_metrics
from api.middleware import FontHeaderMiddleware
from api.routers import generation, resources, dev_dashboard, help


# 전역 상태 관리
manager = multiprocessing.Manager()
JOBS = manager.dict()
PROCESSES = {}
STOP_EVENTS = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 라이프사이클 관리"""
    metrics = get_system_metrics()
    logger.info(f"System Check: {metrics}")
    yield
    for pid, proc in PROCESSES.items():
        if proc.is_alive():
            proc.terminate()
    manager.shutdown()


def create_app() -> FastAPI:
    """FastAPI 애플리케이션 생성 및 설정"""
    
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
    
    app.router.lifespan_context = lifespan
    
    # Middleware
    app.add_middleware(FontHeaderMiddleware)
    
    # Static files
    base_dir = os.path.dirname(os.path.dirname(__file__))
    app.mount("/static", StaticFiles(directory=os.path.join(base_dir, "static")), name="static")
    app.mount("/fonts", StaticFiles(directory=os.path.join(base_dir, "fonts")), name="fonts")
    
    # 라우터에 전역 상태 주입
    generation.init_shared_state(manager, JOBS, PROCESSES, STOP_EVENTS)
    resources.init_shared_state(JOBS)

    # 라우터 등록
    app.include_router(generation.router, tags=["Generation"])
    app.include_router(resources.router, tags=["Resources"])
    app.include_router(help.router, tags=["Help & Documentation"])
    app.include_router(dev_dashboard.router, tags=["Development"])
    
    # Root endpoint
    @app.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse(url="/docs")
    
    return app


# 애플리케이션 인스턴스 생성
app = create_app()
