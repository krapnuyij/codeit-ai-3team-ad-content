# product_image_png_b64 업데이트 가이드

## 변경 개요

`product_image_path` (로컬 파일 경로) → `product_image_png_b64` (PNG base64 인코딩)로 변경하여 클라이언트-서버 간 이미지 전달 방식을 개선했습니다.

**핵심 최적화:** LLM에는 base64 이미지를 전달하지 않고 "이미지 업로드됨" 텍스트만 전달하여 토큰 낭비 방지. 실제 base64 데이터는 MCP 도구 호출 시에만 사용됩니다.

## 변경 이유

1. **환경 독립성**: MCP 서버와 ad_chat이 다른 컨테이너/환경에 있을 경우 로컬 파일 경로로는 서버가 이미지 파일에 접근 불가
2. **토큰 최적화**: LLM에 불필요한 base64 데이터 전송 방지 (수천~수만 토큰 절약)

## 주요 변경 사항

### 1. **generation.py** - 핸들러 수정

```python
async def generate_ad_image(
    product_image_png_b64: Optional[str] = None,  # 변경됨
    ...
) -> str:
    # 제품 이미지 처리 (base64 직접 사용)
    if product_image_png_b64:
        logger.info("제품 이미지 수신 (base64)")
        product_image_b64 = product_image_png_b64
    else:
        logger.info("제품 이미지 없음 - 배경만 생성")
        product_image_b64 = None
```

**변경점:**
- `product_image_path` 파라미터 제거
- `product_image_png_b64` 파라미터 추가
- 파일 시스템 접근(`image_file_to_base64`) 제거
- Base64 문자열을 직접 사용

### 2. **mcp_tools.py** - 스키마 업데이트

```python
"product_image_png_b64": {
    "type": "string",
    "description": "제품 이미지 (PNG base64 인코딩, 선택사항)...",
},
```

### 3. **chat_ui.py** - 이미지 업로더 추가

```python
# 업로드된 제품 이미지 정보 (텍스트로만 전달, base64는 도구 호출 시 사용)
product_image_info = ""
product_image_b64 = st.session_state.get("product_image_b64")
if product_image_b64:
    image_name = st.session_state.get("product_image_name", "unknown")
    product_image_info = f"""

**업로드된 제품 이미지:**
- 파일명: {image_name}
- 상태: ✅ 업로드 완료 (광고 생성 시 자동으로 사용됩니다)
- 참고: 이미지는 generate_ad_image 도구 호출 시 product_image_png_b64 파라미터로 자동 전달됩니다.
"""

# 시스템 프롬프트에 이미지 정보 포함 (base64는 포함 안 함)
system_prompt = f"""당신은 나노코코아(nanoCocoa) AI 광고 생성 시스템의 전문 어시스턴트입니다.
{context_info}{product_image_info}
...
"""
```

**기능:**
- 파일 업로더로 이미지 업로드
- 자동 base64 인코딩 및 세션 상태 저장
- 썸네일 미리보기 제공
- 이미지 제거 버튼
- **LLM에는 이미지 업로드 정보만 텍스트로 전달** (토큰 절약)

### 4. **llm_adapter.py** - 자동 이미지 전달 (토큰 최적화)

```python
class LLMAdapter:
    def __init__(self, ...):
        ...
        # 제품 이미지 base64 (도구 호출 시에만 사용, LLM에는 전달 안 함)
        self._pending_product_image_b64: Optional[str] = None

async def chat(
    self,
    user_message: str,
    max_tool_calls: int = 5,
    product_image_b64: Optional[str] = None,  # 추가
) -> tuple[str, Optional[Dict[str, Any]]]:
    # 제품 이미지를 인스턴스 변수에 저장 (도구 호출 시 사용, LLM에는 전달 안 함)
    self._pending_product_image_b64 = product_image_b64
    ...
    # generate_ad_image 도구 호출 시 자동으로 이미지 추가
    if tool_name == "generate_ad_image":
        if self._pending_product_image_b64 and "product_image_png_b64" not in tool_args:
            logger.info("[제품 이미지 자동 추가] 업로드된 이미지를 product_image_png_b64로 전달 (토큰 절약: LLM에는 미전달)")
            tool_args["product_image_png_b64"] = self._pending_product_image_b64
```

**토큰 절약 전략:**
1. LLM 대화: "업로드된 제품 이미지: banana.png" (텍스트만, ~10 토큰)
2. MCP 도구 호출: 실제 base64 데이터 전달 (수천~수만 바이트, LLM 통과 안 함)
3. 예상 절약: 이미지당 **5,000~20,000 토큰** 절약 (이미지 크기에 따라)

### 5. **시스템 프롬프트 업데이트**

```markdown
- **product_image_png_b64**: 제품 이미지 (PNG base64 인코딩, 선택사항)
  * 세션 상태에 업로드된 이미지가 있으면 자동으로 포함됩니다
  * 사용자가 이미지를 업로드한 경우: `st.session_state.product_image_b64` 값 사용
  * 업로드된 이미지가 없으면 파라미터 생략 (배경 프롬프트만으로 생성)
```

## 사용 흐름

### Case 1: 이미지 업로드 + 광고 생성 (토큰 최적화)

