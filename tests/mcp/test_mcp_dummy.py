"""
test_mcp_dummy.py
Dummy MCP Interface Tests (No actual MCP server required)

이 테스트는 MCP 서버 없이 인터페이스를 검증합니다.
실제 API 호출 대신 Mock을 사용하여 MCP 서버의 동작을 시뮬레이션합니다.
"""

import pytest
import json
import base64
from unittest.mock import Mock, AsyncMock, patch
import sys
from pathlib import Path

# MCP 서버 모듈 임포트를 위한 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src" / "nanoCocoa_aiserver"))


class TestMCPServerDummy:
    """MCP 서버 더미 테스트"""

    @pytest.fixture
    def mock_httpx_client(self):
        """Mock HTTP client"""
        client = AsyncMock()
        return client

    @pytest.fixture
    def server_instance(self, mock_httpx_client):
        """MCP 서버 인스턴스 (mock HTTP client 사용)"""
        from mcp_server import NanoCocoaMCPServer

        server = NanoCocoaMCPServer(api_base_url="http://localhost:8000")
        server.client = mock_httpx_client
        return server

    @pytest.mark.asyncio
    async def test_list_tools(self, server_instance):
        """도구 목록 조회 테스트"""
        tools = await server_instance.list_tools()

        assert len(tools) == 8, "8개의 도구가 있어야 합니다"

        tool_names = [tool.name for tool in tools]
        expected_tools = [
            "health_check",
            "list_fonts",
            "generate_ad",
            "check_job_status",
            "stop_job",
            "list_jobs",
            "delete_job",
            "generate_and_wait"
        ]

        for expected_tool in expected_tools:
            assert expected_tool in tool_names, f"{expected_tool} 도구가 없습니다"

    @pytest.mark.asyncio
    async def test_list_resources(self, server_instance):
        """리소스 목록 조회 테스트"""
        resources = await server_instance.list_resources()

        assert len(resources) == 3, "3개의 리소스가 있어야 합니다"

        resource_uris = [r.uri for r in resources]
        expected_uris = [
            "nanococoa://help/guide",
            "nanococoa://help/parameters",
            "nanococoa://help/examples"
        ]

        for expected_uri in expected_uris:
            assert expected_uri in resource_uris, f"{expected_uri} 리소스가 없습니다"

    @pytest.mark.asyncio
    async def test_health_check_tool(self, server_instance, mock_httpx_client):
        """health_check 도구 테스트"""
        # Mock 응답 설정
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "healthy",
            "server_time": 1234567890.0,
            "total_jobs": 0,
            "active_jobs": 0,
            "system_metrics": {
                "cpu_percent": 25.5,
                "ram_used_gb": 8.2,
                "ram_total_gb": 16.0,
                "ram_percent": 51.2,
                "gpu_info": []
            }
        }
        mock_response.raise_for_status = Mock()
        mock_httpx_client.get.return_value = mock_response

        # 도구 호출
        result = await server_instance.call_tool("health_check", {})

        # 검증
        assert len(result) > 0
        assert result[0].type == "text"
        assert "healthy" in result[0].text

        # API 호출 검증
        mock_httpx_client.get.assert_called_once_with("http://localhost:8000/health")

    @pytest.mark.asyncio
    async def test_list_fonts_tool(self, server_instance, mock_httpx_client):
        """list_fonts 도구 테스트"""
        # Mock 응답 설정
        mock_response = Mock()
        mock_response.json.return_value = {
            "fonts": [
                "NanumGothic/NanumGothic.ttf",
                "NanumSquare/NanumSquareB.ttf"
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_httpx_client.get.return_value = mock_response

        # 도구 호출
        result = await server_instance.call_tool("list_fonts", {})

        # 검증
        assert len(result) > 0
        assert result[0].type == "text"
        assert "NanumGothic" in result[0].text

        # API 호출 검증
        mock_httpx_client.get.assert_called_once_with("http://localhost:8000/fonts")

    @pytest.mark.asyncio
    async def test_generate_ad_tool(self, server_instance, mock_httpx_client):
        """generate_ad 도구 테스트"""
        # Mock 응답 설정
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "job_id": "test-job-123",
            "status": "started"
        }
        mock_response.raise_for_status = Mock()
        mock_httpx_client.post.return_value = mock_response

        # 도구 호출
        arguments = {
            "input_image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ",
            "bg_prompt": "modern office",
            "text_content": "Test Ad"
        }
        result = await server_instance.call_tool("generate_ad", arguments)

        # 검증
        assert len(result) > 0
        assert result[0].type == "text"
        assert "test-job-123" in result[0].text
        assert "started" in result[0].text.lower()

        # API 호출 검증
        mock_httpx_client.post.assert_called_once()
        call_args = mock_httpx_client.post.call_args
        assert call_args[0][0] == "http://localhost:8000/generate"
        assert call_args[1]["json"] == arguments

    @pytest.mark.asyncio
    async def test_generate_ad_busy(self, server_instance, mock_httpx_client):
        """generate_ad 도구 - 서버 busy 테스트"""
        # Mock 응답 설정 (503 Busy)
        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.headers = {"Retry-After": "30"}
        mock_response.json.return_value = {
            "status": "busy",
            "message": "Server is busy",
            "retry_after": 30
        }
        mock_response.raise_for_status = Mock()
        mock_httpx_client.post.return_value = mock_response

        # 도구 호출
        arguments = {
            "input_image": "test_image",
            "bg_prompt": "test background"
        }
        result = await server_instance.call_tool("generate_ad", arguments)

        # 검증
        assert len(result) > 0
        assert "busy" in result[0].text.lower()
        assert "30" in result[0].text

    @pytest.mark.asyncio
    async def test_check_job_status_tool(self, server_instance, mock_httpx_client):
        """check_job_status 도구 테스트"""
        # Mock 응답 설정
        mock_response = Mock()
        mock_response.json.return_value = {
            "job_id": "test-job-123",
            "status": "running",
            "progress_percent": 45,
            "current_step": "step2_text",
            "message": "Generating 3D text...",
            "elapsed_sec": 50.5,
            "eta_seconds": 40
        }
        mock_response.raise_for_status = Mock()
        mock_httpx_client.get.return_value = mock_response

        # 도구 호출
        result = await server_instance.call_tool("check_job_status", {"job_id": "test-job-123"})

        # 검증
        assert len(result) > 0
        assert result[0].type == "text"
        assert "test-job-123" in result[0].text
        assert "45%" in result[0].text
        assert "running" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_check_job_status_completed(self, server_instance, mock_httpx_client):
        """check_job_status 도구 - 완료 테스트"""
        # Mock 응답 설정
        test_image_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
        mock_response = Mock()
        mock_response.json.return_value = {
            "job_id": "test-job-123",
            "status": "completed",
            "progress_percent": 100,
            "current_step": "step3_composite",
            "message": "Generation completed",
            "elapsed_sec": 120.0,
            "final_result": test_image_b64,
            "step1_result": test_image_b64,
            "step2_result": test_image_b64
        }
        mock_response.raise_for_status = Mock()
        mock_httpx_client.get.return_value = mock_response

        # 도구 호출
        result = await server_instance.call_tool("check_job_status", {"job_id": "test-job-123"})

        # 검증
        assert len(result) > 0
        assert "completed" in result[0].text.lower()
        assert "100%" in result[0].text
        assert "Final result available" in result[0].text

    @pytest.mark.asyncio
    async def test_stop_job_tool(self, server_instance, mock_httpx_client):
        """stop_job 도구 테스트"""
        # Mock 응답 설정
        mock_response = Mock()
        mock_response.json.return_value = {
            "job_id": "test-job-123",
            "status": "stopped"
        }
        mock_response.raise_for_status = Mock()
        mock_httpx_client.post.return_value = mock_response

        # 도구 호출
        result = await server_instance.call_tool("stop_job", {"job_id": "test-job-123"})

        # 검증
        assert len(result) > 0
        assert "stopped" in result[0].text.lower()

        # API 호출 검증
        mock_httpx_client.post.assert_called_once_with("http://localhost:8000/stop/test-job-123")

    @pytest.mark.asyncio
    async def test_list_jobs_tool(self, server_instance, mock_httpx_client):
        """list_jobs 도구 테스트"""
        # Mock 응답 설정
        mock_response = Mock()
        mock_response.json.return_value = {
            "total_jobs": 3,
            "active_jobs": 1,
            "completed_jobs": 2,
            "failed_jobs": 0,
            "jobs": [
                {"job_id": "job-1", "status": "running", "progress_percent": 50},
                {"job_id": "job-2", "status": "completed", "progress_percent": 100},
                {"job_id": "job-3", "status": "completed", "progress_percent": 100}
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_httpx_client.get.return_value = mock_response

        # 도구 호출
        result = await server_instance.call_tool("list_jobs", {})

        # 검증
        assert len(result) > 0
        assert "Total Jobs: 3" in result[0].text
        assert "Active Jobs: 1" in result[0].text
        assert "Completed Jobs: 2" in result[0].text

    @pytest.mark.asyncio
    async def test_delete_job_tool(self, server_instance, mock_httpx_client):
        """delete_job 도구 테스트"""
        # Mock 응답 설정
        mock_response = Mock()
        mock_response.json.return_value = {
            "job_id": "test-job-123",
            "status": "deleted",
            "message": "Job successfully deleted"
        }
        mock_response.raise_for_status = Mock()
        mock_httpx_client.delete.return_value = mock_response

        # 도구 호출
        result = await server_instance.call_tool("delete_job", {"job_id": "test-job-123"})

        # 검증
        assert len(result) > 0
        assert "deleted" in result[0].text.lower()

        # API 호출 검증
        mock_httpx_client.delete.assert_called_once_with("http://localhost:8000/jobs/test-job-123")

    @pytest.mark.asyncio
    async def test_read_resource(self, server_instance, mock_httpx_client):
        """리소스 읽기 테스트"""
        # Mock 응답 설정
        mock_response = Mock()
        mock_response.json.return_value = {
            "server_info": {"name": "nanoCocoa AI Ad Generator"},
            "quick_start": {"step1": "Check health"}
        }
        mock_response.raise_for_status = Mock()
        mock_httpx_client.get.return_value = mock_response

        # 리소스 읽기
        content = await server_instance.read_resource("nanococoa://help/guide")

        # 검증
        assert content is not None
        assert "nanoCocoa" in content

        # API 호출 검증
        mock_httpx_client.get.assert_called_once_with("http://localhost:8000/help")

    @pytest.mark.asyncio
    async def test_generate_and_wait_success(self, server_instance, mock_httpx_client):
        """generate_and_wait 도구 - 성공 테스트"""
        # Mock 응답 설정
        # 1. POST /generate
        mock_post_response = Mock()
        mock_post_response.status_code = 200
        mock_post_response.json.return_value = {
            "job_id": "test-job-123",
            "status": "started"
        }
        mock_post_response.raise_for_status = Mock()

        # 2. GET /status (첫 번째 - running)
        mock_status_running = Mock()
        mock_status_running.json.return_value = {
            "job_id": "test-job-123",
            "status": "running",
            "progress_percent": 50,
            "message": "Processing..."
        }
        mock_status_running.raise_for_status = Mock()

        # 3. GET /status (두 번째 - completed)
        test_image_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
        mock_status_completed = Mock()
        mock_status_completed.json.return_value = {
            "job_id": "test-job-123",
            "status": "completed",
            "progress_percent": 100,
            "message": "Completed",
            "final_result": test_image_b64,
            "step1_result": test_image_b64,
            "step2_result": test_image_b64
        }
        mock_status_completed.raise_for_status = Mock()

        # Mock client 설정
        mock_httpx_client.post.return_value = mock_post_response
        mock_httpx_client.get.side_effect = [mock_status_running, mock_status_completed]

        # 도구 호출
        arguments = {
            "input_image": "test_image",
            "bg_prompt": "test background",
            "text_content": "Test"
        }

        # asyncio.sleep을 mock
        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await server_instance.call_tool("generate_and_wait", arguments)

        # 검증
        assert len(result) > 0
        assert "Completed Successfully" in result[0].text
        assert "final_result" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_generate_and_wait_busy(self, server_instance, mock_httpx_client):
        """generate_and_wait 도구 - busy 테스트"""
        # Mock 응답 설정 (503)
        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.headers = {"Retry-After": "60"}
        mock_response.json.return_value = {
            "status": "busy",
            "message": "Server is busy"
        }
        mock_httpx_client.post.return_value = mock_response

        # 도구 호출
        arguments = {
            "input_image": "test",
            "bg_prompt": "test"
        }
        result = await server_instance.call_tool("generate_and_wait", arguments)

        # 검증
        assert len(result) > 0
        assert "busy" in result[0].text.lower()

    def test_tool_input_schemas(self, server_instance):
        """도구 입력 스키마 검증"""
        import asyncio
        tools = asyncio.run(server_instance.list_tools())

        # generate_ad 스키마 검증
        generate_ad = next(t for t in tools if t.name == "generate_ad")
        assert "input_image" in generate_ad.inputSchema["properties"]
        assert "bg_prompt" in generate_ad.inputSchema["properties"]
        assert "input_image" in generate_ad.inputSchema["required"]
        assert "bg_prompt" in generate_ad.inputSchema["required"]

        # check_job_status 스키마 검증
        check_status = next(t for t in tools if t.name == "check_job_status")
        assert "job_id" in check_status.inputSchema["properties"]
        assert "job_id" in check_status.inputSchema["required"]

    def test_resource_metadata(self, server_instance):
        """리소스 메타데이터 검증"""
        import asyncio
        resources = asyncio.run(server_instance.list_resources())

        for resource in resources:
            assert resource.uri.startswith("nanococoa://")
            assert resource.name is not None
            assert resource.mimeType == "application/json"
            assert resource.description is not None


class TestMCPWorkflows:
    """MCP 워크플로우 더미 테스트"""

    @pytest.fixture
    def server_with_mocks(self):
        """Mock이 설정된 서버"""
        from mcp_server import NanoCocoaMCPServer

        server = NanoCocoaMCPServer()
        server.client = AsyncMock()
        return server

    @pytest.mark.asyncio
    async def test_workflow_basic_generation(self, server_with_mocks):
        """기본 광고 생성 워크플로우"""
        server = server_with_mocks
        client = server.client

        # 1. Health check
        mock_health = Mock()
        mock_health.json.return_value = {"status": "healthy", "active_jobs": 0}
        mock_health.raise_for_status = Mock()
        client.get.return_value = mock_health

        health_result = await server.call_tool("health_check", {})
        assert "healthy" in health_result[0].text

        # 2. List fonts
        mock_fonts = Mock()
        mock_fonts.json.return_value = {"fonts": ["NanumGothic/NanumGothic.ttf"]}
        mock_fonts.raise_for_status = Mock()
        client.get.return_value = mock_fonts

        fonts_result = await server.call_tool("list_fonts", {})
        assert "NanumGothic" in fonts_result[0].text

        # 3. Generate ad
        mock_generate = Mock()
        mock_generate.status_code = 200
        mock_generate.json.return_value = {"job_id": "abc-123", "status": "started"}
        mock_generate.raise_for_status = Mock()
        client.post.return_value = mock_generate

        gen_result = await server.call_tool("generate_ad", {
            "input_image": "test",
            "bg_prompt": "luxury background",
            "text_content": "Sale"
        })
        assert "abc-123" in gen_result[0].text

    @pytest.mark.asyncio
    async def test_workflow_retry_text(self, server_with_mocks):
        """텍스트 재생성 워크플로우"""
        server = server_with_mocks
        client = server.client

        # 1. 이전 작업 상태 조회
        mock_status = Mock()
        mock_status.json.return_value = {
            "job_id": "prev-job",
            "status": "completed",
            "step1_result": "base64_background_image"
        }
        mock_status.raise_for_status = Mock()
        client.get.return_value = mock_status

        status_result = await server.call_tool("check_job_status", {"job_id": "prev-job"})
        assert "completed" in status_result[0].text.lower()

        # 2. Step 2부터 새로 생성
        mock_generate = Mock()
        mock_generate.status_code = 200
        mock_generate.json.return_value = {"job_id": "new-job", "status": "started"}
        mock_generate.raise_for_status = Mock()
        client.post.return_value = mock_generate

        gen_result = await server.call_tool("generate_ad", {
            "start_step": 2,
            "step1_image": "base64_background_image",
            "text_content": "New Text",
            "text_model_prompt": "gold metallic"
        })
        assert "new-job" in gen_result[0].text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
