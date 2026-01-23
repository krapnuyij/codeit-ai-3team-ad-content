"""
clip.py
CLIP Score 관련 스키마 정의 (OpenAI CLIP + KoCLIP 지원)
"""

from typing import Literal

from pydantic import BaseModel, Field


class ClipScoreRequest(BaseModel):
    """CLIP Score 계산 요청 스키마"""

    image_base64: str = Field(
        ...,
        title="Base64 인코딩 이미지",
        description="평가할 이미지의 Base64 인코딩 문자열입니다.",
        json_schema_extra={
            "example": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        },
    )

    prompt: str = Field(
        ...,
        title="프롬프트 텍스트",
        description="이미지를 설명하는 텍스트 프롬프트입니다. (한글/영문 모두 지원)",
        json_schema_extra={
            "example": "사과가 그려져 있고 가격과 판매 장소가 적혀 있는 광고 포스터"
        },
    )

    model_type: Literal["openai", "koclip"] = Field(
        "koclip",
        title="모델 타입",
        description=(
            "사용할 CLIP 모델 타입을 선택합니다.\n"
            "- `openai`: OpenAI CLIP (영문 프롬프트에 최적화)\n"
            "- `koclip`: KoCLIP (한글 프롬프트 지원, 기본값)"
        ),
        json_schema_extra={"example": "koclip"},
    )


class ClipScoreResponse(BaseModel):
    """CLIP Score 계산 응답 스키마"""

    clip_score: float = Field(
        ...,
        title="CLIP Score",
        description=(
            "이미지와 텍스트 간 코사인 유사도 점수입니다. "
            "범위: [-1.0, 1.0], 일반적으로 [0.0, 1.0]에 분포. "
            "0.3 이상: 연관성 있음, 0.7 이상: 높은 일치도"
        ),
        json_schema_extra={"example": 0.7324},
    )

    prompt: str = Field(
        ...,
        title="입력 프롬프트",
        description="평가에 사용된 텍스트 프롬프트입니다.",
        json_schema_extra={
            "example": "사과가 그려져 있고 가격과 판매 장소가 적혀 있는 광고 포스터"
        },
    )

    model_type: str = Field(
        ...,
        title="사용된 모델",
        description="점수 계산에 사용된 CLIP 모델 타입입니다.",
        json_schema_extra={"example": "koclip"},
    )

    interpretation: str = Field(
        ...,
        title="점수 해석",
        description="CLIP Score에 대한 자동 해석 가이드입니다.",
        json_schema_extra={
            "example": "매우 높은 일치도 - 이미지가 텍스트 설명과 강하게 부합합니다."
        },
    )
