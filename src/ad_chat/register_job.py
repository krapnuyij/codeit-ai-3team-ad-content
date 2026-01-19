"""
기존 작업 ID를 SimpleJobStore에 등록하는 스크립트
"""

import sys
from pathlib import Path

# 경로 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from ad_chat.services import get_job_store


def register_job(job_id: str, prompt: str):
    """작업 등록"""
    job_store = get_job_store()

    # 이미 존재하는지 확인
    existing_job = job_store.get_job(job_id)
    if existing_job:
        print(f"✅ 작업이 이미 등록되어 있습니다: {job_id}")
        print(f"   상태: {existing_job.get('status')}")
        print(f"   프롬프트: {existing_job.get('prompt')}")
        return

    # 새 작업 등록
    metadata = {
        "text_content": prompt,
        "product_image_path": "test_product.png",
        "composition_mode": "overlay",
        "model": "gpt-5-mini",
        "mcp_server_url": "http://34.44.205.198:3000",
    }

    job_store.create_job(
        job_id=job_id,
        prompt=prompt,
        metadata=metadata,
    )

    print(f"✅ 작업이 등록되었습니다: {job_id}")
    print(f"   프롬프트: {prompt}")
    print(f"   초기 상태: processing")


if __name__ == "__main__":
    job_id = "e1e15740-ce39-4e89-8bad-2d9312a1f2a3"
    prompt = "맛있는 바나나 2500원"

    register_job(job_id, prompt)
