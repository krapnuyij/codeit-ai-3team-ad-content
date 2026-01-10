"""
generation.py
광고 생성 관련 API 엔드포인트
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import multiprocessing
import uuid
import time
from fastapi import APIRouter, HTTPException, Response, status

from config import logger, TOTAL_ESTIMATED_TIME
from utils import get_system_metrics
from schemas import GenerateRequest, StatusResponse, SystemMetrics, GPUMetric
from core.worker import worker_process


router = APIRouter()

# CUDA 호환성을 위한 spawn context 명시적 사용
mp_context = multiprocessing.get_context("spawn")

# 전역 상태 (main.py에서 주입됨)
manager = None
JOBS = None
PROCESSES = None
STOP_EVENTS = None


def init_shared_state(mgr, jobs_dict, processes_dict, stop_events_dict):
    """공유 상태 초기화 (app.py에서 호출)"""
    global manager, JOBS, PROCESSES, STOP_EVENTS
    manager = mgr
    JOBS = jobs_dict
    PROCESSES = processes_dict
    STOP_EVENTS = stop_events_dict


@router.post(
    "/generate",
    summary="AI 광고 생성 작업 시작 (Start Generation Job)",
    response_description="생성된 작업의 ID와 상태",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "작업이 성공적으로 큐에 등록되고 시작됨",
            "content": {
                "application/json": {
                    "example": {
                        "job_id": "550e8400-e29b-41d4-a716-446655440000",
                        "status": "started",
                    }
                }
            },
        },
        503: {
            "description": "서버가 다른 작업을 처리 중임 (Busy)",
            "content": {
                "application/json": {
                    "example": {
                        "status": "busy",
                        "message": "현재 다른 작업이 진행 중입니다. 약 25초 후에 다시 시도해주세요.",
                        "retry_after": 25,
                    }
                }
            },
        },
    },
)
async def generate_ad(req: GenerateRequest, response: Response):
    """
     **새로운 생성 파이프라인을 시작합니다.** (Non-blocking)

    클라이언트는 `job_id`를 반환받은 후, `/status/{job_id}`를 폴링하여 진행 상황과 결과를 확인해야 합니다.

    ### Step 구조 및 실행 방법
    1. **Step 1 (Background)**:
       - `start_step=1` (기본값)
       - `input_image` (누끼 딸 상품 이미지) 선택
    2. **Step 2 (Text Asset)**:
       - `start_step=2`
       - `step1_image` (배경 합성된 이미지) 필수
       - 텍스트만 다시 생성하고 싶을 때 사용
    3. **Step 3 (Composition)**:
       - `start_step=3`
       - `step1_image` (배경), `step2_image` (텍스트) 필수
       - 단순히 두 이미지를 합성만 다시 하고 싶을 때 사용

    ### 동시성 정책
    - 이 서버는 **단일 작업(Single Job)**만 처리합니다.
    - 이미 작업이 돌고 있을 경우 **503 Service Unavailable** 응답과 함께 `Retry-After` 헤더를 반환합니다.
    """

    # 동시성 제어
    active_jobs = [j for j, s in JOBS.items() if s["status"] in ("running", "pending")]
    if active_jobs:
        curr = JOBS[active_jobs[0]]
        elapsed = time.time() - (curr["start_time"] or time.time())
        remain = max(0, TOTAL_ESTIMATED_TIME - elapsed)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        response.headers["Retry-After"] = str(int(remain))
        return {
            "status": "busy",
            "message": f"Busy. Retry after {int(remain)}s",
            "retry_after": int(remain),
        }

    job_id = str(uuid.uuid4())
    stop_event = mp_context.Event()
    input_data = req.model_dump()

    JOBS[job_id] = manager.dict(
        {
            "status": "pending",
            "step_count": 0,
            "progress_percent": 0,
            "current_step": "init",
            "message": "Initializing...",
            "error": None,
            "images": manager.dict(),
            "start_time": None,
            "parameters": input_data,
        }
    )

    p = mp_context.Process(
        target=worker_process, args=(job_id, input_data, JOBS[job_id], stop_event)
    )
    p.start()
    PROCESSES[job_id] = p
    STOP_EVENTS[job_id] = stop_event

    return {"job_id": job_id, "status": "started"}


@router.get(
    "/status/{job_id}",
    response_model=StatusResponse,
    summary="작업 상태 및 결과 조회 (Get Job Status)",
    response_description="진행률, 현재 단계, 생성된 이미지(Base64), 시스템 메트릭 및 파라미터",
)
async def get_status(job_id: str):
    """
    특정 작업(Job)의 현재 진행 상황과 중간/최종 결과물을 조회합니다.
    실시간 CPU/GPU 사용률 및 서브스텝 정보를 포함합니다.

    ### 반환 필드 설명
    - **status**: `pending`, `running`, `completed`, `failed`, `stopped`
    - **progress_percent**: 0 ~ 100 진행률
    - **current_step**: 현재 수행 중인 단계 (`step1_background` 등)
    - **sub_step**: 현재 수행 중인 서브 단계 (`segmentation`, `flux_background_generation` 등)
    - **system_metrics**: 실시간 CPU/RAM/GPU 사용률
    - **parameters**: 작업 생성 시 사용된 모든 입력 파라미터 (재시도 시 유용)
    - **step1_result**: [Optional] 1단계 결과 (Base64 이미지)
    - **step2_result**: [Optional] 2단계 결과 (Base64 이미지)
    - **final_result**: [Optional] 최종 결과 (Base64 이미지)
    """
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")

    state = JOBS[job_id]
    elapsed = time.time() - state["start_time"] if state["start_time"] else 0

    # [실시간 ETA 차감]
    # 워커 업데이트 이후 흐른 시간을 차감하여 부드러운 카운트다운을 구현합니다.
    # 예상 시간 초과 시 음수로 표시되어 지연 시간을 알 수 있습니다.
    eta_seconds = state.get("eta_seconds", 0)
    step_eta_seconds = state.get("step_eta_seconds", 0)
    last_update = state.get("eta_update_time")

    if last_update and state["status"] == "running":
        time_since_update = time.time() - last_update
        eta_seconds = int(eta_seconds - time_since_update)
        step_eta_seconds = int(step_eta_seconds - time_since_update)

    # ManagerDict -> dict copy needed before serializing
    images_snapshot = dict(state["images"])

    # 실시간 시스템 메트릭 가져오기
    current_metrics = get_system_metrics()
    system_metrics_model = SystemMetrics(
        cpu_percent=current_metrics["cpu_percent"],
        ram_used_gb=current_metrics["ram_used_gb"],
        ram_total_gb=current_metrics["ram_total_gb"],
        ram_percent=current_metrics["ram_percent"],
        gpu_info=[GPUMetric(**gpu) for gpu in current_metrics["gpu_info"]],
    )

    return StatusResponse(
        job_id=job_id,
        status=state["status"],
        progress_percent=state["progress_percent"],
        current_step=state["current_step"],
        sub_step=state.get("sub_step"),
        message=state["message"],
        elapsed_sec=round(elapsed, 1),
        eta_seconds=eta_seconds,
        step_eta_seconds=step_eta_seconds,
        system_metrics=system_metrics_model,
        parameters=state.get("parameters", {}),
        step1_result=images_snapshot.get("step1_result"),
        step2_result=images_snapshot.get("step2_result"),
        final_result=images_snapshot.get("final_result"),
    )


@router.post(
    "/stop/{job_id}",
    summary="작업 강제 중단 (Stop Job)",
    response_description="중단 요청 결과",
)
async def stop_job(job_id: str):
    """
    실행 중인 작업을 즉시 중단합니다.
    GPU 리소스를 해제하고 작업을 `stopped` 상태로 변경합니다.
    """
    if job_id in STOP_EVENTS:
        STOP_EVENTS[job_id].set()

    if job_id in PROCESSES:
        p = PROCESSES[job_id]
        if p.is_alive():
            p.join(timeout=3)
            if p.is_alive():
                p.terminate()

        if job_id in JOBS:
            JOBS[job_id]["status"] = "stopped"
        return {"job_id": job_id, "status": "stopped"}

    raise HTTPException(status_code=404, detail="Job not found")


@router.get(
    "/jobs",
    summary="모든 작업 목록 조회 (Get All Jobs)",
    response_description="전체 작업 목록과 각 작업의 상태",
)
async def get_all_jobs():
    """
    서버에 존재하는 모든 작업의 목록을 조회합니다.

    ### 반환 필드 설명
    - **total_jobs**: 전체 작업 개수
    - **jobs**: 작업 목록 (각 작업의 job_id, status, progress, current_step, message 포함)
    - **active_jobs**: 현재 실행 중이거나 대기 중인 작업 개수
    - **completed_jobs**: 완료된 작업 개수
    - **failed_jobs**: 실패한 작업 개수

    ### 작업 상태 설명
    - **pending**: 대기 중
    - **running**: 실행 중
    - **completed**: 완료됨
    - **failed**: 실패함
    - **stopped**: 사용자가 중단함
    """
    jobs_list = []
    active_count = 0
    completed_count = 0
    failed_count = 0

    for job_id, state in JOBS.items():
        start_time = state.get("start_time")
        elapsed_sec = round(time.time() - start_time, 1) if start_time else 0.0

        job_info = {
            "job_id": job_id,
            "status": state["status"],
            "progress_percent": state["progress_percent"],
            "current_step": state["current_step"],
            "message": state["message"],
            "start_time": start_time,
            "elapsed_sec": elapsed_sec,
        }
        jobs_list.append(job_info)

        if state["status"] in ("running", "pending"):
            active_count += 1
        elif state["status"] == "completed":
            completed_count += 1
        elif state["status"] == "failed":
            failed_count += 1

    return {
        "total_jobs": len(jobs_list),
        "active_jobs": active_count,
        "completed_jobs": completed_count,
        "failed_jobs": failed_count,
        "jobs": jobs_list,
    }


@router.delete(
    "/jobs/{job_id}", summary="작업 삭제 (Delete Job)", response_description="삭제 결과"
)
async def delete_job(job_id: str):
    """
    완료되었거나 실패한 작업을 메모리에서 삭제합니다.

    ### 주의사항
    - 실행 중인 작업은 삭제할 수 없습니다. 먼저 `/stop/{job_id}`로 중단해야 합니다.
    - 삭제된 작업의 결과는 더 이상 조회할 수 없습니다.

    ### 사용 시나리오
    - 완료된 작업의 결과를 다운로드한 후 메모리 정리
    - 실패한 작업 기록 제거
    - 서버 리소스 관리 및 최적화
    """
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")

    state = JOBS[job_id]
    if state["status"] in ("running", "pending"):
        raise HTTPException(
            status_code=400,
            detail="Cannot delete running job. Please stop it first using /stop/{job_id}",
        )

    # 프로세스 정리
    if job_id in PROCESSES:
        del PROCESSES[job_id]
    if job_id in STOP_EVENTS:
        del STOP_EVENTS[job_id]

    # 작업 정보 삭제
    del JOBS[job_id]

    return {
        "job_id": job_id,
        "status": "deleted",
        "message": "Job successfully deleted from memory",
    }
