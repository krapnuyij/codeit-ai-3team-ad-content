"""
metrics.py
시스템 메트릭 스키마 정의
"""
from pydantic import BaseModel, Field


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
