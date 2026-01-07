
# Project Specification: Ad-Gen-Pipeline (Flux-Based)

## 1. 프로젝트 개요 (Overview)

* **목표:** 제품 이미지(`image.png`)와 텍스트 프롬프트를 입력받아, 맥락에 맞는 고품질 광고 이미지를 생성하는 파이프라인 구축.
* **핵심 접근:** "생성 후 합성(Generate-then-Fill)" 전략 사용.
* **개발 환경:** Python 3.10+, PyTorch (CUDA), Jupyter Notebook
* **주요 모델:**
* 전처리: `ZhengPeng7/BiRefNet` (Background Removal)
* 배경 생성: `black-forest-labs/FLUX.1-dev`
* 위치 분석: `Qwen/Qwen3-VL-8B-Instruct`
* 합성: `black-forest-labs/FLUX.1-Fill-dev` + `InstantX/FLUX.1-dev-IP-Adapter`

---

## 2. 프로젝트 구조 (Directory Structure)

모듈성을 극대화하여 유지보수와 디버깅이 용이하도록 설계함.

```
├── notebooks/
│   └── pipeline_validation.ipynb  # 단계별 검증 및 최종 실행용
├── src/
│   ├── __init__.py
│   ├── utils.py            # 공통 유틸리티 (이미지 로드/저장, GPU 메모리 정리)
│   ├── preprocessor.py     # Class: ObjectMatting (BiRefNet)
│   ├── generator.py        # Class: BackgroundGenerator (FLUX.1-dev)
│   ├── analyzer.py         # Class: SpatialAnalyzer (Qwen3-VL)
│   └── synthesizer.py      # Class: ObjectSynthesizer (FLUX.1-Fill + IP-Adapter)
├── requirements.txt
└── project.md              # 본 문서

```

---

## 3. 모듈별 상세 명세 (Module Specifications)

### A. 공통 유틸리티 (`src/utils.py`)

* **기능:** GPU VRAM 관리, 이미지 형변환(PIL <-> Tensor).
* **핵심 함수:**
* `flush_gpu()`: `gc.collect()` 및 `torch.cuda.empty_cache()` 실행. 모델 전환 시 필수 호출.
* `load_image(path)`, `save_image(image, path)`



### B. 객체 전처리 (`src/preprocessor.py`)

* **Class:** `ObjectMatting`
* **Model:** `ZhengPeng7/BiRefNet`
* **책임:** 입력된 제품 이미지의 배경을 제거하여 깨끗한 RGBA 이미지 생성.
* **Method:**
* `remove_background(image_path: str) -> PIL.Image`


* **Note:** IP-Adapter의 오염 방지를 위해 필수.

### C. 배경 생성 (`src/generator.py`)

* **Class:** `BackgroundGenerator`
* **Model:** `black-forest-labs/FLUX.1-dev` (Diffusers Pipeline)
* **책임:** 제품이 없는 순수한 배경 이미지 생성.
* **Method:**
* `generate_background(prompt: str, width: int, height: int) -> PIL.Image`


* **Note:** 프롬프트에서 제품 관련 구체적 묘사는 최소화하고 분위기/장소 위주로 작성.

### D. 위치 및 공간 분석 (`src/analyzer.py`)

* **Class:** `SpatialAnalyzer`
* **Model:** `Qwen/Qwen3-VL-8B-Instruct`
* **책임:** 배경 이미지를 분석하여 제품을 놓을 최적의 좌표(BBox)를 찾고 마스크 생성.
* **Method:**
* `detect_surface(image: PIL.Image, query: str) -> dict` (bbox 좌표 반환)
* `create_mask(image_size: tuple, bbox: list) -> PIL.Image` (Black/White 마스크 반환)



### E. 객체 합성 (`src/synthesizer.py`)

* **Class:** `ObjectSynthesizer`
* **Model:**
* Base: `black-forest-labs/FLUX.1-Fill-dev`
* Adapter: `InstantX/FLUX.1-dev-IP-Adapter`


* **책임:** 배경의 빛과 그림자에 맞춰 제품(Reference)을 자연스럽게 합성.
* **Method:**
* `fill_in_object(background: PIL.Image, mask: PIL.Image, reference: PIL.Image, prompt: str) -> PIL.Image`


* **Note:** Inpainting 모드에서 IP-Adapter 가중치를 조절하여 자연스러움(0.7) vs 원본유지(1.0) 균형 조절.

---

## 4. Jupyter Notebook 시나리오 (`notebooks/pipeline_validation.ipynb`)

Notebook은 각 단계별 셀(Cell) 단위 검증 후, 마지막에 파이프라인을 통합 실행한다.

### [Cell 1] 환경 설정 및 유틸리티 로드

* 라이브러리 임포트 (`torch`, `diffusers`, `PIL`, etc.)
* `src` 모듈 임포트.
* GPU 설정 확인.

### [Cell 2] 입력 데이터 정의 (User Scenario)

```python
# 입력 데이터 설정
INPUT_IMAGE_PATH = "image.png" # 맥주병 이미지 등
# 시나리오: 20대초반 K-pop 스타일 남여, 맥주 마시는 테이블, 은은한 조명
PROMPT_SCENARIO = "A photorealistic shot of a K-pop style couple in their early 20s drinking beer at a bar table, soft ambient lighting, cinematic atmosphere, shallow depth of field."

```

### [Cell 3] Step 1: 객체 누끼 따기 (Preprocessing)

* `ObjectMatting` 인스턴스 생성.
* `remove_background()` 실행.
* 결과 이미지(`clean_ref_image`) 출력 및 저장.
* **검증 포인트:** 배경이 투명하게 잘 날아갔는가?
* *메모리 정리 (`flush_gpu`)*

### [Cell 4] Step 2: 배경 생성 (Background Gen)

* `BackgroundGenerator` 인스턴스 생성.
* 배경 전용 프롬프트 변환 (예: "A wooden table in a bar with soft lighting, empty space in center...")
* `generate_background()` 실행.
* 결과 이미지(`bg_image`) 출력.
* **검증 포인트:** 테이블 위에 물건을 놓을 만한 공간이 있는가?
* *메모리 정리*

### [Cell 5] Step 3: 위치 선정 (Spatial Analysis)

* `SpatialAnalyzer` 인스턴스 생성.
* Qwen에게 질의: "Find the flat surface on the table center to place a beer bottle."
* 좌표 획득 및 `create_mask()`로 마스크 이미지 생성.
* 결과 이미지(`mask_image`) 오버레이 확인.
* **검증 포인트:** 마스크가 테이블 위 적절한 위치에 그려졌는가?
* *메모리 정리*

### [Cell 6] Step 4: 최종 합성 (Synthesis)

* `ObjectSynthesizer` 인스턴스 생성.
* `fill_in_object(bg_image, mask_image, clean_ref_image, PROMPT_SCENARIO)` 실행.
* 최종 결과 출력.
* **검증 포인트:** 맥주병이 테이블 조명에 맞춰 자연스럽게 합성되었는가? 그림자가 생겼는가?

### [Cell 7] Full Pipeline Integration

* 위의 모든 클래스를 한 번에 순차 실행하는 `main()` 함수 스타일의 통합 테스트.
* VRAM 관리를 위해 모델 로드/언로드를 자동으로 수행하는 로직 검증.

---

## 5. 요구사항 (Requirements)

```text
torch>=2.4.0
diffusers>=0.30.0
transformers>=4.44.0
accelerate>=0.33.0
opencv-python
pillow
sentencepiece
protobuf

```

