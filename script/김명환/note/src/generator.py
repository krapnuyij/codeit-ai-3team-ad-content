"""
배경 생성 모듈: FLUX.1-dev를 사용하여 깨끗한 배경 이미지 생성
Background Generation Module: Create clean backgrounds using FLUX.1-dev
"""

import torch
from PIL import Image
from diffusers import FluxPipeline, PipelineQuantizationConfig, BitsAndBytesConfig
from typing import Optional
import logging

# Try to import helper_dev_utils, fallback to standard logging if not available
try:
    from helper_dev_utils import get_auto_logger
    logger = get_auto_logger()
except ImportError:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

from .utils import flush_gpu


class BackgroundGenerator:
    """
    FLUX.1-dev를 사용하여 객체가 없는 깨끗한 배경 이미지를 생성하는 클래스

    이 클래스는 나중에 객체 합성에 사용될 분위기 있는 배경을 생성합니다.
    프롬프트는 특정 객체보다는 분위기, 조명, 환경에 초점을 맞춰야 합니다.

    Attributes:
        model_name (str): 사용할 HuggingFace 모델 이름
        device (str): 모델을 실행할 디바이스
        torch_dtype: 모델 가중치의 데이터 타입 (FLUX는 bfloat16 권장)
        pipe: FLUX 파이프라인 인스턴스
    """

    def __init__(
        self,
        model_name: str = "black-forest-labs/FLUX.1-dev",
        device: str = None,
        torch_dtype: torch.dtype = torch.bfloat16,
    ):
        """
        BackgroundGenerator 초기화

        Args:
            model_name: HuggingFace 모델 식별자 (기본값: FLUX.1-dev)
            device: 모델 실행 디바이스 ('cuda' 또는 'cpu', 기본값: 자동 감지)
            torch_dtype: 모델 가중치 데이터 타입 (FLUX는 bfloat16 권장)
        """
        self.model_name = model_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.torch_dtype = torch_dtype
        self.pipe = None  # 지연 로딩 (필요할 때만 로드)

        print(f"🔧 BackgroundGenerator 초기화: {model_name}")

    def _load_model(self):
        """FLUX.1-dev 파이프라인을 디바이스에 로드합니다."""
        if self.pipe is None:
            print(f"  FLUX.1-dev 파이프라인을 {self.device}에 로드 중...")

            # L4 GPU를 위한 8bit 양자화 설정
            # BitsAndBytesConfig를 PipelineQuantizationConfig로 래핑
            bnb_config = BitsAndBytesConfig(
                load_in_8bit=True,
            )

            quantization_config = PipelineQuantizationConfig(
                quant_backend="bitsandbytes_8bit",
                quant_kwargs={
                    "load_in_8bit": True,
                },
            )

            # HuggingFace에서 사전학습된 FLUX 모델 다운로드 및 로드
            # 양자화 처리 시 자동으로 GPU로 이동
            self.pipe = FluxPipeline.from_pretrained(
                self.model_name,
                torch_dtype=self.torch_dtype,  # bfloat16으로 메모리 절약
                quantization_config=quantization_config,  # 8bit 양자화
            )

            # 메모리 최적화 옵션 활성화
            if self.device == "cuda":
                # CPU 오프로딩: 사용하지 않는 컴포넌트를 자동으로 CPU로 이동
                self.pipe.enable_model_cpu_offload()
                # 참고: enable_attention_slicing()은 VRAM 사용량을 줄이지만
                # 생성 속도가 느려질 수 있습니다
                # self.pipe.enable_attention_slicing()

            print(f"  ✓ FLUX.1-dev 파이프라인 로드 완료 (8bit 양자화)")

    def _unload_model(self):
        """VRAM 확보를 위해 파이프라인을 언로드합니다."""
        if self.pipe is not None:
            print("  FLUX.1-dev 파이프라인 언로드 중...")
            # 모든 컴포넌트를 CPU로 이동
            if hasattr(self.pipe, "to"):
                self.pipe.to("cpu")
            del self.pipe
            self.pipe = None
            flush_gpu()  # GPU 캐시 정리

    def generate_background(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 1024,
        num_inference_steps: int = 28,
        guidance_scale: float = 3.5,
        seed: Optional[int] = None,
    ) -> Image.Image:
        """
        텍스트 프롬프트를 기반으로 배경 이미지를 생성합니다.

        Args:
            prompt: 원하는 배경의 텍스트 설명
                   (분위기, 조명, 환경에 초점을 맞추고 객체 묘사는 최소화)
            width: 출력 이미지 너비 (기본값: 1024)
            height: 출력 이미지 높이 (기본값: 1024)
            num_inference_steps: 디노이징 스텝 수 (기본값: 28, 높을수록 품질↑ 속도↓)
            guidance_scale: CFG 스케일 (기본값: 3.5, 높을수록 프롬프트 충실도↑)
            seed: 재현 가능성을 위한 랜덤 시드 (None이면 랜덤)

        Returns:
            생성된 배경 이미지 (PIL.Image)

        Example:
            >>> generator = BackgroundGenerator()
            >>> bg = generator.generate_background(
            ...     "아늑한 바의 나무 테이블, 따뜻한 조명, "
            ...     "중앙에 빈 공간, 얕은 피사계 심도",
            ...     seed=42
            ... )
        """
        try:
            # 모델 로드 (필요시)
            self._load_model()

            # 재현성을 위한 시드 설정
            if seed is not None:
                generator = torch.Generator(device=self.device).manual_seed(seed)
            else:
                generator = None

            print(f"  배경 생성 중 ({width}x{height})...")
            print(f"  프롬프트: {prompt[:80]}...")

            # 이미지 생성
            output = self.pipe(
                prompt=prompt,
                width=width,
                height=height,
                num_inference_steps=num_inference_steps,  # 디노이징 반복 횟수
                guidance_scale=guidance_scale,  # 프롬프트 가이던스 강도
                generator=generator,  # 시드 제어
            )

            image = output.images[0]
            print(f"  ✓ 배경 생성 완료")

            return image

        finally:
            # VRAM 확보를 위해 항상 모델 언로드
            self._unload_model()

    def __del__(self):
        """객체 소멸 시 정리 작업"""
        self._unload_model()
