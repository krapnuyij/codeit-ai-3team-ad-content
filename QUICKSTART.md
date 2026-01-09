# 환경 설정 빠른 시작 가이드

## 📋 3가지 설치 방법

### 1️⃣ Conda 환경 (권장)

**장점**: CUDA Toolkit 자동 설치, 플랫폼 독립적

```bash
# 환경 생성 및 활성화
conda env create -f environment.yml
conda activate py311_ad

# 설치 확인
python -c "import torch; print(f'PyTorch: {torch.__version__}')"
```

---

### 2️⃣ pip 전용 (conda 없이)

**장점**: 경량, 빠른 설치

```bash
# 1. Python 3.11 가상환경 생성
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. PyTorch 먼저 설치 (CUDA 12.8)
pip install torch==2.9.0 torchvision==0.24.0 torchaudio==2.9.0 --index-url https://download.pytorch.org/whl/cu128

# 3. 나머지 패키지 설치
pip install -r requirements.txt
```

**CPU 전용** (CUDA 없는 경우):
```bash
pip install torch==2.9.0 torchvision==0.24.0 torchaudio==2.9.0 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

---

### 3️⃣ Docker (배포용)

**장점**: 재현성, 격리된 환경

#### docker-compose 사용 (권장)

```bash
cd src/nanoCocoa_aiserver

# 빌드 및 백그라운드 실행
sudo docker-compose up -d --build

# 로그 확인
sudo docker-compose logs -f

# 중지
sudo docker-compose down

# 재시작
sudo docker-compose restart
```

#### Docker 명령어 직접 사용

```bash
cd src/nanoCocoa_aiserver

# 이미지 빌드
docker build -t nanococoa-aiserver .

# 컨테이너 실행
docker run --gpus all -p 8000:8000 nanococoa-aiserver
```

**상세 가이드**: [src/nanoCocoa_aiserver/DOCKER.md](src/nanoCocoa_aiserver/DOCKER.md)

---

## 🔍 설치 확인

```bash
# Python 버전
python --version  # Python 3.11.x

# PyTorch 및 CUDA
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"CPU\"}')"

# 주요 패키지
python -c "import transformers, fastapi, gradio; print('All imports OK')"
```

---

## ⚙️ 플랫폼별 차이점

| 패키지 | Linux | Windows | macOS |
|--------|-------|---------|-------|
| `triton` | 자동 설치 | ❌ 미지원 | ❌ 미지원 |
| `kornia_rs` | 자동 설치 | ❌ 미지원 | ❌ 미지원 |
| `bitsandbytes` | 자동 설치 | ⚠️ 비공식 | ❌ 미지원 |
| `opencv-python-headless` | | | |

**플랫폼 조건**: `requirements.txt`에 `sys_platform == "linux"` 조건으로 자동 처리됨

---

## 🐛 자주 발생하는 문제

### 1. CUDA 버전 불일치
```bash
# 시스템 CUDA 확인
nvidia-smi

# PyTorch CUDA 확인
python -c "import torch; print(torch.version.cuda)"
```

### 2. 메모리 부족
```bash
pip install -r requirements.txt --no-cache-dir
```

### 3. Windows에서 C++ 컴파일러 에러
- [Visual Studio Build Tools](https://visualstudio.microsoft.com/downloads/) 설치 필요

---

## 📚 상세 문서

- **상세 설치 가이드**: [src/nanoCocoa_aiserver/INSTALL.md](src/nanoCocoa_aiserver/INSTALL.md)
- **프로젝트 아키텍처**: [docs/doc/아키텍처설계.md](docs/doc/아키텍처설계.md)
- **환경 설정 가이드**: [docs/doc/환경설정_가이드.md](docs/doc/환경설정_가이드.md)

---

## 💡 환경 파일 비교

| 파일 | 용도 | 패키지 수 | CUDA 포함 |
|------|------|----------|----------|
| `environment.yml` | Conda 전체 환경 | 28 (conda) + 172 (pip) | |
| `requirements.txt` | pip 전용 (개발) | 224 | ❌ (별도 설치) |
| `requirements-docker.txt` | Docker 경량화 | 109 | ❌ (베이스 이미지) |

---

**빠른 선택 가이드**:
- 🏢 **개발 환경**: `environment.yml` (Conda)
- 💻 **로컬 테스트**: `requirements.txt` (pip)
- 🐳 **배포/운영**: `requirements-docker.txt` (Docker)
