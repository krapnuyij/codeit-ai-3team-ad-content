"""
setup_mcp.py
MCP 서버를 Claude Desktop에 설정하는 스크립트

사용법:
    python setup_mcp.py --install   # Claude Desktop에 MCP 서버 추가
    python setup_mcp.py --uninstall # Claude Desktop에서 MCP 서버 제거
    python setup_mcp.py --show      # 현재 설정 표시
    python setup_mcp.py --test      # MCP 서버 테스트
"""

import json
import os
import sys
import platform
import subprocess
from pathlib import Path
import argparse


def get_claude_config_path():
    """Claude Desktop 설정 파일 경로 반환"""
    system = platform.system()

    if system == "Windows":
        appdata = os.getenv("APPDATA")
        if not appdata:
            raise RuntimeError("APPDATA 환경 변수를 찾을 수 없습니다")
        return Path(appdata) / "Claude" / "claude_desktop_config.json"

    elif system == "Darwin":  # macOS
        home = Path.home()
        return (
            home
            / "Library"
            / "Application Support"
            / "Claude"
            / "claude_desktop_config.json"
        )

    elif system == "Linux":
        home = Path.home()
        return home / ".config" / "Claude" / "claude_desktop_config.json"

    else:
        raise RuntimeError(f"지원하지 않는 운영체제: {system}")


