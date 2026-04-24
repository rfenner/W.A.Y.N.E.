import os

import pytest

import debug.debugger
from core.client import Client, ClientOutputFormat

ollama_required = pytest.mark.skipif(
    "OLLAMA_RUNNING" not in os.environ and os.environ["OLLAMA_RUNNING"] == "1",
    reason="test requires OLLAMA_RUNNING environment variable to be set"
)

class ClientTestOutput(Client):
    def __init__(self):
        super().__init__(ClientOutputFormat.TEXT)
        self.output = ''

    def send_output(self, msg: str):
        self.output += msg

