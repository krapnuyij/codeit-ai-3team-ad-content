# CODEIT AI 3팀 - SaaS Ad Content Platform

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-teal)
![PyTorch](https://img.shields.io/badge/PyTorch-2.0-orange)
![Docker](https://img.shields.io/badge/Docker-Compose-blue)

**생성형 AI 기술을 활용하여 소상공인이 광고 콘텐츠(배너, 홈페이지)를 손쉽게 제작할 수 있도록 돕는 자동화 플랫폼입니다.**
오프라인 중심의 소상공인이 복잡한 과정 없이 온라인 마케팅을 시작할 수 있도록, 광고 문구, 이미지, 그리고 랜딩 페이지까지 All-in-One으로 생성합니다.

---

## 👥 팀 구성 및 역할

| 이름 | 역할 | 담당 업무 |
|---|---|---|
| **김명환** | 아키텍처/Data | 시스템 아키텍처 설계, 데이터 파이프라인 구성, 모델 관리 서버 설계 |
| **김민혁** | AI Modeling | 텍스트 생성 및 조합 모델 개발, 프롬프트 엔지니어링 |
| **박지윤** | PM | 프로젝트 관리, 일정 조율, 기획, GCP 인프라 구축 |
| **이건희** | Full Stack | 백엔드(FastAPI), 프론트엔드(Jinja2/HTML) |
| **이슬형** | AI Modeling | 이미지 특성 추출, 이미지 생성 모델 최적화 |

---

## 🏗️ 시스템 아키텍처

이 프로젝트는 **Microservices Architecture**를 채택하여 각 기능이 독립적인 컨테이너로 동작하며, Docker Compose를 통해 통합 관리됩니다.

![System Architecture](architecture_view.png)

### 주요 서비스 구성

1.  **SaaS Backend (`backend/`)**
    -   **역할**: 사용자 인터페이스(Web) 제공 및 전체 서비스 조율 (Orchestrator).
    -   **Tech**: FastAPI, Jinja2 Templates, SQLAlchemy.
    -   **Port**: `8890`
    -   사용자의 입력을 받아 DB에 저장하고, 각 AI 서버에 작업을 요청한 뒤 결과를 보여줍니다.

2.  **Homepage Generator (`homepage_generator/`)**
    -   **역할**: 맞춤형 랜딩 페이지 제작 에이전트.
    -   **Tech**: FastAPI, LangGraph.
    -   **Port**: `8891`
    -   기획 -> 디자인 -> 코딩 순서로 진행되는 AI 에이전트 워크플로우를 통해 완전한 정적 웹사이트를 생성합니다.

3.  **NanoCocoa AI Server (`nanoCocoa_aiserver/`)**
    -   **역할**: 고품질 광고 배너 이미지 생성.
    -   **Tech**: FastAPI, PyTorch (CUDA), Diffusers, OpenAI API.
    -   **Port**: `8892`
    -   텍스트 렌더링 및 상품 이미지 합성을 위한 전용 GPU 서버입니다.

4.  **Infrastructure**
    -   **Database**: PostgreSQL (고객 정보 및 생성 이력 관리).
    -   **Web Server**: Nginx (생성된 홈페이지 호스팅).

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
