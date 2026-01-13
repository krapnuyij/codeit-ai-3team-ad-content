"""
이미지 유틸리티 단위 테스트
"""

import pytest
import base64
import io
from pathlib import Path
from PIL import Image

from nanoCocoa_mcpserver.utils.image_utils import (
    image_file_to_base64,
    base64_to_image_file,
    validate_base64_image,
    get_image_info,
    resize_image_if_needed,
    ImageProcessingError,
)


@pytest.fixture
def temp_image_path(tmp_path):
    """테스트용 임시 이미지 생성"""
    img_path = tmp_path / "test_image.png"

    # 100x100 빨간색 이미지 생성
    img = Image.new("RGB", (100, 100), color="red")
    img.save(img_path, "PNG")

    return img_path


@pytest.fixture
def sample_base64_image():
    """테스트용 Base64 이미지 생성"""
    img = Image.new("RGB", (50, 50), color="blue")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    img_bytes = buffer.getvalue()
    return base64.b64encode(img_bytes).decode("utf-8")


def test_image_file_to_base64(temp_image_path):
    """이미지 파일을 Base64로 변환 테스트"""
    result = image_file_to_base64(temp_image_path)

    # Base64 문자열이어야 함
    assert isinstance(result, str)
    assert len(result) > 0

    # Base64 디코딩 가능해야 함
    decoded = base64.b64decode(result)
    assert len(decoded) > 0

    # 실제 이미지로 복원 가능해야 함
    img = Image.open(io.BytesIO(decoded))
    assert img.size == (100, 100)
    assert img.format == "PNG"


def test_image_file_to_base64_file_not_found():
    """존재하지 않는 파일 처리 테스트"""
    with pytest.raises(ImageProcessingError) as exc_info:
        image_file_to_base64("non_existent_file.png")

    assert "파일을 찾을 수 없습니다" in str(exc_info.value)


def test_image_file_to_base64_invalid_image(tmp_path):
    """잘못된 이미지 파일 처리 테스트"""
    invalid_file = tmp_path / "invalid.png"
    invalid_file.write_text("This is not an image")

    with pytest.raises(ImageProcessingError) as exc_info:
        image_file_to_base64(invalid_file)

    assert "유효하지 않은 이미지 파일" in str(exc_info.value)


def test_base64_to_image_file(sample_base64_image, tmp_path):
    """Base64를 이미지 파일로 저장 테스트"""
    output_path = tmp_path / "output.png"

    result = base64_to_image_file(sample_base64_image, output_path)

    # 파일이 생성되었는지 확인
    assert result.exists()
    assert result == output_path

    # 저장된 이미지 확인
    img = Image.open(result)
    assert img.size == (50, 50)
    assert img.format == "PNG"


def test_base64_to_image_file_overwrite(sample_base64_image, tmp_path):
    """파일 덮어쓰기 테스트"""
    output_path = tmp_path / "output.png"

    # 첫 번째 저장
    base64_to_image_file(sample_base64_image, output_path)

    # 덮어쓰기 없이 다시 저장 시도 -> 에러
    with pytest.raises(ImageProcessingError) as exc_info:
        base64_to_image_file(sample_base64_image, output_path, overwrite=False)

    assert "파일이 이미 존재합니다" in str(exc_info.value)

    # overwrite=True로 저장 -> 성공
    result = base64_to_image_file(sample_base64_image, output_path, overwrite=True)
    assert result.exists()


def test_base64_to_image_file_invalid_base64(tmp_path):
    """잘못된 Base64 처리 테스트"""
    output_path = tmp_path / "output.png"

    with pytest.raises(ImageProcessingError) as exc_info:
        base64_to_image_file("invalid_base64!!!", output_path)

    assert "Base64 디코딩 실패" in str(exc_info.value)


def test_base64_to_image_file_creates_parent_dir(sample_base64_image, tmp_path):
    """부모 디렉토리 자동 생성 테스트"""
    output_path = tmp_path / "nested" / "dir" / "output.png"

    # 부모 디렉토리가 없어도 생성되어야 함
    result = base64_to_image_file(sample_base64_image, output_path)

    assert result.exists()
    assert result.parent.exists()


def test_validate_base64_image_valid(sample_base64_image):
    """유효한 Base64 이미지 검증 테스트"""
    is_valid, error_msg = validate_base64_image(sample_base64_image)

    assert is_valid is True
    assert error_msg is None


def test_validate_base64_image_invalid_base64():
    """잘못된 Base64 검증 테스트"""
    is_valid, error_msg = validate_base64_image("not_valid_base64!!!")

    assert is_valid is False
    assert "Base64 디코딩 실패" in error_msg


