"""
Backend 개발 서버 실행 스크립트

필요한 서비스들을 자동으로 실행:
1. PostgreSQL (customer_db) - docker compose로 실행 (sudo 사용)
2. nanoCocoa_aiserver - Python으로 직접 실행
3. homepage_generator - 별도 프로세스로 실행
4. backend (FastAPI) - 메인 프로세스로 실행

사용법:
  python dev.py           # 서버 시작
  python dev.py --killall # 모든 관련 프로세스 종료
"""

import os
import sys
import subprocess
import time
import signal
import atexit
import argparse
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# 프로세스 목록 (종료 시 정리용)
processes = []


def cleanup():
    """종료 시 모든 하위 프로세스 정리"""
    print("\n🛑 서비스 종료 중...")
    for proc in processes:
        try:
            proc.terminate()
            proc.wait(timeout=5)
            print(f"✅ 프로세스 종료: PID {proc.pid}")
        except subprocess.TimeoutExpired:
            proc.kill()
            print(f"⚠️ 강제 종료: PID {proc.pid}")
        except Exception as e:
            print(f"❌ 종료 실패: {e}")


# 프로그램 종료 시 cleanup 실행
atexit.register(cleanup)
signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))


def check_port(port: int) -> bool:
    """포트 사용 여부 확인"""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


def start_postgres():
    """PostgreSQL 컨테이너 시작 (docker-compose)"""
    print("\n📦 PostgreSQL 확인 중...")

    # 이미 실행 중인지 확인
    if check_port(5432):
        print("✅ PostgreSQL 이미 실행 중 (포트 5432)")
        return True

    print("📦 PostgreSQL 시작...")

    # docker-compose 경로
    docker_compose_path = Path(__file__).parent.parent / "docker-compose.yaml"

    if not docker_compose_path.exists():
        print(f"⚠️ docker-compose.yaml을 찾을 수 없습니다: {docker_compose_path}")
        return None

    # customer_db 서비스만 시작 (sudo docker compose 사용)
    try:
        subprocess.run(
            [
                "sudo",
                "docker",
                "compose",
                "-f",
                str(docker_compose_path),
                "up",
                "-d",
                "customer_db",
            ],
            check=True,
            cwd=docker_compose_path.parent,
        )
        print("✅ PostgreSQL 컨테이너 시작 완료")

        # 연결 대기 (최대 30초)
        print("⏳ PostgreSQL 연결 대기 중...")
        for i in range(30):
            if check_port(5432):
                print("✅ PostgreSQL 연결 준비 완료")
                return True
            time.sleep(1)

        print("⚠️ PostgreSQL 연결 타임아웃")
        return None

    except subprocess.CalledProcessError as e:
        print(f"❌ PostgreSQL 시작 실패: {e}")
        return None
    except FileNotFoundError:
        print("❌ docker 명령을 찾을 수 없습니다. Docker가 설치되어 있는지 확인하세요.")
        return None


def start_nanococoa_aiserver():
    """nanoCocoa_aiserver Python으로 직접 실행"""
    print("\n🤖 nanoCocoa_aiserver 확인 중...")

    # 이미 실행 중인지 확인
    if check_port(8000):
        print("✅ nanoCocoa_aiserver 이미 실행 중 (포트 8000)")
        return True

    print("🤖 nanoCocoa_aiserver 시작...")

    aiserver_path = Path(__file__).parent.parent / "nanoCocoa_aiserver"

    if not aiserver_path.exists():
        print(f"⚠️ nanoCocoa_aiserver 경로를 찾을 수 없습니다: {aiserver_path}")
        return None

    dev_file = aiserver_path / "dev.py"
    if not dev_file.exists():
        print(f"⚠️ dev.py를 찾을 수 없습니다: {dev_file}")
        return None

    # Python으로 직접 실행
    try:
        proc = subprocess.Popen(
            [sys.executable, "dev.py"],
            cwd=aiserver_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )

        processes.append(proc)
        print(f"✅ nanoCocoa_aiserver 시작 완료 (PID: {proc.pid})")

        # 서비스 준비 대기 (GPU 모델 로딩 시간 고려)
        print("⏳ nanoCocoa_aiserver 준비 중 (GPU 모델 로딩 중...).")
        for i in range(120):  # 최대 2분 대기
            if check_port(8000):
                print("✅ nanoCocoa_aiserver 준비 완료")
                return proc
            time.sleep(1)

        print("⚠️ nanoCocoa_aiserver 타임아웃")
        return proc

    except Exception as e:
        print(f"❌ nanoCocoa_aiserver 시작 실패: {e}")
        return None


