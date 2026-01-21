"""
schemas 패키지
Pydantic 모델 정의
"""
from .deprecated import ResumeRequest
from .metrics import GPUMetric, SystemMetrics
from .request import GenerateRequest
from .response import StatusResponse

__all__ = [
    "GenerateRequest",
    "StatusResponse", 
    "GPUMetric",
    "SystemMetrics",
    "ResumeRequest",
]
