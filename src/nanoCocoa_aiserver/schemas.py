
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

class GenerateRequest(BaseModel):
    """
    광고 생성 요청 스키마 (Generate Request Schema)
    
    Step 기반의 생성 파이프라인(배경 -> 텍스트 -> 합성)을 제어하기 위한 입력 데이터입니다.
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "start_step": 1,
                "text_content": "New Arrival",
                "bg_prompt": "Wooden table in a cozy cafe, sunlight, realistic",
                "text_model_prompt": "Gold balloon text, 3d render",
                "strength": 0.6,
                "guidance_scale": 3.5
            }
        }
    )
    
    # 1. Step 제어
    start_step: int = Field(
        1, 
        ge=1, 
        le=3, 
        title="시작 단계 (Start Step)",
        description=(
            "파이프라인 실행을 시작할 단계 번호입니다.\n"
            "- `1`: **전체 실행** (배경 생성 -> 3D 텍스트 생성 -> 최종 합성)\n"
            "- `2`: **텍스트 생성부터** (배경 이미지는 `step1_image`로 제공 필요)\n"
            "- `3`: **합성만 수행** (배경 및 텍스트 이미지는 각각 `step1_image`, `step2_image`로 제공 필요)"
        ),
        json_schema_extra={"example": 1}
    )
    
    # 공통 필수 입력
    text_content: str = Field(
        "Special Sale", 
        title="광고 문구 (Text Content)",
        description="3D로 렌더링되어 이미지에 삽입될 텍스트 내용입니다. (예: 'SALE', 'Open', 'New')",
        json_schema_extra={"example": "Summer Sale"}
    )

    # Step 1 (배경 생성) 입력
    input_image: Optional[str] = Field(
        None, 
        title="입력 이미지 (Input Image)",
        description=(
            "**[Step 1 필수]** 배경을 제거하고 광고에 배치할 상품 이미지 (Base64 인코딩 문자열).\n"
            "Step 1부터 시작할 경우 반드시 포함되어야 합니다."
        )
    )
    bg_prompt: str = Field(
        "A close-up view of a rustic wooden table surface. Soft morning sunlight coming from a window, creating gentle shadows. Blurred cozy kitchen background, bokeh, photorealistic, 8k, cinematic lighting.",
        title="배경 생성 프롬프트 (Background Prompt)",
        description="상품 뒤에 생성될 배경 이미지에 대한 영문 묘사 텍스트입니다.",
        json_schema_extra={"example": "Luxury marble podium on a beach, sunset lighting, realistic, 8k"}
    )

    # Step 2 (텍스트 에셋) 입력
    step1_image: Optional[str] = Field(
        None, 
        title="Step 1 결과 이미지 (Step 1 Output Image)",
        description=(
            "**[Step 2 이상 시작 시 필수]** 이전 단계(Step 1)에서 생성된, 상품이 합성된 배경 이미지 (Base64).\n"
            "Step 1부터 실행 시에는 서버가 생성한 이미지를 자동으로 사용하므로 비워둡니다."
        )
    )
    text_model_prompt: str = Field(
        "3D render of Gold foil balloon text, inflated, shiny metallic texture, floating in air, cinematic lighting, sharp details, isolated on black background",
        title="텍스트 모델 프롬프트 (Text Model Prompt)",
        description="3D 텍스트의 재질, 조명, 스타일을 정의하는 영문 프롬프트입니다.",
        json_schema_extra={"example": "3D render of pink neon glass text, glowing, cyberpunk style"}
    )
    negative_prompt: str = Field(
        "floor, ground, dirt, debris, random shapes, multiple objects, clutter, ugly, low quality",
        title="부정 프롬프트 (Negative Prompt)",
        description="생성 결과물에서 배제하고 싶은 요소들에 대한 키워드입니다.",
        json_schema_extra={"example": "blurry, low quality, distorted"}
    )
    font_name: Optional[str] = Field(
        None, 
        title="폰트 이름 (Font Name)",
        description=(
            "3D 텍스트의 기본 형태를 잡을 때 사용할 폰트 파일 이름입니다.\n"
            "`GET /fonts` API를 통해 사용 가능한 목록을 확인할 수 있습니다. (예: 'NanumGothic/NanumGothic.ttf')"
        ),
        json_schema_extra={"example": "NanumSquare/NanumSquareB.ttf"}
    )

    # Step 3 (최종 합성) 입력
    step2_image: Optional[str] = Field(
        None, 
        title="Step 2 결과 이미지 (Step 2 Output Image)",
        description=(
            "**[Step 3 시작 시 필수]** 이전 단계(Step 2)에서 생성된 배경 제거된 3D 텍스트 이미지 (Base64).\n"
            "Step 2 이전부터 실행 시에는 서버가 생성한 이미지를 자동으로 사용하므로 비워둡니다."
        )
    )

    # 공통 파라미터 (고급 설정)
    strength: float = Field(
        0.6, 
        ge=0.0, 
        le=1.0, 
        title="이미지 변환 강도 (Strength)",
        description="Img2Img 변환 시 원본 이미지를 얼마나 변경할지 결정합니다. (0.0: 원본 유지 ~ 1.0: 완전 재창조)",
        json_schema_extra={"example": 0.65}
    )
    guidance_scale: float = Field(
        3.5, 
        ge=1.0, 
        le=20.0, 
        title="프롬프트 가이던스 (Guidance Scale)",
        description="생성 모델이 프롬프트를 얼마나 엄격하게 따를지 결정합니다. 보통 3.5 ~ 7.0 사이가 적절합니다.",
        json_schema_extra={"example": 3.5}
    )
    seed: Optional[int] = Field(
        None, 
        title="랜덤 시드 (Random Seed)",
        description="결과의 재현성을 위한 난수 시드 값입니다. 동일한 시드와 파라미터는 동일한 이미지를 생성합니다.",
        json_schema_extra={"example": 42}
    )
    
    # 테스트 모드 (Dummy Mode)
    test_mode: bool = Field(
        False,
        title="테스트 모드 (Test Mode)",
        description="True일 경우 AI 모델을 구동하지 않고 더미 데이터를 반환합니다. 빠른 API 테스트용입니다.",
        json_schema_extra={"example": False}
    )

class ResumeRequest(BaseModel):
    """
    [Deprecated] 작업 재개 요청 스키마
    현재는 GenerateRequest의 start_step을 사용하여 대체 가능합니다.
    """
    job_id: str = Field(..., title="작업 ID")
    run_from_step: int = Field(..., ge=2, le=3, title="재시작 단계")
    new_text: Optional[str] = Field(None, title="변경할 텍스트")

