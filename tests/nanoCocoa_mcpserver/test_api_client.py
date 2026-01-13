"""
API 클라이언트 단위 테스트
"""

import sys
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from nanoCocoa_mcpserver.client.api_client import AIServerClient, AIServerError
from nanoCocoa_mcpserver.schemas.api_models import (
    GenerateRequest,
    GenerateResponse,
    StatusResponse,
    HealthResponse,
    FontListResponse,
)


@pytest.fixture
def api_client():
    """테스트용 API 클라이언트 생성"""
    return AIServerClient(base_url="http://test-server:8000")


@pytest.mark.asyncio
async def test_client_initialization():
    """클라이언트 초기화 테스트"""
    client = AIServerClient(base_url="http://test:8000", timeout=300, connect_timeout=5)

    assert client.base_url == "http://test:8000"
    assert client.timeout == 300
    assert client.connect_timeout == 5
    assert client._client is None


@pytest.mark.asyncio
async def test_context_manager():
    """컨텍스트 매니저 테스트"""
    async with AIServerClient() as client:
        assert client._client is not None

    # 종료 후 클라이언트가 닫혀야 함
    assert client._client is None


@pytest.mark.asyncio
async def test_check_health(api_client):
    """헬스체크 API 테스트"""
    # Mock 응답 설정
    mock_response = {
        "status": "healthy",
        "server_time": 1234567890.0,
        "total_jobs": 5,
        "active_jobs": 1,
        "system_metrics": None,
    }

    with patch.object(api_client, "_request") as mock_request:
        mock_request.return_value = MagicMock(json=lambda: mock_response)

        result = await api_client.check_health()

        assert isinstance(result, HealthResponse)
        assert result.status == "healthy"
        assert result.active_jobs == 1


@pytest.mark.asyncio
async def test_get_fonts(api_client):
    """폰트 목록 조회 테스트"""
    mock_response = {
        "fonts": ["NanumGothic/NanumGothic.ttf", "NanumSquare/NanumSquareB.ttf"]
    }

    with patch.object(api_client, "_request") as mock_request:
        mock_request.return_value = MagicMock(json=lambda: mock_response)

        result = await api_client.get_fonts()

        assert isinstance(result, list)
        assert len(result) == 2
        assert "NanumGothic/NanumGothic.ttf" in result


@pytest.mark.asyncio
async def test_start_generation(api_client):
    """생성 시작 API 테스트"""
    params = GenerateRequest(
        start_step=1,
        input_image="fake_base64_image",
        bg_prompt="Test background",
        text_content="TEST",
        text_model_prompt="Test style",
    )

    mock_response = {"job_id": "test-job-123", "status": "started"}

    with patch.object(api_client, "_request") as mock_request:
        mock_request.return_value = MagicMock(json=lambda: mock_response)

        result = await api_client.start_generation(params)

        assert isinstance(result, GenerateResponse)
        assert result.job_id == "test-job-123"
        assert result.status == "started"


@pytest.mark.asyncio
async def test_get_status(api_client):
    """상태 조회 API 테스트"""
    mock_response = {
        "job_id": "test-job-123",
        "status": "running",
        "progress_percent": 50,
        "current_step": "STEP2",
        "sub_step": "텍스트 생성 중",
        "message": "Processing...",
        "elapsed_sec": 120.5,
        "eta_seconds": 60,
        "step_eta_seconds": 30,
        "system_metrics": None,
        "parameters": {},
        "step1_result": None,
        "step2_result": None,
        "final_result": None,
    }

    with patch.object(api_client, "_request") as mock_request:
        mock_request.return_value = MagicMock(json=lambda: mock_response)

        result = await api_client.get_status("test-job-123")

        assert isinstance(result, StatusResponse)
        assert result.job_id == "test-job-123"
        assert result.status == "running"
        assert result.progress_percent == 50


