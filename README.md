# CODEIT AI 3팀 - SaaS Ad Content Platform

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-teal)
![PyTorch](https://img.shields.io/badge/PyTorch-2.0-orange)
![Docker](https://img.shields.io/badge/Docker-Compose-blue)

**생성형 AI 기술을 활용하여 소상공인이 광고 콘텐츠(배너, 홈페이지)를 손쉽게 제작할 수 있도록 돕는 자동화 플랫폼입니다.**
오프라인 중심의 소상공인이 복잡한 과정 없이 온라인 마케팅을 시작할 수 있도록, 광고 문구, 이미지, 그리고 랜딩 페이지까지 All-in-One으로 생성합니다.

## 📢 발표 자료

**최종 결과 ppt**: [최종 발표자료 다운로드 (PDF)](./3팀_나노코코아_최종발표자료.pdf)

**시연 영상**: [발표자료/코드잇AI엔지니어4기_3팀_테스트동영상_260123_141208-c.mp4](https://krapnuyij.github.io/codeit-ai-3team-ad-content/발표자료/코드잇AI엔지니어4기_3팀_테스트동영상_260123_141208-c.mp4)<br/>
<video src="https://krapnuyij.github.io/codeit-ai-3team-ad-content/발표자료/코드잇AI엔지니어4기_3팀_테스트동영상_260123_141208-c.mp4" controls width="320"></video>

---

## 👥 팀 구성 및 역할

| 이름 | 역할 | 담당 업무 |
|---|---|---|
| **김명환** | 아키텍처/Data | 시스템 아키텍처 설계, 데이터 파이프라인 구성, 모델 관리 서버 설계 |
| **김민혁** | AI Modeling | 텍스트 생성 및 조합 모델 개발, 프롬프트 엔지니어링 |
| **박지윤** | PM | 프로젝트 관리, 일정 조율, 기획, GCP 인프라 구축 |
| **이건희** | Full Stack | 백엔드(FastAPI), 프론트엔드(Jinja2/HTML) |
| **이솔형** | AI Modeling | 이미지 특성 추출, 이미지 생성 모델 최적화 |

## 📝 협업일지

팀원별 개발 과정 및 학습 내용을 기록한 협업일지입니다.

- [김명환 협업일지 (아키텍처 & 파이프라인)](https://krapnuyij.github.io/codeit-ai-3team-ad-content/협업일지/김명환/)
- [김민혁 협업일지 (텍스트 생성 및 조합 모델 개발)](https://krapnuyij.github.io/codeit-ai-3team-ad-content/협업일지/김민혁/)
- [박지윤 협업일지 (PM & 기획)](https://krapnuyij.github.io/codeit-ai-3team-ad-content/협업일지/박지윤/)
- [이건희 협업일지 (백엔드 & 프론트엔드)](https://krapnuyij.github.io/codeit-ai-3team-ad-content/협업일지/이건희/)
- [이솔형 협업일지 (이미지 특성 추출 및 이미지 생성)](https://krapnuyij.github.io/codeit-ai-3team-ad-content/협업일지/이솔형/)

---

## 🏗️ 시스템 아키텍처

이 프로젝트는 **Microservices Architecture**를 채택하여 각 기능이 독립적인 컨테이너로 동작하며, Docker Compose를 통해 통합 관리됩니다.

**구조도 (High-Level Architecture)**

```mermaid
graph TB
    subgraph "사용자 환경"
        User["사용자 (소상공인)"]
        LLMClient["LLM / GPT
(MCP 클라이언트)"]
    end

    subgraph "Docker Network: nanococoa-network"
        subgraph "백엔드 계층 (backend)"
            Backend["FastAPI 서버
비즈니스 로직
Port: 8080"]
            HPGen["Homepage Generator
LangGraph + Multi-Agent
Port: 8081"]
            DB[("PostgreSQL
고객 데이터")]
        end

        subgraph "MCP 서버 (nanoCocoa_mcpserver)"
            MCPServer["MCP 서버
MCP Protocol Bridge
Port: 3000"]
        end

        subgraph "모델서빙 계층 (nanoCocoa_aiserver)"
            ModelServer["FastAPI 모델 서버
Port: 8000"]

            subgraph "AI 모델 파이프라인"
                BiRefNet["BiRefNet
(이미지 누끼)"]
                FLUX["FLUX.1-dev
(배경 생성)"]
                Qwen["Qwen2-VL
(이미지 분석)"]
            end

            LLMText["OpenAI API
(HTML/CSS 생성)"]
            GPU["NVIDIA L4 GPU
24GB VRAM"]
        end
    end

    User -->|HTTP/웹| Backend
    Backend --> DB
    Backend --> HPGen
    HPGen -->|HTTP| MCPServer
    Backend -->|"REST API
Port 8000"| ModelServer
    
    LLMClient -.->|"MCP Protocol
(SSE)"| MCPServer
    MCPServer -->|"REST API
Internal Network"| ModelServer
    
    ModelServer --> BiRefNet
    ModelServer --> FLUX
    ModelServer --> Qwen
    ModelServer --> LLMText
    
    BiRefNet -.->|JIT 로딩| GPU
    FLUX -.->|JIT 로딩| GPU
    Qwen -.->|JIT 로딩| GPU
```

**시퀀스 다이어그램**

```mermaid
sequenceDiagram
    participant User as 사용자
    participant FE as 프론트엔드 (FastAPI)
    participant BE as 백엔드 (FastAPI)
    participant LLM as OpenAI GPT-5-mini
    participant MS as 모델서빙 (FastAPI)
    participant GPU as L4 GPU

    User->>FE: 1. 이미지 업로드 + 광고 문구 입력
    FE->>FE: 2. 입력 검증
    FE->>BE: 3. POST /api/generate {image, text, options}

    BE->>BE: 4. 요청 검증
    BE->>LLM: 5. 프롬프트 생성 요청 "건어물 대박 세일"
    LLM-->>BE: 6. 영문 프롬프트 반환 "Dried seafood..."

    BE->>MS: 7. POST /generate {product_image, bg_prompt, text_content}
    MS->>MS: 8. Job ID 생성 Worker Process 생성
    MS-->>BE: 9. {job_id, status: "started"}
    BE-->>FE: 10. {job_id}
    FE-->>User: 11. "생성 중..." 표시

    loop 진행 상황 폴링 (Polling)
        FE->>BE: 12. GET /api/status/{job_id}
        BE->>MS: 13. GET /status/{job_id}

        MS->>MS: Stage 1 실행
        MS->>GPU: BiRefNet 로드
        GPU-->>MS: 누끼 이미지
        MS->>GPU: FLUX.1-dev 로드
        GPU-->>MS: 배경 이미지
        MS->>MS: 합성 및 리터칭

        MS-->>BE: 14. {status: "running", progress: 50%, step1_result}
        BE-->>FE: 15. {progress, step1_preview}
        FE-->>User: 16. 진행률 + 중간 결과 표시

        MS->>MS: Stage 2 실행
        
        alt use_qwen_analysis=true
            MS->>GPU: Qwen2-VL 로드
            GPU-->>MS: 이미지 분석 텍스트
            MS->>GPU: Qwen2-VL 언로드
        end
        
        MS->>LLM: HTML/CSS 생성 요청 (Qwen 분석 포함)
        LLM-->>MS: HTML/CSS 코드
        MS->>MS: HTML 렌더링 (Headless Browser)
        MS->>MS: 텍스트 레이어 합성

        MS-->>BE: 17. {status: "completed", final_result}
        BE-->>FE: 18. {status: "done", final_image}
    end

    FE-->>User: 19. 최종 결과 표시 + 다운로드 버튼
```

---

## 🚀 실행 방법

### 1. 사전 준비 (Prerequisites)
- [Docker](https://www.docker.com/products/docker-desktop/) 설치
- NVIDIA GPU 권장 (AI 이미지 생성 속도 향상 위함)
    - GPU 사용 시 `nvidia-container-toolkit` 설정 필요.

### 2. 환경 변수 설정
`src/.env` 파일을 생성하고 아래 내용을 작성하세요. (보안상 실제 키는 제외됨)

```env
# Database
POSTGRES_USER=owner
POSTGRES_PASSWORD=owner1234
POSTGRES_DB=customer_db

# External APIs (필수)
OPENAI_API_KEY=sk-proj-...
HF_TOKEN=hf_...

# Internal Network URLs (Docker Service Names)
DATABASE_URL=postgresql://owner:owner1234@customer_db:5432/customer_db
HOMEPAGE_GENERATOR_URL=http://homepage_generator:8891
NANOCOCOA_URL=http://nanococoa_aiserver:8892
```

### 3. 서비스 실행
`src` 폴더 위치에서 터미널을 열고 실행합니다.

```bash
# 실행 (이미지 빌드 포함)
docker-compose up --build

# 백그라운드 실행 시
docker-compose up --build -d
```

### 4. 접속 정보

| 서비스 | URL | 설명 |
|---|---|---|
| **메인 웹 서비스** | [http://localhost:8890](http://localhost:8890) | 사용자 대시보드 및 작업 요청 |
| **생성된 홈페이지** | [http://localhost:8893/sites/...](http://localhost:8893) | 결과물 확인 (경로는 생성 후 제공됨) |
| **API Docs (Backend)** | [http://localhost:8890/docs](http://localhost:8890/docs) | 백엔드 API 문서 |
| **API Docs (AI)** | [http://localhost:8892/docs](http://localhost:8892/docs) | AI 서버 API 문서 |

---

## 🧪 테스트 실행

### 간편 스크립트 사용 (권장)

```bash
# 전체 테스트 (dummy 모드 - GPU 미사용)
./tests/run_tests.sh

# 빠른 테스트만
./tests/run_tests.sh --fast

# 실제 AI 엔진으로 테스트 (GPU 필요)
./tests/run_tests.sh --real

# 도움말
./tests/run_tests.sh --help
```

### pytest 직접 실행

**기본 테스트 (Dummy 모드)**

```bash
# 전체 테스트 실행 (GPU 미사용, 빠른 인터페이스 테스트)
pytest tests -v

# 빠른 테스트만 (slow, docker 제외)
pytest tests -v -m "not slow and not docker"

# 단위 테스트만
pytest tests/units -v
```

**실제 AI 엔진 테스트 (GPU 필요)**

```bash
# 실제 AI 모델로 테스트 (GPU 필요)
pytest tests -v --no-dummy

# 특정 파일만 실제 엔진으로
pytest tests/units/test_api_scenarios.py -v --no-dummy
```

**마커별 실행**

```bash
# 단위 테스트만
pytest tests -v -m "unit"

# 통합 테스트만 (AI 서버 실행 필요)
pytest tests -v -m "integration"

# slow 테스트 제외
pytest tests -v -m "not slow"
```

자세한 테스트 가이드는 [TEST_GUIDE.md](docs/doc/TEST_GUIDE.md)를 참조하세요.

---

## 📂 디렉토리 구조 상세

```
src/
├── backend/                # 메인 웹 애플리케이션
│   ├── templates/          # Jinja2 HTML 템플릿
│   ├── static/             # CSS, JS, Images
│   └── app.py              # 메인 실행 파일
├── homepage_generator/     # 홈페이지 생성 에이전트
│   ├── nodes/              # LangGraph 노드 (기획, 디자인 등)
│   └── api.py              # API 엔드포인트
├── nanoCocoa_aiserver/     # 이미지 생성 모델 서버
│   ├── models/             # AI 모델 관련 코드
│   └── main.py             # 실행 파일
├── docker-compose.yaml     # 통합 실행 설정
└── README.md               # 프로젝트 설명 (현재 파일)
```
