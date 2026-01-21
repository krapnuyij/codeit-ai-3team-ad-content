"""
작업 관리 핸들러 함수
"""

import logging

from handlers.generation import get_api_client
from client.api_client import AIServerError
from helper_dev_utils import get_auto_logger

logger = get_auto_logger()


async def get_all_jobs() -> str:
    """AI 서버에 등록된 모든 작업 목록을 조회합니다."""
    try:
        client = await get_api_client()
        jobs = await client.list_jobs()

        import json

        if not jobs.jobs:
            return json.dumps(
                {"total_jobs": 0, "jobs": [], "message": "No jobs registered"},
                ensure_ascii=False,
            )

        job_list = []
        for job in jobs.jobs:
            job_data = {
                "job_id": job.job_id,
                "status": job.status,
                "progress_percent": job.progress_percent,
                "current_step": job.current_step,
                "elapsed_sec": round(job.elapsed_sec, 1),
            }
            job_list.append(job_data)

        return json.dumps(
            {"total_jobs": len(jobs.jobs), "jobs": job_list}, ensure_ascii=False
        )

    except AIServerError as e:
        return f"AI 서버 에러: {str(e)}"
    except Exception as e:
        logger.exception(f"작업 목록 조회 중 에러: {e}")
        return f"작업 목록 조회 중 에러 발생: {str(e)}"


async def delete_all_jobs() -> str:
    """완료되었거나 실패한 모든 작업을 삭제합니다."""
    try:
        client = await get_api_client()
        jobs = await client.list_jobs()

        if not jobs.jobs:
            return "삭제할 작업이 없습니다."

        deleted_count = 0
        skipped_count = 0
        errors = []

        for job in jobs.jobs:
            if job.status in ["pending", "running"]:
                skipped_count += 1
                logger.info(
                    f"실행/대기 중인 작업 건너뜀: {job.job_id} (상태: {job.status})"
                )
                continue

            try:
                await client.delete_job(job.job_id)
                deleted_count += 1
                logger.info(f"작업 삭제 완료: {job.job_id}")
            except Exception as e:
                errors.append(f"{job.job_id}: {str(e)}")
                logger.error(f"작업 삭제 실패: {job.job_id}, 에러: {e}")

        response = f"작업 정리 완료\n"
        response += f"  삭제됨: {deleted_count}개\n"
        response += f"  건너뜀 (실행/대기 중): {skipped_count}개\n"

        if errors:
            response += f"\n삭제 실패:\n"
            for error in errors:
                response += f"  - {error}\n"

        return response

    except AIServerError as e:
        return f"AI 서버 에러: {str(e)}"
    except Exception as e:
        logger.exception(f"작업 삭제 중 에러: {e}")
        return f"작업 삭제 중 에러 발생: {str(e)}"


async def delete_job(job_id: str) -> str:
    """특정 작업을 삭제합니다."""
    try:
        client = await get_api_client()
        result = await client.delete_job(job_id)
        return f"작업 삭제 완료\n작업 ID: {job_id}\n상태: {result.get('status', 'deleted')}"

    except AIServerError as e:
        return f"AI 서버 에러: {str(e)}"
    except Exception as e:
        logger.exception(f"작업 삭제 중 에러: {e}")
        return f"작업 삭제 중 에러 발생: {str(e)}"
