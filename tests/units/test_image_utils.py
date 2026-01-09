"""
이미지 유틸리티 함수 단위 테스트.

image_utils 모듈의 Base64 변환 및 Canny Edge 처리 기능을 검증합니다.
"""

import pytest
from PIL import Image
import base64
import io

import sys
from pathlib import Path

# src/nanoCocoa_aiserver를 path에 추가
sys.path.insert(0, str(Path(__file__).parents[2] / "src" / "nanoCocoa_aiserver"))

from utils.images import pil_to_base64, base64_to_pil, pil_canny_edge


class TestPilToBase64:
    """pil_to_base64 함수 테스트"""

    def test_converts_valid_image(self):
        """정상 이미지를 Base64로 변환"""
        img = Image.new("RGB", (100, 100), color="red")
        result = pil_to_base64(img)

        assert isinstance(result, str)
        assert len(result) > 0
        # Base64 문자열은 4의 배수
        assert len(result) % 4 == 0

    def test_raises_on_none_image(self):
        """None 입력 시 ValueError 발생"""
        with pytest.raises(ValueError, match="Image cannot be None"):
            pil_to_base64(None)

    def test_preserves_image_format(self):
        """PNG와 JPEG 형식 모두 지원"""
        img = Image.new("RGB", (100, 100), color="blue")

        png_result = pil_to_base64(img, format="PNG")
        jpeg_result = pil_to_base64(img, format="JPEG")

        assert png_result != jpeg_result
        assert len(png_result) > 0
        assert len(jpeg_result) > 0


class TestBase64ToPil:
    """base64_to_pil 함수 테스트"""

    def test_converts_valid_base64(self):
        """정상 Base64 문자열을 PIL 이미지로 변환"""
        img = Image.new("RGB", (100, 100), color="green")
        b64_str = pil_to_base64(img)

        result = base64_to_pil(b64_str)

        assert isinstance(result, Image.Image)
        assert result.mode == "RGB"
        assert result.size == (100, 100)

    def test_raises_on_empty_string(self):
        """빈 문자열 입력 시 ValueError 발생"""
        with pytest.raises(ValueError, match="Base64 string cannot be empty"):
            base64_to_pil("")

    def test_raises_on_invalid_base64(self):
        """잘못된 Base64 문자열 입력 시 ValueError 발생"""
        with pytest.raises(
            ValueError, match="(Failed to decode Base64 image|Invalid Base64 encoding)"
        ):
            base64_to_pil("not-a-valid-base64-string!!!")

    def test_roundtrip_conversion(self):
        """PIL → Base64 → PIL 라운드트립 변환"""
        original = Image.new("RGB", (200, 200), color="yellow")
        b64 = pil_to_base64(original)
        restored = base64_to_pil(b64)

        assert original.size == restored.size
        assert original.mode == restored.mode


class TestPilCannyEdge:
    """pil_canny_edge 함수 테스트"""

    def test_produces_edge_image(self):
        """정상 이미지에서 엣지 추출"""
        img = Image.new("RGB", (100, 100), color="white")
        result = pil_canny_edge(img)

        assert isinstance(result, Image.Image)
        assert result.mode == "RGB"
        assert result.size == img.size

    def test_raises_on_none_image(self):
        """None 입력 시 ValueError 발생"""
        with pytest.raises(ValueError, match="Image cannot be None"):
            pil_canny_edge(None)

    def test_custom_threshold(self):
        """사용자 지정 임계값 적용"""
        img = Image.new("RGB", (100, 100), color="gray")

        result_low = pil_canny_edge(img, threshold=10)
        result_high = pil_canny_edge(img, threshold=100)

        assert isinstance(result_low, Image.Image)
        assert isinstance(result_high, Image.Image)
        # 임계값이 다르면 결과도 다를 수 있음 (단, 단색 이미지는 동일할 수 있음)
        assert result_low.mode == "RGB"
        assert result_high.mode == "RGB"
