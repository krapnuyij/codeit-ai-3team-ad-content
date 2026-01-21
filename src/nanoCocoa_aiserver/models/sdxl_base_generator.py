import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

import torch
from PIL import Image
from diffusers import StableDiffusionXLPipeline
from config import MODEL_IDS, TORCH_DTYPE, DEVICE
from utils import flush_gpu
from helper_dev_utils import get_auto_logger
from services.monitor import log_gpu_memory

logger = get_auto_logger()


class SDXLBaseGenerator:
    """
    SDXL 모델을 사용하여 배경 이미지를 생성하는 클래스입니다.

    파이프라인 캐싱으로 GPU 메모리를 효율적으로 사용합니다.
    """

    def __init__(self):
        """파이프라인 인스턴스 초기화 (실제 로딩은 각 메서드 호출 시 수행)"""
        self.pipeline = None
        logger.info("SDXLGenerator initialized (pipeline will load on demand)")

    def _load_pipeline(self):
        """SDXL Text-to-Image 파이프라인 로딩 (캐싱)"""
        if self.pipeline is not None:
            return self.pipeline

        logger.info("[SDXLGenerator] Loading SDXL Text-to-Image pipeline...")
        self.pipeline = StableDiffusionXLPipeline.from_pretrained(
            MODEL_IDS["SDXL_BASE"],
            torch_dtype=TORCH_DTYPE,
        ).to(DEVICE)

        self.pipeline.enable_model_cpu_offload()
        self.pipeline.enable_attention_slicing()
        if hasattr(self.pipeline, "vae") and hasattr(
            self.pipeline.vae, "enable_slicing"
        ):
            self.pipeline.vae.enable_slicing()

        logger.info("[SDXLGenerator] Text-to-Image pipeline ready")
        return self.pipeline

    def generate_background(
        self,
        prompt: str,
        negative_prompt: str = None,
        guidance_scale: float = 7.5,
        seed: int = None,
        progress_callback=None,
        auto_unload: bool = True,
    ) -> Image.Image:
        """
        텍스트 프롬프트를 기반으로 배경 이미지를 생성합니다.

        Args:
            prompt (str): 배경 생성 프롬프트
            negative_prompt (str, optional): 배제할 요소들에 대한 부정 프롬프트
            guidance_scale (float): 프롬프트 준수 강도 (기본값: 7.5)
            seed (int, optional): 난수 시드
            progress_callback (callable, optional): 진행률 콜백 함수
            auto_unload (bool): 생성 후 자동 언로드 여부 (기본값: True)

        Returns:
            Image.Image: 생성된 이미지
        """
        logger.info("[SDXLGenerator] Generating background with Text-to-Image...")

        num_steps = 30

        def callback_fn(pipe_obj, step_index, timestep, callback_kwargs):
            if progress_callback:
                progress_callback(step_index + 1, num_steps, "sdxl_bg_generation")
            return callback_kwargs

        callback_fn(None, 0, None, None)

        pipe = self._load_pipeline()

        callback_fn(None, 0, None, None)

        generator = None
        if seed is not None:
            generator = torch.Generator(DEVICE).manual_seed(seed)

        logger.info(f" [SDXLGenerator] prompt='{prompt}' ")
        logger.info(f" [SDXLGenerator] negative_prompt='{negative_prompt}' ")

        image = pipe(
            prompt,
            negative_prompt=negative_prompt,
            height=1024,
            width=1024,
            num_inference_steps=num_steps,
            guidance_scale=guidance_scale,
            generator=generator,
            callback_on_step_end=callback_fn if progress_callback else None,
        ).images[0]

        logger.info("[SDXLGenerator] Background generation completed")

        if auto_unload:
            logger.info("[SDXLGenerator] Auto-unloading after background generation")
            self.unload()

        return image

    def unload(self) -> None:
        """
        명시적으로 SDXL 모델 리소스를 정리합니다.

        캐싱된 파이프라인을 삭제하여 GPU 메모리를 해제합니다.
        """

        log_gpu_memory("SDXLGenerator unload (before)")

        if self.pipeline is not None:
            del self.pipeline
            self.pipeline = None

        flush_gpu()
        log_gpu_memory("SDXLGenerator unload (after)")
        logger.info("SDXLGenerator unloaded (pipeline cleared)")
