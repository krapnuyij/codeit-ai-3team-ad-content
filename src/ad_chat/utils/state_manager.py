"""
유틸리티: Session State 관리

Streamlit Session State 초기화 및 공통 로직
"""

import streamlit as st
from typing import Any, Optional


def init_session_state() -> None:
    """
    Session State 초기화

    앱 시작 시 필요한 모든 상태 변수를 초기화합니다.
    """
    # OpenAI API 키
    if "openai_key" not in st.session_state:
        st.session_state.openai_key = None

    # 인증 완료 여부
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    # 현재 페이지
    if "current_page" not in st.session_state:
        st.session_state.current_page = "auth"  # auth, chat, history

    # 채팅 히스토리
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # 현재 선택된 작업 ID
    if "selected_job_id" not in st.session_state:
        st.session_state.selected_job_id = None

    # 자동 갱신 활성화 여부
    if "auto_refresh_enabled" not in st.session_state:
        st.session_state.auto_refresh_enabled = False


def set_page(page_name: str) -> None:
    """
    페이지 전환

    Args:
        page_name: 전환할 페이지 이름 (auth/chat/history)
    """
    st.session_state.current_page = page_name


def get_page() -> str:
    """
    현재 페이지 반환

    Returns:
        현재 페이지 이름
    """
    return st.session_state.get("current_page", "auth")


def is_authenticated() -> bool:
    """
    인증 상태 확인

    Returns:
        인증 완료 여부
    """
    return (
        st.session_state.get("authenticated", False)
        and st.session_state.get("openai_key") is not None
    )


def set_authenticated(api_key: str) -> None:
    """
    인증 완료 처리

    Args:
        api_key: OpenAI API 키
    """
    st.session_state.openai_key = api_key
    st.session_state.authenticated = True
    st.session_state.current_page = "chat"


def add_chat_message(role: str, content: str) -> None:
    """
    채팅 메시지 추가

    Args:
        role: 메시지 역할 (user/assistant/system)
        content: 메시지 내용
    """
    st.session_state.chat_history.append({"role": role, "content": content})


def clear_chat_history() -> None:
    """채팅 히스토리 초기화"""
    st.session_state.chat_history = []


def get_session_value(key: str, default: Any = None) -> Any:
    """
    Session State 값 조회

    Args:
        key: 키 이름
        default: 기본값

    Returns:
        저장된 값 또는 기본값
    """
    return st.session_state.get(key, default)


def set_session_value(key: str, value: Any) -> None:
    """
    Session State 값 설정

    Args:
        key: 키 이름
        value: 저장할 값
    """
    st.session_state[key] = value
