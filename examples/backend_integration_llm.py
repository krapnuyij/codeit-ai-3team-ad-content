"""
백엔드 통합 예제 2: LLMAdapter 사용
FastAPI 백엔드에서 자연어 입력을 받아 LLM이 MCP 도구를 호출
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import logging
import os

# mcpadapter 임포트
from mcpadapter import LLMAdapter

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI 앱 생성
app = FastAPI(title="nanoCocoa AI Chat Backend")

# OpenAI API 키 (환경변수에서 로드)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY가 설정되지 않았습니다!")


# 요청 모델
class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str


# API 엔드포인트
@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_ai(request: ChatRequest):
    """
    자연어 기반 광고 생성 API

    사용자의 자연어 메시지를 LLM이 해석하여
    자동으로 적절한 MCP 도구를 호출

    예: "product.png로 여름 세일 광고를 만들어줘"
    """
    try:
        logger.info(f"Chat 요청: {request.message}")

        # LLM Adapter 생성 및 대화
        async with LLMAdapter(
            openai_api_key=OPENAI_API_KEY,
            mcp_server_url="http://nanococoa-mcpserver:3000",
            model="gpt-4o",
        ) as adapter:
            response = await adapter.chat(request.message)

        logger.info("Chat 응답 생성 완료")
        return ChatResponse(response=response)

    except Exception as e:
        logger.error(f"Chat 에러: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """헬스체크"""
    return {
        "status": "healthy",
        "service": "nanoCocoa AI Chat Backend",
        "openai_configured": bool(OPENAI_API_KEY),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
