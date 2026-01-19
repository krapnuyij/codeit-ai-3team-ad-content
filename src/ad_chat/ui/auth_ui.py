"""
UI 컴포넌트: 인증 화면

OpenAI API 키 입력 및 검증
"""

import streamlit as st
from openai import OpenAI
from openai import OpenAIError

from config import OPENAI_API_KEY
from utils.state_manager import set_authenticated


def validate_openai_key(api_key: str) -> bool:
    """
    OpenAI API 키 유효성 검증

    Args:
        api_key: 검증할 API 키

    Returns:
        유효하면 True, 그렇지 않으면 False
    """
    try:
        client = OpenAI(api_key=api_key)
        # 간단한 API 호출로 키 검증
        client.models.list()
        return True
    except OpenAIError:
        return False


def render_auth_ui() -> None:
    """
    인증 화면 렌더링

    OpenAI API 키를 입력받고 검증 후 Session State에 저장
    """
    st.title("🎨 AI 광고 생성 시스템")
    st.markdown("---")

    # .env에서 키가 있으면 자동 로그인
    if OPENAI_API_KEY:
        with st.spinner("환경 변수에서 API 키를 확인하는 중..."):
            if validate_openai_key(OPENAI_API_KEY):
                st.success("환경 변수에서 API 키를 불러왔습니다!")
                set_authenticated(OPENAI_API_KEY)
                st.rerun()
            else:
                st.error(
                    ".env의 OPENAI_API_KEY가 유효하지 않습니다. 수동으로 입력해주세요."
                )

    st.header("🔑 시작하기")
    st.write("AI 광고 생성을 위해 OpenAI API 키를 입력해주세요.")

    # API 키 입력
    api_key_input = st.text_input(
        "OpenAI API Key",
        type="password",
        placeholder="sk-...",
        help="https://platform.openai.com/api-keys 에서 발급받으세요. (또는 .env 파일에 OPENAI_API_KEY 설정)",
    )

    # 로그인 버튼
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("시작하기", type="primary", width="content"):
            if not api_key_input:
                st.error("API 키를 입력해주세요.")
                return

            # 키 검증
            with st.spinner("API 키를 확인하는 중..."):
                if validate_openai_key(api_key_input):
                    st.success("인증 완료!")
                    set_authenticated(api_key_input)
                    st.rerun()
                else:
                    st.error("유효하지 않은 API 키입니다. 다시 확인해주세요.")

    # 안내 메시지
    st.markdown("---")
    st.info(
        """
    **주요 기능:**
    - 💬 자연어로 광고 컨셉 논의
    - 🎨 AI 기반 이미지 + 텍스트 광고 생성
    - 📊 작업 진행 상황 실시간 모니터링
    - 📁 과거 작업 히스토리 조회
    """
    )

    st.warning(
        """
    **참고사항:**
    - 광고 생성은 15~30분 정도 소요됩니다.
    - 작업을 요청한 후 다른 작업을 진행하셔도 됩니다.
    - 히스토리 페이지에서 진행 상황을 확인하세요.
    """
    )
