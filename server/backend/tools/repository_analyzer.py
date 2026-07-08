from pydantic import BaseModel, Field

from config import TOP_K_RETRIEVAL
from core.agent_tool import AgentTool, AgentToolResponse
from core.repo_registry import RepositoryRegistry


class RepositoryAnalyzerModel(BaseModel):
    """
    analyzes the structure of a repository returning information about files that match the query
    """
    repo_name: str = Field(description="The name of the repository to analyze")
    query: str = Field(description='The query to use to analyze the repository')
    max_results: int = Field(description=f'The number of results to return with a max limit of {TOP_K_RETRIEVAL}',
                             default=5)


class RepositoryAnalyzer(AgentTool):
    """
    Analyzes a repository for a query
    """

    @classmethod
    def _generate_parameters(cls) -> dict:
        return RepositoryAnalyzerModel.model_json_schema()

    # noinspection PyMethodOverriding
    def run_tool(self, user: 'User', repo_name: str, query: str, max_results: int, **kwargs) -> AgentToolResponse:
        try:
            repo = RepositoryRegistry.get_repository(repo_name)
            if repo is None:
                return AgentToolResponse(
                    message=f"Repository '{repo_name}' not found.",
                )
            indexer = repo.indexer

            file_count = indexer.get_file_count()

            results = indexer.search(query, k=max_results)
            message = f"Repository indexed ({file_count} files).\n\n"

            if not results:
                summary = indexer.get_aggregate_summary()
                return AgentToolResponse(
                    message=message + f"Architecture:\n{summary}\n\nI was unable to find any matches for your query of '{query}'.",
                )

            message +=f" I found the following results for '{query}:\n\n"
            for i, r in enumerate(results, 1):
                message += f"{i} **{r['file_path']}** ({r['language']})\n"
                message += f"   Lines {r['start_line']}-{r['end_line']}\n"
                message += f"   Relevance {r['score']:.2f}\n"
                message += f"   Content:\n   ````\n{r['content'][:300]}\n   ```\n"

            return AgentToolResponse(message=message)
        except Exception as e:
            return AgentToolResponse(
                message="I ran into an error while analyzing the repository.",
            )