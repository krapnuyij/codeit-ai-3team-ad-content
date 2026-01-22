"""
이미지 생성 노드 - LLM MCP 통합
content_design의 모든 ImageBox를 실제 이미지로 생성
"""

import asyncio
import base64
import json
import re
import time
from io import BytesIO
from pathlib import Path
from typing import Dict, Any, Optional

from PIL import Image
from tqdm import tqdm

import sys

project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from mcpadapter import LLMAdapter
from state import AdState, HomePageDesign
from config.config import Settings, PromptsConfig

from helper_dev_utils import get_auto_logger

logger = get_auto_logger()


async def generate_image_with_retry(
    adapter: LLMAdapter,
    prompt: str,
    image_key: str,
    max_retries: int = 3,
) -> Optional[str]:
    """
    단일 이미지 생성 (재시도 로직 포함)

    Args:
        adapter: LLMAdapter 인스턴스
        prompt: 이미지 생성 프롬프트
        image_key: 이미지 식별자 (로깅용)
        max_retries: 최대 재시도 횟수

    Returns:
        Base64 인코딩된 이미지 또는 None (실패 시)
    """
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"  [{image_key}] 생성 시도 {attempt}/{max_retries}")

            # LLM MCP 호출 (이미지 생성 + 상태 확인)
            response_text, tool_params = await adapter.chat(prompt, max_tool_calls=2)

            # job_id 추출
            job_id = None
            patterns = [
                r"작업\s*ID[:\s]+([a-f0-9-]{36})",
                r"job[_\s]*id[:\s]+([a-f0-9-]{36})",
                r"ID[:\s]+([a-f0-9-]{36})",
                r"([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})",
            ]

            for pattern in patterns:
                match = re.search(pattern, response_text, re.IGNORECASE)
                if match:
                    job_id = match.group(1)
                    break

            if not job_id and tool_params and isinstance(tool_params, dict):
                job_id = tool_params.get("job_id")

            if not job_id:
                logger.warning(
                    f"  [{image_key}] job_id를 추출할 수 없습니다. 재시도..."
                )
                continue

            logger.info(f"  [{image_key}] 작업 ID: {job_id}")

            # 작업 상태 무한 폴링 (작업이 완료/실패될 때까지 대기)
            # pending, running 상태면 계속 대기
            poll_interval = 10  # 10초 간격으로 폴링 (서버 부하 감소)
            poll_count = 0
            start_time = time.time()

            while True:
                poll_count += 1
                elapsed = int(time.time() - start_time)

                status_result = await adapter.mcp_client.call_tool(
                    "check_generation_status", {"job_id": job_id}
                )

                # JSON 파싱
                if isinstance(status_result, str):
                    try:
                        status_result = json.loads(status_result)
                    except json.JSONDecodeError:
                        logger.error(f"  [{image_key}] JSON 파싱 실패")
                        break

                status = status_result.get("status")
                progress = status_result.get("progress_percent", 0)

                # 상태 로그 (매 6회마다 = 1분마다)
                if poll_count % 6 == 0:
                    logger.info(
                        f"  [{image_key}] 진행중... status={status}, progress={progress}%, "
                        f"elapsed={elapsed}s, polls={poll_count}"
                    )

                if status == "completed":
                    image_base64 = status_result.get("image_base64")
                    if image_base64:
                        logger.info(
                            f"  [{image_key}] ✅ 생성 완료 (elapsed={elapsed}s, polls={poll_count})"
                        )
                        return image_base64
                    else:
                        logger.warning(f"  [{image_key}] 완료되었으나 이미지 없음")
                        break

                elif status in ["failed", "stopped"]:
                    logger.error(
                        f"  [{image_key}] 생성 실패: {status_result.get('error')} "
                        f"(elapsed={elapsed}s)"
                    )
                    break

                elif status in ["pending", "running"]:
                    # 작업 진행 중 - 계속 폴링
                    await asyncio.sleep(poll_interval)
                    continue

                else:
                    # 알 수 없는 상태
                    logger.warning(
                        f"  [{image_key}] 알 수 없는 상태: {status}, 재시도..."
                    )
                    break

        except Exception as e:
            logger.error(
                f"  [{image_key}] 예외 발생 (시도 {attempt}/{max_retries}): {e}"
            )
            if attempt < max_retries:
                await asyncio.sleep(10)  # 재시도 전 10초 대기
                continue

    # 모든 재시도 실패
    logger.error(f"  [{image_key}] ❌ 생성 실패 (재시도 {max_retries}회 초과)")
    return None


