import json
from time import sleep, time

import ollama
import pytest
import pytest_asyncio

from config import OLLAMA_BASE_URL, OLLAMA_MODEL
from core.repo_registry import RepositoryRegistry
from core.user import User
from tests.conftest import ollama_required, ClientTestOutput
from tools.code_search import CodeSearchTool

@ollama_required
class TestCodeSearchTool:
    @pytest_asyncio.fixture(scope='function', autouse=True)
    async def setup_teardown(self):
        repo = RepositoryRegistry.get_repository('repo')
        if repo is None:
            RepositoryRegistry.load_repositories('/app/tests/test_data/repo_registry_test')
        yield

    @pytest.mark.asyncio
    async def test_tools_runs(self):
        start = time()
        user = User(ClientTestOutput())
        while 'repo' in RepositoryRegistry._indexing:
            sleep(.5)
            if time() - start > 3:
                pytest.fail('Timed out waiting for the repo to finish indexing')

        ollama_client = ollama.Client(host=OLLAMA_BASE_URL)

        messages = [{
            "role":"user", 'content': "find the file and line number that test_method is defined in for the repository named repo"
        }]
        tool = CodeSearchTool('test')
        response = ollama_client.chat(messages=messages, model=OLLAMA_MODEL, tools=[tool.tools_definition(tool.name)])
        assert response.message.tool_calls is not None
        tool_result = tool.run_tool(user, **response.message.tool_calls[0].function.arguments)

        expected_file_path = '/app/tests/test_data/repo_registry_test/repo/test_python.py'
        assert tool_result.message == '[{"file_path": "'+expected_file_path+'", "line_number": 1, "line": "def test_method():\\n"}]'

        messages.append({
            'role':'tool',
            'tool_name':'run_tool',
            'content':tool_result.message
        })

        response = ollama_client.chat(messages=messages, model=OLLAMA_MODEL, tools=[tool.tools_definition(tool.name)],
                                      options={'temperature':0.0})
        assert expected_file_path in response.message.content
        assert 'line number 1' in response.message.content
        assert 'test_method' in response.message.content

