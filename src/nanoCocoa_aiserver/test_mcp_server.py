"""
test_mcp_server.py
Test script for the nanoCocoa MCP Server

This script tests the MCP server functionality by simulating tool calls.
"""

import asyncio
import json
import base64
from pathlib import Path

# Import the MCP server
from mcp_server import NanoCocoaMCPServer


async def test_health_check(server: NanoCocoaMCPServer):
    """Test health check tool"""
    print("\n" + "=" * 60)
    print("Testing: health_check")
    print("=" * 60)

    result = await server.call_tool("health_check", {})
    for item in result:
        print(item.text)


async def test_list_fonts(server: NanoCocoaMCPServer):
    """Test list fonts tool"""
    print("\n" + "=" * 60)
    print("Testing: list_fonts")
    print("=" * 60)

    result = await server.call_tool("list_fonts", {})
    for item in result:
        print(item.text)


async def test_list_jobs(server: NanoCocoaMCPServer):
    """Test list jobs tool"""
    print("\n" + "=" * 60)
    print("Testing: list_jobs")
    print("=" * 60)

    result = await server.call_tool("list_jobs", {})
    for item in result:
        print(item.text)


async def test_generate_ad(server: NanoCocoaMCPServer):
    """Test generate ad tool"""
    print("\n" + "=" * 60)
    print("Testing: generate_ad (test mode)")
    print("=" * 60)

    # Create a simple test image (1x1 pixel PNG)
    test_image_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

    arguments = {
        "input_image": test_image_b64,
        "bg_prompt": "modern office with natural lighting",
        "text_content": "Test Ad",
        "text_model_prompt": "simple text",
        "test_mode": True,  # Use test mode to avoid GPU requirement
    }

    result = await server.call_tool("generate_ad", arguments)
    for item in result:
        print(item.text)

    # Extract job_id from response
    response_text = result[0].text
    if "Job ID:" in response_text:
        lines = response_text.split("\n")
        for line in lines:
            if line.startswith("Job ID:"):
                job_id = line.split("Job ID:")[1].strip()
                return job_id

    return None


async def test_check_job_status(server: NanoCocoaMCPServer, job_id: str):
    """Test check job status tool"""
    print("\n" + "=" * 60)
    print(f"Testing: check_job_status (job_id: {job_id})")
    print("=" * 60)

    result = await server.call_tool("check_job_status", {"job_id": job_id})
    for item in result:
        print(item.text)

    return result


async def test_list_tools(server: NanoCocoaMCPServer):
    """Test list tools"""
    print("\n" + "=" * 60)
    print("Testing: list_tools")
    print("=" * 60)

    tools = await server.list_tools()
    print(f"Available tools: {len(tools)}\n")

    for tool in tools:
        print(f"Tool: {tool.name}")
        print(f"Description: {tool.description[:100]}...")
        print(f"Required params: {tool.inputSchema.get('required', [])}")
        print("-" * 60)


async def test_list_resources(server: NanoCocoaMCPServer):
    """Test list resources"""
    print("\n" + "=" * 60)
    print("Testing: list_resources")
    print("=" * 60)

    resources = await server.list_resources()
    print(f"Available resources: {len(resources)}\n")

    for resource in resources:
        print(f"Resource: {resource.name}")
        print(f"URI: {resource.uri}")
        print(f"Description: {resource.description}")
        print("-" * 60)


async def test_read_resource(server: NanoCocoaMCPServer, uri: str):
    """Test read resource"""
    print("\n" + "=" * 60)
    print(f"Testing: read_resource ({uri})")
    print("=" * 60)

    content = await server.read_resource(uri)
    # Print first 500 chars
    print(content[:500] + "..." if len(content) > 500 else content)


async def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("nanoCocoa MCP Server - Test Suite")
    print("=" * 60)
    print("\nMake sure the FastAPI server is running at http://localhost:8000")
    print("Press Ctrl+C to cancel, or Enter to continue...")

    try:
        input()
    except KeyboardInterrupt:
        print("\nTest cancelled.")
        return

    # Initialize server
    server = NanoCocoaMCPServer(api_base_url="http://localhost:8000")

    try:
        # Test 1: List tools
        await test_list_tools(server)

        # Test 2: List resources
        await test_list_resources(server)

        # Test 3: Read a resource
        await test_read_resource(server, "nanococoa://help/guide")

        # Test 4: Health check
        await test_health_check(server)

        # Test 5: List fonts
        await test_list_fonts(server)

        # Test 6: List jobs
        await test_list_jobs(server)

        # Test 7: Generate ad (in test mode)
        print("\n" + "=" * 60)
        print("OPTIONAL: Test ad generation")
        print("=" * 60)
        print("This will start a job on the server.")
        print("Skip this test if you don't want to start a job. (y/N):")

        try:
            response = input().strip().lower()
            if response == "y":
                job_id = await test_generate_ad(server)

                if job_id:
                    # Wait a bit
                    print("\nWaiting 3 seconds before checking status...")
                    await asyncio.sleep(3)

                    # Test 8: Check job status
                    await test_check_job_status(server, job_id)

                    print("\nYou can continue monitoring with:")
                    print(f"  GET http://localhost:8000/status/{job_id}")
        except KeyboardInterrupt:
            print("\nSkipped ad generation test.")

        print("\n" + "=" * 60)
        print("All tests completed!")
        print("=" * 60)

    except Exception as e:
        print(f"\nError during testing: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # Close HTTP client
        await server.client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
