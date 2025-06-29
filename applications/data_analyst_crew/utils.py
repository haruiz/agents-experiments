import logging

logger = logging.getLogger(__name__)

import os
import uuid

from google.adk import Runner
from google.adk.agents import BaseAgent
from google.adk.artifacts import InMemoryArtifactService
from google.adk.sessions import InMemorySessionService
from google.genai import types

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()

def render_rich_panel(author: str, content: str, language: str = "markdown") -> None:
    """
    Render content inside a stylized Rich panel with optional syntax highlighting.
    """
    syntax = Syntax(content, language, line_numbers=False, theme="monokai")
    panel = Panel(syntax, title=f"[bold cyan]{author}", border_style="green", padding=(1, 2))
    console.print(panel)

def detect_language(content: str) -> str:
    """
    Basic heuristic to guess content type for syntax highlighting.
    """
    if not content:
        return "markdown"
    content = content.strip()
    if content.startswith("{") and content.endswith("}"):
        return "json"
    elif content.lower().startswith("select") or " from " in content.lower():
        return "sql"
    return "markdown"

async def call_agent(agent: BaseAgent, prompt: str) -> None:
    """
    Call the root agent with a prompt and print the final output using Rich panels.

    Args:
        agent:  The agent to be called.
        prompt (str): Natural language query for database.
    """
    APP_NAME = os.getenv("APP_NAME", str(uuid.uuid4()))
    USER_ID = os.getenv("USER_ID", str(uuid.uuid4()))
    SESSION_ID = os.getenv("SESSION_ID", str(uuid.uuid4()))

    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()

    runner = Runner(
        agent=agent,
        app_name=APP_NAME,
        session_service=session_service,
        artifact_service=artifact_service,
    )
    session = await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )

    content = types.Content(role="user", parts=[types.Part(text=prompt)])
    events = runner.run(user_id=USER_ID, session_id=SESSION_ID, new_message=content)

    for event in events:
        if event.is_final_response() and event.content:
            response_text = event.content.parts[0].text
            logger.info(f"Final response from {event.author}")
            print(response_text)