1. 사용자가 이미지 업로더에서 제품 이미지 업로드
2. 이미지가 base64로 인코딩되어 `st.session_state.product_image_b64`에 저장
3. 썸네일 미리보기 표시
4. 사용자가 "바나나 광고 만들어줘" 입력
5. **시스템 프롬프트에 이미지 정보만 텍스트로 추가** (예: "업로드된 제품 이미지: banana.png")
6. `generate_ai_response_async`가 세션 상태에서 이미지를 가져와 LLM Adapter에 전달
7. **LLM Adapter가 `_pending_product_image_b64`에 저장** (LLM 대화에는 포함 안 함)
8. LLM이 `generate_ad_image` 도구 호출 결정
9. **도구 호출 시 `_pending_product_image_b64`를 `product_image_png_b64`로 추가**
10. MCP 서버가 base64 이미지를 받아 처리
11. 광고 생성 시작 후 세션 상태에서 이미지 제거

**토큰 절약 효과:**
- LLM에 전달되는 메시지: "업로드된 제품 이미지: banana.png" (~10 토큰)
- MCP 도구 호출: base64 데이터 직접 전달 (LLM 통과하지 않음)
- 절약된 토큰: 약 **5,000~20,000 토큰/이미지**

### Case 2: 이미지 없이 광고 생성

1. 사용자가 이미지 업로드 없이 "사과 광고 만들어줘" 입력
2. `product_image_b64 = None`으로 LLM Adapter 호출
3. LLM이 `product_image_png_b64` 파라미터 없이 도구 호출
4. 서버가 `background_prompt`만으로 제품 포함 배경 생성

## 테스트 방법

### 1. 이미지 업로드 테스트

```bash
cd /home/spai0433/codeit-ai-3team-ad-content/src/ad_chat
conda activate py311_ad
streamlit run app.py
```

1. 채팅 페이지에서 이미지 업로더 확인
2. 제품 이미지 업로드 (PNG, JPG, JPEG)
3. 썸네일이 정상적으로 표시되는지 확인
4. "🗑️ 이미지 제거" 버튼으로 제거 가능한지 확인

### 2. 광고 생성 테스트 (이미지 있음) - 토큰 최적화 확인

```python
# 테스트 시나리오
1. 제품 이미지 업로드
2. "바나나 특가 광고 만들어줘" 입력
3. 로그 확인:
   - "[디버그] 제품 이미지 업로드됨: banana.png"
   - 시스템 프롬프트에 "업로드된 제품 이미지: banana.png" 포함 확인
   - "[제품 이미지 자동 추가] 업로드된 이미지를 product_image_png_b64로 전달 (토큰 절약: LLM에는 미전달)"
   - "[MCP Handler] bg_model 수신: flux"
   - "제품 이미지 수신 (base64)"
4. 작업 시작 후 이미지가 자동 제거되는지 확인
5. **LLM 대화 히스토리에 base64 데이터가 없는지 확인** (토큰 절약)
```

**토큰 절약 검증:**
- LLM 메시지에 base64 문자열 포함 여부 확인
- 예상: "업로드된 제품 이미지: ..." 텍스트만 있고 base64 없음
- 도구 호출 파라미터에만 `product_image_png_b64` 존재

### 3. 광고 생성 테스트 (이미지 없음)

```python
# 테스트 시나리오
1. 이미지 업로드 없이 "사과 광고 만들어줘" 입력
2. 로그 확인:
   - "[디버그] 제품 이미지 없음"
   - "제품 이미지 없음 - 배경만 생성"
3. 서버가 background_prompt에 제품 설명 포함하여 생성
```

## 주의사항

1. **이미지 크기 제한**: Base64 인코딩으로 데이터 크기가 약 33% 증가하므로 대용량 이미지는 사전 리사이즈 권장
2. **세션 상태 관리**: 광고 생성 시작 후 이미지가 자동 제거되므로 재생성 시 재업로드 필요
3. **호환성**: 기존 `product_image_path`를 사용하는 코드는 더 이상 지원되지 않음
4. **토큰 최적화**: LLM 대화에는 이미지 정보만 텍스트로 전달하여 토큰 낭비 방지
5. **디버깅**: `_pending_product_image_b64`는 도구 호출 시에만 사용되며, conversation_history에는 포함되지 않음

## 토큰 절약 예시

| 시나리오 | 기존 방식 (가정) | 최적화 방식 | 절약 |
|---------|----------------|------------|------|
| 500KB 이미지 | ~20,000 토큰 | ~10 토큰 | **99.95%** |
| 1MB 이미지 | ~40,000 토큰 | ~10 토큰 | **99.98%** |
| 100KB 이미지 | ~4,000 토큰 | ~10 토큰 | **99.75%** |

*참고: Base64 인코딩된 이미지는 약 1.33배 크기 증가, 토큰 계산은 대략적인 추정값*

## 롤백 방법

변경 사항을 되돌리려면:

```bash
git checkout main -- src/nanoCocoa_mcpserver/handlers/generation.py
git checkout main -- src/nanoCocoa_mcpserver/schemas/mcp_tools.py
git checkout main -- src/ad_chat/ui/chat_ui.py
git checkout main -- src/mcpadapter/llm_adapter.py
```

## 참고 자료

- [이미지 처리 유틸리티](/home/spai0433/codeit-ai-3team-ad-content/src/nanoCocoa_mcpserver/utils/image_utils.py)
- [MCP 도구 스키마](/home/spai0433/codeit-ai-3team-ad-content/src/nanoCocoa_mcpserver/schemas/mcp_tools.py)
- [Streamlit 파일 업로더 문서](https://docs.streamlit.io/library/api-reference/widgets/st.file_uploader)
