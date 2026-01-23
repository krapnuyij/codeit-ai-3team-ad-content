"""
UI 컴포넌트: 이미지-텍스트 CLIP 유사도 평가 페이지

업로드된 이미지와 사용자 제공 프롬프트의 CLIP 유사도를 평가하는 독립 페이지
"""

import streamlit as st
import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from helper_streamlit_utils import *

from config import (
    MCP_SERVER_URL,
    MCP_TIMEOUT,
    UPLOADS_DIR,
    CLIP_MODEL_AUTO,
    CLIP_MODEL_KOCLIP,
    CLIP_MODEL_OPENAI,
    CLIP_SCORE_EXCELLENT,
    CLIP_SCORE_GOOD,
    CLIP_SCORE_FAIR,
)
from services import MCPClient
from utils.state_manager import set_page, logout

logger = logging.getLogger(__name__)


def interpret_clip_score(score: float) -> tuple[str, str]:
    """
    CLIP 점수 해석

    Args:
        score: CLIP 유사도 점수 (0.0~1.0)

    Returns:
        (평가 등급, 설명 메시지)
    """
    if score >= CLIP_SCORE_EXCELLENT:
        return "🌟 매우 높은 일치도", "이미지와 프롬프트가 매우 잘 매칭됩니다."
    elif score >= CLIP_SCORE_GOOD:
        return "✅ 높은 일치도", "이미지와 프롬프트가 잘 매칭됩니다."
    elif score >= CLIP_SCORE_FAIR:
        return "⚠️ 중간 일치도", "이미지와 프롬프트에 어느 정도 관련성이 있습니다."
    else:
        return "❌ 낮은 일치도", "이미지와 프롬프트가 잘 맞지 않습니다."


async def evaluate_image_clip_async(
    image_path: str, prompt: str, model_type: str = CLIP_MODEL_AUTO
) -> Optional[Dict[str, Any]]:
    """
    MCP 서버를 통해 CLIP 평가 수행

    Args:
        image_path: 이미지 파일 경로
        prompt: 평가용 텍스트 프롬프트
        model_type: CLIP 모델 타입 ("auto", "koclip", "openai")

    Returns:
        평가 결과 딕셔너리 또는 None (실패 시)
    """
    try:
        logger.info(
            f"CLIP 평가 시작: {image_path}, prompt='{prompt}', model={model_type}"
        )

        async with MCPClient(base_url=MCP_SERVER_URL, timeout=MCP_TIMEOUT) as client:
            result = await client.call_tool(
                "evaluate_image_clip",
                {
                    "image_path": image_path,
                    "prompt": prompt,
                    "model_type": model_type,
                },
            )

        # 결과 파싱
        if isinstance(result, str):
            result_data = json.loads(result)
        else:
            result_data = result

        logger.info(f"CLIP 평가 완료: {result_data}")
        return result_data

    except Exception as e:
        logger.error(f"CLIP 평가 실패: {e}", exc_info=True)
        return None


