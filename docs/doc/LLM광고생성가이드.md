---
layout: default
title: "LLM 광고 생성 가이드"
description: "LLM 광고 생성 가이드"
date: 2026-01-13
author: "김명환"
cache-control: no-cache
expires: 0
pragma: no-cache
---

# LLM 광고 생성 가이드

## 1. 개요

본 문서는 LLMAdapter를 사용하여 자연어로 광고 이미지를 생성하는 방법을 안내합니다.

### 1.1. 특징

- 자연어 입력만으로 광고 생성
- 복잡한 API 파라미터 자동 생성
- OpenAI LLM이 MCP 도구를 자동 호출
- 비동기 작업 지원 (job_id 기반 폴링)

### 1.2. 구조

```
사용자 (자연어) → LLMAdapter → OpenAI LLM → MCP 도구 호출 → AI 서버
```

---

## 2. 기본 사용법

### 2.1. 환경 설정

```python
import os
from pathlib import Path
from mcpadapter import LLMAdapter

# 환경 변수 설정
openai_api_key = os.getenv("OPENAI_API_KEY")
mcp_server_url = "http://localhost:3000"

# 경로 설정
product_image_path = "/path/to/product.png"
output_image_path = "/path/to/result.png"
```

### 2.2. 간단한 광고 생성

```python
async def simple_ad_generation():
    """가장 간단한 광고 생성 예제"""
    async with LLMAdapter(
        openai_api_key=openai_api_key,
        mcp_server_url=mcp_server_url,
        model="gpt-5-mini"
    ) as adapter:
        
        # 자연어 요청
        response = await adapter.chat(
            "product.png로 여름 세일 광고 만들어줘"
        )
        print(response)
```

---

## 3. 자연어 요청 작성 규칙

### 3.1. 요청 구조

```python
user_request = f"""
사용자: {요청_내용}

- product_image_path: "{product_image_path}"
- save_output_path: "{output_image_path}"
- text_content: "{광고_문구}"
- wait_for_completion: {true|false}
- composition_mode: "{overlay|natural_blend}"

모든 프롬프트는 영문으로 작성하세요.
"""
```

### 3.2. 필수 정보

| 항목 | 설명 | 예시 |
|------|------|------|
| `요청_내용` | 광고 유형 및 의도 | "바나나 특가 광고 만들어줘" |
| `product_image_path` | 제품 이미지 경로 (절대경로) | "/app/static/uploads/banana.png" |
| `save_output_path` | 결과 저장 경로 (절대경로) | "/app/static/results/ad.png" |
| `text_content` | 광고 문구 (한글/영문) | "맛있는바나나 2500원" |

### 3.3. 선택 파라미터

| 항목 | 설명 | 기본값 | 옵션 |
|------|------|--------|------|
| `wait_for_completion` | 완료 대기 여부 | `true` | `true`, `false` |
| `composition_mode` | 합성 모드 | `"overlay"` | `"overlay"`, `"natural_blend"` |
| `ad_type` | 광고 유형 | (자동 추론) | `"sale"`, `"premium"`, `"casual"` |
| `font_name` | 폰트 파일명 | (자동 선택) | `"NanumGothicBold.ttf"` |

---

## 4. 실행 모드

### 4.1. 즉시 실행 모드 (max_tool_calls=1)

**특징**
- 사용자 확인 없이 즉시 도구 호출
- 추가 질문 없음
- job_id 반환 후 종료

**사용 예**

```python
async def immediate_generation():
    """즉시 실행 모드 예제"""
    async with LLMAdapter(
        openai_api_key=openai_api_key,
        mcp_server_url=mcp_server_url,
        model="gpt-5-mini"
    ) as adapter:
        
        user_request = f"""
사용자: 바나나 특가 광고 만들어줘

- product_image_path: "{product_image_path}"
- save_output_path: "{output_image_path}"
- text_content: "맛있는바나나 2500원"
- wait_for_completion: false
- composition_mode: "overlay"

모든 프롬프트는 영문으로 작성하세요.
"""
        
        # max_tool_calls=1: 즉시 실행
        response = await adapter.chat(user_request, max_tool_calls=1)
        
        # job_id 추출 (도구 응답에서)
        tool_response = None
        for msg in reversed(adapter.conversation_history):
            if msg.get("role") == "tool":
                tool_response = msg.get("content")
                break
        
        # JSON 파싱
        import json
        tool_data = json.loads(tool_response)
        job_id = tool_data["job_id"]
        
        return job_id
```

