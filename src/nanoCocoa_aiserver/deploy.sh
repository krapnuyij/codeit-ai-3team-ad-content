#!/bin/bash
# Docker 빌드 및 배포 스크립트

set -e

# 색상 코드
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== nanoCocoa AI Server Docker 빌드 및 배포 ===${NC}"

# 1. 디렉토리 확인
if [ ! -f "Dockerfile" ]; then
    echo -e "${RED}❌ Dockerfile이 없습니다. src/nanoCocoa_aiserver 디렉토리에서 실행하세요.${NC}"
    exit 1
fi

# 2. HuggingFace 캐시 디렉토리 생성
echo -e "${YELLOW}📁 HuggingFace 캐시 디렉토리 생성...${NC}"
sudo mkdir -p /opt/huggingface
sudo chown -R $USER:$USER /opt/huggingface
echo -e "${GREEN}/opt/huggingface 생성 완료${NC}"

# 3. 로컬 디렉토리 생성
echo -e "${YELLOW}📁 로컬 디렉토리 생성...${NC}"
mkdir -p static/uploads static/results logs
echo -e "${GREEN}로컬 디렉토리 생성 완료${NC}"

# 4. GPU 확인
echo -e "${YELLOW}🔍 GPU 확인...${NC}"
if ! command -v nvidia-smi &> /dev/null; then
    echo -e "${RED}❌ nvidia-smi를 찾을 수 없습니다. NVIDIA 드라이버를 설치하세요.${NC}"
    exit 1
fi
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
echo -e "${GREEN}GPU 확인 완료${NC}"

# 5. NVIDIA Container Toolkit 확인
echo -e "${YELLOW}🔍 NVIDIA Container Toolkit 확인...${NC}"
if ! docker run --rm --gpus all nvidia/cuda:12.9.1-base-ubuntu22.04 nvidia-smi &> /dev/null; then
    echo -e "${RED}❌ NVIDIA Container Toolkit이 설치되지 않았거나 작동하지 않습니다.${NC}"
    echo -e "${YELLOW}설치 방법: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html${NC}"
    exit 1
fi
echo -e "${GREEN}NVIDIA Container Toolkit 확인 완료${NC}"

# 6. 이전 컨테이너 중지 및 삭제
echo -e "${YELLOW}🛑 이전 컨테이너 중지 및 삭제...${NC}"
docker-compose down 2>/dev/null || true
echo -e "${GREEN}이전 컨테이너 정리 완료${NC}"

# 7. 이미지 빌드
echo -e "${YELLOW}🔨 Docker 이미지 빌드 시작...${NC}"
docker-compose build --no-cache
echo -e "${GREEN}이미지 빌드 완료${NC}"

# 8. 컨테이너 시작
echo -e "${YELLOW}🚀 컨테이너 시작...${NC}"
docker-compose up -d
echo -e "${GREEN}컨테이너 시작 완료${NC}"

# 9. 헬스체크 대기
echo -e "${YELLOW}⏳ 서버 시작 대기 (최대 60초)...${NC}"
for i in {1..60}; do
    if curl -f http://localhost:8000/health &> /dev/null; then
        echo -e "${GREEN}서버가 정상적으로 시작되었습니다!${NC}"
        break
    fi
    if [ $i -eq 60 ]; then
        echo -e "${RED}❌ 서버 시작 실패 (60초 타임아웃)${NC}"
        echo -e "${YELLOW}로그 확인: docker-compose logs -f${NC}"
        exit 1
    fi
    sleep 1
    echo -n "."
done

# 10. 상태 확인
echo -e "\n${GREEN}=== 배포 완료 ===${NC}"
echo -e "${YELLOW}컨테이너 상태:${NC}"
docker-compose ps

echo -e "\n${YELLOW}GPU 사용량:${NC}"
nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader

echo -e "\n${YELLOW}유용한 명령어:${NC}"
echo -e "  로그 확인:    ${GREEN}docker-compose logs -f${NC}"
echo -e "  중지:         ${GREEN}docker-compose down${NC}"
echo -e "  재시작:       ${GREEN}docker-compose restart${NC}"
echo -e "  상태 확인:    ${GREEN}curl http://localhost:8000/health${NC}"
echo -e "  컨테이너 접속: ${GREEN}docker exec -it nanococoa-aiserver bash${NC}"

echo -e "\n${GREEN}🎉 배포 완료! 서버가 http://localhost:8000 에서 실행 중입니다.${NC}"
