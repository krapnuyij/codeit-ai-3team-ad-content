import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

import gc

import torch
from diffusers import (FluxImg2ImgPipeline, FluxInpaintPipeline, FluxPipeline,
                       FluxTransformer2DModel)
from helper_dev_utils import get_auto_logger
from PIL import Image
from transformers import BitsAndBytesConfig

from config import MODEL_IDS, TORCH_DTYPE
from utils import flush_gpu

logger = get_auto_logger()


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

    def generate_background(
        self,
        prompt: str,
        negative_prompt: str = None,
        guidance_scale: float = 3.5,
        seed: int = None,
        progress_callback=None,
        auto_unload: bool = True,
    ) -> Image.Image:
        """
        텍스트 프롬프트를 기반으로 배경 이미지를 생성합니다.

        Args:
            prompt (str): 배경 생성 프롬프트
            negative_prompt (str, optional): 배제할 요소들에 대한 부정 프롬프트
            guidance_scale (float): 프롬프트 준수 강도
            seed (int, optional): 난수 시드
            progress_callback (callable, optional): 진행률 콜백 함수
            auto_unload (bool): 생성 후 자동 언로드 여부 (기본값: True)

        Returns:
            Image.Image: 생성된 이미지
        """
        logger.info("[FluxGenerator] Generating background with Text-to-Image...")

        num_steps = 25

        def callback_fn(pipe_obj, step_index, timestep, callback_kwargs):
            if progress_callback:
                progress_callback(step_index + 1, num_steps, "flux_bg_generation")
            return callback_kwargs

        # 캐싱된 파이프라인 사용
        callback_fn(None, 0, None, None)

        pipe = self._load_t2i_pipeline()

        callback_fn(None, 0, None, None)

        generator = None
        if seed is not None:
            generator = torch.Generator("cpu").manual_seed(seed)

        logger.info(f" [FluxGenerator] prompt='{prompt}' ")
        logger.info(f" [FluxGenerator] negative_prompt='{negative_prompt}' ")

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

        if auto_unload:
            logger.info("[FluxGenerator] Auto-unloading after background generation")
            self.unload()

        return image

    def refine_image(
        self,
        draft_image: Image.Image,
        prompt: str = None,
        negative_prompt: str = None,
        strength: float = 0.6,
        guidance_scale: float = 3.5,
        seed: int = None,
        progress_callback=None,
        auto_unload: bool = True,
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
            auto_unload (bool): 생성 후 자동 언로드 여부 (기본값: True)

        Returns:
            Image.Image: 리터칭된 배경 합성 이미지
        """
        logger.info("[FluxGenerator] Refining image with Img2Img...")

        num_steps = 30

        def callback_fn(pipe_obj, step_index, timestep, callback_kwargs):
            if progress_callback:
                progress_callback(
                    step_index + 1, num_steps, "flux_bg_composition_refinement"
                )
            return callback_kwargs

        callback_fn(None, 0, None, None)

        # 캐싱된 파이프라인 사용
        pipe = self._load_i2i_pipeline()

        callback_fn(None, 0, None, None)

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

        logger.info(f" [FluxGenerator] prompt='{prompt}' ")
        logger.info(f" [FluxGenerator] negative_prompt='{negative_prompt}' ")

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

        if auto_unload:
            logger.info("[FluxGenerator] Auto-unloading after image refinement")
            self.unload()

        return refined_image

    def inject_features_via_inpaint(
        self,
        background: Image.Image,
        product_foreground: Image.Image,
        product_mask: Image.Image,
        position: tuple | str = "center",
        prompt: str = None,
        negative_prompt: str = None,
        strength: float = 0.5,
        guidance_scale: float = 3.5,
        num_inference_steps: int = 28,
        seed: int = None,
        product_scale: float = 0.75,
        progress_callback=None,
        auto_unload: bool = True,
    ) -> Image.Image:
        """
        Flux Inpainting을 사용하여 상품의 특성을 배경에 주입합니다.

        이 메서드는 상품 이미지를 배경에 자연스럽게 합성하기 위해 다음 프로세스를 수행합니다:
        1. 제품 이미지를 배경 크기 대비 비율(product_scale)로 스케일링 (가로세로 비율 유지)
        2. 스케일링된 제품을 지정된 position(좌표 또는 텍스트)에 배치
        3. Flux Inpainting으로 제품 영역에 특성 주입하여 배경과 자연스럽게 통합

        프로세스:
        1. 배경 이미지에 상품 위치 마스킹
        2. 상품 영역에 Inpainting으로 특성 주입
        3. 결과: 상품이 배경과 자연스럽게 통합된 이미지

        Args:
            background (Image.Image): 배경 이미지 (RGB 또는 RGBA)
            product_foreground (Image.Image): 상품 이미지 (투명 배경, RGBA 권장)
            product_mask (Image.Image): 상품 마스크 (L 모드, 255=상품 영역, 0=배경)
            position (tuple | str): 상품 배치 위치
                - tuple (x, y): 제품의 좌상단(left-top) 좌표 직접 지정
                  예: (0, 0) = 배경 좌상단, (512, 512) = 특정 위치
                - str: 텍스트 기반 위치 지정 (배경의 80% 영역 내 자동 배치, 10% 여백)
                  "center": 정중앙 (기본)
                  "top": 상단 중앙
                  "bottom": 하단 중앙
                  "left": 좌측 중앙
                  "right": 우측 중앙
                  "top-left": 좌상단
                  "top-right": 우상단
                  "bottom-left": 좌하단
                  "bottom-right": 우하단
            prompt (str): 특성 주입 프롬프트 (제품과 배경의 자연스러운 통합을 위한 설명)
            negative_prompt (str, optional): 부정 프롬프트 (원하지 않는 요소 명시)
            strength (float): Inpainting 강도 (0.0~1.0)
                낮을수록 원본 유지, 높을수록 프롬프트에 따라 변형
            guidance_scale (float): 프롬프트 준수 강도 (3.0~7.0 권장)
            num_inference_steps (int): 추론 스텝 수 (품질과 속도의 트레이드오프)
            seed (int, optional): 난수 시드 (재현성을 위해 고정값 사용 가능)
            product_scale (float): 배경 대비 제품 크기 비율 (기본값: 0.75, 즉 3/4 크기)
                1.0 = 배경과 동일 크기 (가로 또는 세로 중 작은 쪽 기준)
                0.75 = 배경의 75% 크기 (기본값, 적절한 여백 확보)
                0.5 = 배경의 50% 크기
                제품의 원본 가로세로 비율(aspect ratio)은 항상 유지됨
            progress_callback (callable, optional): 진행률 콜백 함수
                시그니처: callback(current_step, total_steps, stage_name)
            auto_unload (bool): 생성 후 자동 언로드 여부 (기본값: True)
                GPU 메모리 절약을 위해 True 권장

        Returns:
            Image.Image: 특성이 주입된 최종 이미지 (RGB)

        Note:
            - tuple position은 PIL.Image.paste()의 좌상단 좌표 기준
            - str position은 배경의 80% 영역 내 배치 (상하좌우 각 10% 여백)
            - product_scale은 배경의 가로/세로 중 작은 쪽을 기준으로 적용
            - 제품의 원본 가로세로 비율은 항상 유지되어 왜곡 없음
            - 마스크도 제품 이미지와 동일하게 스케일링되어 적용
        """
        logger.info("[FluxGenerator] Injecting features via Inpainting...")

        # Progress callback
        def callback_fn(pipe_obj, step_index, timestep, callback_kwargs):
            if progress_callback:
                progress_callback(
                    step_index + 1, num_inference_steps, "flux_feature_injection"
                )
            return callback_kwargs

        try:

            callback_fn(None, 0, None, None)

            # 캐싱된 파이프라인 사용
            pipe = self._load_inpaint_pipeline()

            callback_fn(None, 0, None, None)

            # === 1단계: 제품 이미지 스케일링 (배경 대비 비율 조정) ===
            # 배경 크기를 기준으로 target 크기 계산
            bg_width, bg_height = background.size
            target_width = int(bg_width * product_scale)
            target_height = int(bg_height * product_scale)

            # === 2단계: 가로세로 비율(aspect ratio) 유지하며 스케일링 ===
            # 원본 제품 이미지의 가로세로 비율을 계산
            prod_width, prod_height = product_foreground.size
            aspect_ratio = prod_width / prod_height

            # target 크기 내에서 비율을 유지하도록 실제 크기 결정
            if target_width / target_height > aspect_ratio:
                # 배경의 가로 비율이 제품보다 크면, 높이 기준으로 맞춤
                scaled_height = target_height
                scaled_width = int(scaled_height * aspect_ratio)
            else:
                # 배경의 세로 비율이 제품보다 크면, 너비 기준으로 맞춤
                scaled_width = target_width
                scaled_height = int(scaled_width / aspect_ratio)

            # === 3단계: 제품 이미지와 마스크를 동일한 크기로 리사이즈 ===
            # LANCZOS 리샘플링으로 고품질 스케일링
            scaled_product = product_foreground.resize(
                (scaled_width, scaled_height), Image.LANCZOS
            )
            scaled_mask = product_mask.resize(
                (scaled_width, scaled_height), Image.LANCZOS
            )

            logger.info(
                f"[FluxGenerator] Product scaled: original={product_foreground.size}, "
                f"scaled={scaled_product.size}, scale={product_scale}"
            )

            # === 4단계: 위치 계산 (텍스트 또는 좌표 기반) ===
            if isinstance(position, str):
                # 텍스트 기반 위치 지정: 배경의 80% 영역 내 배치 (10% 여백)
                margin_x = int(bg_width * 0.1)
                margin_y = int(bg_height * 0.1)
                usable_width = bg_width - 2 * margin_x
                usable_height = bg_height - 2 * margin_y

                position_lower = position.lower()

                # 수평 위치 계산
                if "left" in position_lower:
                    x = margin_x
                elif "right" in position_lower:
                    x = bg_width - margin_x - scaled_width
                else:  # center 또는 top/bottom (중앙 정렬)
                    x = margin_x + (usable_width - scaled_width) // 2

                # 수직 위치 계산
                if "top" in position_lower:
                    y = margin_y
                elif "bottom" in position_lower:
                    y = bg_height - margin_y - scaled_height
                else:  # center 또는 left/right (중앙 정렬)
                    y = margin_y + (usable_height - scaled_height) // 2

                # 좌표가 음수가 되지 않도록 보정
                x = max(0, x)
                y = max(0, y)

                final_position = (x, y)
                logger.info(
                    f"[FluxGenerator] Text position '{position}' resolved to coordinates: {final_position}"
                )
            else:
                # 좌표 직접 지정
                final_position = position
                logger.info(
                    f"[FluxGenerator] Using direct position coordinates: {final_position}"
                )

            # === 5단계: 초안 이미지 생성 (배경에 스케일링된 제품 배치) ===
            # 배경을 RGBA로 변환하여 투명도 처리 가능하도록 함
            draft = background.copy().convert("RGBA")
            # final_position(좌상단 좌표)에 제품 배치, 알파 채널을 마스크로 사용
            draft.paste(scaled_product, final_position, scaled_product)
            # Flux 파이프라인 입력을 위해 RGB로 변환
            draft_rgb = draft.convert("RGB")

            # === 6단계: Generator 설정 (재현성 확보) ===
            generator = None
            if seed is not None:
                generator = torch.Generator("cpu").manual_seed(seed)
            else:
                # 기본 시드 사용 (일정한 결과를 위해)
                generator = torch.Generator("cpu").manual_seed(42)

            logger.info(
                f"[FluxGenerator] Injecting features: prompt='{prompt[:50]}...', strength={strength}"
            )

            logger.info(f" [FluxGenerator] prompt='{prompt}' ")
            logger.info(f" [FluxGenerator] negative_prompt='{negative_prompt}' ")

            # === 7단계: Flux Inpainting 실행 ===
            # scaled_mask 영역만 재생성하여 제품 특성을 배경에 자연스럽게 주입
            # strength: 낮을수록 원본 유지, 높을수록 프롬프트 기반 변형
            result = pipe(
                prompt=prompt,
                negative_prompt=negative_prompt,
                image=draft_rgb,  # 제품이 배치된 초안 이미지
                mask_image=scaled_mask,  # 제품 영역 마스크 (255=인페인팅, 0=보존)
                strength=strength,
                guidance_scale=guidance_scale,
                num_inference_steps=num_inference_steps,
                generator=generator,
                callback_on_step_end=callback_fn if progress_callback else None,
            ).images[0]

            logger.info("[FluxGenerator] Feature injection completed")

            if auto_unload:
                logger.info("[FluxGenerator] Auto-unloading after feature injection")
                self.unload()

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
        negative_prompt: str = None,
        strength: float = 0.4,
        guidance_scale: float = 3.5,
        num_inference_steps: int = 28,
        seed: int = None,
        progress_callback=None,
        auto_unload: bool = True,
    ) -> Image.Image:  # 사용안함
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
            auto_unload (bool): 생성 후 자동 언로드 여부 (기본값: True)

        Returns:
            Image.Image: 합성된 최종 이미지
        """
        logger.info("[FluxGenerator] Compositing via Inpainting...")

        # Progress callback
        def callback_fn(pipe_obj, step_index, timestep, callback_kwargs):
            if progress_callback:
                progress_callback(
                    step_index + 1, num_inference_steps, "flux_inpaint_composite"
                )
            return callback_kwargs

        try:

            callback_fn(None, 0, None, None)

            # 캐싱된 파이프라인 사용
            pipe = self._load_inpaint_pipeline()

            callback_fn(None, 0, None, None)

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

            logger.info(
                f"[FluxGenerator] Running inpainting: prompt='{prompt[:50]}...', steps={num_inference_steps}"
            )

            logger.info(f" [FluxGenerator] prompt='{prompt}' ")
            logger.info(f" [FluxGenerator] negative_prompt='{negative_prompt}' ")

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

            if auto_unload:
                logger.info("[FluxGenerator] Auto-unloading after inpaint composite")
                self.unload()

            return result

        except Exception as e:
            logger.error(f"[FluxGenerator] Inpainting failed: {e}", exc_info=True)
            raise
