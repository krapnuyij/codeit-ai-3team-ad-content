"""
LangGraph 노드 함수들
각 노드는 AdState를 받아서 특정 작업을 수행하고 업데이트된 상태를 반환합니다.
"""

import json
import base64
from io import BytesIO
from PIL import Image
from agent_framework import (
    AgentRunEvent,
    AgentRunUpdateEvent,
    WorkflowOutputEvent,
    ChatMessage,
)
from typing import Dict, Any, cast
from pathlib import Path
from openai import AsyncOpenAI

from agents import OpenAIAgent
from state import (
    AdState,
    BSParser,
    StoreInfo,
    StoreConcept,
    MarketingStrategy,
    HomePageDesign,
    DOMContract,
    ImplementationSpec,
    GeneratedCode,
)
from config.config import Settings, PromptsConfig

from helper_dev_utils import get_auto_logger

logger = get_auto_logger()


# Node 0: Brain Storm
async def create_brain_storm(
    state: AdState, settings: Settings, prompts: PromptsConfig
) -> Dict[str, Any]:
    """
    점포 데이터를 받은 후, 여러 방면의 아이디어 제시
    """
    from agent_framework.openai import OpenAIChatClient
    from agent_framework import ChatAgent, GroupChatBuilder

    def build_brainstorm_text(messages: list[ChatMessage]) -> str:
        lines = []

        for msg in messages:
            if not msg.contents:
                continue

            # speaker = msg.name or msg.role
            speaker = msg.role
            lines.append(f"[{speaker}]")
            print(f"메시지 내용 : {msg.text}")
            lines.append(msg.contents)
            lines.append("")  # 줄바꿈

        return "\n".join(lines)

    client = OpenAIChatClient(
        model_id=settings.openai_config.chat_model,
        api_key=settings.openai_config.api_key,
    )
    # 1. 사용할 에이전트 키 리스트 정의
    # agent_keys = ["sns_bs_agent", "blog_bs_agent", "design_bs_agent", "developer_bs_agent"]
    agent_keys = [
        "pm_agent",
        "designer_agent",
        "developer_agent",
        "content_agent",
        "expander_agent",
    ]
    # 2. 반복문을 이용한 에이전트 생성 및 리스트 저장
    agents = []
    for key in agent_keys:
        agent_config = prompts.bs_agents[key]
        agent = ChatAgent(
            chat_client=client,
            name=agent_config.name,
            description=agent_config.role,
            instructions=agent_config.system_message,
        )
        agents.append(agent)
    manager_config = prompts.bs_agents["bs_manager"]
    manager_agent = ChatAgent(
        chat_client=client,
        name=manager_config.name,
        description=manager_config.role,
        instructions=manager_config.system_message,
    )
    bs_groupchat = (
        GroupChatBuilder()
        .set_manager(manager=manager_agent, display_name="BS_매니저")
        .participants(agents)
        .build()
    )

    final_conversation: list[ChatMessage] = []
    current_speaker: str | None = None

    state["brainstorm_user_input"] = prompts.user_prompt.format(
        StoreInfo=state["store_info"]
    )
    async for event in bs_groupchat.run_stream(message=state["brainstorm_user_input"]):
        # print(event)
        if isinstance(event, AgentRunUpdateEvent):
            speaker_id = event.executor_id.replace("groupchat_agent:", "")

            if speaker_id != current_speaker:
                if current_speaker is not None:
                    print("\n")
                print(f"[{speaker_id}]", flush=True)
                current_speaker = speaker_id

            print(event.data, end="", flush=True)

        elif isinstance(event, WorkflowOutputEvent):
            final_conversation = cast(list[ChatMessage], event.data)

    brainstorm_text = build_brainstorm_text(final_conversation)
    print(brainstorm_text)
    # result = await bs_groupchat.run(message=state["brainstorm_user_input"])
    # print(result)
    # parsed = json.loads(result)
    # brainstorm: BrainStorm = parsed["brainstorm"]
    return {
        "brainstorm": brainstorm_text,
        "log": ["[BrainStorm Node] 브레인스토밍 완료"],
    }


