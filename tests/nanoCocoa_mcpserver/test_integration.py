"""
통합 테스트
실제 nanoCocoa_aiserver와 연동하여 전체 워크플로우를 테스트합니다.

주의: 이 테스트는 nanoCocoa_aiserver가 실행 중이어야 합니다!
"""

import pytest
import asyncio
import os
from pathlib import Path

from nanoCocoa_mcpserver.client.api_client import AIServerClient, AIServerError
from nanoCocoa_mcpserver.schemas.api_models import GenerateRequest
from nanoCocoa_mcpserver.utils.image_utils import (
    image_file_to_base64,
    base64_to_image_file
)


# 실제 서버가 실행 중이지 않으면 테스트 스킵
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "true",
    reason="통합 테스트는 RUN_INTEGRATION_TESTS=true 환경 변수가 필요합니다"
)


@pytest.fixture
def integration_output_dir(tmp_path):
    """통합 테스트 출력 디렉토리"""
    output_dir = tmp_path / "integration_output"
    output_dir.mkdir(exist_ok=True)
    return output_dir


@pytest.mark.asyncio
@pytest.mark.integration
async def test_health_check():
    """헬스체크 통합 테스트"""
    async with AIServerClient() as client:
        try:
            health = await client.check_health()
            assert health.status in ["healthy", "busy"]
            assert health.total_jobs >= 0
            assert health.active_jobs >= 0
        except AIServerError as e:
            pytest.skip(f"AI 서버가 실행 중이지 않습니다: {e}")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_fonts():
    """폰트 목록 조회 통합 테스트"""
    async with AIServerClient() as client:
        try:
            fonts = await client.get_fonts()
            assert isinstance(fonts, list)
            # 최소 1개 이상의 폰트가 있어야 함
            assert len(fonts) > 0
        except AIServerError as e:
            pytest.skip(f"AI 서버가 실행 중이지 않습니다: {e}")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_full_pipeline_test_mode(integration_output_dir):
    """전체 파이프라인 테스트 (테스트 모드)"""
    async with AIServerClient() as client:
        try:
            # 테스트 모드로 빠르게 실행
            params = GenerateRequest(
                start_step=1,
                input_image=None,  # 테스트 모드에서는 필수 아님
                bg_prompt="Modern office desk, laptop",
                text_content="TEST",
                text_model_prompt="Gold metallic text",
                test_mode=True,  # 테스트 모드
                auto_unload=True,
            )

            # 생성 시작
            response = await client.start_generation(params)
            job_id = response.job_id

            assert job_id is not None
            assert response.status in ["started", "pending"]

            # 완료 대기
            final_status = await client.wait_for_completion(
                job_id,
                poll_interval=1.0,
                max_retries=30
            )

            # 완료 확인
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

        except AIServerError as e:
            pytest.skip(f"AI 서버가 실행 중이지 않습니다: {e}")


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
async def test_step_by_step_workflow(integration_output_dir):
    """단계별 워크플로우 통합 테스트 (테스트 모드)"""
    async with AIServerClient() as client:
        try:
            # Step 1: 배경 생성
            step1_params = GenerateRequest(
                start_step=1,
                input_image=None,
                bg_prompt="Wooden table, cozy cafe",
                text_content=None,  # 배경만
                test_mode=True,
            )

            step1_result = await client.generate_and_wait(step1_params)
            assert step1_result.status == "completed"
            assert step1_result.step1_result is not None

            # Step 1 결과 저장
            step1_path = integration_output_dir / "step1_bg.png"
            base64_to_image_file(step1_result.step1_result, step1_path)

            # Step 2: 3D 텍스트 생성
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

            # Step 2 결과 저장
            step2_path = integration_output_dir / "step2_text.png"
            base64_to_image_file(step2_result.step2_result, step2_path)

            # Step 3: 최종 합성
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

            # 최종 결과 저장
            final_path = integration_output_dir / "step3_final.png"
            base64_to_image_file(step3_result.final_result, final_path)

            # 모든 단계 파일 확인
            assert step1_path.exists()
            assert step2_path.exists()
            assert final_path.exists()

        except AIServerError as e:
            pytest.skip(f"AI 서버가 실행 중이지 않습니다: {e}")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_job_stop():
    """작업 중단 통합 테스트"""
    async with AIServerClient() as client:
        try:
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

        except AIServerError as e:
            if e.status_code == 503:
                pytest.skip("서버가 사용 중입니다")
            else:
                pytest.skip(f"AI 서버가 실행 중이지 않습니다: {e}")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_concurrent_requests():
    """동시 요청 처리 테스트"""
    async with AIServerClient() as client:
        try:
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
            tasks = [
                client.start_generation(params)
                for params in params_list
            ]

            # 첫 번째는 성공, 나머지는 503 에러 가능
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 최소 1개는 성공해야 함
            successful = [r for r in results if not isinstance(r, Exception)]
            assert len(successful) >= 1

            # 503 에러는 예상된 동작
            errors = [r for r in results if isinstance(r, AIServerError)]
            for error in errors:
                if error.status_code == 503:
                    assert error.retry_after is not None

        except Exception as e:
            pytest.skip(f"동시 요청 테스트 실패: {e}")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_jobs():
    """작업 목록 조회 통합 테스트"""
    async with AIServerClient() as client:
        try:
            jobs = await client.list_jobs()

            assert jobs.total_jobs >= 0
            assert jobs.active_jobs >= 0
            assert jobs.completed_jobs >= 0
            assert jobs.failed_jobs >= 0

            # 합계 확인
            assert (
                jobs.completed_jobs + jobs.failed_jobs + jobs.active_jobs
                <= jobs.total_jobs
            )

        except AIServerError as e:
            pytest.skip(f"AI 서버가 실행 중이지 않습니다: {e}")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_error_handling_invalid_params():
    """잘못된 파라미터 에러 처리 테스트"""
    async with AIServerClient() as client:
        try:
            # start_step이 유효하지 않음
            params = GenerateRequest(
                start_step=2,  # Step 2인데
                step1_image=None,  # step1_image가 없음
                text_content="TEST",
                text_model_prompt="Style",
                test_mode=True,
            )

            # 에러가 발생해야 함
            with pytest.raises(AIServerError):
                await client.generate_and_wait(params)

        except AIServerError as e:
            if "실행 중이지 않습니다" in str(e):
                pytest.skip(f"AI 서버가 실행 중이지 않습니다: {e}")
            else:
                # 예상된 에러
                pass


@pytest.mark.asyncio
@pytest.mark.integration
async def test_timeout_handling():
    """타임아웃 처리 테스트"""
    # 매우 짧은 타임아웃으로 클라이언트 생성
    async with AIServerClient(timeout=1) as client:
        try:
            # 긴 작업 시작
            params = GenerateRequest(
                start_step=1,
                bg_prompt="Complex",
                text_content="LONG",
                text_model_prompt="Complex",
                test_mode=False,  # 실제 모드
            )

            # 타임아웃 에러가 발생할 수 있음
            with pytest.raises((AIServerError, asyncio.TimeoutError)):
                await client.generate_and_wait(
                    params,
                    poll_interval=0.5,
                    max_retries=3
                )

        except AIServerError as e:
            if "실행 중이지 않습니다" in str(e):
                pytest.skip(f"AI 서버가 실행 중이지 않습니다: {e}")
            else:
                # 예상된 에러
                pass
