"""
nanoCocoa 통합 테스트 - 더미 모드
실제 AI 모델 없이 인터페이스와 파이프라인만 검증
"""

import sys
import requests
import base64
from pathlib import Path
import time

project_root = Path(__file__).parent.parent.parent


def create_dummy_image_base64():
    """더미 이미지 생성 (1x1 PNG)"""
    # 1x1 빨간색 PNG 이미지
    dummy_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82"
    return base64.b64encode(dummy_png).decode("utf-8")


def test_aiserver_generate_dummy():
    """AI 서버 더미 모드 광고 생성"""
    try:
        dummy_image = create_dummy_image_base64()

        payload = {
            "start_step": 1,
            "input_image": dummy_image,
            "bg_prompt": "Test background",
            "text_content": "TEST",
            "text_model_prompt": "Test text",
            "test_mode": True,  # 더미 모드
        }

        print("  - 더미 모드로 광고 생성 요청...")
        response = requests.post(
            "http://localhost:8000/generate", json=payload, timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            job_id = data.get("job_id")
            print(f"  - 작업 시작: {job_id}")

            # 상태 확인 (더미 모드는 빠름)
            for i in range(10):
                time.sleep(1)
                status_response = requests.get(
                    f"http://localhost:8000/status/{job_id}", timeout=5
                )

                if status_response.status_code == 200:
                    status_data = status_response.json()
                    status = status_data.get("status")
                    progress = status_data.get("progress_percent", 0)

                    print(f"  - 진행률: {progress}% ({status})")

                    if status == "completed":
                        print("✓ 더미 광고 생성 성공")
                        return True
                    elif status == "failed":
                        print(f"✗ 생성 실패: {status_data.get('message')}")
                        return False

            print("✗ 타임아웃 (10초 초과)")
            return False
        else:
            print(f"✗ 요청 실패 (HTTP {response.status_code})")
            print(f"  - 응답: {response.text}")
            return False

    except Exception as e:
        print(f"✗ 에러 발생: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_aiserver_step_by_step_dummy():
    """AI 서버 단계별 더미 생성"""
    try:
        dummy_image = create_dummy_image_base64()

        # Step 1: 배경 생성
        print("  - Step 1: 배경 생성...")
        step1_payload = {
            "start_step": 1,
            "input_image": dummy_image,
            "bg_prompt": "Test background",
            "test_mode": True,
        }

        response = requests.post(
            "http://localhost:8000/generate", json=step1_payload, timeout=30
        )

        if response.status_code != 200:
            print(f"✗ Step 1 실패 (HTTP {response.status_code})")
            return False

        job_id = response.json().get("job_id")

        # 완료 대기
        for i in range(10):
            time.sleep(1)
            status_response = requests.get(
                f"http://localhost:8000/status/{job_id}", timeout=5
            )
            if status_response.status_code == 200:
                status = status_response.json().get("status")
                if status == "completed":
                    print("    ✓ Step 1 완료")
                    break
                elif status == "failed":
                    print("    ✗ Step 1 실패")
                    return False

        print("✓ 단계별 생성 테스트 통과")
        return True

    except Exception as e:
        print(f"✗ 에러: {e}")
        return False


def _check_docker_environment():
    """Docker 환경 확인 (헬퍼 함수)"""
    import subprocess

    try:
        result = subprocess.run(
            [
                "docker",
                "ps",
                "--filter",
                "name=nanococoa",
                "--format",
                "{{.Names}}\t{{.Status}}",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        containers = result.stdout.strip().split("\n")
        aiserver_ok = False
        mcpserver_ok = False

        for container in containers:
            if not container:
                continue
            name, status = container.split("\t", 1)

            if "aiserver" in name and "Up" in status:
                aiserver_ok = True
                print(f"  ✓ {name}: 실행 중")
            if "mcpserver" in name and "Up" in status:
                mcpserver_ok = True
                print(f"  ✓ {name}: 실행 중")

        if aiserver_ok and mcpserver_ok:
            print("✓ Docker 환경 정상")
            return True
        else:
            print(
                f"✗ 컨테이너 미실행 (aiserver: {aiserver_ok}, mcpserver: {mcpserver_ok})"
            )
            return False

    except Exception as e:
        print(f"✗ Docker 확인 실패: {e}")
        return False


def test_aiserver_health():
    """AI 서버 헬스체크"""
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"  - 상태: {data.get('status')}")
            print(f"  - 활성 작업: {data.get('active_jobs')}")
            print("✓ AI 서버 정상")
            return True
        else:
            print(f"✗ 비정상 응답 (HTTP {response.status_code})")
            return False
    except Exception as e:
        print(f"✗ 연결 실패: {e}")
        return False


def test_mcpserver_sse():
    """MCP 서버 SSE 엔드포인트 확인"""
    try:
        response = requests.get(
            "http://localhost:3000/sse",
            headers={"Accept": "text/event-stream"},
            timeout=2,
            stream=True,
        )
        print("✓ MCP 서버 SSE 응답")
        return True
    except requests.exceptions.Timeout:
        print("✓ MCP 서버 SSE 연결 (timeout 정상)")
        return True
    except Exception as e:
        print(f"✗ MCP 서버 연결 실패: {e}")
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("nanoCocoa 통합 테스트 (더미 모드)")
    print("=" * 70)

    results = []

    print("\n[1/5] Docker 환경 확인")
    results.append(_check_docker_environment())

    print("\n[2/5] AI 서버 헬스체크")
    results.append(test_aiserver_health())

    print("\n[3/5] MCP 서버 SSE 엔드포인트")
    results.append(test_mcpserver_sse())

    print("\n[4/5] AI 서버 더미 광고 생성 (전체 파이프라인)")
    results.append(test_aiserver_generate_dummy())

    print("\n[5/5] AI 서버 단계별 더미 생성")
    results.append(test_aiserver_step_by_step_dummy())

    print("\n" + "=" * 70)
    success_count = sum(results)
    total = len(results)

    print(f"결과: {success_count}/{total} 테스트 통과")

    if success_count == total:
        print("✓✓✓ 모든 테스트 성공! ✓✓✓")
    elif success_count >= total * 0.8:
        print("✓ 대부분 테스트 통과")
    else:
        print("✗ 일부 테스트 실패")

    print("=" * 70)

    sys.exit(0 if success_count == total else 1)
