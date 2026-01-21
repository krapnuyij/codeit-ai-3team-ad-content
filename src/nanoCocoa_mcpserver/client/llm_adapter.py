"""
LLM-MCP 어댑터
OpenAI LLM과 MCP 서버를 연결하는 어댑터
"""

import asyncio
import json
import logging
import sys
import os
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from typing import Any, Dict, List, Optional, Literal
from pathlib import Path

from openai import AsyncOpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from helper_dev_utils import get_auto_logger

logger = get_auto_logger()


class LLMMCPAdapter:
    """
    OpenAI LLM과 MCP 서버를 연결하는 어댑터 클래스

    LLM의 자연어 입력을 MCP 도구 호출로 변환하고,
    MCP 도구 실행 결과를 LLM에 전달하여 최종 응답 생성
    """

    def __init__(
        self,
        openai_api_key: str,
        model: str = "gpt-5-mini",
        mcp_server_command: str = "python",
        mcp_server_args: Optional[List[str]] = None,
        conda_env: str = "py311_ad",
        temperature: float = 0.7,
        max_completion_tokens: int = 4000,
    ):
        """
        Args:
            openai_api_key: OpenAI API 키
            model: 사용할 OpenAI 모델 (기본값: gpt-5-mini)
            mcp_server_command: MCP 서버 실행 명령어 (기본값: python)
            mcp_server_args: MCP 서버 실행 인자 리스트
            conda_env: 사용할 conda 환경 이름 (기본값: py311_ad)
            temperature: LLM 온도 파라미터
            max_completion_tokens: 최대 완성 토큰 수 (gpt-5 시리즈 모델에서 사용)
        """
        self.client = AsyncOpenAI(api_key=openai_api_key)
        self.model = model
        self.temperature = temperature
        self.max_completion_tokens = max_completion_tokens

        # MCP 서버 설정
        # conda 환경의 파이썬을 직접 사용 (stdio 통신 보장)
        if mcp_server_args is None:
            import subprocess

            # conda 환경의 파이썬 경로 찾기
            result = subprocess.run(
                ["conda", "run", "-n", conda_env, "which", "python"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0 or not result.stdout.strip():
                raise RuntimeError(
                    f"conda 환경 '{conda_env}'의 파이썬을 찾을 수 없습니다\n"
                    f"stderr: {result.stderr}"
                )

            self.mcp_server_command = result.stdout.strip()
            self.mcp_server_args = [
                "-m",
                "src.nanoCocoa_mcpserver.server",
            ]
            logger.info(f"MCP 서버 파이썬 경로: {self.mcp_server_command}")
        else:
            self.mcp_server_command = mcp_server_command
            self.mcp_server_args = mcp_server_args

        # MCP 세션 (lazy initialization)
        self._mcp_session: Optional[ClientSession] = None
        self._mcp_read = None
        self._mcp_write = None
        self._stdio_context = None

        # 대화 히스토리
        self.conversation_history: List[Dict[str, Any]] = []

    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        await self.connect_mcp()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        await self.disconnect_mcp()

    async def connect_mcp(self) -> None:
        """MCP 서버에 연결"""
        if self._mcp_session is not None:
            logger.warning("MCP 세션이 이미 연결되어 있습니다")
            return

        logger.info(
            f"MCP 서버 연결 중: {self.mcp_server_command} {' '.join(self.mcp_server_args)}"
        )

        project_root = Path(__file__).parent.parent.parent.parent

        server_params = StdioServerParameters(
            command=self.mcp_server_command,
            args=self.mcp_server_args,
            env={**os.environ, "PYTHONPATH": str(project_root)},
        )

        # stdio_client 컨텍스트 매니저 진입
        self._stdio_context = stdio_client(server_params)
        self._mcp_read, self._mcp_write = await self._stdio_context.__aenter__()

        # ClientSession 생성 및 초기화
        self._mcp_session = ClientSession(self._mcp_read, self._mcp_write)
        await self._mcp_session.__aenter__()

        # 초기화 핸드셰이크
        await self._mcp_session.initialize()

        logger.info("MCP 서버 연결 완료")

    async def disconnect_mcp(self) -> None:
        """MCP 서버 연결 해제"""
        if self._mcp_session is None:
            return

        logger.info("MCP 서버 연결 해제 중")

        try:
            await self._mcp_session.__aexit__(None, None, None)
            await self._stdio_context.__aexit__(None, None, None)
        except Exception as e:
            logger.error(f"MCP 연결 해제 중 오류: {e}")
        finally:
            self._mcp_session = None
            self._mcp_read = None
            self._mcp_write = None

        logger.info("MCP 서버 연결 해제 완료")

    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """
        MCP 서버에서 사용 가능한 도구 목록 조회

        Returns:
            OpenAI function calling 형식의 도구 목록
        """
        if self._mcp_session is None:
            raise RuntimeError(
                "MCP 서버가 연결되지 않았습니다. connect_mcp()를 먼저 호출하세요."
            )

        # MCP 도구 목록 조회
        tools_list = await self._mcp_session.list_tools()

        # OpenAI function calling 형식으로 변환
        openai_tools = []
        for tool in tools_list.tools:
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema,
                },
            }
            openai_tools.append(openai_tool)

        logger.info(f"사용 가능한 MCP 도구 {len(openai_tools)}개 로드됨")
        return openai_tools

    async def call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        MCP 도구 호출 실행

        Args:
            tool_name: 도구 이름
            arguments: 도구 인자 딕셔너리

        Returns:
            도구 실행 결과 (문자열)
        """
        if self._mcp_session is None:
            raise RuntimeError("MCP 서버가 연결되지 않았습니다")

        logger.info(f"MCP 도구 호출: {tool_name}")
        logger.debug(f"인자: {arguments}")

        try:
            result = await self._mcp_session.call_tool(tool_name, arguments)

            # 결과 추출
            if result.content:
                # TextContent인 경우
                if hasattr(result.content[0], "text"):
                    output = result.content[0].text
                else:
                    output = str(result.content[0])
            else:
                output = "도구 실행 완료 (출력 없음)"

            logger.info(f"MCP 도구 실행 완료: {tool_name}")
            return output

        except Exception as e:
            error_msg = f"MCP 도구 호출 실패 ({tool_name}): {str(e)}"
            logger.error(error_msg)
            return error_msg

    async def chat(
        self,
        user_message: str,
        image_files: Optional[Dict[str, str]] = None,
        system_prompt: Optional[str] = None,
        max_iterations: int = 10,
    ) -> str:
        """
        LLM과 대화하며 필요시 MCP 도구를 자동 호출

        Args:
            user_message: 사용자 메시지
            image_files: 이미지 파일 경로 딕셔너리 (키: 용도, 값: 파일경로)
                        예: {"product": "/path/to/image.png"}
                        LLM에게는 경로만 전달하고, 도구 호출 시 자동 Base64 변환
            system_prompt: 시스템 프롬프트 (선택)
            max_iterations: 최대 도구 호출 반복 횟수

        Returns:
            LLM의 최종 응답
        """
        if self._mcp_session is None:
            raise RuntimeError("MCP 서버가 연결되지 않았습니다")

        # 이미지 파일 경로를 임시 저장 (도구 호출 시 사용)
        self._temp_image_files = image_files or {}

        # 시스템 프롬프트 설정
        if system_prompt is None:
            system_prompt = (
                "당신은 nanoCocoa 광고 생성 AI 어시스턴트입니다. "
                "사용자가 광고 이미지 생성을 요청하면, 제공된 MCP 도구를 사용하여 "
                "전문적인 광고 이미지를 생성하세요. "
                "도구 호출 시 필요한 모든 파라미터를 명확히 전달하세요."
            )

        # 대화 히스토리 초기화 (새 대화 시작)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        # MCP 도구 목록 조회
        tools = await self.get_available_tools()

        # 반복 실행 (도구 호출 + LLM 응답)
        for iteration in range(max_iterations):
            logger.info(f"대화 반복 {iteration + 1}/{max_iterations}")

            # GPT-5/4.1/o1 계열은 temperature 미지원
            params = {
                "model": self.model,
                "messages": messages,
                "tools": tools,
                "max_completion_tokens": self.max_completion_tokens,
            }

            if not self.model.startswith(("gpt-5", "gpt-4.1", "o1")):
                params["temperature"] = self.temperature

            # LLM 호출
            response = await self.client.chat.completions.create(**params)

            assistant_message = response.choices[0].message

            # 도구 호출이 없으면 최종 응답 반환
            if not assistant_message.tool_calls:
                final_response = assistant_message.content or ""
                logger.info("LLM 최종 응답 생성 완료")

                # 대화 히스토리 저장
                self.conversation_history.extend(messages)
                self.conversation_history.append(
                    {"role": "assistant", "content": final_response}
                )

                return final_response

            # 도구 호출 처리
            messages.append(
                {
                    "role": "assistant",
                    "content": assistant_message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in assistant_message.tool_calls
                    ],
                }
            )

            # 각 도구 호출 실행
            for tool_call in assistant_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)

                logger.info(f"도구 호출 요청: {function_name}")

                # 이미지 파일 경로를 Base64로 자동 변환
                function_args = await self._convert_image_paths_to_base64(function_args)

                # MCP 도구 실행
                tool_result = await self.call_mcp_tool(function_name, function_args)

                # 도구 결과를 메시지에 추가
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result,
                    }
                )

        # 최대 반복 횟수 초과
        logger.warning(f"최대 반복 횟수({max_iterations}) 초과")
        return "죄송합니다. 요청 처리 중 최대 반복 횟수를 초과했습니다."

    async def simple_chat(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        도구 호출 없이 단순 LLM 대화

        Args:
            user_message: 사용자 메시지
            system_prompt: 시스템 프롬프트

        Returns:
            LLM 응답
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})

        # GPT-5/4.1/o1 계열은 temperature 미지원
        params = {
            "model": self.model,
            "messages": messages,
            "max_completion_tokens": self.max_completion_tokens,
        }

        if not self.model.startswith(("gpt-5", "gpt-4.1", "o1")):
            params["temperature"] = self.temperature

        response = await self.client.chat.completions.create(**params)

        return response.choices[0].message.content or ""

    async def _convert_image_paths_to_base64(
        self, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        도구 인자에서 이미지 파일 경로를 감지하고 Base64로 변환

        Args:
            arguments: 도구 호출 인자

        Returns:
            Base64로 변환된 인자
        """
        from ..utils.image_utils import image_file_to_base64

        converted_args = arguments.copy()

        # product_image_base64 필드가 있고 파일 경로인 경우 변환
        if "product_image_base64" in converted_args:
            value = converted_args["product_image_base64"]

            # 파일 경로인지 확인 (Base64는 매우 길고, 경로는 짧음)
            if isinstance(value, str) and len(value) < 500:
                image_path = Path(value)

                # 파일이 존재하면 변환
                if image_path.exists() and image_path.is_file():
                    logger.info(f"이미지 파일을 Base64로 변환: {image_path}")
                    converted_args["product_image_base64"] = image_file_to_base64(
                        str(image_path)
                    )

        return converted_args

    def clear_history(self) -> None:
        """대화 히스토리 초기화"""
        self.conversation_history.clear()
        logger.info("대화 히스토리 초기화됨")