def get_project_config():
    """프로젝트 MCP 설정 읽기"""
    config_path = Path(__file__).parent / ".mcp" / "config.json"

    if not config_path.exists():
        raise FileNotFoundError(f"MCP 설정 파일을 찾을 수 없습니다: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    return config["mcpServers"]


def read_claude_config(config_path):
    """Claude Desktop 설정 읽기"""
    if not config_path.exists():
        # 설정 파일이 없으면 빈 설정 생성
        config_path.parent.mkdir(parents=True, exist_ok=True)
        return {"mcpServers": {}}

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_claude_config(config_path, config):
    """Claude Desktop 설정 쓰기"""
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def install_mcp_server():
    """MCP 서버를 Claude Desktop에 설치"""
    try:
        print("🔧 MCP 서버 설치를 시작합니다...\n")

        # Claude Desktop 설정 경로
        config_path = get_claude_config_path()
        print(f"Claude 설정 파일: {config_path}")

        # 프로젝트 설정 읽기
        project_config = get_project_config()

        # mcp_server.py의 절대 경로
        mcp_server_path = Path(__file__).parent / "mcp_server.py"
        if not mcp_server_path.exists():
            raise FileNotFoundError(
                f"MCP 서버 파일을 찾을 수 없습니다: {mcp_server_path}"
            )

        # 설정 업데이트
        server_config = project_config["nanococoa-ad-generator"].copy()
        server_config["args"] = [str(mcp_server_path.resolve())]

        # Claude 설정 읽기
        claude_config = read_claude_config(config_path)

        # mcpServers 섹션이 없으면 생성
        if "mcpServers" not in claude_config:
            claude_config["mcpServers"] = {}

        # MCP 서버 추가
        claude_config["mcpServers"]["nanococoa-ad-generator"] = server_config

        # 설정 저장
        write_claude_config(config_path, claude_config)

        print("MCP 서버가 성공적으로 설치되었습니다!\n")
        print(f"설정 위치: {config_path}")
        print(f"MCP 서버: {mcp_server_path}")
        print("\n Claude Desktop을 재시작해야 변경사항이 적용됩니다.")
        print("\n다음 단계:")
        print("1. FastAPI 서버 시작: python main.py")
        print("2. Claude Desktop 재시작")
        print("3. Claude에서 MCP 도구 사용 가능")

    except Exception as e:
        print(f"설치 중 오류 발생: {e}", file=sys.stderr)
        return False

    return True


def uninstall_mcp_server():
    """MCP 서버를 Claude Desktop에서 제거"""
    try:
        print(" MCP 서버 제거를 시작합니다...\n")

        # Claude Desktop 설정 경로
        config_path = get_claude_config_path()
        print(f"Claude 설정 파일: {config_path}")

        if not config_path.exists():
            print(" Claude Desktop 설정 파일이 없습니다.")
            return True

        # Claude 설정 읽기
        claude_config = read_claude_config(config_path)

        # MCP 서버 제거
        if (
            "mcpServers" in claude_config
            and "nanococoa-ad-generator" in claude_config["mcpServers"]
        ):
            del claude_config["mcpServers"]["nanococoa-ad-generator"]
            write_claude_config(config_path, claude_config)
            print("MCP 서버가 성공적으로 제거되었습니다!")
        else:
            print(" 설치된 MCP 서버를 찾을 수 없습니다.")

        print("\n Claude Desktop을 재시작해야 변경사항이 적용됩니다.")

    except Exception as e:
        print(f"제거 중 오류 발생: {e}", file=sys.stderr)
        return False

    return True


def show_config():
    """현재 설정 표시"""
    try:
        print("현재 MCP 설정\n")
        print("=" * 60)

        # Claude Desktop 설정
        config_path = get_claude_config_path()
        print(f"\n1. Claude Desktop 설정 위치:")
        print(f"   {config_path}")

        if config_path.exists():
            claude_config = read_claude_config(config_path)
            if (
                "mcpServers" in claude_config
                and "nanococoa-ad-generator" in claude_config["mcpServers"]
            ):
                print("\n   MCP 서버가 설치되어 있습니다")
                print("\n   설정 내용:")
                print(
                    json.dumps(
                        claude_config["mcpServers"]["nanococoa-ad-generator"], indent=4
                    )
                )
            else:
                print("\n    MCP 서버가 설치되어 있지 않습니다")
        else:
            print("\n    Claude Desktop 설정 파일이 없습니다")

        # 프로젝트 설정
        print("\n" + "=" * 60)
        print("\n2. 프로젝트 MCP 설정:")
        config_path = Path(__file__).parent / ".mcp" / "config.json"
        print(f"   {config_path}")

        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                project_config = json.load(f)
            print("\n   설정 내용:")
            print(json.dumps(project_config, indent=4, ensure_ascii=False))
        else:
            print("\n    프로젝트 설정 파일이 없습니다")

        # MCP 서버 파일
        print("\n" + "=" * 60)
        print("\n3. MCP 서버 파일:")
        mcp_server_path = Path(__file__).parent / "mcp_server.py"
        print(f"   {mcp_server_path}")
        print(f"   존재: {'예' if mcp_server_path.exists() else '아니오'}")

        print("\n" + "=" * 60)

    except Exception as e:
        print(f"설정 확인 중 오류 발생: {e}", file=sys.stderr)
        return False

    return True


def test_mcp_server():
    """MCP 서버 테스트"""
    print("MCP 서버 테스트를 시작합니다...\n")

    # 1. 의존성 확인
    print("1. 의존성 확인...")
    try:
        import mcp

        print("   mcp 패키지 설치됨")
    except ImportError:
        print("   mcp 패키지가 설치되어 있지 않습니다")
        print("      설치: pip install mcp")
        return False

    try:
        import httpx

        print("   httpx 패키지 설치됨")
    except ImportError:
        print("   httpx 패키지가 설치되어 있지 않습니다")
        print("      설치: pip install httpx")
        return False

    # 2. MCP 서버 파일 확인
    print("\n2. MCP 서버 파일 확인...")
    mcp_server_path = Path(__file__).parent / "mcp_server.py"
    if mcp_server_path.exists():
        print(f"   {mcp_server_path}")
    else:
        print(f"   MCP 서버 파일을 찾을 수 없습니다: {mcp_server_path}")
        return False

    # 3. FastAPI 서버 확인
    print("\n3. FastAPI 서버 연결 확인...")
    try:
        import httpx

        response = httpx.get("http://localhost:8000/health", timeout=5.0)
        if response.status_code == 200:
            print("   FastAPI 서버가 실행 중입니다")
            data = response.json()
            print(f"      상태: {data.get('status')}")
            print(f"      활성 작업: {data.get('active_jobs')}")
        else:
            print(f"    FastAPI 서버 응답: {response.status_code}")
    except Exception as e:
        print(f"   FastAPI 서버에 연결할 수 없습니다")
        print(f"      오류: {e}")
        print("      FastAPI 서버를 먼저 시작해주세요: python main.py")
        return False

    # 4. 테스트 스크립트 실행
    print("\n4. MCP 인터페이스 테스트 실행...")
    test_script = (
        Path(__file__).parent.parent.parent / "tests" / "mcp" / "test_mcp_dummy.py"
    )

    if test_script.exists():
        print(f"   테스트 스크립트: {test_script}")
        print("\n   pytest를 실행하여 MCP 인터페이스를 테스트합니다...")
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_script), "-v"],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            print("\n   모든 테스트 통과!")
        else:
            print("\n    일부 테스트 실패")
            print("\n   출력:")
            print(result.stdout)
            if result.stderr:
                print("\n   오류:")
                print(result.stderr)
    else:
        print(f"    테스트 스크립트를 찾을 수 없습니다: {test_script}")

    print("\n" + "=" * 60)
    print("테스트 완료!")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="nanoCocoa MCP 서버 설정 도구",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python setup_mcp.py --install     # MCP 서버 설치
  python setup_mcp.py --uninstall   # MCP 서버 제거
  python setup_mcp.py --show        # 현재 설정 표시
  python setup_mcp.py --test        # MCP 서버 테스트
        """,
    )

    parser.add_argument(
        "--install", action="store_true", help="MCP 서버를 Claude Desktop에 설치"
    )
    parser.add_argument(
        "--uninstall", action="store_true", help="MCP 서버를 Claude Desktop에서 제거"
    )
    parser.add_argument("--show", action="store_true", help="현재 설정 표시")
    parser.add_argument("--test", action="store_true", help="MCP 서버 테스트")

    args = parser.parse_args()

    # 옵션이 하나도 없으면 도움말 표시
    if not any([args.install, args.uninstall, args.show, args.test]):
        parser.print_help()
        return

    # 작업 실행
    if args.install:
        success = install_mcp_server()
        sys.exit(0 if success else 1)

    if args.uninstall:
        success = uninstall_mcp_server()
        sys.exit(0 if success else 1)

    if args.show:
        success = show_config()
        sys.exit(0 if success else 1)

    if args.test:
        success = test_mcp_server()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
