"""
폰트 관리 모듈.

폰트 디렉토리 탐색, 사용 가능한 폰트 목록 조회, 폰트 경로 반환 기능을 제공합니다.
"""

import os
from typing import List

from config import logger


def get_fonts_dir() -> str:
    """
    폰트 디렉토리 경로를 반환합니다.
    
    Returns:
        str: 폰트 디렉토리의 절대 경로 (프로젝트 루트의 'fonts' 폴더)
    """
    # services/ 폴더에서 한 단계 상위(nanoCocoa_aiserver/)로 이동
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    return os.path.join(parent_dir, "fonts")


def get_available_fonts() -> List[str]:
    """
    사용 가능한 폰트 파일 이름 목록을 반환합니다.
    하위 디렉토리까지 재귀적으로 검색합니다.
    
    Returns:
        List[str]: 폰트 파일의 상대 경로 리스트 
                   (예: '나눔고딕/NanumGothic.ttf')
    """
    fonts_dir = get_fonts_dir()
    if not os.path.exists(fonts_dir):
        logger.warning(f"Fonts directory not found: {fonts_dir}")
        return []
    
    font_files = []
    for root, _, files in os.walk(fonts_dir):
        for file in files:
            if file.lower().endswith(('.ttf', '.otf')):
                # fonts_dir로부터의 상대 경로 저장
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, fonts_dir)
                font_files.append(rel_path)
    
    return sorted(font_files)


def get_font_path(font_name: str) -> str:
    """
    폰트 파일의 전체 경로를 반환합니다.
    
    Args:
        font_name (str): 폰트 파일 경로 (get_available_fonts에서 반환된 상대 경로)
        
    Returns:
        str: 폰트 파일 전체 경로. 존재하지 않으면 Fallback 폰트 반환.
        
    Raises:
        FileNotFoundError: 폰트 디렉토리에 사용 가능한 폰트가 없는 경우
        
    Notes:
        Fallback 우선순위:
        1. 요청된 font_name
        2. font_name이 파일명만 포함한 경우 검색
        3. NanumMyeongjo-YetHangul.ttf (기본 폰트)
        4. 첫 번째 사용 가능한 폰트
    """
    fonts_dir = get_fonts_dir()
    # 입력받은 font_name이 절대경로일 수도 있고, 파일명만 있을 수도 있음
    # 우선 fonts_dir와 결합하여 확인
    font_path = os.path.join(fonts_dir, font_name)
    
    if os.path.exists(font_path) and os.path.isfile(font_path):
        return font_path
    
    # 혹시 파일명만 넘어왔을 경우, 검색
    available = get_available_fonts()
    for rel_path in available:
        if os.path.basename(rel_path) == font_name:
            return os.path.join(fonts_dir, rel_path)

    # 그래도 없으면 기본값 (NanumMyeongjo-YetHangul.ttf 우선 시도)
    yet_hangul = "NanumMyeongjo-YetHangul.ttf"
    if available:
        # 1순위: NanumMyeongjo-YetHangul.ttf 찾기
        for rel_path in available:
            if os.path.basename(rel_path) == yet_hangul:
                logger.info(f"Font '{font_name}' not found. Using fallback '{yet_hangul}'.")
                return os.path.join(fonts_dir, rel_path)
        
        # 2순위: 그냥 첫 번째 폰트
        logger.warning(f"Font '{font_name}' not found. Using fallback '{available[0]}'.")
        return os.path.join(fonts_dir, available[0])
    
    raise FileNotFoundError("No fonts available in 'fonts' directory.")
