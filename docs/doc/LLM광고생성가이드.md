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

## 9. 트러블슈팅

### 9.1. job_id를 찾을 수 없음

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
