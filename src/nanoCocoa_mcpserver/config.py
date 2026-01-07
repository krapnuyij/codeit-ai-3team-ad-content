"""
nanoCocoa MCP Server 설정
nanoCocoa_aiserver를 제어하는 MCP 서버의 설정 상수들
"""

import os
from typing import Final

# =============================================================================
# AI 서버 연결 설정
# =============================================================================

AISERVER_BASE_URL: Final[str] = os.getenv(
    "AISERVER_BASE_URL", "http://localhost:8000"
)
"""nanoCocoa_aiserver REST API의 기본 URL"""

AISERVER_TIMEOUT: Final[int] = int(os.getenv("AISERVER_TIMEOUT", "600"))
"""API 요청 타임아웃 (초 단위, 기본값: 10분)"""

AISERVER_CONNECT_TIMEOUT: Final[int] = int(
    os.getenv("AISERVER_CONNECT_TIMEOUT", "10")
)
"""연결 타임아웃 (초 단위)"""

# =============================================================================
# 폴링 설정
# =============================================================================

STATUS_POLL_INTERVAL: Final[float] = float(
    os.getenv("STATUS_POLL_INTERVAL", "3.0")
)
"""상태 폴링 요청 간격 (초 단위)"""

MAX_POLL_RETRIES: Final[int] = int(os.getenv("MAX_POLL_RETRIES", "200"))
"""최대 상태 폴링 시도 횟수 (3초 간격으로 약 10분)"""

RETRY_BACKOFF_FACTOR: Final[float] = 1.5
"""재시도 시 지수 백오프 계수"""

MAX_RETRY_DELAY: Final[float] = 30.0
"""재시도 간 최대 대기 시간 (초 단위)"""

# =============================================================================
# MCP 서버 설정
# =============================================================================

MCP_SERVER_NAME: Final[str] = "nanococoa-ad-generator"
"""MCP 서버 식별 이름"""

MCP_SERVER_VERSION: Final[str] = "1.0.0"
"""MCP 서버 버전"""

MCP_SERVER_DESCRIPTION: Final[str] = (
    "AI 기반 광고 이미지 생성을 위한 MCP 서버. "
    "nanoCocoa_aiserver를 제어하여 배경 생성, 3D 텍스트 렌더링, "
    "지능형 합성을 통한 전문적인 광고 이미지를 생성합니다."
)

# =============================================================================
# HTTP 클라이언트 설정
# =============================================================================

HTTP_MAX_CONNECTIONS: Final[int] = 10
"""최대 동시 HTTP 연결 수"""

HTTP_MAX_KEEPALIVE_CONNECTIONS: Final[int] = 5
"""최대 Keep-Alive 연결 수"""

HTTP_KEEPALIVE_EXPIRY: Final[float] = 30.0
"""Keep-Alive 연결 만료 시간 (초 단위)"""

# =============================================================================
# 에러 처리
# =============================================================================

RETRY_STATUS_CODES: Final[set[int]] = {503}
"""자동 재시도를 트리거하는 HTTP 상태 코드"""

MAX_RETRIES_ON_503: Final[int] = 5
"""서버가 503(사용 중) 응답 시 최대 재시도 횟수"""

# =============================================================================
# 로깅 설정
# =============================================================================

LOG_LEVEL: Final[str] = os.getenv("LOG_LEVEL", "INFO")
"""로깅 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)"""

LOG_FORMAT: Final[str] = (
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
"""로그 메시지 포맷"""

LOG_FILE: Final[str] = os.getenv(
    "LOG_FILE", "/tmp/nanococoa_mcpserver.log"
)
"""로그 파일 경로 (빈 문자열이면 콘솔만 사용)"""

# =============================================================================
# 이미지 처리
# =============================================================================

MAX_IMAGE_SIZE_MB: Final[int] = 20
"""업로드 가능한 최대 이미지 크기 (메가바이트)"""

SUPPORTED_IMAGE_FORMATS: Final[set[str]] = {"PNG", "JPEG", "JPG", "WEBP"}
"""지원하는 입력 이미지 포맷"""

# =============================================================================
# 기능 플래그
# =============================================================================

ENABLE_CACHING: Final[bool] = os.getenv("ENABLE_CACHING", "false").lower() == "true"
"""중간 결과(step1/step2) 캐싱 활성화 여부"""

ENABLE_METRICS: Final[bool] = os.getenv("ENABLE_METRICS", "true").lower() == "true"
"""성능 메트릭 수집 활성화 여부"""

ENABLE_PROGRESS_NOTIFICATIONS: Final[bool] = (
    os.getenv("ENABLE_PROGRESS_NOTIFICATIONS", "true").lower() == "true"
)
"""장시간 작업 중 MCP 진행 알림 활성화 여부"""

# =============================================================================
# API 엔드포인트 (AISERVER_BASE_URL 기준 상대 경로)
# =============================================================================

class APIEndpoints:
    """nanoCocoa_aiserver API 엔드포인트 경로"""

    # 생성 관련 엔드포인트
    GENERATE = "/generate"
    STATUS = "/status/{job_id}"
    STOP = "/stop/{job_id}"
    JOBS = "/jobs"
    DELETE_JOB = "/jobs/{job_id}"

    # 리소스 관련 엔드포인트
    FONTS = "/fonts"
    HEALTH = "/health"
    FONT_FILE = "/fonts/{font_path}"

    # 도움말 엔드포인트
    HELP = "/help"
    HELP_PARAMETERS = "/help/parameters"
    HELP_EXAMPLES = "/help/examples"

# =============================================================================
# 기본 파라미터
# =============================================================================

class DefaultParameters:
    """생성 파라미터 기본값"""

    START_STEP: int = 1
    COMPOSITION_MODE: str = "overlay"
    TEXT_POSITION: str = "auto"
    STRENGTH: float = 0.75
    GUIDANCE_SCALE: float = 7.5
    BG_NEGATIVE_PROMPT: str = "low quality, blurry, distorted"
    NEGATIVE_PROMPT: str = "low quality, blurry, flat, 2d"
    COMPOSITION_STRENGTH: float = 0.3
    COMPOSITION_STEPS: int = 30
    COMPOSITION_GUIDANCE_SCALE: float = 3.5
    AUTO_UNLOAD: bool = True
    TEST_MODE: bool = False

# =============================================================================
# 검증 제약조건
# =============================================================================

class ValidationConstraints:
    """파라미터 검증 제약조건"""

    MIN_START_STEP: int = 1
    MAX_START_STEP: int = 3

    MIN_STRENGTH: float = 0.0
    MAX_STRENGTH: float = 1.0

    MIN_GUIDANCE_SCALE: float = 1.0
    MAX_GUIDANCE_SCALE: float = 20.0

    MIN_COMPOSITION_STRENGTH: float = 0.0
    MAX_COMPOSITION_STRENGTH: float = 1.0

    MIN_COMPOSITION_STEPS: int = 10
    MAX_COMPOSITION_STEPS: int = 50

    MIN_COMPOSITION_GUIDANCE_SCALE: float = 1.0
    MAX_COMPOSITION_GUIDANCE_SCALE: float = 7.0

    VALID_COMPOSITION_MODES: set[str] = {"overlay", "blend", "behind"}
    VALID_TEXT_POSITIONS: set[str] = {"top", "center", "bottom", "auto"}
