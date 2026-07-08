from pydantic import BaseModel

from core.agent_tool import AgentTool, AgentToolResponse
from core.repo_registry import RepositoryRegistry


class ListRepositoriesModel(BaseModel):
    """
    fetches a list of available repositories
    """


class ListRepositories(AgentTool):
    @classmethod
    def _generate_parameters(cls) -> dict:
        return ListRepositoriesModel.model_json_schema()

    def run_tool(self, user: 'User', *args, **kwargs) -> AgentToolResponse:
        repos = RepositoryRegistry.get_repositories()

        directory_output = [
            "--- AVAILABLE WORKSPACE REPOSITORIES ---",
            "Review the AI-generated directory summaries below to pick the correct repository ID."
        ]

        for repo in repos:
            repo_block = (
                f"\n=========================================\n"
                f"REPOSITORY ID: '{repo.name}'\n"
            )
            if repo.summary_file:
                repo_block += f"LOCAL PATH: {repo.summary_file}\n"
            if repo.summary:
                repo_block += f"AI-GENERATED ARCHITECTURE OVERVIEW:\n{repo.summary}\n"

            repo_block += f"========================================="

            directory_output.append(repo_block)

        directory_output.append("\n--- END OF WORKSPACE REPOSITORIES ---")
        return AgentToolResponse(
            message="\n".join(directory_output)
        )
