
import torch
from PIL import Image
from diffusers import (
    FluxPipeline,
    FluxImg2ImgPipeline,
    FluxTransformer2DModel
)
from transformers import BitsAndBytesConfig
from ..config import MODEL_IDS, TORCH_DTYPE
from ..utils import flush_gpu

class FluxGenerator:
    """
    FLUX 모델을 사용하여 배경 생성 및 이미지 리파인을 수행하는 클래스입니다.
    """
    def generate_background(self, prompt: str, guidance_scale: float = 3.5, seed: int = None) -> Image.Image:
        """
        텍스트 프롬프트를 기반으로 배경 이미지를 생성합니다.
        
        Args:
            prompt (str): 배경 생성 프롬프트
            guidance_scale (float): 프롬프트 준수 강도
            seed (int, optional): 난수 시드
            
        Returns:
            Image.Image: 생성된 이미지
        """
        print("[Engine] Loading FLUX (Text-to-Image)... (FLUX 텍스트-이미지 모델 로딩 중)")
        flush_gpu()
        
        quant_config = BitsAndBytesConfig(load_in_8bit=True)
        transformer = FluxTransformer2DModel.from_pretrained(
            MODEL_IDS["FLUX"], subfolder="transformer", quantization_config=quant_config, torch_dtype=TORCH_DTYPE
        )
        pipe = FluxPipeline.from_pretrained(
            MODEL_IDS["FLUX"], transformer=transformer, torch_dtype=TORCH_DTYPE
        )
        pipe.enable_model_cpu_offload()

        generator = None
        if seed is not None:
             generator = torch.Generator("cpu").manual_seed(seed)
        else:
             generator = torch.Generator("cpu").manual_seed(42) # Default seed for consistency if not specified

        image = pipe(
            prompt, height=1024, width=1024, num_inference_steps=25, guidance_scale=guidance_scale,
            generator=generator
        ).images[0]
        
        del pipe, transformer
        flush_gpu()
        return image

    def refine_image(self, draft_image: Image.Image, prompt: str = None, strength: float = 0.6, guidance_scale: float = 3.5, seed: int = None) -> Image.Image:
        """
        이미지를 리터칭(Img2Img)하여 품질을 높입니다.
        
        Args:
            draft_image (Image.Image): 초안 이미지
            prompt (str): 리터칭 프롬프트 (없을 경우 기본값 사용)
            strength (float): 변환 강도
            guidance_scale (float): 프롬프트 준수 강도
            seed (int, optional): 난수 시드
            
        Returns:
            Image.Image: 리터칭된 이미지
        """
        print("[Engine] Loading FLUX (Img-to-Img)... (FLUX 이미지-이미지 모델 로딩 중)")
        flush_gpu()
        
        quant_config = BitsAndBytesConfig(load_in_8bit=True)
        transformer = FluxTransformer2DModel.from_pretrained(
            MODEL_IDS["FLUX"], subfolder="transformer", quantization_config=quant_config, torch_dtype=TORCH_DTYPE
        )
        pipe = FluxImg2ImgPipeline.from_pretrained(
            MODEL_IDS["FLUX"], transformer=transformer, torch_dtype=TORCH_DTYPE
        )
        pipe.enable_model_cpu_offload()

        default_prompt = (
            "A photorealistic close-up shot of a product lying naturally on a surface. "
            "Heavy contact shadows, ambient occlusion, texture reflection, "
            "warm sunlight, cinematic lighting, 8k, extremely detailed."
        )
        use_prompt = prompt if prompt else default_prompt

        generator = None
        if seed is not None:
             generator = torch.Generator("cpu").manual_seed(seed)
        else:
             generator = torch.Generator("cpu").manual_seed(42)

        refined_image = pipe(
            use_prompt, image=draft_image, strength=strength, num_inference_steps=30, guidance_scale=guidance_scale,
            generator=generator
        ).images[0]

        del pipe, transformer
        flush_gpu()
        return refined_image
