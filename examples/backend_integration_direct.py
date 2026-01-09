"""
백엔드 통합 예제 3: REST API 직접 호출
FastAPI 백엔드에서 nanoCocoa_aiserver REST API를 직접 호출 (MCP 없이)
"""

from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional
import httpx
import base64
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI 앱 생성
app = FastAPI(title="nanoCocoa Direct API Backend")

# AI 서버 URL
AISERVER_URL = "http://nanococoa-aiserver:8000"


# 요청 모델
class DirectGenerateRequest(BaseModel):
    input_image_base64: str
    bg_prompt: str
    text_content: str
    text_model_prompt: str
    font_name: Optional[str] = None
    test_mode: bool = False


class GenerateResponse(BaseModel):
    job_id: str
    status: str
    message: str


# API 엔드포인트
@app.post("/api/direct-generate", response_model=GenerateResponse)
async def direct_generate_ad(request: DirectGenerateRequest):
    """
    AI 서버에 직접 광고 생성 요청 (MCP 없이)

    가장 단순하고 빠른 방식
    """
    try:
        logger.info("직접 API 호출로 광고 생성")

        async with httpx.AsyncClient(timeout=600.0) as client:
            response = await client.post(
                f"{AISERVER_URL}/generate",
                json={
                    "start_step": 1,
                    "input_image": request.input_image_base64,
                    "bg_prompt": request.bg_prompt,
                    "text_content": request.text_content,
                    "text_model_prompt": request.text_model_prompt,
                    "font_name": request.font_name,
                    "test_mode": request.test_mode,
                },
            )
            response.raise_for_status()
            data = response.json()

        return GenerateResponse(**data)

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/upload-and-generate")
async def upload_and_generate(
    file: UploadFile = File(...),
    bg_prompt: str = "Luxury studio background",
    text_content: str = "SALE",
    text_model_prompt: str = "Gold 3D text",
):
    """
    이미지 업로드 + 광고 생성 통합 API
    """
    try:
        # 이미지를 Base64로 인코딩
        image_bytes = await file.read()
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        # 광고 생성 요청
        request = DirectGenerateRequest(
            input_image_base64=image_base64,
            bg_prompt=bg_prompt,
            text_content=text_content,
            text_model_prompt=text_model_prompt,
        )

        return await direct_generate_ad(request)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/status/{job_id}")
async def check_job_status(job_id: str):
    """작업 상태 확인"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{AISERVER_URL}/status/{job_id}")
            response.raise_for_status()
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """헬스체크"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{AISERVER_URL}/health")
            aiserver_healthy = response.status_code == 200
    except:
        aiserver_healthy = False

    return {
        "status": "healthy" if aiserver_healthy else "degraded",
        "aiserver": "healthy" if aiserver_healthy else "unhealthy",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
