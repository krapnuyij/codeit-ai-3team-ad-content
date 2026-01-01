"""
worker.py
백그라운드 워커 프로세스 관리
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

import multiprocessing
import time
from PIL import Image

from config import logger
from utils import pil_to_base64, base64_to_pil, flush_gpu, step_stats_manager
from AIModelEngine import AIModelEngine
from step_processors import process_step1_background, process_step2_text, process_step3_composite


def worker_process(job_id: str, input_data: dict, shared_state: dict, stop_event: multiprocessing.Event):
    """
    Step 기반(1->2->3) 순차 실행 워커 프로세스.
    
    Args:
        job_id: 작업 ID
        input_data: 클라이언트 요청 데이터
        shared_state: 프로세스 간 공유 상태 딕셔너리
        stop_event: 작업 중단 이벤트
    """
    
    # 파라미터 추출
    test_mode = input_data.get('test_mode', False)
    
    # 진행률 업데이트 콜백 함수
    def update_progress(step_num: int, total_steps: int, sub_step_name: str):
        """
        모델 파이프라인 내부의 진행률을 shared_state에 반영합니다.
        
        Args:
            step_num: 현재 스텝 (1-based)
            total_steps: 전체 스텝 수
            sub_step_name: 서브 스텝 이름
        """
        # 현재 메인 스텝 확인
        current_main_step = shared_state.get('current_step', 'step1_background')
        
        # 메인 스텝별 진행률 범위 정의
        # Step 1: 0-33%, Step 2: 33-66%, Step 3: 66-100%
        if 'step1' in current_main_step:
            base_progress = 0
            step_range = 33
        elif 'step2' in current_main_step:
            base_progress = 33
            step_range = 33
        elif 'step3' in current_main_step:
            base_progress = 66
            step_range = 34
        else:
            base_progress = 0
            step_range = 33
        
        # 서브 스텝 내 진행률 계산 (0.0 ~ 1.0)
        sub_progress = step_num / total_steps
        
        # 최종 진행률 = 베이스 + (서브 진행률 * 스텝 범위)
        final_progress = int(base_progress + (sub_progress * step_range))
        final_progress = min(100, max(0, final_progress))
        
        shared_state['progress_percent'] = final_progress
        shared_state['sub_step'] = f"{sub_step_name} ({step_num}/{total_steps})"
        from utils import get_system_metrics
        shared_state['system_metrics'] = get_system_metrics()
        
        shared_state['progress_percent'] = final_progress
        shared_state['sub_step'] = f"{sub_step_name} ({step_num}/{total_steps})"
        from utils import get_system_metrics
        shared_state['system_metrics'] = get_system_metrics()
        
        # [ETA 계산] 통계 기반 동적 예측
        # 현재 진행 중인 단계와 남은 단계들의 평균 소요 시간을 합산하여 계산합니다.
        current_step_key = "step1_background"
        if 'step2' in current_main_step: current_step_key = "step2_text"
        elif 'step3' in current_main_step: current_step_key = "step3_composite"
        
        avg_time = step_stats_manager.get_stat(current_step_key)
        step_remaining = max(0, avg_time * (1.0 - sub_progress))
        shared_state['step_eta_seconds'] = int(step_remaining)
        
        # [전체 ETA 계산]
        # 현재 단계의 남은 시간 + 이후 단계들의 평균 소요 시간 합계
        total_remaining = step_remaining
        # 미래 단계 시간 추가 (현재 단계에 따라 다름)
        if 'step1' in current_main_step:
             total_remaining += step_stats_manager.get_stat("step2_text")
             total_remaining += step_stats_manager.get_stat("step3_composite")
        elif 'step2' in current_main_step:
             total_remaining += step_stats_manager.get_stat("step3_composite")
             
        shared_state['eta_seconds'] = int(total_remaining)
        shared_state['eta_update_time'] = time.time()
    
    engine = AIModelEngine(dummy_mode=test_mode, progress_callback=update_progress)
    
    try:
        shared_state['status'] = 'running'
        shared_state['start_time'] = time.time()
        shared_state['sub_step'] = None
        shared_state['eta_seconds'] = 0
        
        # 파라미터 추출
        start_step = input_data.get('start_step', 1)
        
        # 단계별 결과물 변수 (PIL Image)
        step1_result = None
        step2_result = None
        final_result = None

        # ==========================================
        # Step 1: 배경 생성 (Background Generation)
        # ==========================================
        if start_step <= 1:
            s1_start = time.time()
            step1_result = process_step1_background(engine, input_data, shared_state, stop_event)
            s1_dur = time.time() - s1_start
            step_stats_manager.update_stat("step1_background", s1_dur)
            
            if step1_result:
                shared_state['images']['step1_result'] = pil_to_base64(step1_result)
                shared_state['progress_percent'] = 33
        else:
            # Step 1을 건너뛸 경우, 입력받은 step1_image 사용
            img_s1_b64 = input_data.get('step1_image')
            if img_s1_b64:
                step1_result = base64_to_pil(img_s1_b64)
                shared_state['images']['step1_result'] = img_s1_b64

        # ==========================================
        # Step 2: 텍스트 에셋 생성 (Text Asset Gen)
        # ==========================================
        if start_step <= 2:
            s2_start = time.time()
            step2_result = process_step2_text(engine, input_data, shared_state, stop_event)
            s2_dur = time.time() - s2_start
            step_stats_manager.update_stat("step2_text", s2_dur)

            if step2_result:
                shared_state['images']['step2_result'] = pil_to_base64(step2_result)
                shared_state['progress_percent'] = 66
        else:
            # Step 2 건너뛸 경우
            img_s2_b64 = input_data.get('step2_image')
            if img_s2_b64:
                step2_result = base64_to_pil(img_s2_b64)
                shared_state['images']['step2_result'] = img_s2_b64

        # ==========================================
        # Step 3: 최종 합성 (Final Composite)
        # ==========================================
        if start_step <= 3:
            # Step 1, Step 2 결과물 확보 확인
            if not step1_result and shared_state['images'].get('step1_result'):
                step1_result = base64_to_pil(shared_state['images']['step1_result'])
                
            if not step2_result and shared_state['images'].get('step2_result'):
                step2_result = base64_to_pil(shared_state['images']['step2_result'])
            
            s3_start = time.time()
            final_result = process_step3_composite(step1_result, step2_result, shared_state, stop_event)
            s3_dur = time.time() - s3_start
            step_stats_manager.update_stat("step3_composite", s3_dur)

            if final_result:
                shared_state['images']['final_result'] = pil_to_base64(final_result)
                shared_state['progress_percent'] = 100

        # 완료 처리
        if stop_event.is_set():
            shared_state['status'] = 'stopped'
            shared_state['message'] = 'Job stopped by user.'
        else:
            shared_state['status'] = 'completed'
            shared_state['message'] = 'All steps completed successfully.'

    except Exception as e:
        logger.error(f"Worker error for job {job_id}: {e}", exc_info=True)
        shared_state['status'] = 'failed'
        shared_state['message'] = f'Error: {str(e)}'
        
    finally:
        flush_gpu()
