import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

import torch
import gc
from PIL import Image
from diffusers import (
    FluxPipeline,
    FluxImg2ImgPipeline,
    FluxInpaintPipeline,
    FluxTransformer2DModel,
)
from transformers import BitsAndBytesConfig
from config import MODEL_IDS, TORCH_DTYPE, logger
from utils import flush_gpu


class FluxGenerator:
    """
    FLUX 모델을 사용하여 배경 생성, 이미지 리파인, 지능형 합성을 수행하는 클래스입니다.

    8bit 양자화와 파이프라인 캐싱으로 GPU 메모리를 효율적으로 사용합니다.
    """

    def __init__(self):
        """파이프라인 인스턴스 초기화 (실제 로딩은 각 메서드 호출 시 수행)"""
        self.t2i_pipe = None  # Text-to-Image
        self.i2i_pipe = None  # Img2Img
        self.inpaint_pipe = None  # Inpaint
        self.transformer = None  # 공유 Transformer (8bit 양자화)
        logger.info("FluxGenerator initialized (pipelines will load on demand)")

    def _load_transformer(self):
        """8bit 양자화된 Transformer 로딩 (모든 파이프라인에서 공유)"""
        if self.transformer is not None:
            return self.transformer

        logger.info("[FluxGenerator] Loading 8bit quantized Transformer...")
        quant_config = BitsAndBytesConfig(load_in_8bit=True)
        self.transformer = FluxTransformer2DModel.from_pretrained(
            MODEL_IDS["FLUX"],
            subfolder="transformer",
            quantization_config=quant_config,
            torch_dtype=TORCH_DTYPE,
        )
        logger.info("[FluxGenerator] Transformer loaded with 8bit quantization")
        return self.transformer

    def _load_t2i_pipeline(self):
        """Text-to-Image 파이프라인 로딩 (캐싱)"""
        if self.t2i_pipe is not None:
            return self.t2i_pipe

        logger.info("[FluxGenerator] Loading FLUX Text-to-Image pipeline...")
        transformer = self._load_transformer()
        self.t2i_pipe = FluxPipeline.from_pretrained(
            MODEL_IDS["FLUX"],
            transformer=transformer,
            torch_dtype=TORCH_DTYPE,
        )
        self.t2i_pipe.enable_model_cpu_offload()
        self.t2i_pipe.enable_attention_slicing()
        if hasattr(self.t2i_pipe, "vae") and hasattr(
            self.t2i_pipe.vae, "enable_slicing"
        ):
            self.t2i_pipe.vae.enable_slicing()
        logger.info("[FluxGenerator] Text-to-Image pipeline ready")
        return self.t2i_pipe

    def _load_i2i_pipeline(self):
        """Img2Img 파이프라인 로딩 (캐싱)"""
        if self.i2i_pipe is not None:
            return self.i2i_pipe

        logger.info("[FluxGenerator] Loading FLUX Img2Img pipeline...")
        transformer = self._load_transformer()
        self.i2i_pipe = FluxImg2ImgPipeline.from_pretrained(
            MODEL_IDS["FLUX"],
            transformer=transformer,
            torch_dtype=TORCH_DTYPE,
        )
        self.i2i_pipe.enable_model_cpu_offload()
        self.i2i_pipe.enable_attention_slicing()
        if hasattr(self.i2i_pipe, "vae") and hasattr(
            self.i2i_pipe.vae, "enable_slicing"
        ):
            self.i2i_pipe.vae.enable_slicing()
        logger.info("[FluxGenerator] Img2Img pipeline ready")
        return self.i2i_pipe

    def _load_inpaint_pipeline(self):
        """Inpaint 파이프라인 로딩 (캐싱)"""
        if self.inpaint_pipe is not None:
            return self.inpaint_pipe

        logger.info("[FluxGenerator] Loading FLUX Inpaint pipeline...")
        transformer = self._load_transformer()
        self.inpaint_pipe = FluxInpaintPipeline.from_pretrained(
            MODEL_IDS["FLUX"],
            transformer=transformer,
            torch_dtype=TORCH_DTYPE,
        )
        self.inpaint_pipe.enable_model_cpu_offload()
        self.inpaint_pipe.enable_attention_slicing()
        if hasattr(self.inpaint_pipe, "vae") and hasattr(
            self.inpaint_pipe.vae, "enable_slicing"
        ):
            self.inpaint_pipe.vae.enable_slicing()
        logger.info("[FluxGenerator] Inpaint pipeline ready")
        return self.inpaint_pipe

    def generate_background(
        self,
        prompt: str,
        negative_prompt: str = None,
        guidance_scale: float = 3.5,
        seed: int = None,
        progress_callback=None,
    ) -> Image.Image:
        """
        텍스트 프롬프트를 기반으로 배경 이미지를 생성합니다.

        Args:
            prompt (str): 배경 생성 프롬프트
            negative_prompt (str, optional): 배제할 요소들에 대한 부정 프롬프트
            guidance_scale (float): 프롬프트 준수 강도
            seed (int, optional): 난수 시드
            progress_callback (callable, optional): 진행률 콜백 함수

        Returns:
            Image.Image: 생성된 이미지
        """
        logger.info("[FluxGenerator] Generating background with Text-to-Image...")

        # 캐싱된 파이프라인 사용
        pipe = self._load_t2i_pipeline()

        generator = None
        if seed is not None:
            generator = torch.Generator("cpu").manual_seed(seed)

        num_steps = 25

        def callback_fn(pipe_obj, step_index, timestep, callback_kwargs):
            if progress_callback:
                progress_callback(step_index + 1, num_steps, "flux_bg_generation")
            return callback_kwargs

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

        logger.info("[FluxGenerator] Background generation completed")
        return image

    def unload(self) -> None:
        """
        명시적으로 Flux 모델 리소스를 정리합니다.

        캐싱된 모든 파이프라인과 Transformer를 삭제하여 GPU 메모리를 해제합니다.
        """
        from services.monitor import log_gpu_memory

        log_gpu_memory("FluxGenerator unload (before)")

        # 모든 파이프라인 삭제
        if self.t2i_pipe is not None:
            del self.t2i_pipe
            self.t2i_pipe = None

        if self.i2i_pipe is not None:
            del self.i2i_pipe
            self.i2i_pipe = None

        if self.inpaint_pipe is not None:
            del self.inpaint_pipe
            self.inpaint_pipe = None

        # Transformer 삭제
        if self.transformer is not None:
            del self.transformer
            self.transformer = None

        flush_gpu()
        log_gpu_memory("FluxGenerator unload (after)")
        logger.info("FluxGenerator unloaded (all pipelines cleared)")

    def refine_image(
        self,
        draft_image: Image.Image,
        prompt: str = None,
        negative_prompt: str = None,
        strength: float = 0.6,
        guidance_scale: float = 3.5,
        seed: int = None,
        progress_callback=None,
    ) -> Image.Image:
        """
        이미지를 리터칭(Img2Img, 배경 합성)하여 품질을 높입니다.

        Args:
            draft_image (Image.Image): 초안 이미지
            prompt (str): 배경 합성 프롬프트 (없을 경우 기본값 사용)
            negative_prompt (str): 배경 합성 부정 프롬프트 (없을 경우 기본값 사용)
            strength (float): 변환 강도
            guidance_scale (float): 프롬프트 준수 강도
            seed (int, optional): 난수 시드
            progress_callback (callable, optional): 진행률 콜백 함수

        Returns:
            Image.Image: 리터칭된 배경 합성 이미지
        """
        logger.info("[FluxGenerator] Refining image with Img2Img...")

        # 캐싱된 파이프라인 사용
        pipe = self._load_i2i_pipeline()

        default_prompt = (
            "A photorealistic close-up shot of a product lying naturally on a surface. "
            "Heavy contact shadows, ambient occlusion, texture reflection, "
            "warm sunlight, cinematic lighting, 8k, extremely detailed."
        )
        use_prompt = prompt if prompt else default_prompt

        default_negative = "floating, disconnected, unrealistic shadows, artificial lighting, cut out, sticker effect"
        use_negative = negative_prompt if negative_prompt else default_negative

        generator = None
        if seed is not None:
            generator = torch.Generator("cpu").manual_seed(seed)
        else:
            generator = torch.Generator("cpu").manual_seed(42)

        num_steps = 30

        def callback_fn(pipe_obj, step_index, timestep, callback_kwargs):
            if progress_callback:
                progress_callback(
                    step_index + 1, num_steps, "flux_bg_composition_refinement"
                )
            return callback_kwargs

        refined_image = pipe(
            use_prompt,
            negative_prompt=use_negative,
            image=draft_image,
            strength=strength,
            num_inference_steps=num_steps,
            guidance_scale=guidance_scale,
            generator=generator,
            callback_on_step_end=callback_fn if progress_callback else None,
        ).images[0]

        logger.info("[FluxGenerator] Image refinement completed")
        return refined_image

    def inject_features_via_inpaint(
        self,
        background: Image.Image,
        product_foreground: Image.Image,
        product_mask: Image.Image,
        position: tuple,
        prompt: str,
        negative_prompt: str = None,
        strength: float = 0.5,
        guidance_scale: float = 3.5,
        num_inference_steps: int = 28,
        seed: int = None,
        progress_callback=None,
    ) -> Image.Image:
        """
        Flux Inpainting을 사용하여 상품의 특성을 배경에 주입합니다.

        프로세스:
        1. 배경 이미지에 상품 위치 마스킹
        2. 상품 영역에 Inpainting으로 특성 주입
        3. 결과: 상품이 배경과 자연스럽게 통합된 이미지

        Args:
            background (Image.Image): 배경 이미지
            product_foreground (Image.Image): 상품 이미지 (투명 배경, RGBA)
            product_mask (Image.Image): 상품 마스크 (L 모드, 255=상품 영역)
            position (tuple): 상품 배치 위치 (x, y)
            prompt (str): 특성 주입 프롬프트
            negative_prompt (str, optional): 부정 프롬프트
            strength (float): Inpainting 강도 (0.0~1.0)
            guidance_scale (float): 프롬프트 준수 강도
            num_inference_steps (int): 추론 스텝 수
            seed (int, optional): 난수 시드
            progress_callback (callable, optional): 진행률 콜백

        Returns:
            Image.Image: 특성이 주입된 최종 이미지
        """
        logger.info("[FluxGenerator] Injecting features via Inpainting...")

        try:
            # 캐싱된 파이프라인 사용
            pipe = self._load_inpaint_pipeline()

            # 초안 이미지 생성 (상품을 배경에 임시 배치)
            draft = background.copy().convert("RGBA")
            draft.paste(product_foreground, position, product_foreground)
            draft_rgb = draft.convert("RGB")

            # Generator 설정
            generator = None
            if seed is not None:
                generator = torch.Generator("cpu").manual_seed(seed)
            else:
                generator = torch.Generator("cpu").manual_seed(42)

            # Progress callback
            def callback_fn(pipe_obj, step_index, timestep, callback_kwargs):
                if progress_callback:
                    progress_callback(
                        step_index + 1, num_inference_steps, "flux_feature_injection"
                    )
                return callback_kwargs

            logger.info(
                f"[FluxGenerator] Injecting features: prompt='{prompt[:50]}...', strength={strength}"
            )

            # Inpainting 실행 (상품 영역만 재생성하여 특성 주입)
            result = pipe(
                prompt=prompt,
                negative_prompt=negative_prompt,
                image=draft_rgb,
                mask_image=product_mask,
                strength=strength,
                guidance_scale=guidance_scale,
                num_inference_steps=num_inference_steps,
                generator=generator,
                callback_on_step_end=callback_fn if progress_callback else None,
            ).images[0]

            logger.info("[FluxGenerator] Feature injection completed")
            return result

        except Exception as e:
            logger.error(
                f"[FluxGenerator] Feature injection failed: {e}", exc_info=True
            )
            raise

    def inpaint_composite(
        self,
        background: Image.Image,
        text_asset: Image.Image,
        mask: Image.Image,
        prompt: str,
        strength: float = 0.4,
        guidance_scale: float = 3.5,
        num_inference_steps: int = 28,
        seed: int = None,
        progress_callback=None,
    ) -> Image.Image:
        """
        Flux Inpainting을 사용하여 텍스트를 배경과 맥락적으로 합성합니다.

        Args:
            background (Image.Image): 배경 이미지
            text_asset (Image.Image): 텍스트 에셋 (RGBA)
            mask (Image.Image): 합성 영역 마스크 (255=인페인팅, 0=보존)
            prompt (str): 합성 프롬프트
            strength (float): 변환 강도 (0.0~1.0)
            guidance_scale (float): 프롬프트 준수 강도
            num_inference_steps (int): 추론 스텝 수 (품질 우선: 28~50)
            seed (int, optional): 난수 시드
            progress_callback (callable, optional): 진행률 콜백

        Returns:
            Image.Image: 합성된 최종 이미지
        """
        logger.info("[FluxGenerator] Compositing via Inpainting...")

        try:
            # 캐싱된 파이프라인 사용
            pipe = self._load_inpaint_pipeline()

            # 초안 합성 (텍스트를 배경에 배치)
            draft = background.copy().convert("RGBA")
            text_resized = text_asset.resize(draft.size, Image.LANCZOS)
            draft.paste(text_resized, (0, 0), text_resized)
            draft_rgb = draft.convert("RGB")

            # Generator 설정
            generator = None
            if seed is not None:
                generator = torch.Generator("cpu").manual_seed(seed)
            else:
                generator = torch.Generator("cpu").manual_seed(42)

            # Progress callback
            def callback_fn(pipe_obj, step_index, timestep, callback_kwargs):
                if progress_callback:
                    progress_callback(
                        step_index + 1, num_inference_steps, "flux_inpaint_composite"
                    )
                return callback_kwargs

            logger.info(
                f"[FluxGenerator] Running inpainting: prompt='{prompt[:50]}...', steps={num_inference_steps}"
            )

            # Inpainting 실행
            result = pipe(
                prompt=prompt,
                image=draft_rgb,
                mask_image=mask,
                strength=strength,
                guidance_scale=guidance_scale,
                num_inference_steps=num_inference_steps,
                generator=generator,
                callback_on_step_end=callback_fn if progress_callback else None,
            ).images[0]

            logger.info("[FluxGenerator] Inpainting composition completed")
            return result

        except Exception as e:
            logger.error(f"[FluxGenerator] Inpainting failed: {e}", exc_info=True)
            raise
