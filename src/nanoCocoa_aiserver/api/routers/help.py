"""
help.py
API 사용법 가이드 및 파라미터 레퍼런스 엔드포인트
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from FastAPI import APIRouter


router = APIRouter()


@router.get(
    "/help",
    summary="전체 API 사용 가이드 (API Usage Guide)",
    response_description="API 사용법과 워크플로우 안내"
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
            "description": "상품 이미지 + 텍스트 → AI 광고 이미지 생성 서버 (Nvidia L4 GPU 최적화)"
        },
        "quick_start": {
            "step1": "GET /health - 서버 상태 확인 (선택사항)",
            "step2": "GET /fonts - 사용 가능한 폰트 목록 조회",
            "step3": "POST /generate - 광고 생성 작업 시작 (job_id 반환)",
            "step4": "GET /status/{job_id} - 작업 진행 상태 및 결과 조회 (폴링)",
            "step5": "작업 완료 시 final_result 필드에서 Base64 이미지 다운로드"
        },
        "main_endpoints": {
            "generation": {
                "POST /generate": {
                    "description": "새로운 광고 생성 작업 시작 (비동기)",
                    "required_fields": {
                        "input_image": "상품 이미지 (Base64 인코딩)",
                        "bg_prompt": "배경 설명 (예: 'luxury hotel lobby with warm lighting')",
                        "text_content": "광고 텍스트 (예: 'Summer Sale')"
                    },
                    "optional_fields": "자세한 내용은 GET /help/parameters 참조",
                    "returns": {"job_id": "작업 ID (UUID)", "status": "started"},
                    "concurrency": "한 번에 하나의 작업만 처리 (single job policy)"
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
                        "system_metrics": "실시간 CPU/GPU 사용률"
                    },
                    "polling": "2-5초 간격으로 폴링 권장"
                },
                "POST /stop/{job_id}": {
                    "description": "실행 중인 작업 강제 중단",
                    "use_case": "작업이 너무 오래 걸리거나 잘못된 입력으로 시작한 경우"
                },
                "GET /jobs": {
                    "description": "모든 작업 목록 조회",
                    "returns": {
                        "total_jobs": "전체 작업 수",
                        "active_jobs": "실행 중인 작업 수",
                        "jobs": "각 작업의 상태 정보 배열"
                    }
                },
                "DELETE /jobs/{job_id}": {
                    "description": "완료/실패한 작업을 메모리에서 삭제",
                    "note": "실행 중인 작업은 먼저 /stop으로 중단 필요"
                }
            },
            "resources": {
                "GET /fonts": {
                    "description": "사용 가능한 폰트 목록 조회",
                    "returns": {"fonts": ["NanumGothic/NanumGothic.ttf", "..."]},
                    "usage": "font_name 파라미터에 리스트의 값을 그대로 입력"
                },
                "GET /health": {
                    "description": "서버 상태 및 GPU 메트릭 확인",
                    "returns": {
                        "status": "healthy | busy",
                        "active_jobs": "현재 실행 중인 작업 수",
                        "system_metrics": "CPU/RAM/GPU 사용률"
                    },
                    "use_case": "요청 전 서버 가용성 확인"
                }
            }
        },
        "workflow_examples": {
            "basic_workflow": {
                "description": "기본 광고 생성 워크플로우 (전체 파이프라인)",
                "steps": [
                    {
                        "step": 1,
                        "action": "GET /health",
                        "purpose": "서버가 busy 상태가 아닌지 확인"
                    },
                    {
                        "step": 2,
                        "action": "GET /fonts",
                        "purpose": "사용할 폰트 선택"
                    },
                    {
                        "step": 3,
                        "action": "POST /generate",
                        "body": {
                            "input_image": "<base64_image>",
                            "bg_prompt": "modern office with natural lighting",
                            "text_content": "New Product",
                            "font_name": "NanumSquare/NanumSquareB.ttf",
                            "start_step": 1
                        },
                        "response": {"job_id": "abc-123", "status": "started"}
                    },
                    {
                        "step": 4,
                        "action": "GET /status/abc-123 (2초 간격 폴링)",
                        "purpose": "진행 상태 모니터링"
                    },
                    {
                        "step": 5,
                        "condition": "status == 'completed'",
                        "action": "final_result 필드에서 Base64 이미지 추출 및 저장"
                    },
                    {
                        "step": 6,
                        "action": "DELETE /jobs/abc-123",
                        "purpose": "작업 정보 메모리에서 제거 (선택사항)"
                    }
                ]
            },
            "retry_from_step2": {
                "description": "텍스트만 다시 생성하기 (Step 2부터 재시작)",
                "scenario": "배경은 마음에 드는데 텍스트 스타일만 바꾸고 싶을 때",
                "steps": [
                    {
                        "step": 1,
                        "action": "GET /status/previous-job-id",
                        "purpose": "이전 작업의 step1_result 가져오기"
                    },
                    {
                        "step": 2,
                        "action": "POST /generate",
                        "body": {
                            "start_step": 2,
                            "step1_image": "<step1_result_base64>",
                            "text_content": "Different Text",
                            "text_model_prompt": "gold metallic text with shadow",
                            "font_name": "NanumGothic/NanumGothic.ttf"
                        }
                    }
                ]
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
                            "text_position": "center"
                        }
                    }
                ]
            }
        },
        "step_system": {
            "description": "3단계 파이프라인 시스템",
            "steps": {
                "step1_background": {
                    "name": "배경 생성 및 합성",
                    "sub_steps": [
                        "segmentation - 상품 누끼 따기 (BiRefNet)",
                        "flux_background_generation - 배경 이미지 생성 (Flux)",
                        "flux_inpaint_injection - 상품 + 배경 합성 (Flux Inpaint)"
                    ],
                    "estimated_time": "80초",
                    "output": "step1_result (배경에 상품이 합성된 이미지)"
                },
                "step2_text": {
                    "name": "3D 텍스트 생성",
                    "sub_steps": [
                        "text_canvas_preparation - 텍스트 캔버스 생성",
                        "canny_edge_detection - 텍스트 윤곽선 추출",
                        "sdxl_text_generation - 3D 텍스트 생성 (SDXL ControlNet)",
                        "text_background_removal - 텍스트 배경 제거 (BiRefNet)"
                    ],
                    "estimated_time": "35초",
                    "output": "step2_result (3D 텍스트 이미지)"
                },
                "step3_composite": {
                    "name": "최종 합성",
                    "sub_steps": [
                        "intelligent_composition - 배경 + 텍스트 합성 (Flux Inpaint)"
                    ],
                    "estimated_time": "5초",
                    "output": "final_result (최종 광고 이미지)"
                }
            },
            "step_control": {
                "start_step": {
                    "1": "전체 파이프라인 실행 (기본값)",
                    "2": "텍스트만 다시 생성 (step1_image 필요)",
                    "3": "합성만 다시 실행 (step1_image, step2_image 필요)"
                }
            }
        },
        "error_handling": {
            "503_service_unavailable": {
                "meaning": "다른 작업이 실행 중임 (단일 작업 정책)",
                "response_headers": "Retry-After: <seconds>",
                "action": "헤더의 시간만큼 대기 후 재시도"
            },
            "404_not_found": {
                "meaning": "존재하지 않는 job_id",
                "action": "GET /jobs로 활성 작업 목록 확인"
            },
            "400_bad_request": {
                "meaning": "잘못된 파라미터 또는 실행 중인 작업 삭제 시도",
                "action": "에러 메시지 확인 및 파라미터 수정"
            },
            "status_failed": {
                "meaning": "작업 실행 중 오류 발생",
                "response": "GET /status/{job_id}의 message 필드에 에러 정보 포함",
                "action": "파라미터 확인 후 새 작업 시작"
            }
        },
        "best_practices": {
            "polling": "2-5초 간격으로 /status 폴링 (너무 짧으면 서버 부하)",
            "health_check": "요청 전 /health로 서버 상태 확인",
            "job_cleanup": "완료된 작업은 DELETE /jobs/{job_id}로 정리",
            "error_retry": "실패 시 파라미터 조정 후 재시도",
            "step_reuse": "중간 결과물(step1_result, step2_result)을 저장하여 재사용",
            "gpu_monitoring": "/health의 system_metrics로 GPU 메모리 확인"
        },
        "additional_resources": {
            "parameter_reference": "GET /help/parameters - 모든 파라미터 상세 설명",
            "openapi_docs": "/docs - Swagger UI 인터랙티브 문서",
            "openapi_schema": "/openapi.json - OpenAPI 3.0 스키마"
        }
    }


@router.get(
    "/help/parameters",
    summary="파라미터 레퍼런스 (Parameter Reference)",
    response_description="모든 요청 파라미터의 상세 설명"
)
async def get_parameters_help():
    """
    POST /generate 엔드포인트의 모든 파라미터에 대한 상세 레퍼런스를 제공합니다.

    LLM이나 개발자가 정확한 파라미터를 구성할 수 있도록 각 필드의 역할, 타입, 기본값, 예시를 포함합니다.
    """
    return {
        "endpoint": "POST /generate",
        "description": "광고 생성 요청의 모든 파라미터 레퍼런스",
        "parameters": {
            "step_control": {
                "start_step": {
                    "type": "integer",
                    "required": False,
                    "default": 1,
                    "allowed_values": [1, 2, 3],
                    "description": "파이프라인 시작 단계 선택",
                    "usage": {
                        "1": "전체 파이프라인 (배경 생성 → 텍스트 생성 → 합성)",
                        "2": "텍스트 생성부터 시작 (step1_image 필요)",
                        "3": "합성만 실행 (step1_image, step2_image 필요)"
                    },
                    "example": 1
                }
            },
            "common": {
                "text_content": {
                    "type": "string | null",
                    "required": False,
                    "default": None,
                    "description": "광고에 표시할 텍스트 내용",
                    "note": "None 또는 빈 문자열이면 배경만 생성",
                    "example": "Summer Sale 50% OFF"
                }
            },
            "step1_background": {
                "description": "Step 1 (배경 생성) 관련 파라미터",
                "input_image": {
                    "type": "string (Base64)",
                    "required": True,
                    "description": "상품 이미지 (Base64 인코딩)",
                    "format": "data:image/png;base64,iVBORw0KGgo... 형식 또는 순수 Base64 문자열",
                    "recommended_size": "512x512 ~ 1024x1024",
                    "example": "iVBORw0KGgoAAAANSUhEUgAA..."
                },
                "bg_prompt": {
                    "type": "string",
                    "required": True,
                    "default": "",
                    "description": "생성할 배경 이미지 설명 (영문 권장)",
                    "tips": [
                        "구체적인 장소, 분위기, 조명 포함",
                        "예: 'luxury hotel lobby with warm lighting and marble floor'",
                        "예: 'minimalist white studio with soft shadows'",
                        "예: 'outdoor garden with flowers and sunlight'"
                    ],
                    "example": "modern office workspace with natural light and plants"
                },
                "bg_negative_prompt": {
                    "type": "string",
                    "required": False,
                    "default": "",
                    "description": "배경에서 제외할 요소",
                    "tips": [
                        "생성하고 싶지 않은 물체나 스타일 명시",
                        "예: 'dark, messy, cluttered, people, text'"
                    ],
                    "example": "blurry, low quality, dark, cluttered"
                },
                "bg_composition_prompt": {
                    "type": "string | null",
                    "required": False,
                    "default": None,
                    "description": "상품과 배경의 합성 방식 설명",
                    "example": "product placed on the table naturally"
                },
                "bg_composition_negative_prompt": {
                    "type": "string | null",
                    "required": False,
                    "default": None,
                    "description": "합성 시 제외할 요소",
                    "example": "floating, unnatural placement"
                }
            },
            "step2_text": {
                "description": "Step 2 (텍스트 생성) 관련 파라미터",
                "step1_image": {
                    "type": "string (Base64) | null",
                    "required": "start_step >= 2일 때 필수",
                    "description": "Step 1 결과물 또는 미리 준비된 배경 이미지",
                    "source": "GET /status/{job_id}의 step1_result 필드",
                    "example": "iVBORw0KGgoAAAANSUhEUgAA..."
                },
                "text_model_prompt": {
                    "type": "string",
                    "required": False,
                    "default": "",
                    "description": "3D 텍스트 스타일 설명",
                    "tips": [
                        "재질, 효과, 색상 포함",
                        "예: 'gold metallic text with glossy surface'",
                        "예: 'neon glowing text with pink and blue colors'",
                        "예: 'stone carved text with rough texture'",
                        "예: 'chrome reflective text with mirror finish'"
                    ],
                    "example": "silver metallic 3D text with shadow and reflection"
                },
                "negative_prompt": {
                    "type": "string",
                    "required": False,
                    "default": "",
                    "description": "텍스트 생성 시 제외할 요소",
                    "example": "flat, 2d, blurry, distorted"
                },
                "font_name": {
                    "type": "string | null",
                    "required": False,
                    "default": None,
                    "description": "사용할 폰트 파일 경로",
                    "source": "GET /fonts 엔드포인트에서 조회",
                    "fallback": "None이면 서버 기본 폰트 사용",
                    "example": "NanumSquare/NanumSquareB.ttf"
                }
            },
            "step3_composition": {
                "description": "Step 3 (최종 합성) 관련 파라미터",
                "step2_image": {
                    "type": "string (Base64) | null",
                    "required": "start_step == 3일 때 필수",
                    "description": "Step 2 결과물 또는 미리 준비된 텍스트 이미지",
                    "source": "GET /status/{job_id}의 step2_result 필드",
                    "example": "iVBORw0KGgoAAAANSUhEUgAA..."
                },
                "composition_mode": {
                    "type": "string",
                    "required": False,
                    "default": "overlay",
                    "allowed_values": ["overlay", "blend", "behind"],
                    "description": "텍스트와 배경의 합성 방식",
                    "modes": {
                        "overlay": "텍스트를 배경 위에 겹침 (기본값, 가장 자연스러움)",
                        "blend": "텍스트를 배경에 자연스럽게 블렌딩",
                        "behind": "텍스트를 배경 뒤에 배치"
                    },
                    "example": "overlay"
                },
                "text_position": {
                    "type": "string",
                    "required": False,
                    "default": "auto",
                    "allowed_values": ["top", "center", "bottom", "auto"],
                    "description": "텍스트 배치 위치",
                    "positions": {
                        "top": "상단 배치",
                        "center": "중앙 배치",
                        "bottom": "하단 배치",
                        "auto": "자동 배치 (공간 분석)"
                    },
                    "example": "center"
                },
                "composition_prompt": {
                    "type": "string | null",
                    "required": False,
                    "default": None,
                    "description": "합성 시 추가 지시사항",
                    "example": "text integrated naturally into the scene"
                },
                "composition_negative_prompt": {
                    "type": "string | null",
                    "required": False,
                    "default": None,
                    "description": "합성 시 제외할 요소",
                    "example": "text floating unnaturally"
                },
                "composition_strength": {
                    "type": "float",
                    "required": False,
                    "default": 0.4,
                    "range": "0.0 ~ 1.0",
                    "description": "합성 변형 강도 (낮을수록 원본 유지)",
                    "guide": {
                        "0.2-0.3": "미세한 조정",
                        "0.4-0.5": "균형 잡힌 합성 (권장)",
                        "0.6-0.8": "강한 변형"
                    },
                    "example": 0.4
                },
                "composition_steps": {
                    "type": "integer",
                    "required": False,
                    "default": 28,
                    "range": "10 ~ 50",
                    "description": "합성 추론 스텝 수 (높을수록 품질 향상, 시간 증가)",
                    "guide": {
                        "10-20": "빠른 생성 (품질 낮음)",
                        "25-30": "균형 (권장)",
                        "35-50": "고품질 (느림)"
                    },
                    "example": 28
                },
                "composition_guidance_scale": {
                    "type": "float",
                    "required": False,
                    "default": 3.5,
                    "range": "1.0 ~ 7.0",
                    "description": "프롬프트 준수 강도 (높을수록 프롬프트에 충실)",
                    "guide": {
                        "1.0-2.0": "자유로운 생성",
                        "3.0-4.0": "균형 (권장)",
                        "5.0-7.0": "프롬프트 엄격 준수"
                    },
                    "example": 3.5
                }
            },
            "advanced": {
                "strength": {
                    "type": "float",
                    "required": False,
                    "default": 0.6,
                    "range": "0.0 ~ 1.0",
                    "description": "Step 1, 2의 이미지 변형 강도",
                    "guide": "낮을수록 원본 이미지 유지, 높을수록 새로운 이미지 생성",
                    "example": 0.6
                },
                "guidance_scale": {
                    "type": "float",
                    "required": False,
                    "default": 3.5,
                    "range": "1.0 ~ 20.0",
                    "description": "Step 1, 2의 프롬프트 준수 강도",
                    "guide": "높을수록 프롬프트에 충실하지만 과도하면 부자연스러움",
                    "example": 3.5
                },
                "seed": {
                    "type": "integer | null",
                    "required": False,
                    "default": None,
                    "description": "랜덤 시드 (재현성을 위해 사용)",
                    "note": "같은 시드와 파라미터로 동일한 결과 생성 가능",
                    "example": 42
                },
                "test_mode": {
                    "type": "boolean",
                    "required": False,
                    "default": False,
                    "description": "테스트 모드 (AI 모델 없이 더미 이미지 반환)",
                    "use_case": "API 구조 테스트, GPU 없는 환경에서 테스트",
                    "example": False
                }
            }
        },
        "example_requests": {
            "basic_full_pipeline": {
                "description": "기본 전체 파이프라인 실행",
                "request": {
                    "input_image": "<base64_product_image>",
                    "bg_prompt": "luxury hotel lobby with warm lighting",
                    "text_content": "Grand Opening",
                    "text_model_prompt": "gold metallic 3D text",
                    "font_name": "NanumSquare/NanumSquareB.ttf",
                    "start_step": 1
                }
            },
            "advanced_customization": {
                "description": "고급 커스터마이징 예시",
                "request": {
                    "input_image": "<base64_product_image>",
                    "bg_prompt": "modern minimalist studio with soft shadows",
                    "bg_negative_prompt": "cluttered, dark, people, text",
                    "text_content": "NEW COLLECTION",
                    "text_model_prompt": "chrome reflective text with mirror finish and glow",
                    "negative_prompt": "flat, 2d, blurry, distorted",
                    "font_name": "NanumGothic/NanumGothic.ttf",
                    "composition_mode": "overlay",
                    "text_position": "center",
                    "strength": 0.7,
                    "guidance_scale": 4.0,
                    "composition_strength": 0.5,
                    "composition_steps": 30,
                    "seed": 12345,
                    "start_step": 1
                }
            },
            "retry_text_only": {
                "description": "텍스트만 다시 생성 (Step 2부터)",
                "request": {
                    "step1_image": "<previous_step1_result_base64>",
                    "text_content": "Different Text",
                    "text_model_prompt": "neon glowing text with pink and blue",
                    "font_name": "NanumSquare/NanumSquareB.ttf",
                    "start_step": 2
                }
            },
            "recompose_only": {
                "description": "합성만 다시 실행 (Step 3만)",
                "request": {
                    "step1_image": "<background_base64>",
                    "step2_image": "<text_base64>",
                    "composition_mode": "blend",
                    "text_position": "top",
                    "composition_strength": 0.3,
                    "start_step": 3
                }
            }
        },
        "tips_for_llms": {
            "understanding_base64": "이미지는 Base64 문자열로 인코딩되어야 합니다. 사용자가 이미지 파일을 제공하면 Base64로 변환 후 요청하세요.",
            "polling_strategy": "작업 시작 후 2-5초 간격으로 GET /status/{job_id}를 호출하여 status가 'completed' 또는 'failed'가 될 때까지 폴링하세요.",
            "error_handling": "503 응답 시 Retry-After 헤더를 확인하여 대기 시간을 사용자에게 안내하세요.",
            "step_reuse": "사용자가 특정 부분만 수정하고 싶어하면 이전 결과의 step1_result 또는 step2_result를 재사용하세요.",
            "prompt_engineering": "배경 및 텍스트 프롬프트는 영문이 더 정확합니다. 사용자가 한글로 입력하면 영문으로 번역하여 요청하세요.",
            "parameter_defaults": "대부분의 파라미터는 기본값이 잘 설정되어 있으므로, 사용자가 특별히 요청하지 않으면 기본값을 사용하세요."
        }
    }


@router.get(
    "/help/examples",
    summary="실전 사용 예시 (Usage Examples)",
    response_description="다양한 시나리오별 API 사용 예시"
)
async def get_examples():
    """
    실제 사용 시나리오별 API 호출 예시를 제공합니다.

    각 예시는 cURL, Python, JavaScript 코드와 함께 제공됩니다.
    """
    return {
        "examples": {
            "example1_basic_generation": {
                "scenario": "화장품 광고 이미지 생성",
                "description": "화장품 제품 이미지를 받아서 럭셔리한 배경에 'Premium Beauty' 텍스트를 추가",
                "workflow": [
                    {
                        "step": "1. 서버 상태 확인",
                        "curl": 'curl -X GET "http://localhost:8000/health"',
                        "python": 'response = requests.get("http://localhost:8000/health")',
                        "response": {"status": "healthy", "active_jobs": 0}
                    },
                    {
                        "step": "2. 폰트 목록 조회",
                        "curl": 'curl -X GET "http://localhost:8000/fonts"',
                        "python": 'fonts = requests.get("http://localhost:8000/fonts").json()',
                        "response": {"fonts": ["NanumGothic/NanumGothic.ttf", "NanumSquare/NanumSquareB.ttf"]}
                    },
                    {
                        "step": "3. 생성 작업 시작",
                        "curl": '''curl -X POST "http://localhost:8000/generate" \\
  -H "Content-Type: application/json" \\
  -d '{
    "input_image": "<base64_cosmetic_product>",
    "bg_prompt": "luxury marble bathroom with gold accents and soft lighting",
    "text_content": "Premium Beauty",
    "text_model_prompt": "elegant gold metallic text with subtle glow",
    "font_name": "NanumSquare/NanumSquareB.ttf"
  }' ''',
                        "python": '''import requests
import base64

with open("cosmetic_product.png", "rb") as f:
    image_b64 = base64.b64encode(f.read()).decode()

response = requests.post("http://localhost:8000/generate", json={
    "input_image": image_b64,
    "bg_prompt": "luxury marble bathroom with gold accents and soft lighting",
    "text_content": "Premium Beauty",
    "text_model_prompt": "elegant gold metallic text with subtle glow",
    "font_name": "NanumSquare/NanumSquareB.ttf"
})

job_id = response.json()["job_id"]''',
                        "response": {"job_id": "abc-123-def", "status": "started"}
                    },
                    {
                        "step": "4. 진행 상태 폴링",
                        "python": '''import time

while True:
    status = requests.get(f"http://localhost:8000/status/{job_id}").json()
    print(f"Progress: {status['progress_percent']}% - {status['message']}")

    if status['status'] in ('completed', 'failed', 'stopped'):
        break

    time.sleep(3)

if status['status'] == 'completed':
    final_image_b64 = status['final_result']
    # Base64 디코딩 및 저장
    with open("final_ad.png", "wb") as f:
        f.write(base64.b64decode(final_image_b64))'''
                    }
                ]
            },
            "example2_text_retry": {
                "scenario": "텍스트 스타일 변경",
                "description": "배경은 그대로 두고 텍스트 스타일만 변경",
                "python": '''# 1. 이전 작업의 배경 이미지 가져오기
previous_status = requests.get(f"http://localhost:8000/status/{previous_job_id}").json()
step1_result = previous_status['step1_result']

# 2. 새로운 텍스트 스타일로 재생성
new_response = requests.post("http://localhost:8000/generate", json={
    "start_step": 2,
    "step1_image": step1_result,
    "text_content": "Premium Beauty",
    "text_model_prompt": "chrome reflective text with rainbow gradient",
    "font_name": "NanumGothic/NanumGothic.ttf"
})

new_job_id = new_response.json()["job_id"]'''
            },
            "example3_batch_processing": {
                "scenario": "여러 텍스트 버전 생성",
                "description": "같은 배경에 다른 텍스트를 여러 개 생성 (순차 처리)",
                "python": '''import time

base_job = requests.post("http://localhost:8000/generate", json={
    "input_image": product_image_b64,
    "bg_prompt": "modern office workspace",
    "text_content": ""  # 배경만 생성
}).json()

# 배경 생성 완료 대기
while True:
    status = requests.get(f"http://localhost:8000/status/{base_job['job_id']}").json()
    if status['status'] == 'completed':
        break
    time.sleep(3)

background = status['step1_result']

# 여러 텍스트 버전 생성
texts = [
    {"text": "Sale 50%", "style": "bold red text with shadow"},
    {"text": "New Arrival", "style": "elegant gold text"},
    {"text": "Limited Edition", "style": "silver metallic text"}
]

results = []
for text_config in texts:
    # 서버가 사용 가능할 때까지 대기
    while True:
        health = requests.get("http://localhost:8000/health").json()
        if health['status'] == 'healthy':
            break
        time.sleep(5)

    # 텍스트 생성 요청
    job = requests.post("http://localhost:8000/generate", json={
        "start_step": 2,
        "step1_image": background,
        "text_content": text_config["text"],
        "text_model_prompt": text_config["style"]
    }).json()

    # 완료 대기
    while True:
        status = requests.get(f"http://localhost:8000/status/{job['job_id']}").json()
        if status['status'] == 'completed':
            results.append(status['final_result'])
            break
        time.sleep(3)'''
            },
            "example4_error_handling": {
                "scenario": "에러 처리 및 재시도",
                "python": '''import time

def generate_with_retry(request_data, max_retries=3):
    """에러 처리 및 재시도 로직"""
    for attempt in range(max_retries):
        try:
            # 서버 상태 확인
            health = requests.get("http://localhost:8000/health").json()

            if health['status'] == 'busy':
                wait_time = health.get('active_jobs', 1) * 120  # 예상 대기 시간
                print(f"Server busy. Waiting {wait_time}s...")
                time.sleep(wait_time)
                continue

            # 생성 요청
            response = requests.post("http://localhost:8000/generate", json=request_data)

            if response.status_code == 503:
                retry_after = int(response.headers.get('Retry-After', 30))
                print(f"503 Error. Retry after {retry_after}s")
                time.sleep(retry_after)
                continue

            response.raise_for_status()
            job_id = response.json()["job_id"]

            # 상태 폴링
            while True:
                status = requests.get(f"http://localhost:8000/status/{job_id}").json()

                if status['status'] == 'completed':
                    return status['final_result']

                elif status['status'] == 'failed':
                    print(f"Job failed: {status['message']}")
                    if attempt < max_retries - 1:
                        print(f"Retrying... (attempt {attempt + 2}/{max_retries})")
                        break
                    else:
                        raise Exception(f"Job failed after {max_retries} attempts")

                time.sleep(3)

        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            if attempt < max_retries - 1:
                time.sleep(10)
            else:
                raise

    raise Exception("Max retries exceeded")

# 사용 예시
try:
    final_image = generate_with_retry({
        "input_image": product_b64,
        "bg_prompt": "luxury background",
        "text_content": "Special Offer"
    })
    print("Generation successful!")
except Exception as e:
    print(f"Generation failed: {e}")'''
            }
        },
        "llm_integration_guide": {
            "description": "LLM이 이 API를 사용할 때 권장하는 패턴",
            "pattern": [
                "1. 사용자 요청 분석: 배경, 텍스트, 스타일 요구사항 파악",
                "2. 영문 프롬프트 생성: 한글 입력 시 영문으로 번역",
                "3. GET /health로 서버 가용성 확인",
                "4. 필요시 GET /fonts로 적절한 폰트 선택",
                "5. POST /generate로 작업 시작",
                "6. GET /status/{job_id}를 폴링하여 진행 상황 사용자에게 업데이트",
                "7. 완료 시 final_result 제공",
                "8. 사용자가 수정 요청하면 적절한 start_step으로 재시도",
                "9. DELETE /jobs/{job_id}로 완료된 작업 정리"
            ],
            "best_practices": [
                "프롬프트는 구체적이고 명확하게 작성",
                "progress_percent와 message를 사용자에게 실시간 전달",
                "에러 발생 시 message 필드를 확인하여 원인 파악",
                "step1_result, step2_result를 저장하여 재사용",
                "사용자가 만족할 때까지 파라미터 조정하여 재시도"
            ]
        }
    }
