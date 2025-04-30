from typing import AsyncGenerator
from rich import print
from rich.panel import Panel
from google.adk import Runner
from google.adk.agents import LlmAgent, LoopAgent, BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.artifacts import InMemoryArtifactService
from google.adk.events import Event, EventActions
from google.adk.sessions import InMemorySessionService
from google.genai import types
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# --- Agent Definitions ---
def create_code_refiner() -> LlmAgent:
    return LlmAgent(
        name="CodeRefiner",
        model="gemini-2.0-flash",
        instruction=(
            "Read `state['current_code']` (if present) and `state['requirements']`. "
            "Generate or refine Python code to meet the requirements, "
            "then store the result in `state['current_code']`."
        ),
        output_key="current_code"
    )

def create_quality_checker() -> LlmAgent:
    return LlmAgent(
        name="QualityChecker",
        model="gemini-2.0-flash",
        instruction=(
            "Evaluate the code in `state['current_code']` against `state['requirements']`. "
            "If the code meets the requirements, output 'pass'; otherwise, output 'fail'."
        ),
        output_key="quality_status"
    )

class CheckStatusAndEscalate(BaseAgent):
    """
    Terminates the loop when the quality check passes.
    """
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        status = ctx.session.state.get("quality_status", "fail")
        should_stop = status.strip().lower() == "pass"
        yield Event(author=self.name, actions=EventActions(escalate=should_stop))

# --- Loop Agent ---
refinement_loop = LoopAgent(
    name="CodeRefinementLoop",
    max_iterations=5,
    sub_agents=[
        create_code_refiner(),
        create_quality_checker(),
        CheckStatusAndEscalate(name="StopChecker")
    ]
)

# --- Set root agent for the web user interface ---
root_agent = refinement_loop

def call_agent(prompt: str):
    """
    Send user input to the orchestrator agent and stream responses.
    """
    print(Panel.fit(f"[bold white]User Prompt[/bold white]: {prompt}", title="👤"))
    content = types.Content(role="user", parts=[types.Part(text=prompt)])
    events = runner.run(user_id=USER_ID, session_id=SESSION_ID, new_message=content)

    for event in events:
        if event.is_final_response() and event.content:
            response = event.content.parts[0].text
            print(Panel.fit(f"[bold green]{event.author}:[/bold green] {response}", title="🤖"))

def inspect_state():
    """
    Print the internal session state.
    """
    state = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID).state
    print(Panel.fit("[bold yellow]Session State[/bold yellow]"))
    for key, value in state.items():
        print(f"[cyan]{key}[/cyan]:\n{value}\n")

# --- Entry Point ---
if __name__ == '__main__':
    # --- Constants ---
    APP_NAME = "code_refinement_app"
    USER_ID = "user_123"
    SESSION_ID = "session_456"

    # --- Services ---
    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()

    session = session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )

    # --- Runner Setup ---
    runner = Runner(
        agent=refinement_loop,
        app_name=APP_NAME,
        session_service=session_service,
        artifact_service=artifact_service,
    )
    call_agent("Write a Python function that calculates the factorial of a number."
               "Make sure to add type hints to the function parameters and return type.")
    # inspect_state()
