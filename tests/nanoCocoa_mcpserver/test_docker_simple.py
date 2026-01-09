"""
nanoCocoa MCP Server 간단한 Docker 테스트
실제 Docker 환경에서 기본 기능만 검증
"""

import pytest
import sys
import requests
from pathlib import Path

project_root = Path(__file__).parent.parent.parent


def test_docker_containers(require_docker_server):
    """Docker 컨테이너 상태 확인"""
    import subprocess

    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        containers = result.stdout.strip().split("\n")
        aiserver_ok = False
        mcpserver_ok = False

        print("Docker 컨테이너 상태:")
        for container in containers:
            if not container:
                continue
            name, status = container.split("\t", 1)
            print(f"  - {name}: {status}")

            if "nanococoa-aiserver" in name and "Up" in status:
                aiserver_ok = True
            if "nanococoa-mcpserver" in name and "Up" in status:
                mcpserver_ok = True

        assert (
            aiserver_ok and mcpserver_ok
        ), f"일부 컨테이너 미실행 (aiserver: {aiserver_ok}, mcpserver: {mcpserver_ok})"
        print("✓ 모든 컨테이너 실행 중")

    except Exception as e:
        pytest.fail(f"Docker 상태 확인 실패: {e}")


def test_aiserver_health(require_docker_server):
    """AI 서버 헬스체크"""
    response = requests.get("http://localhost:8000/health", timeout=5)
    assert response.status_code == 200, f"AI 서버 비정상 (HTTP {response.status_code})"

    data = response.json()
    print(f"✓ AI 서버 정상 동작")
    print(f"  - 상태: {data.get('status')}")
    print(f"  - GPU: {len(data.get('system_metrics', {}).get('gpu_info', []))}개")


def test_mcpserver_running(require_docker_server):
    """MCP 서버 실행 확인 (SSE 엔드포인트)"""


def test_mcpserver_running(require_docker_server):
    """MCP 서버 실행 확인 (SSE 엔드포인트)"""
    try:
        response = requests.get(
            "http://localhost:3000/sse",
            headers={"Accept": "text/event-stream"},
            timeout=2,
            stream=True,
        )
        # 응답이 시작되면 성공
        print("✓ MCP 서버 SSE 엔드포인트 응답")
        print(f"  - 상태: HTTP {response.status_code}")
    except requests.exceptions.Timeout:
        # SSE는 연결을 유지하므로 timeout은 정상
        print("✓ MCP 서버 SSE 연결 가능 (timeout은 정상)")


def test_aiserver_fonts(require_docker_server):
    """AI 서버 폰트 목록 조회"""
    response = requests.get("http://localhost:8000/fonts", timeout=5)
    assert (
        response.status_code == 200
    ), f"폰트 목록 조회 실패 (HTTP {response.status_code})"

    fonts = response.json()
    font_count = len(fonts) if isinstance(fonts, list) else 0
    print(f"✓ 폰트 목록 조회 성공: {font_count}개")
    if fonts and font_count > 0:
        print(f"  - 예시: {fonts[0]}")
