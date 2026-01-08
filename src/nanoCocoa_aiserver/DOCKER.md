# nanoCocoa AI Server - Docker 배포 가이드

## 📦 사전 준비

### 1. Docker 및 NVIDIA Container Toolkit 설치

```bash
# Docker 설치 (Ubuntu)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# NVIDIA Container Toolkit 설치
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker

# 설치 확인
docker run --rm --gpus all nvidia/cuda:12.9.1-base-ubuntu22.04 nvidia-smi
```

### 2. HuggingFace 캐시 디렉토리 생성

```bash
# 외부 볼륨 디렉토리 생성 (200GB 디스크)
sudo mkdir -p /opt/huggingface
sudo chown -R $USER:$USER /opt/huggingface
```

---

## 🚀 빌드 및 실행

### 방법 1: docker-compose 사용 (권장)

```bash
cd /home/spai0433/codeit-ai-3team-ad-content/src/nanoCocoa_aiserver

# 빌드 및 실행
docker-compose up -d --build

# 로그 확인
docker-compose logs -f

# 중지
docker-compose down

# 재시작
docker-compose restart
```

### 방법 2: Docker 명령어 직접 사용

```bash
# 이미지 빌드
docker build -t nanococoa-aiserver:latest .

# 컨테이너 실행
docker run -d \
  --name nanococoa-aiserver \
  --gpus all \
  -p 8000:8000 \
  -v /opt/huggingface:/root/.cache/huggingface \
  -v $(pwd)/static/uploads:/app/static/uploads \
  -v $(pwd)/static/results:/app/static/results \
  -v $(pwd)/logs:/app/logs \
  -e PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  -e HF_HOME=/root/.cache/huggingface \
  --restart unless-stopped \
  nanococoa-aiserver:latest

# 로그 확인
docker logs -f nanococoa-aiserver

# 중지 및 삭제
docker stop nanococoa-aiserver
docker rm nanococoa-aiserver
```

---

## 📁 볼륨 매핑

| 호스트 경로 | 컨테이너 경로 | 용도 |
|------------|-------------|------|
| `/opt/huggingface` | `/root/.cache/huggingface` | HuggingFace 모델 캐시 (영구) |
| `./static/uploads` | `/app/static/uploads` | 업로드된 이미지 |
| `./static/results` | `/app/static/results` | 생성된 결과 이미지 |
| `./logs` | `/app/logs` | 애플리케이션 로그 |

**중요**: `/opt/huggingface`는 200GB 디스크에 생성하여 모델을 영구 저장합니다.

---

## 🔍 헬스체크 및 모니터링

### 헬스체크 API

```bash
# 서버 상태 확인
curl http://localhost:8000/health

# 응답 예시
{
  "status": "healthy",
  "uptime": 3600,
  "gpu_available": true,
  "models_loaded": 0
}
```

### 컨테이너 상태 확인

```bash
# 컨테이너 상태
docker ps

# 리소스 사용량 (실시간)
docker stats nanococoa-aiserver

# GPU 사용량
nvidia-smi

# 컨테이너 내부 접속
docker exec -it nanococoa-aiserver bash
```

### 로그 확인

```bash
# 전체 로그
docker logs nanococoa-aiserver

# 실시간 로그 (tail -f)
docker logs -f nanococoa-aiserver

# 최근 100줄
docker logs --tail 100 nanococoa-aiserver

# 특정 시간 이후 로그
docker logs --since 10m nanococoa-aiserver
```

---

## 🐛 문제 해결

### 1. GPU가 인식되지 않음

```bash
# NVIDIA Container Toolkit 재시작
sudo systemctl restart docker

# GPU 테스트
docker run --rm --gpus all nvidia/cuda:12.9.1-base-ubuntu22.04 nvidia-smi
```

### 2. 포트가 이미 사용 중

```bash
# 8000 포트 사용 중인 프로세스 확인
sudo lsof -i :8000
sudo netstat -tulpn | grep :8000

# 다른 포트로 변경 (예: 8001)
docker run -p 8001:8000 ...
```

### 3. 디스크 용량 부족

```bash
# 사용하지 않는 Docker 이미지/컨테이너 정리
docker system prune -a

# 볼륨 확인
df -h /opt/huggingface

# 캐시 정리 (필요시)
rm -rf /opt/huggingface/hub/*
```

### 4. 모델 다운로드 느림

```bash
# HuggingFace 토큰 설정 (선택)
docker run -e HF_TOKEN=your_token_here ...

# 또는 .env 파일 생성
echo "HF_TOKEN=your_token_here" > .env
docker-compose up -d
```

### 5. 컨테이너가 계속 재시작됨

```bash
# 에러 로그 확인
docker logs nanococoa-aiserver

# 헬스체크 비활성화 후 재시작
docker run --no-healthcheck ...
```

---

## 🔧 성능 튜닝

### 1. Worker 수 조정

```yaml
# docker-compose.yml 수정
command: ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

### 2. 메모리 제한

```yaml
# docker-compose.yml에 추가
deploy:
  resources:
    limits:
      memory: 32G
    reservations:
      memory: 16G
```

### 3. CUDA 메모리 최적화

```bash
# 환경 변수 추가
-e PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512,expandable_segments:True
```

---

## 📊 운영 가이드

### 1. 백업

```bash
# 모델 캐시 백업
tar -czf huggingface_cache_backup.tar.gz /opt/huggingface

# 결과 파일 백업
tar -czf results_backup.tar.gz ./static/results
```

### 2. 업데이트

```bash
# 코드 업데이트
git pull origin main

# 이미지 재빌드
docker-compose up -d --build

# 또는
docker-compose build --no-cache
docker-compose up -d
```

### 3. 스케일링 (다중 인스턴스)

```yaml
# docker-compose.yml
services:
  nanococoa-aiserver:
    # ... (기존 설정)
    deploy:
      replicas: 2  # 인스턴스 수
```

---

## 🔐 보안 고려사항

### 1. 방화벽 설정

```bash
# UFW 사용 시
sudo ufw allow 8000/tcp
sudo ufw enable
```

### 2. HTTPS 설정 (Nginx 리버스 프록시)

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /etc/ssl/certs/cert.pem;
    ssl_certificate_key /etc/ssl/private/key.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 3. API 키 인증 (선택)

```python
# main.py에 추가
from fastapi import Security, HTTPException
from fastapi.security.api_key import APIKeyHeader

API_KEY = os.getenv("API_KEY", "your-secret-key")
api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
```

---

## 📚 참고 자료

- [Docker 공식 문서](https://docs.docker.com/)
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/)
- [Docker Compose](https://docs.docker.com/compose/)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)

---

## 💡 빠른 명령어 요약

```bash
# 빌드 및 실행
docker-compose up -d --build

# 로그 확인
docker-compose logs -f

# 중지
docker-compose down

# 재시작
docker-compose restart

# 상태 확인
curl http://localhost:8000/health

# GPU 확인
nvidia-smi

# 컨테이너 내부 접속
docker exec -it nanococoa-aiserver bash
```
