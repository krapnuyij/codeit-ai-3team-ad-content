# nanoCocoa AI Ad Generator - Complete Setup Guide

This guide will help you set up both the REST API server and the MCP server for AI-powered ad generation.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
4. [Running the FastAPI Server](#running-the-fastapi-server)
5. [Setting up the MCP Server](#setting-up-the-mcp-server)
6. [Testing](#testing)
7. [Integration with LLM Clients](#integration-with-llm-clients)
8. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

```
┌──────────────────┐
│   LLM Client     │  (Claude Desktop, etc.)
│  (User Interface)│
└────────┬─────────┘
         │
         │ MCP Protocol (stdio)
         │
┌────────▼─────────┐
│   MCP Server     │  mcp_server.py
│   (Tool Bridge)  │  - Exposes tools to LLM
└────────┬─────────┘  - Manages requests/responses
         │
         │ HTTP REST API
         │
┌────────▼─────────┐
│  FastAPI Server  │  main.py
│   (API Layer)    │  - Handles HTTP requests
└────────┬─────────┘  - Job management
         │            - Progress tracking
         │
┌────────▼─────────┐
│  Core Engine     │  core/
│  (AI Pipeline)   │  - AI model orchestration
└────────┬─────────┘  - Image processing
         │            - Multi-step pipeline
         │
┌────────▼─────────┐
│   AI Models      │  models/
│   (GPU Workers)  │  - BiRefNet (segmentation)
└──────────────────┘  - FLUX (image generation)
                      - SDXL ControlNet (text)
```

---

## Prerequisites

### Hardware Requirements

- **GPU**: Nvidia GPU with at least 12GB VRAM (L4 or better recommended)
- **RAM**: 16GB+ system RAM
- **Storage**: 20GB+ free space for models

### Software Requirements

- **Python**: 3.8 or higher
- **CUDA**: Compatible with your GPU
- **Operating System**: Windows, Linux, or macOS

---

## Installation

### Step 1: Clone/Navigate to Project

```bash
cd d:/project/codeit-ai-3team-ad-content/src/nanoCocoa_aiserver
```

### Step 2: Install FastAPI Server Dependencies

```bash
# Install main dependencies (if requirements.txt exists)
pip install fastapi uvicorn torch torchvision diffusers transformers accelerate

# Install additional dependencies
pip install pillow numpy opencv-python pynvml psutil
```

### Step 3: Install MCP Server Dependencies

```bash
pip install -r requirements_mcp.txt
```

This installs:
- `mcp` - Model Context Protocol SDK
- `httpx` - HTTP client for API calls

### Step 4: Download AI Models

The first run will automatically download required models:
- BiRefNet (background removal)
- FLUX.1-dev (image generation)
- SDXL + ControlNet (3D text generation)

This will take **10-20 minutes** and require **15-20GB** of storage.

---

## Running the FastAPI Server

### Start the Server

```bash
# Development mode (with auto-reload)
python main.py

# Production mode
uvicorn api.app:app --host 0.0.0.0 --port 8000
```

### Verify Server is Running

Open browser and navigate to:
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

You should see:
```json
{
  "status": "healthy",
  "server_time": 1234567890.123,
  "total_jobs": 0,
  "active_jobs": 0,
  "system_metrics": { ... }
}
```

### Available REST Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Server status & metrics |
| `/fonts` | GET | List available fonts |
| `/generate` | POST | Start ad generation |
| `/status/{job_id}` | GET | Check job status |
| `/stop/{job_id}` | POST | Stop running job |
| `/jobs` | GET | List all jobs |
| `/jobs/{job_id}` | DELETE | Delete job |
| `/help` | GET | API usage guide |
| `/help/parameters` | GET | Parameter reference |
| `/help/examples` | GET | Usage examples |

---

## Setting up the MCP Server

### Option A: Automatic Setup (Recommended)

Use the included setup script for automatic configuration:

```bash
cd src/nanoCocoa_aiserver
python setup_mcp.py --install
```

**What it does:**
- Automatically finds Claude Desktop config file
- Adds MCP server configuration with correct paths
- No manual editing required

**Other commands:**
```bash
python setup_mcp.py --uninstall   # Remove MCP server
python setup_mcp.py --show        # View current config
python setup_mcp.py --test        # Test MCP server
```

**Restart Claude Desktop** after installation.

### Option B: Manual Setup

If you prefer manual setup or the script doesn't work:

1. **Locate Claude Desktop Config**
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Linux: `~/.config/Claude/claude_desktop_config.json`

2. **Copy configuration from `.mcp/config.json`**
   - The project includes a pre-configured MCP config file
   - Update the `args` path to your absolute path

3. **Restart Claude Desktop**

### Option C: Direct Execution (Testing)

```bash
cd src/nanoCocoa_aiserver
python mcp_server.py
```

The server will communicate via stdio. You can pipe commands or use MCP client tools.

---

## Testing

### Test 1: FastAPI Server

```bash
# Test health endpoint
curl http://localhost:8000/health

# Test fonts endpoint
curl http://localhost:8000/fonts

# Test help endpoint
curl http://localhost:8000/help
```

### Test 2: MCP Server

**Option 1: Use setup script (Recommended)**

```bash
cd src/nanoCocoa_aiserver
python setup_mcp.py --test
```

This will:
- Check dependencies (mcp, httpx)
- Verify MCP server file exists
- Test FastAPI server connection
- Run MCP interface dummy tests

**Option 2: Run tests directly**

```bash
# Dummy tests (no MCP server required)
cd tests
pytest mcp/test_mcp_dummy.py -v

# Manual interactive test
cd src/nanoCocoa_aiserver
python test_mcp_server.py
```

Tests include:
- ✓ List tools
- ✓ List resources
- ✓ Read resources
- ✓ All tool interfaces (health_check, list_fonts, generate_ad, etc.)
- ✓ Workflow simulations

### Test 3: End-to-End with Claude Desktop

1. Make sure FastAPI server is running
2. Open Claude Desktop
3. Type: "List available fonts from nanoCocoa"
4. Claude should use the `list_fonts` tool and return results

---

## Integration with LLM Clients

### Claude Desktop

Once configured, Claude can use these tools:

**Example Conversation:**

```
User: Create an ad for my coffee product with a cozy cafe background

Claude: I'll help you create an advertising image. First, I need the product image.
Can you provide the coffee product image?

User: [Uploads image]

Claude: [Uses generate_and_wait tool]
Creating your ad with:
- Background: cozy modern cafe interior
- Text: "Fresh Brew"
- Style: warm brown 3D text

[After 90 seconds]
Your ad is ready! [Shows result]
```

### API Client (Python)

```python
import requests
import base64
import time

# Read image
with open("product.png", "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode()

# Start generation
response = requests.post("http://localhost:8000/generate", json={
    "input_image": img_b64,
    "bg_prompt": "luxury hotel lobby with warm lighting",
    "text_content": "Grand Opening",
    "text_model_prompt": "gold metallic 3D text"
})

job_id = response.json()["job_id"]

# Poll for results
while True:
    status = requests.get(f"http://localhost:8000/status/{job_id}").json()

    if status["status"] == "completed":
        # Save result
        with open("result.png", "wb") as f:
            f.write(base64.b64decode(status["final_result"]))
        break

    print(f"Progress: {status['progress_percent']}%")
    time.sleep(3)
```

---

## Troubleshooting

### Issue 1: FastAPI Server Won't Start

**Symptoms**: Port already in use, import errors

**Solutions**:
```bash
# Check if port 8000 is in use
netstat -ano | findstr :8000  # Windows
lsof -i :8000                 # Linux/macOS

# Kill the process or use different port
uvicorn api.app:app --port 8001
```

### Issue 2: MCP Server Not Connecting

**Symptoms**: Claude Desktop doesn't see tools

**Solutions**:
1. Verify FastAPI server is running at `http://localhost:8000`
2. Check absolute path in `claude_desktop_config.json`
3. Check Claude Desktop logs:
   - Windows: `%APPDATA%\Claude\logs`
   - macOS: `~/Library/Logs/Claude`
4. Restart Claude Desktop

### Issue 3: GPU Out of Memory

**Symptoms**: CUDA out of memory errors

**Solutions**:
1. Close other GPU applications
2. Reduce image resolution in requests
3. Wait for current job to finish (single job policy)
4. Check GPU memory: `nvidia-smi`

### Issue 4: Jobs Taking Too Long

**Symptoms**: Jobs exceed estimated time

**Solutions**:
1. Check GPU utilization: `nvidia-smi`
2. Verify GPU is being used (not CPU fallback)
3. Check system load with `/health` endpoint
4. Reduce quality parameters (fewer steps, lower strength)

### Issue 5: Import Errors

**Symptoms**: Module not found errors

**Solutions**:
```bash
# Reinstall dependencies
pip install --upgrade -r requirements_mcp.txt

# Verify MCP installation
python -c "import mcp; print(mcp.__version__)"

# Verify httpx installation
python -c "import httpx; print(httpx.__version__)"
```

---

## Configuration

### Environment Variables

Create `.env` file (optional):

```bash
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_BASE_URL=http://localhost:8000

# Model Configuration
DEVICE=cuda
ENABLE_DEV_DASHBOARD=true

# Logging
LOG_LEVEL=INFO
```

### Model Paths

Models are cached in:
- Windows: `C:\Users\<user>\.cache\huggingface`
- Linux/macOS: `~/.cache/huggingface`

To use custom model path:
```bash
export HF_HOME=/path/to/models
```

---

## Performance Tuning

### Estimated Times (Nvidia L4)

- **Step 1** (Background): ~80 seconds
- **Step 2** (Text): ~35 seconds
- **Step 3** (Composition): ~5 seconds
- **Total**: ~120 seconds

### Optimization Tips

1. **Reuse Results**: Save `step1_result` and `step2_result` for iterations
2. **Adjust Steps**: Use `start_step` to skip completed stages
3. **Reduce Quality**: Lower `composition_steps` (default 28 → 20)
4. **Batch Processing**: Generate background once, multiple texts

---

## Next Steps

1. **FastAPI server running**: http://localhost:8000
2. **MCP server configured**: In Claude Desktop config
3. **Test completed**: All tools working
4. 🚀 **Start creating ads**: Use Claude or direct API

## Additional Resources

- **API Documentation**: http://localhost:8000/docs
- **Usage Guide**: http://localhost:8000/help
- **Parameter Reference**: http://localhost:8000/help/parameters
- **Examples**: http://localhost:8000/help/examples
- **MCP Guide**: [README_MCP.md](README_MCP.md)

---

## Support

For issues or questions:
- Check server logs for errors
- Review `/health` endpoint for system status
- Test with `test_mcp_server.py`
- Verify GPU availability with `nvidia-smi`

**Contact**: c0z0c.dev@gmail.com
