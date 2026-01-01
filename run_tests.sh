#!/bin/bash
# 
# pytest 테스트 실행 스크립트
# 
# 사용법:
#   ./run_tests.sh --dummy    # 더미 모드 (빠른 인터페이스 테스트)
#   ./run_tests.sh            # 전체 모드 (느린 모델 테스트 포함)

set -e

# 색상 정의
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}AI Ad Generator - Test Suite${NC}"
echo -e "${GREEN}========================================${NC}"

# 더미 모드 체크
DUMMY_FLAG=""
if [[ "$1" == "--dummy" ]]; then
    DUMMY_FLAG="--dummy"
    echo -e "${YELLOW}[모드] 더미 모드 (GPU 미사용, 빠른 테스트)${NC}"
else
    echo -e "${YELLOW}[모드] 전체 모드 (GPU 사용, 느린 테스트)${NC}"
fi

# 타임스탬프
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_DIR="tests/reports"
HTML_REPORT="${REPORT_DIR}/report_${TIMESTAMP}.html"

echo ""
echo -e "${GREEN}[1/3] 단위 테스트 실행...${NC}"
conda run -n py311_ad python -m pytest tests/units/ $DUMMY_FLAG \
    -v --tb=short \
    --html="${HTML_REPORT}" --self-contained-html

echo ""
echo -e "${GREEN}[2/3] 통합 테스트 실행...${NC}"
conda run -n py311_ad python -m pytest tests/integration/ $DUMMY_FLAG \
    -v --tb=short \
    --html="${HTML_REPORT}" --self-contained-html

echo ""
echo -e "${GREEN}[3/3] 커버리지 분석...${NC}"
conda run -n py311_ad python -m pytest tests/units/ tests/integration/ $DUMMY_FLAG \
    --cov=src/nanoCocoa_aiserver \
    --cov-report=html:${REPORT_DIR}/coverage_${TIMESTAMP} \
    --cov-report=term-missing

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}테스트 완료!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "HTML 리포트: ${HTML_REPORT}"
echo -e "커버리지: ${REPORT_DIR}/coverage_${TIMESTAMP}/index.html"
echo ""
