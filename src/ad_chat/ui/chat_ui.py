"""
UI 컴포넌트: 채팅 인터페이스

LLMAdapter를 통한 자연어 기반 광고 기획 및 MCP 서버 작업 요청
"""

import streamlit as st
import re
import json
import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from config import (
    OPENAI_MODEL,
    OPENAI_TEMPERATURE,
    OPENAI_MAX_COMPLETION_TOKENS,
    MCP_SERVER_URL,
    MCP_TIMEOUT,
    UPLOADS_DIR,
    RESULTS_DIR,
    JOB_TYPE_FULL,
    STATUS_PROCESSING,
    STATUS_COMPLETED,
    STATUS_FAILED,
    POLLING_INTERVAL,
)
from services import LLMAdapter, MongoManager, MCPClient, get_job_store
from utils.state_manager import add_chat_message, get_session_value, set_page, logout
import time
from PIL import Image as PILImage

logger = logging.getLogger(__name__)

# 작업 저장소 (MongoDB 대안)
job_store = get_job_store()


def render_chat_ui() -> None:
    """
    채팅 인터페이스 렌더링

    LLMAdapter를 통한 대화형 광고 기획 및 MCP 서버 작업 요청
    """
    st.title("💬 AI 광고 기획 채팅")

    # 상단 메뉴
    col1, col2, col3 = st.columns([3, 1, 1])
    with col2:
        if st.button("📁 히스토리", width="content"):
            set_page("history")
            st.rerun()
    with col3:
        if st.button("🚪 로그아웃", width="content"):
            logout()
            st.rerun()

    st.markdown("---")

    # 모니터링 중인 작업 확인 및 완료 알림
    check_and_display_completed_jobs()

    # 채팅 히스토리 표시
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

    # 사용자 입력
    user_input = st.chat_input("광고 아이디어를 말씀해주세요...")

    if user_input:
        # 사용자 메시지 추가
        add_chat_message("user", user_input)
        with st.chat_message("user"):
            st.write(user_input)

        # AI 응답 생성 (LLMAdapter - 자동 MCP 도구 호출)
        with st.chat_message("assistant"):
            with st.spinner("생각 중..."):
                response, job_id, tool_params = asyncio.run(
                    generate_ai_response_async(user_input)
                )
                st.write(response)
                add_chat_message("assistant", response)

                # job_id가 있으면 MongoDB에 저장 및 안내
                if job_id:
                    handle_job_creation(job_id, user_input, tool_params)

        st.rerun()


