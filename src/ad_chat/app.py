"""
AI 광고 생성 시스템 - 메인 애플리케이션

Streamlit 기반 웹 애플리케이션
- OpenAI API를 통한 대화형 광고 기획
- MCP 서버로 장시간 소요 작업 요청 (Fire-and-Forget)
- MongoDB를 통한 작업 상태 및 히스토리 관리
- 폴링 기반 진행 상황 모니터링

Architecture:
    app.py (Entry Point)
    ├── config.py (설정)
    ├── services/
    │   ├── mcp_client.py (MCP 서버 통신)
    │   └── simple_job_store.py  # SimpleJobStore
    ├── ui/
    │   ├── auth_ui.py (인증 화면)
    │   ├── chat_ui.py (채팅 인터페이스)
    │   └── history_ui.py (작업 히스토리)
    └── utils/
        └── state_manager.py (Session State 관리)
"""

import asyncio
import streamlit as st
from helper_streamlit_utils import *
from helper_dev_utils import get_auto_logger
from config import PAGE_TITLE, PAGE_ICON, LAYOUT, MCP_SERVER_URL
from utils.state_manager import init_session_state, is_authenticated, get_page
from ui import render_auth_ui, render_chat_ui, render_history_ui

logger = get_auto_logger()


async def wait_for_mcp_server(max_wait: int = 30) -> bool:
    """
    MCP 서버가 준비될 때까지 대기

    Args:
        max_wait: 최대 대기 시간(초)

    Returns:
        bool: 서버 준비 완료 여부
    """
    from mcpadapter.mcp_client import MCPClient
    import time

    start = time.time()
    logger.info(f"MCP 서버 준비 대기 시작: {MCP_SERVER_URL}")

    while time.time() - start < max_wait:
        try:
            async with MCPClient(base_url=MCP_SERVER_URL, timeout=5) as client:
                await client.list_tools()
                elapsed = time.time() - start
                logger.info(f"MCP 서버 준비 완료 ({elapsed:.1f}초)")
                return True
        except Exception as e:
            logger.debug(f"MCP 서버 대기 중... ({time.time() - start:.1f}초)")
            await asyncio.sleep(1)

    logger.error(f"MCP 서버 대기 시간 초과 ({max_wait}초)")
    return False


def main() -> None:
    """메인 애플리케이션 진입점"""

    # Streamlit 페이지 설정
    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon=PAGE_ICON,
        layout=LAYOUT,
        initial_sidebar_state="collapsed",
    )

    st_style_page_margin_hidden()

    # MCP 서버 준비 대기
    if "mcp_ready" not in st.session_state:
        with st.spinner("MCP 서버 연결 대기 중..."):
            st.session_state.mcp_ready = asyncio.run(wait_for_mcp_server())
            if not st.session_state.mcp_ready:
                st.error("MCP 서버 연결 실패. 관리자에게 문의하세요.")
                st.stop()

    # Session State 초기화
    init_session_state()

    # 라우팅 로직
    if not is_authenticated():
        # 인증되지 않은 경우: 인증 화면
        render_auth_ui()
    else:
        # 인증된 경우: 현재 페이지에 따라 렌더링
        current_page = get_page()

        if current_page == "chat":
            render_chat_ui()
        elif current_page == "history":
            render_history_ui()
        else:
            # 기본값: 채팅 화면
            render_chat_ui()


if __name__ == "__main__":
    main()
