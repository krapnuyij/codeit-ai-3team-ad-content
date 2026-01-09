"""
백엔드 통합 예제 1: MCPClient 직접 사용
FastAPI 백엔드에서 MCP 서버를 직접 호출
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging

# mcpadapter 임포트
from mcpadapter import MCPClient

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI 앱 생성
app = FastAPI(title="nanoCocoa Ad Generation Backend")

# MCP 클라이언트 (전역 싱글톤)
mcp_client = MCPClient(
    base_url="http://nanococoa-mcpserver:3000",  # Docker 네트워크 내부 URL
    timeout=600,
)


# 요청 모델
class AdGenerationRequest(BaseModel):
    product_image_path: str
    background_prompt: str
    text_content: str
    text_style_prompt: str
    font_name: Optional[str] = None
    composition_mode: str = "overlay"
    text_position: str = "auto"
    seed: Optional[int] = None
    test_mode: bool = False
    save_output_path: Optional[str] = None


class AdGenerationResponse(BaseModel):
    success: bool
    result: str
    error: Optional[str] = None


# API 엔드포인트
@app.post("/api/generate-ad", response_model=AdGenerationResponse)
async def generate_advertisement(request: AdGenerationRequest):
    """
    광고 이미지 생성 API

    MCP 서버의 generate_ad_image 도구를 호출하여 광고 생성
    """
    try:
        logger.info(f"광고 생성 요청: {request.text_content}")

        # MCP 도구 호출
        result = await mcp_client.call_tool(
            "generate_ad_image",
            {
                "product_image_path": request.product_image_path,
                "background_prompt": request.background_prompt,
                "text_content": request.text_content,
                "text_style_prompt": request.text_style_prompt,
                "font_name": request.font_name,
                "composition_mode": request.composition_mode,
                "text_position": request.text_position,
                "seed": request.seed,
                "test_mode": request.test_mode,
                "wait_for_completion": True,
                "save_output_path": request.save_output_path,
            },
        )

        logger.info("광고 생성 완료")
        return AdGenerationResponse(success=True, result=str(result))

    except Exception as e:
        logger.error(f"광고 생성 에러: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/server-health")
async def check_mcp_server_health():
    """MCP 서버 상태 확인"""
    try:
        result = await mcp_client.call_tool("check_server_health", {})
        return {"status": "healthy", "mcp_server": result}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@app.get("/api/fonts")
async def list_available_fonts():
    """사용 가능한 폰트 목록"""
    try:
        result = await mcp_client.call_tool("list_available_fonts", {})
        return {"fonts": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 앱 시작/종료 이벤트
@app.on_event("startup")
async def startup_event():
    """앱 시작 시 MCP 클라이언트 초기화"""
    logger.info("MCP 클라이언트 초기화 중...")
    await mcp_client._ensure_client()
    logger.info("MCP 클라이언트 준비 완료")


@app.on_event("shutdown")
async def shutdown_event():
    """앱 종료 시 MCP 클라이언트 종료"""
    logger.info("MCP 클라이언트 종료 중...")
    await mcp_client.close()
    logger.info("MCP 클라이언트 종료 완료")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
