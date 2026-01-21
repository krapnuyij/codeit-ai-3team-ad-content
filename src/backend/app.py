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
import httpx
import asyncio

# 데이터베이스 모듈 import
from customer_db import init_db, save_customer, get_customer_by_id

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
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def process_with_openai(
    image_data: bytes, purpose: str, mood: str, client: OpenAI
) -> AdPrompt:
    """OpenAI Responses API를 사용하여 프롬프트 생성"""
    try:
        encoded_image = to_base64(image_data)
        # Responses API의 parse 메서드 사용
        response = client.responses.parse(
            model="gpt-5-mini",
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": f"이 이미지를 참고해서 '{purpose}' 목적의 '{mood}' 분위기 광고용 이미지 생성을 위한 프롬프트를 만들어줘.",
                        },
                        {
                            "type": "product_image",
                            "image_url": encoded_image,  # ✅ 직접 문자열로 전달
                        },
                    ],
                }
            ],
            text_format=AdPrompt,  # Pydantic 모델로 자동 파싱
        )
        # ✅ JSON 문자열 → 딕셔너리 → AdPrompt 객체
        text = response.output[1].content[0].text
        parsed = json.loads(text)

        return AdPrompt(
            positive_prompt=parsed["positive_prompt"],
            negative_prompt=parsed["negative_prompt"],
        )

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


async def process_with_aiserver(
    image_data: bytes,
    ad_prompt: AdPrompt,
    text_content: str,
    text_style: str,
    text_position: str,
) -> str:
    """AI 서버에 이미지 생성 요청 및 결과 폴링"""
    try:
        encoded_image = to_base64(image_data)

        # AI 서버 URL (환경변수 또는 기본값)
        ai_server_url = os.getenv("NANOCOCOA_URL", "http://nanocacao_aiserver:8000")

        # 텍스트 스타일을 영문 프롬프트로 변환
        text_style_prompts = {
            "골드 풍선": "3D render of Gold foil balloon text, inflated, shiny metallic texture, floating in air, cinematic lighting, sharp details, isolated on black background",
            "네온 글로우": "3D render of neon glowing text, bright luminous effect, cyberpunk style, electric glow, vibrant colors, dramatic lighting, isolated on black background",
            "우드 텍스처": "3D render of wooden carved text, natural wood grain texture, rustic style, carved depth, realistic wood material, warm lighting, isolated on black background",
            "크롬 메탈": "3D render of chrome metallic text, highly reflective surface, polished metal, mirror effect, studio lighting, sleek modern style, isolated on black background",
            "페이퍼 컷": "3D render of paper cut text, layered paper style, subtle shadows, clean edges, minimalist design, soft lighting, isolated on white background",
        }

        text_prompt = text_style_prompts.get(
            text_style, text_style_prompts["골드 풍선"]
        )

        # 한국어 텍스트 감지 및 폰트 선택
        font_name = None
        if any("\uac00" <= char <= "\ud7a3" for char in text_content):
            # 한국어가 포함된 경우
            font_name = "NanumGothic/NanumGothicBold.ttf"

        # 1. 생성 요청 (전체 파이프라인: Step 1 → 2 → 3)
        payload = {
            "start_step": 1,
            "product_image": encoded_image,
            "text_content": text_content,  # ✅ 활성화
            "bg_prompt": ad_prompt.positive_prompt,
            "bg_negative_prompt": ad_prompt.negative_prompt,
            "text_prompt": text_prompt,  # ✅ 텍스트 스타일 프롬프트
            "text_position": text_position,  # ✅ 텍스트 위치
            "auto_unload": True,
        }

        # 한국어 폰트 추가
        if font_name:
            payload["font_name"] = font_name

        async with httpx.AsyncClient() as client:
            # 타임아웃 넉넉하게 설정
            resp = await client.post(
                f"{ai_server_url}/generate", json=payload, timeout=300
            )

            if resp.status_code != 200:
                print(f"❌ AI 서버 요청 실패: {resp.text}")
                return None

            job_data = resp.json()
            job_id = job_data.get("job_id")

            if not job_id:
                return None

            print(f"✅ 작업 시작: {job_id}")

            # 2. 결과 폴링 (최대 30분 대기)
            max_retries = 1800  # 30분 = 1800초
            for i in range(max_retries):
                await asyncio.sleep(5)

                status_resp = await client.get(
                    f"{ai_server_url}/status/{job_id}", timeout=10.0
                )

                if status_resp.status_code != 200:
                    continue

                status_data = status_resp.json()
                status = status_data.get("status")
                progress = status_data.get("progress", 0)

                # 진행 상황 출력 (10초마다)
                if i % 10 == 0:
                    print(f"⏳ 진행 중... {progress}% (경과: {i}초)")

                if status == "completed":
                    print(f"✅ 생성 완료! (총 {i}초 소요)")
                    # 최종 결과 이미지 반환
                    return status_data.get("final_result")

                if status == "failed":
                    error_msg = status_data.get("message", "알 수 없는 오류")
                    print(f"❌ 작업 실패: {error_msg}")
                    return None

            print("⚠️ 작업 시간 초과 (30분)")
            return None

    except Exception as e:
        print(f"⚠️ AI 서버 통신 중 오류: {e}")
        return None


