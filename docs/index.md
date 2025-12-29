---
layout: default
title: "코드잇 AI 4기 3팀 고급 프로젝트 - doc"
description: "코드잇 AI 4기 3팀 고급 프로젝트 - doc"
date: 2025-12-28
cache-control: no-cache
expires: 0
pragma: no-cache
author: "김명환"
---

# 🏥 코드잇 AI 4기 3팀 고급 프로젝트
## 생성형 AI 기반 소상공인 광고 콘텐츠 제작 서비스

**프로젝트 목표**: 전통시장 소상공인을 위한 AI 광고 콘텐츠 자동 생성 서비스  
**1차 특화**: 건어물 상품 프롬프트 엔진 (확장 가능한 설계)

## 👥 팀원

| 역할 | 담당자 | 핵심 업무 |
|---|---|---|
| 아키텍처 & 파이프라인 | [김명환](https://c0z0c.github.io) | 시스템 아키텍처 설계, API 설계, 모델 서버 구성, 모델 관리 서버 |
| 모델 연구 (이미지 특성) | 김민혁 | 이미지 특성 추출 모델 개발, 데이터셋 전처리 |
| PM & 기획 | 박지윤 | 프로젝트 관리, 일정 조율, 문서화, QA |
| 백엔드 & 프론트엔드 | 이건희 | 백엔드(LLM 연동), 프론트엔드(Streamlit), VM 인프라 구성 |
| 모델 연구 (이미지 생성) | 이슬형 | 이미지 생성 및 조합 모델 개발, 프롬프트 엔지니어링 |

## 📝 협업일지

팀원별 개발 과정 및 학습 내용을 기록한 협업일지입니다.

- [김명환 협업일지 (아키텍처 & 파이프라인)]({{- site.baseurl -}}/협업일지/김명환/)
- [김민혁 협업일지 (이미지 특성 추출)]({{- site.baseurl -}}/협업일지/김민혁/)
- [박지윤 협업일지 (PM & 기획)]({{- site.baseurl -}}/협업일지/박지윤/)
- [이건희 협업일지 (백엔드 & 프론트엔드)]({{- site.baseurl -}}/협업일지/이건희/)
- [이슬형 협업일지 (이미지 생성 & 조합)]({{- site.baseurl -}}/협업일지/이슬형/)

- [팀 회의록]({{- site.baseurl -}}/회의록/)

## 📅 프로젝트 기간
**2025.12.29(월) ~ 2026.01.28(수)**

- **1차 목표**: 2026.01.15 - Hugging Face 모델 조합 서비스 구현
- **2차 목표**: 여유 시 모델 양자화 및 최적화
- **최종 제출**: 2026.01.27 19:00
- **최종 발표**: 2026.01.28

**주요 마일스톤:**
- 12.29: 프로젝트 킥오프, 역할 분담, 벤치마킹 (Gemini Veo2 나노바나나)
- 12.30: GCP VM 환경 구축 (IP: 34.44.205.198)
- 01.15: 1차 MVP 완성 (이미지 기반 광고 생성)
- 01.27: 최종 제출 및 발표 자료 완성

**프로젝트 일정:**

```mermaid
gantt
    title Team 3 Project Timeline
    dateFormat  YYYY-MM-DD
    axisFormat  %m-%d
    
    section Setup & Plan
    환경 구축 및 기획        :active, a1, 2025-12-29, 2026-01-04
    신정 휴무              :crit, holiday, 2026-01-01, 1d
    
    section Development
    데이터 및 모델링        :b1, 2026-01-05, 2026-01-11
    서비스 구현 및 고도화    :c1, 2026-01-12, 2026-01-18
    통합 및 최적화          :d1, 2026-01-19, 2026-01-25
    
    section Submission
    보고서 작성             :e1, 2026-01-26, 2d
    최종 제출 (D-1)        :crit, milestone, 2026-01-27, 1d
    최종 발표 (D-Day)      :crit, milestone, 2026-01-28, 1d
    프로젝트 종료           :milestone, 2026-01-29, 1d

```

<script>

// 폴더 정보 가져오기 함수
function getFolderInfo(folderName) {
    folderName = (folderName || '').toString().replace(/^\/+|\/+$/g, '');
    // 폴더명에 따른 아이콘과 설명 (가나다순 정렬)
    const folderMappings = {
        '백업': { icon: '💾', desc: '백업 파일들' },
        '발표자료': { icon: '📊', desc: '발표 자료' },
        '셈플': { icon: '📂', desc: '샘플 파일들' },
        '스터디': { icon: '📒', desc: '학습 자료' },
        '실습': { icon: '🔬', desc: '실습 자료' },
        '위클리페이퍼': { icon: '📰', desc: '주간 학습 리포트' },
        '테스트': { icon: '🧪', desc: '테스트 파일들' },
        '협업일지': { icon: '📓', desc: '협업일지' },
        'doc': { icon: '📋', desc: '팀 doc' },
        'AI 모델 환경 설치가이드': { icon: '⚙️', desc: '설치 가이드' },
        'assets': { icon: '🎨', desc: '정적 자원' },
        'image': { icon: '🖼️', desc: '이미지 파일들' },
        'Learning': { icon: '📚', desc: '학습 자료' },
        'Learning Daily': { icon: '📅', desc: '일일 학습 기록' },
        'md': { icon: '📝', desc: 'Markdown 문서' }
    };
    return folderMappings[folderName] || { icon: '📁', desc: '폴더' };
}

function getFileInfo(extname) {
  switch(extname.toLowerCase()) {
    case '.ipynb':
      return { icon: '📓', type: 'Colab' };
    case '.py':
      return { icon: '🐍', type: 'Python' };
    case '.md':
      return { icon: '📝', type: 'Markdown' };
    case '.json':
      return { icon: '⚙️', type: 'JSON' };
    case '.zip':
      return { icon: '📦', type: '압축' };
    case '.png':
    case '.jpg':
    case '.jpeg':
      return { icon: '🖼️', type: '이미지' };
    case '.csv':
      return { icon: '📊', type: '데이터' };
    case '.pdf':
      return { icon: '📄', type: 'PDF' };
    case '.docx':
      return { icon: '�', type: 'Word' };
    case '.pptx':
      return { icon: '📊', type: 'PowerPoint' };
    case '.xlsx':
      return { icon: '📈', type: 'Excel' };
    case '.hwp':
      return { icon: '📄', type: 'HWP' };
    case '.txt':
      return { icon: '📄', type: 'Text' };
    case '.html':
      return { icon: '🌐', type: 'HTML' };
    default:
      return { icon: '📄', type: '파일' };
  }
}

{% assign cur_dir = "/" %}
{% include cur_files.liquid %}
{% include page_values.html %}
{% include page_folders_tree.html %}

</script>

---

## 폴더목록

<div class="folder-grid">
  <!-- 폴더 목록이 JavaScript로 동적 생성됩니다 -->
</div>

---

**문서 버전**: 0.2
**최종 업데이트**: 2025.12.29
**작성자**: 프로젝트 팀

**주요 변경사항**:
- v0.2 (2025.12.29): 팀원 역할 분담 확정, 프로젝트 특화 방향 설정 (전통시장/건어물)
- v0.1 (2025.12.28): 초기 문서 생성

**기술 스택**:
- Frontend: Streamlit
- Backend: FastAPI, LLM 연동
- Model: HuggingFace (Stable Diffusion), OpenAI API
- Infra: GCP VM (L4 GPU, us-central1)
- Storage: OS 20GB + 데이터 200GB (바인드 마운트)

---

<div class="navigation-footer">
  <a href="{{- site.baseurl -}}/" class="nav-button home">
    <span class="nav-icon">🏠</span> 홈으로
  </a>
  <a href="https://github.com/krapnuyij/codeit-ai-3team-ad-content" target="_blank">
    <span class="link-icon">📱</span> GitHub 저장소
  </a>
</div>