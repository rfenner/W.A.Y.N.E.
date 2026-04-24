import json
from time import sleep, time

import ollama
import pytest
import pytest_asyncio

from config import OLLAMA_BASE_URL, OLLAMA_MODEL
from core.repo_registry import RepositoryRegistry
from tests.conftest import ollama_required
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
        while 'repo' in RepositoryRegistry._indexing:
            sleep(.5)
            if time() - start > 3:
                pytest.fail('Timed out waiting for the repo to finish indexing')

        ollama_client = ollama.Client(host=OLLAMA_BASE_URL)

        messages = [{
            "role":"user", 'content': "find the file that test_method is defined in repository named repo"
        }]
        tool = CodeSearchTool()
        response = ollama_client.chat(messages=messages, model=OLLAMA_MODEL, tools=[tool.run_tool])
        assert response.message.tool_calls is not None
        tool_result = tool.run_tool(**response.message.tool_calls[0].function.arguments)

        expected_file_path = '/app/tests/test_data/repo_registry_test/repo/test_python.py'
        assert len(tool_result) == 1
        assert tool_result[0]['file_path'] == expected_file_path
        assert tool_result[0]['line'] == 'def test_method():\n'
        assert tool_result[0]['line_number'] == 1

        messages.append({
            'role':'tool',
            'tool_name':'run_tool',
            'content':json.dumps(tool_result[0])
        })

        response = ollama_client.chat(messages=messages, model=OLLAMA_MODEL, tools=[tool.run_tool])
        assert expected_file_path in response.message.content
        assert 'line 1' in response.message.content

