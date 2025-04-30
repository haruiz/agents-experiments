import time
from dotenv import load_dotenv, find_dotenv
from google.genai import types
from google import genai
import os
from memory import Memory
from rich import print

load_dotenv(find_dotenv()) # Loads API keys from .env file

class LoopAgent:
    def __init__(
        self,
        model: str,
        name: str = "LoopAgent",
        max_iterations: int = 5,
        system_instruction: str = None,
        tools: list = None,
        terminate_criteria=None,
        **kwargs
    ):
        self.name = name
        self.memory = Memory()
        self.max_iterations = max_iterations
        self.terminate_criteria = terminate_criteria
        self.tools = tools or []
        self.model = model
        self.system_instruction = system_instruction
        self.llm_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

        self.memory.add_entry(
            "system_instruction",
            self.system_instruction
        )


    def perceive(self):
        user_input = input(f"{self.name}: What would you like to know? (type 'exit' to quit)\n> ")
        return user_input.strip().lower()

    def decide(self):
        """
        The agent decides what to do based on the current memory and the system instruction.
        :return:
        """
        return self.llm_client.models.generate_content(
            contents=str(self.memory),
            model=self.model,
            config=types.GenerateContentConfig(
                tools=self.tools,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True
                )
            )
        )

    def act(self, function_name: str, arguments: dict):
        # agents use tools to act and collect data from the environment
        try:
            return globals()[function_name](**arguments)
        except Exception as e:
            return {
                "status": "error",
                "error_message": f"Error executing function '{function_name}': {str(e)}"
            }


    def run(self, use_query=None):
        print(f"{self.name} is online. You can ask questions or type 'exit'.\n")
        iteration = 0
        while iteration < self.max_iterations:
            perception = use_query or self.perceive()

            if perception == "exit":
                print(f"{self.name}: Exiting.")
                break

            self.memory.add_entry("user_question",perception)

            decision = self.decide()
            # if the model attempts to call a function is because it requests information from the environment
            # otherwise we just append the output to the conversation
            if decision.function_calls:
                for function_call in decision.function_calls:
                    function_output = self.act(function_call.name, function_call.args)
                    # we can add error handling here
                    self.memory.add_entry(
                        "context",
                        function_output["result"]
                    )
            else:
                self.memory.add_entry(
                    "model_output",
                    decision.text
                )

            if self.terminate_criteria and self.terminate_criteria(self.memory):
                print(f"{self.name}: Termination condition met.")
                break

            iteration += 1
            time.sleep(0.5)

        print(f"{self.name}: Loop ended after {iteration} iteration(s).")

def get_current_weather(location: str) -> dict:
    """Retrieves the current weather report for a specified location.

    Args:
        location (str): The name of the location for which to retrieve the weather report.

    Returns:
        dict: status and result or error msg.
    """
    if location.lower() == "new york":
        return {
            "status": "success",
            "result": (
                "The weather in New York is sunny with a temperature of 25 degrees"
                " Celsius (41 degrees Fahrenheit)."
            ),
        }
    else:
        return {
            "status": "error",
            "error_message": f"Weather information for '{location}' is not available.",
        }

def get_current_time(location: str) -> dict:
    """Retrieves the current time for a specified location.

    Args:
        location (str): The name of the location for which to retrieve the current time.

    Returns:
        dict: status and result or error msg.
    """
    if location.lower() == "new york":
        return {
            "status": "success",
            "result": (
                "The current time in New York is 12:00 PM."
            ),
        }
    else:
        return {
            "status": "error",
            "error_message": f"Time information for '{location}' is not available.",
        }



if __name__ == '__main__':
    def terminate_criteria(memory):
        memory_entry = memory.get_entry("model_output")
        return memory_entry and "done" in memory_entry.lower()

    # Example usage of LoopAgent
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
        )
    )
    agent.run("What's the time and weather in New York?")
    print(agent.memory.get_entry("model_output").strip().replace("\n", "").replace("done", ""))