"""
MCP 도구 정의
nanoCocoa_aiserver의 기능을 MCP 프로토콜 도구로 노출
"""

from typing import Any
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))


# MCP 도구 정의 (Tool Schema)
# 실제 mcp 라이브러리와 통합 시 이 스키마를 사용합니다

MCP_TOOLS = [
    {
        "name": "generate_ad_image",
        "description": (
            "AI를 사용하여 전문적인 광고 이미지를 생성합니다. "
            "제품 이미지, 배경 설명, 텍스트 내용, 텍스트 스타일을 입력하면 "
            "3단계 파이프라인(배경 생성 → 3D 텍스트 생성 → 합성)을 거쳐 "
            "최종 광고 이미지를 생성합니다."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "product_image_png_b64": {
                    "type": "string",
                    "description": "제품 이미지 (PNG base64 인코딩, 선택사항). 제공하지 않으면 background_prompt에 제품 설명을 포함하여 배경과 함께 생성됩니다.",
                },
                "background_prompt": {
                    "type": "string",
                    "description": "생성할 배경에 대한 영문 설명. 제품 이미지가 없는 경우 제품 설명도 포함해야 함 (예: 'Red apples on golden silk cloth, wooden table in a cozy cafe, sunlight')",
                },
                "bg_model": {
                    "type": "string",
                    "enum": ["flux", "sdxl"],
                    "default": "flux",
                    "description": (
                        "**[필수]** 배경 생성 AI 모델 선택. 사용자 요청에 따라 반드시 명시적으로 설정하세요.\n"
                        "\n"
                        "**'sdxl' 선택 기준** (다음 키워드 감지 시):\n"
                        "  - 속도 관련: '빠르게', '빨리', '신속', '급하게', '테스트', 'quick', 'fast', 'rapid'\n"
                        "  - 품질 관련: '심플', '간단', '기본', '프리뷰', 'simple', 'basic', 'preview'\n"
                        "\n"
                        "**'flux' 선택 기준** (기본값, 다음 경우):\n"
                        "  - 품질 관련: '고품질', '포토리얼', '디테일', 'high-quality', 'photorealistic'\n"
                        "  - 속도 키워드 없을 때\n"
                        "  - 명시적 요청 없을 때\n"
                        "\n"
                        "**예시**:\n"
                        "  - '빠른 배경 이미지' → bg_model='sdxl'\n"
                        "  - '바나나 광고 만들어줘' → bg_model='flux'\n"
                        "  - '고품질 배경' → bg_model='flux'"
                    ),
                },
                "text_content": {
                    "type": "string",
                    "description": "광고에 표시할 텍스트 (예: 'SALE', 'New Arrival', 'Open')",
                },
                "text_prompt": {
                    "type": "string",
                    "description": "3D 텍스트 스타일 설명 (예: 'Gold balloon text, 3d render, shiny metallic')",
                },
                "font_name": {
                    "type": "string",
                    "description": "폰트 파일 이름 (선택사항, 예: 'NanumGothic/NanumGothic.ttf')",
                },
                "composition_mode": {
                    "type": "string",
                    "enum": ["overlay", "blend", "behind"],
                    "default": "overlay",
                    "description": "합성 모드 - overlay: 텍스트를 명확하게 배치, blend: 자연스럽게 혼합, behind: 배경 뒤에 배치",
                },
                "text_position": {
                    "type": "string",
                    "enum": ["top", "center", "bottom", "auto"],
                    "default": "auto",
                    "description": "텍스트 위치 - top/center/bottom 또는 auto (자동 감지)",
                },
                "seed": {
                    "type": "integer",
                    "description": "재현성을 위한 랜덤 시드 (선택사항)",
                },
                "wait_for_completion": {
                    "type": "boolean",
                    "default": True,
                    "description": "True면 완료까지 대기, False면 job_id만 즉시 반환",
                },
                "save_output_path": {
                    "type": "string",
                    "description": "결과 이미지를 저장할 경로 (선택사항, 지정하지 않으면 Base64만 반환)",
                },
                "stop_step": {
                    "type": "integer",
                    "enum": [1, 2, 3],
                    "description": (
                        "파이프라인 중단 단계 (선택사항). "
                        "생략하거나 None=전체 파이프라인 실행(배경→텍스트→합성). "
                        "1=배경만 생성(텍스트 없이 제품+배경), "
                        "2=배경+텍스트 생성(합성 전), "
                        "3=전체 실행(None과 동일). "
                        "활용: stop_step=1로 배경 A/B 테스트, stop_step=2로 텍스트 검토. "
                        "업로드한 이미지에 텍스트만 추가하려면 product_image_png_b64 대신 step1_image 제공."
                    ),
                },
            },
            "required": [],
        },
    },
    {
        "name": "check_generation_status",
        "description": "생성 작업의 진행 상태를 확인합니다. job_id를 사용하여 현재 진행률, 단계, 예상 시간 등을 조회합니다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "확인할 작업 ID (generate_ad_image에서 반환된 ID)",
                },
                "save_result_path": {
                    "type": "string",
                    "description": "완료된 경우 결과 이미지를 저장할 경로 (선택사항)",
                },
            },
            "required": ["job_id"],
        },
    },
    {
        "name": "stop_generation",
        "description": "실행 중인 생성 작업을 중단합니다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "중단할 작업 ID"}
            },
            "required": ["job_id"],
        },
    },
    {
        "name": "list_available_fonts",
        "description": "3D 텍스트 생성에 사용 가능한 폰트 목록을 조회합니다.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "check_server_health",
        "description": "AI 서버의 상태와 사용 가능 여부를 확인합니다. CPU, GPU, 메모리 사용량 등의 시스템 메트릭도 포함됩니다.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
]


def get_tool_by_name(name: str) -> dict[str, Any] | None:
    """도구 이름으로 도구 정의 검색"""
    for tool in MCP_TOOLS:
        if tool["name"] == name:
            return tool
    return None


def get_all_tool_names() -> list[str]:
    """모든 도구 이름 목록 반환"""
    return [tool["name"] for tool in MCP_TOOLS]
