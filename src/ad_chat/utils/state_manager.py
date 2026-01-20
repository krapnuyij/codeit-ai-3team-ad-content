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

    # 폰트 메타데이터 (1회만 로드)
    if "font_metadata" not in st.session_state:
        st.session_state.font_metadata = None

    # 광고 생성 대기 상태 (최종 확인 대기 중인 광고 파라미터)
    if "pending_ad_generation" not in st.session_state:
        st.session_state.pending_ad_generation = None

    # 현재 작업 컨텍스트 (작업 ID별 대화 추적)
    if "current_job_context" not in st.session_state:
        st.session_state.current_job_context = None


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


def logout() -> None:
    """
    로그아웃 처리 (인증 상태만 초기화)
    """
    st.session_state.authenticated = False
    st.session_state.current_page = "auth"
    # openai_key는 유지 (재로그인 시 재사용 가능)
    # 채팅 히스토리 등은 유지


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


def load_job_to_chat(job: dict) -> None:
    """
    히스토리 작업을 채팅에 불러오기

    LLM이 이해할 수 있는 형식으로 저장된 파라미터를 채팅 히스토리에 추가

    Args:
        job: 불러올 작업 데이터
    """
    metadata = job.get("metadata", {})
    user_message = metadata.get("user_message", job.get("prompt", ""))

    # LLM이 이해할 수 있는 형식으로 변환
    formatted_context = f"""이전 작업을 불러왔습니다:

**원본 요청:** {user_message}

**사용된 파라미터:**
- 텍스트 내용: {metadata.get('text_content', 'N/A')}
- 배경 프롬프트: {metadata.get('background_prompt', 'N/A')[:100]}...
- 텍스트 스타일 프롬프트: {metadata.get('text_prompt', 'N/A')[:100]}...
- 합성 모드: {metadata.get('composition_mode', 'overlay')}
- 강도: {metadata.get('strength', 0.35)}
- 가이드 스케일: {metadata.get('guidance_scale', 4.5)}

이 설정을 기반으로 수정하고 싶은 부분을 말씀해주세요.
(예: "글자 색을 빨간색으로 해주세요", "배경을 더 밝게 해주세요")
"""

    # 채팅 히스토리에 추가
    st.session_state.chat_history.append(
        {
            "role": "assistant",
            "content": formatted_context,
        }
    )

    # 현재 불러온 작업 ID 저장 (참조용)
    st.session_state.loaded_job_id = job.get("job_id")
    st.session_state.loaded_job_metadata = metadata


def reset_for_new_ad() -> None:
    """
    새로운 광고 생성을 위한 초기화

    채팅 히스토리, 작업 컨텍스트, 모니터링 작업 목록 초기화
    """
    st.session_state.chat_history = []
    st.session_state.current_job_context = None
    st.session_state.pending_ad_generation = None
    st.session_state.selected_job_id = None

    # 모니터링 작업 목록 초기화
    if "monitoring_jobs" in st.session_state:
        st.session_state.monitoring_jobs = []

    # 불러온 작업 정보 초기화
    if "loaded_job_id" in st.session_state:
        del st.session_state.loaded_job_id
    if "loaded_job_metadata" in st.session_state:
        del st.session_state.loaded_job_metadata
