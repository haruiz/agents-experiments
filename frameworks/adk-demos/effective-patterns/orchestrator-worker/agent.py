from typing import AsyncGenerator, List, Dict, Optional
from dotenv import load_dotenv
from rich import print
from rich.panel import Panel

from google.adk import Runner
from google.adk.agents import LlmAgent, LoopAgent, BaseAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.invocation_context import InvocationContext
from google.adk.artifacts import InMemoryArtifactService
from google.adk.models import LlmRequest, LlmResponse
from google.adk.sessions import InMemorySessionService
from google.adk.events import Event, EventActions
from google.genai import types

# Load .env file
load_dotenv()


# --- Task Definitions ---
TASK_CONFIGS: List[Dict[str, str]] = [
    {
        "name": "joke_generator",
        "instruction": "Generate a joke based on the user prompt",
        "output_key": "joke"
    },
    {
        "name": "song_generator",
        "instruction": "Generate a song based on the user prompt",
        "output_key": "song"
    },
    {
        "name": "poem_generator",
        "instruction": "Generate a poem based on the user prompt",
        "output_key": "poem"
    },
]

# --- Guardrail Callback ---
def on_before_model_callback(callback_context: CallbackContext, llm_request: LlmRequest) -> Optional[LlmResponse]:
    """
    Intercepts the prompt before sending it to the model. Useful for filtering or logging.
    Blocks LLM call if restricted keyword is present.
    """
    prompt = llm_request.contents[0].parts[0].text
    if "bruno" in prompt.lower():
        return LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part(text="LLM call was blocked. We don't talk about Bruno!!")],
            )
        )
    return None

# --- Agent Factory ---
def create_task_handler_agent(task: Dict[str, str]) -> LlmAgent:
    """
    Creates an LLM Agent from a task configuration dictionary.
    Each task must include: name, instruction, and output_key.
    """
    return LlmAgent(
        name=task["name"],
        description=f"Generate a {task['output_key']}",
        model=task.get("model", "gemini-2.0-flash"),
        global_instruction=task.get("global_instruction", f"You are a {task['output_key']} generator."),
        instruction=task["instruction"],
        output_key=task["output_key"],
        generate_content_config=types.GenerateContentConfig(
            temperature=task.get("temperature", 1.0)
        ),
        before_model_callback=on_before_model_callback,
    )

# --- Create Agents from Configs ---
task_handler_agents = [create_task_handler_agent(task) for task in TASK_CONFIGS]

# --- Generic CheckCondition Agent ---
class CheckCondition(BaseAgent):
    output_keys : List[str] = []

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        is_done = all(ctx.session.state.get(key) is not None for key in self.output_keys)
        yield Event(author=self.name, actions=EventActions(escalate=is_done))

# --- Setup Orchestrator Agent ---
output_keys = [task["output_key"] for task in TASK_CONFIGS]

orchestrator_agent = LoopAgent(
    name="coordinator_agent",
    max_iterations=10,
    sub_agents=task_handler_agents + [CheckCondition(name="Checker", output_keys=output_keys)]
)

# --- Set root agent for the web user interface ---
root_agent = orchestrator_agent


# --- Agent Interaction Functions ---
def call_agent(prompt: str):
    """
    Trigger the orchestrator with a prompt.
    """
    print(Panel.fit(f"[bold white]User Prompt:[/bold white] {prompt}", title="👤"))
    content = types.Content(role="user", parts=[types.Part(text=prompt)])
    events = runner.run(user_id=USER_ID, session_id=SESSION_ID, new_message=content)

    for event in events:
        if event.is_final_response() and event.content:
            response = event.content.parts[0].text
            print(Panel.fit(f"[bold green]{event.author}:[/bold green] {response}", title="🤖"))

def inspect_state():
    """
    Print session state from memory.
    """
    state = runner.session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID).state
    print(Panel.fit("[bold yellow]Session State[/bold yellow]"))
    for key, value in state.items():
        print(f"[cyan]{key}[/cyan]: {value}")

# --- Main Entry Point ---
if __name__ == '__main__':
    # --- Constants ---
    APP_NAME = "joke_generator_app"
    USER_ID = "dev_user_01"
    SESSION_ID = "dev_user_session_01"

    # --- Session & Runner Setup ---
    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()
    session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )

    runner = Runner(
        agent=orchestrator_agent,
        app_name=APP_NAME,
        session_service=session_service,
        artifact_service=artifact_service,
    )

    call_agent("Robots")
    # inspect_state()
