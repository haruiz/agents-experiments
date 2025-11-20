import asyncio
import uvicorn
import argparse
from typing import Dict, List, Any
from fastmcp import FastMCP, Context
from fastmcp.server.http import create_streamable_http_app
import logging
from rich.logging import RichHandler

# Configure logging to use Rich for pretty, colorful output
logging.basicConfig(
    level="INFO",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)
logger = logging.getLogger(__name__)


# Create MCP server instance
mcp = FastMCP(
    name="file_upload_server",
    instructions="Provide tools for simulating file uploads with progress updates."
)

@mcp.tool(
    description="A long-running task that simulates work and reports progress in real-time.",
    name="long_running_task",
)
async def long_running_task(
    name: str = "Task",
    steps: int = 10,
    context: Context = None,
) -> Dict[str, Any]:
    """
    A long-running task that simulates work and reports progress in real-time.

    This tool demonstrates how to use the `context` object to stream updates
    (progress, info, debug messages) back to the client during execution.

    Args:
        name: The name of the task to be displayed in progress messages.
        steps: The total number of steps to simulate.
        context: Injected by the FastMCP server to communicate with the client.
    """
    # The 'context' object is injected by the server and allows for streaming
    # responses. We check for its existence to allow the tool to be called
    # directly in tests or other contexts without a server.
    if context:
        await context.info(f"🚀 Initializing '{name}' with {steps} steps...")

    results = []

    for i in range(steps):
        # Simulate work
        await asyncio.sleep(0.5)

        # Create a result for this step
        step_result = f"Processed item {i + 1} for '{name}'"
        results.append(step_result)

        # Report progress back to the client via the context
        if context:
            await context.report_progress(
                progress=i + 1,
                total=steps,
                message=f"Working on item {i + 1}...",
            )
            # Debug messages are also streamed and can be useful for detailed logs
            await context.debug(f"✅ {step_result}")

    if context:
        await context.info(f"🎉 '{name}' completed successfully!")

    return {
        "task_name": name,
        "steps_completed": steps,
        "results": results,
        "status": "completed",
    }

@mcp.tool(
    name="file_upload_simulation",
    description="Simulates file upload with progress updates."
)
async def file_upload_simulation(
        file_count: int = 5,
        context: Context = None
) -> Dict[str, Any]:
    """
    Simulates file upload with progress updates.

    Args:
        file_count: Number of files to upload
    """
    if context:
        await context.info(f"📤 Starting upload of {file_count} files...")

    uploaded_files = []

    for i in range(file_count):
        file_name = f"file_{i + 1}.dat"

        if context:
            await context.info(f"Uploading {file_name}...")

        # Simulate upload by chunks
        chunks = 10
        for chunk in range(chunks):
            await asyncio.sleep(0.2)  # Simulate upload time

            if context:
                await context.report_progress(
                    progress=(i * chunks) + chunk + 1,
                    total=file_count * chunks,
                    message=f"Uploading {file_name} - chunk {chunk + 1}/{chunks}"
                )

        uploaded_files.append({
            "name": file_name,
            "size": f"{(i + 1) * 1024} KB",
            "status": "uploaded"
        })

        if context:
            await context.debug(f"✅ {file_name} uploaded successfully")

    if context:
        await context.info(f"🎉 Upload completed: {len(uploaded_files)} files")

    return {
        "uploaded_count": len(uploaded_files),
        "files": uploaded_files,
        "total_size": sum(int(f["size"].split()[0]) for f in uploaded_files),
        "status": "completed"
    }


async def run_streaming_server(host: str, port: int, debug: bool):
    """Run the streaming server."""
    logger.info(f"🚀 Starting MCP streaming server on http://{host}:{port}")
    if debug:
        logger.warning("Running in debug mode. Do not use in production.")

    # Create Starlette application with streaming support
    app = create_streamable_http_app(
        server=mcp,
        streamable_http_path="/mcp/",
        stateless_http=False,  # Keep session state
        debug=debug,
    )

    # Configure uvicorn
    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="info",
        access_log=False,
    )

    # Run server
    server = uvicorn.Server(config)

    await server.serve()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the FastMCP Streaming Demo Server.")
    parser.add_argument(
        "--host", type=str, default="127.0.0.1", help="Host to bind the server to."
    )
    parser.add_argument(
        "--port", type=int, default=8002, help="Port to listen on."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode for the Starlette app.",
    )
    args = parser.parse_args()

    try:
        asyncio.run(run_streaming_server(host=args.host, port=args.port, debug=args.debug))
    except KeyboardInterrupt:
        logger.info("🛑 Server stopped by user.")
    except Exception as e:
        logger.error("❌ Server error:", exc_info=True)
        raise