import json
import logging
import re
from pathlib import Path
from typing import AsyncGenerator

from dotenv import load_dotenv
from google.adk.agents import LlmAgent, LoopAgent, BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.code_executors import UnsafeLocalCodeExecutor
from google.adk.events import Event, EventActions
from google.adk.code_executors import BuiltInCodeExecutor

from .prompts import get_agents_prompts

load_dotenv(dotenv_path=Path(__file__).parents[1].resolve().joinpath(".env"))
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


def extract_json_from_markdown(markdown_text: str) -> dict:
    """
    Extracts the first JSON code block from a markdown-formatted string and converts it to a Python dictionary.

    Args:
        markdown_text (str): A string containing markdown with a JSON code block.

    Returns:
        dict: A dictionary parsed from the JSON code block.

    Raises:
        ValueError: If no valid JSON code block is found or if JSON parsing fails.
    """
    # Match a JSON block enclosed in triple backticks (```json ... ```)
    json_block_match = re.search(r"```json\s*(\{.*?\})\s*```", markdown_text, re.DOTALL)
    if not json_block_match:
        raise ValueError("No JSON block found in the markdown text.")

    json_str = json_block_match.group(1)

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON: {e}")


class CheckStatusAndEscalate(BaseAgent):
    """
    Terminates the loop when the quality check passes.
    """
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        status_markdown = ctx.session.state.get("review_result",None)
        should_stop = False
        if status_markdown:
            status_json = extract_json_from_markdown(status_markdown)
            should_stop = status_json["quality_status"] == "pass"
        yield Event(author=self.name, actions=EventActions(escalate=should_stop))

def create_coder_assistant_agent(model_name: str = "gemini-2.0-flash", max_iterations: int = 3) -> LoopAgent:

    code_generation_prompt, code_reviewer_prompt = get_agents_prompts()

    code_generator_agent = LlmAgent(
        name="code_generator",
        model=model_name,
        description="Generates Python code based on user requirements.",
        instruction=code_generation_prompt,
        output_key="current_code"
    )

    code_reviewer_agent = LlmAgent(
        name="code_reviewer",
        model=model_name,
        description="Reviews and executes Python code.",
        code_executor=BuiltInCodeExecutor(),
        instruction=code_reviewer_prompt,
        output_key="review_result",
    )

    return LoopAgent(
        name="CodeRefinementLoop",
        max_iterations=max_iterations,
        sub_agents=[
            code_generator_agent,
            code_reviewer_agent,
            CheckStatusAndEscalate(name="StopChecker")
        ]
    )

root_agent = create_coder_assistant_agent(model_name="gemini-2.0-flash" , max_iterations=5)