### 4.2. 대화 모드 (max_tool_calls > 1)

**특징**
- LLM이 옵션 제시 및 사용자 확인 요청
- 여러 번의 대화 가능
- 최종 승인 후 도구 호출

**사용 예**

```python
async def interactive_generation():
    """대화 모드 예제"""
    async with LLMAdapter(
        openai_api_key=openai_api_key,
        mcp_server_url=mcp_server_url,
        model="gpt-5-mini"
    ) as adapter:
        
        # 첫 요청
        response1 = await adapter.chat(
            "여름 세일 광고 만들고 싶어",
            max_tool_calls=5
        )
        print(response1)  # LLM이 옵션 제시
        
        # 사용자 선택
        response2 = await adapter.chat(
            "A안으로 진행해줘",
            max_tool_calls=5
        )
        print(response2)  # 광고 생성 완료
```

---

## 5. 작업 상태 확인 (비동기 폴링)

### 5.1. wait_for_completion=false 사용 이유

- 장시간 작업(30초~5분)에서 타임아웃 방지
- 서버 리소스 효율적 사용
- 클라이언트가 주기적으로 상태 확인

### 5.2. 폴링 구현

```python
import asyncio
import json
from mcpadapter import MCPClient

async def check_ad_generation_status(
    job_id: str,
    save_result_path: str,
    max_attempts: int = 300,
    interval: int = 10
):
    """
    작업 상태 확인 및 완료 시 이미지 저장
    
    Args:
        job_id: 작업 ID (generate_ad_image에서 반환)
        save_result_path: 완료 시 저장할 이미지 경로
        max_attempts: 최대 시도 횟수 (기본값: 300)
        interval: 확인 간격(초, 기본값: 10)
    
    Returns:
        최종 상태 결과 (dict)
    """
    async with MCPClient(
        base_url=mcp_server_url,
        timeout=30
    ) as client:
        
        attempt = 0
        while attempt < max_attempts:
            await asyncio.sleep(interval)
            attempt += 1
            
            # 상태 확인 (save_result_path 필수!)
            status_result = await client.call_tool(
                "check_generation_status",
                {
                    "job_id": job_id,
                    "save_result_path": save_result_path
                }
            )
            
            # JSON 파싱
            status_data = json.loads(status_result) if isinstance(status_result, str) else status_result
            status = status_data.get("status")
            progress = status_data.get("progress_percent", 0)
            
            print(f"[{attempt}/{max_attempts}] status={status}, progress={progress}%")
            
            if status == "completed":
                print(f"✅ 작업 완료! 이미지 저장: {save_result_path}")
                return status_data
            elif status == "failed":
                print(f"❌ 작업 실패: {status_data.get('message')}")
                return status_data
            else:
                print(f"⏳ 진행 중... (단계: {status_data.get('current_step')})")
        
        print(f"⏰ 타임아웃: {max_attempts * interval}초 초과")
        return {"status": "timeout"}
```

### 5.3. 전체 워크플로우

```python
async def full_workflow():
    """전체 광고 생성 워크플로우"""
    
    # Step 1: 광고 생성 요청 (즉시 실행)
    job_id = await immediate_generation()
    print(f"Job ID: {job_id}")
    
    # Step 2: 상태 확인 (폴링)
    status_result = await check_ad_generation_status(
        job_id=job_id,
        save_result_path=output_image_path
    )
    
    # Step 3: 결과 확인
    if status_result["status"] == "completed":
        print(f"광고 생성 완료: {output_image_path}")
        # 이미지 표시 (Jupyter)
        from IPython.display import Image, display
        display(Image(filename=str(output_image_path)))
    else:
        print(f"광고 생성 실패: {status_result}")
```

