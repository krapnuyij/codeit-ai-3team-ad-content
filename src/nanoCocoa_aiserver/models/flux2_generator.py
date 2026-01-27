"""
FLUX.2 Klein 기반 AI 배경 생성 및 합성 엔진

[모델 정보]
- Model ID: black-forest-labs/FLUX.2-klein-4B
- Type: Text-to-Image with Object Composition

[주요 기능]
1. Smart Tilt: 제품의 비율(가로/세로)을 분석하여 3D 입체 기울기 자동 적용 (기준값 0.7)
2. Soft Shadow: 제품 하단에 자연스러운 그림자 생성 (Blur 15, Alpha 140)
3. Quality Guard: 사용자 프롬프트 뒤에 고품질/한국적 스타일 프롬프트 강제 주입
4. Auto Tokenizer: Qwen2 기반 토크나이저 호환성 문제 해결을 위한 수동 조립 로직 적용

[최적화 파라미터 (v26 기준)]
- Product Scale: 0.65 (배경 대비 65%)
- Inference Steps: 12 (고화질)
- Shadow: Blur 15 / Offset 10
"""

import os
import gc
import logging
import cv2
import numpy as np
import torch
from PIL import Image, ImageFilter
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

# diffusers 사용 (FLUX.2 전용)
from diffusers import Flux2KleinPipeline
from diffusers.utils import logging as diffusers_logging, load_image
from typing import Optional
from config import TORCH_DTYPE, DEVICE, MODEL_IDS
from services.monitor import flush_gpu

from helper_dev_utils import get_auto_logger

logger = get_auto_logger()

load_dotenv()


class Flux2Generator:
    def __init__(self):
        self.model_id = MODEL_IDS["FLUX2"]
        self.pipe = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Flux2Generator initialized using: {self.model_id}")

    def _flush_gpu(self):
        if self.pipe is not None:
            del self.pipe
            self.pipe = None
        flush_gpu()
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        torch.cuda.memory_summary()

    def _load_pipelines(self):
        if self.pipe is not None:
            return

        logger.info(f"Loading FLUX.2 Pipeline...")
        self._flush_gpu()

        try:
            # low_cpu_mem_usage=True로 변경 (기본값)
            self.pipe = Flux2KleinPipeline.from_pretrained(
                self.model_id,
                torch_dtype=TORCH_DTYPE,
                low_cpu_mem_usage=True,
            )
            self.pipe = self.pipe.to(DEVICE)

            # Config 강제 수정: guidance_embeds를 True로 설정
            if hasattr(self.pipe.transformer, "config"):
                logger.info(
                    f"Original guidance_embeds: {self.pipe.transformer.config.guidance_embeds}"
                )
                self.pipe.transformer.config.guidance_embeds = True
                logger.info(
                    f"Modified guidance_embeds: {self.pipe.transformer.config.guidance_embeds}"
                )

            logger.info("FLUX.2 Pipelines loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load pipeline: {e}")
            self._flush_gpu()
            raise e

    def image_to_base64(self, img: Image.Image) -> str:
        """이미지를 Data URI 형식으로 변환

        PIL Image 객체를 PNG base64로 인코딩된 문자열로 변환합니다.

        Args:
            img: 변환할 PIL Image 객체

        Returns:
            str: base64로 인코딩된 이미지 문자열
        """
        # BytesIO 버퍼에 PNG 형식으로 이미지 저장
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")

        # 버퍼 데이터를 base64로 인코딩
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

        # Data URI 형식으로 반환
        return img_str

    def image_to_data_uri(self, img):
        img_str = self.image_to_base64(img)
        return f"data:image/png;base64,{img_str}"

    def image_to_prompt_dic(self, img):
        data_uri = self.image_to_base64(img)
        return {"type": "image_url", "image_url": {"url": data_uri}}

    def generate(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        input_image: Optional[Image.Image] = None,
        width: Optional[int] = 1024,
        height: Optional[int] = 1024,
        num_inference_steps: Optional[int] = 30,
        guidance_scale: Optional[float] = 3.5,
        strength: Optional[float] = 0.75,
        seed: Optional[int] = 45,
        progress_callback: Optional[callable] = None,
        auto_unload: Optional[bool] = True,
        **kwargs,
    ) -> tuple[Image.Image, int]:

        image = None
        try:
            self._load_pipelines()

            generator = None
            if seed is not None:
                generator = torch.Generator(device=DEVICE).manual_seed(seed)

            def callback_fn(pipe_obj, step_index, timestep, callback_kwargs):
                if progress_callback:
                    progress_callback(
                        step_index + 1, num_inference_steps, "flux_bg_generation"
                    )
                return callback_kwargs

            pipe_kwargs = {
                "prompt": prompt,
                "height": height,
                "width": width,
                "num_inference_steps": num_inference_steps,
                "guidance_scale": guidance_scale,
                "generator": generator,
                "callback_on_step_end": callback_fn,
            }

            if negative_prompt is not None:
                pipe_kwargs["negative_prompt"] = negative_prompt

            if input_image is not None:
                pipe_kwargs["image"] = [
                    input_image,
                ]

            image = self.pipe(**pipe_kwargs).images[0]

        except Exception as e:
            logger.error(f"Error during image generation: {e}")
            raise e
        finally:
            if auto_unload:
                self._flush_gpu()

        return image, seed
