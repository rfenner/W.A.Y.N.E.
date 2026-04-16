import asyncio
from enum import Enum
from typing import Any

from starlette.websockets import WebSocket

from agent.chat_history import ChatHistory
from agent.executor import Executor
from agent.planner import Planner
from agent.verifier import Verifier
from core.repo_registry import Repository

class ClientOutputFormat(Enum):
    HTML = "html"
    TEXT = "text"

class Client:
    def __init__(self, ws: WebSocket):
        self.ws: WebSocket = ws
        self._client_output = ws.query_params.get('co', 'html')
        self._planner: Planner = Planner(self)
        self._executor = Executor(self)
        self._verifier = Verifier()
        self._active_repository: Repository | None = None
        self._general_chat_history: ChatHistory = ChatHistory('./')
        self._repo_agents: dict[str, dict[str,Any]] = {}
        self.queue: asyncio.Queue = asyncio.Queue()
        self.queue_task = asyncio.create_task(self._send_queue())

    @property
    def websocket(self) -> WebSocket:
        return self.ws

    @property
    def repo(self):
        return self._active_repository

    @property
    def chat_history(self):
        if self._active_repository is None:
            return self._general_chat_history
        return self._repo_agents[self._active_repository.name_key]['history']

    @property
    def editor(self):
        if self._active_repository is not None:
            return self._repo_agents[self._active_repository.name_key]['editor']
        return None

    @property
    def output_format(self):
        return self._client_output

    @property
    def is_html_format(self):
        return self._client_output == ClientOutputFormat.HTML

    @property
    def is_text_format(self):
        return self._client_output == ClientOutputFormat.TEXT

    async def _send_queue(self):
        while True:
            message = await self.queue.get()
            await self.ws.v(message)
            self.queue.task_done()


    def send_output(self, msg: str):
        self.queue.put_nowait(msg)

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
        query = await self.ws.receive_text()

        self.send_output("\n[PLANNING]...")
        plan = self._planner.create_plan(query)

        self.send_output("\n[EXECUTING]...")
        results = self._executor.execute_plan(plan)

        self.send_output("\n[VERIFYING]...")
        status = self._verifier.verify(query, results)

        # Display results - FULL OUTPUT, NO TRUNCATION
        self.send_output("\n" + "=" * 60)
        for res in results:
            # Special handling for edit_file results
            if res.get("tool") == "edit_file":
                edit_result = res.get("result", {})
                if edit_result.get("success"):
                    self.send_output("\n[EDIT PREVIEW]")
                    self.send_output(f"File: {edit_result.get('file_path')}")
                    self.send_output(f"Summary: {edit_result.get('summary')}")
                    self.send_output("\n--- Diff ---")
                    self.send_output(edit_result.get('diff', '[No diff]'))
                    self.send_output("--- End Diff ---\n")
                else:
                    self.send_output(f"❌ Edit failed: {edit_result.get('error', 'Unknown error')}")
            else:
                self._print_result(res)

        self.send_output("=" * 60)
        self.send_output(
            f"Status: {'✅ ACCEPT' if status == 'accept' else '⚠️  RETRY' if status == 'retry' else '❌ ABORT'}\n")

        # Check for pending edit and ask for confirmation
        edit_info = None
        if self._executor.has_pending_edit():
            edit_info = self._executor.get_pending_edit_info()
            confirm = input("Apply this edit? [y/n]: ").strip().lower()
            if confirm == 'y':
                apply_result = self._executor._apply_edit_tool(confirm=True)
                if apply_result.get("success"):
                    self.send_output(f"\n{apply_result.get('message')}")
                else:
                    self.send_output(f"\n❌ {apply_result.get('message')}")
            else:
                self._executor._apply_edit_tool(confirm=False)
                edit_info = None  # Don't log cancelled edits as "edited"
                self.send_output("\n❌ Edit cancelled.")

        # Log turn to history
        last_action = results[-1].get("tool", "unknown") if results else "none"
        self.chat_history.add_turn(query, last_action, edit_info)


