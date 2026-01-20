"""
MongoDB 서비스 계층

작업(Job) 및 프롬프트 히스토리를 MongoDB에 저장/조회/업데이트하는 클래스
"""

from typing import Dict, List, Optional
from datetime import datetime
from pymongo import MongoClient, DESCENDING
from pymongo.errors import PyMongoError
import logging

from config import (
    MONGO_URI,
    MONGO_DB_NAME,
    MONGO_COLLECTION_JOBS,
    MONGO_COLLECTION_PROMPTS,
    STATUS_PENDING,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MongoManager:
    """MongoDB CRUD 작업을 담당하는 클래스"""

    def __init__(self, uri: str = MONGO_URI, db_name: str = MONGO_DB_NAME):
        """
        Args:
            uri: MongoDB 연결 URI
            db_name: 사용할 데이터베이스 이름
        """
        self.uri = uri
        self.db_name = db_name
        self.client: Optional[MongoClient] = None
        self.db = None
        self.connected = False
        self._connect()

    def _connect(self) -> None:
        """MongoDB 연결 초기화"""
        try:
            self.client = MongoClient(self.uri, serverSelectionTimeoutMS=5000)
            # 연결 테스트
            self.client.server_info()
            self.db = self.client[self.db_name]
            self.connected = True
            logger.info(f"MongoDB 연결 성공: {self.db_name}")
        except PyMongoError as e:
            self.connected = False
            logger.warning(f"MongoDB 연결 실패 (선택적 기능 비활성화): {e}")
            logger.info("MongoDB 없이 계속 진행합니다 (작업 이력 저장 불가)")

    def close(self) -> None:
        """MongoDB 연결 종료"""
        if self.client:
            self.client.close()
            logger.info("MongoDB 연결 종료")

    # ===================================================================
    # Job CRUD
    # ===================================================================

    def create_job(
        self,
        job_id: str,
        prompt: str,
        job_type: str,
        status: str = STATUS_PENDING,
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        새 작업 생성

        Args:
            job_id: MCP 서버에서 받은 작업 ID
            prompt: 사용자가 입력한 광고 생성 프롬프트
            job_type: 작업 타입 (full/text_only)
            status: 초기 상태 (기본값: pending)
            metadata: 추가 메타데이터 (제품 이미지 경로 등)

        Returns:
            MongoDB document ID
        """
        job = {
            "job_id": job_id,
            "prompt": prompt,
            "job_type": job_type,
            "status": status,
            "progress_percent": 0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "result_image_path": None,
            "result_text": None,
            "error_message": None,
            "metadata": metadata or {},
        }

        try:
            result = self.db[MONGO_COLLECTION_JOBS].insert_one(job)
            logger.info(f"작업 생성 완료: job_id={job_id}, _id={result.inserted_id}")
            return str(result.inserted_id)
        except PyMongoError as e:
            logger.error(f"작업 생성 실패: {e}")
            raise

    def get_job_by_id(self, job_id: str) -> Optional[Dict]:
        """
        Job ID로 작업 조회

        Args:
            job_id: MCP 서버 작업 ID

        Returns:
            작업 문서 (없으면 None)
        """
        try:
            job = self.db[MONGO_COLLECTION_JOBS].find_one({"job_id": job_id})
            return job
        except PyMongoError as e:
            logger.error(f"작업 조회 실패: {e}")
            return None

    def update_job_status(
        self,
        job_id: str,
        status: str,
        progress_percent: Optional[int] = None,
        result_image_path: Optional[str] = None,
        result_text: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """
        작업 상태 업데이트

        Args:
            job_id: 작업 ID
            status: 새 상태
            progress_percent: 진행률 (0~100)
            result_image_path: 결과 이미지 경로
            result_text: 결과 텍스트
            error_message: 오류 메시지

        Returns:
            성공 여부
        """
        if not self.connected:
            logger.debug(f"MongoDB 비활성화 - 작업 업데이트 생략: {job_id}")
            return False

        update_fields = {"status": status, "updated_at": datetime.utcnow()}

        if progress_percent is not None:
            update_fields["progress_percent"] = progress_percent
        if result_image_path:
            update_fields["result_image_path"] = result_image_path
        if result_text:
            update_fields["result_text"] = result_text
        if error_message:
            update_fields["error_message"] = error_message

        try:
            result = self.db[MONGO_COLLECTION_JOBS].update_one(
                {"job_id": job_id}, {"$set": update_fields}
            )
            if result.modified_count > 0:
                logger.info(f"작업 상태 업데이트: job_id={job_id}, status={status}")
                return True
            return False
        except PyMongoError as e:
            logger.error(f"작업 상태 업데이트 실패: {e}")
            return False

    def get_all_jobs(self, limit: int = 50) -> List[Dict]:
        """
        모든 작업 조회 (최신순)

        Args:
            limit: 최대 반환 개수

        Returns:
            작업 목록
        """
        if not self.connected:
            logger.debug("MongoDB 비활성화 - 빈 작업 목록 반환")
            return []

        try:
            jobs = list(
                self.db[MONGO_COLLECTION_JOBS]
                .find()
                .sort("created_at", DESCENDING)
                .limit(limit)
            )
            return jobs
        except PyMongoError as e:
            logger.error(f"작업 목록 조회 실패: {e}")
            return []

    def delete_job(self, job_id: str) -> bool:
        """
        작업 삭제

        Args:
            job_id: 삭제할 작업 ID

        Returns:
            성공 여부
        """
        try:
            result = self.db[MONGO_COLLECTION_JOBS].delete_one({"job_id": job_id})
            if result.deleted_count > 0:
                logger.info(f"작업 삭제 완료: job_id={job_id}")
                return True
            return False
        except PyMongoError as e:
            logger.error(f"작업 삭제 실패: {e}")
            return False

    # ===================================================================
    # Prompt History CRUD
    # ===================================================================

    def save_prompt(self, prompt: str, metadata: Optional[Dict] = None) -> str:
        """
        프롬프트 히스토리 저장

        Args:
            prompt: 사용자 프롬프트
            metadata: 추가 메타데이터

        Returns:
            MongoDB document ID
        """
        doc = {
            "prompt": prompt,
            "created_at": datetime.utcnow(),
            "metadata": metadata or {},
        }

        try:
            result = self.db[MONGO_COLLECTION_PROMPTS].insert_one(doc)
            return str(result.inserted_id)
        except PyMongoError as e:
            logger.error(f"프롬프트 저장 실패: {e}")
            raise

    def get_recent_prompts(self, limit: int = 10) -> List[Dict]:
        """
        최근 프롬프트 조회

        Args:
            limit: 최대 반환 개수

        Returns:
            프롬프트 목록
        """
        try:
            prompts = list(
                self.db[MONGO_COLLECTION_PROMPTS]
                .find()
                .sort("created_at", DESCENDING)
                .limit(limit)
            )
            return prompts
        except PyMongoError as e:
            logger.error(f"프롬프트 조회 실패: {e}")
            return []
