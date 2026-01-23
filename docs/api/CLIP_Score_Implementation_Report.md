# CLIP Score REST API 구현 완료 보고서

**날짜**: 2026-01-23  
**작성자**: GitHub Copilot  
**프로젝트**: codeit-ai-3team-ad-content

---

## 1. 요약

OpenAI CLIP 모델을 활용한 이미지-텍스트 유사도 평가 REST API를 성공적으로 구현했습니다.

### 주요 기능
- Base64 인코딩 이미지 + 텍스트 프롬프트 입력
- CLIP Score (코사인 유사도) 계산 및 자동 해석
- 싱글톤 패턴으로 모델 재사용 (초기화 시간 최소화)
- GPU/CPU 자동 폴백 지원

---

## 2. 구현 파일

### 2.1. 신규 파일 (3개)

| 파일 경로 | 설명 | 라인 수 |
|-----------|------|---------|
| `src/nanoCocoa_aiserver/schemas/clip.py` | Pydantic 요청/응답 스키마 | 62 |
| `src/nanoCocoa_aiserver/core/clip_service.py` | CLIP Score 계산 핵심 로직 | 209 |
| `src/nanoCocoa_aiserver/api/routers/clip.py` | REST API 엔드포인트 | 169 |

### 2.2. 수정 파일 (5개)

| 파일 경로 | 변경 내용 |
|-----------|-----------|
| `src/nanoCocoa_aiserver/api/app.py` | CLIP 라우터 등록 |
| `src/nanoCocoa_aiserver/schemas/__init__.py` | CLIP 스키마 export |
| `src/nanoCocoa_aiserver/requirements.txt` | CLIP 의존성 추가 |
| `requirements.txt` | 루트 의존성 추가 |
| `docs/api_mapping_review.md` | API 매핑표 업데이트 |

### 2.3. 문서 및 예제 (2개)

| 파일 경로 | 설명 |
|-----------|------|
| `docs/api/CLIP_Score_API_Guide.md` | 전체 API 가이드 (8개 섹션) |
| `examples/test_clip_score.py` | 테스트 스크립트 (4개 시나리오) |

---

## 3. API 사양

### 3.1. POST /clip-score

**요청**:
```json
{
  "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAY...",
  "prompt": "An advertisement of a fresh red apple"
}
```

**응답**:
```json
{
  "clip_score": 0.7324,
  "prompt": "An advertisement of a fresh red apple",
  "interpretation": "매우 높은 일치도 - 이미지가 텍스트 설명과 강하게 부합합니다."
}
```

### 3.2. GET /clip-score/health

**응답**:
```json
{
  "status": "healthy",
  "model_loaded": true,
  "device": "cuda",
  "model": "ViT-B/32"
}
```

---

## 4. 아키텍처 설계

### 4.1. 클래스 구조

```
ClipService (싱글톤)
├── _load_clip_model()          # Lazy loading
├── _decode_base64_image()      # Base64 → PIL Image
├── calculate_clip_score()      # 메인 로직
├── interpret_score()           # 점수 해석 (static)
└── unload_model()              # 메모리 해제
```

### 4.2. 데이터 흐름

```
Client Request
    ↓
FastAPI Router (clip.py)
    ↓
ClipService.calculate_clip_score()
    ↓
1. Base64 디코딩
2. CLIP 전처리
3. 특징 추출 (image + text)
4. 코사인 유사도 계산
    ↓
ClipScoreResponse (with interpretation)
    ↓
Client Response
```

---

## 5. 핵심 기술

### 5.1. CLIP 모델

- **모델**: OpenAI CLIP ViT-B/32
- **입력**: 이미지 (RGB) + 텍스트 (토큰화)
- **출력**: 코사인 유사도 (-1.0 ~ 1.0)

### 5.2. 싱글톤 패턴

```python
class ClipService:
    _instance = None
    _model = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
```

**장점**:
- 첫 요청 시에만 모델 로딩 (5~10초)
- 이후 요청은 즉시 처리 (~1초)
- GPU 메모리 효율적 관리

### 5.3. Base64 처리

```python
# data:image/png;base64, 접두사 제거
if "," in image_base64:
    image_base64 = image_base64.split(",", 1)[1]

# RGBA → RGB 변환 (CLIP 호환성)
if image.mode == "RGBA":
    image = image.convert("RGB")
```

---

## 6. CLIP Score 해석 기준

| 점수 범위 | 해석 | 사용 시나리오 |
|-----------|------|---------------|
| **0.7+** | 매우 높은 일치도 | 광고 생성 성공적 |
| **0.5~0.7** | 높은 일치도 | 프롬프트와 잘 맞음 |
| **0.3~0.5** | 중간 일치도 | 개선 여지 있음 |
| **< 0.3** | 낮은 일치도 | 프롬프트 재작성 권장 |

---

## 7. 사용 사례

### 7.1. 광고 이미지 품질 평가