async def generate_ai_response_async(user_message: str):
    """
    LLMAdapter를 통한 AI 응답 생성 및 자동 MCP 도구 호출

    Args:
        user_message: 사용자 메시지

    Returns:
        (AI 응답 텍스트, job_id 또는 None, 도구 파라미터 또는 None)
    """
    api_key = get_session_value("openai_key")

    # 제품 이미지 자동 생성 (없을 경우)
    product_image = UPLOADS_DIR / "test_product.png"
    if not product_image.exists():
        create_test_product_image(product_image)

    # 시스템 프롬프트 (MCP 도구 사용 안내 포함)
    system_prompt = f"""당신은 나노코코아(nanoCocoa) AI 광고 생성 시스템의 전문 어시스턴트입니다.

**역할:**
1. 사용자와 대화하며 효과적인 광고 컨셉 제안
2. 광고 생성 요청 시 자동으로 MCP 도구를 호출하여 실제 광고 이미지 생성

**광고 생성 프로세스:**
1. 제품/서비스 정보 파악
2. 타겟 고객층 확인
3. 광고 톤앤매너 결정 (세일/프리미엄/캐주얼)
4. 핵심 메시지 및 카피 제안
5. 비주얼 컨셉 제안

**MCP 도구 사용 규칙:**
- 사용자가 "광고 생성", "만들어줘", "생성", "나노코코아로", "create", "generate" 등 광고 생성 의도를 표현하면 즉시 `generate_ad_content` 도구 호출
- 필수 파라미터:
  - product_image_path: "{str(product_image)}" (기본값)
  - text_content: 사용자가 언급한 광고 텍스트 (예: "특가 세일", "50% 할인") 또는 대화 문맥에서 추출
  - composition_mode: "overlay" (기본값)
  - wait_for_completion: false (비동기 처리)

**응답 가이드:**
- 도구 호출 후 "광고 생성 작업이 시작되었습니다. 작업 ID: [job_id]" 형식으로 안내
- 작업은 15~30분 소요되며, 히스토리 페이지에서 진행 상황 확인 가능함을 안내
- **중요:** text_content는 원문 언어(영어는 영어, 한글은 한글)를 유지. 단위, 문맥 등은 적당하게 수정 가능
- background_prompt, text_prompt 등 이미지 생성 prompt(프롬프트)만 영문으로 작성
"""

    try:
        async with LLMAdapter(
            openai_api_key=api_key,
            mcp_server_url=MCP_SERVER_URL,
            model=OPENAI_MODEL,
            temperature=OPENAI_TEMPERATURE,
            max_completion_tokens=OPENAI_MAX_COMPLETION_TOKENS,
        ) as adapter:

            # 대화 히스토리를 LLMAdapter에 전달
            for msg in st.session_state.chat_history[:-1]:  # 현재 메시지 제외
                if msg["role"] == "user":
                    adapter.conversation_history.append(
                        {"role": "user", "content": msg["content"]}
                    )
                elif msg["role"] == "assistant":
                    adapter.conversation_history.append(
                        {"role": "assistant", "content": msg["content"]}
                    )

            # 시스템 프롬프트 주입
            adapter.conversation_history.insert(
                0, {"role": "system", "content": system_prompt}
            )

            # LLM 응답 생성 (필요 시 자동으로 MCP 도구 호출)
            response, tool_params = await adapter.chat(user_message, max_tool_calls=3)

            # job_id 추출 (도구 호출 결과에서)
            job_id = None
            for msg in reversed(adapter.conversation_history):
                if msg.get("role") == "tool":
                    tool_response = msg.get("content", "")
                    job_id = extract_job_id(tool_response)
                    if job_id:
                        logger.info(f"job_id 추출 성공: {job_id}")
                        break

            return response, job_id, tool_params

    except Exception as e:
        logger.error(f"LLMAdapter 오류: {e}")
        return f"오류가 발생했습니다: {str(e)}", None, None


def extract_job_id(tool_response: str):
    """
    도구 응답에서 job_id 추출

    Args:
        tool_response: MCP 도구 호출 결과

    Returns:
        job_id 또는 None
    """
    if not tool_response:
        return None

    # 1. JSON 파싱 시도
    try:
        data = json.loads(tool_response)
        if "job_id" in data:
            return data["job_id"]
    except json.JSONDecodeError:
        pass

    # 2. UUID 패턴 검색
    uuid_pattern = r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}"
    matches = re.findall(uuid_pattern, tool_response, re.IGNORECASE)
    if matches:
        return matches[0]

    return None


def handle_job_creation(
    job_id: str, user_message: str, tool_params: Optional[Dict[str, Any]] = None
) -> None:
    """
    작업 생성 후 저장, 사용자 안내 및 모니터링 시작

    Args:
        job_id: 작업 ID
        user_message: 사용자 요청 메시지
        tool_params: 실제 사용된 도구 파라미터 (재현성)
    """
    # 재현성을 위해 실제 사용된 파라미터 저장
    if tool_params and tool_params.get("parameters"):
        generation_params = tool_params["parameters"].copy()
        # 사용자 원문 메시지도 추가
        generation_params["user_message"] = user_message
        generation_params["model"] = OPENAI_MODEL
        generation_params["mcp_server_url"] = MCP_SERVER_URL
        logger.info(f"실제 도구 파라미터 저장: {list(generation_params.keys())}")
    else:
        # fallback: 기본 파라미터
        product_image = UPLOADS_DIR / "test_product.png"
        generation_params = {
            "user_message": user_message,
            "text_content": user_message,
            "product_image_path": str(product_image),
            "composition_mode": "overlay",
            "model": OPENAI_MODEL,
            "mcp_server_url": MCP_SERVER_URL,
        }
        logger.warning("도구 파라미터 없음, 기본값 사용")

    try:
        # 작업 저장 (파일 기반)
        job_store.create_job(
            job_id=job_id,
            prompt=user_message,
            metadata=generation_params,
        )
        logger.info(f"작업 저장 완료: {job_id}")
        history_msg = "\n\n📁 **히스토리 페이지**에서 진행 상황을 확인하세요."

        # 작업 모니터링 시작
        monitor_job_in_background(job_id)

        st.success(
            f"""
✅ 광고 생성 작업이 시작되었습니다!

**작업 ID:** `{job_id}`

작업은 15~30분 정도 소요됩니다.{history_msg}

⏱️ 완료되면 자동으로 결과를 표시합니다.
"""
        )

    except Exception as e:
        st.warning(f"작업 저장 실패 (작업은 진행 중): {e}")


