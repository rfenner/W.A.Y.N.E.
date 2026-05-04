from typing import Any

from agent.executor import Executor
from agent.planner import Planner
from agent.verifier import Verifier
from core.client import Client
from core.repo_registry import Repository
from core.tools_manager import ToolsManager
from llm.local_llm_client import LocalLLMClient


class User:
    def __init__(self, client: Client):
        """The output client, typically a WSClient"""
        self._client: Client = client
        self._planner: Planner = Planner(self)
        self._executor = Executor(self)
        self._verifier = Verifier()
        """The active repository that we are answering questions on"""
        self._active_repository: Repository | None = None
        """General chat history not tied to a repository"""
        self._chat_history: list =[]
        """Chat history tied to a specific repository"""
        self._repo_agents: dict[str, dict[str, Any]] = {}
        """The llm client that handles send/receive messages from the llm"""
        self._llm_client = LocalLLMClient()
        self._tool_manager = ToolsManager()
        """The tools we need to run for the llm. We store them since a tool may
            go interactive and need to loop several times on user input"""
        self.__llm_tool_calls = []

    @property
    def client(self) -> Client:
        return self._client

    @property
    def repo(self):
        return self._active_repository

    @property
    def chat_history(self):
        if self._active_repository is None:
            return self._chat_history
        return self._repo_agents[self._active_repository.name_key]['history']

    @property
    def editor(self):
        if self._active_repository is not None:
            return self._repo_agents[self._active_repository.name_key]['editor']
        return None

    @property
    def llm_client(self):
        return self._llm_client

    def send_output(self, msg: str):
        """
        Sends output to the client
        """
        self._client.send_output(msg)

    def _print_result(self, res: dict, max_chars: int = None):
        """Pretty print a result, with optional truncation."""
        tool = res.get("tool", "unknown")

        if "error" in res:
            print(f"❌ {tool}: {res['error']}")
            return

        result = res.get("result")

        # Skip printing llm_analysis as it's already streamed during planning
        if tool == "llm_analysis":
            return

        # Show full result without truncation for important tools
        if tool in ["report"]:
            if isinstance(result, str):
                self.send_output(result)
            else:
                import json
                self.send_output(json.dumps(result, indent=2))
        else:
            # For other tools, show snippet
            if isinstance(result, str):
                display = result if not max_chars else result[:max_chars]
                self.send_output(display)
                if max_chars and len(result) > max_chars:
                    self.send_output(f"\n... [output truncated, total length: {len(result)} chars]")
            else:
                import json
                output = json.dumps(result, indent=2)
                display = output if not max_chars else output[:max_chars]
                self.send_output(display)
                if max_chars and len(output) > max_chars:
                    self.send_output(f"\n... [output truncated]")

    async def receive_query(self):
        query = await self._client.receive_input()

        # a tool is in control of the user input so continue with it
        if self._tool_manager.is_tool_in_control:
            tool_response = self._tool_manager.continue_tool(self, query)
            if tool_response is not None:
                self.chat_history.append(tool_response)
        else:
            if not self.__llm_tool_calls:
                self.__llm_tool_calls = self.llm_client.chat(self, query)
            while self.__llm_tool_calls:
                tool = self.__llm_tool_calls.pop(0)
                tool_response = self._tool_manager.run_tool_call(self, tool.function.name, tool.function.arguments)
                if tool_response is not None:
                    self.chat_history.append(tool_response)
                # If a tool went interactive we return so it can take control
                # when it's done we'll continue to process the other tools
                if self._tool_manager.is_tool_in_control:
                    return

