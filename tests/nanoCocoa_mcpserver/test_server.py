"""
MCP 서버 단위 테스트

주의: 이 테스트는 MCP SDK가 설치되지 않은 환경에서는 스킵됩니다.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import base64
import io
import sys
from pathlib import Path
from PIL import Image

# 테스트 파일 위치 기준으로 프로젝트 루트의 src 경로 설정
project_root = Path(__file__).resolve().parents[2] / "src"
assert project_root.exists(), f"src 디렉터리를 찾을 수 없습니다: {project_root}"
sys.path.insert(0, str(project_root))


# MCP가 설치되어 있는지 확인
try:
    from nanoCocoa_mcpserver.server import NanoCocoaMCPServer

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

from nanoCocoa_mcpserver.schemas.api_models import (
    GenerateResponse,
    StatusResponse,
    HealthResponse,
    FontListResponse,
    StopResponse,
)
from nanoCocoa_mcpserver.client.api_client import AIServerError


# MCP가 없으면 모든 테스트 스킵
pytestmark = pytest.mark.skipif(
    not MCP_AVAILABLE,
    reason="MCP SDK가 설치되지 않았습니다. pip install mcp 로 설치하세요.",
)


@pytest.fixture
def mcp_server():
    """테스트용 MCP 서버 인스턴스"""
    return NanoCocoaMCPServer()


@pytest.fixture
def mock_api_client():
    """Mock API 클라이언트"""
    client = AsyncMock()
    client._ensure_client = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def sample_image_base64():
    """테스트용 Base64 이미지"""
    img = Image.new("RGB", (100, 100), color="red")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


@pytest.fixture
def temp_product_image(tmp_path, sample_image_base64):
    """테스트용 임시 제품 이미지 파일"""
    img_path = tmp_path / "product.png"
    img_data = base64.b64decode(sample_image_base64)
    img_path.write_bytes(img_data)
    return str(img_path)


@pytest.mark.asyncio
async def test_server_initialization(mcp_server):
    """MCP 서버 초기화 테스트"""
    assert mcp_server.server is not None
    assert mcp_server.api_client is None


@pytest.mark.asyncio
async def test_handle_list_fonts(mcp_server, mock_api_client):
    """폰트 목록 조회 핸들러 테스트"""
    # Mock 설정
    mock_api_client.get_fonts.return_value = [
        "NanumGothic/NanumGothic.ttf",
        "NanumSquare/NanumSquareB.ttf",
    ]
    mcp_server.api_client = mock_api_client

    # 핸들러 호출
    result = await mcp_server._handle_list_fonts({})

    # 결과 검증
    assert len(result) == 1
    assert result[0].type == "text"
    assert "NanumGothic" in result[0].text
    assert "2개" in result[0].text


@pytest.mark.asyncio
async def test_handle_check_health(mcp_server, mock_api_client):
    """헬스체크 핸들러 테스트"""
    # Mock 설정
    mock_health = HealthResponse(
        status="healthy",
        server_time=1234567890.0,
        total_jobs=10,
        active_jobs=2,
        system_metrics=None,
    )
    mock_api_client.check_health.return_value = mock_health
    mcp_server.api_client = mock_api_client

    # 핸들러 호출
    result = await mcp_server._handle_check_health({})

    # 결과 검증
    assert len(result) == 1
    assert result[0].type == "text"
    assert "healthy" in result[0].text
    assert "10개" in result[0].text
    assert "2개" in result[0].text


@pytest.mark.asyncio
async def test_handle_check_status(mcp_server, mock_api_client):
    """상태 확인 핸들러 테스트"""
    # Mock 설정
    mock_status = StatusResponse(
        job_id="test-job-123",
        status="running",
        progress_percent=50,
        current_step="STEP2",
        sub_step="텍스트 생성 중",
        message="Processing...",
        elapsed_sec=120.5,
        eta_seconds=60,
        step_eta_seconds=30,
        system_metrics=None,
        parameters={},
        step1_result=None,
        step2_result=None,
        final_result=None,
    )
    mock_api_client.get_status.return_value = mock_status
    mcp_server.api_client = mock_api_client

    # 핸들러 호출
    result = await mcp_server._handle_check_status({"job_id": "test-job-123"})

    # 결과 검증
    assert len(result) == 1
    assert result[0].type == "text"
    assert "running" in result[0].text
    assert "50%" in result[0].text
    assert "STEP2" in result[0].text


@pytest.mark.asyncio
async def test_handle_check_status_completed(
    mcp_server, mock_api_client, sample_image_base64, tmp_path
):
    """완료된 작업 상태 확인 테스트"""
    # Mock 설정
    mock_status = StatusResponse(
        job_id="test-job-123",
        status="completed",
        progress_percent=100,
        current_step="STEP3",
        sub_step=None,
        message="Complete",
        elapsed_sec=180.0,
        eta_seconds=0,
        step_eta_seconds=0,
        system_metrics=None,
        parameters={},
        step1_result=None,
        step2_result=None,
        final_result=sample_image_base64,
    )
    mock_api_client.get_status.return_value = mock_status
    mcp_server.api_client = mock_api_client

    # 결과 저장 경로 지정
    save_path = str(tmp_path / "result.png")

    # 핸들러 호출
    result = await mcp_server._handle_check_status(
        {"job_id": "test-job-123", "save_result_path": save_path}
    )

    # 결과 검증
    assert len(result) == 1
    assert "완료" in result[0].text
    assert "100%" in result[0].text

    # 파일 저장 확인
    assert Path(save_path).exists()


@pytest.mark.asyncio
async def test_handle_stop_generation(mcp_server, mock_api_client):
    """작업 중단 핸들러 테스트"""
    # Mock 설정
    mock_stop = StopResponse(job_id="test-job-123", status="stopped")
    mock_api_client.stop_job.return_value = mock_stop
    mcp_server.api_client = mock_api_client

    # 핸들러 호출
    result = await mcp_server._handle_stop_generation({"job_id": "test-job-123"})

    # 결과 검증
    assert len(result) == 1
    assert "중단" in result[0].text
    assert "test-job-123" in result[0].text


@pytest.mark.asyncio
async def test_handle_generate_ad_image_async(
    mcp_server, mock_api_client, temp_product_image
):
    """비동기 광고 이미지 생성 핸들러 테스트"""
    # Mock 설정
    mock_response = GenerateResponse(job_id="new-job-123", status="started")
    mock_api_client.start_generation.return_value = mock_response
    mcp_server.api_client = mock_api_client

    # 핸들러 호출 (비동기 모드: wait_for_completion=False)
    result = await mcp_server._handle_generate_ad_image(
        {
            "product_image_path": temp_product_image,
            "background_prompt": "Test background",
            "text_content": "TEST",
            "text_style_prompt": "Test style",
            "wait_for_completion": False,
        }
    )

    # 결과 검증
    assert len(result) == 1
    assert "시작" in result[0].text
    assert "new-job-123" in result[0].text


@pytest.mark.asyncio
async def test_handle_generate_ad_image_sync(
    mcp_server, mock_api_client, temp_product_image, sample_image_base64
):
    """동기 광고 이미지 생성 핸들러 테스트"""
    # Mock 설정
    mock_final_status = StatusResponse(
        job_id="completed-job",
        status="completed",
        progress_percent=100,
        current_step="STEP3",
        sub_step=None,
        message="Done",
        elapsed_sec=180.0,
        eta_seconds=0,
        step_eta_seconds=0,
        system_metrics=None,
        parameters={},
        step1_result=sample_image_base64,
        step2_result=sample_image_base64,
        final_result=sample_image_base64,
    )
    mock_api_client.generate_and_wait.return_value = mock_final_status
    mcp_server.api_client = mock_api_client

    # 핸들러 호출 (동기 모드: wait_for_completion=True)
    result = await mcp_server._handle_generate_ad_image(
        {
            "product_image_path": temp_product_image,
            "background_prompt": "Test background",
            "text_content": "TEST",
            "text_style_prompt": "Test style",
            "wait_for_completion": True,
        }
    )

    # 결과 검증
    assert len(result) == 1
    assert "완료" in result[0].text
    assert "completed-job" in result[0].text
    assert "180" in result[0].text  # 소요 시간


@pytest.mark.asyncio
async def test_handle_generate_background_only(
    mcp_server, mock_api_client, temp_product_image, sample_image_base64, tmp_path
):
    """배경만 생성 핸들러 테스트"""
    # Mock 설정
    mock_final_status = StatusResponse(
        job_id="bg-job",
        status="completed",
        progress_percent=100,
        current_step="STEP1",
        sub_step=None,
        message="Done",
        elapsed_sec=60.0,
        eta_seconds=0,
        step_eta_seconds=0,
        system_metrics=None,
        parameters={},
        step1_result=sample_image_base64,
        step2_result=None,
        final_result=None,
    )
    mock_api_client.generate_and_wait.return_value = mock_final_status
    mcp_server.api_client = mock_api_client

    save_path = str(tmp_path / "bg_result.png")

    # 핸들러 호출
    result = await mcp_server._handle_generate_background_only(
        {
            "product_image_path": temp_product_image,
            "background_prompt": "Test background",
            "wait_for_completion": True,
            "save_output_path": save_path,
        }
    )

    # 결과 검증
    assert len(result) == 1
    assert "완료" in result[0].text
    assert "bg-job" in result[0].text
    assert Path(save_path).exists()


@pytest.mark.asyncio
async def test_handle_generate_text_asset_only_with_base64(
    mcp_server, mock_api_client, sample_image_base64
):
    """3D 텍스트만 생성 핸들러 테스트 (Base64 입력)"""
    # Mock 설정
    mock_final_status = StatusResponse(
        job_id="text-job",
        status="completed",
        progress_percent=100,
        current_step="STEP2",
        sub_step=None,
        message="Done",
        elapsed_sec=90.0,
        eta_seconds=0,
        step_eta_seconds=0,
        system_metrics=None,
        parameters={},
        step1_result=None,
        step2_result=sample_image_base64,
        final_result=None,
    )
    mock_api_client.generate_and_wait.return_value = mock_final_status
    mcp_server.api_client = mock_api_client

    # 핸들러 호출
    result = await mcp_server._handle_generate_text_asset_only(
        {
            "step1_image_base64": sample_image_base64,
            "text_content": "SALE",
            "text_style_prompt": "Gold metallic",
            "wait_for_completion": True,
        }
    )

    # 결과 검증
    assert len(result) == 1
    assert "완료" in result[0].text


@pytest.mark.asyncio
async def test_handle_generate_text_asset_only_missing_input(
    mcp_server, mock_api_client
):
    """3D 텍스트 생성 - 입력 누락 시 에러 처리"""
    mcp_server.api_client = mock_api_client

    # step1_image 없이 호출
    result = await mcp_server._handle_generate_text_asset_only(
        {"text_content": "SALE", "text_style_prompt": "Gold metallic"}
    )

    # 에러 메시지 확인
    assert len(result) == 1
    assert "에러" in result[0].text
    assert "필수" in result[0].text


@pytest.mark.asyncio
async def test_handle_compose_final_image(
    mcp_server, mock_api_client, sample_image_base64, tmp_path
):
    """최종 합성 핸들러 테스트"""
    # Mock 설정
    mock_final_status = StatusResponse(
        job_id="compose-job",
        status="completed",
        progress_percent=100,
        current_step="STEP3",
        sub_step=None,
        message="Done",
        elapsed_sec=45.0,
        eta_seconds=0,
        step_eta_seconds=0,
        system_metrics=None,
        parameters={},
        step1_result=None,
        step2_result=None,
        final_result=sample_image_base64,
    )
    mock_api_client.generate_and_wait.return_value = mock_final_status
    mcp_server.api_client = mock_api_client

    save_path = str(tmp_path / "final.png")

    # 핸들러 호출
    result = await mcp_server._handle_compose_final_image(
        {
            "step1_image_base64": sample_image_base64,
            "step2_image_base64": sample_image_base64,
            "composition_mode": "overlay",
            "text_position": "center",
            "wait_for_completion": True,
            "save_output_path": save_path,
        }
    )

    # 결과 검증
    assert len(result) == 1
    assert "완료" in result[0].text
    assert Path(save_path).exists()


@pytest.mark.asyncio
async def test_handle_compose_final_image_missing_inputs(mcp_server, mock_api_client):
    """최종 합성 - 입력 누락 시 에러 처리"""
    mcp_server.api_client = mock_api_client

    # step1_image만 제공
    result = await mcp_server._handle_compose_final_image(
        {"step1_image_base64": "base64..."}
    )

    # 에러 메시지 확인
    assert len(result) == 1
    assert "에러" in result[0].text


@pytest.mark.asyncio
async def test_error_handling_image_processing(mcp_server, mock_api_client):
    """이미지 처리 에러 핸들링 테스트"""
    mcp_server.api_client = mock_api_client

    # 존재하지 않는 이미지 파일
    result = await mcp_server._handle_generate_ad_image(
        {
            "product_image_path": "/nonexistent/image.png",
            "background_prompt": "Test",
            "text_content": "TEST",
            "text_style_prompt": "Style",
            "wait_for_completion": False,
        }
    )

    # 에러 메시지 확인
    assert len(result) == 1
    assert "이미지 처리 에러" in result[0].text


@pytest.mark.asyncio
async def test_error_handling_aiserver_error(
    mcp_server, mock_api_client, temp_product_image
):
    """AI 서버 에러 핸들링 테스트"""
    # Mock이 에러 발생하도록 설정
    mock_api_client.start_generation.side_effect = AIServerError(
        "서버 에러", status_code=503, retry_after=10, detail="서버가 사용 중입니다"
    )
    mcp_server.api_client = mock_api_client

    # 핸들러 호출
    result = await mcp_server._handle_generate_ad_image(
        {
            "product_image_path": temp_product_image,
            "background_prompt": "Test",
            "text_content": "TEST",
            "text_style_prompt": "Style",
            "wait_for_completion": False,
        }
    )

    # 에러 메시지 확인
    assert len(result) == 1
    assert "AI 서버 에러" in result[0].text
    assert "10초 후 재시도" in result[0].text


@pytest.mark.asyncio
async def test_mcp_tools_registration(mcp_server):
    """MCP 도구 등록 확인 테스트"""
    # 서버가 도구를 등록했는지 확인
    assert mcp_server.server is not None

    # 도구 개수는 schemas/mcp_tools.py의 MCP_TOOLS 개수와 일치해야 함
    from nanoCocoa_mcpserver.schemas.mcp_tools import MCP_TOOLS

    expected_tool_count = len(MCP_TOOLS)

    # 실제로는 server.list_tools() 핸들러를 통해 확인하지만,
    # 여기서는 간단히 도구 이름만 확인
    from nanoCocoa_mcpserver.schemas.mcp_tools import get_all_tool_names

    tool_names = get_all_tool_names()

    assert len(tool_names) == expected_tool_count
    assert "generate_ad_image" in tool_names
    assert "check_generation_status" in tool_names
    assert "list_available_fonts" in tool_names
