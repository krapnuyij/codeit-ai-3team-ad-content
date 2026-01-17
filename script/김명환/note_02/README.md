# Ad-Gen-Pipeline (Flux-Based)

고품질 광고 이미지 생성 파이프라인 - "생성 후 합성(Generate-then-Fill)" 전략 사용

## 📋 프로젝트 개요

제품 이미지와 텍스트 프롬프트를 입력받아 맥락에 맞는 고품질 광고 이미지를 자동 생성합니다.

### 주요 특징

- **4단계 파이프라인**: 객체 전처리 → 배경 생성 → 위치 분석 → 최종 합성
- **VRAM 최적화**: 각 단계마다 자동 메모리 관리
- **모듈식 설계**: 각 단계를 독립적으로 검증 및 실행 가능
- **고품질 출력**: FLUX 모델 기반의 사실적인 이미지 생성

## 🏗️ 프로젝트 구조

```
.
├── notebooks/
│   └── pipeline_validation.ipynb  # 단계별 검증 및 실행
├── src/
│   ├── __init__.py
│   ├── utils.py            # GPU 메모리 관리 유틸리티
│   ├── preprocessor.py     # 배경 제거 (BiRefNet)
│   ├── generator.py        # 배경 생성 (FLUX.1-dev)
│   ├── analyzer.py         # 위치 분석 (Qwen2-VL)
│   └── synthesizer.py      # 객체 합성 (FLUX.1-Fill + IP-Adapter)
├── requirements.txt
├── project.md              # 상세 명세서
└── README.md
```

## 🚀 설치 방법

### 1. 환경 요구사항

- Python 3.10+
- CUDA 지원 GPU (VRAM 24GB+ 권장)
- Linux/Windows with WSL

### 2. 의존성 설치

```bash
# 가상환경 생성 (선택사항)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt
```

### 3. 모델 다운로드

첫 실행 시 필요한 모델이 자동으로 다운로드됩니다 (약 30GB):
- BiRefNet (배경 제거)
- FLUX.1-dev (배경 생성)
- Qwen2-VL-7B (위치 분석)
- FLUX.1-Fill-dev + IP-Adapter (객체 합성)

## 💻 사용 방법

### Jupyter Notebook으로 실행 (권장)

```bash
cd notebooks
jupyter notebook pipeline_validation.ipynb
```

노트북의 각 셀을 순차적으로 실행하면서 단계별 결과를 확인할 수 있습니다.

### Python 스크립트로 사용

```python
from src import (
    ObjectMatting,
    BackgroundGenerator,
    SpatialAnalyzer,
    ObjectSynthesizer
)

# 1. 배경 제거
matting = ObjectMatting()
clean_ref = matting.remove_background("product.png")

# 2. 배경 생성
generator = BackgroundGenerator()
background = generator.generate_background(
    prompt="A wooden table in a cozy bar with soft lighting",
    width=1024,
    height=1024
)

# 3. 위치 분석
analyzer = SpatialAnalyzer()
detection = analyzer.detect_surface(
    background,
    "Find the center of the table to place a product"
)
mask = analyzer.create_mask(detection['image_size'], detection['bbox'])

# 4. 최종 합성
synthesizer = ObjectSynthesizer()
final_image = synthesizer.fill_in_object(
    background=background,
    mask=mask,
    reference=clean_ref,
    prompt="A beer bottle on a table in warm bar lighting",
    ip_adapter_scale=0.8
)

final_image.save("result.png")
```

## 📊 파이프라인 단계

### Step 1: 객체 전처리 (Object Matting)
- **모델**: BiRefNet
- **기능**: 제품 이미지에서 배경 제거
- **출력**: 투명 배경의 RGBA 이미지

### Step 2: 배경 생성 (Background Generation)
- **모델**: FLUX.1-dev
- **기능**: 분위기에 맞는 배경 이미지 생성
- **출력**: 1024x1024 배경 이미지

### Step 3: 위치 분석 (Spatial Analysis)
- **모델**: Qwen2-VL-7B
- **기능**: 객체 배치 최적 위치 탐지
- **출력**: 바운딩 박스 & 이진 마스크

### Step 4: 객체 합성 (Object Synthesis)
- **모델**: FLUX.1-Fill-dev + IP-Adapter
- **기능**: 자연스러운 조명/그림자로 객체 합성
- **출력**: 최종 광고 이미지

## ⚙️ 주요 파라미터

### IP-Adapter Scale
- `0.6-0.7`: 자연스러운 블렌딩 (원본 형태 약간 변형)
- `0.8`: 균형잡힌 설정 (권장)
- `1.0`: 원본 최대 보존 (덜 자연스러울 수 있음)

### 이미지 크기
- 기본: `1024x1024`
- 가능: `512x512` ~ `1024x1024`

### Seed
- 재현 가능한 결과를 위해 고정 시드 사용 권장

## 🔧 VRAM 관리

모든 클래스는 자동 메모리 관리 기능을 포함합니다:

```python
# 각 단계 후 자동으로 모델 언로드
matting = ObjectMatting()
result = matting.remove_background("image.png")
# 자동으로 GPU 메모리 정리

# 또는 수동으로 정리
from src.utils import flush_gpu
flush_gpu()
```

## 📝 예제 시나리오

### 맥주 광고

```python
INPUT_IMAGE = "beer_bottle.png"

PROMPT_SCENARIO = (
    "A photorealistic shot of a K-pop style couple in their early 20s "
    "drinking beer at a bar table, soft ambient lighting, "
    "cinematic atmosphere, shallow depth of field"
)

PROMPT_BACKGROUND = (
    "A wooden table in a cozy bar with soft warm lighting, "
    "empty space in center, blurred background with bokeh effect"
)
```

### 화장품 광고

```python
INPUT_IMAGE = "lipstick.png"

PROMPT_SCENARIO = (
    "Luxury lipstick on a marble vanity table, "
    "soft morning light, elegant atmosphere"
)

PROMPT_BACKGROUND = (
    "A white marble vanity table with soft natural window light, "
    "empty space in center, minimal elegant setting"
)
```

## 🐛 문제 해결

### CUDA Out of Memory
- 이미지 크기를 512x512로 줄이기
- `enable_attention_slicing()` 활성화
- 각 단계 후 `flush_gpu()` 명시적 호출

### 모델 다운로드 실패
- Hugging Face 토큰이 필요한 경우:
```python
from huggingface_hub import login
login()
```

### 느린 실행 속도
- GPU가 올바르게 감지되었는지 확인
- CUDA 버전과 PyTorch 호환성 확인

## 📚 참고 자료

- [FLUX.1 Documentation](https://github.com/black-forest-labs/flux)
- [BiRefNet Paper](https://arxiv.org/abs/2401.17094)
- [Qwen2-VL](https://github.com/QwenLM/Qwen2-VL)
- [IP-Adapter](https://ip-adapter.github.io/)

## 📄 라이선스

개별 모델의 라이선스를 확인하세요:
- FLUX.1: Apache 2.0 (dev 버전은 비상업적 사용)
- BiRefNet: MIT
- Qwen2-VL: Tongyi Qianwen License

## 🤝 기여

이슈 및 풀 리퀘스트 환영합니다!
