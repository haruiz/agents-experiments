import time
import os
from dotenv import load_dotenv, find_dotenv
from google.genai import types
from google import genai
from memory import Memory
from rich import print
from simple_agent import Agent

# Load environment variables (e.g., GEMINI_API_KEY)
load_dotenv(find_dotenv())

class LoopAgent(Agent):
    """
    A looping verbal agent that uses a large language model (LLM) to reason over context,
    perceive user input, make decisions, and act by calling tools that simulate interaction
    with the external environment.

    This agent extends a base `Agent` class and implements a memory-driven agentic loop.

    Attributes:
        model (str): Name or path of the Gemini model to use.
        name (str): Display name of the agent.
        max_iterations (int): Maximum number of loop iterations.
        tools (list[Callable]): List of callable Python functions (tools) that the LLM can invoke.
            Tools simulate the agent's ability to act on the environment and collect information.
        terminate_criteria (Callable): Optional function to determine if the agent should stop based on memory.
        memory (Memory): An in-memory structure storing perception, actions, outputs, and reasoning steps.
        llm_client (genai.Client): Google Gemini LLM client for generating content.
    """

    def __init__(
        self,
        model: str,
        name: str = "LoopAgent",
        max_iterations: int = 5,
        system_instruction: str = None,
        tools: list = None,
        terminate_criteria=None
    ):
        super().__init__(name)
        self.model = model
        self.max_iterations = max_iterations
        self.terminate_criteria = terminate_criteria
        self.tools = tools or []

        # Attach memory to internal state
        self.memory = Memory()
        self.state["memory"] = self.memory
        self.memory.add_entry("system_instruction", system_instruction)

        # Gemini LLM client
        self.llm_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.system_instruction = system_instruction

    def perceive(self):
        """
        Collect input from the user, representing the agent's perception of its environment.

        Returns:
            str: A user input string or 'exit' to terminate.
        """
        user_input = input(f"{self.name}: What would you like to know? (type 'exit' to quit)\n> ")
        return user_input.strip().lower()

    def decide(self, perception=None):
        """
        Generate a response based on memory and perceived input by invoking the LLM.

        Returns:
            types.GenerateContentResponse: A structured decision that may include tool calls.
        """
        return self.llm_client.models.generate_content(
            contents=str(self.memory),
            model=self.model,
            config=types.GenerateContentConfig(
                tools=self.tools,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            )
        )

    def act(self, decision):
        """
        Executes a decision made by the LLM.

        - If the decision contains function calls, the agent uses tools to interact with the environment.
        - Otherwise, it prints or logs the generated natural language response.

        Args:
            decision (GenerateContentResponse): The LLM output including text or tool calls.
        """
        if decision.function_calls:
            for call in decision.function_calls:
                output = self._execute_tool(call.name, call.args)
                self.memory.add_entry("context", output.get("result", output.get("error_message")))
        else:
            self.memory.add_entry("model_output", decision.text)
            print(f"{self.name}: {decision.text}")

    def _execute_tool(self, name: str, args: dict):
        """
        Safely execute a named tool with arguments.

        Tools simulate the agent's ability to collect data or act on its environment.

        Args:
            name (str): The name of the tool function to call.
            args (dict): Arguments to pass to the function.

        Returns:
            dict: Result or error message from the tool.
        """
        try:
            return globals()[name](**args)
        except Exception as e:
            return {
                "status": "error",
                "error_message": f"Failed to execute '{name}': {e}"
            }

    def run(self, initial_input=None):
        """
        Execute the main agentic loop.

        This function:
        - Repeatedly collects input (perceive),
        - Generates a decision using the LLM (decide),
        - Acts using tools or outputs (act),
        - Maintains memory of all steps, and
        - Stops if termination criteria is met.

        Args:
            initial_input (str, optional): If provided, this will be used as the first perception.
        """
        print(f"[bold green]{self.name} is online. Ask a question or type 'exit'.[/bold green]\n")
        iteration = 0

        while iteration < self.max_iterations:
            perception = initial_input or self.perceive()

            if perception == "exit":
                print(f"[bold red]{self.name}: Exiting.[/bold red]")
                break

            self.memory.add_entry("user_question", perception)
            decision = self.decide(perception)
            self.act(decision)

            if self.terminate_criteria and self.terminate_criteria(self.memory):
                print(f"[yellow]{self.name}: Termination condition met.[/yellow]")
                break

            iteration += 1
            time.sleep(0.5)

        print(f"\n[blue]{self.name}: Loop ended after {iteration} iteration(s).[/blue]")

# ----------- Tools -----------

def get_current_weather(location: str) -> dict:
    """Retrieves the current weather report for a specified location.

    Args:
        location (str): The name of the city for which to retrieve the weather report.

    Returns:
        dict: status and result or error msg.
    """
    if location.lower() == "new york":
        return {
            "status": "success",
            "result": "The weather in New York is sunny with a temperature of 25°C (77°F)."
        }
    return {
        "status": "error",
        "error_message": f"No weather data available for '{location}'."
    }

def get_current_time(location: str) -> dict:
    """Retrieves the current time for a specified location.

    Args:
        location (str): The name of the city for which to retrieve the weather report.

    Returns:
        dict: status and result or error msg.
    """
    if location.lower() == "new york":
        return {
            "status": "success",
            "result": "The current time in New York is 12:00 PM."
        }
    return {
        "status": "error",
        "error_message": f"No time data available for '{location}'."
    }

# ----------- Entry Point -----------

if __name__ == '__main__':
    def terminate_criteria(memory: Memory) -> bool:
        """
        Custom stopping logic: if the model output contains the word 'done', exit the loop.
        """
        output = memory.get_entry("model_output")
        return output and "done" in output.lower()

    agent = LoopAgent(
        model="models/gemini-1.5-flash-8b",
        name="ExampleLoopAgent",
        tools=[get_current_weather, get_current_time],
        max_iterations=3,
        terminate_criteria=terminate_criteria,
        system_instruction=(
            "You are a helpful assistant that can provide information about the weather and time of a given location. "
            "You can call tools or use the information in the context to answer the user's questions. "
            "Once you have the information, you can stop the conversation by saying 'done'."
            "Otherwise, you can keep asking questions until you get the information you need."
            "write the result in XML format."
        )
    )

    agent.run("What's the time and weather in New York?")

    # Display final model output (cleaned)
    final_output = agent.memory.get_entry("model_output")
    if final_output:
        print("\n[bold cyan]Final Output:[/bold cyan]")
        print(final_output.strip().replace("done", ""))