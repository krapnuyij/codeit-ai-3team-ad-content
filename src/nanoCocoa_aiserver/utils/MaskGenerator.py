"""
MaskGenerator.py
합성 영역 마스크 생성 유틸리티

배경 분석 기반 텍스트 배치 영역 마스크를 자동 생성합니다.
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
from PIL import Image, ImageDraw
from typing import Literal, Tuple
from config import logger


MaskMode = Literal["overlay", "top", "center", "bottom", "auto"]


class MaskGenerator:
    """
    합성 영역 마스크 생성기
    
    텍스트 배치 위치와 방식에 따라 적절한 마스크를 생성하여
    Flux Inpainting이 해당 영역만 처리하도록 가이드합니다.
    """
    
    @staticmethod
    def create_text_alpha_mask(
        background: Image.Image,
        text_asset: Image.Image,
        dilation: int = 10
    ) -> Image.Image:
        """
        텍스트 에셋의 알파 채널 기반 마스크 생성
        
        Args:
            background: 배경 이미지 (크기 참조용)
            text_asset: 텍스트 에셋 (RGBA)
            dilation: 마스크 확장 픽셀 (기본 10px)
            
        Returns:
            Image.Image: 마스크 이미지 (L 모드, 255=인페인팅, 0=보존)
        """
        w, h = background.size
        text_resized = text_asset.resize((w, h), Image.LANCZOS)
        
        # 알파 채널 추출
        if text_resized.mode == "RGBA":
            alpha = text_resized.split()[-1]
        else:
            logger.warning("Text asset has no alpha channel, using full white mask")
            alpha = Image.new("L", (w, h), 255)
        
        # 마스크 확장 (텍스트 주변 여백 포함)
        if dilation > 0:
            from PIL import ImageFilter
            # MaxFilter는 홀수 크기만 허용하므로 짝수일 경우 +1
            filter_size = dilation if dilation % 2 == 1 else dilation + 1
            alpha = alpha.filter(ImageFilter.MaxFilter(filter_size))
        
        return alpha
    
    @staticmethod
    def create_position_mask(
        background: Image.Image,
        position: Literal["top", "center", "bottom"],
        coverage: float = 0.4
    ) -> Image.Image:
        """
        위치 기반 영역 마스크 생성
        
        Args:
            background: 배경 이미지
            position: 텍스트 위치 ("top"/"center"/"bottom")
            coverage: 화면 비율 (0.0~1.0, 기본 0.4 = 40%)
            
        Returns:
            Image.Image: 마스크 이미지
        """
        w, h = background.size
        mask = Image.new("L", (w, h), 0)  # 검은색 = 보존
        draw = ImageDraw.Draw(mask)
        
        height_range = int(h * coverage)
        
        if position == "top":
            draw.rectangle([0, 0, w, height_range], fill=255)
        elif position == "center":
            y_start = (h - height_range) // 2
            y_end = y_start + height_range
            draw.rectangle([0, y_start, w, y_end], fill=255)
        elif position == "bottom":
            y_start = h - height_range
            draw.rectangle([0, y_start, w, h], fill=255)
        
        # 부드러운 경계 (가우시안 블러)
        from PIL import ImageFilter
        mask = mask.filter(ImageFilter.GaussianBlur(radius=20))
        
        return mask
    
    @staticmethod
    def create_empty_space_mask(
        background: Image.Image,
        threshold_percentile: int = 40,
        min_area: float = 0.15
    ) -> Image.Image:
        """
        배경의 여백(어두운 영역) 자동 감지 마스크
        
        Args:
            background: 배경 이미지
            threshold_percentile: 밝기 임계값 백분위 (기본 40)
            min_area: 최소 마스크 비율 (기본 0.15 = 15%)
            
        Returns:
            Image.Image: 마스크 이미지
        """
        # 그레이스케일 변환
        bg_gray = background.convert("L")
        bg_arr = np.array(bg_gray)
        
        # 임계값 계산 (어두운 영역 감지)
        threshold = np.percentile(bg_arr, threshold_percentile)
        
        # 마스크 생성 (어두운 영역 = 텍스트 배치 가능 영역)
        mask_arr = (bg_arr < threshold).astype(np.uint8) * 255
        
        # 최소 면적 체크
        mask_ratio = mask_arr.sum() / (bg_arr.shape[0] * bg_arr.shape[1] * 255)
        if mask_ratio < min_area:
            logger.warning(f"Empty space too small ({mask_ratio:.2%}), using top position fallback")
            return MaskGenerator.create_position_mask(background, "top", 0.3)
        
        mask = Image.fromarray(mask_arr)
        
        # 노이즈 제거 및 부드럽게
        from PIL import ImageFilter
        mask = mask.filter(ImageFilter.MedianFilter(size=5))
        mask = mask.filter(ImageFilter.GaussianBlur(radius=10))
        
        return mask
    
    @staticmethod
    def create_combined_mask(
        background: Image.Image,
        text_asset: Image.Image,
        position: Literal["top", "center", "bottom"] = "top",
        mode: MaskMode = "overlay"
    ) -> Image.Image:
        """
        통합 마스크 생성 (권장)
        
        텍스트 알파 + 위치 정보를 결합하여 최적의 마스크 생성
        
        Args:
            background: 배경 이미지
            text_asset: 텍스트 에셋
            position: 텍스트 위치
            mode: 마스크 모드 ("overlay"/"auto" 등)
            
        Returns:
            Image.Image: 최종 마스크
        """
        if mode == "overlay":
            # 텍스트 알파 기반
            return MaskGenerator.create_text_alpha_mask(background, text_asset)
            
        elif mode == "auto":
            # 여백 자동 감지
            return MaskGenerator.create_empty_space_mask(background)
            
        elif mode in ["top", "center", "bottom"]:
            # 위치 기반
            return MaskGenerator.create_position_mask(background, mode)
            
        else:
            logger.warning(f"Unknown mask mode: {mode}, using overlay")
            return MaskGenerator.create_text_alpha_mask(background, text_asset)
    
    @staticmethod
    def visualize_mask(
        background: Image.Image,
        mask: Image.Image,
        alpha: float = 0.5
    ) -> Image.Image:
        """
        마스크 시각화 (디버깅용)
        
        Args:
            background: 배경 이미지
            mask: 마스크 이미지
            alpha: 오버레이 투명도
            
        Returns:
            Image.Image: 마스크가 오버레이된 이미지
        """
        bg_rgba = background.convert("RGBA")
        mask_colored = Image.new("RGBA", mask.size, (255, 0, 0, int(255 * alpha)))
        mask_colored.putalpha(mask)
        
        combined = Image.alpha_composite(bg_rgba, mask_colored)
        return combined.convert("RGB")

    @staticmethod
    def recommend_position(
        background: Image.Image,
        threshold_percentile: int = 40,
        min_area: float = 0.15
    ) -> Literal["top", "center", "bottom"]:
        """
        배경의 여백을 분석하여 최적의 텍스트 배치 위치를 추천합니다.
        
        Args:
            background: 배경 이미지
            threshold_percentile: 밝기 임계값 (기본 40)
            min_area: 최소 면적 비율
            
        Returns:
            Literal["top", "center", "bottom"]: 추천 위치
        """
        w, h = background.size
        # 그레이스케일 변환 및 임계값 마스킹
        bg_gray = background.convert("L")
        bg_arr = np.array(bg_gray)
        threshold = np.percentile(bg_arr, threshold_percentile)
        mask_arr = (bg_arr < threshold) # True for dark areas (empty space)
        
        # 영역별 여백 점수 계산 (단순 픽셀 수)
        # 상단 (0 ~ 33%)
        top_area = mask_arr[0:int(h*0.33), :].sum()
        # 중앙 (33% ~ 66%)
        center_area = mask_arr[int(h*0.33):int(h*0.66), :].sum()
        # 하단 (66% ~ 100%)
        bottom_area = mask_arr[int(h*0.66):h, :].sum()
        
        scores = {
            "top": top_area,
            "center": center_area,
            "bottom": bottom_area
        }
        
        # 가장 여백이 많은 곳 선택
        best_position = max(scores, key=scores.get)
        
        # 전체적으로 여백이 너무 적으면 기본값 top 반환 (안전장치)
        total_pixels = w * h
        if scores[best_position] / (total_pixels / 3) < min_area:
             logger.warning(f"Not enough empty space found (max {scores[best_position]}), defaulting to top")
             return "top"
             
        logger.info(f"Auto-position recommendation: {best_position} (scores: {scores})")
        return best_position
