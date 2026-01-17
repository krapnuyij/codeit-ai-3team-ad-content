"""
공간 분석 모듈: Qwen2-VL을 사용한 최적의 객체 배치 위치 탐지
Spatial Analysis Module: Detect optimal object placement using Qwen2-VL
"""

import torch
from PIL import Image, ImageDraw
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info
from typing import Union, Dict, List, Tuple
import re
import logging

# Try to import helper_dev_utils, fallback to standard logging if not available
try:
    from helper_dev_utils import get_auto_logger
    logger = get_auto_logger()
except ImportError:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

from .utils import flush_gpu


class SpatialAnalyzer:
    """
    Qwen2-VL을 사용하여 배경 이미지에서 최적의 객체 배치 위치를 찾는 클래스

    이 클래스는 Vision-Language 모델을 사용하여 표면을 감지하고,
    바운딩 박스를 결정하며, 객체 합성을 위한 마스크를 생성합니다.

    Attributes:
        model_name (str): 사용할 HuggingFace 모델 이름
        device (str): 모델을 실행할 디바이스
        model: Qwen2-VL 모델 인스턴스
        processor: 이미지/텍스트 전처리 프로세서
    """

    def __init__(
        self, model_name: str = "Qwen/Qwen2-VL-7B-Instruct", device: str = None
    ):
        """
        SpatialAnalyzer 초기화

        Args:
            model_name: HuggingFace 모델 식별자 (기본값: Qwen2-VL-7B-Instruct)
            device: 모델 실행 디바이스 ('cuda' 또는 'cpu', 기본값: 자동 감지)
        """
        self.model_name = model_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.processor = None

        print(f"🔧 SpatialAnalyzer 초기화: {model_name}")

    def _load_model(self):
        """Qwen2-VL 모델과 프로세서를 로드합니다."""
        if self.model is None:
            print(f"  Qwen2-VL 모델을 {self.device}에 로드 중...")

            # Vision-Language 모델 로드
            self.model = Qwen2VLForConditionalGeneration.from_pretrained(
                self.model_name,
                torch_dtype=torch.bfloat16,  # 메모리 절약
                device_map="auto",  # 자동 디바이스 배치
            )

            # 이미지와 텍스트 전처리를 위한 프로세서 로드
            self.processor = AutoProcessor.from_pretrained(self.model_name)

            print(f"  ✓ Qwen2-VL 모델 로드 완료")

    def _unload_model(self):
        """VRAM 확보를 위해 모델을 언로드합니다."""
        if self.model is not None:
            print("  Qwen2-VL 모델 언로드 중...")
            self.model.to("cpu")  # GPU에서 CPU로 이동
            del self.model
            del self.processor
            self.model = None
            self.processor = None
            flush_gpu()  # GPU 캐시 정리

    def detect_surface(
        self,
        image: Union[Image.Image, str],
        query: str = "Find the flat surface where I can place an object. Return the bounding box coordinates.",
    ) -> Dict[str, any]:
        """
        객체 배치를 위한 최적의 표면을 탐지합니다.

        Vision-Language 모델에 이미지와 질문을 제공하여
        객체를 놓을 수 있는 최적의 위치를 찾습니다.

        Args:
            image: PIL Image 객체 또는 이미지 경로
            query: VL 모델에 물어볼 질문 (위치 탐지 요청)

        Returns:
            다음을 포함하는 딕셔너리:
                - 'bbox': [x1, y1, x2, y2] 정규화된 좌표 (0-1000 범위)
                - 'text': 모델의 전체 응답 텍스트
                - 'image_size': 입력 이미지의 (width, height)

        Example:
            >>> analyzer = SpatialAnalyzer()
            >>> result = analyzer.detect_surface(
            ...     bg_image,
            ...     "맥주병을 놓을 테이블 중앙을 찾아주세요"
            ... )
            >>> bbox = result['bbox']  # [x1, y1, x2, y2]
        """
        try:
            # 모델 로드 (필요시)
            self._load_model()

            # 경로가 제공된 경우 이미지 로드
            if isinstance(image, str):
                from .utils import load_image

                image = load_image(image)

            image_size = image.size  # (width, height)

            print(f"  이미지 분석 중 ({image_size[0]}x{image_size[1]})...")
            print(f"  질문: {query}")

            # 모델을 위한 메시지 준비 (멀티모달 입력)
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "image": image,  # 이미지 입력
                        },
                        {"type": "text", "text": query},  # 텍스트 질문
                    ],
                }
            ]

            # 입력 전처리
            text = self.processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            image_inputs, video_inputs = process_vision_info(messages)

            inputs = self.processor(
                text=[text],
                images=image_inputs,
                videos=video_inputs,
                padding=True,
                return_tensors="pt",
            )
            inputs = inputs.to(self.device)

            # 응답 생성 (추론)
            with torch.no_grad():  # 그래디언트 계산 비활성화
                generated_ids = self.model.generate(
                    **inputs, max_new_tokens=256  # 최대 응답 길이
                )

            # 입력 토큰 제거 (생성된 부분만 추출)
            generated_ids_trimmed = [
                out_ids[len(in_ids) :]
                for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
            ]

            # 응답 디코딩 (토큰 -> 텍스트)
            output_text = self.processor.batch_decode(
                generated_ids_trimmed,
                skip_special_tokens=True,
                clean_up_tokenization_spaces=False,
            )[0]

            print(f"  모델 응답: {output_text[:100]}...")

            # 응답에서 바운딩 박스 파싱
            bbox = self._parse_bbox(output_text)

            result = {"bbox": bbox, "text": output_text, "image_size": image_size}

            print(f"  ✓ 표면 탐지 완료: {bbox}")

            return result

        finally:
            # VRAM 확보를 위해 항상 모델 언로드
            self._unload_model()

    def _parse_bbox(self, text: str) -> List[int]:
        """
        모델 출력에서 바운딩 박스 좌표를 파싱합니다.

        Qwen-VL은 일반적으로 다음 형식으로 bbox를 반환합니다:
        - 형식 1: <|box_start|>(x1,y1),(x2,y2)<|box_end|>
        - 형식 2: 텍스트 내의 숫자 나열

        Returns:
            정규화된 좌표의 [x1, y1, x2, y2] (0-1000 범위)
        """
        # 패턴 1: <|box_start|>(x1,y1),(x2,y2)<|box_end|> 형태 찾기
        box_pattern = r"<\|box_start\|\>\((\d+),(\d+)\),\((\d+),(\d+)\)<\|box_end\|\>"
        match = re.search(box_pattern, text)

        if match:
            return [
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3)),
                int(match.group(4)),
            ]

        # 패턴 2: 콤마로 구분된 4개의 숫자 찾기
        numbers = re.findall(r"\b\d+\b", text)
        if len(numbers) >= 4:
            # 처음 4개 숫자를 bbox로 사용
            return [int(numbers[0]), int(numbers[1]), int(numbers[2]), int(numbers[3])]

        # 기본값: 파싱 실패 시 중앙 영역 사용
        print("  ⚠ bbox 파싱 실패, 중앙 영역 사용")
        return [400, 400, 600, 600]  # 중앙 영역 (정규화 0-1000)

    def create_mask(
        self,
        image_size: Tuple[int, int],
        bbox: List[int],
        mask_color: int = 255,
        background_color: int = 0,
    ) -> Image.Image:
        """
        바운딩 박스 좌표로부터 이진 마스크를 생성합니다.

        Args:
            image_size: 대상 이미지의 (width, height)
            bbox: 정규화된 좌표의 [x1, y1, x2, y2] (0-1000 범위)
            mask_color: 마스크 영역의 색상 (기본값: 255 = 흰색)
            background_color: 배경 색상 (기본값: 0 = 검정)

        Returns:
            이진 마스크 이미지 ('L' 모드의 PIL.Image)

        Example:
            >>> mask = analyzer.create_mask((1024, 1024), [400, 400, 600, 600])
        """
        width, height = image_size

        # 정규화된 좌표(0-1000)를 픽셀 좌표로 변환
        x1 = int(bbox[0] * width / 1000)
        y1 = int(bbox[1] * height / 1000)
        x2 = int(bbox[2] * width / 1000)
        y2 = int(bbox[3] * height / 1000)

        # 검은 배경 생성
        mask = Image.new("L", image_size, background_color)
        draw = ImageDraw.Draw(mask)

        # 마스크 영역에 흰색 사각형 그리기
        draw.rectangle([x1, y1, x2, y2], fill=mask_color)

        print(
            f"  ✓ 마스크 생성 완료: {image_size[0]}x{image_size[1]}, "
            f"영역: ({x1},{y1})-({x2},{y2})"
        )

        return mask

    def visualize_bbox(
        self, image: Image.Image, bbox: List[int], color: str = "red", width: int = 3
    ) -> Image.Image:
        """
        이미지에 바운딩 박스를 시각화합니다.

        Args:
            image: 입력 PIL Image
            bbox: 정규화된 좌표의 [x1, y1, x2, y2] (0-1000 범위)
            color: 바운딩 박스 색상
            width: 선 두께

        Returns:
            바운딩 박스가 그려진 이미지

        Example:
            >>> bbox_img = analyzer.visualize_bbox(bg_image, [400, 400, 600, 600])
        """
        img_copy = image.copy()
        draw = ImageDraw.Draw(img_copy)

        # 정규화된 좌표를 픽셀 좌표로 변환
        img_width, img_height = image.size
        x1 = int(bbox[0] * img_width / 1000)
        y1 = int(bbox[1] * img_height / 1000)
        x2 = int(bbox[2] * img_width / 1000)
        y2 = int(bbox[3] * img_height / 1000)

        # 사각형 그리기
        draw.rectangle([x1, y1, x2, y2], outline=color, width=width)

        return img_copy

    def __del__(self):
        """객체 소멸 시 정리 작업"""
        self._unload_model()
