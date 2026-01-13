# CODEIT 4기 3팀 - FastAPI + Jinja2 프로젝트

## 🚀 프로젝트 구조

```
fastapi_project/
├── main.py                 # FastAPI 앱 메인 파일
├── requirements.txt        # 의존성 패키지 목록
├── static/                 # 정적 파일
│   ├── css/
│   │   └── style.css      # 통합 CSS
│   └── js/                # JavaScript 파일 (필요시)
└── templates/             # Jinja2 템플릿
    ├── base.html          # 기본 레이아웃 템플릿
    ├── index.html         # 메인 페이지
    ├── about.html         # About 페이지
    ├── manager.html       # 관리자 대시보드
    └── components/        # 재사용 컴포넌트
        ├── header.html    # 헤더
        └── footer.html    # 푸터
```

## 📦 설치 방법

### 1. 가상환경 생성 (선택사항)
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 또는
venv\Scripts\activate     # Windows
```

### 2. 패키지 설치
```bash
pip install -r requirements.txt
```

## 🏃 실행 방법

### 개발 모드 (자동 재시작)
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 프로덕션 모드
```bash
python main.py
```

브라우저에서 http://localhost:8000 접속

## 🎯 주요 라우트

| URL | 설명 |
|-----|------|
| `/` | 메인 페이지 (로그인) |
| `/about` | About 페이지 |
| `/services` | Services 페이지 |
| `/portfolio` | Portfolio 페이지 |
| `/contact` | Contact 페이지 |
| `/promote-store` | Promote Store 페이지 |
| `/user` | 사용자 대시보드 |
| `/manager` | 관리자 대시보드 |

## 🔧 Jinja2 템플릿 사용법

### 1. 템플릿 상속
```html
{% extends 'base.html' %}

{% block title %}페이지 제목{% endblock %}

{% block content %}
<!-- 페이지 내용 -->
{% endblock %}
```

### 2. 변수 사용
```html
<!-- Python에서 전달: {"user": {"name": "홍길동"}} -->
<h1>{{ user.name }}</h1>
```

### 3. 조건문
```html
{% if user.is_admin %}
    <p>관리자입니다</p>
{% else %}
    <p>일반 사용자입니다</p>
{% endif %}
```

### 4. 반복문
```html
{% for item in items %}
    <li>{{ item.name }}</li>
{% endfor %}
```

### 5. Static 파일 URL
```html
<link rel="stylesheet" href="{{ url_for('static', path='/css/style.css') }}">
<script src="{{ url_for('static', path='/js/script.js') }}"></script>
```

## 💡 FastAPI vs 정적 HTML 차이점

### ❌ 정적 HTML (이전)
```html
<!-- 모든 페이지에 헤더/푸터 중복 -->
<header>...</header>
<main>...</main>
<footer>...</footer>
```

### ✅ FastAPI + Jinja2 (현재)
```html
<!-- base.html에 한 번만 정의 -->
{% extends 'base.html' %}
{% block content %}
    <!-- 페이지별 내용만 -->
{% endblock %}
```

### 장점
1. **코드 재사용**: 헤더/푸터 한 곳에서 관리
2. **동적 데이터**: Python에서 데이터 전달 가능
3. **API 통합**: REST API와 웹페이지 한 프로젝트에
4. **확장성**: 로그인, DB 연동 등 쉽게 추가

## 🔐 데이터 전달 예시

### main.py
```python
@app.get("/manager")
async def manager(request: Request):
    data = {
        "store_name": "오로라 카페",
        "monthly_generated": 12,
        "monthly_limit": 30
    }
    return templates.TemplateResponse(
        "manager.html", 
        {"request": request, "manager": data}
    )
```

### manager.html
```html
<h3>{{ manager.store_name }}</h3>
<p>생성 수: {{ manager.monthly_generated }}/{{ manager.monthly_limit }}</p>
```

## 📝 다음 단계

1. **데이터베이스 연동**
   ```bash
   pip install sqlalchemy databases
   ```

2. **사용자 인증**
   ```bash
   pip install python-jose[cryptography] passlib[bcrypt]
   ```

3. **API 엔드포인트 추가**
   ```python
   @app.post("/api/generate-ad")
   async def generate_ad(data: AdRequest):
       # AI 광고 생성 로직
       return {"ad_url": "..."}
   ```

## 🎨 JavaScript는?

**네, JavaScript는 그대로 작동합니다!**

- `{% block extra_js %}`에 JavaScript 코드 추가
- 또는 `/static/js/` 폴더에 별도 파일로 관리
- manager.html의 섹션 전환 스크립트처럼 사용 가능

예시:
```html
{% block extra_js %}
<script>
    function showSection(sectionId) {
        // 클라이언트 사이드에서 실행
        document.getElementById(sectionId).style.display = 'block';
    }
</script>
{% endblock %}
```

## 🤝 도움말

문제가 있으면:
1. 터미널에서 에러 메시지 확인
2. 브라우저 개발자 도구 (F12) 콘솔 확인
3. FastAPI 자동 문서 확인: http://localhost:8000/docs

---

**Happy Coding! 🚀**
