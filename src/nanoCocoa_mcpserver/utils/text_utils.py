"""
텍스트 처리 유틸리티
언어 감지 및 프롬프트 전처리 기능
"""

import re
from typing import Literal


def detect_language(text: str) -> Literal["koclip", "openai"]:
    """
    텍스트에서 한글 포함 여부로 언어 감지

    Args:
        text: 분석할 텍스트

    Returns:
        "koclip": 한글 포함 시 (KoCLIP 모델 사용)
        "openai": 한글 미포함 시 (OpenAI CLIP 모델 사용)

    Examples:
        >>> detect_language("빨간 사과")
        'koclip'
        >>> detect_language("red apple")
        'openai'
        >>> detect_language("Red apple 빨강")
        'koclip'
    """
    korean_pattern = re.compile(r"[ㄱ-ㅎㅏ-ㅣ가-힣]")
    return "koclip" if korean_pattern.search(text) else "openai"


def truncate_prompt(text: str, max_words: int = 77) -> str:
    """
    프롬프트를 최대 단어 수로 자르기 (CLIP 모델 77토큰 제한 대응)

    Args:
        text: 원본 프롬프트
        max_words: 최대 단어 수 (기본값: 77)

    Returns:
        잘린 프롬프트 (필요 시 "..." 추가)

    Examples:
        >>> truncate_prompt("a " * 100, max_words=5)
        'a a a a a...'
    """
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "..."


def summarize_prompt(text: str, max_words: int = 50) -> str:
    """
    긴 프롬프트를 요약 (핵심 키워드 추출 방식)

    Args:
        text: 원본 프롬프트
        max_words: 최대 단어 수 (기본값: 50)

    Returns:
        요약된 프롬프트

    Examples:
        >>> summarize_prompt("A beautiful red apple on a white background with studio lighting")
        'beautiful red apple white background studio lighting'
    """
    # 불용어 제거 (간단한 버전)
    stopwords = {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "on",
        "in",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "and",
        "or",
        "but",
        "so",
        "이",
        "가",
        "을",
        "를",
        "은",
        "는",
        "에",
        "와",
        "과",
        "의",
        "로",
        "으로",
    }

    words = text.split()
    filtered_words = [
        word for word in words if word.lower() not in stopwords and len(word) > 1
    ]

    # 최대 단어 수로 자르기
    if len(filtered_words) <= max_words:
        return " ".join(filtered_words)

    return " ".join(filtered_words[:max_words])
