import logging
from pathlib import Path

from dotenv import load_dotenv
from google.adk import Agent
from google.adk.tools import load_artifacts
from google.adk.tools import ToolContext
from google.adk.tools.agent_tool import AgentTool
from .prompts import get_agent_instructions

from coder_agent.agent import create_coder_assistant_agent
from sql_agent.agent import create_sql_assistant_agent


load_dotenv(dotenv_path=Path(__file__).parents[1].resolve().joinpath(".env"))
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


coder_assistant = create_coder_assistant_agent(model_name="gemini-2.0-flash")
sql_assistant = create_sql_assistant_agent(model_name="gemini-2.0-flash")

async def call_sql_assistant_agent(
    question: str,
    tool_context: ToolContext,
):
    agent_tool = AgentTool(agent=sql_assistant)
    db_agent_output = await agent_tool.run_async(
        args={"request": question}, tool_context=tool_context
    )
    return db_agent_output


async def call_coder_assistant_agent(
    question: str,
    tool_context: ToolContext,
):
    logger.info(question)
    await tool_context.load_artifact("sql_results.csv")
    agent_tool = AgentTool(agent=coder_assistant)
    db_agent_output = await agent_tool.run_async(
        args={"request": question}, tool_context=tool_context
    )
    return db_agent_output

def create_root_agent(model_name: str = "gemini-2.0-flash") -> Agent:
    """
    Creates a root agent that coordinates SQL and coding assistants.
    """
    return Agent(
        name="root_agent",
        description="Root agent that coordinates SQL and coding assistants.",
        model=model_name,
        global_instruction=(
            "You are a senior tasked to assist user in writing SQL queries and Python code to interact with the provide database schema. "
            "You will be task to identify the user's intent and provide the appropriate SQL or Python code. "
        ),
        instruction=get_agent_instructions(),
        tools=[
            call_sql_assistant_agent,
            call_coder_assistant_agent,
            load_artifacts
        ]
    )


root_agent = create_root_agent(model_name="gemini-2.0-flash")

