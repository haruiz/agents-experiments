from fastapi import FastAPI
from ag_ui_adk import ADKAgent, add_adk_fastapi_endpoint
from google.adk import Agent
from dotenv import load_dotenv
from google.adk.tools import MCPToolset
from google.adk.tools.mcp_tool import StreamableHTTPConnectionParams
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from tools import get_weather, get_place_location, get_place_details
import logging

# Initialize logger for debugging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Load environment variables from .env file
load_dotenv()


agent_instructions = """
You are a helpful assistant designed to answer user questions and provide useful information, 
including weather updates and place details using Google Maps data.

Behavior Guidelines:
- If the user greets you, respond specifically with "Hello".
- If the user greets you without making any request, reply with "Hello" and ask, "How can I assist you?"
- If the user asks a direct question, provide the most accurate and helpful answer possible.

Tool Usage:
- get_weather: Retrieve the current weather information for a specified location.
- get_place_location: Obtain the precise latitude and longitude of a specified place.
- get_place_details: Fetch detailed information about a place using its geographic coordinates.

Always choose the most appropriate tool to fulfill the user's request, and respond clearly and concisely.
"""
# -------------------------------------------------------------------
# Create a base Google ADK agent definition
# This is the core LLM agent that will power the application
# -------------------------------------------------------------------
weather_agent = Agent(
    name="assistant",                    # Internal agent name
    model="gemini-2.5-flash",            # LLM model to use
    instruction=agent_instructions,
    tools=[
        # Provides persistent memory during the session (non-long-term)
        PreloadMemoryTool(),

        # Direct tool integration example
        # get_weather,
        get_place_location,
        get_place_details,
        # MCP Toolset integration
        MCPToolset(
            connection_params=StreamableHTTPConnectionParams(
                url="http://127.0.0.1:8080/mcp"   # Local MCP server endpoint
            )
        )
    ]
)

# -------------------------------------------------------------------
# Wrap the agent inside an ADKAgent middleware
# This provides sessions, user identity, in-memory services,
# and the unified ADK API that frontend UI components expect.
# -------------------------------------------------------------------
ag_weather_agent = ADKAgent(
    adk_agent=weather_agent,            # The core ADK agent
    app_name="demo_app",                # App identifier
    user_id="demo_user",                # Mock user ID (replace in production)
    session_timeout_seconds=3600,       # Session expiration
    use_in_memory_services=True         # Enables in-memory RAG + storage
)

# Create the FastAPI application
app = FastAPI(title="ADK Middleware Basic Chat")

# -------------------------------------------------------------------
# Register an ADK-compliant endpoint with FastAPI.
# This exposes the chat API at "/".
# Your frontend (Next.js + CopilotKit) will call this endpoint.
# -------------------------------------------------------------------
add_adk_fastapi_endpoint(app, ag_weather_agent, path="/")

# -------------------------------------------------------------------
# Run the development server using Uvicorn
# Only executes when running `python main.py`
# -------------------------------------------------------------------
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(
        "main:app",
        host="localhost",
        port=8000,
        reload=True,        # Auto-reload on code changes
        workers=1           # Single worker recommended for MCP tools
    )