---

## 6. 자연어 요청 템플릿

### 6.1. 세일 광고

```python
user_request = f"""
사용자: 여름 세일 광고 만들어줘

- product_image_path: "{product_image_path}"
- save_output_path: "{output_image_path}"
- text_content: "50% 할인"
- ad_type: "sale"
- wait_for_completion: false

요구사항:
- 밝고 역동적인 배경
- 굵은 폰트 사용
- 빨간색/노란색 계열

모든 프롬프트는 영문으로 작성하세요.
"""
```

### 6.2. 프리미엄 광고

```python
user_request = f"""
사용자: 명품 프리미엄 광고 만들어줘

- product_image_path: "{product_image_path}"
- save_output_path: "{output_image_path}"
- text_content: "Limited Edition"
- ad_type: "premium"
- wait_for_completion: false

요구사항:
- 고급스러운 검은 배경
- 우아한 세리프 폰트
- 금색 강조

모든 프롬프트는 영문으로 작성하세요.
"""
```

### 6.3. 캐주얼 광고

```python
user_request = f"""
사용자: 친구들과 함께하는 카페 광고 만들어줘

- product_image_path: "{product_image_path}"
- save_output_path: "{output_image_path}"
- text_content: "함께 즐기는 시간"
- ad_type: "casual"
- wait_for_completion: false

요구사항:
- 따뜻하고 친근한 분위기
- 손글씨 스타일 폰트
- 파스텔 톤

모든 프롬프트는 영문으로 작성하세요.
"""
```

---

## 7. 자연어 요청 작성 팁

### 7.1. 핵심 원칙

1. **명확한 의도**: "바나나 특가 광고 만들어줘"
2. **필수 정보 제공**: 이미지 경로, 광고 문구
3. **스타일 가이드**: 색상, 폰트, 분위기 명시
4. **영문 프롬프트 지시**: "모든 프롬프트는 영문으로 작성하세요"

### 7.2. 좋은 예시

```python
# ✅ 좋은 예시
user_request = """
사용자: 바나나 특가 광고 만들어줘

- product_image_path: "/app/static/uploads/banana.png"
- save_output_path: "/app/static/results/banana_ad.png"
- text_content: "맛있는바나나 2500원"
- wait_for_completion: false
- composition_mode: "overlay"

요구사항:
- 밝고 활기찬 시장 배경
- 노란색/초록색 계열
- 굵은 한글 폰트

모든 프롬프트는 영문으로 작성하세요.
"""
```

### 7.3. 나쁜 예시

```python
# ❌ 나쁜 예시 1: 정보 부족
user_request = "광고 만들어줘"  # 어떤 광고? 어떤 이미지?

# ❌ 나쁜 예시 2: 경로 누락
user_request = "바나나 광고 만들어줘"  # 이미지 경로 없음

# ❌ 나쁜 예시 3: 모호한 요구사항
user_request = "멋진 광고 만들어줘"  # 어떤 스타일?
```

---

## 8. 고급 사용법

### 8.1. 폰트 자동 추천

```python
async def auto_font_selection():
    """광고 유형별 폰트 자동 선택"""
    async with LLMAdapter(
        openai_api_key=openai_api_key,
        mcp_server_url=mcp_server_url,
        model="gpt-5-mini"
    ) as adapter:
        
        # 폰트 추천 요청
        response = await adapter.chat(
            "50% 할인 세일 광고에 어울리는 굵은 폰트 추천해줘"
        )
        print(response)
```

### 8.2. 배경 이미지 없이 텍스트만 생성

```python
user_request = f"""
사용자: 텍스트 에셋만 생성해줘

- text_content: "SUMMER SALE"
- save_output_path: "{output_path}"
- font_name: "NanumGothicExtraBold.ttf"

모든 프롬프트는 영문으로 작성하세요.
"""
```

