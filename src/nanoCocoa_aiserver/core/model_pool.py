"""
model_pool.py
Long-lived 워커 프로세스 풀을 관리하여 AIModelEngine을 메모리에 유지합니다.
"""

import multiprocessing
import os
import queue
import time
from typing import Callable, Dict, Optional

from helper_dev_utils import get_auto_logger

from core.engine import AIModelEngine
from utils import flush_gpu

logger = get_auto_logger()

# 워커 풀 크기 (환경 변수에서 읽거나 기본값 1)
WORKER_POOL_SIZE = int(os.environ.get("WORKER_POOL_SIZE", "1"))


class ModelWorkerPool:
    """
    Long-lived 워커 프로세스 풀을 관리합니다.
    각 워커는 초기화 시 AIModelEngine을 로드하여 메모리에 유지하며,
    태스크 큐를 통해 작업을 수신하고 결과를 반환합니다.
    """

    def __init__(self, num_workers: int = WORKER_POOL_SIZE, dummy_mode: bool = False):
        """
        Args:
            num_workers (int): 생성할 워커 프로세스 수 (기본 환경 변수 WORKER_POOL_SIZE 또는 1)
            dummy_mode (bool): 더미 모드 활성화 여부
        """
        self.num_workers = num_workers
        self.dummy_mode = dummy_mode

        # 멀티프로세싱 컨텍스트 (CUDA 호환을 위한 spawn)
        self.mp_context = multiprocessing.get_context("spawn")

        # Manager 생성 (Queue를 프로세스 간 공유하기 위해 필요)
        self.manager = multiprocessing.Manager()

        # 태스크 큐 및 결과 저장소 (manager.Queue 사용)
        self.task_queue = self.manager.Queue()
        self.workers = []

        # 각 작업의 결과를 저장하는 딕셔너리 (job_id -> result_queue)
        self.result_queues: Dict[str, multiprocessing.Queue] = {}

        logger.info(
            f"ModelWorkerPool 초기화 중: num_workers={num_workers}, dummy_mode={dummy_mode}"
        )

        # 워커 프로세스 시작
        for i in range(num_workers):
            worker_process = self.mp_context.Process(
                target=_worker_loop,
                args=(i, self.task_queue, dummy_mode),
                name=f"ModelWorker-{i}",
            )
            worker_process.start()
            self.workers.append(worker_process)
            logger.info(
                f"워커 프로세스 시작됨: PID={worker_process.pid}, name={worker_process.name}"
            )

    def submit_task(
        self,
        job_id: str,
        task_func: Callable,
        input_data: dict,
        shared_state: dict,
        stop_event,
    ) -> None:
        """
        워커 풀에 태스크를 제출합니다.

        Args:
            job_id (str): 작업 ID
            task_func (Callable): 실행할 함수 (worker_process 함수)
            input_data (dict): 입력 데이터
            shared_state (dict): 프로세스 간 공유 상태
            stop_event (multiprocessing.Event): 중단 이벤트
        """
        # 결과 큐 생성 (manager.Queue 사용)
        result_queue = self.manager.Queue()
        self.result_queues[job_id] = result_queue

        # 태스크를 큐에 추가
        task = {
            "job_id": job_id,
            "task_func": task_func,
            "input_data": input_data,
            "shared_state": shared_state,
            "stop_event": stop_event,
            "result_queue": result_queue,
        }

        self.task_queue.put(task)
        logger.info(f"태스크 제출됨: job_id={job_id}")

    def shutdown(self):
        """
        워커 풀을 종료합니다.
        모든 워커에게 종료 신호를 보내고 프로세스를 종료합니다.
        """
        logger.info("ModelWorkerPool 종료 중...")

        # 모든 워커에게 종료 신호 전송 (None을 큐에 삽입)
        for _ in range(self.num_workers):
            self.task_queue.put(None)

        # 워커 프로세스 종료 대기
        for worker in self.workers:
            worker.join(timeout=5)
            if worker.is_alive():
                logger.warning(
                    f"워커 {worker.name}이 정상 종료되지 않아 강제 종료합니다."
                )
                worker.terminate()
                worker.join()

        # Manager 종료
        self.manager.shutdown()

        logger.info("ModelWorkerPool 종료 완료")