# BS Parser Node
async def create_bs_parser(
    state: AdState, settings: Settings, prompts: PromptsConfig, client: AsyncOpenAI
) -> Dict[str, Any]:
    agent_config = prompts.agents["parser"]
    print(state["brainstorm"])
    agent = OpenAIAgent(
        client=client,
        agent_config=agent_config,
        settings=settings,
    )
    response = agent.create(state["brainstorm"])

    result_text = response.choices[0].message.content
    result_json = json.loads(result_text)

    bs_parser = BSParser(**result_json)

    return {
        "bs_parser": bs_parser,
        "logs": [f"[Parser Node] bs_parser 생성 완료: {bs_parser}"],
    }


# Node A: Campaign Core
async def create_concept_designer(
    state: AdState, settings: Settings, prompts: PromptsConfig, client: AsyncOpenAI
) -> Dict[str, Any]:
    """
    캠페인 핵심 메시지 및 컨셉을 생성합니다.
    """
    agent_config = prompts.agents["concept_designer"]

    agent = OpenAIAgent(
        client=client,
        agent_config=agent_config,
        settings=settings,
    )

    store_info = state["store_info"]

    user_prompts = agent_config.user_message.format(**store_info.model_dump())
    # response = await agent.create(message=user_prompts)
    #
    # result_text = response.choices[0].message.content
    # result_json = json.loads(result_text)
    #
    #
    # store_concept = StoreConcept(**result_json)

    store_concept = await agent.create_structured(
        user_prompts, response_model=StoreConcept
    )
    print(store_concept)

    return {
        "store_concept": store_concept,
        "logs": [f"[Store Concept] 생성 완료: {store_concept.core_message}"],
    }


async def create_marketing_strategy(
    state: AdState, settings: Settings, prompts: PromptsConfig, client: AsyncOpenAI
) -> Dict[str, Any]:
    """
    매장 컨셉을 기준으로 마케팅 전략을 생성합니다.
    """

    agent_config = prompts.agents["marketing_strategy"]

    agent = OpenAIAgent(
        client=client,
        agent_config=agent_config,
        settings=settings,
    )

    store_info = state["store_info"]
    store_concept = state["store_concept"]

    user_prompts = agent_config.user_message.format(
        **store_info.model_dump(),
        **store_concept.model_dump(),
    )
    # response = await agent.create(message=user_prompts)
    #
    # result_text = response.choices[0].message.content
    # result_json = json.loads(result_text)
    #
    # marketing_strategy = MarketingStrategy(**result_json)
    marketing_strategy = await agent.create_structured(
        user_prompts, response_model=MarketingStrategy
    )
    # print(marketing_strategy)
    return {
        "marketing_strategy": marketing_strategy,
        "logs": [f"[Marketing Strategy] 생성 완료: {marketing_strategy.strategy}"],
    }


async def create_homepage_designer(
    state: AdState, settings: Settings, prompts: PromptsConfig, client: AsyncOpenAI
) -> Dict[str, Any]:
    """
    홈페이지를 매장 컨셉에 맞추어, 전체적인 디자인 스펙 생성
    """

    agent_config = prompts.agents["homepage_designer"]

    agent = OpenAIAgent(
        client=client,
        agent_config=agent_config,
        settings=settings,
    )

    store_info = state["store_info"]
    store_concept = state["store_concept"]
    marketing_strategy = state["marketing_strategy"]

    user_prompts = agent_config.user_message.format(
        **store_info.model_dump(),
        **store_concept.model_dump(),
        **marketing_strategy.strategy.model_dump(),  # strategy 내부를 풀어서 전달
    )
    # response = await agent.create(message=user_prompts)
    #
    # result_text = response.choices[0].message.content
    # result_json = json.loads(result_text)
    # print(result_json)
    # homepage_design = HomePageDesign(**result_json)
    homepage_design = await agent.create_structured(
        user_prompts, response_model=HomePageDesign
    )

    return {
        "homepage_design": homepage_design,
        "logs": [f"[Homepage Design] 생성 완료"],
    }


