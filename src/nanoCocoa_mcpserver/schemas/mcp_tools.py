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
                "product_image_path": {
                    "type": "string",
                    "description": "제품 이미지 파일 경로 (선택사항). 제공하지 않으면 background_prompt에 제품 설명을 포함하여 배경과 함께 생성됩니다.",
                },
                "background_prompt": {
                    "type": "string",
                    "description": "생성할 배경에 대한 영문 설명. 제품 이미지가 없는 경우 제품 설명도 포함해야 함 (예: 'Red apples on golden silk cloth, wooden table in a cozy cafe, sunlight')",
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
            },
            "required": [
                "background_prompt",
                "text_content",
                "text_prompt",
            ],
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
    {
        "name": "generate_background_only",
        "description": (
            "[고급] Step 1만 실행 - 제품 이미지와 배경을 합성합니다. "
            "텍스트 없이 배경만 생성하고 싶을 때 사용합니다."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "product_image_path": {
                    "type": "string",
                    "description": "제품 이미지 파일 경로",
                },
                "background_prompt": {"type": "string", "description": "배경 설명"},
                "background_negative_prompt": {
                    "type": "string",
                    "description": "배경에서 제외할 요소 (선택사항)",
                },
                "strength": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "default": 0.6,
                    "description": "이미지 변환 강도",
                },
                "guidance_scale": {
                    "type": "number",
                    "minimum": 1.0,
                    "maximum": 20.0,
                    "default": 3.5,
                    "description": "프롬프트 가이던스",
                },
                "seed": {"type": "integer", "description": "랜덤 시드"},
                "wait_for_completion": {"type": "boolean", "default": False},
                "save_output_path": {"type": "string", "description": "결과 저장 경로"},
            },
            "required": ["product_image_path", "background_prompt"],
        },
    },
    {
        "name": "generate_text_asset_only",
        "description": (
            "[고급] Step 2만 실행 - 3D 텍스트 에셋을 생성합니다. "
            "배경 이미지(step1_image)를 Base64로 제공해야 합니다."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "step1_image_base64": {
                    "type": "string",
                    "description": "Step 1에서 생성된 배경 이미지 (Base64)",
                },
                "step1_image_path": {
                    "type": "string",
                    "description": "또는 Step 1 결과 이미지 파일 경로",
                },
                "text_content": {"type": "string", "description": "렌더링할 텍스트"},
                "text_prompt": {
                    "type": "string",
                    "description": "3D 텍스트 스타일 설명",
                },
                "font_name": {"type": "string", "description": "폰트 파일 이름"},
                "text_negative_prompt": {
                    "type": "string",
                    "description": "제외할 요소",
                },
                "seed": {"type": "integer"},
                "wait_for_completion": {"type": "boolean", "default": False},
                "save_output_path": {"type": "string"},
            },
            "required": ["text_content", "text_prompt"],
        },
    },
    {
        "name": "compose_final_image",
        "description": (
            "[고급] Step 3만 실행 - 배경과 3D 텍스트를 최종 합성합니다. "
            "step1_image와 step2_image를 Base64로 제공해야 합니다."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "step1_image_base64": {
                    "type": "string",
                    "description": "배경 이미지 (Base64)",
                },
                "step1_image_path": {
                    "type": "string",
                    "description": "또는 배경 이미지 파일 경로",
                },
                "step2_image_base64": {
                    "type": "string",
                    "description": "3D 텍스트 이미지 (Base64)",
                },
                "step2_image_path": {
                    "type": "string",
                    "description": "또는 3D 텍스트 이미지 파일 경로",
                },
                "composition_mode": {
                    "type": "string",
                    "enum": ["overlay", "blend", "behind"],
                    "default": "overlay",
                },
                "text_position": {
                    "type": "string",
                    "enum": ["top", "center", "bottom", "auto"],
                    "default": "auto",
                },
                "composition_strength": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "default": 0.4,
                },
                "composition_steps": {
                    "type": "integer",
                    "minimum": 10,
                    "maximum": 50,
                    "default": 28,
                },
                "composition_guidance_scale": {
                    "type": "number",
                    "minimum": 1.0,
                    "maximum": 7.0,
                    "default": 3.5,
                },
                "wait_for_completion": {"type": "boolean", "default": False},
                "save_output_path": {"type": "string"},
            },
            "required": [],
        },
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
