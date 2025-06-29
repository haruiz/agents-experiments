import io

from PIL import Image
from dotenv import load_dotenv
from google.adk import Runner
from google.adk.agents import LlmAgent
from google.adk.artifacts import InMemoryArtifactService
from google.adk.sessions import InMemorySessionService
from google.adk.code_executors import BuiltInCodeExecutor
from google.genai import types
from rich import print
from rich.panel import Panel

# Load .env file
load_dotenv()


root_agent = LlmAgent(
    name="CodeAgent",
    model="gemini-2.0-flash",
    code_executor=BuiltInCodeExecutor(),
    instruction="""You are a calculator agent.
       When given a mathematical expression, function, or task, write and EXECUTE the Python code to obtain the result.
       """,
    description="Executes Python code to perform calculations.",
)


async def call_agent(prompt: str):
    """
    Send user input to the orchestrator agent and stream responses.
    """
    # --- Services ---
    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()
    session = await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )
    # --- Runner Setup ---
    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
        artifact_service=artifact_service,
    )
    print(Panel.fit(f"[bold white]User Prompt[/bold white]: {prompt}", title="👤"))
    content = types.Content(role="user", parts=[types.Part(text=prompt)])
    events = runner.run_async(user_id=USER_ID, session_id=SESSION_ID, new_message=content)

    async for event in events:
        # --- Check for specific parts FIRST ---
        has_specific_part = False
        if event.content and event.content.parts:
            for part in event.content.parts:  # Iterate through all parts
                if part.executable_code:
                    # Access the actual code string via .code
                    print(f"  Debug: Agent generated code:\n```python\n{part.executable_code.code}\n```")
                    has_specific_part = True
                elif part.code_execution_result:
                    # Access outcome and output correctly
                    print(
                        f"  Debug: Code Execution Result: {part.code_execution_result.outcome} - Output:\n{part.code_execution_result.output}")
                    has_specific_part = True
                elif part.inline_data:
                    print(f"  Debug: Inline Data: {part.inline_data.mime_type}")
                    if part.inline_data.mime_type == "image/png":
                        # Access the image data and display it
                        image_data = part.inline_data.data
                        image = Image.open(io.BytesIO(image_data))
                        image.show()
                # Also print any text parts found in any event for debugging
                elif part.text and not part.text.isspace():
                    print(f"  Text: '{part.text.strip()}'")
                    # Do not set has_specific_part=True here, as we want the final response logic below

        # --- Check for final response AFTER specific parts ---
        # Only consider it final if it doesn't have the specific code parts we just handled
        if not has_specific_part and event.is_final_response():
            if event.content and event.content.parts and event.content.parts[0].text:
                final_response_text = event.content.parts[0].text.strip()
                print(f"==> Final Agent Response: {final_response_text}")
            else:
                print("==> Final Agent Response: [No text content in final event]")


# --- Entry Point ---
if __name__ == '__main__':
    # --- Constants ---
    APP_NAME = "code_refinement_app"
    USER_ID = "user_123"
    SESSION_ID = "session_456"

    cor = call_agent(
        "Generates an array of 1000 random numbers from a normal distribution with mean 0 and standard deviation 1, "
        "create a histogram of the data, and "
        "save the histogram as a PNG file plot.png")
    import asyncio
    asyncio.run(cor)