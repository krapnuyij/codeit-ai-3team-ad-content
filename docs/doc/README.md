# 문서 목차

nanoCocoa AI 광고 생성기 프로젝트의 기술 문서 모음입니다.

## 1. 설치 및 설정

### 1.1. [환경설정_가이드.md](환경설정_가이드.md)
크로스 플랫폼 (Windows, Linux, macOS) 환경 설정 가이드입니다.
- Conda 환경 설정
- pip 패키지 설치
- 플랫폼별 주의사항
- 문제 해결 방법

### 1.2. [완전한_설치_가이드.md](완전한_설치_가이드.md)
FastAPI 서버와 MCP 서버의 완전한 설치 및 설정 가이드입니다.
- 아키텍처 개요
- FastAPI 서버 설치 및 실행
- MCP 서버 설정
- 테스트 방법
- 문제 해결

### 1.3. [MCP서버_사용가이드.md](MCP서버_사용가이드.md)
MCP (Model Context Protocol, 모델 컨텍스트 프로토콜) 서버 사용 가이드입니다.
- MCP 도구 설명
- 설치 방법
- 예시 워크플로우
- API 엔드포인트 매핑
- 모범 사례

### 1.4. [GCP_VM_접속가이드.md](GCP_VM_접속가이드.md)
Google Cloud Platform VM 접속 가이드입니다.

## 2. 아키텍처 및 설계

### 2.1. [아키텍처설계.md](아키텍처설계.md)
전체 시스템 아키텍처 설계 문서입니다.

### 2.2. [nanoCocoa_AI_Server_아키텍처설계.md](nanoCocoa_AI_Server_아키텍처설계.md)
nanoCocoa AI 서버의 상세 아키텍처 설계 문서입니다.

### 2.3. [고급_프로젝트_수행_계획_및_환경_검토_보고서.md](고급_프로젝트_수행_계획_및_환경_검토_보고서.md)
프로젝트 수행 계획 및 환경 검토 보고서입니다.

## 3. 리팩토링 및 개선

### 3.1. [REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md)
소스 코드 리팩토링 완료 요약입니다.
- 모듈 분리
- API 구조 개선
- 에러 처리 강화
- 테스트 확장
- 배포 체크리스트

### 3.2. [REFACTORING_REPORT.md](REFACTORING_REPORT.md)
소스 코드 리팩토링 상세 보고서입니다.
- main.py 라우터 분리
- schemas.py 도메인별 분리
- 개선 효과 및 통계

## 4. 개발 문서

### 4.1. [TODO_DOCUMENTATION.md](TODO_DOCUMENTATION.md)
문서화 작업 목록 및 pytest 실행 옵션 가이드입니다.

## 5. 구현 상세

MCP 서버 구현에 대한 상세 내용은 소스 디렉토리를 참조하세요:
- [src/nanoCocoa_aiserver/MCP_IMPLEMENTATION_SUMMARY.md](../../src/nanoCocoa_aiserver/MCP_IMPLEMENTATION_SUMMARY.md)