### 8.3. 배경 이미지만 생성

```python
user_request = f"""
사용자: 여름 해변 배경 이미지만 생성해줘

- save_output_path: "{output_path}"
- background_prompt: "Bright summer beach scene with blue sky"

모든 프롬프트는 영문으로 작성하세요.
"""
```

---

## 9. 개발자를 위한 빠른 테스트 전략

### 9.1. 문제 상황

**일반 광고 생성 시간: 15~20분**

개발 중 가장 큰 장애물은 긴 작업 시간입니다:
- 배경 생성: 5~7분
- 제품 합성: 3~5분
- 텍스트 생성: 4~6분
- 최종 합성: 3~5분

이로 인해:
- 파라미터 조정 시 매번 20분 대기
- 버그 수정 후 검증에 20분 소요
- 하루에 테스트 가능한 횟수 제한 (3~4회)

### 9.2. 전략 1: 테스트 모드 사용 (권장)

**특징**
- 실제 모델 추론 생략
- 더미 이미지 즉시 반환
- 작업 시간: **1~2초**
- API/파라미터 검증에 최적

**사용법**

```python
user_request = f"""
사용자: 바나나 특가 광고 만들어줘

- product_image_path: "{product_image_path}"
- save_output_path: "{output_image_path}"
- text_content: "맛있는바나나 2500원"
- test_mode: true  # ⭐ 테스트 모드 활성화
- wait_for_completion: false

모든 프롬프트는 영문으로 작성하세요.
"""

async with LLMAdapter(...) as adapter:
    response = await adapter.chat(user_request, max_tool_calls=1)
```

**언제 사용하나요?**
- API 연동 개발 초기 단계
- 요청/응답 구조 검증
- 파라미터 전달 테스트
- CI/CD 파이프라인 테스트

**주의사항**
- 더미 이미지는 품질 검증 불가
- 프롬프트 효과 확인 불가
- 실제 배포 전 `test_mode: false`로 전환 필수

### 9.3. 전략 2: 작업 강제 중단 후 테스트

**특징**
- 이전 작업 강제 중단
- 새 작업 즉시 시작
- 서버 리소스 즉시 확보

**기본 구현**

```python
async def force_stop_all_and_start():
    """모든 작업 중단 후 새 광고 생성"""
    
    async with MCPClient(
        base_url=mcp_server_url,
        timeout=30
    ) as client:
        
        # Step 1: 모든 작업 목록 조회
        all_jobs = await client.call_tool("get_all_jobs", {})
        jobs_data = json.loads(all_jobs)
        
        # Step 2: 실행 중/대기 중 작업 강제 중단
        for job in jobs_data.get("jobs", []):
            status = job.get("status")
            job_id = job.get("job_id")
            
            if status in ["pending", "running"]:
                print(f"강제 중단 시도: {job_id} (status={status})")
                await client.call_tool("stop_generation", {"job_id": job_id})
        
        # Step 3: 새 광고 생성 시작
        # ... (이전 예제 코드)
```

**문제점: 중단이 즉시 되지 않음**

모델 로딩 중에는 중단 불가:
- Stable Diffusion 로딩: 30~60초
- ControlNet 로딩: 20~40초
- Shap-E 로딩: 15~30초

### 9.4. 전략 3: 재시도 기반 강제 중단 (권장)

**특징**
- 작업 상태를 지속적으로 확인
- 중단될 때까지 반복 요청
- 타임아웃 설정으로 안전장치 추가

**개선된 구현**