def render_evaluate_ui() -> None:
    """
    CLIP 평가 전용 UI 렌더링
    """
    # 상단 메뉴
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    with col1:
        st.subheader("📊 이미지-텍스트 유사도 평가")

    with col2:
        if st.button("💬 채팅", width="stretch"):
            set_page("chat")
            st.rerun()

    with col3:
        if st.button("📁 히스토리", width="stretch"):
            set_page("history")
            st.rerun()

    with col4:
        if st.button("🚪 로그아웃", width="stretch"):
            logout()
            st.rerun()

    st_div_divider()

    # 설명 섹션
    with st.expander("ℹ️ CLIP 평가란?", expanded=False):
        st.markdown(
            """
**CLIP (Contrastive Language-Image Pre-training) 유사도 평가**는
이미지와 텍스트 프롬프트가 얼마나 잘 매칭되는지를 0.0~1.0 점수로 평가합니다.

**점수 해석:**
- **0.7 이상**: 🌟 매우 높은 일치도 - 완벽한 매칭
- **0.5~0.7**: ✅ 높은 일치도 - 잘 매칭됨
- **0.3~0.5**: ⚠️ 중간 일치도 - 어느 정도 관련성
- **0.3 미만**: ❌ 낮은 일치도 - 매칭 안 됨

**모델 선택:**
- **auto** (권장): 한글 포함 시 KoCLIP, 영문만 있으면 OpenAI CLIP 자동 선택
- **koclip**: 한국어 특화 모델 (한글 프롬프트에 최적)
- **openai**: OpenAI CLIP (영문 프롬프트에 최적)

**사용 예시:**
- 생성된 광고 이미지가 프롬프트와 얼마나 일치하는지 평가
- 제품 이미지가 광고 컨셉과 맞는지 검증
- 다양한 프롬프트로 이미지의 특성 분석
"""
        )

    st_div_divider()

    # 이미지 업로드 섹션
    st.markdown("### 1️⃣ 이미지 업로드")
    uploaded_file = st.file_uploader(
        "평가할 이미지를 업로드하세요 (PNG, JPG, JPEG)",
        type=["png", "jpg", "jpeg"],
        key="evaluate_image_uploader",
    )

    image_path = None

    if uploaded_file is not None:
        # 업로드된 파일 저장
        upload_path = UPLOADS_DIR / uploaded_file.name
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

        with open(upload_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        image_path = str(upload_path)

        # 미리보기
        col1, col2 = st.columns([1, 2])
        with col1:
            st.image(uploaded_file, caption=uploaded_file.name, width="stretch")
        with col2:
            st.success(f"✅ 업로드 완료: `{uploaded_file.name}`")
            st.info(f"📍 저장 경로: `{upload_path}`")

    st_div_divider()

    # 프롬프트 입력 섹션
    st.markdown("### 2️⃣ 평가용 프롬프트 입력")

    col1, col2 = st.columns([3, 1])

    with col1:
        prompt = st.text_area(
            "이미지와 비교할 텍스트 프롬프트를 입력하세요",
            placeholder="예: 신선한 바나나 광고\n예: premium red apple on traditional Korean cloth\n예: 명절 선물 사과",
            height=100,
            help="한글 또는 영문으로 입력 가능합니다. 'auto' 모델은 자동으로 적절한 모델을 선택합니다.",
        )

    with col2:
        model_type = st.selectbox(
            "CLIP 모델",
            options=[CLIP_MODEL_AUTO, CLIP_MODEL_KOCLIP, CLIP_MODEL_OPENAI],
            index=0,
            help="auto: 자동 선택 (권장)\nkoclip: 한국어 특화\nopenai: 영문 특화",
        )

    st_div_divider()

    # 평가 버튼 및 결과 표시
    st.markdown("### 3️⃣ 평가 실행")

    if not image_path:
        st.warning("⚠️ 먼저 이미지를 업로드하세요.")
    elif not prompt or not prompt.strip():
        st.warning("⚠️ 프롬프트를 입력하세요.")
    else:
        if st.button("🚀 CLIP 평가 시작", type="primary", width="stretch"):
            with st.spinner("평가 중... (10~30초 소요)"):
                result = asyncio.run(
                    evaluate_image_clip_async(image_path, prompt.strip(), model_type)
                )

            if result:
                # 성공 - 결과 표시
                clip_score = result.get("clip_score", 0.0)
                used_model = result.get("model_type", model_type)
                interpretation = result.get("interpretation", "")

                # 점수 해석
                grade, description = interpret_clip_score(clip_score)

                st.success("✅ 평가 완료!")

                # 결과 카드
                st.markdown("---")
                st.markdown("### 📈 평가 결과")

                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("CLIP 점수", f"{clip_score:.4f}")

                with col2:
                    st.metric("평가 등급", grade)

                with col3:
                    st.metric("사용 모델", used_model.upper())

                st.info(f"**해석:** {description}")

                if interpretation:
                    with st.expander("🔍 상세 분석", expanded=True):
                        st.markdown(interpretation)

                # 재평가 버튼
                st.markdown("---")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🔄 다른 프롬프트로 재평가", width="stretch"):
                        st.rerun()
                with col2:
                    if st.button("📤 새 이미지 업로드", width="stretch"):
                        st.rerun()

            else:
                # 실패
                st.error(
                    "❌ 평가 중 오류가 발생했습니다. 다시 시도하거나 관리자에게 문의하세요."
                )
