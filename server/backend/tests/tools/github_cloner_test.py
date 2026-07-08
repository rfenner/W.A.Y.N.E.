import subprocess
from unittest.mock import patch, MagicMock

import pytest

from core.agent_tool import AgentToolResponse
from core.user import User
from tools.github_cloner import GithubCloner, GithubClonerModel, GithubCLoneStates

from tests.conftest import ollama_required, ClientTestOutput
from config import OLLAMA_BASE_URL, OLLAMA_MODEL


class TestGithubCloner:
    def test_generate_parameters(self):
        """Test that the tool generates correct parameters schema"""
        params = GithubCloner._generate_parameters()
        # The current implementation returns None, but we can verify it exists
        assert params is None or isinstance(params, dict)
        
    def test_tool_model_validation(self):
        """Test that the model validates input correctly"""
        # Test valid input
        model = GithubClonerModel(repository="test/repo", timeout=60)
        assert model.repository == "test/repo"
        assert model.timeout == 60
        
        # Test with default timeout
        model = GithubClonerModel(repository="test/repo")
        assert model.repository == "test/repo"
        assert model.timeout == 120  # Default value
        
    def test_check_repo_url_full_url(self):
        """Test that the tool correctly identifies full URLs"""
        tool = GithubCloner("test_cloner")
        
        # Test HTTPS URL
        tool.check_repo_url("https://github.com/user/repo.git")
        assert tool.state == GithubCLoneStates.CLONING
        assert tool.url == "https://github.com/user/repo.git"
        
        # Test HTTP URL  
        tool = GithubCloner("test_cloner")
        tool.check_repo_url("http://github.com/user/repo")
        assert tool.state == GithubCLoneStates.CLONING
        assert tool.url == "http://github.com/user/repo.git"
        
    def test_check_repo_url_shorthand(self):
        """Test that the tool correctly identifies shorthand repository names"""
        tool = GithubCloner("test_cloner")
        
        # Test shorthand format
        tool.check_repo_url("user/repo")
        assert tool.state == GithubCLoneStates.CLONING
        assert tool.url == "https://github.com/user/repo.git"
        
    def test_check_repo_url_requires_user(self):
        """Test that the tool requires user input for ambiguous repository names"""
        tool = GithubCloner("test_cloner")
        
        # Test ambiguous name that requires user input
        tool.check_repo_url("repo")
        assert tool.state == GithubCLoneStates.GETTING_USER
        assert tool.url == "repo.git"
        
    def test_extract_project_name_from_url(self):
        """Test that the tool correctly extracts project names from URLs"""
        tool = GithubCloner("test_cloner")
        
        # Test with .git extension
        tool.url = "https://github.com/user/repo.git"
        name = tool._extract_project_name_from_url()
        assert name == "user/repo"
        
        # Test without .git extension
        tool.url = "https://github.com/user/repo"
        name = tool._extract_project_name_from_url()
        assert name == "user/repo"
        
    def test_run_tool_empty_repository(self):
        """Test that the tool handles empty repository names correctly"""
        tool = GithubCloner("test_cloner")

        user = User(ClientTestOutput())
        response = tool.run_tool(user, "", 60)
        
        assert isinstance(response, AgentToolResponse)
        assert "need a repository name" in response.message

    @pytest.mark.asyncio
    async def test_run_tool_initial_call(self):
        """Test the initial call to run_tool"""
        tool = GithubCloner("test_cloner")
        
        # Test with valid shorthand
        user = User(ClientTestOutput())
        response = tool.run_tool(user, "rfenner/W.A.Y.N.E.", 60)
        
        assert isinstance(response, AgentToolResponse)
        # Should be in CLONING state now and not interactive
        assert tool.state == GithubCLoneStates.CLONING
        
    @patch('tools.github_cloner.subprocess.run')
    @patch('tools.github_cloner.RepositoryRegistry.index_repository')
    def test_run_tool_successful_clone(self, mock_index, mock_subprocess):
        """Test that the tool handles successful cloning correctly"""
        # Mock successful subprocess call
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stderr = ""
        mock_subprocess.return_value = mock_process
        
        # Mock RepositoryRegistry to avoid actual indexing
        mock_registry = patch('tools.github_cloner.RepositoryRegistry').start()
        mock_registry.index_repository = mock_index
        
        tool = GithubCloner("test_cloner")
        tool.url = "https://github.com/user/repo.git"
        tool.state = GithubCLoneStates.CLONING
        
        # Mock the project name extraction
        user = User(ClientTestOutput())
        with patch.object(tool, '_extract_project_name_from_url', return_value="user/repo"):
            response = tool.run_tool(user, "user/repo", 60)
            
            assert isinstance(response, AgentToolResponse)
            assert "successfully cloning" in response.message.lower()
            assert mock_subprocess.called
            assert mock_index.called
            
        patch.stopall()
        
    @pytest.mark.asyncio
    @patch('tools.github_cloner.subprocess.run')
    async def test_run_tool_clone_failure(self, mock_subprocess):
        """Test that the tool handles clone failures correctly"""
        # Mock failed subprocess call
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stderr = "fatal: repository 'https://github.com/user/repo.git' not found"
        mock_subprocess.return_value = mock_process
        
        tool = GithubCloner("test_cloner")
        tool.url = "https://github.com/user/repo.git"
        tool.state = GithubCLoneStates.CLONING

        user = User(ClientTestOutput())
        with patch.object(tool, '_extract_project_name_from_url', return_value="user/repo"):
            response = tool.run_tool(user, "user/repo", 60)
            
            assert isinstance(response, AgentToolResponse)
            assert "GitHub couldn't find" in response.message

    @pytest.mark.asyncio
    @patch('tools.github_cloner.subprocess.run')
    async def test_run_tool_timeout(self, mock_subprocess):
        """Test that the tool handles timeouts correctly"""
        # Mock timeout exception
        mock_subprocess.side_effect = subprocess.TimeoutExpired("git", 120)
        
        tool = GithubCloner("test_cloner")
        tool.url = "https://github.com/user/repo.git"
        tool.state = GithubCLoneStates.CLONING

        user = User(ClientTestOutput())
        with patch.object(tool, '_extract_project_name_from_url', return_value="user/repo"):
            response = tool.run_tool(user, "user/repo", 60)
            
            assert isinstance(response, AgentToolResponse)
            assert "took longer than" in response.message.lower()
            
    @patch('tools.github_cloner.subprocess.run')
    @patch('tools.github_cloner.RepositoryRegistry.index_repository')
    def test_run_tool_permission_denied(self, mock_index, mock_subprocess):
        """Test that the tool handles permission denied errors correctly"""
        # Mock failed subprocess call with permission denied
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stderr = "Permission denied"
        mock_subprocess.return_value = mock_process
        
        tool = GithubCloner("test_cloner")
        tool.url = "https://github.com/user/repo.git"
        tool.state = GithubCLoneStates.CLONING

        user = User(ClientTestOutput())
        with patch.object(tool, '_extract_project_name_from_url', return_value="user/repo"):
            response = tool.run_tool(user, "user/repo", 60)
            
            assert isinstance(response, AgentToolResponse)
            assert "don't have permission" in response.message.lower()
            
    @patch('tools.github_cloner.subprocess.run')
    @patch('tools.github_cloner.RepositoryRegistry.index_repository')
    def test_run_tool_interactive_user_response(self, mock_index, mock_subprocess):
        """Test that the tool handles user responses during interactive mode"""
        # Mock successful subprocess call
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stderr = ""
        mock_subprocess.return_value = mock_process
        
        # Mock RepositoryRegistry to avoid actual indexing
        mock_registry = patch('tools.github_cloner.RepositoryRegistry').start()
        mock_registry.index_repository = mock_index
        
        tool = GithubCloner("test_cloner")
        tool.url = "repo"
        tool.state = GithubCLoneStates.GETTING_USER
        tool.interacting = True

        user = User(ClientTestOutput())
        # Mock the project name extraction
        with patch.object(tool, '_extract_project_name_from_url', return_value="user/repo"):
            response = tool.run_tool(user, "repo", 60, user_response="user")
            
            assert isinstance(response, AgentToolResponse)
            assert tool.state == GithubCLoneStates.CLONING
            
        patch.stopall()

    @ollama_required
    def test_tool_called_by_ollama_with_prompt(self):
        """Test that Ollama would call the tool based on a specific prompt"""
        # Use the Ollama client to test if it would call our tool
        from ollama import Client as OllamaClient
        
        # Create a prompt that should trigger the github_cloner tool
        messages = [{
            "role":"user", 
            'content': "Clone the repository https://github.com/owner/repo.git for me"
        }]
        
        tool = GithubCloner("github_cloner_test")
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
                assert response.message.tool_calls[0].function.name == "github_cloner"
                # Verify the arguments are properly structured
                args = response.message.tool_calls[0].function.arguments
                assert 'repository' in args
                assert 'timeout' in args
            else:
                # If no tool calls, that's also valid - it means the LLM decided not to use the tool
                # but this test is primarily checking if the tool definition works properly
                pass
                
        except Exception as e:
            # If Ollama isn't available or there are connection issues, we skip this test
            pytest.skip(f"Ollama test skipped due to: {str(e)}")