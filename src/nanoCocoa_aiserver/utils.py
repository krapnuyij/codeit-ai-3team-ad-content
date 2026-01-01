"""
유틸리티 함수 통합 모듈 (하위 호환성).

이 파일은 기존 코드의 하위 호환성을 위해 분리된 모듈의 함수들을 re-export합니다.
새 코드에서는 개별 모듈을 직접 import하는 것을 권장합니다:
    - image_utils: 이미지 변환 및 처리
    - system_monitor: CPU/GPU 모니터링 및 메모리 관리
    - font_manager: 폰트 디렉토리 관리
    - stats_manager: 단계별 통계 관리
"""

# Image utilities
from image_utils import (
    pil_to_base64,
    base64_to_pil,
    pil_canny_edge,
)

# System monitoring
from system_monitor import (
    flush_gpu,
    get_system_metrics,
)

# Font management
from font_manager import (
    get_fonts_dir,
    get_available_fonts,
    get_font_path,
)

# Stats management
from stats_manager import (
    StepStatsManager,
    step_stats_manager,
)

__all__ = [
    # Image utilities
    "pil_to_base64",
    "base64_to_pil",
    "pil_canny_edge",
    # System monitoring
    "flush_gpu",
    "get_system_metrics",
    # Font management
    "get_fonts_dir",
    "get_available_fonts",
    "get_font_path",
    # Stats management
    "StepStatsManager",
    "step_stats_manager",
]
