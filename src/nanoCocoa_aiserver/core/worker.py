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

# CUDA 호환성을 위한 안전장치: spawn 방식 확인
# main.py에서 이미 설정되었지만, 직접 실행 시를 대비
try:
    if multiprocessing.get_start_method(allow_none=True) != "spawn":
        multiprocessing.set_start_method("spawn", force=True)
except RuntimeError:
    # 이미 설정된 경우 무시
    pass

from config import logger
from utils import (
    pil_to_base64,
    base64_to_pil,
    flush_gpu,
    step_stats_manager,
    get_system_metrics,
)
from core.engine import AIModelEngine
from core.processors import (
    process_step1_background,
    process_step2_text,
    process_step3_composite,
)


def worker_process(
    job_id: str, input_data: dict, shared_state: dict, stop_event: multiprocessing.Event
):
    """
    Step 기반(1->2->3) 순차 실행 워커 프로세스.

    Args:
        job_id: 작업 ID
        input_data: 클라이언트 요청 데이터
        shared_state: 프로세스 간 공유 상태 딕셔너리
        stop_event: 작업 중단 이벤트
    """

    # 파라미터 추출
    test_mode = input_data.get("test_mode", False)
    step1_count = step_stats_manager.get_stat("step1_count")
    step2_count = step_stats_manager.get_stat("step2_count")
    step3_count = step_stats_manager.get_stat("step3_count")
    total_count = step_stats_manager.get_stat("total_count")
    total_time = step_stats_manager.get_stat("total_time")

    # 진행률 업데이트 콜백 함수
    # def update_progress(step_num: int, total_steps: int, sub_step_name: str):
    def update_progress(*args, **kwargs):
        """
        모델 파이프라인 내부의 진행률을 shared_state에 반영합니다.

        Args:
            step_num: 현재 스텝 (1-based)
            total_steps: 전체 스텝 수
            sub_step_name: 서브 스텝 이름
        """
        step_num = kwargs.get("step_num", args[0] if len(args) > 0 else 0)
        total_steps = kwargs.get("total_steps", args[1] if len(args) > 1 else 1)
        sub_step_name = kwargs.get(
            "sub_step_name", args[2] if len(args) > 2 else "unknown"
        )

        # 현재 메인 스텝 확인
        current_main_step = shared_state.get("current_step", "step1_background")

        # 메인 스텝별 진행률 범위 정의
        # Step 1: 0-33%, Step 2: 33-66%, Step 3: 66-100%
        step_num = 0
        total_steps = 1
        if "step1" in current_main_step:
            base_progress = (100 * step1_count) / total_count
            step_range = (100 * step1_count) / total_count
            step_num = shared_state["step_count"]
            total_steps = step1_count
        elif "step2" in current_main_step:
            base_progress = (100 * step2_count) / total_count
            step_range = (100 * (step2_count - step1_count)) / total_count
            step_num = shared_state["step_count"]
            total_steps = step2_count
        elif "step3" in current_main_step:
            base_progress = (100 * step3_count) / total_count
            step_range = (100 * (step3_count - step2_count)) / total_count
            step_num = shared_state["step_count"]
            total_steps = step3_count
        else:
            base_progress = 0
            step_range = (100 * (step3_count - step2_count)) / total_count
            step_num = shared_state["step_count"]
            total_steps = step3_count

        # 최종 진행률 = 베이스 + (가중된 서브 진행률 * 스텝 범위)
        # final_progress = int(base_progress + (progress_weight * step_range))
        final_progress = int((shared_state["step_count"] / total_count) * 100)
        final_progress = min(100, max(0, final_progress))

        shared_state["step_count"] = shared_state["step_count"] + 1
        shared_state["progress_percent"] = final_progress
        shared_state["sub_step"] = f"{sub_step_name} ({step_num}/{total_steps})"
        shared_state["system_metrics"] = get_system_metrics()

        # [ETA 계산] 통계 기반 동적 예측
        # 현재 진행 중인 단계와 남은 단계들의 평균 소요 시간을 합산하여 계산합니다.
        current_step_key = "step1_background"
        if "step2" in current_main_step:
            current_step_key = "step2_text"
        elif "step3" in current_main_step:
            current_step_key = "step3_composite"

        avg_time = step_stats_manager.get_stat(current_step_key)

        # step_remaining = max(0, avg_time * (1.0 - progress_weight))
        step_remaining = max(0, (avg_time * (step_range / 100.0)))
        shared_state["step_eta_seconds"] = int(step_remaining)

        # [전체 ETA 계산]
        # 현재 단계의 남은 시간 + 이후 단계들의 평균 소요 시간 합계
        total_remaining = step_remaining
        # 미래 단계 시간 추가 (현재 단계에 따라 다름)
        if "step1" in current_main_step:
            total_remaining += step_stats_manager.get_stat("step2_text")
            total_remaining += step_stats_manager.get_stat("step3_composite")
        elif "step2" in current_main_step:
            total_remaining += step_stats_manager.get_stat("step3_composite")

        shared_state["eta_seconds"] = int(total_remaining)
        shared_state["eta_update_time"] = time.time()

        logger.debug(" ")
        logger.debug(
            f"step_count={shared_state['step_count']} avg_time={avg_time} step_range={step_range}"
        )

    # auto_unload 설정 (기본값: True)
    auto_unload = input_data.get("auto_unload", True)
    engine = AIModelEngine(
        dummy_mode=test_mode, progress_callback=update_progress, auto_unload=auto_unload
    )

    try:
        shared_state["status"] = "running"
        shared_state["start_time"] = time.time()
        shared_state["sub_step"] = None

        # 파라미터 추출
        start_step = input_data.get("start_step", 1)

        # [초기 ETA 계산]
        initial_eta = 0
        initial_step_eta = 0

        if start_step <= 1:
            initial_eta += step_stats_manager.get_stat("step1_background")
            initial_step_eta = step_stats_manager.get_stat("step1_background")
            # Step 1 implies subsequent steps
            initial_eta += step_stats_manager.get_stat("step2_text")
            initial_eta += step_stats_manager.get_stat("step3_composite")
        elif start_step == 2:
            initial_eta += step_stats_manager.get_stat("step2_text")
            initial_step_eta = step_stats_manager.get_stat("step2_text")
            initial_eta += step_stats_manager.get_stat("step3_composite")
        elif start_step == 3:
            initial_eta += step_stats_manager.get_stat("step3_composite")
            initial_step_eta = step_stats_manager.get_stat("step3_composite")

        shared_state["eta_seconds"] = int(initial_eta)
        shared_state["step_eta_seconds"] = int(initial_step_eta)
        shared_state["eta_update_time"] = time.time()

        # 단계별 결과물 변수 (PIL Image)
        step1_result = None
        step2_result = None
        final_result = None

        # ==========================================
        # Step 1: 배경 생성 (Background Generation)
        # ==========================================
        if start_step <= 1:
            try:
                s1_start = time.time()
                step1_result = process_step1_background(
                    engine, input_data, shared_state, stop_event
                )
                s1_dur = time.time() - s1_start

                if not test_mode:
                    step_stats_manager.update_stat("step1_background", s1_dur)
                    step_stats_manager.update_stat(
                        "step1_count", shared_state["step_count"]
                    )

                if step1_result:
                    shared_state["images"]["step1_result"] = pil_to_base64(step1_result)
                    shared_state["progress_percent"] = int(
                        (step1_count / total_count) * 100
                    )
                else:
                    raise ValueError("Step 1 returned None - 배경 생성 실패")

            except Exception as e:
                logger.error(
                    f"[Worker] Step 1 failed for job {job_id}: {e}", exc_info=True
                )
                shared_state["status"] = "error"
                shared_state["message"] = f"Step 1 오류 (배경 생성 실패): {str(e)}"
                return
        else:
            # Step 1을 건너뛸 경우, 입력받은 step1_image 사용
            img_s1_b64 = input_data.get("step1_image")
            if not img_s1_b64:
                logger.error(f"[Worker] start_step={start_step}인데 step1_image 없음")
                shared_state["status"] = "error"
                shared_state["message"] = (
                    "start_step > 1이지만 step1_image가 제공되지 않았습니다."
                )
                return

            try:
                step1_result = base64_to_pil(img_s1_b64)
                shared_state["images"]["step1_result"] = img_s1_b64
            except Exception as e:
                logger.error(f"[Worker] step1_image 디코딩 실패: {e}")
                shared_state["status"] = "error"
                shared_state["message"] = f"step1_image 디코딩 실패: {str(e)}"
                return

        # text_content가 없으면 STEP 2, 3 건너뛰고 STEP 1 결과를 최종 이미지로 사용
        text_content = input_data.get("text_content")
        if not text_content or text_content.strip() == "":
            logger.info(
                f"[Worker] text_content 없음 → STEP 2, 3 건너뛰고 STEP 1 결과를 최종 이미지로 설정"
            )
            shared_state["images"]["final_result"] = shared_state["images"][
                "step1_result"
            ]
            shared_state["progress_percent"] = 100
            shared_state["status"] = "completed"
            shared_state["message"] = "Background generation completed (텍스트 없음)."
            return

        # ==========================================
        # Step 2: 텍스트 에셋 생성 (Text Asset Gen)
        # ==========================================
        if start_step <= 2:
            try:
                s2_start = time.time()
                step2_result = process_step2_text(
                    engine, input_data, shared_state, stop_event
                )
                s2_dur = time.time() - s2_start

                if not test_mode:
                    step_stats_manager.update_stat("step2_text", s2_dur)
                    step_stats_manager.update_stat(
                        "step2_count", shared_state["step_count"]
                    )

                if step2_result:
                    shared_state["images"]["step2_result"] = pil_to_base64(step2_result)
                    shared_state["progress_percent"] = int(
                        (step2_count / total_count) * 100
                    )
                else:
                    raise ValueError("Step 2 returned None - 텍스트 생성 실패")

            except Exception as e:
                logger.error(
                    f"[Worker] Step 2 failed for job {job_id}: {e}", exc_info=True
                )
                shared_state["status"] = "error"
                shared_state["message"] = f"Step 2 오류 (텍스트 생성 실패): {str(e)}"
                return
        else:
            # Step 2 건너뛸 경우
            img_s2_b64 = input_data.get("step2_image")
            if not img_s2_b64:
                logger.error(f"[Worker] start_step={start_step}인데 step2_image 없음")
                shared_state["status"] = "error"
                shared_state["message"] = (
                    "start_step > 2이지만 step2_image가 제공되지 않았습니다."
                )
                return

            try:
                step2_result = base64_to_pil(img_s2_b64)
                shared_state["images"]["step2_result"] = img_s2_b64
            except Exception as e:
                logger.error(f"[Worker] step2_image 디코딩 실패: {e}")
                shared_state["status"] = "error"
                shared_state["message"] = f"step2_image 디코딩 실패: {str(e)}"
                return

        # ==========================================
        # Step 3: 최종 합성 (Final Composite)
        # ==========================================
        if start_step <= 3:
            try:
                # Step 1, Step 2 결과물 확보 확인
                if not step1_result and shared_state["images"].get("step1_result"):
                    step1_result = base64_to_pil(shared_state["images"]["step1_result"])

                if not step2_result and shared_state["images"].get("step2_result"):
                    step2_result = base64_to_pil(shared_state["images"]["step2_result"])

                if not step1_result or not step2_result:
                    raise ValueError(
                        f"Step 3 requires both step1 and step2 results. "
                        f"step1_result={'exists' if step1_result else 'missing'}, "
                        f"step2_result={'exists' if step2_result else 'missing'}"
                    )

                s3_start = time.time()
                final_result = process_step3_composite(
                    engine,
                    step1_result,
                    step2_result,
                    input_data,
                    shared_state,
                    stop_event,
                )
                s3_dur = time.time() - s3_start

                if not test_mode:
                    step_stats_manager.update_stat("step3_composite", s3_dur)
                    step_stats_manager.update_stat(
                        "step3_count", shared_state["step_count"]
                    )
                    step_stats_manager.update_stat(
                        "total_count", shared_state["step_count"]
                    )
                    step_stats_manager.update_stat(
                        "total_time", time.time() - shared_state["start_time"]
                    )

                if final_result:
                    shared_state["images"]["final_result"] = pil_to_base64(final_result)
                    shared_state["progress_percent"] = int(
                        (step3_count / total_count) * 100
                    )
                else:
                    raise ValueError("Step 3 returned None - 합성 실패")

            except Exception as e:
                logger.error(
                    f"[Worker] Step 3 failed for job {job_id}: {e}", exc_info=True
                )
                shared_state["status"] = "error"
                shared_state["message"] = f"Step 3 오류 (합성 실패): {str(e)}"
                return

        # 완료 처리
        if stop_event.is_set():
            shared_state["status"] = "stopped"
            shared_state["message"] = "Job stopped by user."
        else:
            shared_state["status"] = "completed"
            shared_state["message"] = "All steps completed successfully."

    except Exception as e:
        logger.error(f"[Worker] Unexpected error for job {job_id}: {e}", exc_info=True)
        shared_state["status"] = "error"
        shared_state["message"] = f"예상치 못한 오류: {str(e)}"

    finally:
        flush_gpu()
