"""
Helper for cloning and analyzing GitHub repositories.
"""
import subprocess
import os
from enum import IntEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from config import REPOSITORIES_DIR
from core.agent_tool import AgentTool, AgentToolResponse
from core.repo_registry import RepositoryRegistry

if TYPE_CHECKING:
    from core.user import User


class GithubCLoneStates(IntEnum):
    INITIAL_CALL = 0
    GETTING_USER = 1
    CLONING = 2


class GithubClonerModel(BaseModel):
    repository: str = Field(description="The repository name to clone from ")
    timeout: int = Field(
        description="How long to wait for the cloning process to finish before aborting (default 120 seconds for large repos)",
        default=120)


class GithubCloner(AgentTool):
    """
    Clones a GitHub repository in to the repositories path
    """

    def __init__(self, name: str):
        super().__init__(name)
        self.state = GithubCLoneStates.INITIAL_CALL
        self.url = None
        self.destination = None
        self.interacting = False
        self.timeout = 120

    @classmethod
    def _generate_parameters(cls) -> dict:
        pass

    # noinspection PyMethodOverriding
    def run_tool(self, user: 'User', repository: str, timeout: int, **kwargs) -> AgentToolResponse:
        if self.state == GithubCLoneStates.INITIAL_CALL:
            self.timeout = timeout
            # figure out what we have for repository
            if repository == '':
                return AgentToolResponse(
                    message='I need a repository name to clone'
                )

            # is it a git url
            self.check_repo_url(repository)
            if self.state == GithubCLoneStates.GETTING_USER:
                self.interacting = True
                user.client.send_output(f'What github user do you want to clone {repository} from?')
                return AgentToolResponse(
                    go_interactive=True,
                    interactive_agent=self
                )
        if self.state == GithubCLoneStates.GETTING_USER:
            if 'user_response' not in kwargs:
                user.client.send_output(f'What github user do you want to clone {repository}?')
                return AgentToolResponse()
            else:
                self.url = f"https://github.com/{kwargs['user_response']}/{self.url}"
                self.state = GithubCLoneStates.CLONING

        self.state = GithubCLoneStates.CLONING

        proj_name = self._extract_project_name_from_url()
        local_path = f'{REPOSITORIES_DIR}/{proj_name.replace("/", "_")}'

        user.client.send_output(f"I'm now cloning {proj_name} this may take a minute for large repos")
        message = "I successfully cloning the repository and I'm currently analyzing it and can ask me questions when I finish"
        try:
            clone_result = subprocess.run(
                ["git", "clone", "--depth", "1", self.url, local_path],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            if clone_result.returncode != 0:
                message = 'I was unable to clone this repository due to some error while cloning'
                if 'not found' in clone_result.stderr.lower() or '404' in clone_result.stderr.lower():
                    message = f"GitHub couldn't find repository {self.url} if it's private make sure you have access to it."
                elif 'permission denied' in clone_result.stderr.lower():
                    message = f"GitHub returned that you don't have permission to clone {self.url}, make sure you access to it and try again."

        except subprocess.TimeoutExpired:
            message = f'The cloning took longer than {self.timeout} seconds to complete so I gave up.'
        except Exception as e:
            message = 'I was unable to clone this repository due to some error while cloning'

        # kick off indexing
        RepositoryRegistry.index_repository(local_path)

        return AgentToolResponse(
            message=message,
            interactive_done=self.interacting,
        )

    def _extract_project_name_from_url(self):
        parts = self.url.split('/', maxsplit=3)
        name = parts[3].replace('.git', '')
        return name

    def check_repo_url(self, repo: str):
        """
        Determine the type of repository name we have.

        Examples:
            "Analyze https://github.com/user/repo"
            "Clone and understand facebook/react"
            "Find auth in vue" - This triggers interaction to get the user
        """
        import re

        # Look for full URL first
        url_match = re.search(r'https?://github\.com/[\w\-./]+(?:\.git)?', repo)
        if url_match:
            url = url_match.group(0)
            if not url.endswith('.git'):
                url += '.git'
            self.url = url
            self.state = GithubCLoneStates.CLONING
            return
        # Look for shorthand (user/repo)
        # This regex is more careful to avoid matching too much
        shorthand_match = re.search(r'\b([a-zA-Z0-9][a-zA-Z0-9\-]{0,38})/([a-zA-Z0-9][a-zA-Z0-9\-_.]{0,38})\b', repo)
        if shorthand_match:
            user, repo = shorthand_match.groups()
            # Avoid matching common words
            if user.lower() not in ['the', 'and', 'or', 'for', 'with', 'from']:
                self.url = f"https://github.com/{user}/{repo}.git"
                self.state = GithubCLoneStates.CLONING
                return
        if not repo.endswith('.git'):
            repo += '.git'
        self.state = GithubCLoneStates.GETTING_USER
        self.url = repo
        return
