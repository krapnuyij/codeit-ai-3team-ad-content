"""
main.py
FastAPI 애플리케이션 진입점
"""

import multiprocessing
import sys
from pathlib import Path

# CUDA 멀티프로세싱 호환성을 위해 spawn 방식 사용
# fork 방식은 CUDA 컨텍스트 재초기화 불가
multiprocessing.set_start_method("spawn", force=True)

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from api.app import JOBS, PROCESSES, STOP_EVENTS, app

__all__ = ["app", "JOBS", "PROCESSES", "STOP_EVENTS"]
