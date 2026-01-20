"""
mcpadapter 통합 테스트
MCPClient와 LLMAdapter 기능 검증
"""

import pytest
import asyncio
import os
import sys
import logging
from pathlib import Path
from tqdm import tqdm

from mcpadapter import MCPClient, LLMAdapter


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mcp_server_url():
    """MCP 서버 URL"""
    return "http://localhost:3000"


@pytest.fixture
def openai_api_key():
    """OpenAI API 키 (환경변수에서 로드)"""
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        pytest.skip("OPENAI_API_KEY 환경변수가 설정되지 않았습니다")
    return api_key


# =============================================================================
# 테스트: MCPClient
# =============================================================================


@pytest.mark.asyncio
async def test_mcp_client_basic(mcp_server_url):
    """MCPClient 기본 동작"""
    async with MCPClient(base_url=mcp_server_url, timeout=10) as client:
        # 도구 목록 조회
        tools = await client.list_tools()
        assert len(tools) > 0

        # 서버 헬스체크
        result = await client.call_tool("check_server_health", {})
        assert result is not None


@pytest.mark.asyncio
async def test_mcp_client_context_manager(mcp_server_url):
    """MCPClient context manager 패턴"""
    async with MCPClient(base_url=mcp_server_url) as client:
        result = await client.call_tool("list_available_fonts", {})
        assert "폰트" in result


@pytest.mark.asyncio
async def test_mcp_client_manual_close(mcp_server_url):
    """MCPClient 수동 종료"""
    client = MCPClient(base_url=mcp_server_url)

    try:
        result = await client.call_tool("check_server_health", {})
        assert result is not None
    finally:
        await client.close()


# =============================================================================
# 테스트: LLMAdapter
# =============================================================================


@pytest.mark.asyncio
async def test_llm_adapter_basic(mcp_server_url, openai_api_key):
    """LLMAdapter 기본 동작"""
    async with LLMAdapter(
        openai_api_key=openai_api_key,
        mcp_server_url=mcp_server_url,
        model="gpt-5-mini",
    ) as adapter:
        response = await adapter.chat("서버 상태를 확인해줘")

        assert response is not None
        assert len(response) > 0


@pytest.mark.asyncio
async def test_llm_adapter_font_query(mcp_server_url, openai_api_key):
    """LLMAdapter 자연어 쿼리 - 폰트 목록"""
    async with LLMAdapter(
        openai_api_key=openai_api_key,
        mcp_server_url=mcp_server_url,
        model="gpt-5-mini",
    ) as adapter:
        response = await adapter.chat("사용 가능한 폰트 목록을 알려줘")

        assert response is not None
        assert "폰트" in response or "font" in response.lower()


@pytest.mark.asyncio
async def test_llm_adapter_multi_turn(mcp_server_url, openai_api_key):
    """LLMAdapter 다중 턴 대화"""
    async with LLMAdapter(
        openai_api_key=openai_api_key,
        mcp_server_url=mcp_server_url,
        model="gpt-5-mini",
    ) as adapter:
        # 첫 번째 질문
        response1 = await adapter.chat("서버가 정상인지 확인해줘")
        assert response1 is not None

        # 두 번째 질문 (컨텍스트 유지)
        response2 = await adapter.chat("그럼 폰트 목록도 알려줘")
        assert response2 is not None


# =============================================================================
# 테스트: 에러 처리
# =============================================================================


@pytest.mark.asyncio
async def test_mcp_client_connection_error():
    """MCPClient 연결 에러"""
    client = MCPClient(base_url="http://localhost:9999", timeout=3)

    with pytest.raises(Exception):
        await client.call_tool("check_server_health", {})

    await client.close()


@pytest.mark.asyncio
async def test_mcp_client_invalid_tool(mcp_server_url):
    """MCPClient 존재하지 않는 도구 호출"""
    async with MCPClient(base_url=mcp_server_url) as client:
        with pytest.raises(Exception):
            await client.call_tool("nonexistent_tool", {})


@pytest.mark.asyncio
async def test_llm_adapter_invalid_api_key(mcp_server_url):
    """LLMAdapter 잘못된 API 키"""
    with pytest.raises(Exception):
        async with LLMAdapter(
            openai_api_key="invalid-key",
            mcp_server_url=mcp_server_url,
            model="gpt-5-mini",
        ) as adapter:
            await adapter.chat("테스트")


# =============================================================================
# 테스트: 성능
# =============================================================================


@pytest.mark.asyncio
async def test_mcp_client_response_time(mcp_server_url):
    """MCPClient 응답 시간 측정"""
    import time

    async with MCPClient(base_url=mcp_server_url) as client:
        start = time.time()
        await client.call_tool("check_server_health", {})
        elapsed = time.time() - start

        # 헬스체크는 1초 이내에 완료되어야 함
        assert elapsed < 1.0


@pytest.mark.asyncio
async def test_mcp_client_concurrent_calls(mcp_server_url):
    """MCPClient 동시 호출"""
    from tqdm import tqdm
    import logging

    logger = logging.getLogger(__name__)
    logger.info("동시 호출 테스트 시작 - 5개 요청 처리 중...")

    async with MCPClient(base_url=mcp_server_url) as client:
        tasks = [client.call_tool("check_server_health", {}) for _ in range(5)]

        # tqdm으로 진행상황 표시
        with tqdm(total=len(tasks), desc="동시 호출", unit="req") as pbar:
            completed_results = []
            for coro in asyncio.as_completed(tasks):
                result = await coro
                completed_results.append(result)
                pbar.update(1)

            results = completed_results

        assert len(results) == 5
        for result in results:
            assert result is not None

        logger.info(f"동시 호출 완료: {len(results)}/5 성공")


# =============================================================================
# 실행
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