async def create_content_designer(
    state: AdState, settings: Settings, prompts: PromptsConfig, client: AsyncOpenAI
) -> Dict[str, Any]:
    """
    각 페이지에 구체적인 콘텐츠(버튼, 태그 등) 스펙 생성
    """
    agent_config = prompts.agents["content_agent"]
    agent = OpenAIAgent(
        client=client,
        agent_config=agent_config,
        settings=settings,
    )
    store_info = state["store_info"]
    homepage_design = state["homepage_design"]

    homepage_design_json = json.dumps(
        homepage_design.model_dump(), indent=2, ensure_ascii=False
    )

    user_prompts = agent_config.user_message.format(
        homepage_design=homepage_design_json, **store_info.model_dump()
    )
    content_design = await agent.create_structured(
        user_prompts, response_model=HomePageDesign
    )

    return {
        "content_design": content_design,
        "logs": [f"[Homepage Design with Content] 생성 완료"],
    }


def generate_dom_contract_rule_based(content_design: HomePageDesign) -> DOMContract:
    """
    content_design을 분석하여 DOM Contract를 룰 기반으로 생성

    LLM 없이 deterministic하게 DOM 구조 규칙 생성

    ⚠️ DEPRECATED: Tailwind CDN 방식으로 전환하면서 더 이상 사용되지 않습니다.
    """
    # 1. 사용된 모든 타입 수집
    text_types = set()
    image_types = set()
    button_types = set()

    for page in content_design.page_variations:
        if page.content and page.content.sections:
            for section in page.content.sections:
                # 텍스트 타입 수집
                for text_block in section.text_blocks:
                    if text_block.type:
                        text_types.add(text_block.type)

                # 이미지 타입 수집
                for image in section.images:
                    if image.type:
                        image_types.add(image.type)

                # 버튼 타입 수집
                for button in section.buttons:
                    if button.type:
                        button_types.add(button.type)

    # 2. text_mappings 동적 생성
    text_mappings = {}
    for text_type in text_types:
        text_type_lower = text_type.lower()

        # 시맨틱 태그 선택 규칙
        if "headline" in text_type_lower or text_type == "h1":
            tag = "h1"
        elif "subheading" in text_type_lower or text_type.startswith("h2"):
            tag = "h2"
        elif "title" in text_type_lower or "heading" in text_type_lower:
            tag = "h3"
        elif "tagline" in text_type_lower or "caption" in text_type_lower:
            tag = "p"
        elif "body" in text_type_lower or "paragraph" in text_type_lower:
            tag = "p"
        else:
            tag = "p"  # default

        # BEM 네이밍 생성
        text_mappings[text_type] = f"{tag}.text.text--{text_type}"

    # 3. DOMContract 객체 생성 (기본값 사용, text_mappings만 커스터마이즈)
    dom_contract = DOMContract(
        text_mappings=(
            text_mappings
            if text_mappings
            else {
                "headline": "h1.text.text--headline",
                "subheading": "h2.text.text--subheading",
                "body": "p.text.text--body",
                "tagline": "p.text.text--tagline",
            }
        )
    )

    return dom_contract


async def create_dom_contract(
    state: AdState, settings: Settings, prompts: PromptsConfig, client: AsyncOpenAI
) -> Dict[str, Any]:
    """
    content_design을 분석하여 DOM Contract 생성 (룰 기반)

    ⚠️ DEPRECATED: Tailwind CDN 방식으로 전환하면서 더 이상 사용되지 않습니다.
    하위 호환성을 위해 유지되지만 실제로는 사용되지 않습니다.
    """
    content_design = state["content_design"]

    # 룰 기반 DOM Contract 생성
    dom_contract = generate_dom_contract_rule_based(content_design)

    # 수집된 타입 통계
    text_type_count = len(dom_contract.text_mappings)

    return {
        "dom_contract": dom_contract,
        "logs": [
            f"[DOM Contract] 룰 기반 생성 완료 (text mappings: {text_type_count}개)"
        ],
    }


