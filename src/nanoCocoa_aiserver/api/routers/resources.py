"""
resources.py
시스템 리소스 및 정적 파일 관련 API 엔드포인트
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import os
from fastapi import APIRouter
from fastapi.responses import FileResponse

from utils import get_available_fonts


router = APIRouter()


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


@router.get("/fonts/{font_path:path}", include_in_schema=False)
async def serve_font(font_path: str):
    """
    폰트 파일 제공 (Custom File Response for Korean support)
    """
    from services.fonts import get_fonts_dir
    import os
    from fastapi import HTTPException
    
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
