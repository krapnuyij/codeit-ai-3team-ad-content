"""
환경 설정 파일

모든 상수, URL, 데이터베이스 연결 정보 등을 중앙 관리
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# mcpadapter 경로 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# 환경 변수 로드
load_dotenv()

# ===================================================================
# MCP 서버 설정
# ===================================================================
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://34.44.205.198:3000")
MCP_TIMEOUT = int(os.getenv("MCP_TIMEOUT", "30"))
MCP_MAX_RETRIES = int(os.getenv("MCP_MAX_RETRIES", "3"))

# ===================================================================
# MongoDB 설정
# ===================================================================
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "ai_ad_generator")
MONGO_COLLECTION_JOBS = "jobs"
MONGO_COLLECTION_PROMPTS = "prompts"

# ===================================================================
# 작업 상태 폴링 설정
# ===================================================================
POLLING_INTERVAL = int(os.getenv("POLLING_INTERVAL", "10"))  # 초
POLLING_MAX_ATTEMPTS = int(
    os.getenv("POLLING_MAX_ATTEMPTS", "180")
)  # 30분 = 180 * 10초

# ===================================================================
# 파일 경로 설정 (Docker/로컬 환경 자동 감지)
# ===================================================================
PROJECT_ROOT = Path(__file__).parent.parent.parent


def get_static_paths():
    """
    환경 변수 기반 static 경로 반환

    - Docker 환경: RUNTIME_ENV=docker, STATIC_BASE_PATH=/app/static
    - 로컬 환경: RUNTIME_ENV 미설정 또는 'local'

    Returns:
        tuple: (STATIC_BASE, UPLOADS_DIR, RESULTS_DIR)
    """
    runtime_env = os.getenv("RUNTIME_ENV", "local")

    if runtime_env == "docker":
        # Docker 환경: nanoCocoa_aiserver 컨테이너의 /app/static
        static_base = Path(os.getenv("STATIC_BASE_PATH", "/app/static"))
    else:
        # 로컬 환경: 프로젝트 루트 기준 상대 경로
        static_base = PROJECT_ROOT / "src" / "nanoCocoa_aiserver" / "static"

    uploads_dir = static_base / "uploads"
    results_dir = static_base / "results"

    # 디렉토리 자동 생성 (로컬 환경만)
    if runtime_env == "local":
        uploads_dir.mkdir(parents=True, exist_ok=True)
        results_dir.mkdir(parents=True, exist_ok=True)

    return static_base, uploads_dir, results_dir


# 경로 초기화
STATIC_BASE, UPLOADS_DIR, RESULTS_DIR = get_static_paths()

# ===================================================================
# OpenAI API 설정
# ===================================================================
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "1.0"))
OPENAI_MAX_COMPLETION_TOKENS = int(os.getenv("OPENAI_MAX_COMPLETION_TOKENS", "128000"))

# ===================================================================
# Streamlit 설정
# ===================================================================
PAGE_TITLE = "AI 광고 생성 시스템"
PAGE_ICON = "🎨"
LAYOUT = "wide"

# ===================================================================
# 작업 타입 정의
# ===================================================================
JOB_TYPE_FULL = "full"  # 이미지 + 텍스트 생성
JOB_TYPE_TEXT_ONLY = "text_only"  # 텍스트만 생성

# ===================================================================
# 작업 상태 정의
# ===================================================================
STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_TIMEOUT = "timeout"
