# CLIP Score API 가이드 (OpenAI CLIP + KoCLIP)

## 1. 개요

CLIP Score API는 OpenAI의 CLIP 모델과 한글 지원 KoCLIP 모델을 사용하여 이미지와 텍스트 간 유사도를 측정하는 REST API 엔드포인트입니다. 광고 이미지가 입력 프롬프트와 얼마나 부합하는지 정량적으로 평가할 수 있습니다.

### 지원 모델

| 모델 | 설명 | 최적 사용 사례 |
|------|------|----------------|
| **KoCLIP** | 한국어 데이터로 학습된 CLIP | 한글 프롬프트, 한글이 포함된 이미지 평가 |
| **OpenAI CLIP** | 원본 CLIP 모델 | 영문 프롬프트, 빠른 처리 속도 |

## 2. API 엔드포인트

### 2.1. CLIP Score 계산

**Endpoint**: `POST /clip-score`

**요청 스키마** (`ClipScoreRequest`):

```json
{
  "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAY...",
  "prompt": "사과가 그려져 있고 가격과 판매 장소가 적혀 있는 광고 포스터",
  "model_type": "koclip"
}
```

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|--------|------|
| `image_base64` | string | ✅ | - | Base64 인코딩된 이미지 문자열 (PNG, JPEG 등) |
| `prompt` | string | ✅ | - | 이미지를 설명하는 텍스트 프롬프트 (한글/영문 모두 지원) |
| `model_type` | string | ❌ | `"koclip"` | 사용할 모델 (`"openai"` 또는 `"koclip"`) |

**응답 스키마** (`ClipScoreResponse`):

```json
{
  "clip_score": 0.7324,
  "prompt": "사과가 그려져 있고 가격과 판매 장소가 적혀 있는 광고 포스터",
  "model_type": "koclip",
  "interpretation": "매우 높은 일치도 - 이미지가 텍스트 설명과 강하게 부합합니다."
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `clip_score` | float | 코사인 유사도 점수 (범위: -1.0 ~ 1.0, 일반적으로 0.0 ~ 1.0) |
| `prompt` | string | 평가에 사용된 텍스트 프롬프트 |
| `model_type` | string | 사용된 모델 타입 (`"openai"` 또는 `"koclip"`) |
| `interpretation` | string | 점수에 대한 자동 해석 메시지 |

### 2.2. Health Check

**Endpoint**: `GET /clip-score/health`

CLIP 모델 로딩 여부 및 사용 중인 디바이스(CPU/GPU)를 확인합니다.

**응답 예시**:

```json
{
  "status": "healthy",
  "device": "cuda",
  "models": {
    "openai_clip": {
      "loaded": true,
      "model": "ViT-B/32"
    },
    "koclip": {
      "loaded": true,
      "model": "koclip-base-pt"
    }
  }
}
```

## 3. CLIP Score 해석 가이드

| 점수 범위 | 해석 | 설명 |
|-----------|------|------|
| **0.7 이상** | 매우 높은 일치도 | 광고 생성 성공적, 이미지가 텍스트와 강하게 부합 |
| **0.5 ~ 0.7** | 높은 일치도 | 이미지와 텍스트가 잘 연관되어 있음 |
| **0.3 ~ 0.5** | 중간 일치도 | 어느 정도 연관성 있음 |
| **0.3 미만** | 낮은 일치도 | 연관성 약함, 프롬프트 수정 권장 |

## 4. 사용 사례

### 4.1. 광고 이미지 평가 (한글 프롬프트)

생성된 광고 이미지가 입력 프롬프트와 얼마나 일치하는지 평가:

```python
import base64
import requests

# 이미지 Base64 인코딩
with open("apple_ad_korean.png", "rb") as f:
    image_base64 = base64.b64encode(f.read()).decode("utf-8")

# CLIP Score 계산 (KoCLIP 사용)
response = requests.post(
    "http://localhost:8000/clip-score",
    json={
        "image_base64": image_base64,
        "prompt": "사과가 그려져 있고 가격과 판매 장소가 적혀 있는 광고 포스터",
        "model_type": "koclip"  # 한글 프롬프트이므로 KoCLIP 사용
    }
)

result = response.json()
print(f"CLIP Score: {result['clip_score']}")
print(f"Model: {result['model_type']}")
print(f"Interpretation: {result['interpretation']}")
```

### 4.2. 모델 비교 (한글 vs 영문)

동일 이미지에 대해 KoCLIP과 OpenAI CLIP 비교:

```python
models = {
    "koclip": "사과 광고 포스터",
    "openai": "Apple advertisement poster"
}
scores = {}

for model_type, prompt in models.items():
    response = requests.post(
        "http://localhost:8000/clip-score",
        json={
            "image_base64": image_base64, 
            "prompt": prompt,
            "model_type": model_type
        }
    )
    scores[model_type] = response.json()["clip_score"]

print(f"KoCLIP Score: {scores['koclip']:.4f}")
print(f"OpenAI CLIP Score: {scores['openai']:.4f}")
```

### 4.3. 프롬프트 최적화 (한글)

다양한 한글 프롬프트 중 가장 효과적인 것 선택:

```python
prompts = [
    "빨간 사과",
    "가격표가 있는 신선한 빨간 사과",
    "사과가 그려져 있고 가격과 판매 장소가 적혀 있는 광고 포스터"
]

