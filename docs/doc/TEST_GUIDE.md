---
layout: default
title: "테스트 실행 가이드"
description: "테스트 실행 가이드"
date: 2026-01-13
author: "김명환"
cache-control: no-cache
expires: 0
pragma: no-cache
---

# 테스트 실행 가이드

## 목차
1. [기본 테스트 실행](#1-기본-테스트-실행)
2. [마커별 테스트 실행](#2-마커별-테스트-실행)
3. [pytest 설정](#3-pytest-설정)
4. [문제 해결](#4-문제-해결)

---

## 1. 기본 테스트 실행

### 1.1. 전체 테스트 실행

```bash
# 프로젝트 루트에서 실행
pytest tests -v
```

### 1.2. 빠른 테스트만 실행 (단위 테스트)

```bash
# slow, integration, docker 테스트 제외
pytest tests -v -m "not slow and not integration and not docker"
```

### 1.3. 특정 파일/디렉토리만 실행

```bash
# 단위 테스트만
pytest tests/units -v

# 통합 테스트만
pytest tests/integration -v

# 특정 파일
pytest tests/units/test_api_scenarios.py -v
```

---

## 2. 마커별 테스트 실행

### 2.1. 사용 가능한 마커

| 마커 | 설명 | 실행 조건 |
|------|------|----------|
| `unit` | 단위 테스트 (기본) | 항상 가능 |
| `integration` | 통합 테스트 | AI 서버 실행 필요 |
| `slow` | 느린 테스트 (30초 이상) | 시간 여유 있을 때 |
| `docker` | Docker 환경 테스트 | Docker 컨테이너 실행 필요 |
| `requires_aiserver` | AI 서버 필요 | 8000 포트에서 서버 실행 |
| `requires_mcpserver` | MCP 서버 필요 | 3000 포트에서 서버 실행 |

### 2.2. 마커로 테스트 선택

```bash
# 단위 테스트만
pytest tests -v -m "unit"

# 통합 테스트만 (서버 실행 필요)
pytest tests -v -m "integration"

# slow 테스트 제외
pytest tests -v -m "not slow"

# docker 테스트 제외
pytest tests -v -m "not docker"

# 빠른 테스트만 (slow, docker 제외)
pytest tests -v -m "not slow and not docker"
```

### 2.3. 특정 디렉토리 제외

```bash
# Docker 테스트 디렉토리 제외
pytest tests -v \
  --ignore=tests/nanoCocoa_mcpserver/test_docker_integration.py \
  --ignore=tests/nanoCocoa_mcpserver/test_docker_simple.py
```

---

## 3. pytest 설정

### 3.1. pyproject.toml 설정

```toml
[tool.pytest.ini_options]
minversion = "8.0"
addopts = [
    "-ra",                  # 모든 테스트 결과 요약
    "--strict-markers",     # 정의되지 않은 마커 사용 시 에러
    "-v",                   # verbose 출력
    "--tb=short",           # 짧은 traceback
    "--maxfail=5",          # 5개 실패 시 중단
    "--disable-warnings",   # 경고 숨기기
]
testpaths = ["tests"]
pythonpath = ["src"]
asyncio_mode = "auto"
timeout = 300               # 기본 타임아웃 300초
```

### 3.2. 타임아웃 설정

```bash
# 전체 타임아웃 30초로 제한
pytest tests -v --timeout=30

# slow 테스트 제외하고 타임아웃 적용
pytest tests -v --timeout=30 -m "not slow"
```

### 3.3. 병렬 실행

```bash
# CPU 코어 수만큼 병렬 실행
pytest tests -v -n auto -m "not slow"

# 4개 워커로 병렬 실행
pytest tests -v -n 4 -m "not slow"
```

### 3.4. 커버리지 리포트

```bash
# 커버리지 측정
pytest tests -v --cov=src --cov-report=html

# 결과 확인
open htmlcov/index.html
```

---

## 4. 문제 해결

### 4.1. 테스트가 멈추는 경우

**증상**: 특정 테스트에서 무한 대기

**원인**:
- AI 서버가 응답하지 않음
- 네트워크 타임아웃 설정 부족
- `slow` 테스트가 실제로 오래 걸림

**해결**:
```bash
# 1. Ctrl+C로 중단
# 2. slow 테스트 제외하고 재실행
pytest tests -v -m "not slow" --timeout=30

# 3. 특정 파일만 실행
pytest tests/units -v
```

### 4.2. Docker 테스트 ERROR

**증상**: `test_docker_*.py` 테스트가 모두 ERROR

**원인**: Docker 컨테이너가 실행되지 않음

**해결**:
```bash
# Docker 테스트 제외
pytest tests -v --ignore=tests/nanoCocoa_mcpserver/test_docker_integration.py \
              --ignore=tests/nanoCocoa_mcpserver/test_docker_simple.py

# 또는 마커로 제외
pytest tests -v -m "not docker"
```

### 4.3. AI 서버 연결 실패

**증상**: `require_aiserver` 테스트가 SKIPPED

**원인**: AI 서버(8000 포트)가 실행되지 않음

**확인**:
```bash
# 서버 상태 확인
curl http://localhost:8000/health

# 서버 실행 확인
ps aux | grep uvicorn
```

**해결**:
```bash
# AI 서버 시작
cd src/nanoCocoa_aiserver
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# 또는 통합 테스트 제외
pytest tests -v -m "not integration"
```

### 4.4. Import 에러

**증상**: `ModuleNotFoundError: No module named 'nanoCocoa_aiserver'`

**원인**: 프로젝트 루트가 아닌 곳에서 실행

**해결**:
```bash
# 프로젝트 루트로 이동
cd /home/spai0433/codeit-ai-3team-ad-content

# 다시 실행
pytest tests -v
```

### 4.5. 경고 메시지가 많은 경우

```bash
# 경고 숨기기
pytest tests -v --disable-warnings

# 특정 경고만 숨기기
pytest tests -v -W ignore::DeprecationWarning
```

---

## 5. 권장 실행 방식

### 5.1. 개발 중 (로컬)

```bash
# 빠른 테스트만 실행
pytest tests/units -v --timeout=30
```

### 5.2. PR 전 (통합 테스트)

```bash
# AI 서버 시작 후
pytest tests -v -m "not slow and not docker" --timeout=60
```

### 5.3. CI/CD

```bash
# 전체 테스트 (타임아웃 있음)
pytest tests -v --timeout=300 --maxfail=10
```

### 5.4. 디버깅

```bash
# 특정 테스트만 verbose 모드로
pytest tests/units/test_api_scenarios.py::test_step1_bg_generation -vv -s

# 첫 번째 실패에서 중단
pytest tests -v --maxfail=1 -x
```

---

## 6. 예제 명령어

```bash
# ✅ 일반적인 경우 (빠른 테스트만)
pytest tests -v -m "not slow and not docker"

# ✅ CI/CD (타임아웃 포함)
pytest tests -v --timeout=300 -m "not docker"

# ✅ 단위 테스트만
pytest tests/units -v

# ✅ 특정 파일
pytest tests/units/test_api_scenarios.py -v

# ✅ 병렬 실행 (빠른 테스트만)
pytest tests -v -n auto -m "not slow and not docker"

# ❌ 피해야 할 실행 (느림, 멈출 수 있음)
pytest tests -v  # slow, docker 포함
```

---

## 7. 참고 자료

- [pytest 공식 문서](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [pytest-timeout](https://github.com/pytest-dev/pytest-timeout)
- [pytest 마커 가이드](https://docs.pytest.org/en/stable/example/markers.html)
