---
layout: default
title: "코드잇 AI 4기 3팀 고급 프로젝트 - 이솔형"
description: "코드잇 AI 4기 3팀 고급 프로젝트 - 이솔형"
date: 2025-12-28
cache-control: no-cache
expires: 0
pragma: no-cache
author: "이솔형"
---

# 협업일지 이솔형

<div style="margin-bottom: 20px;">
  <a href="https://www.notion.so/3-10524d5698b68347ac4a01359da8f219?source=copy_link" target="_blank" style="
    display: inline-flex;
    align-items: center;
    padding: 10px 15px;
    background-color: #f7f7f5;
    color: #37352f;
    text-decoration: none;
    border: 1px solid #e1e1e1;
    border-radius: 5px;
    font-weight: bold;
    font-size: 16px;">
    <img src="https://upload.wikimedia.org/wikipedia/commons/4/45/Notion_app_logo.png" alt="Notion" style="width: 20px; height: 20px; margin-right: 8px;">
    이솔형 협업일지 (Notion) 바로가기 ↗
  </a>
</div>

<script>
// 폴더 정보 가져오기 함수
function getFolderInfo(folderName) {
    folderName = (folderName || '').toString().replace(/^\/+|\/+$/g, '');
    const folderMappings = {
        '멘토': { icon: '', desc: '멘토 관련 자료' },
        '백업': { icon: '', desc: '백업 파일들' },
        '발표자료': { icon: '', desc: '발표 자료' },
        '셈플': { icon: '', desc: '샘플 파일들' },
        '스터디': { icon: '', desc: '학습 자료' },
        '실습': { icon: '', desc: '실습 자료' },
        '위클리페이퍼': { icon: '', desc: '주간 학습 리포트' },
        '테스트': { icon: '', desc: '테스트 파일들' },
        '협업일지': { icon: '', desc: '협업일지' },
        '회의록': { icon: '', desc: '팀 회의록' },
        'AI 모델 환경 설치가이드': { icon: '', desc: '설치 가이드' },
        'assets': { icon: '', desc: '정적 자원' },
        'image': { icon: '', desc: '이미지 파일들' },
        'Learning': { icon: '', desc: '학습 자료' },
        'Learning Daily': { icon: '', desc: '일일 학습 기록' },
        'md': { icon: '', desc: 'Markdown 문서' }
    };
    return folderMappings[folderName] || { icon: '', desc: '폴더' };
}

function getFileInfo(extname) {
  switch(extname.toLowerCase()) {
    case '.ipynb': return { icon: '', type: 'Colab' };
    case '.py': return { icon: '', type: 'Python' };
    case '.md': return { icon: '', type: 'Markdown' };
    case '.json': return { icon: '', type: 'JSON' };
    case '.zip': return { icon: '', type: '압축' };
    case '.png': case '.jpg': case '.jpeg': return { icon: '', type: '이미지' };
    case '.csv': return { icon: '', type: '데이터' };
    case '.pdf': return { icon: '', type: 'PDF' };
    case '.docx': return { icon: '', type: 'Word' };
    case '.pptx': return { icon: '', type: 'PowerPoint' };
    case '.xlsx': return { icon: '', type: 'Excel' };
    case '.hwp': return { icon: '', type: 'HWP' };
    case '.txt': return { icon: '', type: 'Text' };
    case '.html': return { icon: '', type: 'HTML' };
    default: return { icon: '', type: '파일' };
  }
}

window.addEventListener('load', function() {
    const targetFilename = "templet_협업일지_Day_1_2026-00-00.md";
    
    const notionUrl = "https://www.notion.so/3-10524d5698b68347ac4a01359da8f219?source=copy_link";

    setTimeout(() => {
        const rows = document.querySelectorAll('tr');

        rows.forEach(row => {
            if (row.innerHTML.includes(targetFilename)) {
                
                const links = row.querySelectorAll('a');
                links.forEach(link => {
                    if (link.innerText.trim().length > 0) {
                        link.href = notionUrl;
                        link.target = "_blank"; 
                        link.style.color = "#E16259"; 
                        link.style.fontWeight = "bold";
                    }
                });

                row.style.cursor = "pointer";
                row.onclick = function(e) {
                    if (e.target.tagName !== 'A' && e.target.parentNode.tagName !== 'A') {
                        window.open(notionUrl, '_blank');
                    }
                };
            }
        });
    }, 500); 
});
</script>

{% assign cur_dir = "/협업일지/이솔형/" %}
{% include cur_files.liquid %}
{% include page_values.html %}
{% include page_files_table.html %}


<div class="file-grid">
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
