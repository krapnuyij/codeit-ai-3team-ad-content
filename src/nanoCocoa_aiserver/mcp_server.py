"""
mcp_server.py
MCP (Model Context Protocol) Server for nanoCocoa AI Ad Generator

This MCP server exposes the FastAPI endpoints as tools that LLMs can use.
It provides a standardized interface for AI assistants to generate ad images.
"""

import asyncio
import base64
import json
import logging
from typing import Any, Optional, Sequence
import httpx

from mcp.server import Server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)
import mcp.server.stdio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nanococoa-mcp-server")

# FastAPI server configuration
API_BASE_URL = "http://localhost:8000"
POLL_INTERVAL = 3  # seconds


class NanoCocoaMCPServer:
    """MCP Server for nanoCocoa AI Ad Generator"""

    def __init__(self, api_base_url: str = API_BASE_URL):
        self.api_base_url = api_base_url
        self.server = Server("nanococoa-ad-generator")
        self.client = httpx.AsyncClient(timeout=300.0)

        # Register handlers
        self.server.list_tools = self.list_tools
        self.server.call_tool = self.call_tool
        self.server.list_resources = self.list_resources
        self.server.read_resource = self.read_resource

    async def list_tools(self) -> list[Tool]:
        """List available tools"""
        return [
            Tool(
                name="health_check",
                description="""Check server health status and availability.

Returns:
- status: 'healthy' or 'busy'
- active_jobs: number of running jobs
- system_metrics: CPU/RAM/GPU usage

Use this before starting a new job to check if server is available.""",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="list_fonts",
                description="""Get list of available fonts for text generation.

Returns:
- fonts: array of font file paths (e.g., ["NanumGothic/NanumGothic.ttf"])

Use the font paths in the 'font_name' parameter when generating ads.""",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="generate_ad",
                description="""Start a new ad generation job.

This is the main tool for creating AI-generated advertising images. It combines product images with AI-generated backgrounds and 3D text effects.

Required Parameters:
- input_image: Product image as Base64 string
- bg_prompt: Background description in English (e.g., "luxury hotel lobby with warm lighting")

Optional Parameters:
- text_content: Text to display (leave empty for background-only generation)
- text_model_prompt: 3D text style description (e.g., "gold metallic text with shadow")
- font_name: Font file path from list_fonts
- composition_mode: "overlay", "blend", or "behind"
- text_position: "top", "center", "bottom", or "auto"
- start_step: 1 (full pipeline), 2 (text only), or 3 (composition only)

Returns:
- job_id: Use this to check status with check_job_status
- status: "started"

Note: This is non-blocking. Use check_job_status to poll for results.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "input_image": {
                            "type": "string",
                            "description": "Product image encoded as Base64 string",
                        },
                        "bg_prompt": {
                            "type": "string",
                            "description": "Background scene description in English",
                        },
                        "text_content": {
                            "type": "string",
                            "description": "Text to display in the ad (optional, leave empty for background-only)",
                        },
                        "text_model_prompt": {
                            "type": "string",
                            "description": "3D text style description (e.g., 'gold metallic text with shadow')",
                        },
                        "font_name": {
                            "type": "string",
                            "description": "Font file path from list_fonts (optional)",
                        },
                        "bg_negative_prompt": {
                            "type": "string",
                            "description": "Elements to exclude from background",
                        },
                        "negative_prompt": {
                            "type": "string",
                            "description": "Elements to exclude from text",
                        },
                        "composition_mode": {
                            "type": "string",
                            "enum": ["overlay", "blend", "behind"],
                            "description": "How to composite text with background",
                        },
                        "text_position": {
                            "type": "string",
                            "enum": ["top", "center", "bottom", "auto"],
                            "description": "Text placement position",
                        },
                        "strength": {
                            "type": "number",
                            "description": "Image transformation strength (0.0-1.0, default: 0.6)",
                        },
                        "guidance_scale": {
                            "type": "number",
                            "description": "Prompt adherence strength (1.0-20.0, default: 3.5)",
                        },
                        "composition_strength": {
                            "type": "number",
                            "description": "Composition transformation strength (0.0-1.0, default: 0.4)",
                        },
                        "seed": {
                            "type": "integer",
                            "description": "Random seed for reproducibility (optional)",
                        },
                        "start_step": {
                            "type": "integer",
                            "enum": [1, 2, 3],
                            "description": "Starting step: 1=full pipeline, 2=text only (needs step1_image), 3=composition only (needs step1_image and step2_image)",
                        },
                        "step1_image": {
                            "type": "string",
                            "description": "Previous background result (Base64) for start_step >= 2",
                        },
                        "step2_image": {
                            "type": "string",
                            "description": "Previous text result (Base64) for start_step == 3",
                        },
                    },
                    "required": ["input_image", "bg_prompt"],
                },
            ),
            Tool(
                name="check_job_status",
                description="""Check the status and results of a generation job.

Parameters:
- job_id: The job ID returned by generate_ad

Returns:
- status: "pending", "running", "completed", "failed", or "stopped"
- progress_percent: 0-100
- current_step: Current pipeline step
- message: Status message
- step1_result: Background image (Base64) when available
- step2_result: Text image (Base64) when available
- final_result: Final composite image (Base64) when completed
- system_metrics: Real-time CPU/GPU metrics

Poll this endpoint every 3-5 seconds until status is 'completed' or 'failed'.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "job_id": {
                            "type": "string",
                            "description": "Job ID from generate_ad",
                        }
                    },
                    "required": ["job_id"],
                },
            ),
            Tool(
                name="stop_job",
                description="""Stop a running generation job.

Parameters:
- job_id: The job ID to stop

Returns:
- job_id: The stopped job ID
- status: "stopped"

Use this to cancel a job that's taking too long or was started with wrong parameters.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "job_id": {"type": "string", "description": "Job ID to stop"}
                    },
                    "required": ["job_id"],
                },
            ),
            Tool(
                name="list_jobs",
                description="""Get list of all jobs on the server.

Returns:
- total_jobs: Total number of jobs
- active_jobs: Number of running/pending jobs
- completed_jobs: Number of completed jobs
- failed_jobs: Number of failed jobs
- jobs: Array of job information

Use this to see all jobs and their current states.""",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="delete_job",
                description="""Delete a completed or failed job from server memory.

Parameters:
- job_id: The job ID to delete

Returns:
- job_id: Deleted job ID
- status: "deleted"

Note: Cannot delete running jobs. Stop them first with stop_job.
Use this to clean up completed jobs and free server memory.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "job_id": {"type": "string", "description": "Job ID to delete"}
                    },
                    "required": ["job_id"],
                },
            ),
            Tool(
                name="generate_and_wait",
                description="""Start ad generation and wait for completion (blocking).

This is a convenience tool that combines generate_ad + polling check_job_status until completion.

Parameters: Same as generate_ad
- input_image: Product image (Base64)
- bg_prompt: Background description
- text_content: Ad text (optional)
- ... (all other generate_ad parameters)

Returns:
- final_result: Base64 encoded final image (when successful)
- step1_result: Background image (Base64)
- step2_result: Text image (Base64)
- status: Final status
- All job status information

This tool will automatically poll the server and return when the job is complete or failed.
Estimated time: 80-120 seconds for full pipeline.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "input_image": {
                            "type": "string",
                            "description": "Product image encoded as Base64 string",
                        },
                        "bg_prompt": {
                            "type": "string",
                            "description": "Background scene description in English",
                        },
                        "text_content": {
                            "type": "string",
                            "description": "Text to display in the ad (optional)",
                        },
                        "text_model_prompt": {
                            "type": "string",
                            "description": "3D text style description",
                        },
                        "font_name": {
                            "type": "string",
                            "description": "Font file path from list_fonts",
                        },
                        "bg_negative_prompt": {"type": "string"},
                        "negative_prompt": {"type": "string"},
                        "composition_mode": {
                            "type": "string",
                            "enum": ["overlay", "blend", "behind"],
                        },
                        "text_position": {
                            "type": "string",
                            "enum": ["top", "center", "bottom", "auto"],
                        },
                        "strength": {"type": "number"},
                        "guidance_scale": {"type": "number"},
                        "composition_strength": {"type": "number"},
                        "seed": {"type": "integer"},
                        "start_step": {"type": "integer", "enum": [1, 2, 3]},
                        "step1_image": {"type": "string"},
                        "step2_image": {"type": "string"},
                    },
                    "required": ["input_image", "bg_prompt"],
                },
            ),
        ]

    async def call_tool(
        self, name: str, arguments: dict
    ) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        """Execute a tool"""
        try:
            if name == "health_check":
                return await self._health_check()
            elif name == "list_fonts":
                return await self._list_fonts()
            elif name == "generate_ad":
                return await self._generate_ad(arguments)
            elif name == "check_job_status":
                return await self._check_job_status(arguments)
            elif name == "stop_job":
                return await self._stop_job(arguments)
            elif name == "list_jobs":
                return await self._list_jobs()
            elif name == "delete_job":
                return await self._delete_job(arguments)
            elif name == "generate_and_wait":
                return await self._generate_and_wait(arguments)
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]
        except Exception as e:
            logger.error(f"Error executing tool {name}: {e}", exc_info=True)
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    async def list_resources(self) -> list[Resource]:
        """List available resources"""
        return [
            Resource(
                uri="nanococoa://help/guide",
                name="API Usage Guide",
                mimeType="application/json",
                description="Complete API usage guide with workflows and examples",
            ),
            Resource(
                uri="nanococoa://help/parameters",
                name="Parameter Reference",
                mimeType="application/json",
                description="Detailed parameter reference for all API endpoints",
            ),
            Resource(
                uri="nanococoa://help/examples",
                name="Usage Examples",
                mimeType="application/json",
                description="Real-world usage examples with code snippets",
            ),
        ]

    async def read_resource(self, uri: str) -> str:
        """Read a resource"""
        try:
            if uri == "nanococoa://help/guide":
                response = await self.client.get(f"{self.api_base_url}/help")
                response.raise_for_status()
                return json.dumps(response.json(), indent=2)
            elif uri == "nanococoa://help/parameters":
                response = await self.client.get(f"{self.api_base_url}/help/parameters")
                response.raise_for_status()
                return json.dumps(response.json(), indent=2)
            elif uri == "nanococoa://help/examples":
                response = await self.client.get(f"{self.api_base_url}/help/examples")
                response.raise_for_status()
                return json.dumps(response.json(), indent=2)
            else:
                raise ValueError(f"Unknown resource: {uri}")
        except Exception as e:
            logger.error(f"Error reading resource {uri}: {e}")
            return f"Error reading resource: {str(e)}"

    async def _health_check(self) -> Sequence[TextContent]:
        """Health check implementation"""
        response = await self.client.get(f"{self.api_base_url}/health")
        response.raise_for_status()
        data = response.json()

        return [TextContent(type="text", text=json.dumps(data, indent=2))]

    async def _list_fonts(self) -> Sequence[TextContent]:
        """List fonts implementation"""
        response = await self.client.get(f"{self.api_base_url}/fonts")
        response.raise_for_status()
        data = response.json()

        return [TextContent(type="text", text=json.dumps(data, indent=2))]

    async def _generate_ad(self, arguments: dict) -> Sequence[TextContent]:
        """Generate ad implementation"""
        response = await self.client.post(
            f"{self.api_base_url}/generate", json=arguments
        )

        if response.status_code == 503:
            retry_after = response.headers.get("Retry-After", "unknown")
            data = response.json()
            return [
                TextContent(
                    type="text",
                    text=f"Server is busy. {data.get('message', '')} Retry after {retry_after} seconds.\n\n"
                    + json.dumps(data, indent=2),
                )
            ]

        response.raise_for_status()
        data = response.json()

        return [
            TextContent(
                type="text",
                text=f"Job started successfully!\n\nJob ID: {data['job_id']}\n\n"
                + "Use 'check_job_status' tool with this job_id to monitor progress.\n\n"
                + json.dumps(data, indent=2),
            )
        ]

    async def _check_job_status(
        self, arguments: dict
    ) -> Sequence[TextContent | ImageContent]:
        """Check job status implementation"""
        job_id = arguments["job_id"]
        response = await self.client.get(f"{self.api_base_url}/status/{job_id}")
        response.raise_for_status()
        data = response.json()

        results = []

        # Status information
        status_text = (
            f"Job Status Report\n"
            f"================\n\n"
            f"Job ID: {data['job_id']}\n"
            f"Status: {data['status']}\n"
            f"Progress: {data['progress_percent']}%\n"
            f"Current Step: {data['current_step']}\n"
            f"Message: {data['message']}\n"
            f"Elapsed Time: {data['elapsed_sec']}s\n"
        )

        if data.get("eta_seconds") is not None:
            status_text += f"Estimated Remaining: {data['eta_seconds']}s\n"

        status_text += f"\nFull Response:\n{json.dumps(data, indent=2)}"

        results.append(TextContent(type="text", text=status_text))

        # Include images if available
        # Note: MCP ImageContent expects data URLs or we can embed as base64
        if data.get("final_result"):
            results.append(
                TextContent(
                    type="text",
                    text=f"\n\nFinal result available! (Base64 length: {len(data['final_result'])} chars)",
                )
            )

        return results

    async def _stop_job(self, arguments: dict) -> Sequence[TextContent]:
        """Stop job implementation"""
        job_id = arguments["job_id"]
        response = await self.client.post(f"{self.api_base_url}/stop/{job_id}")
        response.raise_for_status()
        data = response.json()

        return [
            TextContent(
                type="text",
                text=f"Job stopped successfully.\n\n{json.dumps(data, indent=2)}",
            )
        ]

    async def _list_jobs(self) -> Sequence[TextContent]:
        """List jobs implementation"""
        response = await self.client.get(f"{self.api_base_url}/jobs")
        response.raise_for_status()
        data = response.json()

        summary = (
            f"Jobs Summary\n"
            f"============\n\n"
            f"Total Jobs: {data['total_jobs']}\n"
            f"Active Jobs: {data['active_jobs']}\n"
            f"Completed Jobs: {data['completed_jobs']}\n"
            f"Failed Jobs: {data['failed_jobs']}\n\n"
            f"Full Response:\n{json.dumps(data, indent=2)}"
        )

        return [TextContent(type="text", text=summary)]

    async def _delete_job(self, arguments: dict) -> Sequence[TextContent]:
        """Delete job implementation"""
        job_id = arguments["job_id"]
        response = await self.client.delete(f"{self.api_base_url}/jobs/{job_id}")
        response.raise_for_status()
        data = response.json()

        return [
            TextContent(
                type="text",
                text=f"Job deleted successfully.\n\n{json.dumps(data, indent=2)}",
            )
        ]

    async def _generate_and_wait(self, arguments: dict) -> Sequence[TextContent]:
        """Generate and wait for completion implementation"""
        # Start generation
        response = await self.client.post(
            f"{self.api_base_url}/generate", json=arguments
        )

        if response.status_code == 503:
            retry_after = response.headers.get("Retry-After", "unknown")
            data = response.json()
            return [
                TextContent(
                    type="text",
                    text=f"Server is busy. {data.get('message', '')} Retry after {retry_after} seconds.",
                )
            ]

        response.raise_for_status()
        job_data = response.json()
        job_id = job_data["job_id"]

        logger.info(f"Job started: {job_id}. Waiting for completion...")

        # Poll until completion
        while True:
            await asyncio.sleep(POLL_INTERVAL)

            status_response = await self.client.get(
                f"{self.api_base_url}/status/{job_id}"
            )
            status_response.raise_for_status()
            status_data = status_response.json()

            status = status_data["status"]
            progress = status_data["progress_percent"]
            message = status_data["message"]

            logger.info(f"Job {job_id}: {status} - {progress}% - {message}")

            if status in ("completed", "failed", "stopped"):
                break

        # Return final result
        if status == "completed":
            result_text = (
                f"Generation Completed Successfully!\n\n"
                f"Job ID: {job_id}\n"
                f"Progress: {progress}%\n"
                f"Message: {message}\n\n"
            )

            if status_data.get("final_result"):
                result_text += f"Final Result: Available (Base64 length: {len(status_data['final_result'])} chars)\n"
            if status_data.get("step1_result"):
                result_text += f"Step 1 Result: Available (Base64 length: {len(status_data['step1_result'])} chars)\n"
            if status_data.get("step2_result"):
                result_text += f"Step 2 Result: Available (Base64 length: {len(status_data['step2_result'])} chars)\n"

            result_text += f"\n\nFull Response:\n{json.dumps(status_data, indent=2)}"

            return [TextContent(type="text", text=result_text)]
        else:
            return [
                TextContent(
                    type="text",
                    text=f"Job {status}: {message}\n\n{json.dumps(status_data, indent=2)}",
                )
            ]

    async def run(self):
        """Run the MCP server"""
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream, write_stream, self.server.create_initialization_options()
            )


async def main():
    """Main entry point"""
    server = NanoCocoaMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
