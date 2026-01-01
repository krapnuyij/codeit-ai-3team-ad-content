"""
response.py
응답 스키마 정의
"""
from typing import Optional
from pydantic import BaseModel, Field
from .metrics import SystemMetrics


class StatusResponse(BaseModel):
    """작업 상태 응답 스키마"""
    job_id: str = Field(..., title="작업 ID")
    status: str = Field(..., title="작업 상태")
    progress_percent: int = Field(..., title="진행률 (%)")
    current_step: str = Field(..., title="현재 단계")
    sub_step: Optional[str] = Field(None, title="현재 서브 단계")
    message: str = Field(..., title="상태 메시지")
    elapsed_sec: float = Field(..., title="경과 시간 (초)")
    eta_seconds: Optional[int] = Field(None, title="예상 남은 시간 (초, 음수=초과)", description="양수: 남은 시간, 음수: 예상 시간 초과")
    step_eta_seconds: Optional[int] = Field(None, title="현재 단계 예상 남은 시간 (초, 음수=초과)", description="양수: 남은 시간, 음수: 예상 시간 초과")
    system_metrics: Optional[SystemMetrics] = Field(None, title="시스템 메트릭")
    parameters: dict = Field(default_factory=dict, title="입력 파라미터")
    step1_result: Optional[str] = Field(None, title="Step 1 결과 (Base64)")
    step2_result: Optional[str] = Field(None, title="Step 2 결과 (Base64)")
    final_result: Optional[str] = Field(None, title="최종 결과 (Base64)")