```python
import asyncio
import json
from mcpadapter import MCPClient

async def force_stop_with_retry(
    max_attempts: int = 30,
    interval: int = 2,
    timeout: int = 60
):
    """
    재시도 기반 작업 강제 중단
    
    Args:
        max_attempts: 최대 시도 횟수 (기본값: 30)
        interval: 재시도 간격(초, 기본값: 2)
        timeout: 전체 타임아웃(초, 기본값: 60)
    
    Returns:
        모든 작업이 중단되었는지 여부
    """
    async with MCPClient(
        base_url=mcp_server_url,
        timeout=30
    ) as client:
        
        start_time = asyncio.get_event_loop().time()
        attempt = 0
        
        while attempt < max_attempts:
            elapsed = asyncio.get_event_loop().time() - start_time
            
            # 타임아웃 체크
            if elapsed > timeout:
                print(f"⏰ 타임아웃: {timeout}초 초과")
                return False
            
            # Step 1: 현재 작업 목록 조회
            all_jobs = await client.call_tool("get_all_jobs", {})
            jobs_data = json.loads(all_jobs)
            
            # Step 2: 실행/대기 중인 작업 필터링
            active_jobs = [
                job for job in jobs_data.get("jobs", [])
                if job.get("status") in ["pending", "running"]
            ]
            
            if not active_jobs:
                print("✅ 모든 작업이 중단되었습니다.")
                return True
            
            # Step 3: 각 작업에 중단 요청
            for job in active_jobs:
                job_id = job.get("job_id")
                status = job.get("status")
                
                print(f"[{attempt+1}/{max_attempts}] 중단 요청: {job_id} (status={status}, 경과: {elapsed:.1f}초)")
                
                try:
                    result = await client.call_tool(
                        "stop_generation",
                        {"job_id": job_id}
                    )
                    print(f"   중단 응답: {result}")
                except Exception as e:
                    print(f"   중단 실패: {e}")
            
            # Step 4: 재시도 대기
            await asyncio.sleep(interval)
            attempt += 1
        
        print(f"⚠️ 최대 시도 횟수 도달: {max_attempts}회")
        return False

# 사용 예
success = await force_stop_with_retry(
    max_attempts=30,  # 30회 시도
    interval=2,       # 2초마다
    timeout=60        # 총 60초 제한
)

if success:
    print("새 광고 생성 시작 가능")
else:
    print("강제 중단 실패 - 서버 재시작 고려")
```

### 9.5. 전략 4: 전체 작업 삭제 (완료/실패 작업 정리)

**특징**
- 완료/실패한 작업 이력 삭제
- 실행/대기 중인 작업은 자동 건너뜀
- 서버 메모리 정리

**사용법**

```python
async def cleanup_completed_jobs():
    """완료된 작업 정리"""
    async with MCPClient(
        base_url=mcp_server_url,
        timeout=30
    ) as client:
        
        result = await client.call_tool("delete_all_jobs", {})
        print(result)
```

### 9.6. 추천 개발 워크플로우

#### Phase 1: 초기 개발 (test_mode)

```python
# ✅ 빠른 반복 (1~2초/회)
user_request = f"""
- test_mode: true
- wait_for_completion: true  # 즉시 완료
"""
```

**장점**: API 구조 검증, 파라미터 전달 테스트

#### Phase 2: 프롬프트 튜닝 (강제 중단)

```python
# 1. 이전 작업 강제 중단
await force_stop_with_retry()

# 2. 새 광고 생성 (실제 모델)
user_request = f"""
- test_mode: false
- wait_for_completion: false
"""
```

**장점**: 실제 이미지 품질 확인, 프롬프트 효과 검증

#### Phase 3: 최종 검증 (전체 프로세스)

```python
# 작업 정리 후 처음부터 끝까지 실행
await cleanup_completed_jobs()

user_request = f"""
- test_mode: false
- wait_for_completion: true  # 완료까지 대기
"""
```

**장점**: 실제 운영 환경과 동일한 조건

### 9.7. 시간 비교표

| 전략 | 작업 시간 | 이미지 품질 | 용도 |
|------|-----------|-------------|------|
| 일반 실행 | **15~20분** | ⭐⭐⭐⭐⭐ | 최종 검증 |
| 테스트 모드 | **1~2초** | ❌ (더미) | 초기 개발 |
| 강제 중단 + 재시작 | **1~2분** | ⭐⭐⭐⭐⭐ | 프롬프트 튜닝 |
| 작업 정리 | **1초** | N/A | 환경 초기화 |

