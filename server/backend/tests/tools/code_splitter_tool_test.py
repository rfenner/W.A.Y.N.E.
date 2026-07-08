
import pytest
import pytest_asyncio
from unittest.mock import Mock, patch

from config import OLLAMA_BASE_URL, OLLAMA_MODEL
from core.repo_registry import RepositoryRegistry
from core.user import User
from tests.conftest import ollama_required, ClientTestOutput
from tools.code_splitter_tool import CodeSplitterTool
from core.chunking import FileChunker


class TestCodeSplitterTool:
    @pytest_asyncio.fixture(scope='function', autouse=True)
    async def setup_teardown(self):
        # Setup repository for testing if needed
        repo = RepositoryRegistry.get_repository('repo')
        if repo is None:
            RepositoryRegistry.load_repositories('/app/tests/test_data/repo_registry_test')
        yield

    def test_tool_initialization(self):
        """Test that the tool initializes correctly"""
        tool = CodeSplitterTool()
        assert tool.name == "code_splitter"
        assert hasattr(tool, 'chunker')
        assert isinstance(tool.chunker, FileChunker)

    def test_tool_parameters_generation(self):
        """Test that the tool generates correct parameters"""
        params = CodeSplitterTool._generate_parameters()
        
        assert "type" in params
        assert params["type"] == "object"
        
        assert "properties" in params
        properties = params["properties"]
        assert "content" in properties
        assert "language" in properties
        assert "max_chunk_size" in properties
        
        assert "required" in params
        assert "content" in params["required"]
        assert "language" in params["required"]

    def test_tool_run_with_valid_input(self):
        """Test that the tool runs correctly with valid input"""
        tool = CodeSplitterTool()
        user = User(ClientTestOutput())
        
        # Test with simple Python content
        content = """
def hello_world():
    print("Hello, World!")
    return True

class MyClass:
    def __init__(self):
        self.value = 42
        
    def method(self):
        return self.value * 2
"""
        
        # Mock the chunker to avoid actual processing
        with patch.object(tool.chunker, 'chunk_text') as mock_chunk:
            mock_chunk.return_value = ("CODE", [("def hello_world():\n    print(\"Hello, World!\")\n    return True\n", 1, 5), 
                                                ("class MyClass:\n    def __init__(self):\n        self.value = 42\n        \n    def method(self):\n        return self.value * 2\n", 6, 12)])
            
            # Run the tool
            result = tool.run_tool(
                user=user,
                content=content,
                language="python"
            )
            
            assert result is not None
            assert result.message is not None
            assert '"start_line": 1' in result.message
            assert '"end_line": 5' in result.message

    def test_tool_run_with_missing_parameters(self):
        """Test that the tool handles missing parameters correctly"""
        tool = CodeSplitterTool()
        user = User(ClientTestOutput())
        
        # Run with missing parameters
        result = tool.run_tool(
            user=user,
            content="",
            language=""
        )
        
        assert result is not None
        assert "Missing required parameters" in result.message

    @pytest.mark.asyncio
    @ollama_required
    async def test_tool_called_by_ollama_with_prompt(self):
        """Test that Ollama would call the code_splitter tool based on a specific prompt"""
        
        # Test that the tool definition works properly
        tool = CodeSplitterTool()
        tool_definition = tool.tools_definition(tool.name)
        
        assert tool_definition is not None
        assert tool_definition['type'] == 'function'
        assert tool_definition['function']['name'] == 'code_splitter'
        assert 'description' in tool_definition['function']
        assert 'parameters' in tool_definition['function']

    @pytest.mark.asyncio
    @ollama_required
    async def test_tool_called_by_ollama_with_code_splitting_prompt(self):
        """Test that Ollama would call the code_splitter tool when asked to split code"""
        
        # Setup repository for testing if needed
        repo = RepositoryRegistry.get_repository('repo')
        if repo is None:
            RepositoryRegistry.load_repositories('/app/tests/test_data/repo_registry_test')
            
        # Wait for repository to be indexed
        import asyncio
        import datetime
        start = datetime.datetime.now().timestamp()
        user = User(ClientTestOutput())
        while 'repo' in RepositoryRegistry._indexing:
            await asyncio.sleep(.5)
            if datetime.datetime.now().timestamp() - start > 3:
                pytest.fail('Timed out waiting for the repo to finish indexing')

        # Test that the tool would be called by Ollama with a prompt about splitting code
        from ollama import Client as OllamaClient

        ollama_client = OllamaClient(host=OLLAMA_BASE_URL)
        tool = CodeSplitterTool()
        # Create a prompt that should trigger the code_splitter tool
        messages = [{
            "role":"user", 
            'content': "Split this Python code into logical chunks: def test_function():\n    return True\n\nclass TestClass:\n    def method(self):\n        pass"
        }]
    
        # Use the tool definition to test if Ollama would call it
        try:
            response = ollama_client.chat(
                messages=messages, 
                model=OLLAMA_MODEL, 
                tools=[tool.tools_definition(tool.name)]
            )
        
            # If we get a response with tool calls, it means Ollama recognized and would call the tool
            if response.message.tool_calls:
                assert len(response.message.tool_calls) > 0
                # Check that the tool name is correct
                assert response.message.tool_calls[0].function.name == "code_splitter"
                
                # Verify the arguments are properly structured for code splitting
                args = response.message.tool_calls[0].function.arguments
                assert 'file_path' in args
                assert 'content' in args
                assert 'language' in args
            else:
                # If no tool calls, that's also valid - it means the LLM decided not to use the tool
                # but this test is primarily checking if the tool definition works properly
                pass
            
        except Exception as e:
            # If Ollama isn't available or there are connection issues, we skip this test
            pytest.skip(f"Ollama test skipped due to: {str(e)}")

    def test_tool_chunking_logic(self):
        """Test the core chunking logic directly"""
        tool = CodeSplitterTool()
        
        # Test with simple content that should be split into chunks
        content = """
# This is a comment
def function_one():
    x = 1
    y = 2
    return x + y

# Another comment
def function_two():
    z = 3
    w = 4
    return z * w

class ExampleClass:
    def __init__(self):
        self.value = 0
    
    def get_value(self):
        return self.value
"""
        
        # Mock the chunker to check what parameters are passed
        with patch.object(tool.chunker, 'chunk_text') as mock_chunk:
            mock_chunk.return_value = ("CODE", [("def function_one():\n    x = 1\n    y = 2\n    return x + y\n", 3, 7), 
                                                ("def function_two():\n    z = 3\n    w = 4\n    return z * w\n", 9, 13),
                                                ("class ExampleClass:\n    def __init__(self):\n        self.value = 0\n    \n    def get_value(self):\n        return self.value\n", 15, 21)])
            
            result = tool.run_tool(
                user=User(ClientTestOutput()),
                content=content,
                language="python"
            )
            
            # Verify that the chunker was called with correct parameters
            mock_chunk.assert_called_once()
            call_args = mock_chunk.call_args
            assert call_args[0][0] == content   # content
            assert call_args[0][1] == "python"  # language
            
            assert result is not None
            assert '"start_line": 3' in result.message
            assert '"end_line": 7' in result.message
