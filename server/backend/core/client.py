from typing import Any

from starlette.websockets import WebSocket

from agent.chat_history import ChatHistory
from agent.executor import Executor
from agent.planner import Planner
from agent.verifier import Verifier
from core.repo_registry import Repository


class Client:
    def __init__(self, ws: WebSocket):
        self.ws: WebSocket = ws
        self._planner: Planner = Planner(self)
        self._executor = Executor(self)
        self._verifier = Verifier()
        self._active_repository: Repository | None = None
        self._general_chat_history: ChatHistory = ChatHistory('./')
        self._repo_agents: dict[str, dict[str,Any]] = {}

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
    async def run(self):
        pass

    async def send_text(self, msg: str):
        pass

    def _print_result(res: dict, max_chars: int = None):
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
                print(result)
            else:
                import json
                print(json.dumps(result, indent=2))
        else:
            # For other tools, show snippet
            if isinstance(result, str):
                display = result if not max_chars else result[:max_chars]
                print(display)
                if max_chars and len(result) > max_chars:
                    print(f"\n... [output truncated, total length: {len(result)} chars]")
            else:
                import json
                output = json.dumps(result, indent=2)
                display = output if not max_chars else output[:max_chars]
                print(display)
                if max_chars and len(output) > max_chars:
                    print(f"\n... [output truncated]")

    async def receive_query(self):
        query = await self.ws.receive_text()

        await self.send_text("\n[PLANNING]...")
        plan = self._planner.create_plan(query)

        await self.send_text("\n[EXECUTING]...")
        results = self._executor.execute_plan(plan)

        print("\n[VERIFYING]...")
        status = self._verifier.verify(query, results)

        # Display results - FULL OUTPUT, NO TRUNCATION
        await self.send_text("\n" + "=" * 60)
        for res in results:
            # Special handling for edit_file results
            if res.get("tool") == "edit_file":
                edit_result = res.get("result", {})
                if edit_result.get("success"):
                    await self.send_text("\n[EDIT PREVIEW]")
                    await self.send_text(f"File: {edit_result.get('file_path')}")
                    await self.send_text(f"Summary: {edit_result.get('summary')}")
                    await self.send_text("\n--- Diff ---")
                    await self.send_text(edit_result.get('diff', '[No diff]'))
                    await self.send_text("--- End Diff ---\n")
                else:
                    await self.send_text(f"❌ Edit failed: {edit_result.get('error', 'Unknown error')}")
            else:
                self._print_result(res)

        await self.send_text("=" * 60)
        await self.send_text(
            f"Status: {'✅ ACCEPT' if status == 'accept' else '⚠️  RETRY' if status == 'retry' else '❌ ABORT'}\n")

        # Check for pending edit and ask for confirmation
        edit_info = None
        if self._executor.has_pending_edit():
            edit_info = self._executor.get_pending_edit_info()
            confirm = input("Apply this edit? [y/n]: ").strip().lower()
            if confirm == 'y':
                apply_result = self._executor._apply_edit_tool(confirm=True)
                if apply_result.get("success"):
                    await self.send_text(f"\n{apply_result.get('message')}")
                else:
                    await self.send_text(f"\n❌ {apply_result.get('message')}")
            else:
                self._executor._apply_edit_tool(confirm=False)
                edit_info = None  # Don't log cancelled edits as "edited"
                await self.send_text("\n❌ Edit cancelled.")

        # Log turn to history
        last_action = results[-1].get("tool", "unknown") if results else "none"
        self.chat_history.add_turn(query, last_action, edit_info)
