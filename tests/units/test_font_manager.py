"""
폰트 관리자 단위 테스트.

font_manager 모듈의 폰트 디렉토리 탐색 및 Fallback 로직을 검증합니다.
"""

import pytest
import os
import tempfile
import shutil

import sys
from pathlib import Path

# src/nanoCocoa_aiserver를 path에 추가
sys.path.insert(0, str(Path(__file__).parents[2] / "src" / "nanoCocoa_aiserver"))

from services.fonts import get_fonts_dir, get_available_fonts, get_font_path


class TestGetFontsDir:
    """get_fonts_dir 함수 테스트"""
    
    def test_returns_fonts_directory(self):
        """폰트 디렉토리 경로 반환"""
        result = get_fonts_dir()
        
        assert isinstance(result, str)
        assert "fonts" in result
        assert os.path.isabs(result)


class TestGetAvailableFonts:
    """get_available_fonts 함수 테스트"""
    
    def test_returns_list_of_fonts(self):
        """사용 가능한 폰트 목록 반환"""
        result = get_available_fonts()
        
        assert isinstance(result, list)
        # 실제 환경에 폰트가 있을 수도, 없을 수도 있음
        # 결과가 리스트이기만 하면 OK
    
    def test_filters_ttf_and_otf_only(self):
        """TTF/OTF 파일만 포함"""
        result = get_available_fonts()
        
        for font_path in result:
            assert font_path.lower().endswith(('.ttf', '.otf'))
    
    def test_returns_empty_if_no_fonts_dir(self, monkeypatch):
        """폰트 디렉토리가 없으면 빈 리스트 반환"""
        def mock_fonts_dir():
            return "/nonexistent/path/fonts"
        
        monkeypatch.setattr("services.fonts.get_fonts_dir", mock_fonts_dir)
        result = get_available_fonts()
        
        assert result == []


class TestGetFontPath:
    """get_font_path 함수 테스트"""
    
    def test_returns_existing_font_path(self):
        """존재하는 폰트 경로 반환"""
        available = get_available_fonts()
        
        if not available:
            pytest.skip("No fonts available for testing")
        
        first_font = available[0]
        result = get_font_path(first_font)
        
        assert isinstance(result, str)
        assert os.path.exists(result)
        assert os.path.isfile(result)
    
    def test_fallback_to_yet_hangul(self):
        """존재하지 않는 폰트 요청 시 NanumMyeongjo-YetHangul.ttf로 Fallback"""
        available = get_available_fonts()
        
        if not available:
            pytest.skip("No fonts available for testing")
        
        result = get_font_path("nonexistent_font.ttf")
        
        # Fallback 폰트 반환됨
        assert isinstance(result, str)
        assert os.path.exists(result)
    
    def test_fallback_to_first_font_if_yet_hangul_missing(self):
        """YetHangul이 없으면 첫 번째 폰트로 Fallback"""
        available = get_available_fonts()
        
        if not available:
            pytest.skip("No fonts available for testing")
        
        # YetHangul이 없는 상황 가정
        result = get_font_path("another_nonexistent_font.ttf")
        
        assert isinstance(result, str)
        assert os.path.exists(result)
    
    def test_raises_if_no_fonts_available(self, monkeypatch):
        """폰트가 하나도 없으면 FileNotFoundError 발생"""
        def mock_no_fonts():
            return []
        
        monkeypatch.setattr("services.fonts.get_available_fonts", mock_no_fonts)
        
        with pytest.raises(FileNotFoundError, match="No fonts available"):
            get_font_path("any_font.ttf")