# # Node F: 구현 명세 생성(DEPRECATED)
async def create_implementation_spec(
    state: AdState, settings: Settings, prompts: PromptsConfig, client: AsyncOpenAI
) -> Dict[str, Any]:
    """
    프론트엔드 및 스타일 구현 명세를 생성합니다. DEPRECATED
    """

    prompt = f"""
당신은 프론트엔드 개발 설계자입니다.

다음 정보를 바탕으로 구현 명세를 작성해주세요:

디자인 가이드:
- 컬러: {', '.join(state['design_guide'].color_palette)}
- 타이포그래피: {state['design_guide'].typography}
- 레이아웃: {', '.join(state['design_guide'].layout_principles)}

SNS/블로그 전략:
- SNS 콘텐츠: {', '.join(state['sns_strategy'].content_types)}
- 블로그 구조: {state['blog_strategy'].content_structure}

다음 형식의 JSON으로 응답해주세요:

{{
    "frontend_requirements": ["요구사항1", "요구사항2", "..."],
    "style_requirements": ["스타일1", "스타일2", "..."],
    "asset_requirements": ["에셋1", "에셋2", "..."],
    "technical_constraints": ["제약사항1", "제약사항2", "..."]
}}
"""

    response = await client.chat.completions.create(
        model=settings.openai_config.chat_model,
        messages=[{"role": "user", "content": prompt}],
    )

    result_text = response.choices[0].message.content
    result_json = json.loads(result_text)

    implementation_spec = ImplementationSpec(**result_json)

    return {
        "implementation_spec": implementation_spec,
        "logs": ["[Node F] 구현 명세 생성 완료"],
    }


# Node F2: Header/Footer 생성
async def generate_header_footer(
    state: AdState, settings: Settings, prompts: PromptsConfig, client: AsyncOpenAI
) -> Dict[str, Any]:
    """
    공통 Header와 Footer HTML을 생성합니다.

    모든 페이지에서 일관되게 사용되는 header/footer를 한 번만 생성하여
    중복을 방지하고 일관성을 유지합니다.
    """
    agent_config = prompts.agents["header_footer_coder"]

    agent = OpenAIAgent(
        client=client,
        agent_config=agent_config,
        settings=settings,
    )

    content_design = state["content_design"]
    store_info = state["store_info"]
    design_system = content_design.design_system

    # JSON 직렬화
    colors_json = json.dumps(
        design_system.color_palette.model_dump(), indent=2, ensure_ascii=False
    )

    fonts_json = json.dumps(
        design_system.fonts.model_dump(), indent=2, ensure_ascii=False
    )

    header_json = json.dumps(
        design_system.header.model_dump(), indent=2, ensure_ascii=False
    )

    footer_json = json.dumps(
        design_system.footer.model_dump(), indent=2, ensure_ascii=False
    )

    # 전체 페이지 목록
    all_page_names = [page.page_name for page in content_design.page_variations]
    all_page_names_str = json.dumps(all_page_names, ensure_ascii=False)

    user_prompts = agent_config.user_message.format(
        store_name=store_info.store_name,
        phone_number=store_info.phone_number,
        location=store_info.location,
        colors=colors_json,
        fonts=fonts_json,
        style=design_system.style,
        header=header_json,
        footer=footer_json,
        all_page_names=all_page_names_str,
    )

    result = await agent.create(user_prompts)
    result_text = result.choices[0].message.content

    # JSON 파싱
    result_json = json.loads(result_text)
    header_html = result_json.get("header", "")
    footer_html = result_json.get("footer", "")

    return {
        "header_html": header_html,
        "footer_html": footer_html,
        "logs": [
            f"[Header/Footer] 공통 Header/Footer 생성 완료 (Header: {len(header_html)}자, Footer: {len(footer_html)}자)"
        ],
    }


