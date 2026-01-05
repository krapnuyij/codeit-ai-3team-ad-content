# auto_unload 옵션 기반 메모리 관리 구현

## 1. 개요

CUDA OOM(Out of Memory) 문제 해결을 위한 `auto_unload` 옵션 기반 메모리 관리 시스템을 구현했습니다.

### 1.1 문제 상황

- **발생 시점**: Step 3 (Composition) 진행 시 Flux Inpainting 파이프라인 로드 시도
- **메모리 상태**: GPU 22GB 중 21.75GB 사용 (Step 1 SDXL, Step 2 BiRefNet 모델이 메모리에 상주)
- **오류 내용**: 54MB 추가 할당 실패로 `torch.OutOfMemoryError` 발생

### 1.2 해결 전략

각 단계 완료 후 사용한 모델을 즉시 언로드하여 메모리를 확보하되, 옵션으로 제어 가능하도록 구현.

## 2. 구현 내용

### 2.1 스키마 확장 (request.py)

```python
auto_unload: bool = Field(
    True,
    title="자동 메모리 해제 (Auto Unload)",
    description="각 단계 완료 후 모델을 자동으로 언로드"
)
```

- **기본값**: `True` (메모리 효율 우선)
- **False 설정 시**: 모델 캐싱으로 성능 우선 (경량 모델 사용 시)

### 2.2 설정 파일 (config.py)

```python
AUTO_UNLOAD_DEFAULT = True  # 전역 기본값
```

### 2.3 메모리 모니터링 (services/monitor.py)

```python
def log_gpu_memory(label: str = "") -> None:
    """GPU 메모리 사용량 로깅"""
    allocated = torch.cuda.memory_allocated(0) / 1024**3
    reserved = torch.cuda.memory_reserved(0) / 1024**3
    logger.info(
        f"[{label}] GPU Memory: allocated={allocated:.2f}GB, "
        f"reserved={reserved:.2f}GB"
    )
```

### 2.4 모델 클래스별 unload() 메서드 추가

#### 2.4.1 SegmentationModel (models/segmentation.py)

```python
def unload(self) -> None:
    """BiRefNet 리소스 정리"""
    from services.monitor import log_gpu_memory
    log_gpu_memory("BiRefNet unload (no-op)")
    flush_gpu()
    logger.info("🧹 BiRefNet unloaded")
```

#### 2.4.2 FluxGenerator (models/flux_generator.py)

```python
def unload(self) -> None:
    """Flux 모델 리소스 정리"""
    from services.monitor import log_gpu_memory
    log_gpu_memory("FluxGenerator unload (no-op)")
    flush_gpu()
    logger.info("🧹 FluxGenerator unloaded")
```

#### 2.4.3 SDXLTextGenerator (models/sdxl_text.py)

```python
def unload(self) -> None:
    """SDXL 모델 리소스 정리"""
    from services.monitor import log_gpu_memory
    log_gpu_memory("SDXLTextGenerator unload (no-op)")
    flush_gpu()
    logger.info("🧹 SDXLTextGenerator unloaded")
```

#### 2.4.4 CompositionEngine (models/CompositionEngine.py)

```python
def _unload_pipeline(self):
    """Flux Inpainting 파이프라인 언로드"""
    from services.monitor import log_gpu_memory
    
    if self.pipe is not None:
        log_gpu_memory("Before Flux Inpainting unload")
        del self.pipe
        self.pipe = None
        gc.collect()
        torch.cuda.empty_cache()
        log_gpu_memory("After Flux Inpainting unload")
        logger.info("🧹 Flux Inpainting pipeline unloaded")

def unload(self) -> None:
    """명시적 리소스 정리"""
    self._unload_pipeline()
```

### 2.5 AIModelEngine 확장 (core/engine.py)

#### 2.5.1 초기화 파라미터 추가

```python
def __init__(self, dummy_mode: bool = False, 
             progress_callback=None, 
             auto_unload: bool = True):
    self.auto_unload = auto_unload
    logger.info(f"AIModelEngine initialized: auto_unload={auto_unload}")
```

#### 2.5.2 단계별 언로드 메서드

```python
def unload_step1_models(self) -> None:
    """Step 1 모델 언로드 (Flux 배경 생성)"""
    from services.monitor import log_gpu_memory
    log_gpu_memory("Before Step1 models unload")
    self.flux_gen.unload()
    log_gpu_memory("After Step1 models unload")
    logger.info("✅ Step 1 models unloaded")

def unload_step2_models(self) -> None:
    """Step 2 모델 언로드 (SDXL, BiRefNet)"""
    from services.monitor import log_gpu_memory
    log_gpu_memory("Before Step2 models unload")
    self.sdxl_gen.unload()
    self.segmenter.unload()
    log_gpu_memory("After Step2 models unload")
    logger.info("✅ Step 2 models unloaded")
```

#### 2.5.3 Step 3 완료 후 자동 언로드

```python
def run_intelligent_composite(...):
    result = self.compositor.compose(...)
    
    # Step 3 완료 후 자동 언로드
    if self.auto_unload:
        self.compositor.unload()
    
    return result
```

### 2.6 프로세서 통합 (core/processors.py)

#### 2.6.1 Step 2 완료 후

