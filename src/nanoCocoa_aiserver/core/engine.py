import sys
import time
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from helper_dev_utils import get_auto_logger
from PIL import Image

from models.CompositionEngine import CompositionEngine
from models.flux_generator import FluxGenerator
from models.sdxl_base_generator import SDXLBaseGenerator
from models.sdxl_generator import SDXLGenerator
from models.sdxl_text import SDXLTextGenerator
from models.segmentation import SegmentationModel
from services.monitor import log_gpu_memory
from utils.MaskGenerator import MaskGenerator

logger = get_auto_logger()


class AIModelEngine:
    """
    AI 모델의 실행을 관리하는 오케스트레이터 클래스입니다.
    각 작업 단계별로 적절한 하위 모델 클래스(Segmentation, Flux, SDXL, Composition)를 호출하여 작업을 수행합니다.
    """

    def __init__(
        self, dummy_mode: bool = False, progress_callback=None, auto_unload: bool = True
    ):
        """
        Args:
            dummy_mode (bool): True일 경우 실제 모델을 로드하지 않고 더미 데이터를 반환합니다.
            progress_callback (callable, optional): 진행률 업데이트 콜백 함수 callback(step, total_steps, sub_step_name)
            auto_unload (bool): 각 단계 완료 후 모델을 자동으로 언로드할지 여부 (기본 True)
        """
        self.dummy_mode = dummy_mode
        self.progress_callback = progress_callback
        self.auto_unload = auto_unload

        if not self.dummy_mode:
            # 하위 모델 인스턴스 생성 (실제 모델 로딩은 각 클래스의 메서드 실행 시점에 발생)
            logger.debug("AIModelEngine: Initializing sub-models")
            self.segmenter = SegmentationModel()
            self.flux_gen = FluxGenerator()
            self.sdxl_gen = SDXLGenerator()
            self.sdxl_text_gen = SDXLTextGenerator()
            self.sdxl_base_gen = SDXLBaseGenerator()
            self.compositor = CompositionEngine()
            logger.debug("AIModelEngine: Initializing sub-models completed")
        else:
            logger.info("AIModelEngine initialized in DUMMY MODE.")
            # Dummy mode에서는 모델 인스턴스를 생성하지 않거나 모의 객체 사용

        logger.info(f"AIModelEngine initialized: auto_unload={auto_unload}")

    def _create_dummy_image(
        self, width: int = 1024, height: int = 1024, color: str = "gray"
    ) -> Image.Image:
        return Image.new("RGB", (width, height), color)

    def run_segmentation(self, image: Image.Image) -> tuple[Image.Image, Image.Image]:
        """
        BiRefNet을 사용하여 이미지의 배경을 제거(누끼 따기)합니다.

        Args:
            image (Image.Image): 입력 이미지

        Returns:
            tuple[Image.Image, Image.Image]: (배경이 제거된 이미지, 마스크 이미지)
        """
        if self.dummy_mode:
            # Dummy: 입력 이미지 그대로 혹은 단순 처리 반환
            return image.copy(), image.convert("L")

        return self.segmenter.run(image)

    def run_flux_bg_gen(
        self,
        prompt: str,
        negative_prompt: str = None,
        guidance_scale: float = 3.5,
        seed: int = None,
        auto_unload: bool = True,
    ) -> Image.Image:
        """
        Flux 모델을 로드하여 배경 이미지를 생성하고 즉시 언로드합니다.

        Args:
            prompt (str): 배경 생성을 위한 텍스트 프롬프트
            negative_prompt (str, optional): 배제할 요소들에 대한 부정 프롬프트
            guidance_scale (float): 프롬프트 준수 강도 (기본 3.5)
            seed (int, optional): 난수 시드

        Returns:
            Image.Image: 생성된 배경 이미지
        """
        if self.dummy_mode:
            logger.info(f"[DUMMY] Generating BG with prompt: {prompt}")

            total_steps = 10
            for i in range(total_steps):
                time.sleep(0.5)  # Simulate delay
                if self.progress_callback:
                    self.progress_callback(
                        step_num=i + 1,
                        total_steps=total_steps,
                        sub_step_name="flux_bg_generation",
                    )
            return self._create_dummy_image(1024, 1024, "lightblue")

        self.sdxl_base_gen.unload()

        return self.flux_gen.generate_background(
            prompt,
            negative_prompt,
            guidance_scale,
            seed,
            self.progress_callback,
            auto_unload=auto_unload,
        )

    def run_sdxl_bg_gen(
        self,
        prompt: str,
        negative_prompt: str = None,
        guidance_scale: float = 7.5,
        seed: int = None,
        auto_unload: bool = True,
    ) -> Image.Image:
        return self.sdxl_gen.generate_background(
            prompt,
            negative_prompt,
            guidance_scale,
            seed,
            self.progress_callback,
            auto_unload=auto_unload,
        )

    def run_sdxl_inpaint_injection(
        self,
        background: Image.Image,
        user_bg: Image.Image,
        prompt: str,
        negative_prompt: str = None,
        strength: float = 0.5,
        guidance_scale: float = 3.5,
        seed: int = None,
        auto_unload: bool = True,
    ) -> Image.Image:
        return self.sdxl_gen.generate_background_image(
            user_bg=user_bg,
            prompt=prompt,
            negative_prompt=negative_prompt,
            strength=strength,
            guidance_scale=guidance_scale,
            seed=seed,
            auto_unload=auto_unload,
        )

    def run_sdxl_base_bg_gen(
        self,
        prompt: str,
        negative_prompt: str = None,
        guidance_scale: float = 7.5,
        seed: int = None,
        auto_unload: bool = True,
    ) -> Image.Image:
        """
        SDXL 모델을 로드하여 배경 이미지를 생성하고 즉시 언로드합니다.

        Args:
            prompt (str): 배경 생성을 위한 텍스트 프롬프트
            negative_prompt (str, optional): 배제할 요소들에 대한 부정 프롬프트
            guidance_scale (float): 프롬프트 준수 강도 (기본 7.5, SDXL 권장값)
            seed (int, optional): 난수 시드

        Returns:
            Image.Image: 생성된 배경 이미지
        """
        if self.dummy_mode:
            logger.info(f"[DUMMY] Generating BG with SDXL: {prompt}")

            total_steps = 10
            for i in range(total_steps):
                time.sleep(0.5)  # Simulate delay
                if self.progress_callback:
                    self.progress_callback(
                        step_num=i + 1,
                        total_steps=total_steps,
                        sub_step_name="sdxl_bg_generation",
                    )
            return self._create_dummy_image(1024, 1024, "lightgreen")

        return self.sdxl_base_gen.generate_background(
            prompt,
            negative_prompt,
            guidance_scale,
            seed,
            self.progress_callback,
            auto_unload=auto_unload,
        )

    def run_flux_refinement(
        self,
        draft_image: Image.Image,
        prompt: str = None,
        negative_prompt: str = None,
        strength: float = 0.6,
        guidance_scale: float = 3.5,
        seed: int = None,
        auto_unload: bool = True,
    ) -> Image.Image:
        """
        Flux Img2Img 모델을 로드하여 초안 이미지를 리터칭(배경 합성)하고 언로드합니다.

        Args:
            draft_image (Image.Image): 리터칭할 초안 이미지
            prompt (str, optional): 배경 합성을 위한 프롬프트.
            negative_prompt (str, optional): 배경 합성 부정 프롬프트.
            strength (float): 변환 강도 (0.0 ~ 1.0). 기본 0.6.
            guidance_scale (float): 프롬프트 준수 강도. 기본 3.5.
            seed (int, optional): 난수 시드.

        Returns:
            Image.Image: 리터칭된 최종 배경 합성 이미지
        """
        if self.dummy_mode:
            logger.info(f"[DUMMY] Refining image with strength: {strength}")
            import time

            total_steps = 5
            for i in range(total_steps):
                time.sleep(0.5)
                if self.progress_callback:
                    self.progress_callback(
                        step_num=i + 1,
                        total_steps=total_steps,
                        sub_step_name="flux_refinement",
                    )
            return draft_image.copy()  # 단순 복사

        logger.info(f"prompt={prompt}")
        logger.info(f"negative_prompt={negative_prompt}")

        self.sdxl_base_gen.unload()

        return self.flux_gen.refine_image(
            draft_image=draft_image,
            prompt=prompt,
            negative_prompt=negative_prompt,
            strength=strength,
            guidance_scale=guidance_scale,
            seed=seed,
            progress_callback=self.progress_callback,
            auto_unload=auto_unload,
        )

    def run_flux_inpaint_injection(
        self,
        background: Image.Image,
        product_foreground: Image.Image,
        product_mask: Image.Image,
        position: tuple,
        prompt: str,
        negative_prompt: str = None,
        strength: float = 0.5,
        guidance_scale: float = 3.5,
        seed: int = None,
        auto_unload: bool = True,
    ) -> Image.Image:
        """
        Flux Inpainting을 사용하여 상품 특성을 배경에 주입합니다.

        Args:
            background (Image.Image): 배경 이미지
            product_foreground (Image.Image): 상품 이미지 (RGBA)
            product_mask (Image.Image): 상품 마스크 (L)
            position (tuple): 상품 배치 위치 (x, y)
            prompt (str): 특성 주입 프롬프트
            negative_prompt (str, optional): 부정 프롬프트
            strength (float): Inpainting 강도
            guidance_scale (float): 프롬프트 준수 강도
            seed (int, optional): 난수 시드

        Returns:
            Image.Image: 특성이 주입된 최종 이미지
        """
        if self.dummy_mode:
            logger.info(f"[DUMMY] Injecting features with strength: {strength}")
            total_steps = 10
            for i in range(total_steps):
                time.sleep(0.5)
                if self.progress_callback:
                    self.progress_callback(
                        step_num=i + 1,
                        total_steps=total_steps,
                        sub_step_name="flux_feature_injection",
                    )
            return background.copy()

        logger.info(f"prompt={prompt}")
        logger.info(f"negative_prompt={negative_prompt}")

        self.sdxl_base_gen.unload()

        return self.flux_gen.inject_features_via_inpaint(
            background=background,
            product_foreground=product_foreground,
            product_mask=product_mask,
            position=position,
            prompt=prompt,
            negative_prompt=negative_prompt,
            strength=strength,
            guidance_scale=guidance_scale,
            seed=seed,
            auto_unload=auto_unload,
            progress_callback=self.progress_callback,
        )

    def run_sdxl_text_gen(
        self,
        canny_map: Image.Image,
        prompt: str,
        negative_prompt: str,
        seed: int = None,
    ) -> Image.Image:
        """
        SDXL ControlNet을 로드하여 3D 텍스트 효과를 생성하고 언로드합니다.

        Args:
            canny_map (Image.Image): 텍스트의 윤곽선(Canny) 이미지
            prompt (str): 생성할 텍스트 효과에 대한 프롬프트
            negative_prompt (str): 생성 시 제외할 요소들에 대한 부정 프롬프트
            seed (int, optional): 난수 시드 (None이면 랜덤 생성)

        Returns:
            Image.Image: 생성된 3D 텍스트 이미지
        """
        if self.dummy_mode:
            logger.info(f"[DUMMY] Generating 3D Text with prompt: {prompt}")
            total_steps = 8
            for i in range(total_steps):
                time.sleep(0.5)
                if self.progress_callback:
                    self.progress_callback(
                        step_num=i + 1,
                        total_steps=total_steps,
                        sub_step_name="sdxl_text_gen",
                    )
            return self._create_dummy_image(1024, 1024, "yellow")

        logger.info(f"prompt={prompt}")
        logger.info(f"negative_prompt={negative_prompt}")

        return self.sdxl_text_gen.generate_text_effect(
            canny_map, prompt, negative_prompt, seed, self.progress_callback
        )

    def run_intelligent_composite(
        self,
        background: Image.Image,
        text_asset: Image.Image,
        composition_mode: str = "overlay",
        text_position: str = "top",
        user_prompt: str = None,
        negative_prompt: str = None,
        strength: float = 0.4,
        num_inference_steps: int = 28,
        seed: int = None,
    ) -> Image.Image:
        """
        CompositionEngine을 사용하여 프롬프트 기반 지능형 합성을 수행합니다.

        Args:
            background (Image.Image): 배경 이미지
            text_asset (Image.Image): 텍스트 에셋 (RGBA)
            composition_mode (str): 합성 모드 ("overlay"/"blend"/"behind")
            text_position (str): 텍스트 위치 ("top"/"center"/"bottom")
            user_prompt (str, optional): 사용자 커스텀 프롬프트
            strength (float): 변환 강도 (0.0~1.0)
            num_inference_steps (int): 추론 스텝 수 (품질 우선: 28~50)
            seed (int, optional): 난수 시드

        Returns:
            Image.Image: 합성된 최종 이미지
        """
        if self.dummy_mode:
            logger.info(
                f"[DUMMY] Compositing: mode={composition_mode}, position={text_position}"
            )
            for i in range(5):
                time.sleep(0.5)
                if self.progress_callback:
                    self.progress_callback(
                        step_num=i + 1,
                        total_steps=5,
                        sub_step_name="intelligent_composite",
                    )
            # 단순 합성 반환
            draft = background.copy().convert("RGBA")
            text_resized = text_asset.resize(draft.size, Image.LANCZOS).convert("RGBA")
            # 알파 채널 추출 (L 모드)
            mask = text_resized.split()[3] if text_resized.mode == "RGBA" else None
            draft.paste(text_resized, (0, 0), mask)
            return draft.convert("RGB")

        # 마스크 생성
        mask_mode = (
            composition_mode if composition_mode in ["overlay", "auto"] else "overlay"
        )
        mask = MaskGenerator.create_combined_mask(
            background, text_asset, position=text_position, mode=mask_mode
        )

        logger.info(f"prompt={user_prompt}")
        logger.info(f"negative_prompt={negative_prompt}")

        # Composition Engine 실행
        result = self.compositor.compose(
            background=background,
            text_asset=text_asset,
            mask=mask,
            mode=composition_mode,
            position=text_position,
            user_prompt=user_prompt,
            negative_prompt=negative_prompt,
            strength=strength,
            num_inference_steps=num_inference_steps,
            seed=seed,
            progress_callback=self.progress_callback,
        )

        # Step 3 완료 후 자동 언로드
        if self.auto_unload:
            self.compositor.unload()

        return result

    def unload_step1_models(self) -> None:
        """
        Step 1에서 사용된 모델들을 명시적으로 언로드합니다.
        (Flux 배경 생성 모델)
        """
        if self.dummy_mode:
            return

        log_gpu_memory("Before Step1 models unload")

        self.flux_gen.unload()
        self.sdxl_gen.unload()
        self.sdxl_base_gen.unload()

        log_gpu_memory("After Step1 models unload")
        logger.info("Step 1 models unloaded")

    def unload_step2_models(self) -> None:
        """
        Step 2에서 사용된 모델들을 명시적으로 언로드합니다.
        (SDXL ControlNet, BiRefNet)
        """
        if self.dummy_mode:
            return

        log_gpu_memory("Before Step2 models unload")

        self.sdxl_gen.unload()
        self.sdxl_text_gen.unload()
        self.segmenter.unload()

        log_gpu_memory("After Step2 models unload")
        logger.info("Step 2 models unloaded")

    def unload_all_models(self) -> None:
        """
        모든 모델을 명시적으로 언로드합니다.
        워커 프로세스 종료 전 GPU 메모리 정리용입니다.
        """
        if self.dummy_mode:
            return

        logger.info("[Engine] Starting full model unload")
        log_gpu_memory("Before all models unload")

        self.flux_gen.unload()
        self.sdxl_gen.unload()
        self.sdxl_base_gen.unload()
        self.sdxl_text_gen.unload()
        self.compositor.unload()

        log_gpu_memory("After all models unload")
        logger.info("[Engine] All models unloaded")
