"""
nanoCocoa MCP Server 통합 테스트 (Docker 환경)
aiserver와 mcpserver가 Docker로 실행 중일 때 테스트
"""

import pytest
import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.mcpadapter import MCPClient


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mcp_server_url():
    """MCP 서버 URL (Docker 컨테이너)"""
    return "http://localhost:3000"


@pytest.fixture
async def mcp_client(mcp_server_url):
    """MCP 클라이언트 fixture"""
    client = MCPClient(base_url=mcp_server_url, timeout=600)
    yield client
    await client.close()


# =============================================================================
# 테스트: MCP 서버 기본 동작
# =============================================================================


@pytest.mark.asyncio
async def test_mcp_server_health(mcp_client, require_docker_server):
    """MCP 서버 헬스체크"""
    result = await mcp_client.call_tool("check_server_health", {})

    assert result is not None
    assert "서버 상태" in result
    assert "healthy" in result.lower()


@pytest.mark.asyncio
async def test_list_fonts(mcp_client, require_docker_server):
    """폰트 목록 조회"""
    result = await mcp_client.call_tool("list_available_fonts", {})

    assert result is not None
    assert "폰트" in result
    assert "개" in result  # "N개" 형식


# =============================================================================
# 테스트: 광고 생성 (test_mode)
# =============================================================================


@pytest.mark.asyncio
async def test_generate_ad_test_mode(mcp_client, tmp_path, require_docker_server):
    """광고 생성 - test_mode (더미 데이터)"""
    output_path = tmp_path / "test_ad.png"

    result = await mcp_client.call_tool(
        "generate_ad_image",
        {
            "product_image_path": str(project_root / "tests" / "banana.png"),
            "background_prompt": "Colorful party background",
            "text_content": "SALE",
            "text_style_prompt": "3D gold text",
            "test_mode": True,
            "wait_for_completion": True,
            "save_output_path": str(output_path),
        },
    )

    assert result is not None
    assert "완료" in result
    assert "작업 ID" in result
    assert output_path.exists()


@pytest.mark.asyncio
async def test_generate_ad_async(mcp_client, require_docker_server):
    """광고 생성 - 비동기 모드"""
    result = await mcp_client.call_tool(
        "generate_ad_image",
        {
            "product_image_path": str(project_root / "tests" / "banana.png"),
            "background_prompt": "Modern studio background",
            "text_content": "NEW",
            "text_style_prompt": "Bold 3D text",
            "test_mode": True,
            "wait_for_completion": False,
        },
    )

    assert result is not None
    assert "작업 시작" in result or "작업 ID" in result


# =============================================================================
# 테스트: 단계별 생성
# =============================================================================


@pytest.mark.asyncio
async def test_step_by_step_generation(mcp_client, tmp_path, require_docker_server):
    """단계별 광고 생성 (Step 1 → 2 → 3)"""

    # Step 1: 배경 생성
    step1_path = tmp_path / "step1_bg.png"
    result1 = await mcp_client.call_tool(
        "generate_background_only",
        {
            "product_image_path": str(project_root / "tests" / "banana.png"),
            "background_prompt": "Luxury gold background",
            "test_mode": True,
            "wait_for_completion": True,
            "save_output_path": str(step1_path),
        },
    )

    assert "배경 생성 완료" in result1
    assert step1_path.exists()

    # Step 2: 텍스트 생성
    step2_path = tmp_path / "step2_text.png"
    result2 = await mcp_client.call_tool(
        "generate_text_asset_only",
        {
            "step1_image_path": str(step1_path),
            "text_content": "SALE",
            "text_style_prompt": "3D gold foil text",
            "test_mode": True,
            "wait_for_completion": True,
            "save_output_path": str(step2_path),
        },
    )

    assert "3D 텍스트 생성 완료" in result2
    assert step2_path.exists()

    # Step 3: 최종 합성
    final_path = tmp_path / "final.png"
    result3 = await mcp_client.call_tool(
        "compose_final_image",
        {
            "step1_image_path": str(step1_path),
            "step2_image_path": str(step2_path),
            "composition_mode": "overlay",
            "test_mode": True,
            "wait_for_completion": True,
            "save_output_path": str(final_path),
        },
    )

    assert "최종 합성 완료" in result3
    assert final_path.exists()


# =============================================================================
# 테스트: 에러 처리
# =============================================================================


@pytest.mark.asyncio
async def test_invalid_image_path(mcp_client, require_docker_server):
    """존재하지 않는 이미지 경로 에러 처리"""
    result = await mcp_client.call_tool(
        "generate_ad_image",
        {
            "product_image_path": "/nonexistent/image.png",
            "background_prompt": "Test background",
            "text_content": "TEST",
            "text_style_prompt": "Test text",
            "test_mode": True,
        },
    )

    assert "에러" in result or "실패" in result


@pytest.mark.asyncio
async def test_missing_required_params(mcp_client, require_docker_server):
    """필수 파라미터 누락 에러"""
    with pytest.raises(Exception):
        await mcp_client.call_tool(
            "generate_ad_image",
            {
                "product_image_path": str(project_root / "tests" / "banana.png"),
                # background_prompt 누락
                "text_content": "TEST",
                "text_style_prompt": "Test text",
            },
        )


# =============================================================================
# 테스트: 동시 요청 처리
# =============================================================================


@pytest.mark.asyncio
async def test_concurrent_requests(mcp_client, require_docker_server):
    """동시 요청 처리"""
    tasks = []

    for i in range(3):
        task = mcp_client.call_tool(
            "generate_ad_image",
            {
                "product_image_path": str(project_root / "tests" / "banana.png"),
                "background_prompt": f"Background {i}",
                "text_content": f"TEXT {i}",
                "text_style_prompt": "3D text",
                "test_mode": True,
                "wait_for_completion": False,
            },
        )
        tasks.append(task)

    results = await asyncio.gather(*tasks)

    assert len(results) == 3
    for result in results:
        assert result is not None


# =============================================================================
# 실행
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
