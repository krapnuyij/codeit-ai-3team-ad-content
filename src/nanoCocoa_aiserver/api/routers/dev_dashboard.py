"""
개발자용 대시보드 라우터.

REST API 테스트용 웹 대시보드를 제공합니다.
환경변수 ENABLE_DEV_DASHBOARD로 활성화/비활성화 제어 가능합니다.
"""

import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from fastapi import APIRouter, Response, status
from fastapi.responses import HTMLResponse

from helper_dev_utils import get_auto_logger

logger = get_auto_logger()

router = APIRouter(
    prefix="",
    tags=["개발자 도구 (Development Tools)"],
)

# 환경변수로 대시보드 활성화 제어
ENABLE_DEV_DASHBOARD = os.getenv("ENABLE_DEV_DASHBOARD", "true").lower() in (
    "true",
    "1",
    "yes",
)


@router.get("/example_generation", response_class=HTMLResponse)
async def example_generation_dashboard(response: Response):
    """
    개발 및 테스트를 위한 대시보드 페이지를 반환합니다.

    이 엔드포인트는 REST API 테스트 용도로 제공됩니다.
    프로덕션 환경에서는 환경변수 ENABLE_DEV_DASHBOARD=false로 비활성화할 수 있습니다.

    **🔗 [대시보드 바로가기](/example_generation)**

    Returns:
        HTMLResponse: 대시보드 HTML 페이지

    Raises:
        404: 대시보드가 비활성화된 경우
    """
    if not ENABLE_DEV_DASHBOARD:
        logger.warning("Dev dashboard is disabled via ENABLE_DEV_DASHBOARD env var")
        response.status_code = status.HTTP_404_NOT_FOUND
        return "<h1>404 - Dev Dashboard Disabled</h1><p>Set ENABLE_DEV_DASHBOARD=true to enable.</p>"

    template_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "templates",
        "example_generation.html",
    )

    if not os.path.exists(template_path):
        logger.error(f"Template not found: {template_path}")
        response.status_code = status.HTTP_404_NOT_FOUND
        return "<h1>404 - Template Not Found</h1>"

    try:
        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()
        logger.info("Dev dashboard served successfully")
        return content
    except Exception as e:
        logger.error(f"Failed to read dashboard template: {e}")
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return f"<h1>500 - Internal Server Error</h1><p>{str(e)}</p>"
