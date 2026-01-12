# mcpadapter

nanoCocoa AI 광고 생성 시스템과 통합하기 위한 MCP 클라이언트 어댑터 라이브러리

## 설치

```bash
pip install mcpadapter
```

또는 소스에서 설치:

```bash
cd src/mcpadapter
pip install -e .
```

## 사용 방법

### 1. MCP 클라이언트로 직접 호출

```python
from mcpadapter import MCPClient

async with MCPClient("http://mcpserver:3000") as client:
    # 도구 호출
    result = await client.call_tool(
        "generate_ad_image",
        {
            "product_image_path": "/path/to/product.png",
            "background_prompt": "Luxury marble background",
            "text_content": "SALE 50%",
            "text_prompt": "Gold metallic 3D text"
        }
    )
    print(result)
```

### 2. LLM 어댑터로 자연어 처리

```python
from mcpadapter import LLMAdapter

async with LLMAdapter(
    openai_api_key="your-api-key",
    mcp_server_url="http://mcpserver:3000"
) as adapter:
    # 자연어로 요청
    response = await adapter.chat(
        "product.png 이미지로 여름 세일 광고를 만들어줘. "
        "배경은 햇살 가득한 해변으로, 텍스트는 금색 풍선 스타일로 해줘."
    )
    print(response)
```

## FastAPI 백엔드 통합 예제

```python
from fastapi import FastAPI
from mcpadapter import MCPClient

app = FastAPI()
mcp_client = MCPClient("http://mcpserver:3000")

@app.post("/generate-ad")
async def generate_ad(request: dict):
    result = await mcp_client.call_tool(
        "generate_ad_image",
        request
    )
    return {"result": result}

@app.on_event("startup")
async def startup():
    await mcp_client._ensure_client()

@app.on_event("shutdown")
async def shutdown():
    await mcp_client.close()
```

## 라이선스

MIT
