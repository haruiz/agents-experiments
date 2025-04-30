import time
from abc import abstractmethod
from dotenv import find_dotenv, load_dotenv
from google.genai import types
from modihub.llm import LLM

load_dotenv(find_dotenv()) # Loads API keys from .env file

class Agent:
    def __init__(self, name="Agent"):
        self.name = name
        self.state = {}  # Can store agent's memory or status

    def perceive(self):
        """Simulate perception: get input from the environment."""
        user_input = input(f"{self.name}: What is your command? (type 'exit' to stop) ")
        return user_input.strip().lower()

    @abstractmethod
    def decide(self, perception):
        """Decide based on perception. This should be overridden in subclasses."""
        raise NotImplementedError("Subclasses must implement this method.")

    def act(self, decision):
        """Perform action (in this case, print response)."""
        if decision:
            print(f"{self.name}: {decision}")

    def run(self):
        """Agentic loop: Perceive, Decide, Act"""
        print(f"{self.name} initialized. Type 'exit' to quit.")
        while True:
            perception = self.perceive()
            decision = self.decide(perception)
            if decision is None:  # Exit condition
                print(f"{self.name}: Shutting down.")
                break
            self.act(decision)
            time.sleep(0.5)  # Simulating processing time

class BasicAgent(Agent):
    def __init__(self, name="SimpleAgent"):
        super().__init__(name)

    def decide(self, perception):
        """Decide based on perception."""
        if perception == "exit":
            return None
        elif "weather" in perception:
            return "The weather is sunny."
        elif "time" in perception:
            return "The current time is 12:00 PM."
        else:
            return "I can only provide information about the weather and time."


class LLMAgent(Agent):
    def __init__(self, model: str, name=None, **kwargs):
        super().__init__(name)
        self.llm = LLM.create(model,system_instruction="format the output in XML format", **kwargs)

    @staticmethod
    def get_the_weather(location: str) -> dict:
        """Retrieves the current weather report for a specified location.

        Args:
            location (str): The name of the location for which to retrieve the weather report.

        Returns:
            dict: status and result or error msg.
        """
        if location.lower() == "new york":
            return {
                "status": "success",
                "report": (
                    "The weather in New York is sunny with a temperature of 25 degrees"
                    " Celsius (41 degrees Fahrenheit)."
                ),
            }
        else:
            return {
                "status": "error",
                "error_message": f"Weather information for '{location}' is not available.",
            }

    def decide(self, perception):
        """Decide based on perception."""
        return self.llm(perception, config=types.GenerateContentConfig(
            tools=[self.get_the_weather]
        ))




# Instantiate and run the agent
if __name__ == "__main__":
    # agent = BasicAgent(name="basic-agent")
    # agent.run()
    agent = LLMAgent(name="verbal-agent", model="models/gemini-1.5-flash-8b")
    agent.run()
