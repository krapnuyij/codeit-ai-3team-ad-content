"""
help_parameters.py
파라미터 레퍼런스 엔드포인트
"""

from fastapi import APIRouter

router = APIRouter()


@router.get(
    "/help/parameters",
    summary="파라미터 레퍼런스 (Parameter Reference)",
    response_description="모든 요청 파라미터의 상세 설명",
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
                        "3": "합성만 실행 (step1_image, step2_image 필요)",
                    },
                    "example": 1,
                },
                "stop_step": {
                    "type": "integer | null",
                    "required": False,
                    "default": None,
                    "allowed_values": [1, 2, 3, None],
                    "description": "파이프라인을 중단할 단계 선택 (선택사항)",
                    "usage": {
                        "1": "Step 1까지만 실행 (배경 생성만, Step 2/3 건너뜀)",
                        "2": "Step 2까지만 실행 (배경 + 텍스트, Step 3 건너뜀)",
                        "3": "Step 3까지 실행 (전체 파이프라인)",
                        "None": "start_step부터 끝까지 실행 (기본 동작)",
                    },
                    "constraint": "stop_step >= start_step 이어야 함",
                    "use_cases": {
                        "background_only": "배경만 생성하고 싶을 때: stop_step=1",
                        "preview_steps": "중간 단계 결과만 확인하고 싶을 때",
                        "partial_pipeline": "특정 단계까지만 실행 후 파라미터 조정",
                    },
                    "example": 2,
                },
            },
            "common": {
                "text_content": {
                    "type": "string | null",
                    "required": False,
                    "default": None,
                    "description": "광고에 표시할 텍스트 내용",
                    "note": "None 또는 빈 문자열이면 배경만 생성",
                    "example": "Summer Sale 50% OFF",
                }
            },
            "step1_background": {
                "description": "Step 1 (배경 생성) 관련 파라미터",
                "product_image": {
                    "type": "string (Base64)",
                    "required": False,
                    "description": "상품 이미지 (Base64 인코딩)",
                    "format": "data:image/png;base64,iVBORw0KGgo... 형식 또는 순수 Base64 문자열",
                    "recommended_size": "512x512 ~ 1024x1024",
                    "example": "iVBORw0KGgoAAAANSUhEUgAA...",
                },
                "bg_prompt": {
                    "type": "string",
                    "required": "product_image = None 일 때 필수",
                    "default": "",
                    "description": "생성할 배경 이미지 설명 (영문 권장)",
                    "tips": [
                        "구체적인 장소, 분위기, 조명 포함",
                        "예: 'luxury hotel lobby with warm lighting and marble floor'",
                        "예: 'minimalist white studio with soft shadows'",
                        "예: 'outdoor garden with flowers and sunlight'",
                    ],
                    "example": "modern office workspace with natural light and plants",
                },
                "bg_negative_prompt": {
                    "type": "string",
                    "required": False,
                    "default": "",
                    "description": "배경에서 제외할 요소",
                    "tips": [
                        "생성하고 싶지 않은 물체나 스타일 명시",
                        "예: 'dark, messy, cluttered, people, text'",
                    ],
                    "example": "blurry, low quality, dark, cluttered",
                },
                "bg_composition_prompt": {
                    "type": "string | null",
                    "required": False,
                    "default": None,
                    "description": "상품과 배경의 합성 방식 설명",
                    "example": "product placed on the table naturally",
                },
                "bg_composition_negative_prompt": {
                    "type": "string | null",
                    "required": False,
                    "default": None,
                    "description": "합성 시 제외할 요소",
                    "example": "floating, unnatural placement",
                },
            },
            "step2_text": {
                "description": "Step 2 (텍스트 생성) 관련 파라미터",
                "step1_image": {
                    "type": "string (Base64) | null",
                    "required": "start_step >= 2일 때 필수",
                    "description": "Step 1 결과물 또는 미리 준비된 배경 이미지",
                    "source": "GET /status/{job_id}의 step1_result 필드",
                    "example": "iVBORw0KGgoAAAANSUhEUgAA...",
                },
                "text_prompt": {
                    "type": "string",
                    "required": False,
                    "default": "",
                    "description": "3D 텍스트 스타일 설명",
                    "tips": [
                        "재질, 효과, 색상 포함",
                        "예: 'gold metallic text with glossy surface'",
                        "예: 'neon glowing text with pink and blue colors'",
                        "예: 'stone carved text with rough texture'",
                        "예: 'chrome reflective text with mirror finish'",
                    ],
                    "example": "silver metallic 3D text with shadow and reflection",
                },
                "text_negative_prompt": {
                    "type": "string",
                    "required": False,
                    "default": "",
                    "description": "텍스트 생성 시 제외할 요소",
                    "example": "flat, 2d, blurry, distorted, unreadable text",
                },
                "font_name": {
                    "type": "string | null",
                    "required": False,
                    "default": None,
                    "description": "사용할 폰트 파일 경로",
                    "source": "GET /fonts 엔드포인트에서 조회",
                    "fallback": "None이면 서버 기본 폰트 사용",
                    "example": "NanumSquare/NanumSquareB.ttf",
                },
            },
            "step3_composition": {
                "description": "Step 3 (최종 합성) 관련 파라미터",
                "step2_image": {
                    "type": "string (Base64) | null",
                    "required": "start_step == 3일 때 필수",
                    "description": "Step 2 결과물 또는 미리 준비된 텍스트 이미지",
                    "source": "GET /status/{job_id}의 step2_result 필드",
                    "example": "iVBORw0KGgoAAAANSUhEUgAA...",
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
                        "behind": "텍스트를 배경 뒤에 배치",
                    },
                    "example": "overlay",
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
                        "auto": "자동 배치 (공간 분석)",
                    },
                    "example": "center",
                },
                "composition_prompt": {
                    "type": "string | null",
                    "required": False,
                    "default": None,
                    "description": "합성 시 추가 지시사항",
                    "example": "text integrated naturally into the scene",
                },
                "composition_negative_prompt": {
                    "type": "string | null",
                    "required": False,
                    "default": None,
                    "description": "합성 시 제외할 요소",
                    "example": "text floating unnaturally",
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
                        "0.6-0.8": "강한 변형",
                    },
                    "example": 0.4,
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
                        "35-50": "고품질 (느림)",
                    },
                    "example": 28,
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
                        "5.0-7.0": "프롬프트 엄격 준수",
                    },
                    "example": 3.5,
                },
            },
            "advanced": {
                "strength": {
                    "type": "float",
                    "required": False,
                    "default": 0.6,
                    "range": "0.0 ~ 1.0",
                    "description": "Step 1, 2의 이미지 변형 강도",
                    "guide": "낮을수록 원본 이미지 유지, 높을수록 새로운 이미지 생성",
                    "example": 0.6,
                },
                "guidance_scale": {
                    "type": "float",
                    "required": False,
                    "default": 3.5,
                    "range": "1.0 ~ 20.0",
                    "description": "Step 1, 2의 프롬프트 준수 강도",
                    "guide": "높을수록 프롬프트에 충실하지만 과도하면 부자연스러움",
                    "example": 3.5,
                },
                "seed": {
                    "type": "integer | null",
                    "required": False,
                    "default": None,
                    "description": "랜덤 시드 (재현성을 위해 사용)",
                    "note": "같은 시드와 파라미터로 동일한 결과 생성 가능",
                    "example": 42,
                },
                "test_mode": {
                    "type": "boolean",
                    "required": False,
                    "default": False,
                    "description": "테스트 모드 (AI 모델 없이 더미 이미지 반환)",
                    "use_case": "API 구조 테스트, GPU 없는 환경에서 테스트",
                    "example": False,
                },
            },
        },
        "example_requests": {
            "basic_full_pipeline": {
                "description": "기본 전체 파이프라인 실행",
                "request": {
                    "product_image": "<base64_product_image>",
                    "bg_prompt": "luxury hotel lobby with warm lighting",
                    "text_content": "Grand Opening",
                    "text_prompt": "gold metallic 3D text",
                    "font_name": "NanumSquare/NanumSquareB.ttf",
                    "start_step": 1,
                },
            },
            "advanced_customization": {
                "description": "고급 커스터마이징 예시",
                "request": {
                    "product_image": "<base64_product_image>",
                    "bg_prompt": "modern minimalist studio with soft shadows",
                    "bg_negative_prompt": "cluttered, dark, people, text",
                    "text_content": "NEW COLLECTION",
                    "text_prompt": "chrome reflective text with mirror finish and glow",
                    "text_negative_prompt": "flat, 2d, blurry, distorted",
                    "font_name": "NanumGothic/NanumGothic.ttf",
                    "composition_mode": "overlay",
                    "text_position": "center",
                    "strength": 0.7,
                    "guidance_scale": 4.0,
                    "composition_strength": 0.5,
                    "composition_steps": 30,
                    "seed": 12345,
                    "start_step": 1,
                },
            },
            "retry_text_only": {
                "description": "텍스트만 다시 생성 (Step 2부터)",
                "request": {
                    "step1_image": "<previous_step1_result_base64>",
                    "text_content": "Different Text",
                    "text_prompt": "neon glowing text with pink and blue",
                    "font_name": "NanumSquare/NanumSquareB.ttf",
                    "start_step": 2,
                },
            },
            "recompose_only": {
                "description": "합성만 다시 실행 (Step 3만)",
                "request": {
                    "step1_image": "<background_base64>",
                    "step2_image": "<text_base64>",
                    "composition_mode": "blend",
                    "text_position": "top",
                    "composition_strength": 0.3,
                    "start_step": 3,
                },
            },
            "background_only_with_stop_step": {
                "description": "배경만 생성 (stop_step 사용)",
                "request": {
                    "product_image": "<base64_product_image>",
                    "bg_prompt": "modern office workspace with natural light",
                    "start_step": 1,
                    "stop_step": 1,
                    "text_content": None,
                },
                "note": "stop_step=1로 설정하여 Step 1 완료 후 자동 중단",
            },
            "background_and_text_only": {
                "description": "배경 + 텍스트만 생성 (합성 제외)",
                "request": {
                    "product_image": "<base64_product_image>",
                    "bg_prompt": "luxury marble background",
                    "text_content": "Premium",
                    "text_prompt": "gold metallic 3D text",
                    "start_step": 1,
                    "stop_step": 2,
                },
                "note": "stop_step=2로 설정하여 Step 2 완료 후 자동 중단, Step 3(합성) 건너뜀",
            },
        },
        "tips_for_llms": {
            "understanding_base64": "이미지는 Base64 문자열로 인코딩되어야 합니다. 사용자가 이미지 파일을 제공하면 Base64로 변환 후 요청하세요.",
            "polling_strategy": "작업 시작 후 2-5초 간격으로 GET /status/{job_id}를 호출하여 status가 'completed' 또는 'failed'가 될 때까지 폴링하세요.",
            "error_handling": "503 응답 시 Retry-After 헤더를 확인하여 대기 시간을 사용자에게 안내하세요.",
            "step_reuse": "사용자가 특정 부분만 수정하고 싶어하면 이전 결과의 step1_result 또는 step2_result를 재사용하세요.",
            "stop_step_usage": "사용자가 배경만 원하거나 중간 단계 결과만 필요하면 stop_step을 활용하세요. (예: stop_step=1로 배경만 생성)",
            "step_combination": "start_step과 stop_step을 조합하여 원하는 단계만 실행할 수 있습니다. (예: start_step=2, stop_step=2로 텍스트만 재생성)",
            "prompt_engineering": "배경 및 텍스트 프롬프트는 영문이 더 정확합니다. 사용자가 한글로 입력하면 영문으로 번역하여 요청하세요.",
            "parameter_defaults": "대부분의 파라미터는 기본값이 잘 설정되어 있으므로, 사용자가 특별히 요청하지 않으면 기본값을 사용하세요.",
        },
    }
