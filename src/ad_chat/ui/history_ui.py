"""
UI 컴포넌트: 작업 히스토리 및 상태 조회

MongoDB에 저장된 작업 목록 표시, 진행률 모니터링, 결과 조회
"""

import streamlit as st
import time
import asyncio
from datetime import datetime
from PIL import Image
from pathlib import Path
from helper_streamlit_utils import *

from config import STATUS_PROCESSING, STATUS_COMPLETED, STATUS_FAILED, POLLING_INTERVAL
from services import MCPClient, MongoManager, get_job_store
from utils.state_manager import (
    set_page,
    get_session_value,
    set_session_value,
    load_job_to_chat,
)

# 작업 저장소
job_store = get_job_store()


def render_history_ui() -> None:
    """
    작업 히스토리 화면 렌더링

    작업 목록, 진행률, 결과 표시
    """

    # 상단 메뉴
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        st.subheader("📁 작업 히스토리")

    with col2:
        if st.button("💬 채팅", width="content"):
            set_page("chat")
            st.rerun()
    with col3:
        if st.button("🔄 새로고침", width="content"):
            st.rerun()

    st_div_divider()

    # 자동 갱신 토글
    auto_refresh = st.toggle(
        "자동 갱신 (10초)",
        value=get_session_value("auto_refresh_enabled", False),
        help="진행 중인 작업을 자동으로 갱신합니다.",
    )
    set_session_value("auto_refresh_enabled", auto_refresh)

    # 작업 목록 조회
    jobs = job_store.get_all_jobs(limit=50)

    if not jobs:
        st.info("아직 생성된 작업이 없습니다. 채팅에서 광고를 생성해보세요!")
        return

    # 작업 목록 표시
    st.subheader(f"총 {len(jobs)}개의 작업")

    for job in jobs:
        render_job_card(job)

    # 자동 갱신 처리
    if auto_refresh:
        # 진행 중인 작업이 있는지 확인
        processing_jobs = [j for j in jobs if j.get("status") == "processing"]
        if processing_jobs:
            st.info(
                f"진행 중인 작업 {len(processing_jobs)}개를 {POLLING_INTERVAL}초 후 자동 갱신합니다..."
            )
            # MCP 서버에서 실제 상태 확인 및 업데이트
            for job in processing_jobs:
                asyncio.run(_check_job_status_async(job["job_id"]))

            time.sleep(POLLING_INTERVAL)
            st.rerun()


def render_job_card(job: dict) -> None:
    """
    작업 카드 렌더링

    Args:
        job: 작업 문서
        mongo_manager: MongoDB 매니저
    """
    with st.container():
        st.markdown("---")

        # 헤더
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.subheader(f"🎨 {job.get('job_id', 'Unknown')[:16]}...")
        with col2:
            status = job.get("status", "unknown")
            status_emoji = {
                "processing": "⏳",
                "completed": "✅",
                "failed": "❌",
            }.get(status, "❓")
            st.write(f"{status_emoji} **{status.upper()}**")
        with col3:
            created_at = job.get("created_at")
            if created_at:
                # ISO format string을 datetime으로 변환
                if isinstance(created_at, str):
                    from datetime import datetime

                    created_at = datetime.fromisoformat(created_at)
                st.caption(created_at.strftime("%Y-%m-%d %H:%M"))

        # 프롬프트
        with st.expander("📝 프롬프트", expanded=False):
            st.write(job.get("prompt", "N/A"))

        # 메타데이터
        metadata = job.get("metadata", {})
        if metadata:
            with st.expander("ℹ️ 상세 정보", expanded=False):
                st.json(metadata)

        # 상태별 처리
        status = job.get("status")

        if status == "processing":
            render_processing_status(job)
        elif status == "completed":
            render_completed_status(job)
        elif status == "failed":
            render_failed_status(job)


def render_processing_status(job: dict) -> None:
    """
    진행 중 상태 렌더링

    Args:
        job: 작업 문서
    """
    progress = job.get("progress_percent", 0)
    st.progress(progress / 100.0, text=f"진행률: {progress}%")

    # 상태 확인 버튼
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("🔍 상태 확인", key=f"check_{job['job_id']}"):
            check_job_status(job["job_id"])
            st.rerun()