```python
def process_step2_text(...):
    transparent_text, _ = engine.run_segmentation(raw_3d_text)

    # Step 2 완료 후 Step 1 모델 언로드
    if hasattr(engine, 'auto_unload') and engine.auto_unload:
        engine.unload_step1_models()

    return transparent_text
```

#### 2.6.2 Step 3 시작 전

```python
def process_step3_composite(...):
    # Step 3 시작 전 이전 단계 모델 언로드
    if hasattr(engine, 'auto_unload') and engine.auto_unload:
        engine.unload_step1_models()
        engine.unload_step2_models()
    
    # ... 합성 로직 ...
```

### 2.7 워커 통합 (core/worker.py)

```python
auto_unload = input_data.get('auto_unload', True)
engine = AIModelEngine(
    dummy_mode=test_mode, 
    progress_callback=update_progress,
    auto_unload=auto_unload
)
```

## 3. 메모리 해제 타이밍

```
┌─────────────┬──────────────┬────────────────┬─────────────────┐
│   단계      │   사용 모델   │  언로드 시점    │   해제 대상      │
├─────────────┼──────────────┼────────────────┼─────────────────┤
│ Step 1      │ Flux         │ Step 2 완료 후  │ Flux            │
│ (배경 생성) │              │                │                 │
├─────────────┼──────────────┼────────────────┼─────────────────┤
│ Step 2      │ SDXL         │ Step 3 시작 전  │ SDXL            │
│ (텍스트)    │ BiRefNet     │                │ BiRefNet        │
│             │              │                │ + Flux (중복방지)│
├─────────────┼──────────────┼────────────────┼─────────────────┤
│ Step 3      │ Flux         │ Step 3 완료 후  │ Flux Inpainting │
│ (합성)      │ Inpainting   │                │                 │
└─────────────┴──────────────┴────────────────┴─────────────────┘
```

## 4. 로그 출력 예시

```
[Before Step1 models unload] GPU Memory: allocated=21.75GB, reserved=22.00GB
[FluxGenerator unload (no-op)] GPU Memory: allocated=12.30GB, reserved=13.00GB
🧹 FluxGenerator unloaded
[After Step1 models unload] GPU Memory: allocated=12.30GB, reserved=13.00GB
✅ Step 1 models unloaded

[Before Step2 models unload] GPU Memory: allocated=18.20GB, reserved=19.00GB
[SDXLTextGenerator unload (no-op)] GPU Memory: allocated=12.50GB, reserved=13.50GB
🧹 SDXLTextGenerator unloaded
[BiRefNet unload (no-op)] GPU Memory: allocated=10.20GB, reserved=11.00GB
🧹 BiRefNet unloaded
[After Step2 models unload] GPU Memory: allocated=10.20GB, reserved=11.00GB
✅ Step 2 models unloaded

[Before Flux Inpainting unload] GPU Memory: allocated=21.50GB, reserved=22.00GB
[After Flux Inpainting unload] GPU Memory: allocated=0.50GB, reserved=2.00GB
🧹 Flux Inpainting pipeline unloaded
```

## 5. API 사용 예시

### 5.1 기본 사용 (auto_unload=True)

```json
{
  "text_content": "Summer Sale",
  "bg_prompt": "Beach sunset",
  "auto_unload": true
}
```

- 각 단계 완료 후 자동 언로드
- OOM 방지, 메모리 효율 최우선
- 연속 요청 시 재로드 시간 소요

### 5.2 성능 우선 (auto_unload=False)

```json
{
  "text_content": "Summer Sale",
  "bg_prompt": "Beach sunset",
  "auto_unload": false
}
```

- 모델을 메모리에 유지
- 연속 요청 시 빠른 응답
- 경량 모델 적용 후 사용 권장

## 6. 향후 확장 가능성

### 6.1 단계별 세분화 옵션

```python
auto_unload_step1: bool = True
auto_unload_step2: bool = True
auto_unload_step3: bool = True
```

### 6.2 메모리 임계값 기반 자동 판단

```python
if torch.cuda.memory_allocated(0) / torch.cuda.max_memory_allocated(0) > 0.9:
    # 자동으로 이전 모델 언로드
    engine.unload_step1_models()
```

### 6.3 경량 모델 적용 후 기본값 변경

```python
# 경량 모델 환경에서는 캐싱 우선
AUTO_UNLOAD_DEFAULT = False
```

## 7. 테스트 시나리오

1. **OOM 재현 테스트**: `auto_unload=False` → Step 3에서 OOM 발생 확인
2. **메모리 해제 검증**: `auto_unload=True` → 로그에서 메모리 감소 확인
3. **성능 비교**: 연속 10회 요청 시 `True` vs `False` 평균 응답 시간 측정
4. **재현성 검증**: 동일 seed + 파라미터로 `auto_unload` 값 변경해도 동일 결과 확인

## 8. 주의사항

- 현재 모델들은 이미 메서드 내부에서 load/unload를 수행하므로, `unload()` 메서드는 추가 `flush_gpu()` 호출로 구현
- CompositionEngine만 파이프라인을 인스턴스 변수로 유지하므로 실질적 언로드 수행
- `auto_unload=False` 사용 시 GPU 메모리 22GB 초과 가능성 → 모니터링 필수