### 9.8. 실전 팁

1. **개발 초기**: `test_mode=true`로 시작
2. **프롬프트 조정**: 강제 중단 후 즉시 재시작
3. **중단 안 될 때**: 2초마다 재시도 (최대 60초)
4. **하루 마무리**: `delete_all_jobs()`로 정리
5. **최종 배포 전**: `test_mode=false` + 전체 프로세스 검증

### 9.9. 서버 즉시 초기화 (Server Reset API) ⭐⭐⭐

**가장 빠르고 확실한 초기화 방법**

모든 작업 중단 + 메모리 정리를 한 번의 API 호출로 수행합니다.

**특징**
- 소요 시간: **1~3초** (모델 로딩 중일 경우 최대 10초)
- 모든 작업 강제 중단 + 삭제 + GPU 메모리 정리
- 재시도 로직 내장 (프로세스 kill까지 수행)
- 100% 확실한 초기화 보장

**REST API 직접 호출**

```bash
# cURL
curl -X POST http://localhost:8000/server-reset

# HTTPie
http POST http://localhost:8000/server-reset
```

**Python 코드**

```python
import httpx
import json

async def reset_server_and_start_new():
    """서버 초기화 후 새 광고 생성"""
    
    async with httpx.AsyncClient() as client:
        # Step 1: 서버 초기화
        reset_resp = await client.post("http://localhost:8000/server-reset")
        result = reset_resp.json()
        
        print("=" * 60)
        print("서버 초기화 완료")
        print("=" * 60)
        print(f"상태: {result['status']}")
        print(f"중단된 작업: {result['statistics']['stopped_jobs']}개")
        print(f"삭제된 작업: {result['statistics']['deleted_jobs']}개")
        print(f"종료된 프로세스: {result['statistics']['terminated_processes']}개")
        print(f"GPU 메모리: {result['statistics']['gpu_memory_mb']} MB")
        print(f"소요 시간: {result['statistics']['elapsed_sec']}초")
        print("=" * 60)
        
        # Step 2: 즉시 새 광고 생성 시작
        # ... (이전 예제 코드)

# 실행
await reset_server_and_start_new()
```

**LLMAdapter와 함께 사용**

```python
import httpx
from mcpadapter import LLMAdapter

async def quick_reset_and_generate():
    """초기화 후 즉시 광고 생성 (전체 워크플로우)"""
    
    # Step 1: 서버 초기화
    async with httpx.AsyncClient() as client:
        await client.post("http://localhost:8000/server-reset")
        print("✅ 서버 초기화 완료")
    
    # Step 2: 즉시 새 광고 생성
    async with LLMAdapter(
        openai_api_key=openai_api_key,
        mcp_server_url=mcp_server_url,
        model="gpt-4o"
    ) as adapter:
        
        user_request = f"""
사용자: 바나나 특가 광고 만들어줘

- product_image_path: "{product_image_path}"
- save_output_path: "{output_image_path}"
- text_content: "맛있는바나나 2500원"
- wait_for_completion: false

모든 프롬프트는 영문으로 작성하세요.
"""
        
        response = await adapter.chat(user_request, max_tool_calls=1)
        print("✅ 광고 생성 시작")

# 실행
await quick_reset_and_generate()
```

**언제 사용하나요?**
- ⭐ **프롬프트 변경 후 즉시 재테스트** (가장 많이 사용)
- 강제 중단(stop_job)이 실패할 때
- 여러 작업이 쌓였을 때
- 개발 세션 시작/종료 시
- 서버 재시작이 부담스러울 때

**응답 예시**

```json
{
  "status": "success",
  "message": "Server reset completed successfully",
  "statistics": {
    "stopped_jobs": 2,
    "deleted_jobs": 5,
    "terminated_processes": 2,
    "gpu_memory_mb": 234.56,
    "elapsed_sec": 2.34
  }
}
```

