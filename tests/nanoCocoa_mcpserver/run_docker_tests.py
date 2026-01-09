"""
전체 통합 테스트 실행 스크립트
Docker 환경에서 nanoCocoa MCP 서버 및 어댑터 테스트
"""

import subprocess
import sys
import time
import requests
from pathlib import Path

# 프로젝트 루트
project_root = Path(__file__).parent.parent


def check_docker_services():
    """Docker 서비스 상태 확인"""
    print("\n" + "=" * 70)
    print("Docker 서비스 상태 확인")
    print("=" * 70)

    services = {
        "aiserver": "http://localhost:8000/health",
        "mcpserver": "http://localhost:3000/health",
    }

    all_healthy = True

    for name, url in services.items():
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"✓ {name}: 정상 (HTTP {response.status_code})")
            else:
                print(f"✗ {name}: 비정상 (HTTP {response.status_code})")
                all_healthy = False
        except Exception as e:
            print(f"✗ {name}: 연결 실패 - {e}")
            all_healthy = False

    return all_healthy


def run_tests(test_file, markers=None):
    """pytest 실행"""
    cmd = [
        "pytest",
        str(test_file),
        "-v",
        "--tb=short",
        "--color=yes",
    ]

    if markers:
        cmd.extend(["-m", markers])

    print(f"\n실행: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=project_root)
    return result.returncode == 0


def main():
    """메인 테스트 실행"""
    print("\n" + "=" * 70)
    print("nanoCocoa MCP Server & Adapter 통합 테스트")
    print("=" * 70)

    # 1. Docker 서비스 확인
    if not check_docker_services():
        print("\n⚠ 일부 서비스가 정상 동작하지 않습니다.")
        print("   다음 명령어로 서비스를 시작하세요:")
        print("   cd src/nanoCocoa_aiserver && sudo docker-compose up -d")
        return 1

    print("\n✓ 모든 Docker 서비스가 정상 동작 중입니다.\n")
    time.sleep(2)

    # 2. Docker 통합 테스트
    print("\n" + "=" * 70)
    print("1. Docker 통합 테스트 실행")
    print("=" * 70)

    test_file = project_root / "tests/nanoCocoa_mcpserver/test_docker_integration.py"
    if not run_tests(test_file):
        print("\n✗ Docker 통합 테스트 실패")
        return 1

    print("\n✓ Docker 통합 테스트 성공")

    # 3. mcpadapter 테스트
    print("\n" + "=" * 70)
    print("2. mcpadapter 테스트 실행")
    print("=" * 70)

    test_file = project_root / "tests/nanoCocoa_mcpserver/test_mcpadapter.py"
    if not run_tests(test_file):
        print("\n✗ mcpadapter 테스트 실패")
        return 1

    print("\n✓ mcpadapter 테스트 성공")

    # 4. 전체 성공
    print("\n" + "=" * 70)
    print("✓ 모든 테스트 성공!")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