# Lifespan 이벤트
@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 실행되는 로직"""
    print("🚀 앱 시작")

    # 데이터베이스 초기화
    await init_db()

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


app = FastAPI(title="AI Image Prompt Generator", lifespan=lifespan)

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
        "ctr": 4.2,
    }
    return templates.TemplateResponse(
        "user.html", {"request": request, "manager": manager_data}
    )


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
        "ctr": 4.2,
    }
    return templates.TemplateResponse(
        "manager.html", {"request": request, "manager": manager_data}
    )


@app.post("/generate-ad", response_class=HTMLResponse)  # ← JSONResponse가 아님!
async def generate_ad(
    request: Request,
    file: UploadFile = File(...),
    text_content: str = Form(...),
    purpose: str = Form(...),
    mood: str = Form(...),
    text_style: str = Form(...),
    text_position: str = Form("center"),
    client=Depends(get_client),
    use_openai=Depends(get_use_openai),
):
    """광고 생성 (HTML 페이지로 결과 반환)"""
    try:
        image_data = await file.read()

        if use_openai:
            # 1. 프롬프트 생성
            result = process_with_openai(image_data, purpose, mood, client)

            # 2. 이미지 생성 (AI Server)
            generated_image_b64 = await process_with_aiserver(
                image_data, result, text_content, text_style, text_position
            )

            image_url = None
            if generated_image_b64:
                # base64 헤더가 없는 경우 추가
                if not generated_image_b64.startswith("data:image"):
                    image_url = f"data:image/png;base64,{generated_image_b64}"
                else:
                    image_url = generated_image_b64
        else:
            result = process_with_onnx(image_data, client)
            # ONNX 모드일 때는 이미지 생성 안함 (또는 추후 구현)
            image_url = None

        return templates.TemplateResponse(
            "user.html",
            {
                "request": request,
                "result": result,  # 프롬프트 결과
                "image_url": image_url,  # 생성된 이미지
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/save-customer-data", response_class=HTMLResponse)
async def save_customer_data(
    request: Request,
    store_name: str = Form(...),
    store_type: str = Form(...),
    budget: str = Form(...),
    period: str = Form(...),
    advertising_goal: str = Form(...),
    target_customer: str = Form(...),
    advertising_media: str = Form(...),
    store_strength: str = Form(...),
    contact_name: str = Form(...),
    company_name: str = Form(None),  # 선택 사항이므로 기본값 None
    email: str = Form(...),
    phone: str = Form(...),
    agree: str = Form(...),
):
    """홈페이지 생성 요청 처리 및 DB 저장"""
    try:
        # 고객 데이터 딕셔너리 생성
        customer_data = {
            "store_name": store_name,
            "store_type": store_type,
            "budget": budget,
            "period": period,
            "advertising_goal": advertising_goal,
            "target_customer": target_customer,
            "advertising_media": advertising_media,
            "store_strength": store_strength,
            "contact_name": contact_name,
            "company_name": (
                company_name if company_name else store_name
            ),  # 비어있으면 매장명 사용
            "email": email,
            "phone": phone,
            "agree": agree,
        }

        # 데이터베이스에 저장
        saved_customer = await save_customer(customer_data)

        result = f"✅ 데이터를 안전하게 저장하였습니다. (고객 ID: {saved_customer.id})"

        return templates.TemplateResponse(
            "promote_store.html",
            {"request": request, "result": result, "customer_id": saved_customer.id},
        )

    except Exception as e:
        print(f"❌ 에러 발생: {e}")
        result = "데이터 저장 중 오류가 발생했습니다. 다시 시도해주세요."
        return templates.TemplateResponse(
            "promote_store.html",
            {"request": request, "result": result, "error": str(e)},
        )


@app.post("/generate-homepage/{customer_id}", response_class=HTMLResponse)
async def generate_homepage(request: Request, customer_id: int):
    """저장된 고객 데이터로 홈페이지 생성 요청"""
    try:
        # DB에서 고객 데이터 조회
        customer = await get_customer_by_id(customer_id)

        # homepage_generator에 전달할 데이터 구성
        customer_data = {
            "store_name": customer.store_name,
            "store_type": customer.store_type,
            "budget": int(customer.budget),
            "period": int(customer.period),
            "advertising_goal": customer.advertising_goal,
            "target_customer": customer.target_customer,
            "advertising_media": customer.advertising_media,
            "store_strength": customer.store_strength,
            "location": customer.company_name or customer.store_name,
            "phone_number": customer.phone,
        }

        # homepage_generator 컨테이너에 데이터 전송
        homepage_generator_url = os.getenv(
            "HOMEPAGE_GENERATOR_URL", "http://homepage_generator:8891"
        )

        async with httpx.AsyncClient(timeout=600.0) as client:
            response = await client.post(
                f"{homepage_generator_url}/generate", json=customer_data
            )

            if response.status_code == 200:
                generation_result = response.json()
                output_path = generation_result.get("output_path", "알 수 없음")
                result = f"""