# Node G: Main 콘텐츠 생성 (Tailwind 방식)
async def generate_html_code(
    state: AdState, settings: Settings, prompts: PromptsConfig, client: AsyncOpenAI
) -> Dict[str, Any]:
    """
    content_design를 기반으로 페이지별 main 콘텐츠만 생성합니다.

    Header/Footer는 별도로 생성되며, 각 페이지는 <main> 태그 내부만 생성합니다.
    최종 조합은 package_output에서 처리됩니다.
    """
    agent_config = prompts.agents["html_coder"]

    agent = OpenAIAgent(
        client=client,
        agent_config=agent_config,
        settings=settings,
    )

    content_design = state["content_design"]
    design_system = content_design.design_system

    # JSON 직렬화 (공통 데이터)
    colors_json = json.dumps(
        design_system.color_palette.model_dump(), indent=2, ensure_ascii=False
    )

    fonts_json = json.dumps(
        design_system.fonts.model_dump(), indent=2, ensure_ascii=False
    )

    # 페이지별로 main 콘텐츠 생성
    html_codes = {}
    for page in content_design.page_variations:
        page_name = page.page_name

        # 개별 페이지 데이터 직렬화
        page_data_json = json.dumps(page.model_dump(), indent=2, ensure_ascii=False)

        user_prompts = agent_config.user_message.format(
            page_name=page_name,
            page_data=page_data_json,
            colors=colors_json,
            fonts=fonts_json,
            style=design_system.style,
        )

        result = await agent.create(user_prompts)
        main_content = result.choices[0].message.content
        html_codes[page_name] = main_content

    total_length = sum(len(code) for code in html_codes.values())

    return {
        "html_codes": html_codes,
        "logs": [
            f"[Main Content (Tailwind)] {len(html_codes)}개 페이지 main 콘텐츠 생성 완료 (총 길이: {total_length} 문자)"
        ],
    }


# Node H: CSS 코드 생성 (DEPRECATED)
async def generate_css_code(
    state: AdState, settings: Settings, prompts: PromptsConfig, client: AsyncOpenAI
) -> Dict[str, Any]:
    """
    ⚠️ DEPRECATED: Tailwind CDN 방식 도입으로 더 이상 사용되지 않습니다.

    content_design, dom_contract, html_codes를 기반으로 CSS 코드를 생성합니다. (MPA 방식)
    """
    agent_config = prompts.agents["css_coder"]

    agent = OpenAIAgent(
        client=client,
        agent_config=agent_config,
        settings=settings,
    )

    content_design = state["content_design"]
    dom_contract = state["dom_contract"]
    html_codes = state["html_codes"]
    design_system = content_design.design_system

    # JSON 직렬화
    dom_contract_json = json.dumps(
        dom_contract.model_dump(), indent=2, ensure_ascii=False
    )

    # 모든 HTML 코드를 문자열로 변환 (페이지별로 구분)
    html_codes_str = json.dumps(html_codes, indent=2, ensure_ascii=False)
    # HTML은 너무 길 수 있으니 일부만 전달 (각 페이지당 최대 2000자)
    truncated_html_codes = {
        page_name: html[:2000] + ("..." if len(html) > 2000 else "")
        for page_name, html in html_codes.items()
    }
    html_codes_truncated_str = json.dumps(
        truncated_html_codes, indent=2, ensure_ascii=False
    )

    user_prompts = agent_config.user_message.format(
        primary=design_system.color_palette.primary,
        accent=design_system.color_palette.accent,
        text=design_system.color_palette.text,
        heading=design_system.fonts.heading,
        body_font=design_system.fonts.body,
        style=design_system.style,
        dom_contract=dom_contract_json,
        html_codes=html_codes_truncated_str,
    )

    result = await agent.create(user_prompts)
    css_code = result.choices[0].message.content

    return {
        "css_code": css_code,
        "logs": [f"[CSS Code] 생성 완료 (길이: {len(css_code)} 문자)"],
    }


