import abc
import asyncio
import inspect
import json
import logging
import time
from abc import ABCMeta
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Union, Any, Callable, Literal

from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from fastmcp.client.elicitation import ElicitResult
from google.genai import types
from mcp import ClientSession, StdioServerParameters, Tool
from mcp import types as mcp_types
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.shared.context import RequestContext
from mcp.types import CallToolResult
from pydantic import BaseModel
from utils import mcp_tools_to_gemini

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class AsyncMessageBus:
    """A simple asynchronous message bus for event subscription and broadcasting."""
    def __init__(self):
        self._subscribers: List[Callable] = []

    def subscribe(self, callback: Callable):
        """Register a new subscriber."""
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable):
        """Unregister a subscriber."""
        self._subscribers.remove(callback)

    async def broadcast(self, *args: Any, **kwargs: Any):
        """Broadcast a message to all subscribers."""
        for callback in self._subscribers:
            # Case 1: async function
            if inspect.iscoroutinefunction(callback):
                return await callback(*args, **kwargs)

            # Case 2: class instance with async __call__
            elif callable(callback) and inspect.iscoroutinefunction(getattr(callback, "__call__", None)):
                return await callback(*args, **kwargs)

            # Case 3: sync callable — run in threadpool if needed
            elif callable(callback):
                result = callback(*args, **kwargs)
                if inspect.isawaitable(result):
                    return await result  # handles generators returning coroutines
            else:
                raise TypeError(f"Subscriber {callback} is not callable")



class ProgressUpdate(BaseModel): # No change, but moved for logical grouping
    """Represents a progress update."""
    progress: float
    total: float
    message: str
    percentage: float
    timestamp: datetime = datetime.now()


class ToolResult(BaseModel):
    """Represents the result of a task."""
    name: str
    result: Dict[str, Any] | str
    status: Literal["success", "failure"]
    progress_updates: Optional[List[ProgressUpdate]] = []
    duration: Optional[float]  = None  # Duration in seconds