def monitor_job_in_background(job_id: str) -> None:
    """
    백그라운드에서 작업 상태를 모니터링하고 완료 시 결과 저장

    Args:
        job_id: 작업 ID
    """
    # Session state에 모니터링 작업 추가
    if "monitoring_jobs" not in st.session_state:
        st.session_state.monitoring_jobs = []

    if job_id not in st.session_state.monitoring_jobs:
        st.session_state.monitoring_jobs.append(job_id)
        logger.info(f"작업 모니터링 시작: {job_id}")


async def check_job_status_and_update(job_id: str) -> dict:
    """
    MCP 서버에서 작업 상태 확인 및 저장소 업데이트

    Args:
        job_id: 작업 ID

    Returns:
        작업 상태 정보
    """
    try:
        # 로컬 저장 경로 생성
        save_result_path = RESULTS_DIR / f"{job_id}.png"

        async with MCPClient(base_url=MCP_SERVER_URL, timeout=MCP_TIMEOUT) as client:
            # MCP 서버에서 상태 확인 (save_result_path 전달하여 완료 시 이미지 저장)
            status_params = {
                "job_id": job_id,
                "save_result_path": str(save_result_path),
            }

            result = await client.call_tool("check_generation_status", status_params)

            # 결과 파싱
            if isinstance(result, str):
                status_data = json.loads(result)
            else:
                status_data = result

            status = status_data.get("status")
            progress = status_data.get("progress_percent", 0)

            # 작업 저장소 업데이트
            if status == "completed":
                logger.info(f"✅ 작업 완료: {job_id}")
                logger.info(f"   이미지 저장됨: {save_result_path}")

                # 파일 존재 확인
                if save_result_path.exists():
                    logger.info(
                        f"   파일 크기: {save_result_path.stat().st_size:,} bytes"
                    )
                else:
                    logger.warning(
                        f"   ⚠️  이미지 파일이 생성되지 않았습니다: {save_result_path}"
                    )

                job_store.update_job(
                    job_id=job_id,
                    status="completed",
                    progress_percent=100,
                    result_image_path=str(save_result_path),
                )
            elif status == "failed":
                error_msg = status_data.get("message", "Unknown error")
                job_store.update_job(
                    job_id=job_id,
                    status="failed",
                    error_message=error_msg,
                )
                logger.error(f"❌ 작업 실패: {job_id} - {error_msg}")
            elif status == "processing":
                job_store.update_job(
                    job_id=job_id,
                    status="processing",
                    progress_percent=progress,
                )
                logger.debug(f"⏳ 작업 진행 중: {job_id} ({progress}%)")

            return status_data

    except Exception as e:
        logger.error(f"작업 상태 확인 실패: {e}")
        return {"status": "unknown", "error": str(e)}


