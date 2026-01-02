# nanoCocoa MCP 서버 - 구현 요약

## 1. 프로젝트 개요

nanoCocoa AI 광고 생성 서버를 위한 MCP (Model Context Protocol, 모델 컨텍스트 프로토콜) 서버 구현이 완료되었습니다.
LLM (Large Language Model, 대규모 언어 모델) Claude 등이 REST API를 통해 AI 광고 이미지를 생성할 수 있도록 표준화된 인터페이스를 제공합니다.

## 2. 구현된 기능

### 2.1. REST API 확장

기존 FastAPI에 다음 엔드포인트 (endpoint, 엔드포인트)를 추가했습니다:

#### 2.1.1. 새로 추가된 엔드포인트

| 엔드포인트 | 메서드 | 설명 | 파일 |
|-----------|--------|------|------|
| `GET /jobs` | GET | 모든 작업 목록 조회 | [generation.py:224](api/routers/generation.py#L224) |
| `DELETE /jobs/{job_id}` | DELETE | 완료/실패한 작업 삭제 | [generation.py:279](api/routers/generation.py#L279) |
| `GET /health` | GET | 서버 상태 및 GPU 메트릭 | [resources.py:54](api/routers/resources.py#L54) |
| `GET /help` | GET | 전체 API 사용 가이드 | [help.py:16](api/routers/help.py#L16) |
| `GET /help/parameters` | GET | 파라미터 레퍼런스 | [help.py:184](api/routers/help.py#L184) |
| `GET /help/examples` | GET | 실전 사용 예시 | [help.py:600](api/routers/help.py#L600) |

#### 2.1.2. 기존 엔드포인트 (변경 없음)

- `POST /generate` - 광고 생성 작업 시작
- `GET /status/{job_id}` - 작업 상태 조회
- `POST /stop/{job_id}` - 작업 중단
- `GET /fonts` - 사용 가능한 폰트 목록

### 2.2. MCP Server 구현

파일: [mcp_server.py](mcp_server.py)

#### 2.2.1. 제공되는 MCP Tools

| Tool 이름 | 설명 | 비동기 |
|-----------|------|--------|
| `health_check` | 서버 상태 및 GPU 메트릭 확인 | ✓ |
| `list_fonts` | 사용 가능한 폰트 목록 | ✓ |
| `generate_ad` | 광고 생성 작업 시작 (non-blocking) | ✓ |
| `check_job_status` | 작업 진행 상태 및 결과 조회 | ✓ |
| `stop_job` | 실행 중인 작업 강제 중단 | ✓ |
| `list_jobs` | 모든 작업 목록 조회 | ✓ |
| `delete_job` | 완료된 작업 메모리에서 삭제 | ✓ |
| `generate_and_wait` | 생성 후 완료까지 대기 (blocking) | ✓ |

#### 2.2.2. 제공되는 MCP Resources

| Resource URI | 설명 |
|--------------|------|
| `nanococoa://help/guide` | 완전한 API 사용 가이드 |
| `nanococoa://help/parameters` | 파라미터 (parameter, 파라미터) 상세 레퍼런스 |
| `nanococoa://help/examples` | 코드 예시 및 워크플로우 (workflow, 워크플로우) |

### 2.3. 문서화

다음 문서들이 생성되었습니다:

- **[README_MCP.md](README_MCP.md)**: MCP 서버 개요 및 기본 사용법
- **[SETUP_GUIDE.md](SETUP_GUIDE.md)**: 완전한 설치 및 설정 가이드
- **[MCP_IMPLEMENTATION_SUMMARY.md](MCP_IMPLEMENTATION_SUMMARY.md)**: 이 문서 (구현 요약)

### 4. 테스트 도구

**파일**: [test_mcp_server.py](test_mcp_server.py)

MCP 서버의 모든 기능을 테스트하는 스크립트:
- Tools 목록 확인
- Resources 목록 확인
- 각 엔드포인트 호출 테스트
- 실제 작업 생성 및 상태 확인 (옵션)

### 5. 설정 파일

- **[mcp_config.json](mcp_config.json)**: MCP 서버 설정 예시
- **[requirements_mcp.txt](requirements_mcp.txt)**: MCP 서버 의존성

---

## 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                     LLM Client Layer                         │
│                  (Claude Desktop, etc.)                      │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            │ MCP Protocol (stdio)
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                     MCP Server Layer                         │
│                      mcp_server.py                           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Tools:                                               │   │
│  │  - health_check, list_fonts, generate_ad            │   │
│  │  - check_job_status, stop_job, list_jobs            │   │
│  │  - delete_job, generate_and_wait                    │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Resources:                                           │   │
│  │  - nanococoa://help/guide                           │   │
│  │  - nanococoa://help/parameters                      │   │
│  │  - nanococoa://help/examples                        │   │
│  └──────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            │ HTTP REST (httpx)
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                   FastAPI Server Layer                       │
│                    api/app.py, main.py                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Routers:                                             │   │
│  │  - generation: /generate, /status, /stop, /jobs     │   │
│  │  - resources: /fonts, /health                       │   │
│  │  - help: /help, /help/parameters, /help/examples    │   │
│  └──────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            │ Function Calls
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    Core Engine Layer                         │
│                         core/                                │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ - engine.py: AI model orchestration                 │   │
│  │ - processors.py: Step processing logic              │   │
│  │ - worker.py: Background job execution               │   │
│  └──────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            │ Model Loading & Inference
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                      AI Models Layer                         │
│                        models/                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ - BiRefNet: Background removal                      │   │
│  │ - FLUX: Image generation & inpainting               │   │
│  │ - SDXL ControlNet: 3D text generation               │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 파일 구조

```
src/nanoCocoa_aiserver/
├── api/
│   ├── app.py                    # FastAPI 앱 초기화
│   ├── middleware.py             # 미들웨어
│   └── routers/
│       ├── generation.py         # ✨ 작업 관리 엔드포인트 (확장됨)
│       ├── resources.py          # ✨ 리소스 엔드포인트 (확장됨)
│       ├── help.py               # ✨ 새로 추가: Help 엔드포인트
│       └── dev_dashboard.py      # 개발 대시보드
├── core/
│   ├── engine.py                 # AI 모델 엔진
│   ├── processors.py             # 단계 처리기
│   └── worker.py                 # 워커 프로세스
├── models/                       # AI 모델 구현
├── services/                     # 비즈니스 로직
├── schemas/                      # Pydantic 스키마
├── utils/                        # 유틸리티
├── mcp_server.py                 # ✨ 새로 추가: MCP 서버
├── test_mcp_server.py            # ✨ 새로 추가: MCP 테스트
├── requirements_mcp.txt          # ✨ 새로 추가: MCP 의존성
├── mcp_config.json               # ✨ 새로 추가: MCP 설정
├── README_MCP.md                 # ✨ 새로 추가: MCP 문서
├── SETUP_GUIDE.md                # ✨ 새로 추가: 설치 가이드
├── MCP_IMPLEMENTATION_SUMMARY.md # ✨ 새로 추가: 구현 요약
├── main.py                       # FastAPI 실행 엔트리포인트
└── config.py                     # 설정 파일
```

---

## 사용 방법

### 1. FastAPI 서버 시작

```bash
cd src/nanoCocoa_aiserver
python main.py
```

서버가 `http://localhost:8000`에서 실행됩니다.

### 2. MCP 서버 설정 (Claude Desktop)

Claude Desktop 설정 파일에 추가:

**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "nanococoa-ad-generator": {
      "command": "python",
      "args": [
        "D:\\project\\codeit-ai-3team-ad-content\\src\\nanoCocoa_aiserver\\mcp_server.py"
      ],
      "env": {
        "API_BASE_URL": "http://localhost:8000"
      }
    }
  }
}
```

### 3. Claude Desktop 재시작

설정 후 Claude Desktop을 재시작하면 MCP 서버 도구를 사용할 수 있습니다.

### 4. 테스트

```bash
# MCP 서버 테스트
python test_mcp_server.py

# REST API 테스트
curl http://localhost:8000/health
curl http://localhost:8000/help
```

---

## LLM 사용 예시

### 예시 1: 기본 광고 생성

```
User: 커피 제품 광고를 만들어줘. 배경은 아늑한 카페로

Claude: [Uses health_check → list_fonts → generate_and_wait]

제품 이미지를 업로드해주세요.

User: [Uploads coffee.png]

Claude: 광고를 생성하고 있습니다...
- 배경: 아늑한 모던 카페 인테리어
- 텍스트: Fresh Brew
- 스타일: 브라운 3D 텍스트

[90초 후]
광고 생성 완료! [Shows image]
```

### 예시 2: 텍스트 스타일 변경

```
User: 텍스트를 골드 메탈릭으로 바꿔줘

Claude: [Uses generate_ad with start_step=2]

이전 배경을 재사용하여 텍스트만 새로 생성합니다...

[35초 후]
텍스트 스타일 변경 완료!
```

---

## 주요 기능

### LLM이 쉽게 이해할 수 있는 설계

1. **명확한 Tool 설명**: 각 tool은 상세한 설명과 파라미터 안내 포함
2. **풍부한 Documentation**: `/help` 엔드포인트로 실시간 가이드 제공
3. **단계별 워크플로우**: 복잡한 파이프라인을 간단한 단계로 분리
4. **에러 처리 가이드**: 일반적인 에러와 해결 방법 문서화

### 개발자 친화적

1. **완전한 REST API**: MCP 없이도 직접 API 호출 가능
2. **테스트 도구**: `test_mcp_server.py`로 모든 기능 검증
3. **상세한 문서**: Setup 가이드, 파라미터 레퍼런스, 예시 코드
4. **OpenAPI 스키마**: `/docs`에서 인터랙티브 문서 확인

### 프로덕션 준비

1. **Health Check**: 서버 상태 및 GPU 메트릭 실시간 모니터링
2. **Job Management**: 작업 목록 조회 및 삭제로 메모리 관리
3. **에러 처리**: 503 Busy 응답, Retry-After 헤더 제공
4. **Progress Tracking**: 실시간 진행률 및 ETA 제공

---

## 성능

### 예상 처리 시간 (Nvidia L4)

- **Step 1 (배경)**: ~80초
- **Step 2 (텍스트)**: ~35초
- **Step 3 (합성)**: ~5초
- **전체 파이프라인**: ~120초

### 동시성

- **단일 작업 정책**: 한 번에 하나의 작업만 처리
- **Busy 응답**: 진행 중일 때 503 + Retry-After 헤더
- **큐 없음**: 리소스 과부하 방지

---

## 의존성

### FastAPI Server

- fastapi, uvicorn
- torch, diffusers, transformers
- pillow, opencv-python
- pynvml, psutil

### MCP Server

- mcp (Model Context Protocol SDK)
- httpx (HTTP client)

---

## 다음 단계

### 완료된 작업 ✅

1. REST API 검토 및 확장
2. Job 관리 엔드포인트 추가
3. Health check 엔드포인트 추가
4. Help/Documentation 엔드포인트 추가
5. MCP 서버 구현
6. 테스트 스크립트 작성
7. 완전한 문서화

### 선택적 개선 사항 (향후)

1. ⭐ **이미지 캐싱**: 중간 결과물 자동 저장
2. ⭐ **배치 처리**: 여러 텍스트 버전 동시 생성
3. ⭐ **프리셋 관리**: 자주 사용하는 스타일 저장
4. ⭐ **웹훅 지원**: 작업 완료 시 알림
5. ⭐ **메트릭 대시보드**: 사용 통계 및 모니터링

---

## 문제 해결

### MCP 서버가 연결되지 않을 때

1. FastAPI 서버가 `http://localhost:8000`에서 실행 중인지 확인
2. `claude_desktop_config.json`의 경로가 절대 경로인지 확인
3. Claude Desktop 재시작
4. 로그 확인: `%APPDATA%\Claude\logs`

### GPU 메모리 부족

1. 다른 GPU 애플리케이션 종료
2. `nvidia-smi`로 메모리 상태 확인
3. 현재 작업 완료 대기 (단일 작업 정책)

### 작업이 너무 오래 걸릴 때

1. `/health`로 시스템 상태 확인
2. GPU가 사용되고 있는지 확인 (CPU fallback 아님)
3. 품질 파라미터 조정 (steps, strength 낮춤)

---

## 연락처

- **Email**: c0z0c.dev@gmail.com
- **Project**: codeit-ai-3team-ad-content
- **Location**: `d:\project\codeit-ai-3team-ad-content\src\nanoCocoa_aiserver`

---

## 라이선스

nanoCocoa AI Ad Generator 프로젝트의 일부입니다.

---

**구현 완료 날짜**: 2026-01-01
**버전**: 2.0.0
**Status**: Production Ready