def test_validate_base64_image_not_image():
    """이미지가 아닌 Base64 검증 테스트"""
    text_b64 = base64.b64encode(b"Just some text").decode("utf-8")

    is_valid, error_msg = validate_base64_image(text_b64)

    assert is_valid is False
    assert "유효하지 않은 이미지" in error_msg


def test_get_image_info(sample_base64_image):
    """이미지 정보 추출 테스트"""
    info = get_image_info(sample_base64_image)

    assert isinstance(info, dict)
    assert info["width"] == 50
    assert info["height"] == 50
    assert info["format"] == "PNG"
    assert info["mode"] == "RGB"
    assert info["size_kb"] > 0


def test_get_image_info_invalid():
    """잘못된 이미지 정보 추출 테스트"""
    with pytest.raises(ImageProcessingError) as exc_info:
        get_image_info("invalid_base64")

    assert "이미지 정보를 추출할 수 없습니다" in str(exc_info.value)


def test_resize_image_if_needed_no_resize():
    """리사이즈 불필요한 경우 테스트"""
    # 작은 이미지 생성 (100x100)
    img = Image.new("RGB", (100, 100), color="green")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    original_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    # 2048 이하이므로 리사이즈 안 됨
    result = resize_image_if_needed(original_b64, max_dimension=2048)

    # 원본과 동일해야 함
    assert result == original_b64


def test_resize_image_if_needed_with_resize():
    """리사이즈 필요한 경우 테스트"""
    # 큰 이미지 생성 (3000x2000)
    img = Image.new("RGB", (3000, 2000), color="yellow")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    original_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    # 1000으로 리사이즈
    result = resize_image_if_needed(original_b64, max_dimension=1000)

    # 다른 Base64여야 함
    assert result != original_b64

    # 리사이즈된 이미지 확인
    decoded = base64.b64decode(result)
    resized_img = Image.open(io.BytesIO(decoded))

    # 최대 치수가 1000 이하여야 함
    assert max(resized_img.size) <= 1000

    # 비율은 유지되어야 함 (3000:2000 = 3:2)
    width, height = resized_img.size
    ratio = width / height
    assert abs(ratio - 1.5) < 0.01  # 3:2 = 1.5


def test_resize_image_preserves_aspect_ratio():
    """리사이즈 시 비율 유지 테스트"""
    # 800x400 이미지 (2:1 비율)
    img = Image.new("RGB", (800, 400), color="purple")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    original_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    # 500으로 리사이즈
    result = resize_image_if_needed(original_b64, max_dimension=500)

    # 리사이즈된 이미지 확인
    decoded = base64.b64decode(result)
    resized_img = Image.open(io.BytesIO(decoded))

    # 500x250이어야 함 (2:1 비율 유지)
    assert resized_img.size == (500, 250)


def test_roundtrip_conversion(temp_image_path, tmp_path):
    """파일 -> Base64 -> 파일 왕복 변환 테스트"""
    # 파일을 Base64로 변환
    b64 = image_file_to_base64(temp_image_path)

    # Base64를 다시 파일로 저장
    output_path = tmp_path / "roundtrip.png"
    base64_to_image_file(b64, output_path)

    # 원본과 결과 비교
    original_img = Image.open(temp_image_path)
    result_img = Image.open(output_path)

    assert original_img.size == result_img.size
    assert original_img.format == result_img.format
    assert original_img.mode == result_img.mode


def test_supported_formats(tmp_path):
    """지원하는 이미지 포맷 테스트"""
    formats = ["PNG", "JPEG"]

    for fmt in formats:
        # 이미지 생성
        img_path = tmp_path / f"test.{fmt.lower()}"
        img = Image.new("RGB", (100, 100), color="red")
        img.save(img_path, format=fmt)

        # Base64 변환 성공해야 함
        b64 = image_file_to_base64(img_path)
        assert len(b64) > 0

        # 검증 성공해야 함
        is_valid, _ = validate_base64_image(b64)
        assert is_valid


def test_unsupported_format(tmp_path):
    """지원하지 않는 포맷 처리 테스트"""
    # BMP 이미지 생성 (지원 목록에 없음)
    img_path = tmp_path / "test.bmp"
    img = Image.new("RGB", (100, 100), color="red")
    img.save(img_path, format="BMP")

    # Base64 변환 시 에러 발생
    with pytest.raises(ImageProcessingError) as exc_info:
        image_file_to_base64(img_path)

    assert "지원하지 않는 이미지 포맷" in str(exc_info.value)
