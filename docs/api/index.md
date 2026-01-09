---
layout: default
title: "코드잇 AI 4기 3팀 고급 프로젝트 - API"
description: "코드잇 AI 4기 3팀 고급 프로젝트 - API 문서"
date: 2025-01-08
cache-control: no-cache
expires: 0
pragma: no-cache
author: "김명환"
---

# API 문서

nanoCocoa 프로젝트의 API 문서입니다.

## 목차

### 1. [nanoCocoa AI Server REST API](./nanoCocoa_aiserver_REST_API.md)

AI 광고 생성 서버의 REST API 문서입니다.

- **서버 정보**: L4 Optimized AI Ad Generator v2.0.0
- **주요 기능**: 
  - 배경 생성 및 합성 (BiRefNet, Flux)
  - 3D 텍스트 생성 (SDXL ControlNet)
  - 최종 합성 (Intelligent Composition)
- **API 카테고리**:
  - Generation API (광고 생성, 상태 조회, 작업 관리)
  - Resources API (폰트, 서버 상태)
  - Help & Documentation API (사용 가이드, 파라미터 레퍼런스)
- **클라이언트 예시**: Python, JavaScript, cURL

---

## API 빠른 참조

### nanoCocoa AI Server

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/generate` | POST | 광고 생성 작업 시작 |
| `/status/{job_id}` | GET | 작업 상태 및 결과 조회 |
| `/stop/{job_id}` | POST | 작업 강제 중단 |
| `/jobs` | GET | 모든 작업 목록 조회 |
| `/jobs/{job_id}` | DELETE | 작업 삭제 |
| `/fonts` | GET | 사용 가능한 폰트 목록 조회 |
| `/health` | GET | 서버 상태 체크 |
| `/help` | GET | 전체 API 사용 가이드 |
| `/help/parameters` | GET | 파라미터 레퍼런스 |

---

## 개발 리소스

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI Schema**: `http://localhost:8000/openapi.json`
- **개발자 대시보드**: `http://localhost:8000/example_generation`

---

# api

<script>

// 폴더 정보 가져오기 함수
function getFolderInfo(folderName) {
    folderName = (folderName || '').toString().replace(/^\/+|\/+$/g, '');
    // 폴더명에 따른 아이콘과 설명 (가나다순 정렬)
    const folderMappings = {
        '멘토': { icon: '', desc: '멘토 관련 자료' },
        '백업': { icon: '', desc: '백업 파일들' },
        '발표자료': { icon: '', desc: '발표 자료' },
        '셈플': { icon: '', desc: '샘플 파일들' },
        'api': { icon: '', desc: '학습 자료' },
        '실습': { icon: '', desc: '실습 자료' },
        '위클리페이퍼': { icon: '', desc: '주간 학습 리포트' },
        '테스트': { icon: '', desc: '테스트 파일들' },
        'api': { icon: '', desc: '협업일지' },
        'api': { icon: '', desc: '팀 api' },
        'AI 모델 환경 설치가이드': { icon: '', desc: '설치 가이드' },
        'assets': { icon: '', desc: '정적 자원' },
        'image': { icon: '', desc: '이미지 파일들' },
        'Learning': { icon: '', desc: '학습 자료' },
        'Learning Daily': { icon: '', desc: '일일 학습 기록' },
        'md': { icon: '', desc: 'Markdown api' }
    };
    return folderMappings[folderName] || { icon: '', desc: '폴더' };
}

function getFileInfo(extname) {
  switch(extname.toLowerCase()) {
    case '.ipynb':
      return { icon: '', type: 'Colab' };
    case '.py':
      return { icon: '', type: 'Python' };
    case '.md':
      return { icon: '', type: 'Markdown' };
    case '.json':
      return { icon: '', type: 'JSON' };
    case '.zip':
      return { icon: '', type: '압축' };
    case '.png':
    case '.jpg':
    case '.jpeg':
      return { icon: '', type: '이미지' };
    case '.csv':
      return { icon: '', type: '데이터' };
    case '.pdf':
      return { icon: '', type: 'PDF' };
    case '.docx':
      return { icon: '', type: 'Word' };
    case '.pptx':
      return { icon: '', type: 'PowerPoint' };
    case '.xlsx':
      return { icon: '', type: 'Excel' };
    case '.hwp':
      return { icon: '', type: 'HWP' };
    case '.txt':
      return { icon: '', type: 'Text' };
    case '.html':
      return { icon: '', type: 'HTML' };
    default:
      return { icon: '', type: '파일' };
  }
}

{% assign cur_dir = "/api/" %}
{% include cur_files.liquid %}
{% include page_values.html %}
{% include page_files_table.html %}

</script>

<div class="file-grid">
  <!-- 파일 목록이 JavaScript로 동적 생성됩니다 -->
</div>

---

<div class="navigation-footer">
  <a href="{{- site.baseurl -}}/" class="nav-button home">
    <span class="nav-icon">🏠</span> 홈으로
  </a>
  <a href="https://github.com/krapnuyij/codeit-ai-3team-ad-content" target="_blank">
    <span class="link-icon">📱</span> GitHub 저장소
  </a>
</div>