class MCPClient(metaclass=ABCMeta):
    """
    Abstract Base Class for MCP clients, defining a common interface for connecting,
    executing tools, and managing the client lifecycle.
    """
    @abc.abstractmethod
    async def connect_to_server(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_tools(self) -> List[Tool]:
        raise NotImplementedError

    @abc.abstractmethod
    async def close(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def execute_tool(self, tool_name: str, tool_args: Dict[str, Any], progress_callback: Optional[Callable] = None) -> ToolResult:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_tools_for_gemini(self) -> List[types.Tool]:
        raise NotImplementedError

    @abc.abstractmethod
    def subscribe(self, callback):
        raise NotImplementedError

    @abc.abstractmethod
    def subscribe_elicitation(self, callback):
        raise NotImplementedError

    @abc.abstractmethod
    def subscribe_sampling(self, callback):
        raise NotImplementedError


class _BaseMCPClient(MCPClient, metaclass=ABCMeta):
    """
    Internal base class to handle common MCP client connection lifecycle logic,
    including task management and ready/shutdown events.
    """
    def __init__(self):
        # Async task that runs the client session loop
        self._client_task: Optional[asyncio.Task] = None
        # Event to signal when session is ready or has failed
        self._session_ready_event = asyncio.Event()
        # Event to trigger client shutdown
        self._shutdown_event = asyncio.Event()
        # MCP session
        self.session: Optional[ClientSession] = None
        # Status flags and exception tracking
        self._connected: bool = False
        self._startup_exception: Optional[Exception] = None

        self.reader: Optional[asyncio.StreamReader | MemoryObjectReceiveStream] = None
        self.writer: Optional[asyncio.StreamWriter | MemoryObjectSendStream] = None
        self.message_bus = AsyncMessageBus()
        self.elicitation_bus = AsyncMessageBus()
        self.sampling_bus = AsyncMessageBus()

    async def _internal_message_handler(self, message: Any):
        """Internal handler to broadcast messages to subscribers."""
        await self.message_bus.broadcast(message)

    async def _internal_elicitation_handler(self, context: RequestContext["ClientSession", Any],
                                  params: mcp_types.ElicitRequestParams) -> mcp_types.ElicitResult | mcp_types.ErrorData:
        """Internal handler to broadcast elicitation messages to subscribers."""
        return await self.elicitation_bus.broadcast(context, params)

    async def _internal_sampling_handler(self, context: RequestContext["ClientSession", Any],
                                  params: mcp_types.CreateMessageRequestParams) -> mcp_types.CreateMessageResult | mcp_types.ErrorData:
        """Internal handler to broadcast sampling messages to subscribers."""
        return await self.sampling_bus.broadcast(context, params)

    def subscribe(self, callback: Callable):
        self.message_bus.subscribe(callback)

    def subscribe_elicitation(self, callback: Callable):
        self.elicitation_bus.subscribe(callback)

    def subscribe_sampling(self, callback: Callable):
        self.sampling_bus.subscribe(callback)

    async def __aenter__(self):
        await self.connect_to_server()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def connect_to_server(self):
        """
        Starts the internal MCP client session task and waits for it to initialize.
        Raises exception if session setup fails.
        """
        if self._client_task:
            logger.warning("Client is already connected or connecting.")
            return

        self._startup_exception = None
        self._session_ready_event.clear()
        self._shutdown_event.clear()

        self._client_task = asyncio.create_task(self._run_client_session_wrapper())
        await self._session_ready_event.wait()

        if self._startup_exception:
            raise self._startup_exception

    async def _run_client_session_wrapper(self):
        """
        Wraps the main session runner to handle setup and teardown signals.
        """
        try:
            await self._run_session()
        except Exception as e:
            logger.exception("Failed to initialize or run MCP session.")
            self._startup_exception = e
        finally:
            self._connected = False
            self.session = None
            # Ensure ready event is set in case of failure during startup
            if not self._session_ready_event.is_set():
                self._session_ready_event.set()
            logger.info("Client session has been closed.")

    @abc.abstractmethod
    async def _run_session(self):
        """Subclasses must implement this to establish and manage the session."""
        raise NotImplementedError

    async def close(self):
        """
        Shuts down the MCP session and waits for the client task to complete.
        """
        if self._client_task and not self._client_task.done():
            self._shutdown_event.set()
            await self._client_task
            self._client_task = None
        logger.info("Client shutdown complete.")


    async def get_tools(self) -> List[Tool]:
        """
        Returns a list of available tools with their details from the connected MCP server.
        """
        if not self.session:
            raise RuntimeError("Session is not initialized. Call connect_to_server() first.")
        response = await self.session.list_tools()
        return response.tools

    async def get_tools_for_gemini(self) -> List[types.Tool]:
        """
        Converts MCP tools into Gemini-compatible Tool objects.
        """
        if not self.session:
            raise RuntimeError("Session is not initialized. Call connect_to_server() first.")

        mcp_tools_result = await self.session.list_tools()
        return mcp_tools_to_gemini(mcp_tools_result.tools)


class MCPStdioClient(_BaseMCPClient):
    """
    Handles the lifecycle and communication with a single MCP server over stdio.
    """
    def __init__(self,
                 server_params: Optional[StdioServerParameters] = None,
                 ):
        super().__init__()
        self._server_params = server_params


    async def execute_tool(self, tool_name: str, tool_args: Dict[str, Any], progress_callback: Optional[Callable] = None) -> ToolResult:

        """
        Executes a tool by name with the provided arguments.

        Args:
            tool_name (str): The name of the tool to execute.
            tool_args (Dict): Arguments to pass to the tool.
            progress_callback (Callable, optional): Callback function to handle progress updates.

        Returns:
            ToolResult: An object containing the result and metadata of the task execution.
        """
        if not self.session:
            raise RuntimeError("Session is not initialized. Call connect_to_server() first.")

        start_time = time.monotonic()
        try:
            response = await self.session.call_tool(
                tool_name,
                arguments={
                    **tool_args,
                    "meta": {
                        "data_format": "json"
                    }
                }
            )
            duration = time.monotonic() - start_time
            result_text = response.content[0].text
            return ToolResult(
                name=tool_name,
                result={"output": result_text},
                progress_updates=[],  # Stdio doesn't support progress
                duration=duration,
                status="success"

            )
        except Exception as e:
            logger.error(f"Failed to execute tool '{tool_name}': {e}")
            duration = time.monotonic() - start_time
            return ToolResult(
                name=tool_name,
                result=str(e),
                progress_updates=[],
                duration=duration,
                status="failure"
            )

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "MCPStdioClient":
        """
        Instantiate MCPClient from a dictionary with 'command', 'args', and optional 'env'.
        """
        command = config.get("command")
        if not command:
            raise ValueError("config for MCPStdioClient must include a 'command'.")
        args = config.get("args", [])
        env = config.get("env")
        return cls(StdioServerParameters(
            command=command,
            args=args,
            env=env
        ))

    async def _run_session(self):
        logger.info(f"MCPStdioClient session started with command: {self._server_params.command} {self._server_params.args}")
        """Main async task that handles connection, initialization, and lifecycle management."""
        async with stdio_client(self._server_params) as (reader, writer):
            self.reader = reader
            self.writer = writer

            async with ClientSession(
                    read_stream=reader,
                    write_stream=writer,
                    message_handler=self._internal_message_handler, # No elicitation/sampling for stdio
                    read_timeout_seconds=timedelta(seconds=3600)

            ) as session:
                await session.initialize()
                self.session = session
                self._connected = True
                self._session_ready_event.set()
                await self._shutdown_event.wait()


class MCPStreamableHttpClient(_BaseMCPClient):
    """MCP client with streaming capabilities."""

    def __init__(self,
                 server_url: str,
                 timeout: Optional[int] = 3600,
                 sse_read_timeout: Optional[int] = 3600
                 ):
        super().__init__()
        self._server_url = server_url
        self._sse_read_timeout = sse_read_timeout
        self._timeout = timeout
        self.reader: Optional[MemoryObjectReceiveStream] = None
        self.writer: Optional[MemoryObjectSendStream] = None


    async def _run_session(self):
        logger.info(f"Connecting to MCP server at {self._server_url} with timeout {self._timeout} and SSE read timeout {self._sse_read_timeout}")
        async with streamablehttp_client(
                self._server_url,
                timeout=self._timeout,
                sse_read_timeout=self._sse_read_timeout
            ) as (reader, writer, get_session_id):
                self.reader = reader
                self.writer = writer
                async with ClientSession(
                        read_stream=reader,
                        write_stream=writer,
                        message_handler=self._internal_message_handler,
                        elicitation_callback=self._internal_elicitation_handler,
                        sampling_callback=self._internal_sampling_handler,

                ) as session:
                    result = await session.initialize()
                    logger.info(f"Connected to: {result.serverInfo.name}")
                    logger.info(f"Protocol: {result.protocolVersion}")
                    current_session_id = get_session_id()
                    if current_session_id:
                        logger.info(f"Current session ID: {current_session_id}")

                    self.session = session
                    self._connected = True
                    self._session_ready_event.set()
                    await self._shutdown_event.wait()

    async def execute_tool(self, tool_name: str, tool_args: Dict[str, Any], progress_callback: Optional[Callable] = None) -> ToolResult:
        """
        Executes a tool by name with the provided arguments.

        Args:
            tool_name (str): The name of the tool to execute.
            tool_args (Dict): Arguments to pass to the tool.
            progress_callback (Callable, optional): Callback function to handle progress updates.

        Returns:
            ToolResult: An object containing the result and metadata of the task execution.
        """
        if not self.session:
            raise RuntimeError("Session is not initialized. Call connect_to_server() first.")
        start_time = time.monotonic()
        try:
            result = await self.session.call_tool(
                tool_name,
                arguments={
                    **tool_args
                },
                progress_callback=progress_callback
            )
            duration = time.monotonic() - start_time
            content = getattr(result, 'content', result)
            result_dict = self._process_tool_output(content)

            return ToolResult(
                name=tool_name,
                result=result_dict,
                progress_updates=getattr(progress_callback, 'progress_updates', []),
                duration=duration,
                status="success"
            )
        except Exception as e:
            logger.error(f"Failed to execute tool '{tool_name}': {e}")
            duration = time.monotonic() - start_time

            return ToolResult(
                name=tool_name,
                result=str(e),
                progress_updates=getattr(progress_callback, 'progress_updates', []),
                duration=duration,
                status="failure"
            )

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "MCPStreamableHttpClient":
        """
        Instantiate MCPClient from a dictionary with 'server_url', and optional 'timeout' and 'sse_read_timeout'.
        """
        server_url = config.get("url")
        if not server_url:
            raise ValueError("config for MCPStreamingClient must include a 'url'.")
        timeout = config.get("timeout")
        sse_read_timeout = config.get("sse_read_timeout")
        return cls(server_url, timeout=timeout, sse_read_timeout=sse_read_timeout)

    @staticmethod
    def _process_tool_output(content: Union[CallToolResult, Any]) -> Dict[str, Any]:
        """
        Processes the tool output to ensure it is a dictionary.
        If the output is a string, it attempts to parse it as JSON.
        If parsing fails or the result is not a dictionary, it wraps the content
        in a dictionary under the key 'output'.
        Args:
            content: The output from the tool execution.
        Returns:
            The processed output as a dictionary.
        """
        if isinstance(content, list):
            # This assumes content is a list of TextContent objects
            texts = [item.text for item in content if hasattr(item, 'text')]
            processed_content = '\n'.join(texts) if texts else str(content)
        else:
            processed_content = content

        if isinstance(processed_content, str):
            try:
                # Attempt to parse string as JSON
                parsed_json = json.loads(processed_content)
                if isinstance(parsed_json, dict):
                    return parsed_json
                # It's valid JSON, but not a dict (e.g., a list, number, or string)
                return {"output": parsed_json}
            except json.JSONDecodeError:
                # It's just a plain string
                return {"output": processed_content}

        if isinstance(processed_content, dict):
            return processed_content
        # For any other type (int, float, list from the start, etc.)
        return {"output": processed_content}


class MCPClientManager:
    """
    Manages multiple MCPClient instances and routes tool execution requests
    to the appropriate connected server that provides the desired tool.
    """

    def __init__(self, client_map: Dict[str, MCPClient]):
        self.clients: Dict[str, MCPClient] = client_map

        # tool_name → { server_name: str, client: MCPClient }
        self.tool_registry: Dict[str, Dict[str, Any]] = {}
        self.message_bus = AsyncMessageBus()
        self.elicitation_bus = AsyncMessageBus()
        self.sampling_bus = AsyncMessageBus()

    def __getitem__(self, tool_name: str) -> Dict[str, Any]:
        entry = self.tool_registry.get(tool_name)
        if not entry:
            raise KeyError(f"Tool '{tool_name}' not found in registry.")
        return entry

    @classmethod
    def from_json_config(cls, config_path: Union[str, Path]) -> "MCPClientManager":
        config = json.loads(Path(config_path).read_text())
        if not isinstance(config, dict):
            raise ValueError("Invalid config: expected a dictionary.")
        return cls.from_dict(config)

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "MCPClientManager":
        # check if config is None or and empty dictionary
        client_map = {}
        if config:
            if "mcpServers" not in config or not isinstance(config["mcpServers"], dict):
                raise ValueError("Invalid config: expected 'mcpServers' dictionary.")

            client_map = {
                server_name: MCPStreamableHttpClient.from_dict(server_config) if server_config.get("url")
                else MCPStdioClient.from_dict(server_config)
                for server_name, server_config in config["mcpServers"].items()
            }
        return cls(client_map)

    async def connect_all(self):
        async def connect_safe(server_name: str, client: MCPClient):
            try:
                await client.connect_to_server()
                # Subscribe the manager's bus to this client's messages
                client.subscribe(
                    lambda msg: asyncio.create_task(self.message_bus.broadcast(msg, server_name=server_name))
                )
                client.subscribe_elicitation(
                    lambda context, params: asyncio.create_task(self.elicitation_bus.broadcast(context, params, server_name=server_name))
                )
                client.subscribe_sampling(
                    lambda context, params: asyncio.create_task(self.sampling_bus.broadcast(context, params, server_name=server_name))
                )
                logger.info(f"Connected to server '{server_name}'")
            except Exception as e:
                logger.error(f"Failed to connect to server '{server_name}': {e}")

        await asyncio.gather(*[
            connect_safe(name, client) for name, client in self.clients.items()
        ])

        await self._build_tool_registry()

    def subscribe(self, callback: Callable):
        """Subscribe to messages from all managed clients."""
        self.message_bus.subscribe(callback)

    def subscribe_elicitation(self, callback: Callable):
        """Subscribe to elicitation requests from all managed clients."""
        self.elicitation_bus.subscribe(callback)

    def subscribe_sampling(self, callback: Callable):
        """Subscribe to sampling requests from all managed clients."""
        self.sampling_bus.subscribe(callback)

    async def _build_tool_registry(self):
        """
        Build a map of tool_name → { server_name, client }
        Only the first discovered instance per tool is used.
        """
        self.tool_registry.clear()

        for server_name, client in self.clients.items():
            try:
                tools = await client.get_tools()
                for tool in tools:
                    if tool.name not in self.tool_registry:
                        self.tool_registry[tool.name] = {
                            "server_name": server_name,
                            "client": client,
                            "meta": tool.meta
                        }
                        logger.debug(f"Registered tool '{tool.name}' on '{server_name}'")
            except Exception as e:
                logger.error(f"Failed to fetch tools from '{server_name}': {e}")

    async def has_tool(self, tool_name: str) -> bool:
        return tool_name in self.tool_registry

    async def get_all_available_tools(self) -> Dict[str, List[str]]:
        """
        Returns: Dict of server_name → list of available tool names.
        """
        listing: Dict[str, List[str]] = {}
        for server_name, client in self.clients.items():
            try:
                listing[server_name] = [tool.name for tool in await client.get_tools()]
            except Exception as e:
                logger.error(f"Failed to retrieve tools from '{server_name}': {e}")
                listing[server_name] = []
        return listing

    async def get_all_gemini_tools(self) -> List[types.Tool]:
        tools: List[types.Tool] = []
        for server_name, client in self.clients.items():
            try:
                tools.extend(await client.get_tools_for_gemini())
            except Exception as e:
                logger.error(f"Failed to fetch Gemini tools from '{server_name}': {e}")
        return tools

    async def execute_tool(self, tool_name: str, tool_args: Dict[str, Any] = None, progress_callback: Optional[Callable] = None) -> ToolResult:
        """
        Executes a tool and returns a structured TaskResult.
        """
        tool_entry = self.tool_registry.get(tool_name)
        if not tool_entry:
            return ToolResult(
                name=tool_name,
                result=f"Tool '{tool_name}' not found on any connected MCP server.",
                progress_updates=[],
                duration=0,
                status="failure"
            )

        server_name = tool_entry["server_name"]
        client = tool_entry["client"]

        try:
            # All clients now return a TaskResult, so we can just return it.
            return await client.execute_tool(
                tool_name, tool_args or {},
                progress_callback=progress_callback
            )
        except Exception as e:
            logger.error(f"Failed to execute tool '{tool_name}' on '{server_name}': {e}")
            return ToolResult(
                name=tool_name,
                result=str(e),
                progress_updates=[],
                duration=0,
                status="failure"
            )

    async def close_all(self):
        async def close_safe(server_name: str, client: MCPClient):
            try:
                await client.close()
                logger.info(f"Disconnected from server '{server_name}'")
            except Exception as e:
                logger.error(f"Failed to close server '{server_name}': {e}")

        await asyncio.gather(*[
            close_safe(name, client) for name, client in self.clients.items()
        ])


class ElicitationCallbackHandler:
    """Handles elicitation requests from MCP servers."""
    def __init__(self):
        ...

    async def __call__(self,
                       context: RequestContext["ClientSession", Any],
                       params: mcp_types.ElicitRequestParams,
                       server_name: str
                       ) -> mcp_types.ElicitResult | mcp_types.ErrorData:

        logger.info(f"Elicitation request from:  '{server_name}': {params}")
        return ElicitResult(
            action="accept",
            content={
                "confirm": True,
                "notes": "Auto-accepted by client"
            }
        )


class StreamingProgressHandler:
    """Handles streaming progress in a visual way."""

    def __init__(self):
        self.start_time = time.time()

    async def __call__(self, progress: float, total: float, message: str):
        percentage = (progress / total) * 100 if total > 0 else 0
        elapsed = time.time() - self.start_time
        logger.info(f"Progress: {percentage:.2f}% - {message} (Elapsed: {elapsed:.2f}s)")


async def get_mcp_tools(mcp_server_config_path: Union[Path, str]):
    """
    Placeholder for fetching MCP tools if needed.
    """
    try:
        mcp_manager = MCPClientManager.from_json_config(mcp_server_config_path)
        await mcp_manager.connect_all()
        tools = await mcp_manager.get_all_available_tools()
        logger.info(f"Available tools: {tools}")
        gemini_tools = await mcp_manager.get_all_gemini_tools()
        logger.info(f"Gemini-compatible tools: {gemini_tools}")

        function_name = "file_upload_simulation"
        progress_handler = StreamingProgressHandler()
        if await mcp_manager.has_tool(function_name):
            result = await mcp_manager.execute_tool(
                tool_name=function_name,
                tool_args={
                    "file_count": 5,
                },
                progress_callback=progress_handler
            )
            logger.info(f"Tool execution result: {result}")
        await mcp_manager.close_all()

        return tools
    except Exception as e:
        logger.error(f"Failed to connect to MCP server or retrieve tools: {e}")
        raise


if __name__ == '__main__':

    asyncio.run(get_mcp_tools("mcp_servers.json"))
