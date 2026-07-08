from pydantic import BaseModel, Field

from config import TOP_K_RERANK
from core.agent_tool import AgentTool, AgentToolResponse
from core.repo_registry import RepositoryRegistry


class GetCodebaseContextModel(BaseModel):
    """
    Get the sematic context of a codebase repository or exact file contents based on a search query
    """
    repo_name: str = Field(description="Repository name to get the context for")
    search_query: str = Field(description="The specific code feature or variable name to locate.")


class GetCodebaseContext(AgentTool):
    @classmethod
    def _generate_parameters(cls) -> dict:
        return GetCodebaseContextModel.model_json_schema()

    # noinspection PyMethodOverriding
    def run_tool(self, user: 'User', repo_name: str, query: str, **kwargs) -> AgentToolResponse:
        repo = RepositoryRegistry.get_repository(repo_name)

        if repo is None:
            valid_repos = RepositoryRegistry.get_repositories()
            if valid_repos:
                repo_names = []
                for repo in valid_repos:
                    repo_names.append(repo.name)
                valid_repos = ','.join(repo_names)
                return AgentToolResponse(
                    message=(
                        f"CRITICAL ERROR: '{repo_name}' is an invalid or unknown repository ID.\n"
                        f"The only valid repository IDs currently registered in this workspace are: {valid_repos}.\n"
                        f"REMEDY: Choose the matching ID from this list and call 'get_codebase_context' again."
                    )
                )
            else:
                return AgentToolResponse(
                    message=(
                        f"CRITICAL ERROR: there are no repositories available to query\n"
                        f"The only valid repository IDs currently registered in this workspace are: {valid_repos}.\n"
                        f"REMEDY: Choose the matching ID from this list and call 'get_codebase_context' again."
                    )
                )

        results = repo.indexer.search(query, k=TOP_K_RERANK)
        if len(results) == 0:
            return AgentToolResponse(
                message=f'I was unable to find any snippets matching {query}'
            )

        # compile the blocks into a context string for the llm
        context_blocks = [
            f"--- RE-RANKED CODE CONTEXT START FOR REPOSITORY: {repo.name} ---",
            "The following code snippets have been verified and sorted by structural engineering relevance."
        ]
        for idx, result in enumerate(results, start=1):
            block = (
                f"\n[Snippet #{idx}] File: {result['path']} (Lines {result['start_line']}-{result['end_line']}) "
                f"| Language: {result['language']}\n"
                f"| Relevance Score: {round(result['rerank_score'], 3)}\n"
                f"```{result['language']}\n"
                f"{result['text'].strip()}\n"
                f"```"
            )
            context_blocks.append(block)

        context_blocks.append(f"\n--- RE-RANKED CODE CONTEXT END FOR REPOSITORY: {repo.name} ---")
        return AgentToolResponse(message="\n".join(context_blocks))