✅ 홈페이지 생성 완료!<br>
<br>
고객 ID: {customer_id}<br>
매장명: {customer.store_name}<br>
생성 경로: {output_path}<br>
홈페이지 경로 : <a href="http://34.44.205.198:8893/sites/{output_path.split('/')[-1]}/index.html" target="_blank">http://34.44.205.198:8893/sites/{output_path.split('/')[-1]}/index.html</a>
"""
            else:
                result = f"❌ 홈페이지 생성 중 오류가 발생했습니다. (상태 코드: {response.status_code})"

        return templates.TemplateResponse(
            "promote_store.html", {"request": request, "result": result}
        )

    except ValueError as e:
        # 고객 데이터를 찾을 수 없는 경우
        result = f"❌ {str(e)}"
        return templates.TemplateResponse(
            "promote_store.html", {"request": request, "result": result}
        )
    except httpx.ConnectError:
        result = f"❌ homepage_generator 서버에 연결할 수 없습니다."
        return templates.TemplateResponse(
            "promote_store.html", {"request": request, "result": result}
        )
    except httpx.TimeoutException:
        result = f"⚠️ 홈페이지 생성 시간이 초과되었습니다. (5분 이상 소요)"
        return templates.TemplateResponse(
            "promote_store.html", {"request": request, "result": result}
        )
    except Exception as e:
        print(f"❌ 홈페이지 생성 오류: {e}")
        result = f"❌ 홈페이지 생성 중 오류가 발생했습니다: {str(e)}"
        return templates.TemplateResponse(
            "promote_store.html", {"request": request, "result": result}
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8890)
