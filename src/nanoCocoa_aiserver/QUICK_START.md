# nanoCocoa MCP Server - Quick Start Guide

빠르게 시작하기 위한 간단한 가이드입니다.

## 🚀 5분 안에 시작하기

### 1. FastAPI 서버 시작

```bash
cd src/nanoCocoa_aiserver
python dev.py
```

서버가 `http://localhost:8000`에서 실행됩니다.

### 2. MCP 의존성 설치

```bash
pip install -r requirements_mcp.txt
```

### 3. MCP 서버 설정

**자동 설치 (권장):**
```bash
python setup_mcp.py --install
```

**수동 설치:**
1. `.mcp/config.json` 파일 확인
2. Claude Desktop 설정 파일에 복사
3. 경로를 절대 경로로 수정

### 4. Claude Desktop 재시작

### 5. 테스트

```bash
python setup_mcp.py --test
```

또는

```bash
cd ../../tests
pytest mcp/test_mcp_dummy.py -v
```

## 📁 프로젝트 구조

```
src/nanoCocoa_aiserver/
├── .mcp/
│   └── config.json           # ✨ MCP 설정 파일 (프로젝트 내)
├── api/
│   └── routers/
│       ├── generation.py     # ✨ 확장됨: /jobs, DELETE /jobs/{id}
│       ├── resources.py      # ✨ 확장됨: /health
│       └── help.py           # ✨ 새로 추가: Help 엔드포인트
├── mcp_server.py             # ✨ MCP 서버 구현
├── setup_mcp.py              # ✨ MCP 설정 스크립트
├── test_mcp_server.py        # MCP 수동 테스트
└── requirements_mcp.txt      # MCP 의존성

tests/
└── mcp/
    └── test_mcp_dummy.py     # ✨ MCP 더미 테스트 (pytest)
```

## 🔧 주요 명령어

### MCP 설정

```bash
# MCP 서버 설치
python setup_mcp.py --install

# MCP 서버 제거
python setup_mcp.py --uninstall

# 현재 설정 확인
python setup_mcp.py --show

# MCP 서버 테스트
python setup_mcp.py --test
```

### API 테스트

```bash
# 서버 상태 확인
curl http://localhost:8000/health

# 폰트 목록 조회
curl http://localhost:8000/fonts

# API 가이드
curl http://localhost:8000/help

# 파라미터 레퍼런스
curl http://localhost:8000/help/parameters
```

### pytest 테스트

```bash
# MCP 더미 테스트
cd tests
pytest mcp/test_mcp_dummy.py -v

# 특정 테스트만 실행
pytest mcp/test_mcp_dummy.py::TestMCPServerDummy::test_list_tools -v
```

## 🎯 MCP Tools 사용 예시

Claude Desktop에서 다음과 같이 사용할 수 있습니다:

### 1. 기본 광고 생성

```
User: 커피 제품 광고를 만들어줘. 배경은 아늑한 카페로

Claude:
[Uses health_check → list_fonts → generate_and_wait]

제품 이미지를 업로드해주세요.

User: [Uploads coffee.png]

Claude: 광고를 생성하고 있습니다...
- 배경: 아늑한 모던 카페
- 텍스트: Fresh Brew
- 스타일: 브라운 3D 텍스트

[90초 후]
광고가 완성되었습니다!
```

### 2. 텍스트 스타일 변경

```
User: 텍스트를 골드 메탈릭으로 바꿔줘

Claude:
[Uses generate_ad with start_step=2]

이전 배경을 재사용하여 텍스트를 다시 생성합니다...

[35초 후]
완료!
```

## 🛠️ 트러블슈팅

### MCP 서버가 연결되지 않을 때

```bash
# 1. 설정 확인
python setup_mcp.py --show

# 2. FastAPI 서버 확인
curl http://localhost:8000/health

# 3. Claude Desktop 로그 확인 (Windows)
notepad %APPDATA%\Claude\logs\mcp.log
```

### 테스트 실패

```bash
# 의존성 확인
pip list | grep mcp
pip list | grep httpx

# 재설치
pip install --upgrade -r requirements_mcp.txt
```

## 📚 더 자세한 정보

- **완전한 설치 가이드**: [SETUP_GUIDE.md](SETUP_GUIDE.md)
- **MCP 서버 문서**: [README_MCP.md](README_MCP.md)
- **구현 상세**: [MCP_IMPLEMENTATION_SUMMARY.md](MCP_IMPLEMENTATION_SUMMARY.md)
- **API 문서**: http://localhost:8000/docs

## 체크리스트

설정이 완료되면 다음을 확인하세요:

- [ ] FastAPI 서버가 http://localhost:8000에서 실행 중
- [ ] `curl http://localhost:8000/health` 응답 정상
- [ ] `python setup_mcp.py --test` 통과
- [ ] `pytest tests/mcp/test_mcp_dummy.py -v` 통과
- [ ] Claude Desktop에서 MCP 도구 사용 가능

모두 체크되었다면 사용 준비 완료! 🎉

## 🔗 바로가기

- API 문서: http://localhost:8000/docs
- Health Check: http://localhost:8000/health
- Help: http://localhost:8000/help
- Parameters: http://localhost:8000/help/parameters
- Examples: http://localhost:8000/help/examples