**주의사항**
- **개발 전용**: 운영 환경 사용 금지
- 모든 작업 결과 삭제 (복구 불가)
- 실행 중인 작업이 즉시 중단됨
- GPU 메모리 정리 시간이 추가로 소요될 수 있음

**전략 4 (delete_all_jobs)와의 차이**

| 기능 | delete_all_jobs | server-reset |
|------|-----------------|--------------|
| 완료된 작업 삭제 | ✅ | ✅ |
| 실행 중 작업 중단 | ❌ | ✅ |
| 프로세스 강제 종료 | ❌ | ✅ |
| GPU 메모리 정리 | ❌ | ✅ |
| 소요 시간 | 1초 | 1~3초 |
| 확실성 | 중간 | **100%** |

**실전 개발 워크플로우 (업데이트)**

```python
# 🔥 권장: 서버 초기화 사용
await reset_server_and_start_new()

# 기존 방식 (비교)
# await force_stop_with_retry()  # 30~60초 소요
# await cleanup_completed_jobs()  # 실행 중 작업은 남음
```

---

## 10. 트러블슈팅

### 10.1. 강제 중단이 안 되는 경우

**증상**: `stop_generation()` 호출했으나 작업이 계속 실행됨

**원인**:
- 모델 로딩 중 (Stable Diffusion, ControlNet, Shap-E)
- GPU 메모리 할당 중
- 추론 단계 전환 중

**해결**:
```python
# 재시도 기반 강제 중단 사용 (섹션 9.4 참고)
await force_stop_with_retry(
    max_attempts=30,
    interval=2,
    timeout=60
)
```

### 10.2. job_id를 찾을 수 없음

**증상**: `job_id를 찾을 수 없습니다` 경고

**원인**:
- LLM 응답에 JSON 형식이 없음
- 도구 호출 실패

**해결**:
1. `adapter.conversation_history` 확인
2. `max_tool_calls=1` 설정 확인
3. 도구 응답에서 JSON 파싱

```python
# 도구 응답 추출
tool_response = None
for msg in reversed(adapter.conversation_history):
    if msg.get("role") == "tool":
        tool_response = msg.get("content")
        break

# JSON 파싱
import json
tool_data = json.loads(tool_response)
job_id = tool_data["job_id"]
```

### 9.2. 타임아웃 발생

**증상**: `⏰ 타임아웃: 3000초 동안 작업이 완료되지 않음`

**원인**:
- 서버 과부하
- 복잡한 프롬프트
- 네트워크 문제

**해결**:
1. `max_attempts` 증가
2. 서버 상태 확인: `check_server_health()`
3. 간단한 프롬프트로 테스트

### 9.3. 이미지가 저장되지 않음

**증상**: 작업 완료되었으나 이미지 없음

**원인**:
- `save_result_path` 누락
- 디렉토리 권한 문제

**해결**:
```python
# save_result_path 필수 전달
status_result = await client.call_tool(
    "check_generation_status",
    {
        "job_id": job_id,
        "save_result_path": save_result_path  # 필수!
    }
)

# 디렉토리 권한 확인
import os
output_dir = Path(save_result_path).parent
os.chmod(output_dir, 0o777)
```

---

## 10. 참고 자료

### 10.1. 관련 파일

- `src/mcpadapter/llm_adapter.py`: LLMAdapter 구현
- `src/mcpadapter/mcp_client.py`: MCPClient 구현
- `src/nanoCocoa_mcpserver/server.py`: MCP 도구 정의
- `script/김명환/test_llm_mcp.ipynb`: 전체 예제 노트북

### 10.2. MCP 도구 목록

| 도구 이름 | 설명 | 주요 파라미터 |
|-----------|------|---------------|
| `generate_ad_image` | 광고 이미지 생성 | `product_image_path`, `text_content` |
| `check_generation_status` | 작업 상태 확인 | `job_id`, `save_result_path` |
| `recommend_font_for_ad` | 폰트 추천 | `text_content`, `ad_type` |
| `list_available_fonts` | 폰트 목록 조회 | (없음) |
| `check_server_health` | 서버 상태 확인 | (없음) |
| `stop_generation` | 작업 중단 | `job_id` |
| `delete_job` | 작업 삭제 | `job_id` |

