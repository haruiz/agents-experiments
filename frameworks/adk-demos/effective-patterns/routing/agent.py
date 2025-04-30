from dotenv import load_dotenv
from rich import print
from rich.panel import Panel
from typing import Optional, List, Dict

from google.adk import Runner
from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.artifacts import InMemoryArtifactService
from google.adk.models import LlmRequest, LlmResponse
from google.adk.sessions import InMemorySessionService
from google.genai import types

# --- Load environment ---
load_dotenv()

# --- Constants ---
BLOCKED_KEYWORDS = ["apple"]

# --- Router Config: Define Routing Sub-Agents ---
ROUTER_CONFIG: List[Dict] = [
    {
        "name": "joke_generator",
        "description": "Generate a joke",
        "instruction": "Generate a joke based on the user prompt",
        "output_key": "joke",
        "temperature": 1.0
    },
    {
        "name": "song_generator",
        "description": "Generate a song",
        "instruction": "Generate a song based on the user prompt",
        "output_key": "song",
        "temperature": 1.0
    },
    {
        "name": "poem_generator",
        "description": "Generate a poem",
        "instruction": "Generate a poem based on the user prompt",
        "output_key": "poem",
        "temperature": 1.0
    }
]

# --- Guardrail Callback ---
def on_before_model_callback(callback_context: CallbackContext, llm_request: LlmRequest) -> Optional[LlmResponse]:
    prompt = llm_request.contents[0].parts[0].text.lower()
    print(Panel.fit(f"[bold magenta]Agent:[/bold magenta] {callback_context.agent_name}\n[bold cyan]Prompt:[/bold cyan] {prompt}"))

    for word in BLOCKED_KEYWORDS:
        if word in prompt:
            raise ValueError(f"❌ Prompt contains forbidden word: '{word}'. Please rephrase.")

    return None


# --- Helper: Agent Factory from Router Config ---
def create_llm_agent(config: Dict) -> LlmAgent:
    return LlmAgent(
        name=config["name"],
        description=config["description"],
        model="gemini-2.0-flash",
        global_instruction=f"You are a {config['description'].lower()}.",
        instruction=config["instruction"],
        output_key=config["output_key"],
        generate_content_config=types.GenerateContentConfig(temperature=config.get("temperature", 1.0)),
        before_model_callback=on_before_model_callback
    )

# Create sub-agents from config
sub_agents = [create_llm_agent(cfg) for cfg in ROUTER_CONFIG]

# --- Router Agent ---
router_instruction = (
    "You are a router agent.\n"
    "Given the user prompt, decide whether it's a request for a joke, song, or poem, and delegate accordingly.\n"
    "Use only the appropriate sub-agent based on the topic.\n"
)

router_agent = LlmAgent(
    name="root_router",
    model="gemini-2.0-flash",
    description="Router agent that delegates to joke, song, or poem generators.",
    instruction=router_instruction,
    sub_agents=sub_agents,
    output_key="final_response",
    before_model_callback=on_before_model_callback
)

# --- Set root agent for the web user interface ---
root_agent = router_agent

# --- Execution Helpers ---
def call_agent(prompt: str):
    """
    Call the router agent with a user prompt and print the response.
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
    Print the internal session state.
    """
    state = session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID).state
    print(Panel.fit("[bold yellow]Session State[/bold yellow]"))
    for key, value in state.items():
        print(f"[cyan]{key}[/cyan]: {value}")


# --- Entry Point ---
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
        agent=router_agent,
        app_name=APP_NAME,
        session_service=session_service,
        artifact_service=artifact_service
    )

    try:
        topic = "robots"
        call_agent(f"write a poem about {topic}")
        inspect_state()
    except Exception as e:
        print(Panel.fit(f"[bold red]Error:[/bold red] {str(e)}", title="❌"))
