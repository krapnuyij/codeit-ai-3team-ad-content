# nanoCocoa MCP Server

AI 기반 광고 이미지 생성을 위한 MCP (Model Context Protocol) 서버

## 개요

nanoCocoa_mcpserver는 nanoCocoa_aiserver의 REST API를 MCP 프로토콜로 감싸서 제공하는 브릿지 서버입니다. LLM(GPT, Claude 등)이 자연어 명령을 통해 AI 광고 이미지를 생성할 수 있도록 합니다.

### 시스템 아키텍처

```
사용자 입력 (자연어)
      ↓
백엔드 + MCP 어댑터 + LLM
      ↓
nanoCocoa_mcpserver (MCP 서버) ← 이 프로젝트
      ↓
nanoCocoa_aiserver (AI 서빙 서버)
      ↓
GPU 기반 AI 모델 (FLUX, SDXL 등)
```

## 주요 기능

### 제공되는 MCP 도구 (8개)

#### 기본 도구
1. **generate_ad_image** - 전체 파이프라인 광고 이미지 생성
2. **check_generation_status** - 생성 작업 진행 상태 확인
3. **stop_generation** - 실행 중인 작업 중단
4. **list_available_fonts** - 사용 가능한 폰트 목록 조회
5. **check_server_health** - AI 서버 상태 및 리소스 확인

#### 고급 도구 (단계별 실행)
6. **generate_background_only** - Step 1만 실행 (배경 생성)
7. **generate_text_asset_only** - Step 2만 실행 (3D 텍스트 생성)
8. **compose_final_image** - Step 3만 실행 (최종 합성)

## 설치

