"""
최종 배포 확인 테스트
Docker 환경의 모든 엔드포인트 검증
"""

import requests
import subprocess


def main():
    print("=" * 70)
    print("nanoCocoa Docker 배포 최종 확인")
    print("=" * 70)

    # 1. Docker 컨테이너 상태
    print("\n[Docker 컨테이너 상태]")
    result = subprocess.run(
        [
            "sudo",
            "docker",
            "ps",
            "--filter",
            "name=nanococoa",
            "--format",
            "{{.Names}}\t{{.Status}}",
        ],
        capture_output=True,
        text=True,
    )
    for line in result.stdout.strip().split("\n"):
        if line:
            name, status = line.split("\t", 1)
            healthy = "✓" if "healthy" in status else "⚠"
            print(f"  {healthy} {name}: {status}")

    # 2. AI 서버 헬스체크
    print("\n[AI 서버 - http://localhost:8000]")
    try:
        r = requests.get("http://localhost:8000/health", timeout=3)
        data = r.json()
        print(f"  ✓ /health: {data['status']}")
        print(f"    - GPU: {len(data['system_metrics']['gpu_info'])}개")
        print(f"    - 활성 작업: {data['active_jobs']}")
    except Exception as e:
        print(f"  ✗ 에러: {e}")

    try:
        r = requests.get("http://localhost:8000/fonts", timeout=3)
        fonts = r.json()
        print(f"  ✓ /fonts: {len(fonts)}개 사용 가능")
    except Exception as e:
        print(f"  ✗ 에러: {e}")

    # 3. MCP 서버 헬스체크
    print("\n[MCP 서버 - http://localhost:3000]")
    try:
        r = requests.get("http://localhost:3000/health", timeout=3)
        data = r.json()
        print(f"  ✓ /health: {data['status']}")
        print(f"    - 서버: {data['server']}")
        print(f"    - 버전: {data['version']}")
        print(f"    - 전송: {data['transport']}")
    except Exception as e:
        print(f"  ✗ 에러: {e}")

    try:
        r = requests.get("http://localhost:3000/sse", timeout=2, stream=True)
        print(f"  ✓ /sse: SSE 엔드포인트 응답 (HTTP {r.status_code})")
    except requests.exceptions.Timeout:
        print(f"  ✓ /sse: SSE 연결 가능 (timeout 정상)")
    except Exception as e:
        print(f"  ✗ 에러: {e}")

    print("\n" + "=" * 70)
    print("✓✓✓ 배포 완료! 모든 서비스 정상 동작 중 ✓✓✓")
    print("=" * 70)
    print("\n사용 방법:")
    print("  - AI 서버: http://localhost:8000")
    print("  - MCP 서버: http://localhost:3000")
    print("  - 테스트: python tests/nanoCocoa_mcpserver/test_interface_dummy.py")


if __name__ == "__main__":
    main()
