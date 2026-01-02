"""
mcp_server.py
nanoCocoa AI 광고 생성기를 위한 MCP (Model Context Protocol) 서버

이 MCP 서버는 FastAPI 엔드포인트를 LLM이 사용할 수 있는 도구로 노출합니다.
AI 어시스턴트가 광고 이미지를 생성할 수 있는 표준화된 인터페이스를 제공합니다.
"""

import asyncio
import base64
import json
import logging
from typing import Any, Optional, Sequence
import httpx

from mcp.server import Server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)
import mcp.server.stdio

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nanococoa-mcp-server")

# FastAPI 서버 설정
API_BASE_URL = "http://localhost:8000"
POLL_INTERVAL = 3  # 폴링 간격 (초)


class NanoCocoaMCPServer:
    """nanoCocoa AI 광고 생성기를 위한 MCP 서버"""

    def __init__(self, api_base_url: str = API_BASE_URL):
        """
        MCP 서버 초기화

        Args:
            api_base_url (str): FastAPI 서버의 기본 URL (기본값: http://localhost:8000)
        """
        self.api_base_url = api_base_url
        self.server = Server("nanococoa-ad-generator")
        self.client = httpx.AsyncClient(timeout=300.0)

        # 핸들러 등록
        self.server.list_tools = self.list_tools
        self.server.call_tool = self.call_tool
        self.server.list_resources = self.list_resources
        self.server.read_resource = self.read_resource

    async def list_tools(self) -> list[Tool]:
        """사용 가능한 도구 목록 반환"""
        return [
            Tool(
                name="health_check",
                description="""서버 상태 및 가용성을 확인합니다.

반환값:
- status: 'healthy' 또는 'busy'
- active_jobs: 실행 중인 작업 수
- system_metrics: CPU/RAM/GPU 사용률

새 작업을 시작하기 전에 서버 가용성을 확인하는 데 사용합니다.""",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="list_fonts",
                description="""텍스트 생성에 사용 가능한 폰트 목록을 가져옵니다.

반환값:
- fonts: 폰트 파일 경로 배열 (예: ["NanumGothic/NanumGothic.ttf"])

광고 생성 시 'font_name' 매개변수에 폰트 경로를 사용하세요.""",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="generate_ad",
                description="""새 광고 생성 작업을 시작합니다.

AI 생성 광고 이미지를 만드는 주요 도구입니다. 상품 이미지를 AI 생성 배경 및 3D 텍스트 효과와 결합합니다.

필수 매개변수:
- input_image: Base64 문자열로 인코딩된 상품 이미지
- bg_prompt: 영어로 작성된 배경 설명 (예: "luxury hotel lobby with warm lighting")

선택 매개변수:
- text_content: 표시할 텍스트 (배경만 생성하려면 비워두세요)
- text_model_prompt: 3D 텍스트 스타일 설명 (예: "gold metallic text with shadow")
- font_name: list_fonts에서 가져온 폰트 파일 경로
- composition_mode: "overlay", "blend", "behind" 중 하나
- text_position: "top", "center", "bottom", "auto" 중 하나
- start_step: 1 (전체 파이프라인), 2 (텍스트만), 3 (합성만)

반환값:
- job_id: check_job_status로 상태 확인 시 사용
- status: "started"

참고: 이 작업은 비차단 방식입니다. check_job_status를 사용하여 결과를 폴링하세요.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "input_image": {
                            "type": "string",
                            "description": "Base64 문자열로 인코딩된 상품 이미지",
                        },
                        "bg_prompt": {
                            "type": "string",
                            "description": "영어로 작성된 배경 장면 설명",
                        },
                        "text_content": {
                            "type": "string",
                            "description": "광고에 표시할 텍스트 (선택사항, 배경만 생성하려면 비워두세요)",
                        },
                        "text_model_prompt": {
                            "type": "string",
                            "description": "3D 텍스트 스타일 설명 (예: 'gold metallic text with shadow')",
                        },
                        "font_name": {
                            "type": "string",
                            "description": "list_fonts에서 가져온 폰트 파일 경로 (선택사항)",
                        },
                        "bg_negative_prompt": {
                            "type": "string",
                            "description": "배경에서 제외할 요소",
                        },
                        "negative_prompt": {
                            "type": "string",
                            "description": "텍스트에서 제외할 요소",
                        },
                        "composition_mode": {
                            "type": "string",
                            "enum": ["overlay", "blend", "behind"],
                            "description": "배경과 텍스트를 합성하는 방식",
                        },
                        "text_position": {
                            "type": "string",
                            "enum": ["top", "center", "bottom", "auto"],
                            "description": "텍스트 배치 위치",
                        },
                        "strength": {
                            "type": "number",
                            "description": "이미지 변환 강도 (0.0-1.0, 기본값: 0.6)",
                        },
                        "guidance_scale": {
                            "type": "number",
                            "description": "프롬프트 준수 강도 (1.0-20.0, 기본값: 3.5)",
                        },
                        "composition_strength": {
                            "type": "number",
                            "description": "합성 변환 강도 (0.0-1.0, 기본값: 0.4)",
                        },
                        "seed": {
                            "type": "integer",
                            "description": "재현성을 위한 난수 시드 (선택사항)",
                        },
                        "start_step": {
                            "type": "integer",
                            "enum": [1, 2, 3],
                            "description": "시작 단계: 1=전체 파이프라인, 2=텍스트만 (step1_image 필요), 3=합성만 (step1_image와 step2_image 필요)",
                        },
                        "step1_image": {
                            "type": "string",
                            "description": "start_step >= 2일 때 사용할 이전 배경 결과 (Base64)",
                        },
                        "step2_image": {
                            "type": "string",
                            "description": "start_step == 3일 때 사용할 이전 텍스트 결과 (Base64)",
                        },
                    },
                    "required": ["input_image", "bg_prompt"],
                },
            ),
            Tool(
                name="check_job_status",
                description="""생성 작업의 상태와 결과를 확인합니다.

매개변수:
- job_id: generate_ad에서 반환된 작업 ID

반환값:
- status: "pending", "running", "completed", "failed", "stopped" 중 하나
- progress_percent: 0-100 진행률
- current_step: 현재 파이프라인 단계
- message: 상태 메시지
- step1_result: 사용 가능할 때 배경 이미지 (Base64)
- step2_result: 사용 가능할 때 텍스트 이미지 (Base64)
- final_result: 완료 시 최종 합성 이미지 (Base64)
- system_metrics: 실시간 CPU/GPU 메트릭

상태가 'completed' 또는 'failed'가 될 때까지 3-5초마다 이 엔드포인트를 폴링하세요.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "job_id": {
                            "type": "string",
                            "description": "generate_ad에서 받은 작업 ID",
                        }
                    },
                    "required": ["job_id"],
                },
            ),
            Tool(
                name="stop_job",
                description="""실행 중인 생성 작업을 중지합니다.

매개변수:
- job_id: 중지할 작업 ID

반환값:
- job_id: 중지된 작업 ID
- status: "stopped"

너무 오래 걸리거나 잘못된 매개변수로 시작된 작업을 취소하는 데 사용합니다.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "job_id": {"type": "string", "description": "중지할 작업 ID"}
                    },
                    "required": ["job_id"],
                },
            ),
            Tool(
                name="list_jobs",
                description="""서버의 모든 작업 목록을 가져옵니다.

반환값:
- total_jobs: 전체 작업 수
- active_jobs: 실행 중/대기 중인 작업 수
- completed_jobs: 완료된 작업 수
- failed_jobs: 실패한 작업 수
- jobs: 작업 정보 배열

모든 작업과 현재 상태를 확인하는 데 사용합니다.""",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="delete_job",
                description="""완료되거나 실패한 작업을 서버 메모리에서 삭제합니다.

매개변수:
- job_id: 삭제할 작업 ID

반환값:
- job_id: 삭제된 작업 ID
- status: "deleted"

참고: 실행 중인 작업은 삭제할 수 없습니다. 먼저 stop_job으로 중지하세요.
완료된 작업을 정리하고 서버 메모리를 확보하는 데 사용합니다.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "job_id": {"type": "string", "description": "삭제할 작업 ID"}
                    },
                    "required": ["job_id"],
                },
            ),
            Tool(
                name="generate_and_wait",
                description="""광고 생성을 시작하고 완료될 때까지 대기합니다 (차단 방식).

generate_ad + check_job_status 폴링을 완료될 때까지 결합한 편의 도구입니다.

매개변수: generate_ad와 동일
- input_image: 상품 이미지 (Base64)
- bg_prompt: 배경 설명
- text_content: 광고 텍스트 (선택사항)
- ... (generate_ad의 모든 다른 매개변수)

반환값:
- final_result: Base64로 인코딩된 최종 이미지 (성공 시)
- step1_result: 배경 이미지 (Base64)
- step2_result: 텍스트 이미지 (Base64)
- status: 최종 상태
- 모든 작업 상태 정보

이 도구는 자동으로 서버를 폴링하고 작업이 완료되거나 실패할 때 반환합니다.
예상 소요 시간: 전체 파이프라인 80-120초.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "input_image": {
                            "type": "string",
                            "description": "Base64 문자열로 인코딩된 상품 이미지",
                        },
                        "bg_prompt": {
                            "type": "string",
                            "description": "영어로 작성된 배경 장면 설명",
                        },
                        "text_content": {
                            "type": "string",
                            "description": "광고에 표시할 텍스트 (선택사항)",
                        },
                        "text_model_prompt": {
                            "type": "string",
                            "description": "3D 텍스트 스타일 설명",
                        },
                        "font_name": {
                            "type": "string",
                            "description": "list_fonts에서 가져온 폰트 파일 경로",
                        },
                        "bg_negative_prompt": {"type": "string"},
                        "negative_prompt": {"type": "string"},
                        "composition_mode": {
                            "type": "string",
                            "enum": ["overlay", "blend", "behind"],
                        },
                        "text_position": {
                            "type": "string",
                            "enum": ["top", "center", "bottom", "auto"],
                        },
                        "strength": {"type": "number"},
                        "guidance_scale": {"type": "number"},
                        "composition_strength": {"type": "number"},
                        "seed": {"type": "integer"},
                        "start_step": {"type": "integer", "enum": [1, 2, 3]},
                        "step1_image": {"type": "string"},
                        "step2_image": {"type": "string"},
                    },
                    "required": ["input_image", "bg_prompt"],
                },
            ),
        ]

    async def call_tool(
        self, name: str, arguments: dict
    ) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        """
        도구 실행

        Args:
            name (str): 실행할 도구 이름
            arguments (dict): 도구 실행에 필요한 인자

        Returns:
            Sequence[TextContent | ImageContent | EmbeddedResource]: 도구 실행 결과
        """
        try:
            if name == "health_check":
                return await self._health_check()
            elif name == "list_fonts":
                return await self._list_fonts()
            elif name == "generate_ad":
                return await self._generate_ad(arguments)
            elif name == "check_job_status":
                return await self._check_job_status(arguments)
            elif name == "stop_job":
                return await self._stop_job(arguments)
            elif name == "list_jobs":
                return await self._list_jobs()
            elif name == "delete_job":
                return await self._delete_job(arguments)
            elif name == "generate_and_wait":
                return await self._generate_and_wait(arguments)
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]
        except Exception as e:
            logger.error(f"Error executing tool {name}: {e}", exc_info=True)
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    async def list_resources(self) -> list[Resource]:
        """사용 가능한 리소스 목록 반환"""
        return [
            Resource(
                uri="nanococoa://help/guide",
                name="API 사용 가이드",
                mimeType="application/json",
                description="워크플로우 및 예제가 포함된 완전한 API 사용 가이드",
            ),
            Resource(
                uri="nanococoa://help/parameters",
                name="매개변수 참조",
                mimeType="application/json",
                description="모든 API 엔드포인트에 대한 상세 매개변수 참조",
            ),
            Resource(
                uri="nanococoa://help/examples",
                name="사용 예제",
                mimeType="application/json",
                description="코드 스니펫이 포함된 실제 사용 예제",
            ),
        ]

    async def read_resource(self, uri: str) -> str:
        """
        리소스 읽기

        Args:
            uri (str): 읽을 리소스의 URI

        Returns:
            str: 리소스 내용 (JSON 형식)
        """
        try:
            if uri == "nanococoa://help/guide":
                response = await self.client.get(f"{self.api_base_url}/help")
                response.raise_for_status()
                return json.dumps(response.json(), indent=2)
            elif uri == "nanococoa://help/parameters":
                response = await self.client.get(f"{self.api_base_url}/help/parameters")
                response.raise_for_status()
                return json.dumps(response.json(), indent=2)
            elif uri == "nanococoa://help/examples":
                response = await self.client.get(f"{self.api_base_url}/help/examples")
                response.raise_for_status()
                return json.dumps(response.json(), indent=2)
            else:
                raise ValueError(f"Unknown resource: {uri}")
        except Exception as e:
            logger.error(f"Error reading resource {uri}: {e}")
            return f"Error reading resource: {str(e)}"

    async def _health_check(self) -> Sequence[TextContent]:
        """서버 상태 확인 구현"""
        response = await self.client.get(f"{self.api_base_url}/health")
        response.raise_for_status()
        data = response.json()

        return [TextContent(type="text", text=json.dumps(data, indent=2))]

    async def _list_fonts(self) -> Sequence[TextContent]:
        """폰트 목록 조회 구현"""
        response = await self.client.get(f"{self.api_base_url}/fonts")
        response.raise_for_status()
        data = response.json()

        return [TextContent(type="text", text=json.dumps(data, indent=2))]

    async def _generate_ad(self, arguments: dict) -> Sequence[TextContent]:
        """광고 생성 구현"""
        response = await self.client.post(
            f"{self.api_base_url}/generate", json=arguments
        )

        if response.status_code == 503:
            retry_after = response.headers.get("Retry-After", "unknown")
            data = response.json()
            return [
                TextContent(
                    type="text",
                    text=f"서버가 사용 중입니다. {data.get('message', '')} {retry_after}초 후 재시도하세요.\n\n"
                    + json.dumps(data, indent=2),
                )
            ]

        response.raise_for_status()
        data = response.json()

        return [
            TextContent(
                type="text",
                text=f"작업이 성공적으로 시작되었습니다!\n\n작업 ID: {data['job_id']}\n\n"
                + "진행 상황을 모니터링하려면 이 job_id로 'check_job_status' 도구를 사용하세요.\n\n"
                + json.dumps(data, indent=2),
            )
        ]

    async def _check_job_status(
        self, arguments: dict
    ) -> Sequence[TextContent | ImageContent]:
        """작업 상태 확인 구현"""
        job_id = arguments["job_id"]
        response = await self.client.get(f"{self.api_base_url}/status/{job_id}")
        response.raise_for_status()
        data = response.json()

        results = []

        # 상태 정보
        status_text = (
            f"작업 상태 보고서\n"
            f"================\n\n"
            f"작업 ID: {data['job_id']}\n"
            f"상태: {data['status']}\n"
            f"진행률: {data['progress_percent']}%\n"
            f"현재 단계: {data['current_step']}\n"
            f"메시지: {data['message']}\n"
            f"경과 시간: {data['elapsed_sec']}초\n"
        )

        if data.get("eta_seconds") is not None:
            status_text += f"예상 남은 시간: {data['eta_seconds']}초\n"

        status_text += f"\n전체 응답:\n{json.dumps(data, indent=2)}"

        results.append(TextContent(type="text", text=status_text))

        # 사용 가능한 이미지가 있으면 포함
        # 참고: MCP ImageContent는 데이터 URL을 기대하거나 base64로 임베드할 수 있습니다
        if data.get("final_result"):
            results.append(
                TextContent(
                    type="text",
                    text=f"\n\n최종 결과 사용 가능! (Base64 길이: {len(data['final_result'])} 문자)",
                )
            )

        return results

    async def _stop_job(self, arguments: dict) -> Sequence[TextContent]:
        """작업 중지 구현"""
        job_id = arguments["job_id"]
        response = await self.client.post(f"{self.api_base_url}/stop/{job_id}")
        response.raise_for_status()
        data = response.json()

        return [
            TextContent(
                type="text",
                text=f"작업이 성공적으로 중지되었습니다.\n\n{json.dumps(data, indent=2)}",
            )
        ]

    async def _list_jobs(self) -> Sequence[TextContent]:
        """작업 목록 조회 구현"""
        response = await self.client.get(f"{self.api_base_url}/jobs")
        response.raise_for_status()
        data = response.json()

        summary = (
            f"작업 요약\n"
            f"============\n\n"
            f"전체 작업: {data['total_jobs']}\n"
            f"활성 작업: {data['active_jobs']}\n"
            f"완료된 작업: {data['completed_jobs']}\n"
            f"실패한 작업: {data['failed_jobs']}\n\n"
            f"전체 응답:\n{json.dumps(data, indent=2)}"
        )

        return [TextContent(type="text", text=summary)]

    async def _delete_job(self, arguments: dict) -> Sequence[TextContent]:
        """작업 삭제 구현"""
        job_id = arguments["job_id"]
        response = await self.client.delete(f"{self.api_base_url}/jobs/{job_id}")
        response.raise_for_status()
        data = response.json()

        return [
            TextContent(
                type="text",
                text=f"작업이 성공적으로 삭제되었습니다.\n\n{json.dumps(data, indent=2)}",
            )
        ]

    async def _generate_and_wait(self, arguments: dict) -> Sequence[TextContent]:
        """생성 및 완료 대기 구현"""
        # 생성 시작
        response = await self.client.post(
            f"{self.api_base_url}/generate", json=arguments
        )

        if response.status_code == 503:
            retry_after = response.headers.get("Retry-After", "unknown")
            data = response.json()
            return [
                TextContent(
                    type="text",
                    text=f"서버가 사용 중입니다. {data.get('message', '')} {retry_after}초 후 재시도하세요.",
                )
            ]

        response.raise_for_status()
        job_data = response.json()
        job_id = job_data["job_id"]

        logger.info(f"작업 시작됨: {job_id}. 완료 대기 중...")

        # 완료될 때까지 폴링
        while True:
            await asyncio.sleep(POLL_INTERVAL)

            status_response = await self.client.get(
                f"{self.api_base_url}/status/{job_id}"
            )
            status_response.raise_for_status()
            status_data = status_response.json()

            status = status_data["status"]
            progress = status_data["progress_percent"]
            message = status_data["message"]

            logger.info(f"작업 {job_id}: {status} - {progress}% - {message}")

            if status in ("completed", "failed", "stopped"):
                break

        # 최종 결과 반환
        if status == "completed":
            result_text = (
                f"생성이 성공적으로 완료되었습니다!\n\n"
                f"작업 ID: {job_id}\n"
                f"진행률: {progress}%\n"
                f"메시지: {message}\n\n"
            )

            if status_data.get("final_result"):
                result_text += f"최종 결과: 사용 가능 (Base64 길이: {len(status_data['final_result'])} 문자)\n"
            if status_data.get("step1_result"):
                result_text += f"Step 1 결과: 사용 가능 (Base64 길이: {len(status_data['step1_result'])} 문자)\n"
            if status_data.get("step2_result"):
                result_text += f"Step 2 결과: 사용 가능 (Base64 길이: {len(status_data['step2_result'])} 문자)\n"

            result_text += f"\n\n전체 응답:\n{json.dumps(status_data, indent=2)}"

            return [TextContent(type="text", text=result_text)]
        else:
            return [
                TextContent(
                    type="text",
                    text=f"작업 {status}: {message}\n\n{json.dumps(status_data, indent=2)}",
                )
            ]

    async def run(self):
        """MCP 서버 실행"""
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream, write_stream, self.server.create_initialization_options()
            )


async def main():
    """메인 진입점"""
    server = NanoCocoaMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
