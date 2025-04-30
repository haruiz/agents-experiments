# Agent Experiments

This repository provides a curated collection of practical examples showcasing a variety of agent design patterns and applications. It includes hands-on demonstrations for building and orchestrating multi-agent systems using leading frameworks such as Google’s Agent Development Kit (ADK), LangGraph, CrewAI, AutoGen and others. 

## Overview

The repository is organized into three main sections:

1. **`frameworks/`**  
   Demonstrates how to implement key agent design patterns using ADK and other popular frameworks. These examples focus on reusable architectural concepts such as chaining, tool use, and agent collaboration.

2. **`applications/`**  
   Contains more advanced, real-world scenarios—such as an agent querying a database using natural language—that illustrate how to integrate agent capabilities into full applications.

3. **`foundations/`**  
   Covers fundamental agent concepts, including perceive-decide-act loops, memory management, and system instructions. These demos often use lightweight or custom agent implementations to highlight core principles without added framework complexity.


## Demos Included

Here's a breakdown of the patterns and concepts illustrated in the demos:

**`frameworks/`**

**`adk-demos/effective-patterns`**


  *   **`evaluator-optimizer`**: Implements an iterative refinement loop. One agent generates content (e.g., code), another evaluates it against criteria, and a control mechanism determines if the loop should terminate based on the evaluation. Uses LLM-based agents within a looping structure.
  *   **`prompt_chaining`**: Shows a sequential workflow (prompt chaining) where the output of one agent step feeds into the next (e.g., joke generation -> improvement -> publishing). Includes an example of intercepting LLM calls for guardrails. Implemented using sequential execution of LLM agents.
  *   **`orchestrator-worker`**: Illustrates a central orchestrator coordinating multiple worker agents (e.g., generating jokes, songs, poems based on a topic). The orchestrator (often a loop) continues until a completion condition is met (e.g., all workers have produced output). Implemented using a looping agent managing multiple LLM-based worker agents and a condition-checking agent.
  *   **`parallelization`**: Demonstrates running multiple agents concurrently (e.g., joke, song, poem generators) based on the same initial input. A subsequent agent step merges the parallel outputs into a structured response. Implemented using parallel execution constructs followed by a merging agent.
  *   **`routing`**: Shows an agent acting as a router, analyzing user input to determine the user's intent and delegating the task to the appropriate specialized sub-agent (e.g., joke, song, or poem generator). Implemented using an LLM agent configured with multiple sub-agents it can choose from.

**`adk-demos/basic-*`**

*   **`basic-loop-agent`**: A simple writer-critic cycle implemented within a loop. One LLM agent writes content, another critiques it, iterating for a fixed number of times.
*   **`basic-multitool-agent`**: A single agent equipped with multiple distinct Python functions as tools (e.g., `get_weather`, `get_current_time`). The agent uses an LLM to decide which tool (if any) to call based on the user query to fulfill the request.
*   **`basic-multiagent-demo`**: A straightforward sequential pipeline where agents execute in order: Code Writer -> Code Reviewer -> Code Refactorer. Each step uses the output of the previous one.

**`applications/`**

*   **`db-agent`**: An agent designed to interact with a SQL database based on natural language queries. It includes:
    *   Tools (Python functions) to fetch the database schema and execute SQL queries.
    *   A multistep pipeline where one agent drafts a SQL query based on the user request and schema, and another agent potentially validates and executes it.
    *   Illustrates combining LLM reasoning with external tool execution for data retrieval.

**`foundations/`**

*   **`simple_agent.py`**: Basic implementation of an agent structure with `perceive`, `decide`, `act` methods, showing both simple rule-based logic and an LLM-powered decision-making process.
*   **`memory.py`**: A simple class structure for managing agent state or conversation history in memory, organized into sections.
*   **`full_agent.py` / `full_agent_.py`**: More complete examples implementing an agentic loop (perceive-decide-act). These integrate memory, external tools (like weather/time functions), LLM calls (Gemini) for decision making, and criteria for loop termination, demonstrating the core cycle of an autonomous agent.

## Prerequisites

*   Python 3.10+
*   Access to Google AI Studio and a Gemini API Key (for demos using Google Gemini).
*   `uv` for manage the demos dependencies and environment.
*   Git (for cloning the repository).
*   (For `db-agent`) A SQLite database file (e.g., `chinook.db`) is required.
    *   You can download it from various sources online. For the `db-agent` demo, the database used was 'northwind.db' that you can find at https://github.com/jpwhite3/northwind-SQLite3. Make sure to update the path in the `.env` file accordingly.

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd agents-experiments
    uv sync
    ```
2. **Configure environment variables for the demos:**
- Each demo folder inside the `adk-demos` directory should include its own `.env` file. 
- The `.env` file should contain the necessary environment variables.
    ```dotenv
    GOOGLE_GENAI_USE_VERTEXAI=FALSE
    GOOGLE_API_KEY="YOUR_API_KEY_HERE"
    DB_PATH="YOUR DB_PATH_HERE" # if required
    ```

## Running the Demos

Each demo can typically be run by executing its main Python script (often `agent.py`) from the root directory:

```bash
# Example: Running the Routing demo
python frameworks/effective-patterns/routing/agent.py
```

You can also use the  adk-demos CLI to run the Web UI:

```bash
cd frameworks/effective-patterns
adk web
```

## Key Agent Concepts Illustrated

*   **Agent Types**: LLM-powered agents, Tool-using agents, Agents with custom logic.
*   **Agent Composition**: Building complex behaviors by combining agents (Sequentially, Looping structures, Parallel execution).
*   **State Management**: Passing information and context between different agents or steps, often using a shared session state.
*   **Tool Use**: Enhancing agent capabilities by allowing them to call external functions (Python code) to fetch data or perform actions.
*   **Control Flow**: Implementing logic for how agents interact, including routing decisions based on input, iterative refinement, and termination conditions.
*   **Callbacks/Hooks**: Intercepting agent execution steps for purposes like logging, input/output validation, or implementing guardrails.
*   **Perceive-Decide-Act Cycle**: The fundamental loop demonstrated in foundation examples where an agent takes input, reasons about it (often with an LLM), and performs an action.
*   **Memory**: Storing conversation history, intermediate results, or contextual information for agents to use in their reasoning process.

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs, improvements, or new demo ideas illustrating different agent patterns or concepts.

## Acknowledgments

✨ Google ML Developer Programs and Google Developers Program supported this work by providing Google Cloud and Gemini API Credits ✨


