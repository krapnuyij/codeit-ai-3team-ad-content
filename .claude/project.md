# [AI] 고급 프로젝트

### 1.1. 배경 및 목적
* **주제**: 생성형 AI(Generative AI) 기술을 활용한 소상공인 광고 콘텐츠 제작 지원 서비스
* **목표**: 디자인 역량이 부족한 소상공인이 제품 이미지, 배너, 광고 문구 등을 손쉽게 생성하여 온라인 마케팅 진입 장벽을 낮출 수 있도록 지원
* **핵심 가치**: 비용 절감, 콘텐츠 제작 시간 단축, 마케팅 효율 증대

### 1.2. 서비스 범위 (Scope)
* **타겟 유저**: 오프라인 중심의 개인/법인 사업자 (소상공인)
* **필수 기능**: 생성형 AI를 활용한 이미지 또는 텍스트 생성 기능 최소 1종 구현
* **제공 형태**: Streamlit 기반의 웹 어플리케이션


## 2. 프로젝트
src/nanoCocoa_aiserver
**1.1. 설계 목표 (Design Goals)**
1. **자원 최적화 (Resource Optimization):** 제한된 24GB VRAM 환경에서 거대 모델(FLUX, SDXL)을 운용하기 위해 JIT (Just-In-Time) 로딩 및 언로딩 전략을 채택합니다.
2. **비동기 처리 (Asynchronous Processing):** FastAPI 메인 스레드의 블로킹을 방지하기 위해 `multiprocessing (멀티프로세싱)`을 활용하여 추론 작업을 격리합니다.
3. **상태 보존 및 제어 (State Persistence & Control):** 외부 데이터베이스 없이 인메모리(In-Memory) 공유 객체를 통해 작업 단계(Stage)별 결과물을 저장하고, 실패 시 또는 사용자 요청 시 중간 지점부터 재시작(Resume)할 수 있는 기능을 제공합니다.
4. **MCP 호환성 (MCP Compatibility):** LLM 에이전트가 도구(Tool)로서 쉽게 호출할 수 있도록 명확한 API 스키마와 상태 코드를 정의합니다.
5. tests에 유닛테스트 통과 필수
6. src/nanoCocoa_aiserver
- fastapi를 기반으로 ai 모델링 서비스
- fastapi tests폴더에서 RESET API 유닛 테스트
- 브라우저 접근가능한 /test test_dashboard.html를 이용하여 RESET API 테스트


## 3. 참고사항
script 폴더는 기본적으로 무시하자