### 10.3. 광고 유형별 프롬프트 가이드

**세일 광고 (sale)**
- background: vibrant, dynamic, energetic
- text: bold, large, eye-catching
- color: red, yellow, orange
- font: bold sans-serif

**프리미엄 광고 (premium)**
- background: elegant, minimalist, dark
- text: sophisticated, refined
- color: gold, silver, black
- font: serif, thin, elegant

**캐주얼 광고 (casual)**
- background: warm, friendly, cozy
- text: handwritten, playful
- color: pastel, soft tones
- font: script, handwriting

---

## 11. 전체 예제 코드

```python
import os
import asyncio
import json
from pathlib import Path
from mcpadapter import LLMAdapter, MCPClient

# 환경 설정
openai_api_key = os.getenv("OPENAI_API_KEY")
mcp_server_url = "http://localhost:3000"
product_image_path = "/app/static/uploads/banana.png"
output_image_path = "/app/static/results/banana_ad.png"

async def main():
    """전체 광고 생성 워크플로우"""
    
    # Step 1: 광고 생성 요청
    async with LLMAdapter(
        openai_api_key=openai_api_key,
        mcp_server_url=mcp_server_url,
        model="gpt-5-mini"
    ) as adapter:
        
        user_request = f"""
사용자: 바나나 특가 광고 만들어줘

- product_image_path: "{product_image_path}"
- save_output_path: "{output_image_path}"
- text_content: "맛있는바나나 2500원"
- wait_for_completion: false
- composition_mode: "overlay"

모든 프롬프트는 영문으로 작성하세요.
"""
        
        # 즉시 실행
        response = await adapter.chat(user_request, max_tool_calls=1)
        
        # job_id 추출
        tool_response = None
        for msg in reversed(adapter.conversation_history):
            if msg.get("role") == "tool":
                tool_response = msg.get("content")
                break
        
        tool_data = json.loads(tool_response)
        job_id = tool_data["job_id"]
        print(f"Job ID: {job_id}")
    
    # Step 2: 상태 확인 (폴링)
    async with MCPClient(
        base_url=mcp_server_url,
        timeout=30
    ) as client:
        
        max_attempts = 300
        interval = 10
        attempt = 0
        
        while attempt < max_attempts:
            await asyncio.sleep(interval)
            attempt += 1
            
            status_result = await client.call_tool(
                "check_generation_status",
                {
                    "job_id": job_id,
                    "save_result_path": output_image_path
                }
            )
            
            status_data = json.loads(status_result)
            status = status_data.get("status")
            progress = status_data.get("progress_percent", 0)
            
            print(f"[{attempt}/{max_attempts}] status={status}, progress={progress}%")
            
            if status == "completed":
                print(f"✅ 광고 생성 완료: {output_image_path}")
                break
            elif status == "failed":
                print(f"❌ 작업 실패: {status_data.get('message')}")
                break

# 실행
await main()
```

---

## 12. 요약

### 12.1. 핵심 포인트

1. **자연어 요청**: 복잡한 API 파라미터 불필요
2. **즉시 실행**: `max_tool_calls=1`로 즉시 도구 호출
3. **비동기 폴링**: `wait_for_completion=false` + `check_generation_status`
4. **경로 필수**: 절대 경로 사용
5. **영문 프롬프트**: "모든 프롬프트는 영문으로 작성하세요" 필수

### 12.2. 기본 워크플로우

```
1. LLMAdapter 초기화
2. 자연어 요청 작성 (필수 정보 포함)
3. adapter.chat() 호출 (max_tool_calls=1)
4. job_id 추출
5. check_generation_status()로 폴링
6. 완료 시 이미지 저장 확인
```
