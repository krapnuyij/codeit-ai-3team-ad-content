"""
이미지 처리 유틸리티
Base64 인코딩/디코딩 및 이미지 검증 기능
"""

import base64
import io
import sys
import logging
from pathlib import Path
from typing import Optional

from PIL import Image
from pathlib import Path

from ..config import MAX_IMAGE_SIZE_MB, SUPPORTED_IMAGE_FORMATS

# MCP stdio 프로토콜은 stdout을 사용하므로 stderr로만 로깅
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
    force=True,
)
logger = logging.getLogger(__name__)


class ImageProcessingError(Exception):
    """이미지 처리 중 발생하는 에러"""

    pass


def image_file_to_base64(file_path: str | Path) -> str:
    """
    이미지 파일을 읽어서 Base64 문자열로 변환

    Args:
        file_path: 이미지 파일 경로

    Returns:
        Base64로 인코딩된 이미지 문자열

    Raises:
        ImageProcessingError: 파일을 읽을 수 없거나 유효하지 않은 이미지인 경우
    """
    try:
        path = Path(file_path)

        # 파일 존재 확인
        if not path.exists():
            raise ImageProcessingError(f"파일을 찾을 수 없습니다: {file_path}")

        # 파일 크기 확인
        file_size_mb = path.stat().st_size / (1024 * 1024)
        if file_size_mb > MAX_IMAGE_SIZE_MB:
            raise ImageProcessingError(
                f"파일 크기가 너무 큽니다: {file_size_mb:.2f}MB "
                f"(최대: {MAX_IMAGE_SIZE_MB}MB)"
            )

        # 이미지 유효성 검증
        try:
            with Image.open(path) as img:
                img_format = img.format
                if img_format not in SUPPORTED_IMAGE_FORMATS:
                    raise ImageProcessingError(
                        f"지원하지 않는 이미지 포맷: {img_format}. "
                        f"지원 포맷: {', '.join(SUPPORTED_IMAGE_FORMATS)}"
                    )
        except Exception as e:
            if isinstance(e, ImageProcessingError):
                raise
            raise ImageProcessingError(f"유효하지 않은 이미지 파일: {e}")

        # Base64로 인코딩
        with open(path, "rb") as image_file:
            encoded = base64.b64encode(image_file.read()).decode("utf-8")

        return encoded

    except ImageProcessingError:
        raise
    except Exception as e:
        raise ImageProcessingError(f"이미지 파일을 읽는 중 에러 발생: {e}")


def base64_to_image_file(
    base64_str: str, output_path: str | Path, overwrite: bool = False
) -> Path:
    """
    Base64 문자열을 이미지 파일로 저장

    Args:
        base64_str: Base64로 인코딩된 이미지 문자열
        output_path: 저장할 파일 경로
        overwrite: 기존 파일 덮어쓰기 여부

    Returns:
        저장된 파일 경로

    Raises:
        ImageProcessingError: Base64 디코딩 실패 또는 파일 저장 실패
    """
    try:
        path = Path(output_path)

        # 기존 파일 확인
        if path.exists() and not overwrite:
            raise ImageProcessingError(
                f"파일이 이미 존재합니다: {output_path}. "
                "overwrite=True로 설정하여 덮어쓸 수 있습니다."
            )

        # 부모 디렉토리 생성
        path.parent.mkdir(parents=True, exist_ok=True)

        # Base64 디코딩
        try:
            image_data = base64.b64decode(base64_str)
        except Exception as e:
            raise ImageProcessingError(f"Base64 디코딩 실패: {e}")

        # 이미지 유효성 검증
        try:
            img = Image.open(io.BytesIO(image_data))
            img.verify()  # 손상된 이미지 검사
        except Exception as e:
            raise ImageProcessingError(f"유효하지 않은 이미지 데이터: {e}")

        # 파일로 저장
        with open(path, "wb") as f:
            f.write(image_data)

        return path

    except ImageProcessingError:
        raise
    except Exception as e:
        raise ImageProcessingError(f"이미지를 저장하는 중 에러 발생: {e}")


def validate_base64_image(base64_str: str) -> tuple[bool, Optional[str]]:
    """
    Base64 문자열이 유효한 이미지인지 검증

    Args:
        base64_str: 검증할 Base64 문자열

    Returns:
        (유효 여부, 에러 메시지) 튜플. 유효하면 에러 메시지는 None
    """
    try:
        # Base64 디코딩
        try:
            image_data = base64.b64decode(base64_str)
        except Exception as e:
            return False, f"Base64 디코딩 실패: {e}"

        # 이미지 검증
        try:
            img = Image.open(io.BytesIO(image_data))
            img.verify()

            # 포맷 확인
            if img.format not in SUPPORTED_IMAGE_FORMATS:
                return False, (
                    f"지원하지 않는 이미지 포맷: {img.format}. "
                    f"지원 포맷: {', '.join(SUPPORTED_IMAGE_FORMATS)}"
                )

            return True, None

        except Exception as e:
            return False, f"유효하지 않은 이미지: {e}"

    except Exception as e:
        return False, f"검증 중 예상치 못한 에러: {e}"


def get_image_info(base64_str: str) -> dict:
    """
    Base64 이미지의 정보 추출

    Args:
        base64_str: Base64 인코딩된 이미지

    Returns:
        이미지 정보 딕셔너리 (width, height, format, mode, size_kb)

    Raises:
        ImageProcessingError: 이미지 정보를 추출할 수 없는 경우
    """
    try:
        image_data = base64.b64decode(base64_str)
        img = Image.open(io.BytesIO(image_data))

        return {
            "width": img.width,
            "height": img.height,
            "format": img.format,
            "mode": img.mode,
            "size_kb": len(image_data) / 1024,
        }

    except Exception as e:
        raise ImageProcessingError(f"이미지 정보를 추출할 수 없습니다: {e}")


def resize_image_if_needed(base64_str: str, max_dimension: int = 2048) -> str:
    """
    이미지가 너무 크면 비율을 유지하며 리사이즈

    Args:
        base64_str: Base64 인코딩된 원본 이미지
        max_dimension: 최대 가로/세로 크기 (픽셀)

    Returns:
        리사이즈된 이미지의 Base64 문자열 (리사이즈가 필요없으면 원본 반환)

    Raises:
        ImageProcessingError: 리사이즈 실패
    """
    try:
        image_data = base64.b64decode(base64_str)
        img = Image.open(io.BytesIO(image_data))

        # 리사이즈 필요 여부 확인
        if img.width <= max_dimension and img.height <= max_dimension:
            return base64_str  # 리사이즈 불필요

        # 비율 유지하며 리사이즈
        img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

        # Base64로 재인코딩
        buffer = io.BytesIO()
        img.save(buffer, format=img.format)
        resized_data = buffer.getvalue()

        return base64.b64encode(resized_data).decode("utf-8")

    except Exception as e:
        raise ImageProcessingError(f"이미지 리사이즈 실패: {e}")
