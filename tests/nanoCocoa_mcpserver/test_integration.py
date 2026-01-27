"""
통합 테스트
실제 nanoCocoa_aiserver와 연동하여 전체 워크플로우를 테스트합니다.

주의: 이 테스트는 nanoCocoa_aiserver가 실행 중이어야 합니다!
실행 방법:
1. AI 서버 시작: python -m uvicorn nanoCocoa_aiserver.main:app --host 0.0.0.0 --port 8000
2. 테스트 실행: pytest tests/nanoCocoa_mcpserver/test_integration.py -v
"""

import pytest
import asyncio
import os
import logging
from pathlib import Path
from tqdm import tqdm

from nanoCocoa_mcpserver.client.api_client import AIServerClient, AIServerError
from nanoCocoa_mcpserver.schemas.api_models import GenerateRequest
from nanoCocoa_mcpserver.utils.image_utils import (
    image_file_to_base64,
    base64_to_image_file,
)


@pytest.fixture
def integration_output_dir(tmp_path):
    """통합 테스트 출력 디렉토리"""
    output_dir = tmp_path / "integration_output"
    output_dir.mkdir(exist_ok=True)
    return output_dir


@pytest.mark.asyncio
@pytest.mark.integration
async def test_health_check(require_aiserver):
    """헬스체크 통합 테스트"""
    async with AIServerClient() as client:
        health = await client.check_health()
        assert health.status in ["healthy", "busy"]
        assert health.total_jobs >= 0
        assert health.active_jobs >= 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_fonts(require_aiserver):
    """폰트 목록 조회 통합 테스트"""
    async with AIServerClient() as client:
        fonts = await client.get_fonts()
        assert isinstance(fonts, list)
        # 최소 1개 이상의 폰트가 있어야 함
        assert len(fonts) > 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_full_pipeline_test_mode(require_aiserver, integration_output_dir):
    """전체 파이프라인 테스트 (테스트 모드)"""
    logger = logging.getLogger(__name__)
    logger.info("전체 파이프라인 테스트 시작 - 테스트 모드로 빠르게 진행합니다...")

    async with AIServerClient() as client:
        # 테스트 모드로 빠르게 실행
        params = GenerateRequest(
            start_step=1,
            product_image=None,  # 테스트 모드에서는 필수 아님
            bg_prompt="Modern office desk, laptop",
            text_content="TEST",
            text_model_prompt="Gold metallic text",
            test_mode=True,  # 테스트 모드
            auto_unload=False,
        )

        # 생성 시작
        logger.info("작업 생성 요청 중...")
        response = await client.start_generation(params)
        job_id = response.job_id

        assert job_id is not None
        assert response.status in ["started", "pending"]
        logger.info(
            f"작업 시작됨 (Job ID: {job_id}) - 완료까지 최대 30초 소요, 잠시 기다려주세요..."
        )

        # 완료 대기
        final_status = await client.wait_for_completion(
            job_id, poll_interval=1.0, max_retries=30
        )

        # 완료 확인
        logger.info("작업 완료 - 결과 검증 중...")
        assert final_status.status == "completed"
        assert final_status.progress_percent == 100

        # 테스트 모드에서도 결과가 있어야 함
        assert final_status.final_result is not None

        # 결과 저장
        output_path = integration_output_dir / "test_mode_result.png"
        base64_to_image_file(final_status.final_result, output_path)
        assert output_path.exists()

        # 작업 삭제
        await client.delete_job(job_id)


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
async def test_step_by_step_workflow(require_aiserver, integration_output_dir):
    """단계별 워크플로우 통합 테스트 (테스트 모드)"""
    logger = logging.getLogger(__name__)
    async with AIServerClient() as client:
        # Step 1: 배경 생성
        logger.info("[Step 1/3] 배경 생성 시작 - 잠시 기다려주세요...")
        step1_params = GenerateRequest(
            start_step=1,
            product_image=None,
            bg_prompt="Wooden table, cozy cafe",
            text_content=None,  # 배경만
            test_mode=True,
        )

        step1_result = await client.generate_and_wait(step1_params)
        assert step1_result.status == "completed"
        assert step1_result.step1_result is not None
        logger.info("[Step 1/3] 배경 생성 완료")

        # Step 1 결과 저장
        step1_path = integration_output_dir / "step1_bg.png"
        base64_to_image_file(step1_result.step1_result, step1_path)

        # Step 2: 3D 텍스트 생성
        logger.info("[Step 2/3] 3D 텍스트 생성 시작 - 잠시 기다려주세요...")
        step2_params = GenerateRequest(
            start_step=2,
            step1_image=step1_result.step1_result,
            text_content="SALE",
            text_model_prompt="Gold balloon text",
            test_mode=True,
        )

        step2_result = await client.generate_and_wait(step2_params)
        assert step2_result.status == "completed"
        assert step2_result.step2_result is not None
        logger.info("[Step 2/3] 3D 텍스트 생성 완료")

        # Step 2 결과 저장
        step2_path = integration_output_dir / "step2_text.png"
        base64_to_image_file(step2_result.step2_result, step2_path)

        # Step 3: 최종 합성
        logger.info("[Step 3/3] 최종 합성 시작 - 잠시 기다려주세요...")
        step3_params = GenerateRequest(
            start_step=3,
            step1_image=step1_result.step1_result,
            step2_image=step2_result.step2_result,
            composition_mode="overlay",
            text_position="center",
            test_mode=True,
        )

        step3_result = await client.generate_and_wait(step3_params)
        assert step3_result.status == "completed"
        assert step3_result.final_result is not None
        logger.info("[Step 3/3] 최종 합성 완료")

        # 최종 결과 저장
        final_path = integration_output_dir / "step3_final.png"
        base64_to_image_file(step3_result.final_result, final_path)

        # 모든 단계 파일 확인
        assert step1_path.exists()
        assert step2_path.exists()
        assert final_path.exists()
        logger.info("모든 단계 완료 및 검증 성공")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_job_stop(require_aiserver):
    """작업 중단 통합 테스트"""
    async with AIServerClient() as client:
        # 긴 작업 시작
        params = GenerateRequest(
            start_step=1,
            bg_prompt="Complex scene",
            text_content="LONG",
            text_model_prompt="Complex style",
            test_mode=False,  # 실제 모드 (더 오래 걸림)
        )

        response = await client.start_generation(params)
        job_id = response.job_id

        # 약간 대기
        await asyncio.sleep(2)

        # 작업 중단
        stop_result = await client.stop_job(job_id)
        assert stop_result.job_id == job_id
        assert stop_result.status == "stopped"

        # 상태 확인
        status = await client.get_status(job_id)
        assert status.status in ["stopped", "stopping"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_concurrent_requests(require_aiserver):
    """동시 요청 처리 테스트"""
    logger = logging.getLogger(__name__)
    logger.info("동시 요청 테스트 시작 - 3개의 작업을 동시에 처리합니다...")

    async with AIServerClient() as client:
        # 여러 작업 동시 시작
        params_list = [
            GenerateRequest(
                start_step=1,
                bg_prompt=f"Scene {i}",
                text_content=f"TEST{i}",
                text_model_prompt="Simple style",
                test_mode=True,
            )
            for i in range(3)
        ]

        # 동시에 시작 (하나는 실행, 나머지는 503 대기)
        tasks = [client.start_generation(params) for params in params_list]

        # tqdm으로 진행상황 표시
        with tqdm(total=len(tasks), desc="동시 요청 처리", unit="req") as pbar:
            completed_results = []
            for coro in asyncio.as_completed(tasks):
                try:
                    result = await coro
                    completed_results.append(result)
                except Exception as e:
                    completed_results.append(e)
                pbar.update(1)

            results = completed_results

        # 최소 1개는 성공해야 함
        successful = [r for r in results if not isinstance(r, Exception)]
        assert len(successful) >= 1
        logger.info(f"동시 요청 완료: 성공 {len(successful)}/{len(results)}")

        # 503 에러는 예상된 동작
        errors = [r for r in results if isinstance(r, AIServerError)]
        for error in errors:
            if error.status_code == 503:
                assert error.retry_after is not None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_jobs(require_aiserver):
    """작업 목록 조회 통합 테스트"""
    async with AIServerClient() as client:
        jobs = await client.list_jobs()

        assert jobs.total_jobs >= 0
        assert jobs.active_jobs >= 0
        assert jobs.completed_jobs >= 0
        assert jobs.failed_jobs >= 0

        # 합계 확인
        assert (
            jobs.completed_jobs + jobs.failed_jobs + jobs.active_jobs <= jobs.total_jobs
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_error_handling_invalid_params(require_aiserver):
    """잘못된 파라미터 에러 처리 테스트 - 서버가 요청을 거부하지 않고 받아들이는지 확인"""
    async with AIServerClient() as client:
        # start_step이 유효하지 않음
        params = GenerateRequest(
            start_step=2,  # Step 2인데
            step1_image=None,  # step1_image가 없음
            text_content="TEST",
            text_model_prompt="Style",
            test_mode=True,
        )

        # 서버가 요청을 받아들여야 함 (에러를 던지지 않음)
        # test_mode에서는 validation을 느슨하게 처리
        result = await client.start_generation(params)
        assert result.job_id
        assert result.status == "started"

        # 작업이 대기열에 추가되었는지 확인
        status = await client.get_status(result.job_id)
        assert status.status in ["pending", "processing", "completed", "failed"]


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow  # 느린 테스트 마커
async def test_timeout_handling(require_aiserver):
    """타임아웃 처리 테스트 - test_mode로 빠르게 검증"""
    import logging

    logger = logging.getLogger(__name__)

    logger.info("[TEST] test_timeout_handling 시작")

    # 매우 짧은 타임아웃으로 클라이언트 생성
    logger.info("[TEST] AIServerClient 생성 (timeout=0.5)")
    async with AIServerClient(timeout=0.5) as client:
        # test_mode로 빠른 응답 받기
        logger.info("[TEST] GenerateRequest 파라미터 생성")
        params = GenerateRequest(
            start_step=1,
            bg_prompt="Test",
            text_content="TEST",
            text_model_prompt="Test",
            test_mode=True,  # 테스트 모드로 빠른 완료
        )
        logger.info(
            f"[TEST] 생성된 파라미터: start_step={params.start_step}, test_mode={params.test_mode}"
        )

        # test_mode에서는 정상 완료되어야 함
        logger.info("[TEST] generate_and_wait 호출 시작")
        result = await client.generate_and_wait(params)
        logger.info(f"[TEST] generate_and_wait 완료: status={result.status}")

        assert result.status in ["success", "completed"]
        logger.info("[TEST] test_timeout_handling 성공적으로 완료")
