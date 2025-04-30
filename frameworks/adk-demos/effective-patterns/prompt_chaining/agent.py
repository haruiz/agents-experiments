from typing import Optional, List, Dict
from dotenv import load_dotenv
from rich import print
from rich.panel import Panel

from google.adk import Runner
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.artifacts import InMemoryArtifactService
from google.adk.models import LlmRequest, LlmResponse
from google.adk.sessions import InMemorySessionService
from google.genai import types

# --- Load environment variables ---
load_dotenv()

# --- Constants ---
BLOCKED_KEYWORDS = ["apple"]  # Extendable

# --- Agent Configs ---
AGENT_CONFIGS: List[Dict] = [
    {
        "name": "joke_generator",
        "description": "Generate a joke",
        "instruction": "Generate a joke based on the user prompt",
        "output_key": "joke",
        "temperature": 1.0
    },
    {
        "name": "joke_improver",
        "description": "Improve the joke",
        "instruction": "Make the joke funnier and more engaging",
        "output_key": "improved_joke",
        "temperature": 0.7
    },
    {
        "name": "joke_publisher",
        "description": "Publish the joke",
        "instruction": "Publish the joke, add a surprise twist at the end",
        "output_key": "published_joke",
        "temperature": 0.5
    },
]

# --- Guardrail Callback ---
def on_before_model_callback(callback_context: CallbackContext, llm_request: LlmRequest) -> Optional[LlmResponse]:
    """
    Guardrail function to block inappropriate prompts.
    """
    prompt = llm_request.contents[0].parts[0].text.lower()
    print(Panel.fit(f"[bold magenta]Agent:[/bold magenta] {callback_context.agent_name}\n[bold cyan]Prompt:[/bold cyan] {prompt}"))

    for word in BLOCKED_KEYWORDS:
        if word in prompt:
            raise ValueError(f"❌ Prompt contains forbidden word: '{word}'. Please rephrase.")

    return None

# --- Agent Factory ---
def create_llm_agent(config: Dict) -> LlmAgent:
    return LlmAgent(
        name=config["name"],
        description=config["description"],
        model="gemini-2.0-flash",
        global_instruction=f"You are a {config['description'].lower()}.",
        instruction=config["instruction"],
        output_key=config["output_key"],
        generate_content_config=types.GenerateContentConfig(temperature=config["temperature"]),
        before_model_callback=on_before_model_callback
    )

# --- Create Sequential Workflow ---
joke_agents = [create_llm_agent(cfg) for cfg in AGENT_CONFIGS]
joke_workflow = SequentialAgent(
    name="joke_generator_workflow",
    description="Generate, improve, and publish a joke",
    sub_agents=joke_agents
)

# --- Set root agent for the web user interface ---
root_agent = joke_workflow

# --- Execution Handlers ---
def call_agent(prompt: str):
    """
    Run the agent workflow with a user prompt.
    """
    print(Panel.fit(f"[bold white]User Prompt:[/bold white] {prompt}", title="👤"))
    content = types.Content(role="user", parts=[types.Part(text=prompt)])
    events = runner.run(user_id=USER_ID, session_id=SESSION_ID, new_message=content)

    for event in events:
        if event.is_final_response() and event.content:
            print(Panel.fit(f"[bold green]{event.author}:[/bold green] {event.content.parts[0].text}", title="🤖"))

def inspect_state():
    """
    Inspect and print the internal session state.
    """
    state = runner.session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID).state
    print(Panel.fit("[bold yellow]Session State[/bold yellow]"))
    for key, value in state.items():
        print(f"[cyan]{key}[/cyan]:\n{value}\n")

# --- Main Execution ---
if __name__ == '__main__':
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
        agent=joke_workflow,
        app_name=APP_NAME,
        session_service=session_service,
        artifact_service=artifact_service
    )

    try:
        call_agent("Tell me a robot joke")
        inspect_state()
    except Exception as e:
        print(Panel.fit(f"[bold red]Error:[/bold red] {str(e)}", title="❌"))
