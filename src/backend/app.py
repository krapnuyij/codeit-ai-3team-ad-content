from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

import onnxruntime
from openai import OpenAI

from pydantic import BaseModel
import base64

import json
import numpy as np
import cv2
import os
from typing import Union
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# Pydantic 모델
class AdPrompt(BaseModel):
    positive_prompt: str
    negative_prompt: str


# 의존성 주입 함수들
def get_client(request: Request):
    """클라이언트 인스턴스 반환"""
    return request.app.state.client

def get_use_openai(request: Request):
    """OpenAI 사용 여부 반환"""
    return request.app.state.use_openai

# 유틸리티 함수
def to_base64(image_bytes: bytes) -> str:
    """이미지 바이트를 base64 문자열로 변환"""
    encoded = base64.b64encode(image_bytes).decode('utf-8')
    return f"data:image/png;base64,{encoded}"

def process_with_openai(image_data: bytes, purpose:str, mood:str, client: OpenAI) -> AdPrompt:
    """OpenAI Responses API를 사용하여 프롬프트 생성"""
    try:
        encoded_image = to_base64(image_data)
        # Responses API의 parse 메서드 사용
        response = client.responses.parse(
            model="gpt-5-mini",
            input=[{
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": f"이 이미지를 참고해서 '{purpose}' 목적의 '{mood}' 분위기 광고용 이미지 생성을 위한 프롬프트를 만들어줘."
                    },
                    {
                        "type": "input_image",
                        "image_url": encoded_image  # ✅ 직접 문자열로 전달
                    }
                ]
            }],
            text_format=AdPrompt,  # Pydantic 모델로 자동 파싱
        )
        # ✅ JSON 문자열 → 딕셔너리 → AdPrompt 객체
        text = response.output[1].content[0].text
        parsed = json.loads(text)

        return AdPrompt(
            positive_prompt=parsed["positive_prompt"],
            negative_prompt=parsed["negative_prompt"]
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"OpenAI Responses API 호출 실패: {str(e)}"
        )

def process_with_onnx(image_data: bytes, ort_session) -> AdPrompt:
    """ONNX 모델을 사용하여 프롬프트 생성"""
    try:
        # 이미지 디코딩
        img = cv2.imdecode(
            np.frombuffer(image_data, np.uint8),
            cv2.IMREAD_COLOR
        )

        if img is None:
            raise ValueError("이미지 디코딩 실패")

        # 전처리 (모델에 맞게 조정 필요)
        img = cv2.resize(img, (224, 224))
        img = img.astype(np.float32) / 255.0
        img = np.transpose(img, (2, 0, 1))  # HWC -> CHW
        img = np.expand_dims(img, axis=0)  # 배치 차원 추가

        # ONNX 추론
        input_name = ort_session.get_inputs()[0].name
        output = ort_session.run(None, {input_name: img})

        # 결과 처리 (모델 출력에 맞게 조정 필요)
        positive_prompt = f"ONNX 모델 출력 기반 프롬프트: {output[0]}"
        negative_prompt = "low quality, blurry"

        return AdPrompt(
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"ONNX 모델 처리 실패: {str(e)}"
        )

# Lifespan 이벤트
@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 실행되는 로직"""
    print("🚀 앱 시작")

    api_key = os.getenv("OPENAI_API_KEY")
    app.state.use_openai = False

    # OpenAI 초기화 시도
    if api_key:
        try:
            app.state.client = OpenAI(api_key=api_key)
            app.state.use_openai = True
            print("✅ OpenAI 클라이언트 초기화 성공")
        except Exception as e:
            print(f"⚠️ OpenAI 초기화 실패: {e}")

    # ONNX 모델로 fallback
    if not app.state.use_openai:
        print("🔄 OpenAI 실패 → ONNX로 fallback")
        try:
            onnx_path = "model.onnx"
            app.state.client = onnxruntime.InferenceSession(onnx_path)
            print("✅ ONNX 모델 로드 성공")
        except Exception as e:
            print(f"❌ ONNX 로딩 실패: {e}")
            raise RuntimeError("모든 클라이언트 초기화 실패") from e

    yield

    # 앱 종료 시 cleanup
    print("🛑 앱 종료")


app = FastAPI(
    title="AI Image Prompt Generator",
    lifespan=lifespan
)

# Static 파일 마운트
app.mount("/static", StaticFiles(directory="static"), name="static")

# Jinja2 템플릿 설정
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """메인 페이지 (로그인)"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    """About 페이지"""
    return templates.TemplateResponse("about.html", {"request": request})


@app.get("/services", response_class=HTMLResponse)
async def services(request: Request):
    """Services 페이지"""
    return templates.TemplateResponse("services.html", {"request": request})


@app.get("/portfolio", response_class=HTMLResponse)
async def portfolio(request: Request):
    """Portfolio 페이지"""
    return templates.TemplateResponse("portfolio.html", {"request": request})


@app.get("/contact", response_class=HTMLResponse)
async def contact(request: Request):
    """Contact 페이지"""
    return templates.TemplateResponse("contact.html", {"request": request})


@app.get("/promote-store", response_class=HTMLResponse)
async def promote_store(request: Request):
    """Promote Store 페이지"""
    return templates.TemplateResponse("promote_store.html", {"request": request})


@app.get("/user", response_class=HTMLResponse)
async def user_dashboard(request: Request):
    """사용자 대시보드"""
    # 실제로는 로그인 확인 후 사용자 정보 전달
    manager_data = {
        "store_name": "오로라 카페",
        "email": "owner@aurora.com",
        "monthly_generated": 12,
        "monthly_limit": 30,
        "total_views": 8400,
        "ctr": 4.2
    }
    return templates.TemplateResponse("user.html", {
        "request": request,
        "manager": manager_data
    })


@app.get("/manager", response_class=HTMLResponse)
async def manager_dashboard(request: Request):
    """관리자 대시보드"""
    # 실제로는 관리자 권한 확인 후 데이터 전달
    manager_data = {
        "store_name": "오로라 카페",
        "email": "owner@aurora.com",
        "monthly_generated": 12,
        "monthly_limit": 30,
        "total_views": 8400,
        "ctr": 4.2
    }
    return templates.TemplateResponse("manager.html", {
        "request": request,
        "manager": manager_data
    })


@app.post("/generate-ad", response_class=HTMLResponse)  # ← JSONResponse가 아님!
async def generate_ad(
        request: Request,
        file: UploadFile = File(...),
        purpose: str = Form(...),
        mood: str = Form(...),
        client=Depends(get_client),
        use_openai=Depends(get_use_openai)
):
    """광고 생성 (HTML 페이지로 결과 반환)"""
    try:
        image_data = await file.read()

        if use_openai:
            result = process_with_openai(image_data, purpose, mood, client)
        else:
            result = process_with_onnx(image_data, client)
        # ✅ manager.html을 다시 렌더링하되, 결과 포함
        manager_data = {
            "store_name": "오로라 카페",
            "email": "owner@aurora.com",
            "monthly_generated": 12,
            "monthly_limit": 30,
            "total_views": "8.4k",
            "ctr": 4.2
        }

        return templates.TemplateResponse("user.html", {
            "request": request,
            "manager": manager_data,
            "result": result  # ← 결과 전달!
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
