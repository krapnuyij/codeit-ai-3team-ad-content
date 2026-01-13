# nanoCocoa MCP 서버 테스트 가이드

## 테스트 구조

### 1. 단위 테스트 (Unit Tests)
서버 실행 없이 Mock을 사용하여 테스트합니다.

- **test_image_utils.py**: 이미지 처리 유틸리티
- **test_api_client.py**: AI 서버 API 클라이언트
- **test_server.py**: MCP 서버 FastAPI 엔드포인트

### 2. 통합 테스트 (Integration Tests)
실제 AI 서버와 연동하여 전체 워크플로우를 테스트합니다.

- **test_integration.py**: 전체 파이프라인, 단계별 생성, 동시 요청 등

## 테스트 실행 방법

### 방법 1: 테스트 스크립트 사용 (권장)

```bash
# 프로젝트 루트에서 실행

# 단위 테스트만 실행 (서버 불필요)
python tests/nanoCocoa_mcpserver/run_tests.py --unit

# 통합 테스트만 실행 (AI 서버 필요)
python tests/nanoCocoa_mcpserver/run_tests.py --integration

# 모든 테스트 실행
python tests/nanoCocoa_mcpserver/run_tests.py --all
```

### 방법 2: pytest 직접 사용

```bash
# 단위 테스트
pytest tests/nanoCocoa_mcpserver/test_image_utils.py -v
pytest tests/nanoCocoa_mcpserver/test_api_client.py -v
pytest tests/nanoCocoa_mcpserver/test_server.py -v

# 통합 테스트 (AI 서버 필요)
pytest tests/nanoCocoa_mcpserver/test_integration.py -v -m integration

# 빠른 테스트만 (slow 제외)
pytest tests/nanoCocoa_mcpserver/test_integration.py -v -m "integration and not slow"
```

## AI 서버 실행

통합 테스트를 실행하기 전에 AI 서버를 먼저 시작해야 합니다.

```bash
# 터미널 1: AI 서버 시작
cd src/nanoCocoa_aiserver
python -m uvicorn nanoCocoa_aiserver.main:app --host 0.0.0.0 --port 8000

# 터미널 2: 테스트 실행
python tests/nanoCocoa_mcpserver/run_tests.py --integration
```

## Fixture 사용

### 서버 상태 확인 Fixtures

- **aiserver_running**: AI 서버 실행 여부 확인
- **mcpserver_running**: MCP 서버 실행 여부 확인
- **require_aiserver**: AI 서버가 없으면 테스트 skip
- **require_mcpserver**: MCP 서버가 없으면 테스트 skip

### 사용 예시

```python
@pytest.mark.asyncio
async def test_example(require_aiserver):
    """AI 서버가 필요한 테스트"""
    async with AIServerClient() as client:
        health = await client.check_health()
        assert health.status == "healthy"
```

## 테스트 마커

- **@pytest.mark.integration**: 통합 테스트 표시
- **@pytest.mark.slow**: 시간이 오래 걸리는 테스트
- **@pytest.mark.asyncio**: 비동기 테스트

## 문제 해결

### AI 서버가 실행 중이지 않습니다

```bash
# AI 서버 상태 확인
curl http://localhost:8000/health

# AI 서버 시작
cd src/nanoCocoa_aiserver
python -m uvicorn nanoCocoa_aiserver.main:app --host 0.0.0.0 --port 8000
```

### 테스트가 skip됩니다

통합 테스트는 AI 서버가 실행 중이어야 합니다. `require_aiserver` fixture가 자동으로 서버 상태를 확인하고 없으면 skip합니다.

### 환경 변수 설정

더 이상 `RUN_INTEGRATION_TESTS=true` 환경 변수가 필요하지 않습니다. Fixture가 자동으로 서버 상태를 확인합니다.

## 테스트 커버리지

```bash
# 커버리지 측정
pytest tests/nanoCocoa_mcpserver/ --cov=nanoCocoa_mcpserver --cov-report=html

# 결과 확인
open htmlcov/index.html
```

## CI/CD 통합

GitHub Actions 등에서 사용할 경우:

```yaml
- name: Run Unit Tests
  run: python tests/nanoCocoa_mcpserver/run_tests.py --unit

- name: Start AI Server
  run: |
    cd src/nanoCocoa_aiserver
    python -m uvicorn nanoCocoa_aiserver.main:app --host 0.0.0.0 --port 8000 &
    sleep 10

- name: Run Integration Tests
  run: python tests/nanoCocoa_mcpserver/run_tests.py --integration
```
