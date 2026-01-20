# AI 광고 생성 시스템 (Streamlit + MongoDB + MCP)

Streamlit 기반 AI 광고 생성 웹 애플리케이션입니다.

## 주요 기능

- **대화형 광고 기획**: OpenAI API를 통한 자연어 대화로 광고 컨셉 구상
- **비동기 작업 처리**: MCP 서버로 장시간 소요 작업 요청 (15~30분)
- **작업 모니터링**: 실시간 진행률 확인 및 결과 조회
- **히스토리 관리**: MongoDB 기반 작업 이력 저장 및 조회

## 프로젝트 구조

```
src/ad_chat/
├── app.py                   # 메인 실행 파일 (라우팅 및 진입점)
├── config.py                # 환경 설정 (상수, URL 등)
├── requirements.txt         # 의존성 목록
├── services/                # 비즈니스 로직 계층
│   ├── __init__.py          # mcpadapter.MCPClient, LLMAdapter import
│   └── mongo_service.py     # MongoDB CRUD
├── ui/                      # UI 컴포넌트 계층
│   ├── __init__.py
│   ├── auth_ui.py           # API Key 입력 화면
│   ├── chat_ui.py           # 채팅 및 생성 요청 인터페이스
│   └── history_ui.py        # 작업 목록, 진행률, 결과 조회 화면
└── utils/                   # 유틸리티
    ├── __init__.py
    └── state_manager.py     # Session State 관리
```

## 설치 및 실행

### 1. mcpadapter 설치 (필수)

```bash
# 프로젝트 루트에서 실행
pip install -e src/mcpadapter
```

### 2. 의존성 설치

```bash
cd src/ad_chat
pip install -r requirements.txt
```

### 3. 환경 변수 설정

프로젝트 루트에 `.env` 파일 생성:

```env
# OpenAI API
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5-mini

# MCP 서버
MCP_SERVER_URL=http://34.44.205.198:3000
MCP_TIMEOUT=30

# MongoDB
MONGO_URI=mongodb://localhost:27017/
MONGO_DB_NAME=ai_ad_generator

# 폴링 설정
POLLING_INTERVAL=10
POLLING_MAX_ATTEMPTS=180
```

### 4. MongoDB 실행

로컬 MongoDB 실행:

```bash
# Docker 사용 시
docker run -d -p 27017:27017 --name mongodb mongo:latest

# 또는 MongoDB Atlas 클라우드 사용 (MONGO_URI 변경)
```

### 5. 애플리케이션 실행

```bash
cd src/ad_chat
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 접속

## 사용 방법

### 1단계: 인증

- OpenAI API 키 입력 (https://platform.openai.com/api-keys)
- 키 검증 후 채팅 화면으로 자동 이동

### 2단계: 광고 기획 대화

- 자연어로 제품/서비스 정보 입력
- AI가 광고 컨셉, 카피, 비주얼 제안
- "최종 생성", "광고 만들어줘" 등 키워드로 작업 요청

### 3단계: 작업 모니터링

- 작업 요청 후 Job ID 발급
- 히스토리 페이지에서 진행률 확인 (프로그래스바)
- 자동 갱신 토글로 실시간 모니터링

### 4단계: 결과 확인

- 작업 완료 시 결과 이미지 자동 표시
- MongoDB에 영구 저장된 히스토리 조회 가능

## 아키텍처 특징

### Fire-and-Forget 패턴

- 사용자가 작업 완료까지 기다리지 않음
- MCP 서버가 백그라운드에서 처리
- 폴링을 통한 상태 조회

### mcpadapter 활용

- **MCPClient**: 프로젝트 공통 MCP 클라이언트 재사용
- **LLMAdapter**: LLM 기반 자연어 → MCP Tool 자동 변환
- 비동기 기반 (asyncio.run 래핑)

### 클래스 기반 설계

- **MongoManager**: MongoDB CRUD 작업
- 각 UI 컴포넌트는 독립적인 모듈

### 에러 핸들링

- API 호출 실패 시 재시도 로직 (최대 3회)
- MongoDB 연결 오류 처리
- 사용자 친화적 오류 메시지

## 기술 스택

- **Frontend**: Streamlit 1.30+
- **Backend**: Python 3.9+
- **Database**: MongoDB (PyMongo 4.6+)
- **AI**: OpenAI API (gpt-5-mini)
- **MCP Client**: mcpadapter (프로젝트 공통 라이브러리)
- **Worker**: MCP Server (REST API)

## 환경 변수 상세

| 변수명 | 기본값 | 설명 |
|--------|--------|------|
| `MCP_SERVER_URL` | `http://34.44.205.198:3000` | MCP 서버 주소 |
| `MCP_TIMEOUT` | `30` | API 타임아웃 (초) |
| `MCP_MAX_RETRIES` | `3` | 재시도 횟수 |
| `MONGO_URI` | `mongodb://localhost:27017/` | MongoDB URI |
| `MONGO_DB_NAME` | `ai_ad_generator` | 데이터베이스 이름 |
| `POLLING_INTERVAL` | `10` | 상태 확인 간격 (초) |
| `POLLING_MAX_ATTEMPTS` | `180` | 최대 폴링 횟수 |

## 개발 참고사항

### MongoDB 컬렉션 스키마

**jobs 컬렉션:**
```json
{
  "job_id": "uuid",
  "prompt": "사용자 요청",
  "job_type": "full" | "text_only",
  "status": "pending" | "processing" | "completed" | "failed",
  "progress_percent": 0-100,
  "created_at": "datetime",
  "updated_at": "datetime",
  "result_image_path": "/path/to/image.png",
  "result_text": "생성된 텍스트",
  "error_message": null,
  "metadata": {}
}
```

**prompts 컬렉션:**
```json
{
  "prompt": "사용자 입력",
  "created_at": "datetime",
  "metadata": {}
}
```

### MCP 서버 API 엔드포인트

- `POST /call-tool` - Tool 실행
  - `check_server_health` - 서버 상태 확인
  - `generate_ad_content` - 광고 생성 요청
  - `check_generation_status` - 작업 상태 조회
  - `list_available_fonts` - 폰트 목록
  - `recommend_font_for_ad` - 폰트 추천

## 라이선스

MIT License
