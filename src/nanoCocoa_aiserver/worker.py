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
from utils import pil_to_base64, base64_to_pil, flush_gpu
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
    
    engine = AIModelEngine(dummy_mode=test_mode, progress_callback=update_progress)
    
    try:
        shared_state['status'] = 'running'
        shared_state['start_time'] = time.time()
        shared_state['sub_step'] = None
        
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
            step1_result = process_step1_background(engine, input_data, shared_state, stop_event)
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
            step2_result = process_step2_text(engine, input_data, shared_state, stop_event)
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
            
            final_result = process_step3_composite(step1_result, step2_result, shared_state, stop_event)
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
