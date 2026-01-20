"""
객체 매팅 모듈: BiRefNet을 사용한 배경 제거
Object Matting Module: Background Removal using BiRefNet
"""

import torch
from PIL import Image
from transformers import AutoModelForImageSegmentation
from torchvision import transforms
from typing import Union
from pathlib import Path
import logging

# Try to import helper_dev_utils, fallback to standard logging if not available
try:
    from helper_dev_utils import get_auto_logger

    logger = get_auto_logger()
except ImportError:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

from .utils import flush_gpu, load_image


class ObjectMatting:
    """
    BiRefNet을 사용하여 제품 이미지에서 배경을 제거하는 클래스

    이 클래스는 깨끗한 RGBA 이미지를 생성하기 위해 배경을 제거합니다.
    이는 합성 단계에서 IP-Adapter 오염을 방지하는 데 필수적입니다.

    Attributes:
        model_name (str): 사용할 HuggingFace 모델 이름
        device (str): 모델을 실행할 디바이스 ('cuda' 또는 'cpu')
        model: BiRefNet 모델 인스턴스 (필요할 때만 로드)
        transform: 이미지 전처리 변환 파이프라인
    """

    def __init__(self, model_name: str = "ZhengPeng7/BiRefNet", device: str = None):
        """
        ObjectMatting 모델 초기화

        Args:
            model_name: HuggingFace 모델 식별자 (기본값: BiRefNet)
            device: 모델 실행 디바이스 ('cuda' 또는 'cpu', 기본값: 자동 감지)
        """
        self.model_name = model_name
        # CUDA 사용 가능하면 GPU, 아니면 CPU 사용
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.transform = None

        print(f"🔧 ObjectMatting 초기화: {model_name}")

    def _load_model(self):
        """BiRefNet 모델을 디바이스에 로드합니다."""
        if self.model is None:
            print(f"  BiRefNet 모델을 {self.device}에 로드 중...")
            # HuggingFace에서 사전학습된 모델 다운로드 및 로드
            self.model = AutoModelForImageSegmentation.from_pretrained(
                self.model_name, trust_remote_code=True  # 커스텀 코드 실행 허용
            )
            self.model.to(self.device)  # GPU 또는 CPU로 이동
            self.model.eval()  # 평가 모드 (학습 안 함)

            # 이미지 전처리 파이프라인 정의
            # 1024x1024로 리사이즈 -> 텐서 변환 -> ImageNet 정규화
            self.transform = transforms.Compose(
                [
                    transforms.Resize((1024, 1024)),  # 모델 입력 크기로 조정
                    transforms.ToTensor(),  # PIL -> Tensor 변환
                    transforms.Normalize(
                        [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]
                    ),  # ImageNet 정규화
                ]
            )

            print(f"  ✓ BiRefNet 모델 로드 완료")

    def _unload_model(self):
        """GPU VRAM을 확보하기 위해 모델을 언로드합니다."""
        if self.model is not None:
            print("  BiRefNet 모델 언로드 중...")
            self.model.to("cpu")  # GPU에서 CPU로 이동
            del self.model  # 모델 삭제
            self.model = None
            self.transform = None
            flush_gpu()  # GPU 캐시 정리

    def remove_background(
        self, image_path: Union[str, Path], return_rgba: bool = True
    ) -> Image.Image:
        """
        입력 이미지에서 배경을 제거합니다.

        Args:
            image_path: 입력 이미지 경로
            return_rgba: True이면 RGBA 이미지 반환, False이면 검은 배경의 RGB 반환

        Returns:
            배경이 제거된 PIL 이미지 (RGBA 또는 RGB)

        Example:
            >>> matting = ObjectMatting()
            >>> clean_image = matting.remove_background("product.png")
            >>> clean_image.save("product_no_bg.png")
        """
        try:
            # 모델 로드 (필요시)
            self._load_model()

            # 원본 이미지 로드 및 전처리
            original_image = load_image(image_path)
            original_size = original_image.size

            # 처리를 위해 RGB로 변환
            if original_image.mode != "RGB":
                product_image = original_image.convert("RGB")
            else:
                product_image = original_image

            # 이미지 전처리 (1024x1024로 리사이즈 및 정규화)
            input_tensor = self.transform(product_image).unsqueeze(0).to(self.device)

            # 추론 실행 (배경 마스크 생성)
            print("  배경 제거 실행 중...")
            with torch.no_grad():  # 그래디언트 계산 비활성화 (메모리 절약)
                predictions = self.model(input_tensor)[-1]  # 모델 출력
                pred_mask = (
                    predictions.sigmoid().cpu()
                )  # 시그모이드 활성화 후 CPU로 이동

            # 마스크 후처리
            pred_mask = pred_mask.squeeze().numpy()  # Tensor -> NumPy 배열
            mask_image = Image.fromarray(
                (pred_mask * 255).astype("uint8")
            )  # 0-255 범위로 변환
            mask_image = mask_image.resize(
                original_size, Image.LANCZOS
            )  # 원본 크기로 복원

            # 결과 이미지 생성
            if return_rgba:
                # RGBA 이미지 생성 (투명 배경)
                result = product_image.convert("RGBA")
                result.putalpha(mask_image)  # 알파 채널로 마스크 적용
                print("  ✓ 배경 제거 완료 (RGBA)")
            else:
                # 검은 배경의 RGB 이미지 생성
                result = Image.new("RGB", original_size, (0, 0, 0))
                result.paste(product_image, mask=mask_image)
                print("  ✓ 배경 제거 완료 (RGB)")

            return result

        finally:
            # VRAM 확보를 위해 항상 모델 언로드
            self._unload_model()

    def __del__(self):
        """객체 소멸 시 정리 작업"""
        self._unload_model()
