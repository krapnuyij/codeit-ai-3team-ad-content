"""
통계 관리자 단위 테스트.

stats_manager 모듈의 ETA 계산 및 통계 저장 로직을 검증합니다.
"""

import pytest
import json
import tempfile
import os

import sys
from pathlib import Path

# src/nanoCocoa_aiserver를 path에 추가
sys.path.insert(0, str(Path(__file__).parents[2] / "src" / "nanoCocoa_aiserver"))

from services.stats import StepStatsManager


class TestStepStatsManager:
    """StepStatsManager 클래스 테스트"""
    
    @pytest.fixture
    def temp_stats_file(self):
        """임시 통계 파일 생성"""
        fd, path = tempfile.mkstemp(suffix=".json")
        # 현재 운영 환경 기본값 (2026-01-01 기준)
        test_defaults = {
            "step1_background": 80.0,
            "step2_text": 35.0,
            "step3_composite": 5.0
        }
        with os.fdopen(fd, 'w') as f:
            json.dump(test_defaults, f)
        
        yield path
        # Cleanup
        if os.path.exists(path):
            os.remove(path)
    
    def test_initializes_with_default_stats(self, temp_stats_file):
        """기본 통계로 초기화"""
        manager = StepStatsManager(stats_file=temp_stats_file)
        
        assert manager.get_stat("step1_background") == 80.0
        assert manager.get_stat("step2_text") == 35.0
        assert manager.get_stat("step3_composite") == 5.0
    
    def test_updates_stat_with_ema(self, temp_stats_file):
        """EMA 방식으로 통계 업데이트"""
        manager = StepStatsManager(stats_file=temp_stats_file)
        
        # 초기값: 80.0
        initial = manager.get_stat("step1_background")
        
        # 100초 소요 시뮬레이션
        manager.update_stat("step1_background", 100.0)
        
        # EMA: (80.0 * 0.8) + (100.0 * 0.2) = 84.0
        assert manager.get_stat("step1_background") == 84.0
    
    def test_creates_new_stat_if_not_exists(self, temp_stats_file):
        """존재하지 않는 단계의 통계 생성"""
        manager = StepStatsManager(stats_file=temp_stats_file)
        
        manager.update_stat("step4_new", 30.0)
        
        assert manager.get_stat("step4_new") == 30.0
    
    def test_persists_stats_to_file(self, temp_stats_file):
        """통계를 파일에 저장"""
        manager = StepStatsManager(stats_file=temp_stats_file)
        
        manager.update_stat("step1_background", 200.0)
        
        # 파일 읽기
        with open(temp_stats_file, 'r') as f:
            data = json.load(f)
        
        # EMA 적산: (80.0 * 0.8) + (200.0 * 0.2) = 104.0
        assert data["step1_background"] == 104.0
    
    def test_loads_existing_stats_from_file(self, temp_stats_file):
        """기존 통계 파일 로드"""
        # 파일에 미리 통계 저장
        stats_data = {
            "step1_background": 500.0,
            "step2_text": 300.0,
            "step3_composite": 80.0
        }
        with open(temp_stats_file, 'w') as f:
            json.dump(stats_data, f)
        
        manager = StepStatsManager(stats_file=temp_stats_file)
        
        assert manager.get_stat("step1_background") == 500.0
        assert manager.get_stat("step2_text") == 300.0
        assert manager.get_stat("step3_composite") == 80.0
    
    def test_returns_default_for_unknown_stat(self, temp_stats_file):
        """알 수 없는 통계는 기본값 반환"""
        manager = StepStatsManager(stats_file=temp_stats_file)
        
        # DEFAULT_STATS에도 없고 stats에도 없는 경우
        result = manager.get_stat("unknown_step")
        
        assert result == 10.0  # Fallback default
    
    def test_handles_corrupted_stats_file(self):
        """손상된 통계 파일은 기본값으로 Fallback"""
        # 별도 임시 파일 생성
        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            # 잘못된 JSON 작성
            with os.fdopen(fd, 'w') as f:
                f.write("{ invalid json }")
            
            manager = StepStatsManager(stats_file=path)
            
            # DEFAULT_STATS로 fallback됨 (현재 실제 기본값)
            assert manager.get_stat("step1_background") == 80.0
            assert manager.get_stat("step2_text") == 35.0
            assert manager.get_stat("step3_composite") == 5.0
        finally:
            if os.path.exists(path):
                os.remove(path)
    
    def test_multiple_updates_converge_to_recent_value(self, temp_stats_file):
        """여러 번 업데이트 시 최근 값으로 수렴"""
        manager = StepStatsManager(stats_file=temp_stats_file)
        
        # 초기값: 80.0
        # 200초를 10번 업데이트
        for _ in range(10):
            manager.update_stat("step1_background", 200.0)
        
        final_value = manager.get_stat("step1_background")
        
        # 200초에 가까워야 함 (EMA로 인해 점진적 수렴)
        # 초기값 80.0에서 시작하여 200.0으로 수렴
        assert 150.0 <= final_value <= 200.0
