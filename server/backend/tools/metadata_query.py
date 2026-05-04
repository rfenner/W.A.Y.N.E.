from enum import StrEnum
from typing import Optional, TYPE_CHECKING

from pydantic import BaseModel, Field

from core.agent_tool import AgentTool
from core.repo_registry import RepositoryRegistry

if TYPE_CHECKING:
    from core.user import User

class MetadataTypes(StrEnum):
    LIST = "list"
    STRUCTURE = "structure"
    TOTAL_COUNT = "total_count"
    COUNT_TYPE = "count_specific"
    COUNT_TYPES = "count_types"
    GENERAL = "general"

class MetadataQueryModel(BaseModel):
    repo_name:str = Field(description='The name of the repository for which the metadata is requested')
    metadata_type:MetadataTypes = Field(description="""The type of metadat to retrieve: 
    'list' to list the files, 
    'structure' to list the files grouped by type and how manny, 
    'total_count' to get a count of total files and how many of each type,
     'file_type' to get a list of the specified file with a specific type or all list of the unique file types, 
     'general' a general report of the repository as default
     """)
    file_types:Optional[list|None] = Field(description='A list of file types that may be requested')

class MetadataQuery(AgentTool):
    """
    Gets metadata about a repository such as how many files, what
    types of files,  repository structure or a list of files in the repository
    or list of a particular type of files.
    """
    @classmethod
    def _generate_parameters(cls) -> dict:
        return MetadataQueryModel.model_json_schema()

    # noinspection PyMethodOverriding
    def run_tool(self, user:'User', repo_name:str, metadata_type:MetadataTypes, file_types:list|None=None) -> str:
        repo = RepositoryRegistry.get_repository(repo_name)
        if repo is None:
            return f"I don't know about repository {repo_name}. Perhaps you should clone and I can then provide answers on it."

        match metadata_type:
            case MetadataTypes.LIST:
                pass
            case MetadataTypes.STRUCTURE:
                pass
            case MetadataTypes.COUNT:
                pass
            case MetadataTypes.FILE_TYPE:
                pass
            case MetadataTypes.GENERAL:
                pass