@pytest.mark.asyncio
async def test_error_handling_404(api_client):
    """404 에러 처리 테스트"""
    # _request가 AIServerError를 발생시키도록 설정
    with patch.object(api_client, "_request") as mock_request:
        error = AIServerError(
            "API 요청 실패: 404", status_code=404, detail="Job not found"
        )
        mock_request.side_effect = error

        with pytest.raises(AIServerError) as exc_info:
            await api_client.get_status("non-existent-job")

        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_error_handling_503(api_client):
    """503 에러 (서버 사용 중) 처리 테스트"""
    with patch.object(api_client, "_request") as mock_request:
        # 503 에러를 발생시키도록 설정
        error = AIServerError(
            "서버가 계속 사용 중입니다. 나중에 다시 시도하세요.",
            status_code=503,
            retry_after=5,
        )
        mock_request.side_effect = error

        with pytest.raises(AIServerError) as exc_info:
            await api_client.check_health()

        assert exc_info.value.status_code == 503
        assert exc_info.value.retry_after == 5


@pytest.mark.asyncio
async def test_wait_for_completion_success(api_client):
    """완료까지 대기 - 성공 케이스"""
    # 진행 중 상태 -> 완료 상태 시뮬레이션
    status_responses = [
        {
            "job_id": "test-job",
            "status": "running",
            "progress_percent": 30,
            "current_step": "STEP1",
            "sub_step": None,
            "message": "Processing",
            "elapsed_sec": 10.0,
            "eta_seconds": 20,
            "step_eta_seconds": 10,
            "system_metrics": None,
            "parameters": {},
            "step1_result": None,
            "step2_result": None,
            "final_result": None,
        },
        {
            "job_id": "test-job",
            "status": "completed",
            "progress_percent": 100,
            "current_step": "STEP3",
            "sub_step": None,
            "message": "Completed",
            "elapsed_sec": 30.0,
            "eta_seconds": 0,
            "step_eta_seconds": 0,
            "system_metrics": None,
            "parameters": {},
            "step1_result": "step1_base64",
            "step2_result": "step2_base64",
            "final_result": "final_base64",
        },
    ]

    call_count = 0

    async def mock_get_status(job_id):
        nonlocal call_count
        response_data = status_responses[min(call_count, len(status_responses) - 1)]
        call_count += 1
        return StatusResponse(**response_data)

    with patch.object(api_client, "get_status", side_effect=mock_get_status):
        result = await api_client.wait_for_completion(
            "test-job",
            poll_interval=0.1,  # 빠른 테스트를 위해 짧은 간격
            max_retries=10,
        )

        assert result.status == "completed"
        assert result.progress_percent == 100
        assert result.final_result == "final_base64"


@pytest.mark.asyncio
async def test_wait_for_completion_failure(api_client):
    """완료까지 대기 - 실패 케이스"""
    mock_status = StatusResponse(
        job_id="test-job",
        status="failed",
        progress_percent=50,
        current_step="STEP2",
        sub_step=None,
        message="Error occurred",
        elapsed_sec=15.0,
        eta_seconds=None,
        step_eta_seconds=None,
        system_metrics=None,
        parameters={},
        step1_result=None,
        step2_result=None,
        final_result=None,
    )

    with patch.object(api_client, "get_status", return_value=mock_status):
        with pytest.raises(AIServerError) as exc_info:
            await api_client.wait_for_completion("test-job")

        assert "작업 실패" in str(exc_info.value)


@pytest.mark.asyncio
async def test_generate_and_wait(api_client):
    """원스톱 생성 및 대기 테스트"""
    params = GenerateRequest(
        start_step=1,
        input_image="test_image",
        bg_prompt="Test",
        text_content="TEST",
        text_model_prompt="Style",
    )

    mock_gen_response = GenerateResponse(job_id="test-job", status="started")

    mock_final_status = StatusResponse(
        job_id="test-job",
        status="completed",
        progress_percent=100,
        current_step="STEP3",
        sub_step=None,
        message="Done",
        elapsed_sec=60.0,
        eta_seconds=0,
        step_eta_seconds=0,
        system_metrics=None,
        parameters={},
        step1_result=None,
        step2_result=None,
        final_result="final_result_base64",
    )

    with patch.object(api_client, "start_generation", return_value=mock_gen_response):
        with patch.object(
            api_client, "wait_for_completion", return_value=mock_final_status
        ):
            result = await api_client.generate_and_wait(params)

            assert result.status == "completed"
            assert result.final_result == "final_result_base64"
