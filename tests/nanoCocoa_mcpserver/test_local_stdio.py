"""
nanoCocoa MCP Server 로컬 stdio 모드 테스트
Docker 없이 로컬 환경에서 직접 테스트
"""

import subprocess
import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def test_mcp_server_stdio():
    """stdio 모드로 MCP 서버와 통신 테스트"""

    # MCP 서버 프로세스 시작
    server_path = project_root / "src" / "nanoCocoa_mcpserver" / "server.py"

    # initialize 요청
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"},
        },
    }

    try:
        # MCP 서버 실행 (stdio 모드)
        proc = subprocess.Popen(
            ["python", "-m", "nanoCocoa_mcpserver.server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=project_root / "src",
        )

        # 요청 전송
        request_str = json.dumps(init_request) + "\n"
        proc.stdin.write(request_str)
        proc.stdin.flush()

        # 응답 대기 (timeout 5초)
        import time

        time.sleep(2)

        # 프로세스 종료
        proc.terminate()
        stdout, stderr = proc.communicate(timeout=3)

        print("=== STDOUT ===")
        print(stdout)
        print("\n=== STDERR ===")
        print(stderr)

        # 응답 확인
        if "serverInfo" in stdout or "result" in stdout:
            print("\n✓ MCP 서버 stdio 통신 성공")
            return True
        else:
            print("\n✗ MCP 서버 응답 없음")
            return False

    except Exception as e:
        print(f"\n✗ 에러: {e}")
        return False


def test_server_import():
    """서버 모듈 import 테스트"""
    try:
        sys.path.insert(0, str(project_root / "src"))
        from nanoCocoa_mcpserver import server

        print("✓ 서버 모듈 import 성공")
        print(f"  - MCP 서버 이름: {server.MCP_SERVER_NAME}")
        print(f"  - MCP 서버 버전: {server.MCP_SERVER_VERSION}")
        return True
    except Exception as e:
        print(f"✗ 서버 모듈 import 실패: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_aiserver_connection():
    """AI 서버 연결 테스트"""
    import requests

    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✓ AI 서버 연결 성공")
            print(f"  - 상태: {response.json()}")
            return True
        else:
            print(f"✗ AI 서버 연결 실패 (HTTP {response.status_code})")
            return False
    except Exception as e:
        print(f"✗ AI 서버 연결 실패: {e}")
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("nanoCocoa MCP Server 로컬 테스트")
    print("=" * 70)

    results = []

    print("\n[1/3] 서버 모듈 import 테스트")
    results.append(test_server_import())

    print("\n[2/3] AI 서버 연결 테스트")
    results.append(test_aiserver_connection())

    print("\n[3/3] MCP stdio 통신 테스트")
    results.append(test_mcp_server_stdio())

    print("\n" + "=" * 70)
    print(f"결과: {sum(results)}/{len(results)} 성공")
    print("=" * 70)

    sys.exit(0 if all(results) else 1)
