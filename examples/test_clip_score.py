"""
CLIP Score API 테스트 예제 (OpenAI CLIP + KoCLIP)
"""

import base64
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import requests
from PIL import Image


def create_test_image() -> str:
    """
    테스트용 간단한 이미지 생성 및 Base64 인코딩

    Returns:
        str: Base64 인코딩된 이미지 문자열
    """
    # 100x100 빨간색 이미지 생성
    from io import BytesIO

    img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    img_base64 = base64.b64encode(buffer.read()).decode("utf-8")
    return img_base64


def test_clip_score_api():
    """CLIP Score API 엔드포인트 테스트"""

    # API 서버 URL (로컬 테스트)
    base_url = "http://localhost:8000"

    # 1. Health Check
    print("=" * 60)
    print("1. CLIP Service Health Check")
    print("=" * 60)

    response = requests.get(f"{base_url}/clip-score/health")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    print()

    # 2. CLIP Score 계산 (테스트 이미지)
    print("=" * 60)
    print("2. CLIP Score Calculation (Test Image)")
    print("=" * 60)

    test_image_base64 = create_test_image()
    test_prompt = "A red square"

    payload = {"image_base64": test_image_base64, "prompt": test_prompt}

    response = requests.post(f"{base_url}/clip-score", json=payload)
    print(f"Status Code: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print(f"CLIP Score: {result['clip_score']}")
        print(f"Prompt: {result['prompt']}")
        print(f"Interpretation: {result['interpretation']}")
    else:
        print(f"Error: {response.json()}")
    print()

    # 3. CLIP Score 계산 (한글 프롬프트 - KoCLIP)
    print("=" * 60)
    print("3. CLIP Score Calculation (Korean Prompt - KoCLIP)")
    print("=" * 60)

    image_base64 = test_image_base64
    prompt_korean = "사과가 그려져 있고 가격과 판매 장소가 적혀 있는 광고 포스터"

    payload = {
        "image_base64": image_base64,
        "prompt": prompt_korean,
        "model_type": "koclip",
    }

    response = requests.post(f"{base_url}/clip-score", json=payload)
    print(f"Status Code: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print(f"CLIP Score: {result['clip_score']}")
        print(f"Model: {result['model_type']}")
        print(f"Prompt: {result['prompt']}")
        print(f"Interpretation: {result['interpretation']}")
    else:
        print(f"Error: {response.json()}")
    print()

    # 4. CLIP Score 계산 (영문 프롬프트 - OpenAI CLIP)
    print("=" * 60)
    print("4. CLIP Score Calculation (English Prompt - OpenAI CLIP)")
    print("=" * 60)

    prompt_english = (
        "An advertisement of a fresh red apple with a price tag and store location"
    )

    payload = {
        "image_base64": image_base64,
        "prompt": prompt_english,
        "model_type": "openai",
    }

    response = requests.post(f"{base_url}/clip-score", json=payload)
    print(f"Status Code: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print(f"CLIP Score: {result['clip_score']}")
        print(f"Model: {result['model_type']}")
        print(f"Prompt: {result['prompt']}")
        print(f"Interpretation: {result['interpretation']}")
    else:
        print(f"Error: {response.json()}")
    print()

    # 5. 에러 케이스 테스트 (잘못된 Base64)
    print("=" * 60)
    print("5. Error Case (Invalid Base64)")
    print("=" * 60)

    invalid_payload = {"image_base64": "invalid_base64_string", "prompt": "test"}

    response = requests.post(f"{base_url}/clip-score", json=invalid_payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    print()


if __name__ == "__main__":
    try:
        test_clip_score_api()
    except requests.exceptions.ConnectionError:
        print("❌ API 서버가 실행되지 않았습니다.")
        print("다음 명령어로 서버를 시작하세요:")
        print("  cd src/nanoCocoa_aiserver")
        print("  uvicorn main:app --reload")
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {e}")
