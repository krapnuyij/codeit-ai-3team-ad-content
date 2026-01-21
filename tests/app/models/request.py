from pydantic import BaseModel, Field
from typing import Optional

class GenerateRequest(BaseModel):
    mode: str = Field("sdxl", description="Inference mode: 'sdxl' or 'sd15_controlnet'")
    preset_name: str = Field("market_tone", description="Name of the preset in configs/presets.json")
    
    strength: float = Field(0.28, ge=0.0, le=1.0, description="Inpaint strength (denoising strength)")
    control_scale: float = Field(0.5, ge=0.0, le=1.0, description="ControlNet conditioning scale")
    
    num_steps: int = Field(30, ge=1, le=100)
    guidance: float = Field(7.5, ge=1.0, le=20.0)
    seed: Optional[int] = Field(None, description="Random seed for reproducibility")
    
    num_images: int = Field(1, ge=1, le=4, description="Number of candidates to generate")

    class Config:
        json_schema_extra = {
            "example": {
                "mode": "sdxl",
                "preset_name": "market_tone",
                "strength": 0.28,
                "control_scale": 0.5,
                "num_steps": 30,
                "guidance": 7.5,
                "num_images": 1
            }
        }