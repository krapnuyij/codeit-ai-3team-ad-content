"""
API 모델 정의
nanoCocoa_aiserver의 요청/응답 스키마를 MCP 서버용으로 복제
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


# =============================================================================
# 시스템 메트릭 스키마
# =============================================================================


class GPUMetric(BaseModel):
    """GPU 메트릭 정보"""

    index: int = Field(..., title="GPU 인덱스")
    name: str = Field(..., title="GPU 이름")
    gpu_util: int = Field(..., title="GPU 사용률 (%)")
    vram_used_gb: float = Field(..., title="사용 중인 VRAM (GB)")
    vram_total_gb: float = Field(..., title="전체 VRAM (GB)")
    vram_percent: float = Field(..., title="VRAM 사용률 (%)")


class SystemMetrics(BaseModel):
    """시스템 메트릭 정보"""

    cpu_percent: float = Field(..., title="CPU 사용률 (%)")
    ram_used_gb: float = Field(..., title="사용 중인 RAM (GB)")
    ram_total_gb: float = Field(..., title="전체 RAM (GB)")
    ram_percent: float = Field(..., title="RAM 사용률 (%)")
    gpu_info: list[GPUMetric] = Field(default_factory=list, title="GPU 정보 목록")


# =============================================================================
# 요청 스키마
# =============================================================================


class GenerateRequest(BaseModel):
    """
    광고 생성 요청 스키마

    Step 기반의 생성 파이프라인(배경 -> 텍스트 -> 합성)을 제어하기 위한 입력 데이터
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "start_step": 1,
                "text_content": "New Arrival",
                "bg_prompt": "Wooden table in a cozy cafe, sunlight, realistic",
                "text_prompt": "Gold balloon text, 3d render",
                "strength": 0.6,
                "guidance_scale": 3.5,
            }
        }
    )

    # Step 제어
    start_step: int = Field(
        1,
        ge=1,
        le=3,
        title="시작 단계",
        description="파이프라인 실행을 시작할 단계 번호 (1: 전체, 2: 텍스트부터, 3: 합성만)",
    )

    # 공통 입력
    text_content: Optional[str] = Field(
        None,
        title="광고 문구",
        description="3D로 렌더링될 텍스트 내용 (예: 'SALE', 'Open', 'New')",
    )

    # Step 1 (배경 생성) 입력
    input_image: Optional[str] = Field(
        None,
        title="입력 이미지 (Base64)",
        description="제품 이미지 (Base64 인코딩 문자열)",
    )
    bg_prompt: str = Field(
        "A close-up view of a rustic wooden table surface. Soft morning sunlight coming from a window, creating gentle shadows. Blurred cozy kitchen background, bokeh, photorealistic, 8k, cinematic lighting.",
        title="배경 생성 프롬프트",
        description="생성될 배경에 대한 영문 설명",
    )
    bg_negative_prompt: str = Field(
        "blurry, low quality, distorted, ugly, bad lighting, overexposed, underexposed",
        title="배경 부정 프롬프트",
        description="배경 생성 시 배제할 요소",
    )
    bg_composition_prompt: Optional[str] = Field(
        None,
        title="배경 합성 프롬프트",
        description="배경과 제품을 자연스럽게 합성하기 위한 프롬프트",
    )
    bg_composition_negative_prompt: Optional[str] = Field(
        None,
        title="배경 합성 부정 프롬프트",
        description="배경 합성 시 제외할 요소",
    )

    # Step 2 (텍스트 에셋) 입력
    step1_image: Optional[str] = Field(
        None,
        title="Step 1 결과 이미지 (Base64)",
        description="Step 2 이상 시작 시 필수: 배경 이미지",
    )
    text_prompt: str = Field(
        "3D render of Gold foil balloon text, inflated, shiny metallic texture, floating in air, cinematic lighting, sharp details, isolated on black background",
        title="텍스트 모델 프롬프트",
        description="3D 텍스트의 재질, 조명, 스타일 정의",
    )
    negative_prompt: str = Field(
        "floor, ground, dirt, debris, random shapes, multiple objects, clutter, ugly, low quality",
        title="부정 프롬프트",
        description="생성 결과에서 배제할 요소",
    )
    font_name: Optional[str] = Field(
        None,
        title="폰트 이름",
        description="3D 텍스트 형태를 잡을 때 사용할 폰트 파일 이름 (예: 'NanumGothic/NanumGothic.ttf')",
    )

    # Step 3 (최종 합성) 입력
    step2_image: Optional[str] = Field(
        None,
        title="Step 2 결과 이미지 (Base64)",
        description="Step 3 시작 시 필수: 3D 텍스트 이미지",
    )

    # Step 3 합성 파라미터
    composition_mode: str = Field(
        "overlay",
        title="합성 모드",
        description="텍스트와 배경 합성 방식 (overlay/blend/behind)",
    )
    text_position: str = Field(
        "top",
        title="텍스트 위치",
        description="텍스트 배치 위치 (top/center/bottom/auto)",
    )
    composition_prompt: Optional[str] = Field(
        None,
        title="합성 커스텀 프롬프트",
        description="합성 시 추가로 적용할 사용자 정의 프롬프트",
    )
    composition_negative_prompt: Optional[str] = Field(
        None,
        title="합성 네거티브 프롬프트",
        description="합성 시 제외할 요소",
    )
    composition_strength: float = Field(
        0.4,
        ge=0.0,
        le=1.0,
        title="합성 변환 강도",
        description="Flux Inpainting 합성 시 변환 강도 (0.0~1.0)",
    )
    composition_steps: int = Field(
        28,
        ge=10,
        le=50,
        title="합성 추론 스텝",
        description="Flux Inpainting 합성 시 추론 스텝 수",
    )
    composition_guidance_scale: float = Field(
        3.5,
        ge=1.0,
        le=7.0,
        title="합성 가이던스 스케일",
        description="Flux Inpainting 합성 시 프롬프트 준수 강도",
    )

    # 공통 파라미터
    strength: float = Field(
        0.6,
        ge=0.0,
        le=1.0,
        title="이미지 변환 강도",
        description="Img2Img 변환 시 원본 이미지 변경 정도 (0.0: 원본 유지 ~ 1.0: 완전 재창조)",
    )
    guidance_scale: float = Field(
        3.5,
        ge=1.0,
        le=20.0,
        title="프롬프트 가이던스",
        description="생성 모델이 프롬프트를 따르는 정도 (보통 3.5~7.0)",
    )
    seed: Optional[int] = Field(
        None,
        title="랜덤 시드",
        description="결과 재현성을 위한 난수 시드 값",
    )

    # 테스트 모드
    test_mode: bool = Field(
        False,
        title="테스트 모드",
        description="True일 경우 AI 모델 없이 더미 데이터 반환",
    )

    # 메모리 관리
    auto_unload: bool = Field(
        True,
        title="자동 메모리 해제",
        description="각 단계 완료 후 모델을 메모리에서 언로드 여부",
    )


