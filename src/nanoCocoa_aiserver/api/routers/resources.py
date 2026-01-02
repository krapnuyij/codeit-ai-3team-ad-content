"""
resources.py
시스템 리소스 및 정적 파일 관련 API 엔드포인트
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import os
import time
from FastAPI import APIRouter, HTTPException
from FastAPI.responses import FileResponse

from utils import get_available_fonts, get_system_metrics


router = APIRouter()

# 전역 상태 (generation.py에서 주입됨)
JOBS = None


def init_shared_state(jobs_dict):
    """공유 상태 초기화 (app.py에서 호출)"""
    global JOBS
    JOBS = jobs_dict


@router.get(
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


@router.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """파비콘 제공"""
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    return FileResponse(os.path.join(static_dir, "favicon.ico"))


@router.get(
    "/health",
    summary="서버 상태 체크 (Health Check)",
    response_description="서버 가용성, GPU 상태, 현재 작업 정보"
)
async def health_check():
    """
    서버의 현재 상태와 가용성을 확인합니다.

    ### 반환 필드 설명
    - **status**: "healthy" 또는 "busy" (작업 실행 여부)
    - **server_time**: 현재 서버 시간 (Unix timestamp)
    - **total_jobs**: 전체 작업 개수
    - **active_jobs**: 현재 실행 중이거나 대기 중인 작업 개수
    - **system_metrics**: 실시간 CPU/RAM/GPU 사용률
      - **cpu_percent**: CPU 사용률 (%)
      - **ram_used_gb**: 사용 중인 RAM (GB)
      - **ram_total_gb**: 전체 RAM (GB)
      - **ram_percent**: RAM 사용률 (%)
      - **gpu_info**: GPU 정보 리스트
        - **index**: GPU 인덱스
        - **name**: GPU 이름
        - **gpu_util**: GPU 사용률 (%)
        - **vram_used_gb**: 사용 중인 VRAM (GB)
        - **vram_total_gb**: 전체 VRAM (GB)
        - **vram_percent**: VRAM 사용률 (%)

    ### 사용 시나리오
    - 요청 전 서버 가용성 확인
    - GPU 메모리 상태 모니터링
    - 서버 부하 확인 및 최적화 시점 판단
    """
    metrics = get_system_metrics()

    # 활성 작업 개수 계산
    active_count = 0
    total_jobs = 0
    if JOBS:
        total_jobs = len(JOBS)
        for state in JOBS.values():
            if state['status'] in ('running', 'pending'):
                active_count += 1

    server_status = "busy" if active_count > 0 else "healthy"

    return {
        "status": server_status,
        "server_time": time.time(),
        "total_jobs": total_jobs,
        "active_jobs": active_count,
        "system_metrics": metrics
    }


@router.get("/fonts/{font_path:path}", include_in_schema=False)
async def serve_font(font_path: str):
    """
    폰트 파일 제공 (Custom File Response for Korean support)
    """
    from services.fonts import get_fonts_dir

    fonts_dir = get_fonts_dir()

    # URL decoding is handled by FastAPI automatically for path params
    full_path = os.path.join(fonts_dir, font_path)

    # Security check: Ensure the path is within fonts_dir
    try:
        common_prefix = os.path.commonpath([fonts_dir, full_path])
        if os.path.abspath(common_prefix) != os.path.abspath(fonts_dir):
            raise HTTPException(status_code=403, detail="Access denied")
    except ValueError:
         raise HTTPException(status_code=403, detail="Access denied")

    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail="Font not found")

    media_type = "font/ttf"
    if full_path.endswith(".otf"):
        media_type = "font/otf"

    return FileResponse(full_path, media_type=media_type)
