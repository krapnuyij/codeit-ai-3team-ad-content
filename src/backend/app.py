import numpy as np
import cv2
from FastAPI import FastAPI, UploadFile, File, Depends, HTTPException, Request
from FastAPI.responses import JSONResponse
from contextlib import asynccontextmanager
import onnxruntime
from openai import OpenAI
from dotenv import load_dotenv
import os
import base64
from pydantic import BaseModel
from typing import Union

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
            print("OpenAI 클라이언트 초기화 성공")
        except Exception as e:
            print(f"OpenAI 초기화 실패: {e}")

    # ONNX 모델로 fallback
    if not app.state.use_openai:
        print("🔄 OpenAI 실패 → ONNX로 fallback")
        try:
            onnx_path = "model.onnx"
            app.state.client = onnxruntime.InferenceSession(onnx_path)
            print("ONNX 모델 로드 성공")
        except Exception as e:
            print(f"ONNX 로딩 실패: {e}")
            raise RuntimeError("모든 클라이언트 초기화 실패") from e

    yield

    # 앱 종료 시 cleanup
    print("🛑 앱 종료")


# FastAPI 앱 생성
app = FastAPI(title="AI Image Prompt Generator", lifespan=lifespan)


# 유틸리티 함수
def to_base64(image_bytes: bytes) -> str:
    """이미지 바이트를 base64 문자열로 변환"""
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def process_with_openai(image_data: bytes, client: OpenAI) -> AdPrompt:
    """OpenAI Responses API를 사용하여 프롬프트 생성"""
    try:
        encoded_image = to_base64(image_data)
        response = client.chat.completions.create()
        # Responses API의 parse 메서드 사용
        response = client.responses.parse(
            model="gpt-5-mini",  # 또는 "gpt-4o-2024-08-06"
            input=[
                {
                    "role": "system",
                    "content": "당신은 광고 이미지 생성을 위한 프롬프트 전문가입니다.",
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "이 이미지를 참고해서 광고용 이미지 생성을 위한 프롬프트를 만들어줘.",
                        },
                        {"type": "image_url", "image_url": {"url": encoded_image}},
                    ],
                },
            ],
            text_format=AdPrompt,  # Pydantic 모델로 자동 파싱
        )

        # 파싱된 결과 반환
        return response.output_parsed

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"OpenAI Responses API 호출 실패: {str(e)}"
        )


def process_with_onnx(image_data: bytes, ort_session) -> AdPrompt:
    """ONNX 모델을 사용하여 프롬프트 생성"""
    try:
        # 이미지 디코딩
        img = cv2.imdecode(np.frombuffer(image_data, np.uint8), cv2.IMREAD_COLOR)

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
            positive_prompt=positive_prompt, negative_prompt=negative_prompt
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ONNX 모델 처리 실패: {str(e)}")


# API 엔드포인트
@app.get("/", response_class=JSONResponse)
async def root():
    """루트 엔드포인트"""
    return {
        "message": "AI Image Prompt Generator API",
        "endpoints": {"generate_prompt": "/generate-prompt (POST)"},
    }


@app.post("/generate-prompt", response_model=AdPrompt)
async def generate_image_prompt(
    file: UploadFile = File(...),
    client: Union[OpenAI, onnxruntime.InferenceSession] = Depends(get_client),
    use_openai: bool = Depends(get_use_openai),
):
    """
    업로드된 이미지로부터 광고용 이미지 생성 프롬프트 생성

    Args:
        file: 업로드된 이미지 파일
        client: OpenAI 또는 ONNX 클라이언트 (자동 주입)
        use_openai: OpenAI 사용 여부 (자동 주입)

    Returns:
        AdPrompt: positive_prompt와 negative_prompt 포함
    """
    try:
        # 이미지 데이터 읽기
        image_data = await file.read()

        if not image_data:
            raise HTTPException(status_code=400, detail="빈 파일입니다")

        # OpenAI 또는 ONNX로 처리
        if use_openai:
            print("🤖 OpenAI Responses API로 프롬프트 생성 중...")
            result = process_with_openai(image_data, client)
        else:
            print("🔧 ONNX 모델로 프롬프트 생성 중...")
            result = process_with_onnx(image_data, client)

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"이미지 처리 중 오류 발생: {str(e)}"
        )


@app.get("/health")
async def health_check(request: Request):
    """헬스 체크 엔드포인트"""
    return {
        "status": "healthy",
        "using_openai": request.app.state.use_openai,
        "client_type": "OpenAI" if request.app.state.use_openai else "ONNX",
    }


# 개발 서버 실행 (옵션)
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