# =============================================================================
# 응답 스키마
# =============================================================================


class StatusResponse(BaseModel):
    """작업 상태 응답 스키마"""

    job_id: str = Field(..., title="작업 ID")
    status: str = Field(
        ..., title="작업 상태 (pending/running/completed/failed/stopped)"
    )
    progress_percent: int = Field(..., title="진행률 (%)")
    current_step: str = Field(..., title="현재 단계")
    sub_step: Optional[str] = Field(None, title="현재 서브 단계")
    message: str = Field(..., title="상태 메시지")
    elapsed_sec: float = Field(..., title="경과 시간 (초)")
    eta_seconds: Optional[int] = Field(None, title="예상 남은 시간 (초, 음수=초과)")
    step_eta_seconds: Optional[int] = Field(None, title="현재 단계 예상 남은 시간 (초)")
    system_metrics: Optional[SystemMetrics] = Field(None, title="시스템 메트릭")
    parameters: dict = Field(default_factory=dict, title="입력 파라미터")
    step1_result: Optional[str] = Field(None, title="Step 1 결과 (Base64)")
    step2_result: Optional[str] = Field(None, title="Step 2 결과 (Base64)")
    final_result: Optional[str] = Field(None, title="최종 결과 (Base64)")


class GenerateResponse(BaseModel):
    """생성 시작 응답 스키마"""

    job_id: str = Field(..., title="작업 ID")
    status: str = Field(..., title="초기 상태")
    message: Optional[str] = Field(None, title="메시지")


class StopResponse(BaseModel):
    """작업 중단 응답 스키마"""

    job_id: str = Field(..., title="작업 ID")
    status: str = Field(..., title="상태")
    message: Optional[str] = Field(None, title="메시지")


class JobSummary(BaseModel):
    """작업 요약 정보"""

    job_id: str
    status: str
    progress_percent: int
    current_step: str
    elapsed_sec: float


class JobListResponse(BaseModel):
    """작업 목록 응답 스키마"""

    total_jobs: int = Field(..., title="전체 작업 수")
    active_jobs: int = Field(..., title="활성 작업 수")
    completed_jobs: int = Field(..., title="완료된 작업 수")
    failed_jobs: int = Field(..., title="실패한 작업 수")
    jobs: list[JobSummary] = Field(default_factory=list, title="작업 목록")


class HealthResponse(BaseModel):
    """헬스체크 응답 스키마"""

    status: str = Field(..., title="서버 상태 (healthy/busy)")
    server_time: float = Field(..., title="서버 시간 (Unix timestamp)")
    total_jobs: int = Field(..., title="전체 작업 수")
    active_jobs: int = Field(..., title="활성 작업 수")
    system_metrics: Optional[SystemMetrics] = Field(None, title="시스템 메트릭")


class FontListResponse(BaseModel):
    """폰트 목록 응답 스키마"""

    fonts: list[str] = Field(..., title="사용 가능한 폰트 목록")


class ErrorResponse(BaseModel):
    """에러 응답 스키마"""

    error: str = Field(..., title="에러 유형")
    message: str = Field(..., title="에러 메시지")
    detail: Optional[str] = Field(None, title="상세 정보")
    retry_after: Optional[int] = Field(None, title="재시도 대기 시간 (초)")
