import os

import pytest

import debug.debugger
from core.client import Client, ClientOutputFormat
from core.tools_manager import ToolsManager

ollama_required = pytest.mark.skipif(
    "OLLAMA_RUNNING" not in os.environ and os.environ["OLLAMA_RUNNING"] == "1",
    reason="test requires OLLAMA_RUNNING environment variable to be set"
)

class ClientTestOutput(Client):
    def __init__(self):
        super().__init__(ClientOutputFormat.TEXT)
        self.output = ''
        self.input_to_return = ''

    def send_output(self, msg: str):
        self.output += msg

    def receive_input(self):
        return self.input_to_return

@pytest.fixture(scope='function')
def reset_restore_system_tools():
    # noinspection PyProtectedMember
    tools = ToolsManager._system_tools
    ToolsManager._system_tools = {}
    yield
    ToolsManager._system_tools = tools