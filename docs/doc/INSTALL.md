# 환경 설정 가이드 (Cross-Platform)

이 프로젝트는 **Windows**, **Linux**, **macOS**에서 모두 작동합니다.

## 📋 파일 설명

| 파일 | 용도 | OS 지원 |
|------|------|---------|
| `environment.yml` | Conda 환경 설정 (권장) | Windows/Linux/macOS |
| `requirements.txt` | pip 패키지 목록 | Windows/Linux/macOS |

## 🚀 방법 1: Conda 사용 (권장)

### Windows / Linux / macOS

```bash
# 1. 환경 생성
conda env create -f environment.yml

# 2. 환경 활성화
conda activate py311_ad

# 3. 설치 확인
python -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA Available: {torch.cuda.is_available()}')"
```

### CUDA 없는 시스템 (CPU only)

CUDA가 없는 경우 [environment.yml:28](environment.yml#L28)에서 다음 줄을 주석 처리:
```yaml
  # - pytorch::pytorch-cuda=12.8  # For CUDA systems
```

그 후 동일하게 실행:
```bash
conda env create -f environment.yml
conda activate py311_ad
```

## 🔧 방법 2: pip 사용

### 1단계: Python 환경 생성

#### Conda 사용
```bash
conda create -n py311_ad python=3.11
conda activate py311_ad
```

#### venv 사용 (Python 내장)
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

### 2단계: PyTorch 설치

CUDA 시스템인지에 따라 선택:

#### CUDA 있는 경우 (GPU)
```bash
# CUDA 12.8
pip install torch==2.9.0 torchvision==0.24.0 torchaudio==2.9.0 --index-url https://download.pytorch.org/whl/cu128
```

#### CUDA 없는 경우 (CPU only)
```bash
pip install torch==2.9.0 torchvision==0.24.0 torchaudio==2.9.0 --index-url https://download.pytorch.org/whl/cpu
```

### 3단계: 나머지 패키지 설치
```bash
pip install -r requirements.txt
```

## ⚠️ 플랫폼별 주의사항

### Windows 사용자

다음 패키지들은 플랫폼 조건으로 자동 제외됩니다:

- **triton==3.5.0** - Linux 전용 (`sys_platform == "linux"`)
- **kornia_rs==0.1.10** - Linux 전용
- **bitsandbytes==0.49.0** - Linux 전용 (Windows는 비공식 빌드 필요)

Windows에서 bitsandbytes가 필요한 경우:
```bash
pip install bitsandbytes-windows
```

### Linux 사용자

모든 패키지가 자동으로 설치됩니다. 플랫폼 조건이 자동 적용됨:
```bash
# requirements.txt에 이미 포함 (조건부)
triton==3.5.0; sys_platform == "linux"
kornia_rs==0.1.10; sys_platform == "linux"
bitsandbytes==0.49.0; sys_platform == "linux"
```

### macOS (Apple Silicon - M1/M2/M3)

```bash
# MPS (Metal Performance Shaders) 백엔드 자동 사용
python -c "import torch; print(f'MPS Available: {torch.backends.mps.is_available()}')"
```

## 🔍 설치 후 확인

```bash
# Python 버전 확인
python --version  # Python 3.11.x 여야 함

# 주요 패키지 확인
python -c "import torch, transformers, FastAPI, gradio; print('All imports successful!')"

# CUDA 확인 (GPU 사용 시)
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}'); print(f'Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"CPU\"}')"
```

## 🐛 문제 해결

### 1. Windows에서 C++ 컴파일러 에러
```bash
# Visual Studio Build Tools 설치 필요
# https://visualstudio.microsoft.com/downloads/ (Build Tools for Visual Studio)
```

### 2. Linux에서 컴파일러 에러
```bash
# GCC/G++ 설치
sudo apt-get update
sudo apt-get install build-essential

# 또는 conda로 설치
conda install -c conda-forge cxx-compiler c-compiler
```

### 3. CUDA 버전 불일치
```bash
# 현재 CUDA 버전 확인
nvidia-smi

# PyTorch CUDA 버전 확인
python -c "import torch; print(torch.version.cuda)"
```

### 4. 메모리 부족 에러
```bash
# pip 설치 시 캐시 사용 안 함
pip install -r requirements.txt --no-cache-dir
```

### 5. 패키지 충돌
```bash
# 환경 완전히 삭제 후 재설치
conda env remove -n py311_ad
conda env create -f environment.yml
```

## 📝 환경 내보내기

현재 환경을 다른 시스템에서 재현하려면:

```bash
# Conda 환경 내보내기 (플랫폼 독립적)
conda env export --no-builds > my_environment.yml

# pip 패키지만 내보내기
pip freeze > my_requirements.txt
```

## 🔄 환경 업데이트

```bash
# Conda 환경 업데이트 (사용하지 않는 패키지 제거)
conda env update -f environment.yml --prune

# pip 패키지 업데이트
pip install -r requirements.txt --upgrade
```

## 📚 주요 변경 사항

### 수정된 문제점

1. **python-multipart 중복 제거**
2. **Windows 비호환 패키지 주석 처리** (triton, bitsandbytes, kornia_rs)
3. **모든 패키지에 최소 버전 명시**
4. **ImageIO 대소문자 수정** (ImageIO → imageio)
5. **environment.yml과 requirements.txt 동기화**

### 📦 권장 설치 방법

| 환경 | 권장 방법 | 파일 | 명령어 |
|------|----------|------|--------|
| 개발 환경 (모든 기능) | Conda | `environment.yml` | `conda env create -f environment.yml` |
| 로컬 배포 (pip) | pip | `requirements.txt` | `pip install -r requirements.txt` |
| Docker 컨테이너 | pip | `requirements-docker.txt` | `pip install -r requirements-docker.txt` |

**Docker 사용 시**: `requirements-docker.txt`는 경량화되어 있으며 헤드리스 패키지만 포함합니다.

```dockerfile
FROM nvidia/cuda:12.8.0-cudnn9-runtime-ubuntu22.04
RUN pip install -r requirements-docker.txt
```

## 🎯 빠른 시작

```bash
# 1. 저장소 클론
git clone <repository-url>
cd codeit-ai-3team-ad-content/src/nanoCocoa_aiserver

# 2. 환경 생성 (Conda)
conda env create -f environment.yml
conda activate py311_ad

# 3. 서버 실행
python main.py  # 또는 uvicorn main:app --reload
```

## 💡 추가 정보

- **CUDA Toolkit**: [NVIDIA CUDA Downloads](https://developer.nvidia.com/cuda-downloads)
- **PyTorch 설치 가이드**: [PyTorch Get Started](https://pytorch.org/get-started/locally/)
- **Conda 채널 우선순위**: pytorch > nvidia > conda-forge > defaults
- **가상환경 삭제**: `conda env remove -n py311_ad`
