"""
동시성 제어 통합 테스트.

여러 클라이언트가 동시에 /generate를 호출할 때 
503 응답 및 작업 큐 동작을 검증합니다.
"""

import pytest
import asyncio
from fastapi.testclient import TestClient

import sys
from pathlib import Path

# src/nanoCocoa_aiserver를 path에 추가
sys.path.insert(0, str(Path(__file__).parents[2] / "src" / "nanoCocoa_aiserver"))

from main import app


class TestConcurrency:
    """동시성 제어 테스트"""
    
    @pytest.fixture
    def client(self):
        """TestClient 생성"""
        return TestClient(app)
    
    @pytest.mark.integration
    def test_single_job_accepted(self, client):
        """단일 작업은 정상 수락"""
        payload = {
            "product_image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            "background_prompt": "Simple white background",
            "text_content": "SALE",
            "test_mode": True  # 더미 모드
        }
        
        response = client.post("/generate", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "started"
    
    @pytest.mark.integration
    @pytest.mark.skip(reason="동시성 테스트는 실제 멀티프로세싱 환경 필요")
    def test_concurrent_jobs_return_503(self, client):
        """동시 작업 요청 시 503 응답"""
        payload = {
            "product_image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            "background_prompt": "Simple white background",
            "text_content": "SALE",
            "test_mode": True
        }
        
        # 첫 번째 작업 시작
        response1 = client.post("/generate", json=payload)
        assert response1.status_code == 200
        
        # 즉시 두 번째 작업 요청
        response2 = client.post("/generate", json=payload)
        
        # 두 번째 요청은 503 Busy 응답
        assert response2.status_code == 503
        data2 = response2.json()
        assert data2["status"] == "busy"
        assert "retry_after" in data2
    
    @pytest.mark.integration
    def test_job_status_endpoint(self, client):
        """작업 상태 조회 엔드포인트"""
        # 작업 생성
        payload = {
            "product_image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            "background_prompt": "Simple white background",
            "text_content": "SALE",
            "test_mode": True
        }
        
        create_response = client.post("/generate", json=payload)
        job_id = create_response.json()["job_id"]
        
        # 상태 조회
        status_response = client.get(f"/status/{job_id}")
        
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["job_id"] == job_id
        assert "status" in status_data
        assert status_data["status"] in ["queued", "running", "completed", "error", "stopped"]
    
    @pytest.mark.integration
    def test_invalid_job_id_returns_404(self, client):
        """존재하지 않는 작업 ID 조회 시 404"""
        response = client.get("/status/nonexistent-job-id")
        
        assert response.status_code == 404
