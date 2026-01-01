"""
deprecated.py
더 이상 사용하지 않는 스키마
"""
from typing import Optional
from pydantic import BaseModel, Field


class ResumeRequest(BaseModel):
    """
    [Deprecated] 작업 재개 요청 스키마
    현재는 GenerateRequest의 start_step을 사용하여 대체 가능합니다.
    """
    job_id: str = Field(..., title="작업 ID")
    run_from_step: int = Field(..., ge=2, le=3, title="재시작 단계")
    new_text: Optional[str] = Field(None, title="변경할 텍스트")
