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
        model: str = "gpt-4o",
        temperature: float = 1.0,
        max_completion_tokens: int = 4000,
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

    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        await self.mcp_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        await self.mcp_client.__aexit__(exc_type, exc_val, exc_tb)

    def _build_system_prompt(self, user_message: str, max_tool_calls: int = 5) -> str:
        """
        사용자 메시지를 분석하여 작업 유형별 최적 system prompt 생성

        작업 유형:
        - 생성: generate_ad_image, generate_background_only, generate_text_asset_only
        - 조회/관리: check_*, get_*, delete_*, stop_*
        - 추천: recommend_font_for_ad, get_fonts_metadata

        Args:
            user_message: 사용자 메시지
            max_tool_calls: 최대 도구 호출 횟수 (1=즉시실행, >1=대화모드)

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
            base_prompt = "당신은 광고 이미지 생성 전문 AI입니다.\n\n"

            # max_tool_calls=1이면 즉시 실행 모드
            if max_tool_calls == 1:
                base_prompt += (
                    "⚡ [즉시 실행 모드]\n"
                    "사용자 확인 없이 바로 generate_ad_image 도구를 호출하세요.\n"
                    "추가 질문이나 선택지(A/B/C)를 제시하지 마세요.\n"
                    "도구 호출 결과만 간단히 요약하여 응답하세요.\n\n"
                )
            else:
                base_prompt += (
                    "💬 [대화 모드]\n"
                    "필요시 사용자에게 옵션을 제시하고 확인을 받은 후 도구를 호출하세요.\n\n"
                )

            base_prompt += (
                "[핵심 원칙]\n"
                "generate_ad_image 호출 시 optional 파라미터를 MUST 생성하세요.\n\n"
                "[필수 생성 파라미터]\n"
                "1. background_negative_prompt (8-15 keywords)\n"
                "   품질: blurry, low quality, distorted\n"
                "   조명: bad lighting, harsh shadows, overexposed\n"
                "   정리: cluttered, watermark, text, logo\n\n"
                "2. bg_composition_prompt (10-20 words)\n"
                "   Product integration, lighting consistency, depth of field, color harmony\n\n"
                "3. bg_composition_negative_prompt (7-12 keywords)\n"
                "   floating, disconnected, unrealistic shadows, mismatched lighting\n\n"
                "4. text_prompt (10-20 words)\n"
                "   Text style, font characteristics, readability, visual impact, brand tone\n\n"
                "5. text_negative_prompt (7-12 keywords)\n"
                "   unreadable, distorted text, blurry fonts, poor contrast, illegible\n\n"
                "6. composition_prompt (12-25 words)\n"
                "   Text integration, lighting/shadows, visual hierarchy, quality standards\n\n"
                "7. composition_negative_prompt (8-15 keywords)\n"
                "   artificial looking, pasted on, halos, color mismatch, poor blending\n\n"
                "[예시]\n"
                "사용자: 바나나 특가 광고 만들어줘\n"
                "AI: generate_ad_image(\n"
                "  background_prompt='Vibrant Korean market, colorful fruit stalls...',\n"
                "  background_negative_prompt='blurry, cluttered, watermark, harsh shadows',\n"
                "  bg_composition_prompt='Banana naturally placed, matching warm lighting, realistic depth',\n"
                "  bg_composition_negative_prompt='floating, disconnected, unrealistic shadows',\n"
                "  text_prompt='Bold 3D Korean text with yellow-gold gradient, glossy surface',\n"
                "  text_negative_prompt='floor, ground, background, flat, 2D, blurry fonts',\n"
                "  composition_prompt='Text floating naturally with soft shadows, consistent lighting',\n"
                "  composition_negative_prompt='artificial looking, halos, color mismatch'\n"
                ")\n\n"
                "모든 프롬프트는 영문으로 작성하세요."
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
                "2. 폰트 추천: recommend_font_for_ad(text_content, ad_type, tone)\n"
                "3. 폰트 메타데이터: get_fonts_metadata(), list_available_fonts()\n"
                "4. 작업 관리: check_*, get_*, delete_*, stop_*\n\n"
                "[광고 생성 시 필수]\n"
                "background_negative_prompt, bg_composition_prompt, "
                "bg_composition_negative_prompt, text_prompt, text_negative_prompt, "
                "composition_prompt, composition_negative_prompt를 영문으로 생성하세요.\n\n"
                "[폰트 추천 시]\n"
                "ad_type: sale/premium/casual/promotion\n"
                "tone: energetic/elegant/friendly/modern"
            )

    async def chat(
        self,
        user_message: str,
        max_tool_calls: int = 5,
    ) -> str:
        """
        자연어 메시지를 처리하여 응답 생성

        내부적으로 LLM이 필요시 MCP 도구를 호출하고,
        결과를 종합하여 최종 응답을 생성

        Args:
            user_message: 사용자 메시지
            max_tool_calls: 최대 도구 호출 횟수

        Returns:
            LLM의 최종 응답 텍스트
        """
        # 시스템 프롬프트 추가 (첫 메시지인 경우에만)
        if not self.conversation_history:
            system_prompt = self._build_system_prompt(user_message, max_tool_calls)
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
                return message.content

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

                # generate_ad_image 필수 optional 파라미터 자동 생성 (누락 시)
                if tool_name == "generate_ad_image":
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
        return "작업을 완료할 수 없습니다. 너무 많은 도구 호출이 필요합니다."

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