best_score = 0
best_prompt = None

for prompt in prompts:
    response = requests.post(
        "http://localhost:8000/clip-score",
        json={
            "image_base64": image_base64, 
            "prompt": prompt,
            "model_type": "koclip"
        }
    )
    score = response.json()["clip_score"]
    
    if score > best_score:
        best_score = score
        best_prompt = prompt

print(f"Best Prompt: {best_prompt} (Score: {best_score:.4f})")
```

## 5. 주의사항

### 5.1. 모델 로딩 시간

- 첫 요청 시 CLIP 모델 로딩으로 약 **5~10초** 소요될 수 있습니다.
- KoCLIP과 OpenAI CLIP은 독립적으로 로딩됩니다.
- 이후 요청은 즉시 처리됩니다 (싱글톤 패턴).

### 5.2. 한글 텍스트 인식

**KoCLIP의 강점**:
- ✅ **한글 프롬프트 이해**: "사과"라는 개념을 정확히 파악
- ✅ **이미지 내 한글 인식**: 이미지에 "사과"라는 글자가 있으면 시각적 패턴으로 인식
- ✅ **의미 연결**: 텍스트 "사과"와 이미지 속 한글 "사과"를 연결

**한계**:
- ❌ **정확한 OCR 아님**: "1,000원"의 정확한 숫자보다 "가격표"라는 시각적 패턴 인식
- ❌ **복잡한 문장**: 매우 긴 문장이나 복잡한 구문은 성능 저하 가능

**권장사항**:
- 정확한 텍스트 검증이 필요한 경우 `EasyOCR` 또는 `Tesseract` 병행 사용
- 프롬프트는 명확하고 간결하게 작성 (핵심 키워드 중심)

### 5.3. GPU 메모리

| 모델 | VRAM 사용량 |
|------|-------------|
| OpenAI CLIP (ViT-B/32) | ~1.5GB |
| KoCLIP (koclip-base-pt) | ~1.8GB |
| **동시 로딩 시** | ~3.3GB |

GPU가 없는 환경에서는 자동으로 CPU로 폴백됩니다 (속도 감소).

## 6. 아키텍처

### 6.1. 파일 구조

```
src/nanoCocoa_aiserver/
├── api/routers/
│   └── clip.py              # CLIP Score API 엔드포인트 (KoCLIP + OpenAI)
├── core/
│   └── clip_service.py      # CLIP Score 계산 핵심 로직 (싱글톤, 멀티 모델)
├── schemas/
│   └── clip.py              # Pydantic 요청/응답 스키마 (model_type 지원)
└── requirements.txt          # CLIP 의존성 (ftfy, regex, CLIP, transformers)
```

### 6.2. 핵심 클래스

#### `ClipService` (싱글톤, 멀티 모델 지원)

```python
class ClipService:
    """CLIP Score 계산 서비스 (싱글톤 패턴)"""
    
    def calculate_clip_score(
        self, 
        image_base64: str, 
        prompt: str,
        model_type: Literal["openai", "koclip"] = "koclip"
    ) -> float:
        """이미지-텍스트 코사인 유사도 계산"""
        if model_type == "openai":
            return self._calculate_openai_clip_score(image, prompt)
        else:
            return self._calculate_koclip_score(image, prompt)
    
    def _calculate_koclip_score(self, image: Image.Image, prompt: str) -> float:
        """KoCLIP으로 점수 계산 (한글 지원)"""
        # 1. 이미지와 텍스트 전처리
        # 2. 특징 추출 및 유사도 계산 (0~100 → 0~1 정규화)
        pass
```

## 7. 설치 및 실행

### 7.1. 의존성 설치

```bash
# conda 환경 활성화
conda activate py311_ad

# CLIP 및 KoCLIP 라이브러리 설치
pip install ftfy regex tqdm transformers
pip install git+https://github.com/openai/CLIP.git
```

### 7.2. 서버 실행

```bash
cd src/nanoCocoa_aiserver
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 7.3. API 문서 확인

브라우저에서 `http://localhost:8000/docs` 접속 → **CLIP Score** 섹션 확인.

### 7.4. 테스트 실행

```bash
python examples/test_clip_score.py
```

## 8. 참고 자료

### 논문
- [CLIP (2021)](https://arxiv.org/abs/2103.00020): Learning Transferable Visual Models From Natural Language Supervision
- [CLIPScore (2021)](https://arxiv.org/abs/2104.08718): CLIPScore: A Reference-free Evaluation Metric for Image Captioning

### 모델
- [OpenAI CLIP GitHub](https://github.com/openai/CLIP): 원본 CLIP 모델
- [KoCLIP (Hugging Face)](https://huggingface.co/Bingsu/koclip-base-pt): 한국어 CLIP 모델
- [KoCLIP 논문](https://arxiv.org/abs/2211.14031): KoCLIP: Korean Contrastive Language-Image Pretraining
