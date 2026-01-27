import sys
import time
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from PIL import Image
from typing import Optional, Tuple, Dict, Any
from helper_dev_utils import get_auto_logger

from models.flux2_generator import Flux2Generator
from models.qwen3_analyzer import Qwen3Analyzer
from models.llm_prompt import LLMPrompt

from services.monitor import log_gpu_memory
from utils.MaskGenerator import MaskGenerator

logger = get_auto_logger()


class AIModelEngine:
    """
    AI 모델의 실행을 관리하는 오케스트레이터 클래스입니다.
    각 작업 단계별로 적절한 하위 모델 클래스(Segmentation, Flux, SDXL, Composition)를 호출하여 작업을 수행합니다.
    """

    def __init__(
        self,
        dummy_mode: bool = False,
        progress_callback=None,
        auto_unload: bool = False,
    ):
        """
        Args:
            dummy_mode (bool): True일 경우 실제 모델을 로드하지 않고 더미 데이터를 반환합니다.
            progress_callback (callable, optional): 진행률 업데이트 콜백 함수 callback(step, total_steps, sub_step_name)
            auto_unload (bool): 각 단계 완료 후 모델을 자동으로 언로드할지 여부 (기본 False, 워커 풀 환경에서는 메모리 유지)
        """
        self.dummy_mode = dummy_mode
        self.progress_callback = progress_callback
        self.auto_unload = auto_unload

        if not self.dummy_mode:
            # 하위 모델 인스턴스 생성 (실제 모델 로딩은 각 클래스의 메서드 실행 시점에 발생)
            logger.debug("AIModelEngine: Initializing sub-models")
            self.flux2_gen = Flux2Generator()
            self.qwen3_analyzer = Qwen3Analyzer()
            self.llm_prompt = LLMPrompt(qwen=self.qwen3_analyzer)
            logger.debug("AIModelEngine: Initializing sub-models completed")
        else:
            logger.info("AIModelEngine initialized in DUMMY MODE.")
            # Dummy mode에서는 모델 인스턴스를 생성하지 않거나 모의 객체 사용

        logger.info(f"AIModelEngine initialized: auto_unload={auto_unload}")

    def _create_dummy_image(
        self, width: int = 1024, height: int = 1024, color: str = "gray"
    ) -> Image.Image:
        return Image.new("RGB", (width, height), color)

    def run_text2image(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        guidance_scale: Optional[float] = 3.5,
        seed: Optional[int] = None,
        auto_unload: Optional[bool] = False,
    ) -> Image.Image:
        """
        Flux 모델을 로드하여 배경 이미지를 생성합니다.

        Args:
            prompt (str): 배경 생성을 위한 텍스트 프롬프트
            negative_prompt (str, optional): 배제할 요소들에 대한 부정 프롬프트
            guidance_scale (float): 프롬프트 준수 강도 (기본 3.5)
            seed (int, optional): 난수 시드
            auto_unload (bool): 생성 후 모델 언로드 여부 (기본 False, 워커 풀 환경에서는 유지)

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

        result_image, result_seed = self.flux2_gen.generate(
            prompt=prompt,
            negative_prompt=negative_prompt,
            guidance_scale=guidance_scale,
            seed=seed,
            progress_callback=self.progress_callback,
            auto_unload=auto_unload,
        )

        return result_image

    def run_image2image(
        self,
        input_image: Image.Image,
        prompt: Optional[str] = None,
        negative_prompt: Optional[str] = None,
        strength: Optional[float] = 0.6,
        guidance_scale: Optional[float] = 3.5,
        seed: Optional[int] = None,
        auto_unload: Optional[bool] = False,
    ) -> Image.Image:
        """
        Flux Img2Img 모델을 로드하여 초안 이미지를 리터칭(배경 합성)합니다.

        Args:
            input_image (Image.Image): 재품 이미지
            prompt (Optional[str], optional): 배경 합성을 위한 프롬프트.
            negative_prompt (Optional[str], optional): 배경 합성 부정 프롬프트.
            strength (Optional[float]): 변환 강도 (0.0 ~ 1.0). 기본 0.6.
            guidance_scale (Optional[float]): 프롬프트 준수 강도. 기본 3.5.
            seed (Optional[int], optional): 난수 시드.
            auto_unload (bool): 생성 후 모델 언로드 여부 (기본 False, 워커 풀 환경에서는 유지)
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
            return input_image.copy()  # 단순 복사

        logger.info(f"prompt={prompt}")
        logger.info(f"negative_prompt={negative_prompt}")

        image_analyze = self.qwen3_analyzer.analyze_image_flux_product(
            image=input_image, auto_unload=False
        )

        flux_prompt = self.llm_prompt.generate_flux_prompt(
            product_prompt=image_analyze,
            image_edit_prompt=f"제품과 잘 조화 되도록 배경을 리터칭 한다. {prompt if prompt else ''}",
        )

        logger.debug(f"Generated FLUX Prompt: {flux_prompt}")

        result_image, result_seed = self.flux2_gen.generate(
            input_image=input_image,
            prompt=flux_prompt,
            negative_prompt=negative_prompt,
            guidance_scale=guidance_scale,
            seed=seed,
            progress_callback=self.progress_callback,
            auto_unload=auto_unload,
        )

        return result_image

    async def run_composite(
        self,
        bg_image: Image.Image,
        ad_text: str,
        text_prompt: Optional[str] = None,
        composition_prompt: Optional[str] = None,
    ) -> Image.Image:
        """
        배경 이미지에 광고 텍스트와 레이아웃을 적용하여 최종 광고 이미지를 합성합니다.
        LLM을 통해 HTML 기반의 텍스트 레이아웃을 생성하고 이를 PNG 이미지로 렌더링합니다.

        Args:
            bg_image (Image.Image): 배경 이미지
            ad_text (str): 광고에 표시할 텍스트 내용 (필수)
            text_prompt (Optional[str]): 텍스트 스타일 및 표현 방식에 대한 프롬프트
            composition_prompt (Optional[str]): 전체 레이아웃 구성에 대한 프롬프트

        Returns:
            Image.Image: 텍스트와 레이아웃이 합성된 최종 광고 이미지
        """
        # LLM을 사용하여 HTML 기반 광고 이미지 생성
        html_image = await self.llm_prompt.generate_prompt_html_png(
            image=bg_image,
            ad_text=ad_text,
            text_prompt=text_prompt,
            composition_prompt=composition_prompt,
        )

        return html_image