def render_completed_status(job: dict) -> None:
    """
    완료 상태 렌더링

    Args:
        job: 작업 문서
    """
    st.success("✅ 작업이 완료되었습니다!")

    # 결과 이미지 표시
    result_image_path = job.get("result_image_path")
    if result_image_path and Path(result_image_path).exists():
        with open(result_image_path, "rb") as f:
            st.image(f.read(), caption="생성된 광고")

        # 다운로드 버튼
        with open(result_image_path, "rb") as f:
            st.download_button(
                label="⬇️ 이미지 다운로드",
                data=f,
                file_name=Path(result_image_path).name,
                mime="image/png",
                key=f"download_{job['job_id']}",
            )
    else:
        st.warning("결과 이미지를 찾을 수 없습니다.")

    # 결과 텍스트
    result_text = job.get("result_text")
    if result_text:
        with st.expander("📄 생성된 텍스트", expanded=False):
            st.write(result_text)

    # 생성 파라미터 (재현성)
    metadata = job.get("metadata", {})
    if metadata:
        with st.expander("🔄 생성 파라미터 (재현 가능)", expanded=False):
            st.json(metadata)

    # 액션 버튼
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button(
            "📝 불러오기", key=f"load_{job['job_id']}", use_container_width=True
        ):
            load_job_to_chat(job)
            set_page("chat")
            st.success("작업을 채팅에 불러왔습니다!")
            st.rerun()

    with col2:
        if st.button(
            "🗑️ 삭제",
            key=f"delete_{job['job_id']}",
            use_container_width=True,
            type="secondary",
        ):
            if job_store.delete_job(job["job_id"]):
                st.success("작업이 삭제되었습니다.")
                st.rerun()
            else:
                st.error("삭제 실패")

    with col3:
        if st.button(
            "🔁 동일 설정으로 재생성",
            key=f"regenerate_{job['job_id']}",
            use_container_width=True,
        ):
            st.info("재생성 기능은 추후 구현 예정입니다.")
            # TODO: 동일 파라미터로 새 작업 생성


def render_failed_status(job: dict) -> None:
    """
    실패 상태 렌더링

    Args:
        job: 작업 문서
    """
    error_msg = job.get("error_message", "알 수 없는 오류")
    st.error(f"❌ 작업 실패: {error_msg}")

    # 삭제 버튼
    if st.button(
        "🗑️ 삭제", key=f"delete_failed_{job['job_id']}", use_container_width=True
    ):
        if job_store.delete_job(job["job_id"]):
            st.success("작업이 삭제되었습니다.")
            st.rerun()
        else:
            st.error("삭제 실패")


def check_job_status(job_id: str) -> None:
    """
    MCP 서버에서 작업 상태 확인 및 DB 업데이트 (비동기 래핑)

    Args:
        job_id: 확인할 작업 ID
    """
    asyncio.run(_check_job_status_async(job_id))


async def _check_job_status_async(job_id: str) -> None:
    """
    MCP 서버에서 작업 상태 확인 및 DB 업데이트 (비동기)

    Args:
        job_id: 확인할 작업 ID
    """
    try:
        # 작업 정보 조회
        job = job_store.get_job(job_id)
        if not job:
            st.error("작업을 찾을 수 없습니다.")
            return

        # MCPClient를 async with로 사용
        async with MCPClient(
            base_url="http://34.44.205.198:3000", timeout=30
        ) as mcp_client:
            # MCP 서버에서 상태 확인
            output_path = job.get("metadata", {}).get("output_path")

            status_result = await mcp_client.call_tool(
                "check_generation_status",
                {"job_id": job_id, "save_result_path": output_path},
            )

            # 응답 정규화
            if isinstance(status_result, dict):
                status = status_result.get("status", "unknown")
                progress = status_result.get(
                    "progress_percent", status_result.get("progress", 0)
                )
            else:
                # 문자열 응답 처리
                status = "unknown"
                progress = 0

            # 상태 업데이트
            if status == "completed":
                job_store.update_job(
                    job_id=job_id,
                    status="completed",
                    progress_percent=100,
                    result_image_path=output_path,
                )
                st.success("작업이 완료되었습니다!")
            elif status == "failed":
                error_msg = (
                    status_result.get("message", "알 수 없는 오류")
                    if isinstance(status_result, dict)
                    else "알 수 없는 오류"
                )
                job_store.update_job(
                    job_id=job_id, status="failed", error_message=error_msg
                )
                st.error(f"작업 실패: {error_msg}")
            else:
                # 진행 중
                job_store.update_job(
                    job_id=job_id, status="processing", progress_percent=progress
                )
                current_step = (
                    status_result.get("current_step", "N/A")
                    if isinstance(status_result, dict)
                    else "N/A"
                )
                st.info(f"진행률: {progress}% (단계: {current_step})")

    except Exception as e:
        st.error(f"상태 확인 실패: {e}")
