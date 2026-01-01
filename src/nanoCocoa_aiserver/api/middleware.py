"""
middleware.py
FastAPI 미들웨어 정의
"""
from starlette.middleware.base import BaseHTTPMiddleware


class FontHeaderMiddleware(BaseHTTPMiddleware):
    """폰트 파일 응답 헤더 설정 미들웨어"""
    
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/fonts/"):
            # 폰트 파일 MIME 타입 및 CORS 헤더 설정
            if request.url.path.endswith(".ttf"):
                response.headers["Content-Type"] = "font/ttf"
            elif request.url.path.endswith(".otf"):
                response.headers["Content-Type"] = "font/otf"
            response.headers["Access-Control-Allow-Origin"] = "*"
        return response
