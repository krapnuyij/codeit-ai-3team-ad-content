"""
간단한 작업 저장소 (MongoDB 대안)

메모리 기반 작업 추적 (재시작 시 소실)
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import logging
from helper_dev_utils import get_auto_logger

logger = get_auto_logger()

# 작업 저장 파일
JOBS_FILE = Path(__file__).parent.parent / "data" / "jobs.json"


class SimpleJobStore:
    """파일 기반 간단한 작업 저장소"""

    def __init__(self):
        """초기화"""
        self.jobs_file = JOBS_FILE
        self.jobs_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_jobs()

    def _load_jobs(self) -> None:
        """파일에서 작업 로드"""
        try:
            if self.jobs_file.exists():
                with open(self.jobs_file, "r", encoding="utf-8") as f:
                    self.jobs = json.load(f)
            else:
                self.jobs = {}
        except Exception as e:
            logger.warning(f"작업 파일 로드 실패: {e}")
            self.jobs = {}

    def _save_jobs(self) -> None:
        """파일에 작업 저장"""
        try:
            with open(self.jobs_file, "w", encoding="utf-8") as f:
                json.dump(self.jobs, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"작업 파일 저장 실패: {e}")

    def create_job(self, job_id: str, prompt: str, metadata: dict) -> None:
        """작업 생성"""
        self.jobs[job_id] = {
            "job_id": job_id,
            "prompt": prompt,
            "status": "processing",
            "progress_percent": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "metadata": metadata,
            "result_image_path": None,
            "error_message": None,
        }
        self._save_jobs()
        logger.info(f"작업 생성: {job_id}")

    def get_job(self, job_id: str) -> Optional[Dict]:
        """작업 조회"""
        return self.jobs.get(job_id)

    def update_job(self, job_id: str, **kwargs) -> None:
        """작업 업데이트"""
        if job_id in self.jobs:
            self.jobs[job_id].update(kwargs)
            self.jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()
            self._save_jobs()
            logger.info(f"작업 업데이트: {job_id}")

    def get_all_jobs(self, limit: int = 50) -> List[Dict]:
        """모든 작업 조회 (최신순)"""
        jobs_list = list(self.jobs.values())
        jobs_list.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return jobs_list[:limit]

    def delete_job(self, job_id: str) -> bool:
        """작업 삭제"""
        if job_id in self.jobs:
            del self.jobs[job_id]
            self._save_jobs()
            logger.info(f"작업 삭제: {job_id}")
            return True
        return False


# 싱글톤 인스턴스
_job_store = None


def get_job_store() -> SimpleJobStore:
    """작업 저장소 인스턴스 반환"""
    global _job_store
    if _job_store is None:
        _job_store = SimpleJobStore()
    return _job_store
