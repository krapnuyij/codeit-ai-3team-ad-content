from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(title="Market AI Image Generator")

app.include_router(router)

@app.get("/")
def root():
    return {"status": "ok", "service": "market-ai-image-generator"}

# 테스트 단계 후 처리 예정