def start_homepage_generator():
    """homepage_generator 서비스 시작"""
    print("\n🏠 homepage_generator 확인 중...")

    # 이미 실행 중인지 확인
    if check_port(8891):
        print("✅ homepage_generator 이미 실행 중 (포트 8891)")
        return True

    print("🏠 homepage_generator 시작...")

    generator_path = Path(__file__).parent.parent / "homepage_generator"

    if not generator_path.exists():
        print(f"⚠️ homepage_generator 경로를 찾을 수 없습니다: {generator_path}")
        return None

    api_file = generator_path / "api.py"
    if not api_file.exists():
        print(f"⚠️ api.py를 찾을 수 없습니다: {api_file}")
        return None

    # uvicorn으로 실행
    try:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "api:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8891",
                "--reload",
            ],
            cwd=generator_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )

        processes.append(proc)
        print(f"✅ homepage_generator 시작 완료 (PID: {proc.pid})")

        # 서비스 준비 대기
        print("⏳ homepage_generator 준비 중...")
        for i in range(30):
            if check_port(8891):
                print("✅ homepage_generator 준비 완료")
                return proc
            time.sleep(1)

        print("⚠️ homepage_generator 타임아웃")
        return proc

    except Exception as e:
        print(f"❌ homepage_generator 시작 실패: {e}")
        return None


def check_nanococoa_aiserver():
    """nanoCocoa_aiserver 실행 여부 확인"""
    print("\n🤖 nanoCocoa_aiserver 확인...")

    if check_port(8000):
        print("✅ nanoCocoa_aiserver 실행 중 (포트 8000)")
        return True
    else:
        print("⚠️ nanoCocoa_aiserver가 실행 중이지 않습니다 (포트 8000)")
        print("   nanoCocoa_aiserver를 먼저 실행해주세요:")
        print("   cd ../nanoCocoa_aiserver && python dev.py")
        return False


def start_backend():
    """Backend FastAPI 서버 시작"""
    print("\n🚀 Backend 서버 확인 중...")

    # 이미 실행 중인지 확인
    if check_port(8890):
        print("❌ Backend 서버가 이미 실행 중입니다 (포트 8890)")
        print("   기존 서버를 종료하거나 다른 포트를 사용하세요.")
        sys.exit(1)

    print("🚀 Backend 서버 시작...")
    print("=" * 60)
    print("Backend 개발 서버 실행 중")
    print("=" * 60)
    print("URL: http://localhost:8890")
    print("Docs: http://localhost:8890/docs")
    print("=" * 60)
    print("\n종료하려면 Ctrl+C를 누르세요\n")

    # 환경변수 설정 (명시적으로)
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://owner:owner1234@localhost:5432/customer_db",
    )
    os.environ.setdefault("HOMEPAGE_GENERATOR_URL", "http://localhost:8891")
    os.environ.setdefault("NANOCOCOA_URL", "http://localhost:8000")

    # uvicorn 실행
    uvicorn.run("app:app", host="0.0.0.0", port=8890, reload=True, log_level="info")