async def evaluate_code_value(
    state: AdState, settings: Settings, prompts: PromptsConfig, client: AsyncOpenAI
) -> Dict[str, Any]:
    agent_config = prompts.agents[""]
    agent = OpenAIAgent(
        client=client,
        agent_config=agent_config,
        settings=settings,
    )

    html_code = state["html_codes"]


# Node I: 최종 패키징 (Tailwind 방식)
async def package_output(
    state: AdState, settings: Settings, prompts: PromptsConfig
) -> Dict[str, Any]:
    """
    모든 결과물을 파일로 저장합니다. (MPA 방식: 페이지별 HTML 파일)

    Header + Main + Footer를 조합하여 완전한 HTML 문서를 생성합니다.
    Tailwind CDN을 사용하므로 별도의 CSS 파일을 저장하지 않습니다.
    """
    from datetime import datetime

    store_info = state["store_info"]

    # 매장명에서 띄어쓰기를 언더스코어로 치환
    store_name_safe = store_info.store_name.replace(" ", "_")

    # 타임스탬프 생성 (YYYYMMDD_HHMMSS)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 동적 경로 생성: ./generated_ad/매장명_타임스탬프/
    base_path = Path(settings.paths.generated_path)
    output_dir = base_path / f"{store_name_safe}_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # images/ 폴더 생성
    images_dir = output_dir / "images"
    images_dir.mkdir(exist_ok=True)

    # 생성된 이미지 저장 (Base64 -> PNG)
    generated_images = state.get("generated_images", {})
    image_mapping = {}  # placeholder URL -> 로컬 경로 매핑

    if generated_images:
        logger.info(f"[Package Output] {len(generated_images)}개 이미지 저장 중...")
        for image_key, base64_data in generated_images.items():
            try:
                # Base64 디코딩
                img_data = base64.b64decode(base64_data)
                img = Image.open(BytesIO(img_data))

                # 파일 저장
                img_filename = f"{image_key}.png"
                img_path = images_dir / img_filename
                img.save(img_path)

                # 매핑 저장 (상대 경로)
                local_path = f"images/{img_filename}"
                image_mapping[image_key] = local_path

                logger.info(f"  저장: {img_filename}")
            except Exception as e:
                logger.error(f"  이미지 저장 실패 ({image_key}): {e}")

    header_html = state["header_html"]
    footer_html = state["footer_html"]
    html_codes = state["html_codes"]  # main 콘텐츠만 포함

    # 페이지별 HTML 파일 저장 (header + main + footer 조합)
    html_paths = []
    for page_name, main_content in html_codes.items():
        # 파일명 매핑: home -> index.html, menu -> menu.html, 기타 -> {page_name}.html
        if page_name.lower() == "home":
            filename = "index.html"
            page_title = store_info.store_name
        else:
            filename = f"{page_name.lower()}.html"
            page_title = f"{page_name.title()} - {store_info.store_name}"

        # placeholder 이미지 URL을 로컬 경로로 치환
        # https://placehold.co/* 패턴을 images/*.png로 치환
        import re

        # 모든 이미지 태그에서 placeholder URL 찾기
        def replace_placeholder(match):
            # 이미지 키를 찾기 위해 alt 텍스트나 주변 컨텍스트 활용
            # 간단하게 순차적으로 매핑 적용
            return match.group(0)

        # 정규식으로 모든 placehold.co URL을 찾고 치환
        content_with_images = main_content

        # 각 이미지 키에 대해 치환 (정확한 매칭을 위해 순회)
        for image_key, local_path in image_mapping.items():
            # 이미지 키가 HTML에 포함된 경우 (data 속성이나 alt 텍스트에서 매칭)
            # 단순화: placehold.co/* 패턴을 순차적으로 치환
            pass

        # 모든 placehold.co 이미지를 생성된 이미지로 순차 치환
        placeholder_pattern = r'src="https://placehold\.co/[^"]*"'
        placeholders = re.findall(placeholder_pattern, content_with_images)

        # 이미지 매핑을 순서대로 적용
        image_keys_list = list(image_mapping.keys())
        for idx, placeholder in enumerate(placeholders):
            if idx < len(image_keys_list):
                image_key = image_keys_list[idx]
                local_path = image_mapping[image_key]
                content_with_images = content_with_images.replace(
                    placeholder, f'src="{local_path}"', 1  # 한 번만 치환
                )

        # 완전한 HTML 문서 조합
        full_html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{page_title}</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50">
{header_html}
{content_with_images}
{footer_html}
</body>
</html>"""

        html_path = output_dir / filename
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(full_html)
        html_paths.append(html_path)

    # GeneratedCode 객체 생성 (첫 번째 완전한 HTML을 대표로, CSS는 빈 문자열)
    first_page_name = next(iter(html_codes.keys())) if html_codes else ""
    if first_page_name:
        first_main = html_codes[first_page_name]
        first_full_html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{store_info.store_name}</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50">
{header_html}
{first_main}
{footer_html}
</body>
</html>"""
    else:
        first_full_html = ""

    generated_code = GeneratedCode(
        html=first_full_html,
        css="",  # Tailwind CDN 사용으로 불필요
        assets={},
    )

    # 전략 문서 저장
    strategy_path = output_dir / "strategy.md"
    store_concept = state["store_concept"]
    marketing_strategy = state["marketing_strategy"]

    with open(strategy_path, "w", encoding="utf-8") as f:
        f.write(f"# {store_info.store_name} 광고 캠페인 전략\n\n")
        f.write(f"## 매장 정보\n")
        f.write(f"- 매장명: {store_info.store_name}\n")
        f.write(f"- 업종: {store_info.store_type}\n")
        f.write(f"- 목표: {store_info.advertising_goal}\n")
        f.write(f"- 예산: {store_info.budget}만원\n")
        f.write(f"- 기간: {store_info.period}일\n\n")

        f.write(f"## 매장 컨셉\n")
        f.write(f"- 핵심 메시지: {store_concept.core_message}\n")
        f.write(f"- 톤앤매너: {store_concept.tone_and_manner}\n")
        f.write(f"- 목표 감성: {', '.join(store_concept.target_emotions)}\n\n")

        f.write(f"## 마케팅 전략\n")
        f.write(f"- 필요 페이지: {', '.join(marketing_strategy.strategy.pages)}\n")
        f.write(f"- 주요 기능: {', '.join(marketing_strategy.strategy.features)}\n")
        f.write(f"- 마케팅 포커스: {marketing_strategy.strategy.marketing_focus}\n")
        f.write(f"- 핵심 메시지: {marketing_strategy.strategy.key_message}\n\n")

    # DOM Contract 저장 (DEPRECATED이지만 참고용으로 유지)
    dom_contract_path = output_dir / "dom_contract.json"
    with open(dom_contract_path, "w", encoding="utf-8") as f:
        json.dump(state["dom_contract"].model_dump(), f, ensure_ascii=False, indent=2)

    # Content Design 저장
    content_design_path = output_dir / "content_design.json"
    with open(content_design_path, "w", encoding="utf-8") as f:
        json.dump(state["content_design"].model_dump(), f, ensure_ascii=False, indent=2)

    # 로그 메시지 생성
    log_messages = [
        f"[Package Output (Header+Main+Footer)] 결과물 패키징 완료: {output_dir}",
        f"  - Header 길이: {len(header_html)}자",
        f"  - Footer 길이: {len(footer_html)}자",
    ]
    for html_path in html_paths:
        log_messages.append(f"  - 완전한 HTML: {html_path}")
    log_messages.extend(
        [
            f"  - 전략 문서: {strategy_path}",
            f"  - DOM Contract (참고용): {dom_contract_path}",
            f"  - Content Design: {content_design_path}",
        ]
    )

    return {
        "generated_code": generated_code,
        "output_path": str(output_dir),
        "logs": log_messages,
    }
