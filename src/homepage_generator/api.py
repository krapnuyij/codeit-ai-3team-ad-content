"""
FastAPI 서버 - Homepage Generator API
Backend에서 고객 데이터를 받아서 홈페이지를 생성합니다.
"""
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager

from main import AdGenGraph
from config.config import StoreConfig


# 요청 데이터 모델
class CustomerData(BaseModel):
    store_name: str
    store_type: str
    budget: int
    period: int
    advertising_goal: str
    target_customer: str
    advertising_media: str
    store_strength: str
    location: str
    phone_number: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 실행되는 생명주기 관리"""
    print("🚀 Homepage Generator API 시작")
    yield
    print("👋 Homepage Generator API 종료")


app = FastAPI(
    title="Homepage Generator API",
    description="고객 데이터를 기반으로 홈페이지를 생성하는 API (Backend에서 데이터 수신)",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """헬스체크 엔드포인트"""
    return {
        "status": "running",
        "service": "Homepage Generator API",
        "version": "1.0.0"
    }


@app.post("/generate")
def generate_homepage(customer_data: CustomerData):
    """
    Backend에서 전달받은 고객 데이터로 홈페이지를 생성합니다.

    Args:
        customer_data: 고객 정보 (store_name, budget, advertising_goal 등)

    Returns:
        생성된 홈페이지 경로 및 상태 정보
    """
    try:
        print(f"\n{'='*60}")
        print(f"🎨 홈페이지 생성 요청")
        print(f"{'='*60}\n")
        print(f"매장명: {customer_data.store_name}")
        print(f"매장 유형: {customer_data.store_type}")
        print(f"광고 목표: {customer_data.advertising_goal}")
        print(f"예산: {customer_data.budget}만원 / 기간: {customer_data.period}일\n")

        # StoreConfig 객체 생성
        store_config = StoreConfig(
            store_name=customer_data.store_name,
            store_type=customer_data.store_type,
            budget=customer_data.budget,
            period=customer_data.period,
            advertising_goal=customer_data.advertising_goal,
            target_customer=customer_data.target_customer,
            advertising_media=customer_data.advertising_media,
            store_strength=customer_data.store_strength,
            location=customer_data.location,
            phone_number=customer_data.phone_number
        )

        # AdGenGraph 인스턴스 생성
        graph = AdGenGraph()

        # 초기 상태 생성
        initial_state = graph.init_state(store_config)

        print(f"✅ 고객 데이터 로드 완료\n")

        # 워크플로우 실행
        final_state = initial_state.copy()
        for step_output in graph.workflow.stream(initial_state):
            if step_output:
                for node_name, node_result in step_output.items():
                    print(f"✓ 노드 완료: {node_name}")
                current_result = next(iter(step_output.values()))
                final_state.update(current_result)

        # 결과 확인
        output_path = final_state.get('output_path', '')
        errors = final_state.get('errors', [])

        if errors:
            print(f"\n⚠️ 경고: 일부 오류가 발생했습니다:")
            for error in errors:
                print(f"  - {error}")

        print(f"\n{'='*60}")
        print(f"✅ 홈페이지 생성 완료!")
        print(f"📦 출력 경로: {output_path}")
        print(f"{'='*60}\n")

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "홈페이지가 성공적으로 생성되었습니다.",
                "store_name": customer_data.store_name,
                "output_path": output_path,
                "errors": errors,
                "logs": final_state.get('logs', [])
            }
        )

    except Exception as e:
        # 예외 처리
        print(f"\n❌ 예상치 못한 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"홈페이지 생성 중 오류가 발생했습니다: {str(e)}"
        )


@app.get("/health")
async def health_check():
    """서버 상태 확인"""
    return {
        "status": "healthy",
        "service": "homepage_generator"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