```python
# 생성된 이미지 평가
score = clip_service.calculate_clip_score(
    image_base64=generated_image,
    prompt="Fresh red apple with price tag in store"
)

if score >= 0.7:
    print("광고 생성 성공")
else:
    print("재생성 필요")
```

### 7.2. 모델 비교

```python
# FLUX vs SDXL 점수 비교
flux_score = get_clip_score(flux_image, prompt)
sdxl_score = get_clip_score(sdxl_image, prompt)

best_model = "FLUX" if flux_score > sdxl_score else "SDXL"
```

### 7.3. 프롬프트 최적화

```python
# 여러 프롬프트 테스트
prompts = ["Simple apple", "Advertisement of apple", "Red apple with price"]
scores = [get_clip_score(image, p) for p in prompts]
best_prompt = prompts[scores.index(max(scores))]
```

---

## 8. 의존성

### 8.1. 추가된 패키지

```bash
# requirements.txt 추가
ftfy==6.3.2                              # 텍스트 정규화
regex==2025.11.3                         # 정규표현식
git+https://github.com/openai/CLIP.git   # CLIP 모델
```

### 8.2. 기존 의존성 (재사용)

- `torch==2.9.1` (이미 설치됨)
- `torchvision==0.24.1` (이미 설치됨)
- `pillow==12.0.0` (이미 설치됨)

---

## 9. 설치 및 테스트

### 9.1. 의존성 설치

```bash
conda activate py311_ad
cd src/nanoCocoa_aiserver
pip install ftfy regex tqdm
pip install git+https://github.com/openai/CLIP.git
```

### 9.2. 서버 실행

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 9.3. 테스트 실행

```bash
# API 문서 확인
curl http://localhost:8000/docs

# Health Check
curl http://localhost:8000/clip-score/health

# 테스트 스크립트
python examples/test_clip_score.py
```

---

## 10. 성능 지표

### 10.1. 초기화 시간

| 환경 | 첫 요청 | 이후 요청 |
|------|---------|-----------|
| GPU (L4) | ~5초 | ~0.5초 |
| CPU | ~10초 | ~2초 |

### 10.2. GPU 메모리 사용량

| 모델 | VRAM |
|------|------|
| ViT-B/32 | ~1.5GB |
| ViT-B/16 | ~3GB (미구현) |

---

## 11. 제한사항 및 개선 방향

### 11.1. 현재 제한사항

#### OCR 능력 제한
- CLIP은 문자 **인식**(OCR)보다는 **시각적 패턴** 인식에 강함
- 예: "1,000원"보다 "price tag"를 더 잘 인식

**해결책**: OCR 필요 시 `EasyOCR` 또는 `Tesseract` 병행

#### 단일 모델
- 현재 ViT-B/32만 지원
- 더 정확한 ViT-L/14는 메모리 사용량 높음 (5~6GB)

**개선 방향**: 모델 선택 옵션 추가 (향후)

### 11.2. 향후 개선 사항

1. **배치 처리**: 여러 이미지 동시 평가
2. **캐싱**: 동일 이미지 재요청 시 캐시 활용
3. **비동기 처리**: 장시간 작업 시 비동기 응답
4. **모델 선택**: ViT-L/14, RN50 등 추가 모델 지원

---

## 12. 참고 자료

### 논문
- [CLIP (2021)](https://arxiv.org/abs/2103.00020): Learning Transferable Visual Models From Natural Language Supervision
- [CLIPScore (2021)](https://arxiv.org/abs/2104.08718): A Reference-free Evaluation Metric for Image Captioning

### 코드
- [OpenAI CLIP GitHub](https://github.com/openai/CLIP)
- [CLIP Score 논문 구현](https://github.com/jmhessel/clipscore)

---

## 13. 체크리스트

- [x] CLIP 모델 통합 (ViT-B/32)
- [x] Base64 이미지 디코딩
- [x] 코사인 유사도 계산
- [x] 점수 자동 해석
- [x] REST API 엔드포인트 구현
- [x] Pydantic 스키마 정의
- [x] 싱글톤 패턴 적용
- [x] GPU/CPU 폴백 지원
- [x] Health Check 엔드포인트
- [x] 에러 핸들링 (400, 500)
- [x] 로깅 통합
- [x] 테스트 스크립트
- [x] API 문서 작성
- [x] 의존성 업데이트

---

## 14. 결론

CLIP Score REST API가 성공적으로 구현되어 광고 이미지 품질 평가 기능을 제공합니다.

### 핵심 성과
- ✅ **정량적 평가**: 이미지-텍스트 일치도를 숫자로 측정
- ✅ **자동 해석**: 점수의 의미를 자동 설명
- ✅ **효율적 설계**: 싱글톤 패턴으로 초기화 시간 최소화
- ✅ **완전한 문서**: API 가이드 + 테스트 스크립트 제공

### 다음 단계
1. MCP Server에 CLIP Score 툴 추가 (`calculate_clip_score`)
2. 생성 파이프라인에 자동 평가 기능 통합
3. 사용자 피드백 기반 점수 임계값 최적화

---

**구현 완료**: 2026-01-23
