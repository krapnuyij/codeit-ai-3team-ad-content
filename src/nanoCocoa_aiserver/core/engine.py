import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from PIL import Image
from models.segmentation import SegmentationModel
from models.flux_generator import FluxGenerator
from models.sdxl_text import SDXLTextGenerator
from models.CompositionEngine import CompositionEngine
from utils.MaskGenerator import MaskGenerator
from config import logger


class AIModelEngine:
    """
    AI 모델의 실행을 관리하는 오케스트레이터 클래스입니다.
    각 작업 단계별로 적절한 하위 모델 클래스(Segmentation, Flux, SDXL, Composition)를 호출하여 작업을 수행합니다.
    """
    def __init__(self, dummy_mode: bool = False, progress_callback=None):
        """
        Args:
            dummy_mode (bool): True일 경우 실제 모델을 로드하지 않고 더미 데이터를 반환합니다.
            progress_callback (callable, optional): 진행률 업데이트 콜백 함수 callback(step, total_steps, sub_step_name)
        """
        self.dummy_mode = dummy_mode
        self.progress_callback = progress_callback
        
        if not self.dummy_mode:
            # 하위 모델 인스턴스 생성 (실제 모델 로딩은 각 클래스의 메서드 실행 시점에 발생)
            self.segmenter = SegmentationModel()
            self.flux_gen = FluxGenerator()
            self.sdxl_gen = SDXLTextGenerator()
            self.compositor = CompositionEngine()
        else:
            logger.info("AIModelEngine initialized in DUMMY MODE.")
            # Dummy mode에서는 모델 인스턴스를 생성하지 않거나 모의 객체 사용

    def _create_dummy_image(self, width: int = 1024, height: int = 1024, color: str = "gray") -> Image.Image:
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

    def run_flux_bg_gen(self, prompt: str, negative_prompt: str = None, guidance_scale: float = 3.5, seed: int = None) -> Image.Image:
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
            import time
            total_steps = 10
            for i in range(total_steps):
                time.sleep(0.5)  # Simulate delay
                if self.progress_callback:
                    self.progress_callback(i + 1, total_steps, "flux_bg_generation")
            return self._create_dummy_image(1024, 1024, "lightblue")
            
        return self.flux_gen.generate_background(prompt, negative_prompt, guidance_scale, seed, self.progress_callback)

    def run_flux_refinement(self, draft_image: Image.Image, prompt: str = None, negative_prompt: str = None, strength: float = 0.6, guidance_scale: float = 3.5, seed: int = None) -> Image.Image:
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
                    self.progress_callback(i + 1, total_steps, "flux_refinement")
            return draft_image.copy() # 단순 복사
            
        return self.flux_gen.refine_image(
            draft_image=draft_image,
            prompt=prompt,
            negative_prompt=negative_prompt,
            strength=strength,
            guidance_scale=guidance_scale,
            seed=seed,
            progress_callback=self.progress_callback
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
        seed: int = None
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
            import time
            total_steps = 10
            for i in range(total_steps):
                time.sleep(0.5)
                if self.progress_callback:
                    self.progress_callback(i + 1, total_steps, "flux_feature_injection")
            return background.copy()
            
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
            progress_callback=self.progress_callback
        )

    def run_sdxl_text_gen(self, canny_map: Image.Image, prompt: str, negative_prompt: str) -> Image.Image:
        """
        SDXL ControlNet을 로드하여 3D 텍스트 효과를 생성하고 언로드합니다.
        
        Args:
            canny_map (Image.Image): 텍스트의 윤곽선(Canny) 이미지
            prompt (str): 생성할 텍스트 효과에 대한 프롬프트
            negative_prompt (str): 생성 시 제외할 요소들에 대한 부정 프롬프트
            
        Returns:
            Image.Image: 생성된 3D 텍스트 이미지
        """
        if self.dummy_mode:
            logger.info(f"[DUMMY] Generating 3D Text with prompt: {prompt}")
            import time
            total_steps = 8
            for i in range(total_steps):
                time.sleep(0.5)
                if self.progress_callback:
                    self.progress_callback(i + 1, total_steps, "sdxl_text_gen")
            return self._create_dummy_image(1024, 1024, "yellow")
            
        return self.sdxl_gen.generate_text_effect(canny_map, prompt, negative_prompt, self.progress_callback)

    def run_intelligent_composite(
        self,
        background: Image.Image,
        text_asset: Image.Image,
        composition_mode: str = "overlay",
        text_position: str = "top",
        user_prompt: str = None,
        strength: float = 0.4,
        num_inference_steps: int = 28,
        seed: int = None
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
            logger.info(f"[DUMMY] Compositing: mode={composition_mode}, position={text_position}")
            import time
            for i in range(5):
                time.sleep(0.5)
                if self.progress_callback:
                    self.progress_callback(i + 1, 5, "intelligent_composite")
            # 단순 합성 반환
            draft = background.copy().convert("RGBA")
            text_resized = text_asset.resize(draft.size, Image.LANCZOS).convert("RGBA")
            # 알파 채널 추출 (L 모드)
            mask = text_resized.split()[3] if text_resized.mode == "RGBA" else None
            draft.paste(text_resized, (0, 0), mask)
            return draft.convert("RGB")
        
        # 마스크 생성
        mask_mode = composition_mode if composition_mode in ["overlay", "auto"] else "overlay"
        mask = MaskGenerator.create_combined_mask(
            background, 
            text_asset, 
            position=text_position,
            mode=mask_mode
        )
        
        # Composition Engine 실행
        return self.compositor.compose(
            background=background,
            text_asset=text_asset,
            mask=mask,
            mode=composition_mode,
            position=text_position,
            user_prompt=user_prompt,
            strength=strength,
            num_inference_steps=num_inference_steps,
            progress_callback=self.progress_callback
        )
