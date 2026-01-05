from pydantic import BaseModel
from typing import Optional


class GenerateRequest(BaseModel):
    mode: str = "sd15_controlnet"   # "sd15_controlnet" | "sdxl"
    num_steps: int = 30
    guidance: float = 5.5
    num_images: int = 3
    seed: int = 42
    control_scale: float = 0.45
