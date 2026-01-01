---
layout: default
title: "코드잇 AI 4기 3팀 고급 프로젝트 - 협업일지"
description: "코드잇 AI 4기 3팀 고급 프로젝트 - 협업일지"
date: 2025-12-28
cache-control: no-cache
expires: 0
pragma: no-cache
author: "김명환"
---

# 협업일지

<script>

// 폴더 정보 가져오기 함수
function getFolderInfo(folderName) {
    folderName = (folderName || '').toString().replace(/^\/+|\/+$/g, '');
    // 폴더명에 따른 아이콘과 설명 (가나다순 정렬)
    const folderMappings = {
        '멘토': { icon: '👨‍🏫', desc: '멘토 관련 자료' },
        '백업': { icon: '💾', desc: '백업 파일들' },
        '발표자료': { icon: '📊', desc: '발표 자료' },
        '셈플': { icon: '📂', desc: '샘플 파일들' },
        '협업일지': { icon: '📒', desc: '학습 자료' },
        '실습': { icon: '🔬', desc: '실습 자료' },
        '위클리페이퍼': { icon: '📰', desc: '주간 학습 리포트' },
        '테스트': { icon: '🧪', desc: '테스트 파일들' },
        '협업일지': { icon: '📓', desc: '협업일지' },
        '회의록': { icon: '📋', desc: '팀 회의록' },
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

{% assign cur_dir = "/협업일지/" %}
{% include cur_files.liquid %}
{% include page_values.html %}
{% include page_files_table.html %}
{% include page_folders_tree.html %}

</script>

<div class="file-grid">
  <!-- 파일 목록이 JavaScript로 동적 생성됩니다 -->
</div>

---

## 폴더목록

<div class="folder-grid">
  <!-- 폴더 목록이 JavaScript로 동적 생성됩니다 -->
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