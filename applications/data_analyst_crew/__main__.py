import asyncio

from applications.data_analyst_crew.utils import  call_agent
from applications.data_analyst_crew.coder_agent import root_agent as coder_agent
from applications.data_analyst_crew.sql_agent import root_agent as sql_agent
from applications.data_analyst_crew.orchestrator_agent import root_agent as orchestrator_agent
if __name__ == '__main__':
    # Example usage
    try:
        user_prompt = "Write a python function to train a linear regression model using sklearn. The function should take in a dataset and return the trained model."
        print("Calling Coder Agent...")
        asyncio.run(call_agent(coder_agent, user_prompt))
        print("Calling SQL Agent...")
        user_prompt = "Write a SQL query to find the top 10 customers by total order amount from the orders table."
        asyncio.run(call_agent(sql_agent, user_prompt))

        print("Calling Orchestrator Agent...")
        user_prompt = (
            "Generate a report that includes the top 10 customers by total order amount and a summary of their orders."
        )
        asyncio.run(call_agent(orchestrator_agent, user_prompt))


    except Exception as e:
        print(f"Error calling Coder Agent: {e}")