def _worker_loop(worker_id: int, task_queue: multiprocessing.Queue, dummy_mode: bool):
    """
    워커 프로세스의 메인 루프입니다.
    초기화 시 AIModelEngine을 로드하고, 태스크 큐에서 작업을 가져와 실행합니다.

    Args:
        worker_id (int): 워커 ID
        task_queue (multiprocessing.Queue): 태스크 큐
        dummy_mode (bool): 더미 모드 활성화 여부
    """
    logger.info(f"[Worker-{worker_id}] 프로세스 시작 (PID: {os.getpid()})")

    # GPU 메모리 초기화
    logger.info(f"[Worker-{worker_id}] GPU 메모리 초기화 중...")
    flush_gpu()
    logger.info(f"[Worker-{worker_id}] GPU 메모리 초기화 완료")

    # AIModelEngine 초기화 (메모리에 유지)
    logger.info(f"[Worker-{worker_id}] AIModelEngine 초기화 중...")
    engine = None

    # 태스크 루프
    task = None
    while True:
        try:
            # 큐에서 태스크 가져오기 (블로킹)
            task = task_queue.get(timeout=1)

            # 종료 신호 (None) 확인
            if task is None:
                logger.info(f"[Worker-{worker_id}] 종료 신호 수신, 워커 종료")
                break

            job_id = task["job_id"]
            task_func = task["task_func"]
            input_data = task["input_data"]
            shared_state = task["shared_state"]
            stop_event = task["stop_event"]
            result_queue = task["result_queue"]

            logger.info(f"[Worker-{worker_id}] 태스크 실행 시작: job_id={job_id}")

            # 진행률 콜백 함수 정의
            def update_progress(*args, **kwargs):
                """진행률 업데이트를 shared_state에 반영"""
                step_num = kwargs.get("step_num", args[0] if len(args) > 0 else 0)
                total_steps = kwargs.get("total_steps", args[1] if len(args) > 1 else 1)
                sub_step_name = kwargs.get(
                    "sub_step_name", args[2] if len(args) > 2 else "unknown"
                )

                # shared_state 업데이트는 원래 worker_process 함수 내에서 수행
                # 여기서는 단순히 로깅만 수행
                pass

            # AIModelEngine 초기화 (첫 태스크 실행 시 1회만)
            if engine is None:
                auto_unload = input_data.get("auto_unload", False)
                test_mode = input_data.get("test_mode", False)
                engine = AIModelEngine(
                    dummy_mode=test_mode or dummy_mode,
                    progress_callback=update_progress,
                    auto_unload=auto_unload,
                )
                logger.info(
                    f"[Worker-{worker_id}] AIModelEngine 초기화 완료 (auto_unload={auto_unload})"
                )

            # 태스크 함수 실행 (worker_process)
            start_time = time.time()
            task_func(
                job_id=job_id,
                input_data=input_data,
                shared_state=shared_state,
                stop_event=stop_event,
                engine=engine,  # AIModelEngine 인스턴스 전달
            )
            elapsed_time = time.time() - start_time

            logger.info(
                f"[Worker-{worker_id}] 태스크 실행 완료: job_id={job_id}, elapsed={elapsed_time:.2f}s"
            )

            # 결과 큐에 완료 신호 전송 (현재는 사용하지 않음)
            result_queue.put({"status": "completed", "job_id": job_id})

        except queue.Empty:
            # 타임아웃 발생 시 계속 대기
            continue

        except Exception as e:
            logger.error(
                f"[Worker-{worker_id}] 태스크 실행 중 오류 발생: {e}", exc_info=True
            )
            # shared_state에 오류 상태 기록 (task가 정의된 경우에만)
            if task and "shared_state" in task:
                task["shared_state"]["status"] = "error"
                task["shared_state"]["message"] = f"워커 오류: {str(e)}"

    # 워커 종료 시 GPU 메모리 정리
    logger.info(f"[Worker-{worker_id}] GPU 메모리 정리 중...")
    flush_gpu()
    logger.info(f"[Worker-{worker_id}] 프로세스 종료")
