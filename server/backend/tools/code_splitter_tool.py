import json
from pydantic import BaseModel, Field

from core.agent_tool import AgentTool, AgentToolResponse
from core.chunking import FileChunker
from core.user import User


class CodeSplitterInput(BaseModel):
    """Input parameters for the code splitter tool"""
    content: str = Field(description="Content of the code to be split")
    language: str = Field(description="Programming language of the code")
    max_chunk_size: int = Field(default=1000, description="Maximum tokens per chunk")


class CodeSplitterTool(AgentTool):
    """
    A tool that splits code form a query into logical chunks using the existing chunking infrastructure.
    This tool leverages the FileChunker class to properly split code based on language-specific
    syntax boundaries for better LLM processing.
    """
    
    def __init__(self):
        super().__init__(name="code_splitter")
        self.chunker = FileChunker()
    
    @classmethod
    def _generate_parameters(cls) -> dict:
        return CodeSplitterInput.model_json_schema()

    # noinspection PyMethodOverriding
    def run_tool(self, user: User, content:str, language:str, **kwargs) -> AgentToolResponse:
        """
        Split code content into logical chunks using the existing chunking infrastructure.
        
        Args:
            user: The user requesting the tool
            **kwargs: Arguments including file_path, content, language, and max_chunk_size
            
        Returns:
            AgentToolResponse with the split chunks and metadata
        """
        try:
            max_chunk_size = kwargs.get("max_chunk_size", 1000)
            
            if len(content) == 0:
                return AgentToolResponse(
                    message="Missing required parameters: file_path, content, and language are required"
                )
            if len(language) == 0:
                language = "text"
            # Use the existing chunking infrastructure
            chunk_type, chunks = self.chunker.chunk_text(content, language)
            
            # Convert to our expected output format
            formatted_chunks = []
            for chunk_text, start_line, end_line in chunks:
                formatted_chunks.append({
                    "content":chunk_text,
                    "file_path":'',
                    "language":language,
                    "start_line":start_line,
                    "end_line":end_line
                })
            
            # Return the results
            return AgentToolResponse(
                message=json.dumps(formatted_chunks),
                go_interactive=False,
                interactive_done=True,
            )
            
        except Exception as e:
            return AgentToolResponse(
                message=f"Error splitting code: {str(e)}",
                go_interactive=False,
                interactive_done=True,
            )

