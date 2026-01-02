# nanoCocoa AI Ad Generator - MCP Server

This is an MCP (Model Context Protocol) server that provides AI-powered advertising image generation capabilities to LLM applications like Claude Desktop.

## Features

The MCP server exposes the following tools:

### 1. **health_check**
Check server availability and system metrics before starting jobs.

### 2. **list_fonts**
Get available fonts for text generation.

### 3. **generate_ad**
Start a new ad generation job (non-blocking).
- Combines product images with AI-generated backgrounds
- Adds 3D text effects
- Returns job_id for status tracking

### 4. **check_job_status**
Monitor job progress and retrieve results.
- Real-time progress updates
- Step-by-step status
- Base64 encoded image results

### 5. **stop_job**
Cancel a running job.

### 6. **list_jobs**
View all jobs and their statuses.

### 7. **delete_job**
Remove completed jobs from memory.

### 8. **generate_and_wait** (Convenience Tool)
Start generation and automatically wait for completion (blocking).
- Combines generate_ad + polling
- Returns final results when ready
- Estimated time: 80-120 seconds

### Resources

The server also provides documentation resources:
- `nanococoa://help/guide` - Complete API usage guide
- `nanococoa://help/parameters` - Parameter reference
- `nanococoa://help/examples` - Code examples

## Installation

### Prerequisites

1. **FastAPI Server**: The MCP server connects to the FastAPI backend
2. **Python 3.8+**
3. **MCP SDK**: Install the Model Context Protocol SDK

```bash
pip install mcp httpx
```

### Setup

1. Make sure the FastAPI server is running:
```bash
cd src/nanoCocoa_aiserver
python main.py
```

2. The FastAPI server should be available at `http://localhost:8000`

## Usage

### Option 1: Automatic Setup (Recommended)

Use the setup script to automatically configure Claude Desktop:

```bash
cd src/nanoCocoa_aiserver
python setup_mcp.py --install
```

The script will:
- Locate your Claude Desktop configuration file
- Add the MCP server configuration
- Use the correct absolute path automatically

To uninstall:
```bash
python setup_mcp.py --uninstall
```

To view current configuration:
```bash
python setup_mcp.py --show
```

To test the MCP server:
```bash
python setup_mcp.py --test
```

### Option 2: Manual Setup

If you prefer manual setup, the MCP configuration is stored in:
- **Project Config**: `.mcp/config.json` (in this directory)
- **Claude Desktop Config**: Platform-specific location

1. Find your Claude Desktop config:
   - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Linux**: `~/.config/Claude/claude_desktop_config.json`

2. Copy the server configuration from `.mcp/config.json` to your Claude config

3. Update the `args` path to the absolute path of `mcp_server.py` on your system

### Option 2: Direct Execution (Testing)

Run the MCP server directly for testing:

```bash
cd src/nanoCocoa_aiserver
python mcp_server.py
```

The server will start and communicate via stdio.

## Example Workflows

### Basic Ad Generation

```
User: Generate an ad for a coffee product with a cozy cafe background and "Fresh Brew" text

LLM will:
1. Use health_check to verify server availability
2. Use list_fonts to get available fonts
3. Use generate_and_wait with:
   - input_image: <base64 coffee product>
   - bg_prompt: "cozy modern cafe interior with warm lighting and wooden tables"
   - text_content: "Fresh Brew"
   - text_model_prompt: "dark brown 3D text with coffee texture"
4. Return the final image when complete
```

### Iterative Refinement

```
User: Change the text style to gold metallic

LLM will:
1. Use the previous step1_result (background)
2. Use generate_ad with:
   - start_step: 2 (text only)
   - step1_image: <previous background>
   - text_content: "Fresh Brew"
   - text_model_prompt: "gold metallic text with glossy surface"
3. Monitor with check_job_status
```

## API Endpoints Mapping

| MCP Tool | REST Endpoint | Description |
|----------|---------------|-------------|
| health_check | GET /health | Server status |
| list_fonts | GET /fonts | Available fonts |
| generate_ad | POST /generate | Start job |
| check_job_status | GET /status/{job_id} | Job status |
| stop_job | POST /stop/{job_id} | Cancel job |
| list_jobs | GET /jobs | All jobs |
| delete_job | DELETE /jobs/{job_id} | Remove job |

## Best Practices for LLMs

1. **Always check health first**: Use `health_check` before starting jobs
2. **Use generate_and_wait for simplicity**: Automatically handles polling
3. **Provide descriptive prompts**: Better prompts = better results
   - Background: "luxury hotel lobby with marble floor and warm lighting"
   - Text: "gold metallic 3D text with shadow and reflection"
4. **Handle busy responses**: Server processes one job at a time
5. **Clean up completed jobs**: Use `delete_job` after retrieving results
6. **Reuse intermediate results**: Save step1_result and step2_result for iterations

## Troubleshooting

### MCP Server Not Connecting
- Ensure FastAPI server is running at `http://localhost:8000`
- Check the API_BASE_URL in configuration
- Verify network connectivity

### Jobs Taking Too Long
- Normal generation time: 80-120 seconds
- Use `check_job_status` to monitor progress
- Check GPU availability with `health_check`

### Server Always Busy
- Server processes one job at a time (single job policy)
- Use `list_jobs` to see active jobs
- Use `stop_job` to cancel if needed

## Architecture

```
┌─────────────────┐
│   LLM Client    │
│ (Claude, etc.)  │
└────────┬────────┘
         │ MCP Protocol
         │ (stdio)
┌────────▼────────┐
│   MCP Server    │
│  mcp_server.py  │
└────────┬────────┘
         │ HTTP REST
         │
┌────────▼────────┐
│  FastAPI Server │
│    main.py      │
└────────┬────────┘
         │
┌────────▼────────┐
│   AI Models     │
│  (GPU Workers)  │
└─────────────────┘
```

## License

Part of the nanoCocoa AI Ad Generator project.

## Support

For issues or questions:
- Check FastAPI server logs
- Review MCP server logs
- Ensure GPU is available for generation
