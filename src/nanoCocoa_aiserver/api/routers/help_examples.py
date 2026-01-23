"""
help_examples.py
실전 사용 예시 엔드포인트
"""

from fastapi import APIRouter

router = APIRouter()


@router.get(
    "/help/examples",
    summary="실전 사용 예시 (Usage Examples)",
    response_description="다양한 시나리오별 API 사용 예시",
)
async def get_examples():
    """
    실제 사용 시나리오별 API 호출 예시를 제공합니다.

    각 예시는 cURL, Python, JavaScript 코드와 함께 제공됩니다.
    """
    return {
        "examples": {
            "example1_basic_generation": {
                "scenario": "화장품 광고 이미지 생성",
                "description": "화장품 제품 이미지를 받아서 럭셔리한 배경에 'Premium Beauty' 텍스트를 추가",
                "workflow": [
                    {
                        "step": "1. 서버 상태 확인",
                        "curl": 'curl -X GET "http://localhost:8000/health"',
                        "python": 'response = requests.get("http://localhost:8000/health")',
                        "response": {"status": "healthy", "active_jobs": 0},
                    },
                    {
                        "step": "2. 폰트 목록 조회",
                        "curl": 'curl -X GET "http://localhost:8000/fonts"',
                        "python": 'fonts = requests.get("http://localhost:8000/fonts").json()',
                        "response": {
                            "fonts": [
                                "NanumGothic/NanumGothic.ttf",
                                "NanumSquare/NanumSquareB.ttf",
                            ]
                        },
                    },
                    {
                        "step": "3. 생성 작업 시작",
                        "curl": """curl -X POST "http://localhost:8000/generate" \\
  -H "Content-Type: application/json" \\
  -d '{
    "product_image": "<base64_cosmetic_product>",
    "bg_prompt": "luxury marble bathroom with gold accents and soft lighting",
    "text_content": "Premium Beauty",
    "text_prompt": "elegant gold metallic text with subtle glow",
    "font_name": "NanumSquare/NanumSquareB.ttf"
  }' """,
                        "python": """import requests
import base64

with open("cosmetic_product.png", "rb") as f:
    image_b64 = base64.b64encode(f.read()).decode()

response = requests.post("http://localhost:8000/generate", json={
    "product_image": image_b64,
    "bg_prompt": "luxury marble bathroom with gold accents and soft lighting",
    "text_content": "Premium Beauty",
    "text_prompt": "elegant gold metallic text with subtle glow",
    "font_name": "NanumSquare/NanumSquareB.ttf"
})

job_id = response.json()["job_id"]""",
                        "response": {"job_id": "abc-123-def", "status": "started"},
                    },
                    {
                        "step": "4. 진행 상태 폴링",
                        "python": """import time

while True:
    status = requests.get(f"http://localhost:8000/status/{job_id}").json()
    print(f"Progress: {status['progress_percent']}% - {status['message']}")

    if status['status'] in ('completed', 'failed', 'stopped'):
        break

    time.sleep(3)

if status['status'] == 'completed':
    final_image_b64 = status['final_result']
    # Base64 디코딩 및 저장
    with open("final_ad.png", "wb") as f:
        f.write(base64.b64decode(final_image_b64))""",
                    },
                ],
            },
            "example2_text_retry": {
                "scenario": "텍스트 스타일 변경",
                "description": "배경은 그대로 두고 텍스트 스타일만 변경",
                "python": """# 1. 이전 작업의 배경 이미지 가져오기
previous_status = requests.get(f"http://localhost:8000/status/{previous_job_id}").json()
step1_result = previous_status['step1_result']

# 2. 새로운 텍스트 스타일로 재생성
new_response = requests.post("http://localhost:8000/generate", json={
    "start_step": 2,
    "step1_image": step1_result,
    "text_content": "Premium Beauty",
    "text_prompt": "chrome reflective text with rainbow gradient",
    "font_name": "NanumGothic/NanumGothic.ttf"
})

new_job_id = new_response.json()["job_id"]""",
            },
            "example3_batch_processing": {
                "scenario": "여러 텍스트 버전 생성",
                "description": "같은 배경에 다른 텍스트를 여러 개 생성 (순차 처리)",
                "python": """import time

base_job = requests.post("http://localhost:8000/generate", json={
    "product_image": product_image_b64,
    "bg_prompt": "modern office workspace",
    "text_content": ""  # 배경만 생성
}).json()

# 배경 생성 완료 대기
while True:
    status = requests.get(f"http://localhost:8000/status/{base_job['job_id']}").json()
    if status['status'] == 'completed':
        break
    time.sleep(3)

background = status['step1_result']

# 여러 텍스트 버전 생성
texts = [
    {"text": "Sale 50%", "style": "bold red text with shadow"},
    {"text": "New Arrival", "style": "elegant gold text"},
    {"text": "Limited Edition", "style": "silver metallic text"}
]

results = []
for text_config in texts:
    # 서버가 사용 가능할 때까지 대기
    while True:
        health = requests.get("http://localhost:8000/health").json()
        if health['status'] == 'healthy':
            break
        time.sleep(5)

    # 텍스트 생성 요청
    job = requests.post("http://localhost:8000/generate", json={
        "start_step": 2,
        "step1_image": background,
        "text_content": text_config["text"],
        "text_prompt": text_config["style"]
    }).json()

    # 완료 대기
    while True:
        status = requests.get(f"http://localhost:8000/status/{job['job_id']}").json()
        if status['status'] == 'completed':
            results.append(status['final_result'])
            break
        time.sleep(3)""",
            },
            "example4_error_handling": {
                "scenario": "에러 처리 및 재시도",
                "python": '''import time

def generate_with_retry(request_data, max_retries=3):
    """에러 처리 및 재시도 로직"""
    for attempt in range(max_retries):
        try:
            # 서버 상태 확인
            health = requests.get("http://localhost:8000/health").json()

            if health['status'] == 'busy':
                wait_time = health.get('active_jobs', 1) * 120  # 예상 대기 시간
                print(f"Server busy. Waiting {wait_time}s...")
                time.sleep(wait_time)
                continue

            # 생성 요청
            response = requests.post("http://localhost:8000/generate", json=request_data)

            if response.status_code == 503:
                retry_after = int(response.headers.get('Retry-After', 30))
                print(f"503 Error. Retry after {retry_after}s")
                time.sleep(retry_after)
                continue

            response.raise_for_status()
            job_id = response.json()["job_id"]

            # 상태 폴링
            while True:
                status = requests.get(f"http://localhost:8000/status/{job_id}").json()

                if status['status'] == 'completed':
                    return status['final_result']

                elif status['status'] == 'failed':
                    print(f"Job failed: {status['message']}")
                    if attempt < max_retries - 1:
                        print(f"Retrying... (attempt {attempt + 2}/{max_retries})")
                        break
                    else:
                        raise Exception(f"Job failed after {max_retries} attempts")

                time.sleep(3)

        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            if attempt < max_retries - 1:
                time.sleep(10)
            else:
                raise

    raise Exception("Max retries exceeded")

# 사용 예시
try:
    final_image = generate_with_retry({
        "product_image": product_b64,
        "bg_prompt": "luxury background",
        "text_content": "Special Offer"
    })
    print("Generation successful!")
except Exception as e:
    print(f"Generation failed: {e}")''',
            },
        },
        "llm_integration_guide": {
            "description": "LLM이 이 API를 사용할 때 권장하는 패턴",
            "pattern": [
                "1. 사용자 요청 분석: 배경, 텍스트, 스타일 요구사항 파악",
                "2. 영문 프롬프트 생성: 한글 입력 시 영문으로 번역",
                "3. GET /health로 서버 가용성 확인",
                "4. 필요시 GET /fonts로 적절한 폰트 선택",
                "5. POST /generate로 작업 시작",
                "6. GET /status/{job_id}를 폴링하여 진행 상황 사용자에게 업데이트",
                "7. 완료 시 final_result 제공",
                "8. 사용자가 수정 요청하면 적절한 start_step으로 재시도",
                "9. DELETE /jobs/{job_id}로 완료된 작업 정리",
            ],
            "best_practices": [
                "프롬프트는 구체적이고 명확하게 작성",
                "progress_percent와 message를 사용자에게 실시간 전달",
                "에러 발생 시 message 필드를 확인하여 원인 파악",
                "step1_result, step2_result를 저장하여 재사용",
                "사용자가 만족할 때까지 파라미터 조정하여 재시도",
            ],
        },
    }
