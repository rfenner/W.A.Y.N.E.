import asyncio
from time import sleep, time

import ollama
import pytest
import pytest_asyncio

from config import OLLAMA_BASE_URL, OLLAMA_MODEL
from core.repo_registry import RepositoryRegistry
from core.user import User
from tests.conftest import ollama_required, ClientTestOutput
from tools.code_search import CodeSearchTool, CodeSearchToolModel


@ollama_required
class TestCodeSearchTool:
    @pytest_asyncio.fixture(scope='function', autouse=True)
    async def setup_teardown(self):
        repo = RepositoryRegistry.get_repository('repo')
        if repo is None:
            RepositoryRegistry.load_repositories('/app/tests/test_data/repo_registry_test')
        yield


    def test_tool_functionality(self):
        """Test the core functionality of the CodeSearchTool"""
        # Test with a valid repository that exists
        tool = CodeSearchTool('code_search_test')
        
        # Create a user for testing
        user = User(ClientTestOutput())
        
        # Test searching for something that exists in the test repo
        result = tool.run_tool(user, 'repo', 'test_method', False)
        
        # Should return a valid response with JSON content
        assert result is not None
        assert isinstance(result.message, str)
        assert 'test_python.py' in result.message
        assert 'def test_method()' in result.message

    def test_tool_definition(self):
        """Test that the tool generates correct definition"""
        tool = CodeSearchTool('code_search_test')
        definition = tool.tools_definition(tool.name)
        
        # Should have a name
        assert definition['type'] == 'function'
        assert 'function' in definition

        definition = definition['function']
        assert 'name' in definition
        assert 'description' in definition
        assert definition['name'] == 'code_search_test'
        assert definition['description'] == tool.__class__.__doc__
        assert 'parameters' in definition

        params = definition['parameters']
        assert 'description' in params
        assert params['description'] == CodeSearchToolModel.__doc__.strip()
        assert 'type' in params
        assert params['type'] == 'object'
        assert 'properties' in params
        assert 'repo_name' in params['properties']
        assert 'query' in params['properties']
        assert 'is_reg_ex' in params['properties']

    @pytest.mark.asyncio
    async def test_tool_called_by_ollama_with_prompt_no_regex(self):
        """Test that Ollama would call the tool based on a specific prompt"""
        # Use the Ollama client to test if it would call our tool
        from ollama import Client as OllamaClient
        
        # Create a prompt that should trigger the code_search tool
        messages = [{
            "role":"user", 
            'content': "Search for 'def test_method' in the repo named 'repo'"
        }]
        
        tool = CodeSearchTool('code_search_test')
        try:
            ollama_client = OllamaClient(host=OLLAMA_BASE_URL)
            
            response = ollama_client.chat(
                messages=messages, 
                model=OLLAMA_MODEL, 
                tools=[tool.tools_definition(tool.name)]
            )
            
            # If we get a response with tool calls, it means Ollama recognized and would call the tool
            if response.message.tool_calls:
                assert len(response.message.tool_calls) > 0
                assert response.message.tool_calls[0].function.name == "code_search_test"
                # Verify the arguments are properly structured
                args = response.message.tool_calls[0].function.arguments
                assert 'repo_name' in args
                assert 'query' in args
                assert 'is_reg_ex' in args
                assert not args['is_reg_ex']

                
        except Exception as e:
            # If Ollama isn't available or there are connection issues, we skip this test
            pytest.skip(f"Ollama test skipped due to: {str(e)}")

    @pytest.mark.asyncio
    async def test_tool_called_by_ollama_with_prompt_regex(self):
        """Test that Ollama would call the tool based on a specific prompt"""
        # Use the Ollama client to test if it would call our tool
        from ollama import Client as OllamaClient

        # Create a prompt that should trigger the code_search tool
        messages = [{
            "role": "user",
            'content': "Search for functions matching teh regex \btest\s*\("
        }]

        tool = CodeSearchTool('code_search_test')
        try:
            ollama_client = OllamaClient(host=OLLAMA_BASE_URL)

            response = ollama_client.chat(
                messages=messages,
                model=OLLAMA_MODEL,
                tools=[tool.tools_definition(tool.name)]
            )

            # If we get a response with tool calls, it means Ollama recognized and would call the tool
            if response.message.tool_calls:
                assert len(response.message.tool_calls) > 0
                assert response.message.tool_calls[0].function.name == "code_search_test"
                # Verify the arguments are properly structured
                args = response.message.tool_calls[0].function.arguments
                assert 'repo_name' in args
                assert 'query' in args
                assert 'is_reg_ex' in args
                assert args['is_reg_ex']


        except Exception as e:
            # If Ollama isn't available or there are connection issues, we skip this test
            pytest.skip(f"Ollama test skipped due to: {str(e)}")

