"""
LLM + MCP 통합 어댑터
OpenAI LLM이 자연어를 해석하여 MCP 도구를 호출하도록 지원
"""

import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve()
sys.path.insert(0, str(project_root))

import logging
from helper_dev_utils import get_auto_logger

logger = get_auto_logger()

from typing import Any, Dict, List, Optional
from openai import AsyncOpenAI
from .mcp_client import MCPClient, MCPClientError


class LLMAdapter:
    """
    LLM(OpenAI)과 MCP 서버를 연결하는 어댑터

    자연어 입력을 MCP 도구 호출로 변환하고,
    MCP 도구 실행 결과를 LLM에 전달하여 최종 응답 생성

    사용 예:
        async with LLMAdapter(openai_api_key, mcp_url) as adapter:
            response = await adapter.chat("product.png로 SALE 광고 만들어줘")
    """

    def __init__(
        self,
        openai_api_key: str,
        mcp_server_url: str = "http://localhost:3000",
        model: str = "gpt-5-mini",
        temperature: float = 1.0,
        max_completion_tokens: int = 128000,
    ):
        """
        Args:
            openai_api_key: OpenAI API 키
            mcp_server_url: MCP 서버 URL
            model: 사용할 OpenAI 모델
            temperature: LLM 온도 파라미터 (기본값: 1.0, gpt-5-mini는 1만 지원)
            max_completion_tokens: 최대 완성 토큰 수
        """
        self.openai_client = AsyncOpenAI(api_key=openai_api_key)
        self.mcp_client = MCPClient(base_url=mcp_server_url)
        self.model = model
        self.temperature = temperature
        self.max_completion_tokens = max_completion_tokens

        # 대화 히스토리
        self.conversation_history: List[Dict[str, Any]] = []

        # 마지막 도구 호출 파라미터 (재현성을 위해 저장)
        self.last_tool_call_params: Optional[Dict[str, Any]] = None

    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        await self.mcp_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        await self.mcp_client.__aexit__(exc_type, exc_val, exc_tb)

    def _parse_explicit_params(self, user_message: str) -> Dict[str, Any]:
        """
        사용자 메시지에서 명시적 파라미터 추출

        예: "bg_model=sdxl, start_step=1, 바나나 광고 만들어줘"
        → {'bg_model': 'sdxl', 'start_step': 1}

        Args:
            user_message: 사용자 메시지

        Returns:
            파싱된 파라미터 딕셔너리
        """
        import re

        params = {}

        # key=value 패턴 추출 (쉼표 또는 공백으로 구분)
        pattern = r"(\w+)\s*=\s*([^\s,]+)"
        matches = re.findall(pattern, user_message)

        for key, value in matches:
            # 타입 변환 시도
            if value.lower() in ("true", "false"):
                params[key] = value.lower() == "true"
            elif value.isdigit():
                params[key] = int(value)
            elif value.replace(".", "", 1).isdigit():
                params[key] = float(value)
            else:
                params[key] = value

        if params:
            logger.info(f"명시적 파라미터 파싱됨: {params}")

        return params

    def _build_system_prompt(
        self,
        user_message: str,
        max_tool_calls: int = 5,
        explicit_params: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        사용자 메시지를 분석하여 작업 유형별 최적 system prompt 생성

        작업 유형:
        - 생성: generate_ad_image, generate_background_only, generate_text_asset_only
        - 조회/관리: check_*, get_*, delete_*, stop_*
        - 추천: recommend_font_for_ad, get_fonts_metadata

        Args:
            user_message: 사용자 메시지
            max_tool_calls: 최대 도구 호출 횟수 (1=즉시실행, >1=대화모드)
            explicit_params: 사용자가 명시적으로 지정한 파라미터 (예: {'bg_model': 'sdxl'})

        Returns:
            작업 유형에 최적화된 system prompt
        """
        msg_lower = user_message.lower()

        # 생성 키워드 감지
        generation_keywords = [
            "만들어",
            "생성",
            "광고",
            "배경",
            "텍스트",
            "합성",
            "create",
            "generate",
            "make",
            "ad",
            "background",
        ]
        is_generation = any(kw in msg_lower for kw in generation_keywords)

        # 조회/관리 키워드 감지
        query_keywords = [
            "확인",
            "조회",
            "상태",
            "삭제",
            "중단",
            "목록",
            "check",
            "status",
            "delete",
            "stop",
            "list",
            "get",
        ]
        is_query = any(kw in msg_lower for kw in query_keywords)

        if is_generation and not is_query:
            # 생성 작업: max_tool_calls에 따라 모드 결정
            base_prompt = "당신은 나노코코아(nanoCocoa) AI 광고 생성 시스템의 전문 어시스턴트입니다.\n\n"

            # max_tool_calls=1이면 즉시 실행 모드
            if max_tool_calls == 1:
                base_prompt += (
                    "[즉시 실행 모드]\n"
                    "사용자 확인 없이 바로 적절한 도구를 호출하세요.\n"
                    "추가 질문이나 선택지(A/B/C)를 제시하지 마세요.\n"
                    "도구 호출 결과만 간단히 요약하여 응답하세요.\n\n"
                )
            else:
                base_prompt += (
                    "[대화 모드 - 2단계 프로세스]\n\n"
                    "### 1단계: 기획 및 의견 교환 (도구 호출 없음)\n"
                    "- 제품/서비스 정보 파악\n"
                    "- 타겟 고객층 확인\n"
                    "- 광고 톤앤매너 결정 (세일/프리미엄/캐주얼)\n"
                    "- 핵심 메시지 및 카피 제안\n"
                    "- 비주얼 컨셉 제안\n"
                    "- 폰트 추천 (필요 시 recommend_font 도구 사용)\n"
                    "- bg_model 선택 가이드 제공 (sdxl vs flux)\n\n"
                    "### 2단계: 최종 확인 및 생성 실행\n"
                    "**중요:** 사용자가 다음 표현을 **명확히** 사용할 때만 도구 호출:\n"
                    '  - "생성해줘", "만들어줘", "광고 생성", "시작", "실행"\n'
                    '  - "지금 만들어", "이제 생성", "OK 생성", "확인 생성"\n'
                    '  - "배경만 만들어줘", "배경만 생성", "텍스트 추가해줘", "글자 넣어줘"\n'
                    '  - 영어: "generate", "create now", "start generation", "add text"\n\n'
                    "**도구 호출 전 확인 금지 표현:**\n"
                    '  - "어떤가요?", "괜찮나요?", "의견 있으세요?", "수정할 부분?", "의견은?"\n'
                    "  - 이런 질문은 **기획 단계**이므로 도구 호출하지 말 것\n\n"
                    "**생성 후 추가 대화:**\n"
                    "  - 광고가 이미 생성되었으면 추가 의견 교환 시 **새로운 광고 생성하지 말 것**\n"
                    '  - "새 광고", "다시 생성", "another one" 등 명시적 요청 시에만 재생성\n\n'
                )

            base_prompt += (
                "**[핵심 원칙]**\n"
                "generate_ad_image 호출 시 optional 파라미터를 MUST 생성하세요.\n\n"
                "**[배경 모델 선택 (bg_model)] - 필수 생성**\n"
                "**중요:** bg_model은 ALWAYS 명시적으로 설정해야 합니다. 생략 금지!\n\n"
                + (
                    f"**사용자 명시 파라미터:** {explicit_params}\n"
                    f"**우선순위 1: 사용자가 'bg_model={explicit_params.get('bg_model')}'를 명시했으므로 반드시 이 값 사용!**\n\n"
                    if explicit_params and "bg_model" in explicit_params
                    else ""
                )
                + "**우선순위 규칙:**\n"
                "1. **사용자가 'bg_model=sdxl' 또는 'bg_model=flux'를 직접 명시한 경우**: 해당 값 우선 사용\n"
                "2. **키워드 기반 자동 선택** (명시 없을 때):\n\n"
                "**'sdxl' 사용 조건** (다음 키워드 포함 시):\n"
                "  - 속도: '빠르게', '빨리', '신속', '급하게', 'quick', 'fast', 'rapid'\n"
                "  - 간소화: '심플', '간단', '기본', '테스트', 'simple', 'basic', 'preview'\n"
                "  - 예: '빠른 배경 이미지' → bg_model='sdxl'\n"
                "  - guidance_scale은 자동으로 7.5 조정됨\n\n"
                "**'flux' 사용 조건** (기본값):\n"
                "  - 고품질: '고품질', '디테일', '포토리얼', 'high-quality', 'photorealistic'\n"
                "  - 속도 키워드 없음\n"
                "  - 예: '바나나 광고', '배경 생성' → bg_model='flux'\n"
                "  - guidance_scale 기본 3.5 권장\n\n"
                "**[제품 이미지 제공 여부에 따른 처리]**\n"
                "1. **제품 이미지 있음**: product_image_path 제공 + background_prompt는 배경만 설명\n"
                '   - 예: "Elegant marble surface with soft lighting, luxury background"\n'
                "2. **제품 이미지 없음**: product_image_path 생략 + background_prompt에 제품+배경 모두 설명\n"
                '   - 예: "Premium red apples on golden traditional Korean bojagi cloth, \n'
                "           juicy and fresh, photorealistic, Korean ink painting style background \n"
                '           with magpie and yut game elements"\n\n'
                "**[부분 생성 요청 감지 및 도구 선택]**\n"
                '- **"배경만"**: generate_background_only 도구 사용 또는 generate_ad_image에 stop_step=1, text_content=None\n'
                '- **"텍스트만 추가", "글자 넣어줘"**: generate_text_asset_only 도구 사용 (step1_image 필요)\n'
                '- **"합성만"**: compose_final_image 도구 사용 (step1_image, step2_image 필요)\n'
                '- **"배경 + 텍스트만"**: generate_ad_image에 stop_step=2\n\n'
                "**[필수 생성 파라미터]**\n"
                "0. **bg_model**: 'sdxl' 또는 'flux' (위 조건에 따라)\n\n"
                "1. **background_prompt** (100단어 이상, 영문)\n"
                "   - 제품 이미지 제공 시: 배경만 상세 설명\n"
                "   - 제품 이미지 없을 시: 제품+배경 모두 상세 설명\n"
                "   - 조명, 색상, 분위기, 스타일 포함\n\n"
                "2. **background_negative_prompt** (8-15 keywords, 영문)\n"
                "   - 품질: blurry, low quality, distorted\n"
                "   - 조명: bad lighting, harsh shadows, overexposed\n"
                "   - 정리: cluttered, watermark, text, logo\n\n"
                "3. **bg_composition_prompt** (10-20 words, 영문)\n"
                "   - Product integration, lighting consistency, depth of field, color harmony\n\n"
                "4. **bg_composition_negative_prompt** (7-12 keywords, 영문)\n"
                "   - floating, disconnected, unrealistic shadows, mismatched lighting\n\n"
                "5. **text_prompt** (10-20 words, 영문, '3D render' 필수)\n"
                "   - Text style, font characteristics, readability, visual impact, brand tone\n\n"
                "6. **text_negative_prompt** (7-12 keywords, 영문)\n"
                "   - unreadable, distorted text, blurry fonts, poor contrast, illegible\n"
                "   - floor, ground, background, flat, 2D (텍스트가 바닥에 붙지 않도록)\n\n"
                "7. **composition_prompt** (12-25 words, 영문)\n"
                "   - Text integration, lighting/shadows, visual hierarchy, quality standards\n"
                "   - Text floating naturally with soft shadows, consistent lighting\n\n"
                "8. **composition_negative_prompt** (8-15 keywords, 영문)\n"
                "   - artificial looking, pasted on, halos, color mismatch, poor blending\n\n"
                "**[MCP 도구 목록]**\n"
                "1. **generate_ad_image**: 전체 파이프라인 또는 부분 실행 (stop_step 활용)\n"
                "   - 필수: bg_model, background_prompt, text_content, text_prompt\n"
                "   - 선택: product_image_path, composition_mode, wait_for_completion, stop_step\n"
                "2. **generate_background_only**: 배경만 생성 (Step 1 전용)\n"
                "3. **generate_text_asset_only**: 텍스트만 생성 (Step 2 전용, step1_image 필요)\n"
                "4. **compose_final_image**: 합성만 실행 (Step 3 전용, step1_image + step2_image 필요)\n"
                "5. **recommend_font**: 폰트 추천 (text_content, ad_type, tone, weight)\n"
                "6. **list_fonts_with_metadata**: 전체 폰트 목록\n\n"
                "**[stop_step 활용 시나리오]**\n"
                '1. **"배경만 만들어줘"**:\n'
                "   - 권장: generate_background_only 도구 사용\n"
                "   - 대안: generate_ad_image에 stop_step=1, text_content=None\n"
                '2. **"이 이미지에 텍스트만 추가해줘"**:\n'
                "   - 권장: generate_text_asset_only 도구 사용\n"
                "   - 파라미터: step1_image_path, text_content, text_prompt\n"
                '3. **"이미지 두 개 합성만 해줘"**:\n'
                "   - 권장: compose_final_image 도구 사용\n"
                "   - 파라미터: step1_image_path (배경), step2_image_path (텍스트)\n"
                '4. **"배경과 텍스트만 생성하고 합성은 나중에"**:\n'
                "   - generate_ad_image에 stop_step=2\n\n"
                "**[예시]**\n"
                "사용자: 바나나 특가 광고 만들어줘\n"
                'AI (기획): "바나나 특가 광고를 기획해 드리겠습니다.\n'
                "  - 컨셉: 신선함과 활기를 강조하는 한국 시장 분위기\n"
                "  - 배경: 전통 시장의 과일 진열대, 따뜻한 조명\n"
                "  - 텍스트: '특가 세일' 또는 '바나나 할인' (어떤 카피를 원하시나요?)\n"
                "  - 폰트: 굵고 생동감 있는 스타일 추천\n"
                "  생성을 원하시면 '생성해줘'라고 말씀해주세요.\"\n\n"
                "사용자: 생성해줘\n"
                "AI (실행): generate_ad_image(\n"
                "  bg_model='flux',\n"
                "  background_prompt='Vibrant Korean traditional market scene with colorful fruit stalls, '\n"
                "                   'warm golden lighting, fresh bananas displayed on wooden crates, '\n"
                "                   'authentic market atmosphere with soft bokeh background, '\n"
                "                   'photorealistic quality, inviting and appetizing presentation',\n"
                "  background_negative_prompt='blurry, cluttered, watermark, harsh shadows, text, logo, '\n"
                "                            'overexposed, bad lighting, low quality, distorted',\n"
                "  text_content='바나나 특가',\n"
                "  text_prompt='Bold 3D Korean text with vibrant yellow-gold gradient, glossy metallic surface, '\n"
                "              'energetic style, high readability, dynamic composition, 3D render',\n"
                "  text_negative_prompt='floor, ground, background, flat, 2D, unreadable, blurry fonts, '\n"
                "                      'poor contrast, illegible, distorted text',\n"
                "  bg_composition_prompt='Banana naturally integrated with warm market lighting, realistic depth of field, '\n"
                "                       'harmonized color palette, seamless professional blend',\n"
                "  bg_composition_negative_prompt='floating, disconnected, unrealistic shadows, mismatched lighting, '\n"
                "                                'poor integration',\n"
                "  composition_prompt='Text floating naturally above market scene with soft shadows beneath, '\n"
                "                    'consistent warm lighting, clear visual hierarchy as focal point, '\n"
                "                    'professional overlay quality, smooth blending',\n"
                "  composition_negative_prompt='artificial looking, pasted on, halos, color mismatch, '\n"
                "                             'poorly integrated, visible edges, poor blending'\n"
                ")\n\n"
                "**[중요 규칙]**\n"
                "- **text_content**: 원문 언어 유지 (영어→영어, 한글→한글). 단위, 문맥 등은 적당하게 수정 가능\n"
                "- **모든 prompt 파라미터**: 영문으로 작성 (background_prompt, text_prompt, ...prompt 등)\n"
                "- **background_prompt**: 100단어 이상 상세 작성\n"
                "- **wait_for_completion**: 기본값 false (비동기 처리, job_id 즉시 반환)\n"
                "- **composition_mode**: 기본값 'overlay' 사용\n"
            )
            return base_prompt

        elif is_query:
            # 조회/관리 작업: 간결한 프롬프트
            return (
                "당신은 광고 이미지 생성 시스템 관리 AI입니다.\n\n"
                "[역할]\n"
                "- 작업 상태 조회: check_generation_status(job_id)\n"
                "- 서버 상태: check_server_health()\n"
                "- 작업 목록: get_all_jobs()\n"
                "- 작업 삭제: delete_job(job_id) 또는 delete_all_jobs()\n"
                "- 작업 중단: stop_generation(job_id)\n\n"
                "[지침]\n"
                "사용자 요청을 정확히 파악하여 적절한 도구를 호출하세요.\n"
                "job_id는 사용자가 제공하거나 이전 대화에서 추출하세요."
            )

        else:
            # 추천/기타 작업: 균형잡힌 프롬프트
            return (
                "당신은 광고 이미지 생성 전문 AI입니다.\n\n"
                "[주요 기능]\n"
                "1. 광고 생성: generate_ad_image (상세 파라미터 필요)\n"
                "2. 폰트 추천: recommend_font_for_ad(text_content, ad_type, tone, weight)\n"
                "3. 폰트 메타데이터: get_fonts_metadata(), list_available_fonts()\n"
                "4. 작업 관리: check_*, get_*, delete_*, stop_*\n\n"
                "[광고 생성 시 필수]\n"
                "bg_model (sdxl/flux), background_prompt (100단어 이상), background_negative_prompt, "
                "bg_composition_prompt, bg_composition_negative_prompt, text_prompt, text_negative_prompt, "
                "composition_prompt, composition_negative_prompt를 영문으로 생성하세요.\n"
                "text_content는 원문 언어를 유지하세요.\n\n"
                "[폰트 추천 시]\n"
                "ad_type: sale/premium/casual/promotion\n"
                "tone: energetic/elegant/friendly/modern\n"
                "weight: light/bold/heavy"
            )

    async def chat(
        self,
        user_message: str,
        max_tool_calls: int = 5,
    ) -> tuple[str, Optional[Dict[str, Any]]]:
        """
        자연어 메시지를 처리하여 응답 생성

        내부적으로 LLM이 필요시 MCP 도구를 호출하고,
        결과를 종합하여 최종 응답을 생성

        Args:
            user_message: 사용자 메시지
            max_tool_calls: 최대 도구 호출 횟수

        Returns:
            (LLM의 최종 응답 텍스트, 사용된 도구 파라미터 또는 None)
        """
        # 사용자 메시지에서 명시적 파라미터 파싱 (예: "bg_model=sdxl, ...")
        explicit_params = self._parse_explicit_params(user_message)

        # 시스템 프롬프트 추가 (첫 메시지인 경우에만)
        if not self.conversation_history:
            system_prompt = self._build_system_prompt(
                user_message, max_tool_calls, explicit_params
            )
            self.conversation_history.append(
                {"role": "system", "content": system_prompt}
            )

        # 사용자 메시지 추가
        self.conversation_history.append({"role": "user", "content": user_message})

        # MCP 도구 목록 조회
        tools = await self._get_mcp_tools_schema()

        # LLM과 대화 (도구 호출 포함)
        tool_call_count = 0

        while tool_call_count < max_tool_calls:
            # LLM 호출
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=self.conversation_history,
                tools=tools,
                temperature=self.temperature,
                max_completion_tokens=self.max_completion_tokens,
            )

            message = response.choices[0].message

            # 도구 호출이 없으면 종료
            if not message.tool_calls:
                self.conversation_history.append(
                    {"role": "assistant", "content": message.content}
                )
                return message.content, self.last_tool_call_params

            # 어시스턴트 메시지 추가
            self.conversation_history.append(
                {
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [tc.dict() for tc in message.tool_calls],
                }
            )

            # 도구 호출 실행
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                # [디버그] LLM이 선택한 파라미터 로깅
                if tool_name == "generate_ad_image":
                    logger.info("=" * 60)
                    logger.info("[LLM 도구 호출] generate_ad_image")
                    logger.info(f"  bg_model: {tool_args.get('bg_model', 'NOT_SET')}")
                    logger.info(f"  stop_step: {tool_args.get('stop_step', 'NOT_SET')}")
                    logger.info(
                        f"  text_content: {tool_args.get('text_content', 'NOT_SET')}"
                    )
                    bg_prompt = tool_args.get("background_prompt", "NOT_SET")
                    if bg_prompt != "NOT_SET":
                        logger.info(f"  background_prompt: {bg_prompt[:100]}...")
                    else:
                        logger.info(f"  background_prompt: {bg_prompt}")
                    logger.info("[LLM이 생성한 전체 파라미터]")
                    for key, value in tool_args.items():
                        if key not in [
                            "background_prompt",
                            "bg_model",
                            "stop_step",
                            "text_content",
                        ]:
                            val_str = str(value)[:80] if value else "None"
                            logger.info(f"    {key}: {val_str}")
                    logger.info("=" * 60)

                # generate_ad_image 필수 optional 파라미터 자동 생성 (누락 시)
                if tool_name == "generate_ad_image":
                    # 명시적 파라미터가 있으면 강제 적용 (유효한 파라미터만)
                    if explicit_params:
                        # generate_ad_image의 유효한 파라미터 목록
                        valid_params = {
                            "product_image_path",
                            "background_prompt",
                            "text_content",
                            "text_prompt",
                            "font_name",
                            "background_negative_prompt",
                            "text_negative_prompt",
                            "composition_negative_prompt",
                            "composition_mode",
                            "text_position",
                            "bg_composition_prompt",
                            "bg_composition_negative_prompt",
                            "composition_prompt",
                            "strength",
                            "guidance_scale",
                            "composition_strength",
                            "composition_steps",
                            "composition_guidance_scale",
                            "auto_unload",
                            "seed",
                            "test_mode",
                            "wait_for_completion",
                            "save_output_path",
                            "stop_step",
                            "bg_model",
                        }

                        for key, value in explicit_params.items():
                            if key in valid_params:
                                # stop_step 검증 (MCP 서버 제약: 1-3)
                                if key == "stop_step" and not (1 <= value <= 3):
                                    logger.warning(
                                        f"[명시적 파라미터 무시] {key}={value} (유효 범위: 1-3, 1=배경만/2=텍스트까지/3=전체)"
                                    )
                                    continue

                                if key not in tool_args or tool_args[key] != value:
                                    logger.info(
                                        f"[명시적 파라미터 적용] {key}={value} (LLM이 생성한 값: {tool_args.get(key, 'None')} → 덮어쓰기)"
                                    )
                                    tool_args[key] = value
                            else:
                                logger.warning(
                                    f"[명시적 파라미터 무시] {key}={value} (generate_ad_image에서 지원하지 않는 파라미터)"
                                )

                    if not tool_args.get("bg_composition_prompt"):
                        tool_args["bg_composition_prompt"] = (
                            "Product naturally integrated with consistent lighting, "
                            "matching ambient shadows, proper depth of field, "
                            "harmonized color palette, seamless professional blend"
                        )
                        logger.info("bg_composition_prompt 자동 생성됨 (기본값)")

                    if not tool_args.get("bg_composition_negative_prompt"):
                        tool_args["bg_composition_negative_prompt"] = (
                            "floating, disconnected, unrealistic shadows, "
                            "mismatched lighting, pasted on, poor integration"
                        )
                        logger.info(
                            "bg_composition_negative_prompt 자동 생성됨 (기본값)"
                        )

                    if not tool_args.get("text_prompt"):
                        tool_args["text_prompt"] = (
                            "Bold professional typography with high readability, "
                            "strong visual impact, consistent brand tone, "
                            "clean font characteristics, optimized legibility"
                        )
                        logger.info("text_prompt 자동 생성됨 (기본값)")

                    if not tool_args.get("text_negative_prompt"):
                        tool_args["text_negative_prompt"] = (
                            "unreadable, distorted text, blurry fonts, "
                            "poor contrast, illegible, warped letters"
                        )
                        logger.info("text_negative_prompt 자동 생성됨 (기본값)")

                    if not tool_args.get("composition_prompt"):
                        tool_args["composition_prompt"] = (
                            "Text floating naturally above background with soft shadows beneath, "
                            "consistent atmospheric lighting, clear visual hierarchy as focal point, "
                            "professional overlay quality, smooth blending"
                        )
                        logger.info("composition_prompt 자동 생성됨 (기본값)")

                    if not tool_args.get("composition_negative_prompt"):
                        tool_args["composition_negative_prompt"] = (
                            "artificial looking, pasted on, poorly integrated, "
                            "color mismatch, halos, visible edges, poor blending"
                        )
                        logger.info("composition_negative_prompt 자동 생성됨 (기본값)")

                    if not tool_args.get("background_negative_prompt"):
                        tool_args["background_negative_prompt"] = (
                            "blurry, low quality, bad lighting, cluttered, watermark, "
                            "harsh shadows, overexposed, unprofessional"
                        )
                        logger.info("background_negative_prompt 자동 생성됨 (기본값)")

                # 재현성을 위해 실제 사용된 파라미터 저장
                if tool_name == "generate_ad_image":
                    self.last_tool_call_params = {
                        "tool_name": tool_name,
                        "parameters": tool_args.copy(),
                    }

                logger.info(f"MCP 도구 호출 tool_name={tool_name}")
                logger.info(f"MCP 도구 호출 tool_args={tool_args}")

                try:
                    result = await self.mcp_client.call_tool(tool_name, tool_args)
                    tool_result = str(result)
                    logger.info(f"MCP 도구 호출 성공: {tool_result[:200]}...")
                except MCPClientError as e:
                    tool_result = f"에러: {e}"
                    logger.error(f"MCP 도구 호출 실패: {e}")
                except Exception as e:
                    tool_result = f"예외: {e}"
                    logger.error(f"MCP 도구 호출 예외: {e}")

                # 도구 결과 추가
                self.conversation_history.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result,
                    }
                )

            tool_call_count += 1

        # 최대 호출 횟수 초과
        logger.warning(f"최대 도구 호출 횟수({max_tool_calls}) 초과")
        return "작업을 완료할 수 없습니다. 너무 많은 도구 호출이 필요합니다.", None

    async def _get_mcp_tools_schema(self) -> List[Dict[str, Any]]:
        """
        MCP 도구 목록을 OpenAI Function Calling 스키마로 변환

        Returns:
            OpenAI tools 스키마 리스트
        """
        mcp_tools = await self.mcp_client.list_tools()

        openai_tools = []
        for tool in mcp_tools:
            openai_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get(
                            "parameters",
                            tool.get(
                                "inputSchema", {"type": "object", "properties": {}}
                            ),
                        ),
                    },
                }
            )

        return openai_tools
