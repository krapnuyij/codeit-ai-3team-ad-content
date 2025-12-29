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
## 👥 팀원

| 역할 | 담당자 | 핵심 업무 |
|---|---|---|
| xxx | [김명환](https://c0z0c.github.io) | xxx |
| xxx | 김민혁 | xxx |
| xxx | 박지윤 | xxx |
| xxx | 이건희 | xxx |
| xxx | 이슬형 | xxx |

## 📝 협업일지

팀원별 개발 과정 및 학습 내용을 기록한 협업일지입니다.

- [김명환 협업일지 (Project Manager)](https://krapnuyij.github.io/codeit_ai_codeit-ai-3team-ad-content/협업일지/김명환/)
- [김민혁 협업일지 (Project Manager)](https://krapnuyij.github.io/codeit_ai_codeit-ai-3team-ad-content/협업일지/김민혁/)
- [박지윤 협업일지 (Project Manager)](https://krapnuyij.github.io/codeit_ai_codeit-ai-3team-ad-content/협업일지/박지윤/)
- [이건희 협업일지 (Project Manager)](https://krapnuyij.github.io/codeit_ai_codeit-ai-3team-ad-content/협업일지/이건희/)
- [이슬형 협업일지 (Project Manager)](https://krapnuyij.github.io/codeit_ai_codeit-ai-3team-ad-content/협업일지/이슬형/)

- [팀 회의록](https://krapnuyij.github.io/codeit_ai_codeit-ai-3team-ad-content/회의록/)

## 📅 프로젝트 기간
**2025.12.29(월) ~ 2026.01.29(목)**

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

**문서 버전**: 0.1
**최종 업데이트**: 2025.12.29
**작성자**: 프로젝트 팀

**주요 변경사항 (v0.1)**:

---

<div class="navigation-footer">
  <a href="{{- site.baseurl -}}/" class="nav-button home">
    <span class="nav-icon">🏠</span> 홈으로
  </a>
  <a href="https://github.com/krapnuyij/codeit-ai-3team-ad-content" target="_blank">
    <span class="link-icon">📱</span> GitHub 저장소
  </a>
</div>