
import torch
from PIL import Image
from diffusers import (
    StableDiffusionXLControlNetPipeline,
    ControlNetModel,
    AutoencoderKL
)
from ..config import MODEL_IDS, TORCH_DTYPE, DEVICE
from ..utils import flush_gpu

class SDXLTextGenerator:
    """
    SDXL ControlNet을 사용하여 3D 텍스트 효과를 생성하는 클래스입니다.
    """
    def generate_text_effect(self, canny_map: Image.Image, prompt: str, negative_prompt: str) -> Image.Image:
        """
        Canny 엣지 맵과 프롬프트를 사용하여 3D 텍스트 이미지를 생성합니다.
        
        Args:
            canny_map (Image.Image): 텍스트의 윤곽선(Canny) 이미지
            prompt (str): 생성할 텍스트 효과에 대한 프롬프트
            negative_prompt (str): 생성 시 제외할 요소들에 대한 부정 프롬프트
            
        Returns:
            Image.Image: 생성된 3D 텍스트 이미지
        """
        print("[Engine] Loading SDXL ControlNet... (SDXL ControlNet 로딩 중)")
        flush_gpu()
        
        controlnet = ControlNetModel.from_pretrained(
            MODEL_IDS["SDXL_CNET"], torch_dtype=TORCH_DTYPE, use_safetensors=True
        )
        vae = AutoencoderKL.from_pretrained(MODEL_IDS["SDXL_VAE"], torch_dtype=TORCH_DTYPE)
        pipe = StableDiffusionXLControlNetPipeline.from_pretrained(
            MODEL_IDS["SDXL_BASE"], controlnet=controlnet, vae=vae, torch_dtype=TORCH_DTYPE
        ).to(DEVICE)
        
        generated_img = pipe(
            prompt, negative_prompt=negative_prompt, image=canny_map, 
            controlnet_conditioning_scale=1.0, num_inference_steps=30
        ).images[0]
        
        del pipe, controlnet, vae
        flush_gpu()
        return generated_img
