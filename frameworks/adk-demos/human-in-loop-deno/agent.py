import os
import uuid

from google.adk.agents import Agent
from google.adk.events import Event
from google.adk.runners import InMemorySessionService, InMemoryRunner
from google.adk.tools import ToolContext, LongRunningFunctionTool
from typing import Any, Dict, Union
import asyncio
from google.genai import types
from dotenv import load_dotenv, find_dotenv
from rich import print

load_dotenv(find_dotenv())

def reimburse(purpose: str, amount: float) -> dict[str, Any]:
  """Reimburse the amount of money to the employee."""
  return {
      'status': 'ok',
       'amount': amount,
  }


def ask_for_approval(
    purpose: str, amount: float, tool_context: ToolContext
) -> dict[str, Any]:
  """Ask for approval for the reimbursement."""
  return {
      'status': 'pending',
      'amount': amount,
      'ticketId': 'reimbursement-ticket-001',
  }

root_agent = Agent(
    model='gemini-1.5-flash',
    name='reimbursement_agent',
    instruction="""
      You are an agent whose job is to handle the reimbursement process for
      the employees. If the amount is less than $100, you will automatically
      approve the reimbursement.

      If the amount is greater than $100, you will
      ask for approval from the manager. If the manager approves, you will
      call reimburse() to reimburse the amount to the employee. If the manager
      rejects, you will inform the employee of the rejection.
    """,
    tools=[reimburse, LongRunningFunctionTool(func=ask_for_approval)],
    generate_content_config=types.GenerateContentConfig(temperature=0.1),
)



async def call_agent(message: types.Content, runner: InMemoryRunner,state: dict,  user_id: str, session_id: str) -> None:
    """Main function to run the agent."""
    events = runner.run_async(user_id=user_id, session_id=session_id, new_message=message)

    # Run the agent
    async for event in events:
        if event.content and event.content.parts:
            for i, part in enumerate(event.content.parts):
                if part.text:
                    print(f"Part {i} [Text]: {part.text.strip()}")
                if part.function_call:
                    print(f"Part {i} [Function Call]: {part.function_call.name} with args {part.function_call.args}")
                    if part.function_call.id in ( event.long_running_tool_ids or [] ):
                        print(f"Part {i} [Long Running Tool]: {part.function_call.name} with args {part.function_call.args}")
                        state["current_long_running_function_call"] = part.function_call

                if part.function_response:
                    print(f"Part {i} [Function Response]: {part.function_response.response}")
                    if part.function_response.id == state.get("current_long_running_function_call").id:
                        state["current_long_running_initial_tool_response"] = part.function_response
                        if part.function_response:
                            state["current_long_running_function_ticket_id"] = part.function_response.response.get("ticketId", "unknown")
                            print(f"Ticket ID: {state['current_long_running_function_ticket_id']}")


async def simulate_reimbursement_process(runner: InMemoryRunner, state: dict, user_id: str, session_id: str):
    """Simulate the reimbursement process with a sample query."""
    user_feedback = input("Please enter your feedback: ")
    if user_feedback:
        print(f"User Feedback: {user_feedback}")
        if state.get("current_long_running_function_call"):
            if user_feedback.strip() == "y":
                    print(f"Approving reimbursement for ticket ID: {state['current_long_running_function_ticket_id']}")

                    updated_tool_output_data = {
                        "status": "approved",
                        "ticketId": state["current_long_running_function_ticket_id"],
                        "approver_feedback": "Approved by manager at " + str(
                            asyncio.get_event_loop().time()
                        ),
                    }
            else:
                print(f"Rejecting reimbursement for ticket ID: {state['current_long_running_function_ticket_id']}")

                updated_tool_output_data = {
                    "status": "rejected",
                    "ticketId": state["current_long_running_function_ticket_id"],
                    "approver_feedback": "Rejected by manager at " + str(
                        asyncio.get_event_loop().time()
                    ),
                }

            updated_function_response_part = types.Part(
                function_response=types.FunctionResponse(
                    id=state["current_long_running_function_call"].id,
                    name= state["current_long_running_function_call"].name,
                    response=updated_tool_output_data,
                )
            )
            await call_agent(
                types.Content(
                    parts=[updated_function_response_part], role="user"
                ),
                runner=runner,
                state=state,
                user_id=user_id,
                session_id=session_id
            )



async def main() -> None:
    app_name = os.getenv('APP_NAME', str(uuid.uuid4()))
    user_id = os.getenv('USER_ID', 'user-123')
    session_id = os.getenv('SESSION_ID', 'session-456')

    runner = InMemoryRunner(agent=root_agent, app_name=app_name)
    session = await runner.session_service.create_session(
        app_name=app_name, user_id=user_id, session_id=session_id
    )

    state = {
        "current_long_running_function_call": None,
        "current_long_running_initial_tool_response": None,
        "current_long_running_function_ticket_id": None,
    }

    query = "I need to reimburse $150 for office supplies."
    print(f"User Prompt: {query}")
    message = types.Content(role="user", parts=[types.Part(text=query)])
    await call_agent(message, runner, state, user_id, session_id)
    # Simulate the reimbursement process
    await simulate_reimbursement_process(runner, state, user_id, session_id)


if __name__ == '__main__':

    asyncio.run(main())

    # You can also test with a smaller amount
    # query = "I need to reimburse $50 for lunch."
    # asyncio.run(call_agent(query))
