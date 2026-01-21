"""
유틸리티 함수 통합 모듈 (하위 호환성).

이 파일은 기존 코드의 하위 호환성을 위해 분리된 모듈의 함수들을 re-export합니다.
새 코드에서는 개별 모듈을 직접 import하는 것을 권장합니다:
    - image_utils: 이미지 변환 및 처리
    - system_monitor: CPU/GPU 모니터링 및 메모리 관리
    - font_manager: 폰트 디렉토리 관리
    - stats_manager: 단계별 통계 관리
"""


# Lazy import를 위한 __getattr__ 구현
def __getattr__(name):
    # Image utilities
    if name in ("pil_to_base64", "base64_to_pil", "pil_canny_edge"):
        from utils.images import base64_to_pil, pil_canny_edge, pil_to_base64

        return locals()[name]
    # System monitoring
    elif name in ("flush_gpu", "get_system_metrics", "log_gpu_memory"):
        from services.monitor import (flush_gpu, get_system_metrics,
                                      log_gpu_memory)

        return locals()[name]
    # Font management
    elif name in ("get_fonts_dir", "get_available_fonts", "get_font_path"):
        from services.fonts import (get_available_fonts, get_font_path,
                                    get_fonts_dir)

        return locals()[name]
    # Stats management
    elif name in ("StepStatsManager", "step_stats_manager"):
        from services.stats import StepStatsManager, step_stats_manager

        return locals()[name]
    raise AttributeError(f"module 'utils' has no attribute '{name}'")


__all__ = [
    # Image utilities
    "pil_to_base64",
    "base64_to_pil",
    "pil_canny_edge",
    # System monitoring
    "flush_gpu",
    "get_system_metrics",
    "log_gpu_memory",
    # Font management
    "get_fonts_dir",
    "get_available_fonts",
    "get_font_path",
    # Stats management
    "StepStatsManager",
    "step_stats_manager",
]
