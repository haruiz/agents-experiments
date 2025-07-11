import asyncio
import os
import uuid

from google.adk.agents import BaseAgent
from google.adk.agents.loop_agent import LoopAgent
from google.adk.agents.llm_agent import LlmAgent
from google.adk.artifacts import InMemoryArtifactService
from google.genai import types
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from dotenv import load_dotenv, find_dotenv

# Load environment variables from .env file
load_dotenv(find_dotenv())

# --- Constants ---
APP_NAME = "doc_writing_app"
GEMINI_MODEL = "gemini-2.0-flash"

# --- State Keys ---
STATE_INITIAL_TOPIC = "quantum physics"
STATE_CURRENT_DOC = "current_document"
STATE_CRITICISM = "criticism"

writer_agent = LlmAgent(
    name="WriterAgent",
    model=GEMINI_MODEL,
    instruction=f"""
    You are a Creative Writer AI.
    Check the session state for '{STATE_CURRENT_DOC}'.
    If '{STATE_CURRENT_DOC}' does NOT exist or is empty, write a very short (1-2 sentence) story or document based on the topic in state key '{STATE_INITIAL_TOPIC}'.
    If '{STATE_CURRENT_DOC}' *already exists* and '{STATE_CRITICISM}', refine '{STATE_CURRENT_DOC}' according to the comments in '{STATE_CRITICISM}'."
    Output *only* the story or the exact pass-through message.
    """,
    description="Writes the initial document draft.",
    output_key=STATE_CURRENT_DOC # Saves output to state
)

# Critic Agent (LlmAgent)
critic_agent = LlmAgent(
    name="CriticAgent",
    model=GEMINI_MODEL,
    instruction=f"""
    You are a Constructive Critic AI.
    Review the document provided in the session state key '{STATE_CURRENT_DOC}'.
    Provide 1-2 brief suggestions for improvement (e.g., "Make it more exciting", "Add more detail").
    Output *only* the critique.
    """,
    description="Reviews the current document draft.",
    output_key=STATE_CRITICISM # Saves critique to state
)

# Create the LoopAgent
loop_agent = LoopAgent(
    name="LoopAgent", sub_agents=[writer_agent, critic_agent], max_iterations=5
)

root_agent = loop_agent


async def call_agent_async(agent: BaseAgent, prompt: str) -> None:
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
    events = runner.run_async(user_id=USER_ID, session_id=SESSION_ID, new_message=content)

    async for event in events:
        if event.is_final_response() and event.content:
            response_text = event.content.parts[0].text
            print(response_text)

if __name__ == '__main__':
    asyncio.run(call_agent_async(
        agent=root_agent,
        prompt=f"Write a short document about {STATE_INITIAL_TOPIC}."
    ))