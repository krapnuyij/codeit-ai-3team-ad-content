#!/usr/bin/env python3
"""
nanoCocoa MCP 서버 테스트 실행 스크립트

테스트 종류:
1. 단위 테스트 (Unit Tests): Mock 사용, 서버 불필요
2. 통합 테스트 (Integration Tests): 실제 AI 서버 필요

실행 방법:
    # 단위 테스트만 실행
    python tests/nanoCocoa_mcpserver/run_tests.py --unit

    # 통합 테스트만 실행 (AI 서버 필요)
    python tests/nanoCocoa_mcpserver/run_tests.py --integration

    # 모든 테스트 실행
    python tests/nanoCocoa_mcpserver/run_tests.py --all
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    print("requests 패키지가 필요합니다: pip install requests")
    sys.exit(1)


class Colors:
    """터미널 색상 코드"""

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_header(text: str):
    """헤더 출력"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 70}")
    print(f"{text}")
    print(f"{'=' * 70}{Colors.RESET}\n")


def print_success(text: str):
    """성공 메시지 출력"""
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")


def print_error(text: str):
    """에러 메시지 출력"""
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")


def print_warning(text: str):
    """경고 메시지 출력"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")


def check_aiserver() -> bool:
    """AI 서버 상태 확인"""
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            status = data.get("status", "unknown")
            print_success(f"AI 서버 정상 (상태: {status})")
            return True
        else:
            print_error(f"AI 서버 비정상 (HTTP {response.status_code})")
            return False
    except Exception as e:
        print_error(f"AI 서버 연결 실패: {e}")
        return False


def check_mcpserver() -> bool:
    """MCP 서버 상태 확인"""
    try:
        response = requests.get("http://localhost:3000/health", timeout=5)
        if response.status_code == 200:
            print_success("MCP 서버 정상")
            return True
        else:
            print_error(f"MCP 서버 비정상 (HTTP {response.status_code})")
            return False
    except Exception as e:
        print_error(f"MCP 서버 연결 실패: {e}")
        return False


def run_pytest(
    test_path: str, markers: Optional[str] = None, verbose: bool = True
) -> bool:
    """pytest 실행"""
    project_root = Path(__file__).parent.parent.parent

    cmd = [
        "pytest",
        test_path,
        "--tb=short",
        "--color=yes",
    ]

    if verbose:
        cmd.append("-v")

    if markers:
        cmd.extend(["-m", markers])

    print(f"\n실행: {' '.join(cmd)}\n")
    result = subprocess.run(cmd, cwd=project_root)
    return result.returncode == 0


def run_unit_tests() -> bool:
    """단위 테스트 실행"""
    print_header("단위 테스트 (Unit Tests)")

    tests = [
        ("이미지 유틸리티", "tests/nanoCocoa_mcpserver/test_image_utils.py"),
        ("API 클라이언트", "tests/nanoCocoa_mcpserver/test_api_client.py"),
        ("MCP 서버", "tests/nanoCocoa_mcpserver/test_server.py"),
    ]

    results = []
    for name, path in tests:
        print(f"\n{Colors.BOLD}테스트: {name}{Colors.RESET}")
        success = run_pytest(path)
        results.append((name, success))

        if success:
            print_success(f"{name} 테스트 성공")
        else:
            print_error(f"{name} 테스트 실패")

    # 결과 요약
    print_header("단위 테스트 결과 요약")
    passed = sum(1 for _, success in results if success)
    total = len(results)

    for name, success in results:
        status = "✓ 성공" if success else "✗ 실패"
        color = Colors.GREEN if success else Colors.RED
        print(f"{color}{status}: {name}{Colors.RESET}")

    print(f"\n총 {total}개 테스트 중 {passed}개 성공")

    return all(success for _, success in results)


def run_integration_tests() -> bool:
    """통합 테스트 실행"""
    print_header("통합 테스트 (Integration Tests)")

    # AI 서버 확인
    print("AI 서버 상태 확인...")
    if not check_aiserver():
        print_warning("AI 서버가 실행 중이지 않습니다.")
        print_warning("통합 테스트를 실행하려면 AI 서버를 먼저 시작하세요:")
        print_warning("  cd src/nanoCocoa_aiserver")
        print_warning(
            "  python -m uvicorn nanoCocoa_aiserver.main:app --host 0.0.0.0 --port 8000"
        )
        return False

    print("\n통합 테스트 실행 (AI 서버 연동)...")
    success = run_pytest(
        "tests/nanoCocoa_mcpserver/test_integration.py", markers="integration"
    )

    if success:
        print_success("통합 테스트 성공")
    else:
        print_error("통합 테스트 실패")

    return success


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="nanoCocoa MCP 서버 테스트 실행 스크립트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--unit",
        action="store_true",
        help="단위 테스트만 실행 (서버 불필요)",
    )

    parser.add_argument(
        "--integration",
        action="store_true",
        help="통합 테스트만 실행 (AI 서버 필요)",
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="모든 테스트 실행",
    )

    parser.add_argument(
        "--quick",
        action="store_true",
        help="빠른 테스트만 실행 (slow 마크 제외)",
    )

    args = parser.parse_args()

    # 옵션이 없으면 도움말 표시
    if not (args.unit or args.integration or args.all):
        parser.print_help()
        return 1

    print_header("nanoCocoa MCP 서버 테스트")

    results = []

    # 단위 테스트
    if args.unit or args.all:
        success = run_unit_tests()
        results.append(("단위 테스트", success))

    # 통합 테스트
    if args.integration or args.all:
        success = run_integration_tests()
        results.append(("통합 테스트", success))

    # 최종 결과
    print_header("최종 결과")

    all_passed = all(success for _, success in results)

    for name, success in results:
        status = "✓ 성공" if success else "✗ 실패"
        color = Colors.GREEN if success else Colors.RED
        print(f"{color}{status}: {name}{Colors.RESET}")

    if all_passed:
        print_success("\n모든 테스트 성공!")
        return 0
    else:
        print_error("\n일부 테스트 실패")
        return 1


if __name__ == "__main__":
    sys.exit(main())
