"""
nanoCocoa MCP Server (FastAPI REST API)
REST API를 통해 nanoCocoa_aiserver를 제어하는 서버
LLM Adapter와 HTTP 통신
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# 프로젝트 루트 경로 추가 (직접 실행 시에도 임포트 가능하도록)
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from config import (
    MCP_SERVER_NAME,
    MCP_SERVER_VERSION,
    MCP_SERVER_DESCRIPTION,
)
from client.api_client import AIServerError
from schemas.api_models import GenerateRequest
from handlers import (
    generate_ad_image,
    check_generation_status,
    stop_generation,
    list_available_fonts,
    get_fonts_metadata,
    recommend_font_for_ad,
    get_all_jobs,
    delete_all_jobs,
    delete_job,
    check_server_health,
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# FastAPI 서버 초기화
app = FastAPI(
    title=MCP_SERVER_NAME,
    version=MCP_SERVER_VERSION,
    description=MCP_SERVER_DESCRIPTION,
)


# =============================================================================
# OpenAI Function Calling Schema 정의
# =============================================================================

TOOL_SCHEMAS = [
    {
        "name": "generate_ad_image",
        "description": "제품 이미지를 기반으로 AI가 전문적인 광고 이미지를 생성합니다. 3단계 파이프라인(배경 생성 → 3D 텍스트 생성 → 최종 합성)을 자동으로 실행합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_image_path": {
                    "type": "string",
                    "description": "제품 이미지 파일의 절대 경로 (PNG, JPG, JPEG, WEBP 지원)",
                },
                "background_prompt": {
                    "type": "string",
                    "description": "Detailed English description of commercial-quality background (15-30 words). Include: main elements, lighting (natural/studio/dramatic), color palette, textures (surfaces/materials), composition style.",
                },
                "text_content": {
                    "type": "string",
                    "description": "광고에 표시할 텍스트 내용 (예: 'SALE', '50% OFF', '특가 2500원')",
                },
                "text_prompt": {
                    "type": "string",
                    "description": "Detailed English description for 3D text rendering (10-20 words). MUST include: '3D render' (mandatory), material type (metallic/balloon/glass/neon), surface finish (glossy/matte/reflective), lighting effects.",
                },
                "font_name": {
                    "type": "string",
                    "description": "텍스트 렌더링에 사용할 폰트 파일명 (선택사항, list_available_fonts로 확인 가능)",
                },
                "background_negative_prompt": {
                    "type": "string",
                    "description": "Comma-separated English keywords to exclude from background (8-15 keywords recommended).",
                },
                "text_negative_prompt": {
                    "type": "string",
                    "description": "Comma-separated English keywords to exclude from 3D text. CRITICAL: ALWAYS include 'floor, ground, background, scene' to ensure floating 3D effect.",
                },
                "composition_negative_prompt": {
                    "type": "string",
                    "description": "Comma-separated English keywords to exclude from final composition (8-15 keywords recommended).",
                },
                "composition_mode": {
                    "type": "string",
                    "description": "배경과 텍스트 합성 방식 ('overlay', 'blend', 'behind' 중 선택, 기본값: 'overlay')",
                    "default": "overlay",
                },
                "text_position": {
                    "type": "string",
                    "description": "텍스트 배치 위치 ('auto', 'top', 'center', 'bottom' 중 선택, 기본값: 'auto')",
                    "default": "auto",
                },
                "bg_composition_prompt": {
                    "type": "string",
                    "description": "Detailed English instructions for natural product-background composition (10-20 words recommended).",
                },
                "bg_composition_negative_prompt": {
                    "type": "string",
                    "description": "Comma-separated English keywords to exclude from product-background composition (7-12 keywords recommended).",
                },
                "composition_prompt": {
                    "type": "string",
                    "description": "Detailed English instructions for text-background composition (12-25 words recommended).",
                },
                "strength": {
                    "type": "number",
                    "description": "이미지 변환 강도 (0.0~1.0, 기본값: 0.6)",
                    "default": 0.6,
                    "minimum": 0.0,
                    "maximum": 1.0,
                },
                "guidance_scale": {
                    "type": "number",
                    "description": "프롬프트 가이던스 (1.0~20.0, 기본값: 3.5)",
                    "default": 3.5,
                    "minimum": 1.0,
                    "maximum": 20.0,
                },
                "composition_strength": {
                    "type": "number",
                    "description": "합성 변환 강도 (0.0~1.0, 기본값: 0.4)",
                    "default": 0.4,
                    "minimum": 0.0,
                    "maximum": 1.0,
                },
                "composition_steps": {
                    "type": "integer",
                    "description": "합성 추론 스텝 수 (10~50, 기본값: 28)",
                    "default": 28,
                    "minimum": 10,
                    "maximum": 50,
                },
                "composition_guidance_scale": {
                    "type": "number",
                    "description": "합성 가이던스 (1.0~7.0, 기본값: 3.5)",
                    "default": 3.5,
                    "minimum": 1.0,
                    "maximum": 7.0,
                },
                "auto_unload": {
                    "type": "boolean",
                    "description": "모델 자동 언로드 (기본값: true)",
                    "default": True,
                },
                "seed": {
                    "type": "integer",
                    "description": "재현성을 위한 랜덤 시드 (선택사항)",
                },
                "test_mode": {
                    "type": "boolean",
                    "description": "더미 데이터 테스트 모드 (기본값: false)",
                    "default": False,
                },
                "wait_for_completion": {
                    "type": "boolean",
                    "description": "생성 완료까지 대기 여부 (기본값: true)",
                    "default": False,
                },
                "save_output_path": {
                    "type": "string",
                    "description": "생성된 이미지를 저장할 파일 경로 (선택사항)",
                },
                "stop_step": {
                    "type": "integer",
                    "description": "파이프라인 중단 단계 (선택사항). None(기본값)=전체 실행, 1=배경만 생성, 2=배경+텍스트 생성.",
                    "enum": [1, 2, 3],
                },
            },
            "required": [],
        },
    },
    {
        "name": "check_generation_status",
        "description": "비동기로 시작된 광고 생성 작업의 현재 진행 상태를 확인합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "확인할 작업의 고유 ID (generate_ad_image 호출 시 반환된 ID)",
                },
                "save_result_path": {
                    "type": "string",
                    "description": "작업이 완료된 경우 결과 이미지를 저장할 파일 경로 (선택사항)",
                },
            },
            "required": ["job_id"],
        },
    },
    {
        "name": "stop_generation",
        "description": "실행 중인 광고 생성 작업을 강제로 중단합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "중단할 작업의 고유 ID",
                }
            },
            "required": ["job_id"],
        },
    },
    {
        "name": "list_available_fonts",
        "description": "텍스트 렌더링에 사용할 수 있는 폰트 목록을 반환합니다.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_fonts_metadata",
        "description": "폰트별 상세 메타데이터(스타일, 굵기, 용도, 톤앤매너)를 조회하여 광고 콘텐츠에 적합한 폰트를 선택할 수 있습니다.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "recommend_font_for_ad",
        "description": "광고 콘텐츠와 유형에 따라 적합한 폰트를 자동으로 추천합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "text_content": {
                    "type": "string",
                    "description": "광고에 사용할 텍스트 (한글/영문 구분용)",
                },
                "ad_style": {
                    "type": "string",
                    "description": "광고 스타일 (modern/elegant/bold/casual/playful)",
                    "default": "modern",
                },
                "language": {
                    "type": "string",
                    "description": "언어 (auto/korean/english)",
                    "default": "auto",
                },
            },
            "required": ["text_content"],
        },
    },
    {
        "name": "check_server_health",
        "description": "AI 서버의 현재 상태와 시스템 리소스 사용량을 확인합니다.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_all_jobs",
        "description": "AI 서버에 등록된 모든 작업 목록을 조회합니다.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "delete_all_jobs",
        "description": "완료되었거나 실패한 모든 작업을 삭제합니다. 실행/대기 중인 작업은 건너뜁니다.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "delete_job",
        "description": "특정 작업을 삭제합니다. 완료/실패한 작업만 삭제 가능합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "삭제할 작업의 고유 ID",
                }
            },
            "required": ["job_id"],
        },
    },
]

# Tool name → function mapping
TOOL_FUNCTIONS = {
    "generate_ad_image": generate_ad_image,
    "check_generation_status": check_generation_status,
    "stop_generation": stop_generation,
    "list_available_fonts": list_available_fonts,
    "get_fonts_metadata": get_fonts_metadata,
    "recommend_font_for_ad": recommend_font_for_ad,
    "check_server_health": check_server_health,
    "get_all_jobs": get_all_jobs,
    "delete_all_jobs": delete_all_jobs,
    "delete_job": delete_job,
}


# =============================================================================
# REST API 엔드포인트
# =============================================================================


@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    return {
        "status": "healthy",
        "server": MCP_SERVER_NAME,
        "version": MCP_SERVER_VERSION,
        "description": MCP_SERVER_DESCRIPTION,
    }


@app.get("/tools")
async def list_tools():
    """사용 가능한 도구 목록 반환 (OpenAI Function Calling 스키마 형식)"""
    return {"tools": TOOL_SCHEMAS}


@app.post("/tools/{tool_name}")
async def call_tool(tool_name: str, request: Dict[str, Any]):
    """특정 도구 실행"""
    if tool_name not in TOOL_FUNCTIONS:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")

    try:
        tool_func = TOOL_FUNCTIONS[tool_name]
        logger.info(f"도구 호출: {tool_name}")
        logger.info(f"받은 파라미터: {list(request.keys())}")
        result = await tool_func(**request)
        return {"result": result}
    except TypeError as e:
        logger.error(f"TypeError 발생: {tool_name}")
        logger.error(f"받은 파라미터: {request}")
        logger.error(f"에러 상세: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid parameters for {tool_name}: {str(e)}. Received params: {list(request.keys())}",
        )
    except Exception as e:
        logger.exception(f"Error executing tool {tool_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Tool execution failed: {str(e)}")


# =============================================================================
# 서버 실행
# =============================================================================


def main():
    """메인 진입점"""
    import os
    import uvicorn

    logger.info(f"{MCP_SERVER_NAME} v{MCP_SERVER_VERSION} 시작")
    logger.info(f"설명: {MCP_SERVER_DESCRIPTION}")

    port = int(os.getenv("MCP_PORT", "3000"))
    host = os.getenv("MCP_HOST", "0.0.0.0")
    logger.info(f"REST API 모드로 실행: {host}:{port}")

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
