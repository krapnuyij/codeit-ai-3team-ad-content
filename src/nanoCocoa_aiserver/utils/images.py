"""
이미지 변환 및 처리 유틸리티 모듈.

Base64 <-> PIL 변환, Canny Edge 처리 등 이미지 관련 헬퍼 함수를 제공합니다.
"""

import base64
from io import BytesIO
from typing import Optional

from PIL import Image, ImageFilter


def pil_to_base64(image: Image.Image, format: str = "PNG") -> str:
    """
    PIL 이미지를 Base64 문자열로 변환합니다.
    
    Args:
        image (Image.Image): 변환할 PIL 이미지
        format (str): 이미지 저장 형식 (기본값: "PNG")
        
    Returns:
        str: Base64로 인코딩된 문자열
        
    Raises:
        ValueError: image가 None이거나 유효하지 않은 경우
    """
    if image is None:
        raise ValueError("Image cannot be None")
    
    buffered = BytesIO()
    image.save(buffered, format=format)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def base64_to_pil(b64_str: str) -> Image.Image:
    """
    Base64 문자열을 PIL 이미지로 변환합니다.
    
    Args:
        b64_str (str): Base64로 인코딩된 이미지 문자열
        
    Returns:
        Image.Image: RGB 모드로 변환된 PIL 이미지
        
    Raises:
        ValueError: 유효하지 않은 Base64 문자열인 경우
    """
    if not b64_str:
        raise ValueError("Base64 string cannot be empty")
    
    try:
        return Image.open(BytesIO(base64.b64decode(b64_str))).convert("RGB")
    except Exception as e:
        raise ValueError(f"Failed to decode Base64 image: {e}")


def pil_canny_edge(image: Image.Image, threshold: int = 30) -> Image.Image:
    """
    PIL 이미지를 입력받아 Canny Edge 처리된 이미지를 반환합니다.
    
    Args:
        image (Image.Image): 입력 이미지
        threshold (int): 엣지 검출 임계값 (기본값: 30)
        
    Returns:
        Image.Image: 엣지 처리가 완료된 RGB 이미지
        
    Raises:
        ValueError: image가 None이거나 유효하지 않은 경우
    """
    if image is None:
        raise ValueError("Image cannot be None")
    
    gray = image.convert("L")
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edges = edges.point(lambda x: 255 if x > threshold else 0)
    return edges.convert("RGB")


def reposition_text_asset(
    image: Image.Image, 
    target_position: str, 
    margin: int = 100
) -> Image.Image:
    """
    텍스트 에셋(투명 배경)의 내용물을 감지하여 box를 계산하고,
    지정된 위치(top/center/bottom)로 이동시킵니다.
    
    Args:
        image: 텍스트 에셋 이미지 (RGBA)
        target_position: 'top', 'center', 'bottom'
        margin: 상/하단 여백 (px)
        
    Returns:
        Image.Image: 위치가 조정된 이미지
    """
    if image.mode != "RGBA":
        image = image.convert("RGBA")
        
    # 1. 텍스트 영역 Bounding Box 찾기
    # 알파 채널에서 0이 아닌 영역 찾기
    alpha = image.split()[-1]
    bbox = alpha.getbbox()
    
    if not bbox:
        # 빈 이미지인 경우 그대로 반환
        return image
        
    text_content = image.crop(bbox)
    content_w, content_h = text_content.size
    w, h = image.size
    
    # 2. 이동할 목표 좌표 (좌상단 기준)
    target_x = (w - content_w) // 2
    
    if target_position == "top":
        target_y = margin
    elif target_position == "center":
        target_y = (h - content_h) // 2
    elif target_position == "bottom":
        target_y = h - content_h - margin
    else:
        # 알 수 없는 위치면 원래대로
        return image
        
    # 3. 새 캔버스에 붙여넣기
    new_image = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    new_image.paste(text_content, (target_x, target_y))
    
    return new_image
