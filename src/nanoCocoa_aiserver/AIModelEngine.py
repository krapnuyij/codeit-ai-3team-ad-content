import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from PIL import Image
from models.segmentation import SegmentationModel
from models.flux_generator import FluxGenerator
from models.sdxl_text import SDXLTextGenerator
from config import logger


class AIModelEngine:
    """
    AI 모델의 실행을 관리하는 오케스트레이터 클래스입니다.
    각 작업 단계별로 적절한 하위 모델 클래스(Segmentation, Flux, SDXL)를 호출하여 작업을 수행합니다.
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

    def run_flux_refinement(self, draft_image: Image.Image, prompt: str = None, strength: float = 0.6, guidance_scale: float = 3.5, seed: int = None) -> Image.Image:
        """
        Flux Img2Img 모델을 로드하여 초안 이미지를 리터칭(보정)하고 언로드합니다.
        
        Args:
            draft_image (Image.Image): 리터칭할 초안 이미지
            prompt (str, optional): 리터칭을 위한 프롬프트.
            strength (float): 변환 강도 (0.0 ~ 1.0). 기본 0.6.
            guidance_scale (float): 프롬프트 준수 강도. 기본 3.5.
            seed (int, optional): 난수 시드.
            
        Returns:
            Image.Image: 리터칭된 최종 이미지
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
