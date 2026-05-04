import json
import re
import requests
from typing import List, Dict, Any, TYPE_CHECKING

from pydantic import BaseModel, Field

from core.agent_tool import AgentTool, AgentToolResponse
from core.repo_registry import RepositoryRegistry

if TYPE_CHECKING:
    from core.user import User

class CodeSearchToolModel(BaseModel):
    """
    Searches a repository for a query in the code of a repository.
    """
    repo_name:str = Field(description="The Repositories Name")
    query:str = Field(description="The query to search for in the code")
    is_reg_ex:bool = Field(description="Whether or not the query is reg ex pattern")

class CodeSearchTool(AgentTool):
    """
    Searches a repository for a query in the code of a repository.
    """
    @classmethod
    def _generate_parameters(cls) -> dict:
        return CodeSearchToolModel.model_json_schema()

    # noinspection PyMethodOverriding
    def run_tool(self, user:'User', repo_name:str, query:str, is_reg_ex:bool, **kwargs) -> AgentToolResponse:
        repo = RepositoryRegistry.get_repository(repo_name.lower())
        if repo is None:
            return AgentToolResponse(
                message='[]'
            )
        file_list = repo.repository_files

        results = []
        for file in file_list:
            with open(file, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    found = False
                    if is_reg_ex:
                        if re.search(query, line):
                            found = True
                    else:
                        if query in line:
                            found = True
                    if found:
                        results.append({
                            "file_path": file,
                            "line_number": i + 1,
                            "line": line,
                        })
        return AgentToolResponse(
            message=json.dumps(results),
        )

def search_github(repo_url: str, query: str) -> List[Dict[str, Any]]:
    """Searches a remote repo using GitHub Search API."""
    parts = repo_url.replace("https://github.com/", "").split("/")
    if len(parts) < 2: return []
    owner, repo = parts[0], parts[1]
    
    # Auth headers are optional but recommended
    headers = {
        "Accept": "application/vnd.github.v3+json"
    }
    
    # GitHub Search API 
    api_url = f"https://api.github.com/search/code?q={query}+repo:{owner}/{repo}"
    
    try:
        resp = requests.get(api_url, headers=headers)
        if resp.status_code == 200:
            items = resp.json().get("items", [])
            results = []
            for item in items:
                # Determine raw url for download/viewing
                raw_url = item["html_url"].replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
                results.append({
                    "file_path": item["path"],
                    "line_number": "N/A (Remote Search)", 
                    "line": f"Match found in {item['name']}",
                    "download_url": raw_url
                })
            return results
        return [{"error": f"GitHub API Error: {resp.status_code} - {resp.reason}"}]
    except Exception as e:
        return [{"error": str(e)}]

