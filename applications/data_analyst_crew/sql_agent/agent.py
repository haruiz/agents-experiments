import logging
from pathlib import Path
from dotenv import load_dotenv
from google.adk import Agent
from google.adk.agents import LlmAgent, LoopAgent
from google.genai import types

from .tools import get_db_schema, execute_sql_query
from .prompts import get_agents_prompts

# Load environment variables
load_dotenv(dotenv_path=Path(__file__).parents[1].resolve().joinpath(".env"))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_sql_assistant_agent(model_name: str = "gemini-2.0-flash", max_iterations: int = 5) -> LoopAgent:
    """
    Creates a SQL assistant agent that generates and executes SQL queries.
    """
    junior_instruction, senior_instruction = get_agents_prompts()

    sql_junior_writer_agent = LlmAgent(
        name="sql_junior_writer_agent",
        model=model_name,
        description="Generates SQL queries from user prompts.",
        global_instruction="You are a data assistant specializing in SQL. Use the provided schema to write syntactically correct SQL queries.",
        instruction=junior_instruction,
        output_key="sql_query",
        tools=[get_db_schema],
        generate_content_config=types.GenerateContentConfig(temperature=0.01),
    )

    sql_senior_writer_agent = Agent(
        name="sql_senior_writer_agent",
        model=model_name,
        description="Validates and executes SQL queries.",
        instruction=senior_instruction,
        output_key="sql_results",
        tools=[execute_sql_query, get_db_schema],
        generate_content_config=types.GenerateContentConfig(temperature=0.01),
    )

    return LoopAgent(
        name="root_agent",
        sub_agents=[sql_junior_writer_agent, sql_senior_writer_agent],
        max_iterations=max_iterations,
        description="Coordinates SQL generation and execution pipeline.",
    )


# Initialize agent
root_agent = create_sql_assistant_agent(model_name="gemini-2.0-flash", max_iterations=5)

