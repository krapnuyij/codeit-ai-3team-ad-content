"""
작업 모니터링 테스트 스크립트
"""

import asyncio
import sys
from pathlib import Path

# 경로 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from ad_chat.services import get_job_store, MCPClient
from ad_chat.config import MCP_SERVER_URL, MCP_TIMEOUT


async def test_job_monitoring():
    """작업 모니터링 테스트"""
    job_id = "e1e15740-ce39-4e89-8bad-2d9312a1f2a3"

    print(f"=== 작업 모니터링 테스트 ===")
    print(f"작업 ID: {job_id}")
    print(f"MCP 서버: {MCP_SERVER_URL}")
    print()

    # 작업 저장소 연결
    job_store = get_job_store()
    print("✅ 작업 저장소 연결 성공")

    # 작업 조회
    job = job_store.get_job(job_id)
    if job:
        print(f"\n📋 저장된 작업:")
        print(f"  - 상태: {job.get('status')}")
        print(f"  - 프롬프트: {job.get('prompt')}")
        print(f"  - 생성 시간: {job.get('created_at')}")
    else:
        print(f"\n⚠️  작업 {job_id}를 찾을 수 없습니다.")

    # MCP 서버에서 상태 확인
    try:
        print(f"\n🔍 MCP 서버에서 상태 확인 중...")
        async with MCPClient(base_url=MCP_SERVER_URL, timeout=MCP_TIMEOUT) as client:
            result = await client.call_tool(
                "check_generation_status", {"job_id": job_id}
            )
            print(f"\n📊 작업 상태:")
            print(result)
    except Exception as e:
        print(f"❌ 상태 확인 실패: {e}")


if __name__ == "__main__":
    asyncio.run(test_job_monitoring())
