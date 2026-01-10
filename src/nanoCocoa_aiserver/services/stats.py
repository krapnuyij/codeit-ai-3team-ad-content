"""
단계별 실행 통계 관리 모듈.

이전 실행 기록을 바탕으로 평균 소요 시간을 계산하고 저장합니다.
지수 이동 평균(EMA) 방식으로 동적 업데이트를 지원합니다.
"""

import json
import os
from typing import Dict, Optional

from config import logger


class StepStatsManager:
    """
    단계별 실행 통계를 관리하는 클래스입니다.
    이전 실행 기록을 바탕으로 평균 소요 시간을 계산하고 저장합니다.
    """

    DEFAULT_STATS = {
        "step1_background": 80.0,  # 실측 평균 ~80초 (배경 생성)
        "step2_text": 35.0,  # 실측 평균 ~35초 (텍스트 생성)
        "step3_composite": 5.0,  # 실측 평균 ~5초 (합성, 최소 안전값)
        "step1_count": 29,  # step1 의 합계의 안전값
        "step2_count": 46,  # step2 의 합계의 안전값
        "step3_count": 94,  # step3 의 합계의 안전값
        "total_count": 94,  # step1 + step2 + step3 의 합계의 안전값
        "total_time": 900,  # 전체 요청당 최대 시간 (초)
    }

    def __init__(self, stats_file: Optional[str] = None):
        """
        Args:
            stats_file (str, optional): 통계 파일 경로. None이면 기본 경로 사용.
        """
        if stats_file is None:
            stats_file = os.path.join(os.path.dirname(__file__), "step_stats.json")

        self.stats_file = stats_file
        self.stats = self.load_stats()

    def load_stats(self) -> Dict[str, float]:
        """
        파일에서 통계를 로드하거나 기본값을 반환합니다.

        Returns:
            Dict[str, float]: 단계별 평균 소요 시간 (초)
        """
        if not os.path.exists(self.stats_file):
            logger.info(
                f"Stats file not found. Using default values: {self.DEFAULT_STATS}"
            )
            return self.DEFAULT_STATS.copy()

        try:
            with open(self.stats_file, "r") as f:
                data = json.load(f)

            # Ensure all keys exist
            for key, val in self.DEFAULT_STATS.items():
                if key not in data:
                    data[key] = val

            logger.info(f"Loaded stats from {self.stats_file}: {data}")
            return data
        except Exception as e:
            logger.error(f"Failed to load step stats: {e}")
            return self.DEFAULT_STATS.copy()

    def update_stat(self, step_name: str, duration: float) -> None:
        """
        지수 이동 평균(EMA) 방식을 사용하여 특정 단계의 평균 소요 시간을 업데이트합니다.

        Args:
            step_name (str): 단계 이름 (예: "step1_background")
            duration (float): 실제 소요 시간 (초)

        Notes:
            EMA 공식: new_avg = (current_avg * 0.8) + (duration * 0.2)
            최근 값에 20% 가중치를 부여합니다.
        """
        if step_name not in self.stats:
            self.stats[step_name] = duration
            logger.info(f"Initialized new stat '{step_name}' = {duration:.2f}s")
        else:
            # EMA with alpha = 0.2 (recent values have 20% weight)
            self.stats[step_name] = duration
            logger.debug(f"Updated stat '{step_name}': {duration}s")
            # current_avg = self.stats[step_name]
            # new_avg = (current_avg * 0.8) + (duration * 0.2)
            # self.stats[step_name] = round(new_avg, 2)
            # logger.debug(
            #     f"Updated stat '{step_name}': {current_avg:.2f}s -> {new_avg:.2f}s"
            # )

        self.save_stats()

    def get_stat(self, step_name: str) -> float:
        """
        특정 단계의 평균 소요 시간을 반환합니다.

        Args:
            step_name (str): 단계 이름

        Returns:
            float: 평균 소요 시간 (초). 존재하지 않으면 기본값 10.0 반환.
        """
        return self.stats.get(step_name, self.DEFAULT_STATS.get(step_name, 10.0))

    def save_stats(self) -> None:
        """
        현재 통계를 파일에 저장합니다.
        """
        try:
            with open(self.stats_file, "w") as f:
                json.dump(self.stats, f, indent=4)
            logger.debug(f"Saved stats to {self.stats_file}")
        except Exception as e:
            logger.error(f"Failed to save step stats: {e}")


# 전역 싱글톤 인스턴스
step_stats_manager = StepStatsManager()
