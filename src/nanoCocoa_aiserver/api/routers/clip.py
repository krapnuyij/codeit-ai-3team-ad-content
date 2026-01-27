"""
clip.py
CLIP Score 계산 API 엔드포인트 (OpenAI CLIP + KoCLIP 지원)
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from fastapi import APIRouter, HTTPException, status

from config import logger
from core.clip_service import ClipService
from schemas.clip import ClipScoreRequest, ClipScoreResponse

router = APIRouter()

# ClipService 싱글톤 인스턴스
clip_service = ClipService()


@router.post(
    "/clip-score",
    summary="CLIP Score 계산 (Calculate CLIP Score)",
    response_description="이미지-텍스트 간 유사도 점수",
    response_model=ClipScoreResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "CLIP Score 계산 성공",
            "content": {
                "application/json": {
                    "example": {
                        "clip_score": 0.7324,
                        "prompt": "사과가 그려져 있고 가격과 판매 장소가 적혀 있는 광고 포스터",
                        "model_type": "koclip",
                        "interpretation": "매우 높은 일치도 - 이미지가 텍스트 설명과 강하게 부합합니다.",
                    }
                }
            },
        },
        400: {
            "description": "잘못된 요청 (유효하지 않은 이미지 또는 프롬프트)",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid base64 image: Incorrect padding"}
                }
            },
        },
        500: {
            "description": "서버 내부 오류 (CLIP 모델 로딩 또는 추론 실패)",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "CLIP Score calculation failed: CUDA out of memory"
                    }
                }
            },
        },
    },
)
async def calculate_clip_score(req: ClipScoreRequest) -> ClipScoreResponse:
    """
    **이미지와 텍스트 간 CLIP Score를 계산합니다. (한글/영문 모두 지원)**

    OpenAI CLIP(영문) 또는 KoCLIP(한글) 모델을 사용하여 이미지와 텍스트 간
    코사인 유사도를 측정합니다. 광고 이미지가 입력 프롬프트와
    얼마나 부합하는지 평가하는 데 유용합니다.

    ### 모델 선택 가이드
    - **koclip** (기본값): 한글 프롬프트 지원, 한글이 포함된 이미지 평가에 최적
    - **openai**: 영문 프롬프트에 최적화, 빠른 처리 속도

    ### CLIP Score 해석 가이드
    - **0.7 이상**: 매우 높은 일치도 (광고 생성 성공적)
    - **0.5~0.7**: 높은 일치도 (이미지와 텍스트 잘 연관됨)
    - **0.3~0.5**: 중간 일치도 (어느 정도 연관성 있음)
    - **0.3 미만**: 낮은 일치도 (연관성 약함)

    ### 사용 예시
    1. **광고 이미지 평가**: 생성된 광고 이미지가 입력 프롬프트와 일치하는지 확인
    2. **모델 비교**: 여러 모델의 생성 결과를 정량적으로 비교
    3. **프롬프트 최적화**: 다양한 프롬프트 중 가장 효과적인 것 선택

    ### 입력 요구사항
    - **image_base64**: Base64 인코딩된 이미지 (PNG, JPEG 등)
    - **prompt**: 이미지를 설명하는 텍스트 (한글/영문 모두 가능)
    - **model_type**: 사용할 모델 (`koclip` 또는 `openai`)

    ### 주의사항
    - KoCLIP은 한글 프롬프트 및 이미지 내 한글 텍스트 인식에 강합니다.
    - CLIP은 이미지의 '의미'를 파악하는 데 강하지만, OCR(정확한 문자 인식) 능력은 제한적입니다.
    - 첫 요청 시 모델 로딩으로 약 5~10초 소요될 수 있습니다.
    """

    try:
        logger.info(
            f"[CLIP API] Received request | Model: {req.model_type} | Prompt: {req.prompt[:50]}..."
        )

        # CLIP Score 계산 (auto_unload=False로 메모리 자동 해제)
        score = clip_service.calculate_clip_score(
            image_base64=req.image_base64,
            prompt=req.prompt,
            model_type=req.model_type,
            auto_unload=True,
        )

        # 점수 해석
        interpretation = ClipService.interpret_score(score)

        logger.info(
            f"[CLIP API] Model: {req.model_type} | Score: {score:.4f} | {interpretation}"
        )

        return ClipScoreResponse(
            clip_score=round(score, 4),
            prompt=req.prompt,
            model_type=req.model_type,
            interpretation=interpretation,
        )

    except ValueError as e:
        # 입력 검증 오류 (400)
        logger.warning(f"[CLIP API] Invalid request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    except RuntimeError as e:
        # CLIP 모델 로딩/추론 오류 (500)
        logger.error(f"[CLIP API] Runtime error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

    except Exception as e:
        # 기타 예상치 못한 오류 (500)
        logger.error(f"[CLIP API] Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {e}",
        )


@router.get(
    "/clip-score/health",
    summary="CLIP 서비스 상태 확인 (Health Check)",
    response_description="CLIP 모델 로딩 여부 및 사용 가능한 디바이스",
    status_code=status.HTTP_200_OK,
)
async def clip_health_check():
    """
    **CLIP 서비스의 상태를 확인합니다.**

    OpenAI CLIP 및 KoCLIP 모델의 로딩 상태와 사용 중인 디바이스(CPU/GPU)를 반환합니다.
    """

    openai_loaded = clip_service._clip_model is not None
    koclip_loaded = clip_service._koclip_model is not None
    device = clip_service._device if clip_service._device else "not loaded"

    return {
        "status": "healthy" if (openai_loaded or koclip_loaded) else "not initialized",
        "device": device,
        "models": {
            "openai_clip": {
                "loaded": openai_loaded,
                "model": "ViT-B/32" if openai_loaded else None,
            },
            "koclip": {
                "loaded": koclip_loaded,
                "model": "clip-vit-base-patch32-ko" if koclip_loaded else None,
            },
        },
    }
