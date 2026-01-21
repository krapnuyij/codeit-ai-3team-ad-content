"""
서버 헬스체크 핸들러 함수
"""

import logging

from handlers.generation import get_api_client
from client.api_client import AIServerError

from helper_dev_utils import get_auto_logger

logger = get_auto_logger()


async def check_server_health() -> str:
    """
    AI 서버가 정상적으로 실행 중인지 확인하고 시스템 리소스 사용 현황을 조회합니다.

    사용 시나리오:
    - 광고 생성 전 AI 서버 연결 상태 확인
    - GPU 메모리가 충분한지 사전 체크
    - 서버 과부하 상태 확인 (여러 작업 동시 실행 중인지)
    - 에러 발생 시 서버 문제인지 디버깅

    반환 정보:
    - 서버 상태 (healthy/unhealthy)
    - 전체 작업 수 및 현재 실행 중인 작업 수
    - CPU 사용률 (%)
    - RAM 사용량 (GB) 및 사용률 (%)
    - GPU 사용률 (%) 및 VRAM 사용량 (GB) - GPU가 있는 경우

    정상 상태 기준:
    - status: "healthy"
    - active_jobs: 0~2개 (동시 작업이 많으면 느려질 수 있음)
    - GPU VRAM: 12GB 이상 여유 (Flux 모델 실행에 필요)

    Returns:
        서버 상태 및 시스템 리소스 정보 텍스트

    사용 예시:
        작업 전에 항상 check_server_health()를 호출하여 서버가 준비되었는지 확인하세요.
    """
    try:
        client = await get_api_client()
        health = await client.check_health()

        response = (
            f"서버 상태: {health.status}\n"
            f"전체 작업: {health.total_jobs}개\n"
            f"활성 작업: {health.active_jobs}개\n"
        )

        if health.system_metrics:
            metrics = health.system_metrics
            response += (
                f"\n시스템 리소스:\n"
                f"  CPU: {metrics.cpu_percent:.1f}%\n"
                f"  RAM: {metrics.ram_used_gb:.1f}/{metrics.ram_total_gb:.1f} GB "
                f"({metrics.ram_percent:.1f}%)\n"
            )
            if metrics.gpu_info:
                for gpu in metrics.gpu_info:
                    response += (
                        f"  GPU {gpu.index} ({gpu.name}): {gpu.gpu_util}%, "
                        f"VRAM: {gpu.vram_used_gb:.1f}/{gpu.vram_total_gb:.1f} GB\n"
                    )

        return response

    except AIServerError as e:
        return f"AI 서버 에러: {str(e)}"