async def generate_images_with_llm(
    state: AdState, settings: Settings, prompts: PromptsConfig
) -> Dict[str, Any]:
    """
    content_design의 모든 ImageBox를 LLM MCP로 순차 생성

    - LLM이 DesignSystem + ImageBox.description을 조합하여 프롬프트 생성
    - 순차 처리 (MCP 서버 제약)
    - tqdm 진행률 표시
    - 3회 재시도 후 실패 시 해당 이미지 스킵 (부분 성공 허용)

    Returns:
        {
            "generated_images": Dict[str, str],  # key=이미지ID, value=Base64
            "logs": List[str]
        }
    """
    content_design: HomePageDesign = state["content_design"]
    store_concept = state["store_concept"]
    design_system = content_design.design_system

    # 모든 ImageBox 수집
    image_tasks = []
    for page in content_design.page_variations:
        if not page.content or not page.content.sections:
            continue

        for section in page.content.sections:
            for idx, image in enumerate(section.images):
                if not image.description:
                    continue

                # 이미지 ID 생성
                image_key = (
                    f"{page.page_name}_{section.section_name}_{image.type}_{idx}"
                )

                image_tasks.append(
                    {
                        "key": image_key,
                        "page": page.page_name,
                        "section": section.section_name,
                        "image": image,
                    }
                )

    total = len(image_tasks)
    if total == 0:
        logger.warning("[Image Generation] 생성할 이미지가 없습니다.")
        return {
            "generated_images": {},
            "logs": ["[Image Generation] 생성할 이미지 없음"],
        }

    logger.info(f"[Image Generation] 총 {total}개 이미지 생성 시작")

    generated_images = {}
    success_count = 0
    fail_count = 0

    # LLMAdapter 초기화
    async with LLMAdapter(
        openai_api_key=settings.openai_config.api_key,
        mcp_server_url=settings.mcp_config.server_url,
        model="gpt-5-mini",
        temperature=1.0,
    ) as adapter:

        # tqdm 진행률 표시
        with tqdm(total=total, desc="이미지 생성", unit="img", ncols=100) as pbar:
            for task in image_tasks:
                image_key = task["key"]
                image = task["image"]

                # LLM에게 스타일 반영 프롬프트 생성 요청
                style_prompt = f"""
다음 홈페이지 디자인 시스템과 이미지 설명을 기반으로,
MCP 서버의 generate_ad_image 도구를 호출하여 배경 이미지를 생성하세요.

[디자인 시스템]
- 컬러: primary={design_system.color_palette.primary}, accent={design_system.color_palette.accent}
- 스타일: {design_system.style}
- 톤앤매너: {store_concept.tone_and_manner}
- 목표 감성: {', '.join(store_concept.target_emotions)}

[이미지 설명]
{image.description}

[이미지 타입]
{image.type}

[비율]
{image.aspect_ratio}

**중요 지침:**
1. background_prompt는 위 디자인 시스템의 색상, 스타일, 톤앤매너를 반영하여 상세히 작성 (100자 이상 영문)
2. bg_model=sdxl 사용
3. stop_step=1 설정 (배경만 생성)
4. **wait_for_completion=False 설정 (즉시 job_id 반환, 폴링은 클라이언트에서 처리)**
5. 홈페이지 전체 분위기와 조화롭게

지금 바로 이미지를 생성하세요.
"""

                pbar.set_description(f"생성 중: {image_key[:30]}...")

                # 이미지 생성 (재시도 포함)
                image_base64 = await generate_image_with_retry(
                    adapter=adapter,
                    prompt=style_prompt,
                    image_key=image_key,
                    max_retries=3,
                )

                if image_base64:
                    generated_images[image_key] = image_base64
                    success_count += 1
                    pbar.set_postfix({"성공": success_count, "실패": fail_count})
                else:
                    fail_count += 1
                    pbar.set_postfix({"성공": success_count, "실패": fail_count})

                pbar.update(1)

    logger.info(
        f"[Image Generation] 완료 - 성공: {success_count}/{total}, 실패: {fail_count}/{total}"
    )

    return {
        "generated_images": generated_images,
        "logs": [
            f"[Image Generation] {success_count}/{total}개 이미지 생성 완료",
            f"[Image Generation] {fail_count}개 이미지 생성 실패 (재시도 3회 초과)",
        ],
    }