def create_test_product_image(output_path: Path) -> None:
    """
    테스트용 제품 이미지 생성

    Args:
        output_path: 저장 경로
    """
    from PIL import Image, ImageDraw
    import stat

    try:
        logger.info(f"테스트 이미지 생성 중: {output_path}")
    except:
        pass  # logger 없을 경우 무시

    # 디렉토리 권한 확인 및 수정
    output_dir = output_path.parent
    if output_dir.exists():
        current_mode = output_dir.stat().st_mode
        try:
            logger.info(f"디렉토리 권한: {oct(stat.S_IMODE(current_mode))}")
        except:
            pass

        # 쓰기 권한 부여 (755)
        try:
            output_dir.chmod(0o755)
            try:
                logger.info("디렉토리 권한 수정 완료 (755)")
            except:
                pass
        except Exception as e:
            try:
                logger.warning(f"권한 수정 실패 (무시하고 계속): {e}")
            except:
                pass
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            logger.info(f"디렉토리 생성: {output_dir}")
        except:
            pass

    # 512x512 바나나 이미지 생성
    img = Image.new("RGB", (512, 512), color="white")
    draw = ImageDraw.Draw(img)

    # 바나나 모양
    draw.ellipse([150, 100, 450, 200], fill="#FFD700", outline="#FFA500", width=3)
    draw.ellipse([100, 200, 400, 300], fill="#FFD700", outline="#FFA500", width=3)
    draw.ellipse([120, 280, 380, 400], fill="#FFD700", outline="#FFA500", width=3)

    try:
        img.save(output_path)
        try:
            logger.info(f"테스트 이미지 생성 완료: {output_path}")
            logger.info(f"  크기: {output_path.stat().st_size:,} bytes")
        except:
            pass
    except PermissionError as e:
        try:
            logger.error(f"저장 실패 (권한 오류): {e}")
            logger.info("해결 방법:")
            logger.info(f"  터미널에서 실행: chmod 755 {output_dir}")
        except:
            pass
        raise


def check_and_display_completed_jobs() -> None:
    """
    모니터링 중인 작업의 완료 여부 확인 및 결과 표시
    """
    if (
        "monitoring_jobs" not in st.session_state
        or not st.session_state.monitoring_jobs
    ):
        return

    try:
        completed_jobs = []

        for job_id in st.session_state.monitoring_jobs[:]:
            # MCP 서버에서 최신 상태 확인 후 업데이트
            asyncio.run(check_job_status_and_update(job_id))

            # 업데이트된 작업 정보 조회
            job = job_store.get_job(job_id)

            if not job:
                logger.warning(f"작업 {job_id}를 찾을 수 없습니다")
                continue

            status = job.get("status")

            if status == "completed":
                # 완료된 작업 표시
                display_completed_job_result(job)
                completed_jobs.append(job_id)

            elif status == "failed":
                st.error(
                    f"❌ 작업 실패: {job_id}\n{job.get('error_message', 'Unknown error')}"
                )
                completed_jobs.append(job_id)

        # 완료된 작업을 모니터링 목록에서 제거
        for job_id in completed_jobs:
            st.session_state.monitoring_jobs.remove(job_id)

        # 진행 중인 작업이 있으면 자동 새로고침
        if st.session_state.monitoring_jobs:
            with st.spinner(
                f"⏳ {len(st.session_state.monitoring_jobs)}개 작업 진행 중... {POLLING_INTERVAL}초 후 자동 갱신"
            ):
                time.sleep(POLLING_INTERVAL)
                st.rerun()

    except Exception as e:
        logger.error(f"작업 확인 중 오류: {e}")


def display_completed_job_result(job: dict) -> None:
    """
    완료된 작업의 결과 표시

    Args:
        job: 작업 문서
    """
    st.success(f"✅ 광고 생성 완료! (작업 ID: {job['job_id'][:16]}...)")

    # 결과 이미지 표시
    result_path = job.get("result_image_path")
    if result_path:
        result_file = Path(result_path)
        if result_file.exists():
            st.image(str(result_file), caption="생성된 광고 이미지", width="content")
        else:
            st.warning(f"⚠️ 이미지 파일을 찾을 수 없습니다: {result_path}")

    # 생성 파라미터 표시 (재현성)
    with st.expander("📋 생성 파라미터 (재현 가능)"):
        metadata = job.get("metadata", {})
        st.json(metadata)

    # 히스토리 페이지 링크
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📁 히스토리에서 자세히 보기", key=f"view_{job['job_id']}"):
            set_page("history")
            st.rerun()
    with col2:
        if st.button("🔄 새로운 광고 생성", key=f"new_{job['job_id']}"):
            st.rerun()
