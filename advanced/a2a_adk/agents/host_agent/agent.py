from google.adk.agents.llm_agent import Agent
from google.adk.agents.remote_a2a_agent import AGENT_CARD_WELL_KNOWN_PATH
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent

from dotenv import load_dotenv

load_dotenv()

weather_agent = RemoteA2aAgent(
    name='weather_agent',
    description='An agent that provides weather information for a given location.',
    agent_card='http://localhost:8002' + AGENT_CARD_WELL_KNOWN_PATH,
)

maps_agent = RemoteA2aAgent(
    name='maps_agent',
    description='An agent that provides maps and location information.',
    agent_card='http://localhost:8001' + AGENT_CARD_WELL_KNOWN_PATH,
)

# maps_tool = AgentTool(agent=maps_agent)
# weather_tool = AgentTool(agent=weather_agent)

root_agent = Agent(
    model='gemini-2.5-flash',
    name='root_agent',
    description='A helpful assistant for user questions.',
    #tools=[maps_tool, weather_tool],
    instruction="""
    You are a helpful assistant that helps users with various questions.
    Your capabilities include:
    - Providing weather information using the Weather Agent tool.
    - Providing maps and location information using the Maps Agent tool.
    - Answering general knowledge questions.""",
    sub_agents=[weather_agent, maps_agent],
)