def killall_services():
    """모든 관련 서비스 종료"""
    print("=" * 60)
    print("🛑 모든 서비스 종료 중...")
    print("=" * 60)

    # 1. Backend 프로세스 종료 (포트 8890)
    print("\n1️⃣ Backend 프로세스 종료 중...")
    killed_count = 0
    try:
        result = subprocess.run(
            ["lsof", "-ti", ":8890"], capture_output=True, text=True
        )
        if result.stdout.strip():
            pids = result.stdout.strip().split("\n")
            for pid in pids:
                try:
                    subprocess.run(["kill", "-9", pid], check=True)
                    print(f"   ✅ Backend PID {pid} 종료")
                    killed_count += 1
                except subprocess.CalledProcessError:
                    print(f"   ⚠️ PID {pid} 종료 실패")
        else:
            print("   ℹ️ Backend 프로세스 없음")
    except FileNotFoundError:
        print("   ⚠️ lsof 명령을 찾을 수 없습니다")

    # 2. nanoCocoa_aiserver 프로세스 종료 (포트 8000)
    print("\n2️⃣ nanoCocoa_aiserver 프로세스 종료 중...")
    try:
        result = subprocess.run(
            ["lsof", "-ti", ":8000"], capture_output=True, text=True
        )
        if result.stdout.strip():
            pids = result.stdout.strip().split("\n")
            for pid in pids:
                try:
                    subprocess.run(["kill", "-9", pid], check=True)
                    print(f"   ✅ nanoCocoa_aiserver PID {pid} 종료")
                    killed_count += 1
                except subprocess.CalledProcessError:
                    print(f"   ⚠️ PID {pid} 종료 실패")
        else:
            print("   ℹ️ nanoCocoa_aiserver 프로세스 없음")
    except FileNotFoundError:
        pass

    # 3. homepage_generator 프로세스 종료 (포트 8891)
    print("\n3️⃣ homepage_generator 프로세스 종료 중...")
    try:
        result = subprocess.run(
            ["lsof", "-ti", ":8891"], capture_output=True, text=True
        )
        if result.stdout.strip():
            pids = result.stdout.strip().split("\n")
            for pid in pids:
                try:
                    subprocess.run(["kill", "-9", pid], check=True)
                    print(f"   ✅ homepage_generator PID {pid} 종료")
                    killed_count += 1
                except subprocess.CalledProcessError:
                    print(f"   ⚠️ PID {pid} 종료 실패")
        else:
            print("   ℹ️ homepage_generator 프로세스 없음")
    except FileNotFoundError:
        pass

    # 4. PostgreSQL 컨테이너 종료
    print("\n4️⃣ PostgreSQL 컨테이너 종료 중...")
    docker_compose_path = Path(__file__).parent.parent / "docker-compose.yaml"
    if docker_compose_path.exists():
        try:
            subprocess.run(
                [
                    "sudo",
                    "docker",
                    "compose",
                    "-f",
                    str(docker_compose_path),
                    "stop",
                    "customer_db",
                ],
                check=True,
                cwd=docker_compose_path.parent,
                capture_output=True,
            )
            print("   ✅ PostgreSQL 컨테이너 중지")
            killed_count += 1
        except subprocess.CalledProcessError:
            print("   ⚠️ PostgreSQL 컨테이너 중지 실패")
        except FileNotFoundError:
            print("   ⚠️ docker 명령을 찾을 수 없습니다")
    else:
        print("   ⚠️ docker-compose.yaml을 찾을 수 없습니다")

    print("\n" + "=" * 60)
    if killed_count > 0:
        print(f"✅ 총 {killed_count}개 서비스 종료 완료")
    else:
        print("ℹ️ 종료할 서비스가 없습니다")
    print("=" * 60)


if __name__ == "__main__":
    # 명령줄 인자 파싱
    parser = argparse.ArgumentParser(description="Backend 개발 서버 관리")
    parser.add_argument("--killall", action="store_true", help="모든 관련 서비스 종료")
    args = parser.parse_args()

    # --killall 옵션 처리
    if args.killall:
        killall_services()
        sys.exit(0)
    print("=" * 60)
    print("Backend 개발 환경 시작")
    print("=" * 60)

    # 1. PostgreSQL 시작
    postgres_ok = start_postgres()
    if not postgres_ok:
        print(
            "\n❌ PostgreSQL 시작 실패. 수동으로 시작하거나 docker-compose를 확인하세요."
        )
        sys.exit(1)

    # 2. nanoCocoa_aiserver 시작
    aiserver_proc = start_nanococoa_aiserver()
    if not aiserver_proc:
        print("\n⚠️ nanoCocoa_aiserver 시작 실패. AI 이미지 생성 기능이 제한됩니다.")

    # 3. homepage_generator 시작
    generator_proc = start_homepage_generator()
    if not generator_proc:
        print("\n⚠️ homepage_generator 시작 실패. 일부 기능이 제한될 수 있습니다.")

    # 4. Backend 서버 시작 (메인 프로세스)
    try:
        start_backend()
    except KeyboardInterrupt:
        print("\n\n👋 서버 종료 요청...")
    except Exception as e:
        print(f"\n❌ Backend 서버 오류: {e}")
    finally:
        cleanup()
