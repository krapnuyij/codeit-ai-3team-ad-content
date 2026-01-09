"""
CompositionEngine.py
프롬프트 기반 지능형 이미지 합성 엔진

Flux Inpainting을 활용하여 텍스트 에셋을 배경 이미지와 맥락적으로 통합
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import gc
import torch
from PIL import Image
from typing import Literal, Optional
from config import DEVICE, TORCH_DTYPE, MODEL_IDS, logger
from transformers import BitsAndBytesConfig
from diffusers import FluxTransformer2DModel


CompositionMode = Literal["overlay", "blend", "behind"]
TextPosition = Literal["top", "center", "bottom"]


class CompositionEngine:
    """
    프롬프트 기반 지능형 합성 엔진

    배경 이미지와 텍스트 에셋을 Flux Inpainting으로 자연스럽게 통합합니다.
    단순 alpha composite가 아닌 맥락적 이해를 기반으로 합성합니다.
    """

    def __init__(self, device: str = DEVICE):
        """
        Args:
            device: 실행 디바이스 ("cuda" 또는 "cpu")
        """
        self.device = device
        self.pipe = None
        logger.info(f"CompositionEngine initialized on {device}")

    def _load_pipeline(self):
        """Flux Inpainting 파이프라인 로드 (8bit 양자화 적용)"""
        if self.pipe is not None:
            return

        try:
            from diffusers import FluxInpaintPipeline

            logger.info("Loading Flux Inpainting pipeline for composition...")

            # 8bit 양자화로 메모리 사용량 감소
            quant_config = BitsAndBytesConfig(load_in_8bit=True)
            transformer = FluxTransformer2DModel.from_pretrained(
                MODEL_IDS["FLUX"],
                subfolder="transformer",
                quantization_config=quant_config,
                torch_dtype=TORCH_DTYPE,
            )

            self.pipe = FluxInpaintPipeline.from_pretrained(
                MODEL_IDS["FLUX"], transformer=transformer, torch_dtype=TORCH_DTYPE
            )

            # GPU 메모리 절약을 위한 최적화
            self.pipe.enable_model_cpu_offload()

            logger.info(
                "Flux Inpainting pipeline loaded successfully with 8bit quantization and CPU offload"
            )

        except Exception as e:
            logger.error(f"Failed to load Flux Inpainting: {e}", exc_info=True)
            raise

    def _unload_pipeline(self):
        """메모리 해제"""
        from services.monitor import log_gpu_memory

        if self.pipe is not None:
            log_gpu_memory("Before Flux Inpainting unload")
            del self.pipe
            self.pipe = None
            gc.collect()
            torch.cuda.empty_cache()
            log_gpu_memory("After Flux Inpainting unload")
            logger.info("Flux Inpainting pipeline unloaded")

    def unload(self) -> None:
        """
        명시적으로 Composition Engine 리소스를 정리합니다.
        """
        self._unload_pipeline()

    def _build_composition_prompt(
        self,
        mode: CompositionMode,
        position: TextPosition,
        user_prompt: Optional[str] = None,
    ) -> str:
        """
        합성 프롬프트 생성

        Args:
            mode: 합성 모드 (overlay/blend/behind)
            position: 텍스트 위치 (top/center/bottom)
            user_prompt: 사용자 지정 프롬프트 (옵션)

        Returns:
            str: Flux Inpainting용 프롬프트
        """
        base_prompts = {
            "overlay": {
                "top": "place stylized text at top of image, above all objects, crisp and prominent",
                "center": "place stylized text in center, overlaying the scene, bold and eye-catching",
                "bottom": "place stylized text at bottom, above all elements, clear and readable",
            },
            "blend": {
                "top": "naturally blend stylized text at top, harmonious with background colors and lighting",
                "center": "seamlessly integrate text in center, matching scene atmosphere and style",
                "bottom": "organically merge text at bottom, cohesive with overall composition",
            },
            "behind": {
                "top": "integrate text at top with subtle depth, slightly behind main object, ethereal effect",
                "center": "place text in center with depth cues, partially obscured by foreground, layered look",
                "bottom": "position text at bottom with depth, behind scene elements, atmospheric integration",
            },
        }

        base = base_prompts.get(mode, base_prompts["overlay"]).get(position, "")

        # 공통 품질 향상 프롬프트
        quality_suffix = ", professional advertising, high quality, photorealistic lighting, seamless integration"

        if user_prompt:
            prompt = f"{base}, {user_prompt}{quality_suffix}"
        else:
            prompt = f"{base}{quality_suffix}"

        return prompt

    def compose(
        self,
        background: Image.Image,
        text_asset: Image.Image,
        mask: Image.Image,
        mode: CompositionMode = "overlay",
        position: TextPosition = "top",
        user_prompt: Optional[str] = None,
        negative_prompt: Optional[str] = None,
        strength: float = 0.4,
        guidance_scale: float = 3.5,
        num_inference_steps: int = 28,
        seed: Optional[int] = None,
        progress_callback=None,
    ) -> Image.Image:
        """
        Flux Inpainting으로 지능형 합성 수행

        Args:
            background: 배경 이미지
            text_asset: 텍스트 에셋 이미지 (RGBA)
            mask: 합성 영역 마스크 (흰색=인페인팅, 검은색=보존)
            mode: 합성 모드 ("overlay"/"blend"/"behind")
            position: 텍스트 위치 ("top"/"center"/"bottom")
            user_prompt: 사용자 커스텀 프롬프트 (옵션)
            negative_prompt: 네거티브 프롬프트 (옵션)
            strength: 변환 강도 (0.0~1.0, 낮을수록 원본 보존)
            guidance_scale: 프롬프트 준수 강도
            num_inference_steps: 추론 스텝 수 (품질 우선: 28~50)
            seed: 난수 시드 (재현성 보장용, None=랜덤)
            progress_callback: 진행률 콜백

        Returns:
            Image.Image: 합성된 최종 이미지
        """
        self._load_pipeline()

        try:
            # 1. 초안 합성 (텍스트를 배경에 배치)
            logger.info(f"Creating composition draft: mode={mode}, position={position}")

            draft = background.copy().convert("RGBA")
            text_resized = text_asset.resize(draft.size, Image.LANCZOS)
            draft.paste(text_resized, (0, 0), text_resized)
            draft_rgb = draft.convert("RGB")

            # 2. 프롬프트 생성
            composition_prompt = self._build_composition_prompt(
                mode, position, user_prompt
            )
            logger.info(f"Composition prompt: {composition_prompt}")

            # 네거티브 프롬프트 설정
            default_negative = (
                "floating, disconnected, unrealistic, bad composition, low quality"
            )
            final_negative = (
                f"{negative_prompt}, {default_negative}"
                if negative_prompt
                else default_negative
            )

            # 3. Generator 설정 (재현성 보장)
            generator = None
            if seed is not None:
                generator = torch.Generator("cpu").manual_seed(seed)
                logger.info(f"Using seed: {seed} for reproducibility")
            else:
                logger.info("Using random seed")

            # 4. Flux Inpainting 실행
            logger.info(
                f"Running Flux Inpainting: strength={strength}, guidance={guidance_scale}, steps={num_inference_steps}"
            )

            def callback_fn(pipe_obj, step_index, timestep, callback_kwargs):
                if progress_callback:
                    progress_callback(
                        step_index + 1, num_inference_steps, "intelligent_composite"
                    )
                return callback_kwargs

            result = self.pipe(
                prompt=composition_prompt,
                negative_prompt=final_negative,
                image=draft_rgb,
                mask_image=mask,
                strength=strength,
                guidance_scale=guidance_scale,
                num_inference_steps=num_inference_steps,
                generator=generator,
                callback_on_step_end=callback_fn if progress_callback else None,
            ).images[0]

            logger.info("Composition completed successfully")

            return result

        except Exception as e:
            logger.error(f"Composition failed: {e}", exc_info=True)
            raise

        finally:
            self._unload_pipeline()

    def compose_simple(
        self, background: Image.Image, text_asset: Image.Image
    ) -> Image.Image:
        """
        Fallback: 단순 Alpha Composite

        Flux Inpainting 실패 시 기본 합성 방식으로 대체

        Args:
            background: 배경 이미지
            text_asset: 텍스트 에셋 (RGBA)

        Returns:
            Image.Image: 합성된 이미지
        """
        logger.warning("Using fallback simple composition (alpha composite)")

        base_comp = background.convert("RGBA")
        text_resized = text_asset.convert("RGBA")

        if base_comp.size != text_resized.size:
            text_resized = text_resized.resize(base_comp.size, Image.LANCZOS)

        final_comp = Image.alpha_composite(base_comp, text_resized)
        return final_comp.convert("RGB")