### 요구사항
- Python 3.10 이상
- nanoCocoa_aiserver 실행 중 (http://localhost:8000)
- Docker 및 Docker Compose (컨테이너 배포 시)

### 설치 방법

#### 방법 1: Docker Compose로 실행 (권장)

Docker Compose를 사용하면 AI 서버와 MCP 서버를 함께 자동으로 배포할 수 있습니다.

```bash
# src 디렉토리로 이동
cd codeit-ai-3team-ad-content/src

# 모든 서비스 시작 (AI 서버 + MCP 서버)
sudo docker-compose up -d --build

# 서비스 상태 확인
docker-compose ps

# MCP 서버 로그 확인
docker-compose logs -f nanococoa-mcpserver

# 서비스 중지
sudo docker-compose down
```

**배포되는 서비스**:
- `nanococoa-aiserver`: AI 모델 서빙 서버 (포트 8000)
- `nanococoa-mcpserver`: MCP 프로토콜 브릿지 서버 (포트 3000)

**Docker 네트워크**:
- MCP 서버는 내부 네트워크를 통해 `http://nanococoa-aiserver:8000`으로 AI 서버에 접근

#### 방법 2: 직접 설치 (개발 환경)

```bash
# 프로젝트 루트에서
cd codeit-ai-3team-ad-content

# 의존성 설치
pip install -e .

# 개발 의존성 포함 설치
pip install -e ".[dev]"
```

## 사용 방법

### 1. MCP 서버 실행

#### Docker Compose 사용 (권장)

```bash
# src 디렉토리에서
cd codeit-ai-3team-ad-content/src

# 모든 서비스 시작
sudo docker-compose up -d

# MCP 서버 상태 확인
curl http://localhost:3000/health

# 로그 모니터링
docker-compose logs -f nanococoa-mcpserver
```

#### 직접 실행

```bash
# MCP 서버 시작
python -m nanoCocoa_mcpserver.server

# 또는 스크립트 사용
nanococoa-mcpserver
```

### 2. API 클라이언트 직접 사용

MCP 서버 없이 Python 코드에서 직접 API 클라이언트를 사용할 수 있습니다.

```python
import asyncio
from nanoCocoa_mcpserver.client.api_client import AIServerClient
from nanoCocoa_mcpserver.schemas.api_models import GenerateRequest
from nanoCocoa_mcpserver.utils.image_utils import (
    image_file_to_base64,
    base64_to_image_file
)

async def main():
    async with AIServerClient() as client:
        # 서버 상태 확인
        health = await client.check_health()
        print(f"서버 상태: {health.status}")

        # 이미지 로드
        product_image = image_file_to_base64("product.png")

        # 생성 요청
        params = GenerateRequest(
            start_step=1,
            input_image=product_image,
            bg_prompt="Wooden table, cozy cafe, sunlight",
            text_content="SALE",
            text_model_prompt="Gold balloon text, 3d render",
        )

        # 생성 및 완료 대기
        result = await client.generate_and_wait(
            params,
            progress_callback=lambda s: print(f"{s.progress_percent}% - {s.message}")
        )

        # 결과 저장
        if result.final_result:
            base64_to_image_file(result.final_result, "output.png")
            print("완료!")

asyncio.run(main())
```

### 3. 단계별 워크플로우

각 단계를 독립적으로 실행하고 중간 결과를 재사용할 수 있습니다.

```python
async def step_workflow():
    async with AIServerClient() as client:
        # Step 1: 배경 생성
        step1_params = GenerateRequest(
            start_step=1,
            input_image=product_image_b64,
            bg_prompt="Marble podium, sunset beach",
            text_content=None,  # 배경만
        )
        step1_result = await client.generate_and_wait(step1_params)

        # Step 2: 3D 텍스트 생성
        step2_params = GenerateRequest(
            start_step=2,
            step1_image=step1_result.step1_result,  # Step 1 결과 사용
            text_content="NEW",
            text_model_prompt="Crystal ice text, transparent",
        )
        step2_result = await client.generate_and_wait(step2_params)

        # Step 3: 최종 합성
        step3_params = GenerateRequest(
            start_step=3,
            step1_image=step1_result.step1_result,
            step2_image=step2_result.step2_result,
            composition_mode="blend",
            text_position="center",
        )
        final_result = await client.generate_and_wait(step3_params)
```

## 환경 변수 설정

### Docker Compose 환경 변수

Docker Compose로 실행 시 환경 변수는 `docker-compose.yml`에서 자동으로 설정됩니다:

```yaml
environment:
  - MCP_TRANSPORT=sse
  - MCP_PORT=3000
  - MCP_HOST=0.0.0.0
  - AISERVER_BASE_URL=http://nanococoa-aiserver:8000  # 내부 네트워크 주소
  - LOG_LEVEL=INFO
```

### 직접 실행 시 환경 변수

`.env` 파일을 생성하여 설정을 커스터마이즈할 수 있습니다.

```bash
# AI 서버 연결
AISERVER_BASE_URL=http://localhost:8000  # 로컬 실행 시
AISERVER_TIMEOUT=600
AISERVER_CONNECT_TIMEOUT=10

# 폴링 설정
STATUS_POLL_INTERVAL=3.0
MAX_POLL_RETRIES=200

# 로깅
LOG_LEVEL=INFO
LOG_FILE=/var/log/nanococoa_mcpserver.log

# 기능 플래그
ENABLE_CACHING=false
ENABLE_METRICS=true
ENABLE_PROGRESS_NOTIFICATIONS=true
```

**참고**: Docker 환경에서는 AI 서버 URL이 `http://nanococoa-aiserver:8000`으로 설정되어 내부 네트워크를 통해 통신합니다.

## 예제 코드

### 예제 1: 기본 사용
```bash
python examples/nanoCocoa_mcpserver/basic_usage.py
```

### 예제 2: 단계별 워크플로우
```bash
python examples/nanoCocoa_mcpserver/step_based_workflow.py
```

## 테스트

```bash
# 전체 테스트 실행
pytest tests/nanoCocoa_mcpserver/

# 커버리지 포함
pytest tests/nanoCocoa_mcpserver/ --cov=nanoCocoa_mcpserver

# 특정 테스트만 실행
pytest tests/nanoCocoa_mcpserver/test_api_client.py
```

## API 레퍼런스

### AIServerClient

#### 주요 메서드

- `check_health() -> HealthResponse` - 서버 상태 확인
- `get_fonts() -> list[str]` - 폰트 목록 조회
- `start_generation(params) -> GenerateResponse` - 생성 시작
- `get_status(job_id) -> StatusResponse` - 상태 조회
- `stop_job(job_id) -> StopResponse` - 작업 중단
- `wait_for_completion(job_id) -> StatusResponse` - 완료까지 대기
- `generate_and_wait(params) -> StatusResponse` - 원스톱 생성

### 주요 데이터 모델

#### GenerateRequest
```python
GenerateRequest(
    start_step=1,              # 1, 2, 3
    input_image="base64...",   # 제품 이미지
    bg_prompt="...",           # 배경 설명
    text_content="SALE",       # 텍스트
    text_model_prompt="...",   # 텍스트 스타일
    font_name="...",           # 폰트 (선택)
    composition_mode="overlay",# overlay/blend/behind
    text_position="auto",      # top/center/bottom/auto
    seed=42,                   # 랜덤 시드
    # ... 기타 파라미터
)
```

#### StatusResponse
```python
StatusResponse(
    job_id="...",
    status="completed",        # pending/running/completed/failed/stopped
    progress_percent=100,
    current_step="STEP3",
    message="...",
    elapsed_sec=120.5,
    eta_seconds=0,
    step1_result="base64...",  # 배경 이미지
    step2_result="base64...",  # 텍스트 이미지
    final_result="base64...",  # 최종 결과
    system_metrics={...},
)
```

## 에러 처리

### AIServerError

모든 API 에러는 `AIServerError` 예외로 래핑됩니다.

```python
from nanoCocoa_mcpserver.client.api_client import AIServerError

try:
    result = await client.start_generation(params)
except AIServerError as e:
    print(f"에러: {e.message}")
    print(f"상태 코드: {e.status_code}")
    if e.retry_after:
        print(f"{e.retry_after}초 후 재시도")
```

### 일반적인 에러

- **503 Service Unavailable**: 서버가 다른 작업 처리 중 → 재시도 필요
- **404 Not Found**: job_id가 존재하지 않음
- **400 Bad Request**: 잘못된 파라미터
- **Timeout**: 요청 시간 초과

## 개발 가이드

### 프로젝트 구조

```
src/nanoCocoa_mcpserver/
├── __init__.py
├── server.py              # MCP 서버 메인
├── config.py              # 설정 상수
├── schemas/
│   ├── api_models.py      # API 데이터 모델
│   └── mcp_tools.py       # MCP 도구 정의
├── client/
│   └── api_client.py      # REST API 클라이언트
└── utils/
    ├── image_utils.py     # 이미지 처리
    └── logging.py         # 로깅 유틸
```

### 코드 스타일

```bash
# 코드 포맷팅
black src/ tests/

# 린팅
ruff check src/ tests/

# 타입 체크
mypy src/
```

## 트러블슈팅

### Q: "AI 서버에 연결할 수 없습니다" 에러
**A**: nanoCocoa_aiserver가 실행 중인지 확인하세요.
```bash
curl http://localhost:8000/health
```

### Q: 이미지가 너무 커서 실패합니다
**A**: `MAX_IMAGE_SIZE_MB` 설정을 확인하거나 이미지를 리사이즈하세요.
```python
from nanoCocoa_mcpserver.utils.image_utils import resize_image_if_needed
resized = resize_image_if_needed(base64_image, max_dimension=2048)
```

### Q: 폴링이 너무 오래 걸립니다
**A**: `STATUS_POLL_INTERVAL` 및 `MAX_POLL_RETRIES` 설정을 조정하세요.

## 라이선스

MIT License

## 문의

문제가 있거나 기능 제안이 있으면 GitHub Issues에 등록해주세요.
