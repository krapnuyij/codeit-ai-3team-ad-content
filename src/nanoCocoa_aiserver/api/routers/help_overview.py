"""
help_overview.py
전체 API 사용 가이드 엔드포인트
"""

from fastapi import APIRouter

router = APIRouter()


@router.get(
    "/help",
    summary="전체 API 사용 가이드 (API Usage Guide)",
    response_description="API 사용법과 워크플로우 안내",
)
async def get_help():
    """
    nanoCocoa AI 광고 생성 서버의 전체 사용 가이드를 제공합니다.

    이 엔드포인트는 LLM이나 개발자가 API를 처음 사용할 때 필요한 모든 정보를 제공합니다.
    """
    return {
        "server_info": {
            "name": "L4 Optimized AI Ad Generator",
            "version": "2.0.0",
            "description": "상품 이미지 + 텍스트 → AI 광고 이미지 생성 서버 (Nvidia L4 GPU 최적화)",
        },
        "quick_start": {
            "step1": "GET /health - 서버 상태 확인 (선택사항)",
            "step2": "GET /fonts - 사용 가능한 폰트 목록 조회",
            "step3": "POST /generate - 광고 생성 작업 시작 (job_id 반환)",
            "step4": "GET /status/{job_id} - 작업 진행 상태 및 결과 조회 (폴링)",
            "step5": "작업 완료 시 final_result 필드에서 Base64 이미지 다운로드",
        },
        "main_endpoints": {
            "generation": {
                "POST /generate": {
                    "description": "새로운 광고 생성 작업 시작 (비동기)",
                    "required_fields": {
                        "product_image": "상품 이미지 (Base64 인코딩)",
                        "bg_prompt": "배경 설명 (예: 'luxury hotel lobby with warm lighting')",
                        "text_content": "광고 텍스트 (예: 'Summer Sale')",
                    },
                    "optional_fields": "자세한 내용은 GET /help/parameters 참조",
                    "returns": {"job_id": "작업 ID (UUID)", "status": "started"},
                    "concurrency": "한 번에 하나의 작업만 처리 (single job policy)",
                },
                "GET /status/{job_id}": {
                    "description": "작업 진행 상태 및 결과 조회",
                    "returns": {
                        "status": "pending | running | completed | failed | stopped",
                        "progress_percent": "0-100 진행률",
                        "current_step": "현재 단계 (step1_background, step2_text, step3_composite)",
                        "step1_result": "배경 합성 이미지 (Base64)",
                        "step2_result": "3D 텍스트 이미지 (Base64)",
                        "final_result": "최종 합성 이미지 (Base64)",
                        "system_metrics": "실시간 CPU/GPU 사용률",
                    },
                    "polling": "2-5초 간격으로 폴링 권장",
                },
                "POST /stop/{job_id}": {
                    "description": "실행 중인 작업 강제 중단",
                    "use_case": "작업이 너무 오래 걸리거나 잘못된 입력으로 시작한 경우",
                },
                "GET /jobs": {
                    "description": "모든 작업 목록 조회",
                    "returns": {
                        "total_jobs": "전체 작업 수",
                        "active_jobs": "실행 중인 작업 수",
                        "jobs": "각 작업의 상태 정보 배열",
                    },
                },
                "DELETE /jobs/{job_id}": {
                    "description": "완료/실패한 작업을 메모리에서 삭제",
                    "note": "실행 중인 작업은 먼저 /stop으로 중단 필요",
                },
            },
            "resources": {
                "GET /fonts": {
                    "description": "사용 가능한 폰트 목록 조회",
                    "returns": {"fonts": ["NanumGothic/NanumGothic.ttf", "..."]},
                    "usage": "font_name 파라미터에 리스트의 값을 그대로 입력",
                },
                "GET /health": {
                    "description": "서버 상태 및 GPU 메트릭 확인",
                    "returns": {
                        "status": "healthy | busy",
                        "active_jobs": "현재 실행 중인 작업 수",
                        "system_metrics": "CPU/RAM/GPU 사용률",
                    },
                    "use_case": "요청 전 서버 가용성 확인",
                },
            },
        },
        "workflow_examples": {
            "basic_workflow": {
                "description": "기본 광고 생성 워크플로우 (전체 파이프라인)",
                "steps": [
                    {
                        "step": 1,
                        "action": "GET /health",
                        "purpose": "서버가 busy 상태가 아닌지 확인",
                    },
                    {"step": 2, "action": "GET /fonts", "purpose": "사용할 폰트 선택"},
                    {
                        "step": 3,
                        "action": "POST /generate",
                        "body": {
                            "product_image": "<base64_image>",
                            "bg_prompt": "modern office with natural lighting",
                            "text_content": "New Product",
                            "font_name": "NanumSquare/NanumSquareB.ttf",
                            "start_step": 1,
                        },
                        "response": {"job_id": "abc-123", "status": "started"},
                    },
                    {
                        "step": 4,
                        "action": "GET /status/abc-123 (2초 간격 폴링)",
                        "purpose": "진행 상태 모니터링",
                    },
                    {
                        "step": 5,
                        "condition": "status == 'completed'",
                        "action": "final_result 필드에서 Base64 이미지 추출 및 저장",
                    },
                    {
                        "step": 6,
                        "action": "DELETE /jobs/abc-123",
                        "purpose": "작업 정보 메모리에서 제거 (선택사항)",
                    },
                ],
            },
            "retry_from_step2": {
                "description": "텍스트만 다시 생성하기 (Step 2부터 재시작)",
                "scenario": "배경은 마음에 드는데 텍스트 스타일만 바꾸고 싶을 때",
                "steps": [
                    {
                        "step": 1,
                        "action": "GET /status/previous-job-id",
                        "purpose": "이전 작업의 step1_result 가져오기",
                    },
                    {
                        "step": 2,
                        "action": "POST /generate",
                        "body": {
                            "start_step": 2,
                            "step1_image": "<step1_result_base64>",
                            "text_content": "Different Text",
                            "text_prompt": "gold metallic text with shadow",
                            "font_name": "NanumGothic/NanumGothic.ttf",
                        },
                    },
                ],
            },
            "composition_only": {
                "description": "합성만 다시 하기 (Step 3만 실행)",
                "scenario": "배경과 텍스트는 그대로 두고 합성 방식만 변경",
                "steps": [
                    {
                        "step": 1,
                        "action": "POST /generate",
                        "body": {
                            "start_step": 3,
                            "step1_image": "<background_base64>",
                            "step2_image": "<text_base64>",
                            "composition_mode": "blend",
                            "text_position": "center",
                        },
                    }
                ],
            },
        },
        "step_system": {
            "description": "3단계 파이프라인 시스템",
            "steps": {
                "step1_background": {
                    "name": "배경 생성 및 합성",
                    "sub_steps": [
                        "segmentation - 상품 누끼 따기 (BiRefNet)",
                        "flux_background_generation - 배경 이미지 생성 (Flux)",
                        "flux_inpaint_injection - 상품 + 배경 합성 (Flux Inpaint)",
                    ],
                    "estimated_time": "80초",
                    "output": "step1_result (배경에 상품이 합성된 이미지)",
                },
                "step2_text": {
                    "name": "3D 텍스트 생성",
                    "sub_steps": [
                        "text_canvas_preparation - 텍스트 캔버스 생성",
                        "canny_edge_detection - 텍스트 윤곽선 추출",
                        "sdxl_text_generation - 3D 텍스트 생성 (SDXL ControlNet)",
                        "text_background_removal - 텍스트 배경 제거 (BiRefNet)",
                    ],
                    "estimated_time": "35초",
                    "output": "step2_result (3D 텍스트 이미지)",
                },
                "step3_composite": {
                    "name": "최종 합성",
                    "sub_steps": [
                        "intelligent_composition - 배경 + 텍스트 합성 (Flux Inpaint)"
                    ],
                    "estimated_time": "5초",
                    "output": "final_result (최종 광고 이미지)",
                },
            },
            "step_control": {
                "start_step": {
                    "1": "전체 파이프라인 실행 (기본값)",
                    "2": "텍스트만 다시 생성 (step1_image 필요)",
                    "3": "합성만 다시 실행 (step1_image, step2_image 필요)",
                },
                "stop_step": {
                    "description": "파이프라인을 중단할 단계 (선택사항)",
                    "1": "Step 1까지만 실행 (배경 생성만)",
                    "2": "Step 2까지만 실행 (배경 + 텍스트 생성)",
                    "3": "Step 3까지 실행 (전체, 기본값)",
                    "None": "start_step부터 끝까지 실행 (기본 동작)",
                    "constraint": "stop_step >= start_step 이어야 함",
                },
                "usage_examples": {
                    "background_only": "start_step=1, stop_step=1 → 배경만 생성",
                    "text_generation": "start_step=1, stop_step=2 → 배경 + 텍스트 생성 (합성 없음)",
                    "full_pipeline": "start_step=1, stop_step=3 (또는 None) → 전체 실행",
                    "retry_text": "start_step=2, stop_step=2 → 텍스트만 재생성",
                },
            },
        },
        "error_handling": {
            "503_service_unavailable": {
                "meaning": "다른 작업이 실행 중임 (단일 작업 정책)",
                "response_headers": "Retry-After: <seconds>",
                "action": "헤더의 시간만큼 대기 후 재시도",
            },
            "404_not_found": {
                "meaning": "존재하지 않는 job_id",
                "action": "GET /jobs로 활성 작업 목록 확인",
            },
            "400_bad_request": {
                "meaning": "잘못된 파라미터 또는 실행 중인 작업 삭제 시도",
                "action": "에러 메시지 확인 및 파라미터 수정",
            },
            "status_failed": {
                "meaning": "작업 실행 중 오류 발생",
                "response": "GET /status/{job_id}의 message 필드에 에러 정보 포함",
                "action": "파라미터 확인 후 새 작업 시작",
            },
        },
        "best_practices": {
            "polling": "2-5초 간격으로 /status 폴링 (너무 짧으면 서버 부하)",
            "health_check": "요청 전 /health로 서버 상태 확인",
            "job_cleanup": "완료된 작업은 DELETE /jobs/{job_id}로 정리",
            "error_retry": "실패 시 파라미터 조정 후 재시도",
            "step_reuse": "중간 결과물(step1_result, step2_result)을 저장하여 재사용",
            "gpu_monitoring": "/health의 system_metrics로 GPU 메모리 확인",
        },
        "additional_resources": {
            "parameter_reference": "GET /help/parameters - 모든 파라미터 상세 설명",
            "examples": "GET /help/examples - 실전 사용 예시",
            "openapi_docs": "/docs - Swagger UI 인터랙티브 문서",
            "openapi_schema": "/openapi.json - OpenAPI 3.0 스키마",
        },
    }
