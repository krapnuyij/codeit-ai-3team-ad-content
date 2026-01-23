"""
폰트 관련 핸들러 함수
"""

import logging
from typing import Optional

from handlers.generation import get_api_client
from client.api_client import AIServerError

from helper_dev_utils import get_auto_logger

logger = get_auto_logger()


async def list_available_fonts() -> str:
    """AI 서버에 설치된 폰트 목록을 조회합니다."""
    try:
        client = await get_api_client()
        fonts = await client.get_fonts()

        response = f"사용 가능한 폰트 ({len(fonts)}개):\n\n"
        for font in fonts:
            response += f"  - {font}\n"

        return response

    except AIServerError as e:
        return f"AI 서버 에러: {str(e)}"


async def get_fonts_metadata() -> str:
    """폰트 메타데이터를 조회합니다 (스타일, 굵기, 용도 등)."""
    import json

    try:
        client = await get_api_client()
        metadata = await client.get_fonts_metadata()

        return json.dumps(metadata, ensure_ascii=False, indent=2)

    except AIServerError as e:
        logger.error(f"AI 서버 연결 실패: {e}")
        # JSON 형식으로 에러 반환 (파싱 오류 방지)
        error_response = {
            "error": "ai_server_connection_failed",
            "message": str(e),
            "fonts": [],  # 빈 폰트 목록 반환
        }
        return json.dumps(error_response, ensure_ascii=False)


async def recommend_font_for_ad(
    text_content: str,
    ad_type: str = "general",
    tone: Optional[str] = None,
    weight_preference: Optional[str] = None,
) -> str:
    """
    광고 콘텐츠에 적합한 폰트를 자동으로 추천합니다.

    Args:
        text_content: 광고 텍스트
        ad_type: 광고 유형 (sale/premium/casual/promotion/general)
        tone: 톤앤매너 (energetic/elegant/friendly/modern/traditional)
        weight_preference: 선호 굵기 (light/bold/heavy)
    """
    try:
        client = await get_api_client()
        metadata = await client.get_fonts_metadata()

        if not metadata:
            return "폰트 메타데이터를 가져올 수 없습니다."

        # 한글 텍스트 판별
        has_korean = any("\uac00" <= char <= "\ud7a3" for char in text_content)

        # 필터링: 영문 전용 폰트 제외
        if has_korean:
            candidates = [f for f in metadata if "d2coding" not in f["name"].lower()]
        else:
            candidates = metadata

        if not candidates:
            return "조건에 맞는 폰트를 찾을 수 없습니다."

        # 광고 유형별 필터링
        if ad_type == "sale":
            candidates = [
                f
                for f in candidates
                if f["style"] == "gothic"
                and f["weight"] in ["bold", "extrabold", "heavy"]
                and "sale" in f["usage"]
            ]
        elif ad_type == "premium":
            candidates = [
                f
                for f in candidates
                if (f["style"] == "serif" or f["weight"] in ["light", "regular"])
                and "premium" in f["usage"]
            ]
        elif ad_type == "casual":
            candidates = [f for f in candidates if f["style"] == "handwriting"]
        elif ad_type == "promotion":
            candidates = [
                f
                for f in candidates
                if f["style"] == "gothic" and "promotion" in f["usage"]
            ]

        # 톤앤매너 필터링
        if tone and candidates:
            tone_filtered = [f for f in candidates if tone in f["tone"]]
            if tone_filtered:
                candidates = tone_filtered

        # 굵기 선호도 필터링
        if weight_preference and candidates:
            weight_filtered = [
                f for f in candidates if f["weight"] == weight_preference
            ]
            if weight_filtered:
                candidates = weight_filtered

        # 최종 선택
        if not candidates:
            if has_korean:
                default_fonts = [
                    f
                    for f in metadata
                    if "gothic" in f["name"].lower() or "고딕" in f["name"]
                ]
                selected = default_fonts[0] if default_fonts else metadata[0]
            else:
                selected = metadata[0]
            reason = "조건에 정확히 맞는 폰트가 없어 기본 폰트를 선택했습니다."
        else:
            selected = candidates[0]
            reason = f"광고 유형({ad_type}), 스타일({selected['style']}), 굵기({selected['weight']})를 고려하여 선택했습니다."

        return (
            f"추천 폰트: {selected['name']}\n"
            f"스타일: {selected['style']}\n"
            f"굵기: {selected['weight']}\n"
            f"용도: {', '.join(selected['usage'])}\n"
            f"톤: {', '.join(selected['tone'])}\n"
            f"선택 이유: {reason}"
        )

    except AIServerError as e:
        return f"AI 서버 에러: {str(e)}"
    except Exception as e:
        logger.exception(f"폰트 추천 중 에러: {e}")
        return f"폰트 추천 중 에러 발생: {str(e)}"
