import logging
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from google.adk import Runner, Agent
from google.adk.agents import LlmAgent, LoopAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.artifacts import InMemoryArtifactService
from google.adk.sessions import InMemorySessionService
from google.genai import types
from rich.logging import RichHandler
from tabulate import tabulate

# Load environment variables from .env
load_dotenv()

# --- Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=False)],
)
logger = logging.getLogger(__name__)

# Use this path for testing your agent using the Web UI since the command is run from the root folder
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.getenv("DB_PATH")
APP_NAME = "db_agent_app"
USER_ID = "dev_user_01"
SESSION_ID = "dev_user_session_01"

# --- Agent Tools ---
def get_db_schema() -> Dict[str, Any]:
    """
    Fetch the SQL schema of the database as Markdown text.

    Returns:
        dict: Dictionary containing status and schema or error message.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name, sql FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name;
            """)
            schema_entries = cursor.fetchall()

        schema_md = "** SQLite Schema\n"
        for table_name, create_sql in schema_entries:
            schema_md += f"\n** Table: {table_name}\n{create_sql};\n"

        return {"status": "success", "schema": schema_md}
    except sqlite3.Error as e:
        logger.exception("Failed to fetch DB schema.")
        return {"status": "error", "error_message": str(e)}


def execute_sql_query(query: str) -> Dict[str, Any]:
    """
    Execute a SQL query and return results as a Markdown table.

    Args:
        query (str): The SQL statement to run.

    Returns:
        dict: Dictionary containing execution status and results or error message.
    """
    logger.info("Executing SQL query:\n%s", query)
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            headers = [desc[0] for desc in cursor.description]

        if not rows:
            logger.info("Query executed successfully. No rows returned.")
            return {"status": "success", "results": "No results returned."}

        markdown_table = tabulate(rows, headers=headers, tablefmt="github")
        logger.info("Query executed successfully.")
        return {"status": "success", "results": markdown_table}
    except sqlite3.Error as e:
        logger.exception("Query execution failed.")
        return {"status": "error", "error_message": str(e)}


def on_before_agent_call(callback_context: CallbackContext) -> None:
    """
    Invoked before each agent call. Used to inspect or modify context.

    Args:
        callback_context (CallbackContext): Execution context.
    """
    logger.debug("Before agent callback triggered. State: %s", callback_context.state)


# --- Initialize Schema ---
schema_result = get_db_schema()
if schema_result["status"] != "success":
    raise RuntimeError("Failed to retrieve database schema.")

schema_text = schema_result["schema"]

# --- Define Agents ---
sql_junior_writer_agent = LlmAgent(
    name="sql_junior_writer_agent",
    model="gemini-2.0-flash",
    description="Generates SQL queries from user prompts.",
    global_instruction=(
        "You are a data assistant specializing in SQL. "
        f"Use this schema to write syntactically correct SQL: {schema_text}"
    ),
    instruction=(
        "Use the provided schema in session state under 'db_schema' to write a SQL query. "
        "Store your result in 'sql_query'. Do not execute it."
    ),
    output_key="sql_query",
    tools=[get_db_schema],
    generate_content_config=types.GenerateContentConfig(temperature=0.01),
)

sql_senior_writer_agent = Agent(
    name="sql_senior_writer_agent",
    model="gemini-2.0-flash",
    description="Validates and executes SQL queries.",
    instruction=(
        "Review the SQL query in session state under 'sql_query' using this schema: "
        f"{schema_text}. Validate it for correctness and best practices. "
        "If valid, execute it using 'execute_sql_query' and return the result."
    ),
    tools=[execute_sql_query, get_db_schema],
    output_key="sql_results",
    generate_content_config=types.GenerateContentConfig(temperature=0.01),
)

# --- Loop Agent ---
root_agent = LoopAgent(
    name="root_agent",
    sub_agents=[sql_junior_writer_agent, sql_senior_writer_agent],
    max_iterations=3,
    before_agent_callback=on_before_agent_call,
    description="Coordinates SQL generation and execution pipeline.",
)

# --- Runtime Entrypoint ---
def call_agent(prompt: str) -> None:
    """
    Call the root agent with a prompt and print the final output.

    Args:
        prompt (str): Natural language query for database.
    """
    content = types.Content(role="user", parts=[types.Part(text=prompt)])
    events = runner.run(user_id=USER_ID, session_id=SESSION_ID, new_message=content)

    for event in events:
        if event.is_final_response() and event.content:
            logger.info("\n\n[Final Response]\n%s", event.content.parts[0].text)


if __name__ == "__main__":
    # --- Session & Runner Setup ---
    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()
    session = session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )

    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
        artifact_service=artifact_service
    )

    call_agent("List the name of the first 5 customers in my database")
