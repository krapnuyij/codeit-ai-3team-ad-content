# nanoCocoa_mcpserver 테스트 가이드

## 테스트 구성

### 1. **단위 테스트 (Unit Tests)**

#### test_image_utils.py
- 이미지 Base64 인코딩/디코딩
- 이미지 검증 및 리사이즈
- 파일 저장 및 로드
- 에러 처리

**실행:**
```bash
pytest tests/nanoCocoa_mcpserver/test_image_utils.py -v
```

#### test_api_client.py
- API 클라이언트 초기화
- 각 API 엔드포인트 호출 (Mock 사용)
- 에러 처리 (503, 404 등)
- 재시도 로직
- 완료 대기 및 폴링

**실행:**
```bash
pytest tests/nanoCocoa_mcpserver/test_api_client.py -v
```

#### test_server.py
- MCP 서버 초기화
- 각 MCP 도구 핸들러 (Mock 사용)
- 이미지 저장 기능
- 에러 핸들링

**실행:**
```bash
pytest tests/nanoCocoa_mcpserver/test_server.py -v
```

### 2. **통합 테스트 (Integration Tests)**

#### test_integration.py
- 실제 nanoCocoa_aiserver와 연동
- 전체 워크플로우 테스트
- 단계별 생성 테스트
- 동시 요청 처리
- 작업 중단 및 관리

**주의:** 통합 테스트는 nanoCocoa_aiserver가 실행 중이어야 합니다!

**실행:**
```bash
# AI 서버 먼저 실행
python -m uvicorn nanoCocoa_aiserver.main:app --host 0.0.0.0 --port 8000

# 통합 테스트 실행 (별도 터미널)
RUN_INTEGRATION_TESTS=true pytest tests/nanoCocoa_mcpserver/test_integration.py -v
```

## 전체 테스트 실행

### 단위 테스트만 실행
```bash
pytest tests/nanoCocoa_mcpserver/ -m "not integration" -v
```

### 통합 테스트만 실행
```bash
RUN_INTEGRATION_TESTS=true pytest tests/nanoCocoa_mcpserver/ -m integration -v
```

### 모든 테스트 실행
```bash
RUN_INTEGRATION_TESTS=true pytest tests/nanoCocoa_mcpserver/ -v
```

### 느린 테스트 제외
```bash
pytest tests/nanoCocoa_mcpserver/ -m "not slow" -v
```

## 커버리지 리포트

### 커버리지 측정
```bash
pytest tests/nanoCocoa_mcpserver/ \
  --cov=nanoCocoa_mcpserver \
  --cov-report=html \
  --cov-report=term-missing \
  -v
```

### HTML 리포트 확인
```bash
# 커버리지 리포트 생성 후
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

## 테스트 마커 사용

### 마커 종류
- `@pytest.mark.unit` - 단위 테스트 (기본)
- `@pytest.mark.integration` - 통합 테스트
- `@pytest.mark.slow` - 느린 테스트

### 특정 마커만 실행
```bash
# 통합 테스트만
pytest tests/nanoCocoa_mcpserver/ -m integration

# 느린 테스트 제외
pytest tests/nanoCocoa_mcpserver/ -m "not slow"

# 통합 + 느린 테스트 제외
pytest tests/nanoCocoa_mcpserver/ -m "integration and not slow"
```

## 특정 테스트만 실행

### 파일 단위
```bash
pytest tests/nanoCocoa_mcpserver/test_api_client.py -v
```

### 클래스 단위
```bash
pytest tests/nanoCocoa_mcpserver/test_api_client.py::TestClassName -v
```

### 함수 단위
```bash
pytest tests/nanoCocoa_mcpserver/test_api_client.py::test_client_initialization -v
```

### 패턴 매칭
```bash
# "health"가 포함된 테스트만
pytest tests/nanoCocoa_mcpserver/ -k "health" -v

# "generate"가 포함된 테스트만
pytest tests/nanoCocoa_mcpserver/ -k "generate" -v
```

## 실패 시 디버깅

### 실패한 테스트만 재실행
```bash
pytest tests/nanoCocoa_mcpserver/ --lf -v
```

### 첫 번째 실패에서 중단
```bash
pytest tests/nanoCocoa_mcpserver/ -x -v
```

### 상세한 출력
```bash
pytest tests/nanoCocoa_mcpserver/ -vv -s
```

### PDB 디버거 사용
```bash
pytest tests/nanoCocoa_mcpserver/ --pdb
```

## CI/CD 통합

### GitHub Actions 예제
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Run unit tests
        run: |
          pytest tests/nanoCocoa_mcpserver/ \
            -m "not integration" \
            --cov=nanoCocoa_mcpserver \
            --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

## 테스트 작성 가이드

### 단위 테스트 작성 시
1. **Mock 사용**: 외부 의존성은 Mock으로 대체
2. **독립성**: 각 테스트는 독립적으로 실행 가능해야 함
3. **명확한 이름**: 테스트 함수 이름으로 의도를 명확히
4. **AAA 패턴**: Arrange, Act, Assert

### 통합 테스트 작성 시
1. **서버 확인**: AI 서버 연결 실패 시 skip
2. **정리**: 생성한 작업은 삭제하여 정리
3. **타임아웃**: 적절한 타임아웃 설정
4. **테스트 모드**: 가능하면 test_mode=True 사용

## 테스트 통계

현재 테스트 현황:

| 파일 | 테스트 수 | 커버리지 목표 |
|------|-----------|---------------|
| test_image_utils.py | 20+ | 95%+ |
| test_api_client.py | 15+ | 90%+ |
| test_server.py | 15+ | 85%+ |
| test_integration.py | 10+ | 실제 연동 |

## 문제 해결

### Q: "ModuleNotFoundError: No module named 'nanoCocoa_mcpserver'"
**A:** Python 경로 설정 확인
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
# 또는
pip install -e .
```

### Q: 통합 테스트가 스킵됨
**A:** 환경 변수 설정
```bash
export RUN_INTEGRATION_TESTS=true
```

### Q: "AI 서버가 실행 중이지 않습니다"
**A:** nanoCocoa_aiserver 실행 확인
```bash
curl http://localhost:8000/health
```

### Q: 테스트가 너무 느림
**A:** 느린 테스트 제외
```bash
pytest tests/nanoCocoa_mcpserver/ -m "not slow" -v
```
