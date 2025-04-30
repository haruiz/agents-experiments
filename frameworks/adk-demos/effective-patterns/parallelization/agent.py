from dotenv import load_dotenv
from rich import print
from rich.panel import Panel
from typing import List, Dict, Optional

from google.adk import Runner
from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.artifacts import InMemoryArtifactService
from google.adk.models import LlmRequest, LlmResponse
from google.adk.sessions import InMemorySessionService
from google.genai import types

# --- Load Environment ---
load_dotenv()

# --- Constants ---
BLOCKED_KEYWORDS = ["bruno"]

# --- Task Definitions ---
TASK_CONFIGS: List[Dict[str, str]] = [
    {
        "name": "joke_generator",
        "description": "Generate a joke",
        "instruction": "Generate a joke based on the user prompt",
        "output_key": "joke"
    },
    {
        "name": "song_generator",
        "description": "Generate a song",
        "instruction": "Generate a song based on the user prompt",
        "output_key": "song"
    },
    {
        "name": "poem_generator",
        "description": "Generate a poem",
        "instruction": "Generate a poem based on the user prompt",
        "output_key": "poem"
    },
]

# --- Callback Guardrail ---
def on_before_model_callback(callback_context: CallbackContext, llm_request: LlmRequest) -> Optional[LlmResponse]:
    """
    Guardrail to block LLM execution for specific banned phrases.
    """
    prompt = llm_request.contents[0].parts[0].text.lower()
    print(Panel.fit(f"[bold magenta]Agent:[/bold magenta] {callback_context.agent_name}\n[bold cyan]Prompt:[/bold cyan] {prompt}"))

    for banned in BLOCKED_KEYWORDS:
        if banned in prompt:
            return LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=f"LLM call blocked. We don't talk about {banned.capitalize()}!!")]
                )
            )
    return None


# --- Helper: Create Agent from Task Config ---
def create_task_handler_agent(task: Dict[str, str]) -> LlmAgent:
    return LlmAgent(
        name=task["name"],
        description=task["description"],
        model="gemini-2.0-flash",
        global_instruction=f"You are a {task['description'].lower()} generator.",
        instruction=task["instruction"],
        output_key=task["output_key"],
        generate_content_config=types.GenerateContentConfig(temperature=1.0),
        before_model_callback=on_before_model_callback
    )

# --- Create Sub-agents ---
sub_agents = [create_task_handler_agent(task) for task in TASK_CONFIGS]

# --- Aggregator (Parallel Execution) ---
aggregator_agent = ParallelAgent(
    name="ParallelGenerator",
    sub_agents=sub_agents,
    description="Run joke, song, and poem generators in parallel based on the user prompt."
)

# --- Merger Agent ---
merger_agent = LlmAgent(
    name="merger_agent",
    description="Merge the outputs of the sub-agents into a structured response.",
    model="gemini-2.0-flash",
    global_instruction="You are a merger agent.",
    instruction=(
        "Your task is to merge the outputs of multiple sub-agents into a single, coherent, and structured response.\n\n"
        "- Do **not** add any external information, context, or commentary.\n"
        "- Use **only** the provided inputs: {joke}, {song}, and {poem}.\n"
        "- Maintain the exact order and structure specified below.\n\n"
        "### Joke:\n{joke}\n\n"
        "### Song:\n{song}\n\n"
        "### Poem:\n{poem}\n\n"
        "Instructions:\n"
        "- Do **not** include any introductory or concluding phrases.\n"
        "- Do **not** modify, interpret, or enhance the content of the inputs.\n"
        "- Strictly follow the format above and output only the merged content as shown."
    ),
    output_key="merged_response",
    generate_content_config=types.GenerateContentConfig(temperature=0.5),
)

# --- Root Agent (Sequential Flow) ---
root_agent = SequentialAgent(
    name="root_agent",
    sub_agents=[aggregator_agent, merger_agent],
    description="Coordinates generation and merging of joke, song, and poem."
)


# --- Interaction Functions ---
def call_agent(prompt: str):
    """
    Send a prompt to the root agent and print structured results.
    """
    print(Panel.fit(f"[bold white]User Prompt:[/bold white] {prompt}", title="👤"))
    content = types.Content(role="user", parts=[types.Part(text=prompt)])
    events = runner.run(user_id=USER_ID, session_id=SESSION_ID, new_message=content)

    for event in events:
        if event.is_final_response() and event.content:
            print(Panel.fit(f"[bold green]{event.author}:[/bold green]\n{event.content.parts[0].text}", title="🤖"))

def inspect_state():
    """
    Print the internal state of the session.
    """
    state = runner.session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID).state
    print(Panel.fit("[bold yellow]Session State[/bold yellow]"))
    for key, value in state.items():
        print(f"[cyan]{key}[/cyan]: {value}")

# --- Main ---
if __name__ == '__main__':
    APP_NAME = "joke_generator_app"
    USER_ID = "dev_user_01"
    SESSION_ID = "dev_user_session_01"

    # --- Session & Runner Setup ---
    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()

    session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID
    )

    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
        artifact_service=artifact_service
    )

    call_agent("Please generate something funny and poetic.")
    inspect_state()
