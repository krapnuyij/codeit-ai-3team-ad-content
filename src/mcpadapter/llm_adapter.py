"""
LLM + MCP 통합 어댑터
OpenAI LLM이 자연어를 해석하여 MCP 도구를 호출하도록 지원
"""

import json
import logging
from typing import Any, Dict, List, Optional
from openai import AsyncOpenAI

from .mcp_client import MCPClient, MCPClientError

logger = logging.getLogger(__name__)


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

                logger.info(f"MCP 도구 호출: {tool_name}")

                try:
                    result = await self.mcp_client.call_tool(tool_name, tool_args)
                    tool_result = str(result)
                except MCPClientError as e:
                    tool_result = f"에러: {e}"

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
