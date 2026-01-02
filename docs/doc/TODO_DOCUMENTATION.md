---
layout: default
title: "문서화 TODO (모든 기능 완성 후 작업)"
description: "문서화 TODO (모든 기능 완성 후 작업)"
date: 2026-01-02
author: "김명환"
cache-control: no-cache
expires: 0
pragma: no-cache
---

# 문서화 TODO (모든 기능 완성 후 작업)

## 1. pytest 실행 옵션 가이드

### 1.1. 현재 설정 상태
- 기본 모드: dummy (GPU 미사용, 빠른 인터페이스 테스트)
- 실제 엔진 모드: `--no-dummy` 옵션으로 활성화

### 1.2. 문서화 필요 항목

#### 1. README 또는 tests/README.md 업데이트
- [ ] pytest 실행 옵션 섹션 추가
  ```bash
  # 기본 실행 (dummy 모드 - GPU 미사용)
  pytest
  
  # 실제 AI 엔진 사용 (GPU 필요)
  pytest --no-dummy
  
  # 마커 활용
  pytest -m unit          # 단위 테스트만
  pytest -m integration   # 통합 테스트만
  pytest -m slow          # 느린 테스트만
  pytest -m dummy         # dummy 마커 테스트만
  
  # 특정 테스트 파일 실행
  pytest tests/units/test_font_manager.py
  
  # 병렬 실행 (pytest-xdist 필요)
  pytest -n auto
  ```

#### 2. CI/CD 파이프라인 스크립트 확인 및 업데이트
- [ ] `.github/workflows/*.yml` 또는 CI 설정 파일 확인
- [ ] dummy 기본값 변경에 따른 스크립트 조정
  - CI에서는 dummy 모드 유지할지 결정
  - GPU 환경에서는 `--no-dummy` 사용 여부 결정

#### 3. `run_tests.sh` 스크립트 검토
- [ ] 현재 스크립트에 주석 추가
- [ ] dummy/실제 엔진 모드 선택 옵션 추가 고려
  ```bash
  # 예시:
  # ./run_tests.sh          # 기본 dummy 모드
  # ./run_tests.sh --real   # 실제 엔진 모드
  ```

#### 4. conftest.py 주석 업데이트
- [x] `pytest_addoption` docstring 업데이트 완료
- [x] `dummy_mode` fixture docstring 업데이트 완료

#### 5. 테스트 타임아웃 최적화
- [x] 멀티프로세싱 워커 폴링 타임아웃: 5초 → 30초로 증가 완료
- [ ] 실제 엔진 모드에서 타임아웃 조정 필요 여부 검토

## 완료된 작업

### 2026-01-01
1. ✅ `conftest.py` 수정
   - `--dummy` 옵션 기본값: `False` → `True`
   - `--no-dummy` 옵션 추가
   - docstring 업데이트

2. ✅ `test_api_scenarios.py` 수정
   - `test_red_rose_generation` 폴링 타임아웃: 5초 → 30초
   - `test_kindergarten_ad_generation` 폴링 타임아웃: 5초 → 30초
   - 완료 상태에 `error` 추가
   - 더 나은 에러 메시지 제공

3. ✅ 테스트 검증
   - 전체 테스트 스위트: 41 passed, 1 skipped
   - dummy 모드가 기본으로 정상 작동 확인

## 참고 사항

### 실제 파이프라인 vs pytest 기본값 차이
- **pytest 기본값**: dummy 모드 (개발/테스트 최적화)
- **실제 프로덕션 파이프라인**: 실제 엔진 사용 (API의 `test_mode` 기본값은 `False`)
- 이 차이는 의도된 것임: 테스트는 빠르게, 프로덕션은 실제 모델 사용

### conda 환경
- 반드시 `py311_ad` conda 환경 활성화 필요
- 명령어: `conda activate py311_ad`
