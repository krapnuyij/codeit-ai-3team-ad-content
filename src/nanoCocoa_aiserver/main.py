"""
main.py
FastAPI 애플리케이션 진입점
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from api.app import app, JOBS, PROCESSES, STOP_EVENTS

__all__ = ['app', 'JOBS', 'PROCESSES', 'STOP_EVENTS']
