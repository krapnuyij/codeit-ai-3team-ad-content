# Codeit AI 3팀 - 생성형 AI 기반 소상공인을 위한 광고 콘텐츠 제작 서비스 

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28-red)
![PyTorch](https://img.shields.io/badge/PyTorch-2.0-orange)
![GCP](https://img.shields.io/badge/GCP-L4%20GPU-green)


---

## 1. 프로젝트 개요
- 본 프로젝트의 목표는 **생성형 AI 기술을 활용하여 소상공인이 광고 콘텐츠를 손쉽게 제작할 수 있도록 서비스를 개발**하는 것입니다.
- 디자인 역량이나 전문 도구 없이도 **제품 이미지, 배너, 상세 페이지용 시각 자료, 메뉴판 이미지, 광고 문구** 같은 콘텐츠를 자동으로 생성하는 서비스를 구현합니다.
- 따라서 오프라인 중심의 사업자들이 온라인 마케팅에 쉽게 진입할 수 있도록 하는 것이 서비스의 목표입니다.
- **특화 타겟**: 전통시장 소상공인 (1차 특화: 건어물 상품)
- **기술 방향**: 이미지 기반 광고 제작 (영상 제외), 확장 가능한 설계 구조

---

## 2. 프로젝트 기간
2025년 12월 29일 ~ 2026년 1월 28일
- 1차 목표: 2026년 1월 15일 (Hugging Face 모델 조합 서비스 구현)
- 2차 목표: 여유 시 모델 양자화 및 최적화
- 최종 제출: 2026년 1월 27일 19:00

---

## 3. 팀 구성 및 역할

- 김명환: 아키텍처 설계 및 파이프라인 구성 (API, 데이터 포맷, 모델 서버), 모델 관리 서버 설계
- 김민혁: 텍스트 생성 및 조합 모델 개발
- 박지윤: PM (프로젝트 관리 및 일정 조율)
- 이건희: 백엔드 개발 (LLM 연동), 프론트엔드 개발, Google Cloud VM 서버 구성
- 이슬형: 이미지 특성 추출 및 이미지 생성

### 📝 협업일지

팀원별 개발 과정 및 학습 내용을 기록한 협업일지입니다.
- [김명환 협업일지 (Project Manager)]({{- site.baseurl -}}/협업일지/김명환/)
- [김민혁 협업일지 (Project Manager)]({{- site.baseurl -}}/협업일지/김민혁/)
- [박지윤 협업일지 (Project Manager)]({{- site.baseurl -}}/협업일지/박지윤/)
- [이건희 협업일지 (Project Manager)]({{- site.baseurl -}}/협업일지/이건희/)
- [이슬형 협업일지 (Project Manager)]({{- site.baseurl -}}/협업일지/이슬형/)

- [팀 회의록]({{- site.baseurl -}}/회의록/)


---

## 4. 주요 기능
- 수정 예정
- 광고 문구 생성
- 프롬프트 기반 이미지 생성

---
## 5. 아키텍처
추가 예정

---

## 6. 기술 스택
- Frontend: Streamlit
- Backend: FastAPI (선택), LLM 연동
- Model: HuggingFace (Stable Diffusion 계열), OpenAI API (프롬프트 엔지니어링)
- Infra: GCP VM (L4 GPU, 34.44.205.198, us-central1)
- Storage: OS 20GB + 데이터 200GB (바인드 마운트)
- Collaboration: GitHub, Discord, Notion

---
