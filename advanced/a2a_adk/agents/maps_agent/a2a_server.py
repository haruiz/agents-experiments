from google.adk.a2a.utils.agent_to_a2a import to_a2a
from agent import  root_agent

# Make your agent A2A-compatible
a2a_app = to_a2a(root_agent, port=8001)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run("a2a_server:a2a_app", host="localhost", port=8001, reload=True, workers=1)