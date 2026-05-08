import inspect
from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING

from pydantic import BaseModel, Field, ConfigDict

if TYPE_CHECKING:
    from core.user import User


class AgentToolResponse(BaseModel):
    """
    The response that agents return to the tool manager
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    message: str | None = Field(description='The message that will be sent back to the llm', default=None)
    go_interactive: bool = Field(description='Indicates the tool wants to directly interact with the user',
                                 default=False)
    interactive_done: bool = Field(
        description='Indicates that tool is done interacting with the user and response should go to the llm or previous active tool',
        default=False)
    interactive_agent: 'AgentTool' = Field(
        description='The agent that will be used to interact with the user, could be the agent returning the response',
        default=None)


class AgentTool(ABC):
    """
    Class that tools implement so the tool manager can:
    1. locate them when loading
    2. provide a consistent interface for the tools manager to run them
        when the llm requests them
    """

    """Holds the arguments extracted from run_tool so llm arguments can be mapped to it"""
    _run_tool_arguments:dict[Any, list] = {}

    def __init__(self, name: str):
        self.name = name

    @classmethod
    @abstractmethod
    def _generate_parameters(cls) -> dict:
        """
        Class should override this method to generate a dict of parameters
        """
        pass

    @classmethod
    def tools_definition(cls, tool_name: str | None = None) -> dict:
        """
        Returns the tools definition for the llm to use.
        Class method so we don't have to instantiate it to get the def
        """

        if tool_name is None:
            tool_name = cls.__name__

        desc = cls.__doc__
        if desc is None:
            raise RuntimeError(f"{cls.__name__}: Has no class description.")

        return {
            'type': 'function',
            'function': {
                'name': tool_name,
                'description': desc,
                'parameters': cls._generate_parameters(),
            }
        }

    @classmethod
    def run_tool_arguments(cls):
        # only extract it once
        arguments = cls._run_tool_arguments.get(cls)
        if arguments:
            return arguments

        cls._run_tool_arguments[cls] = []

        signature = inspect.signature(cls.run_tool)
        for param in signature.parameters.values():
            # we skip the user parameter since it's one passed by
            # use and not one we expect from the llm
            if param.name == 'user' or param.name == 'self' or \
                param.name == 'args' or param.name == 'kwargs':
                continue
            cls._run_tool_arguments[cls].append(param.name)

        return cls._run_tool_arguments[cls]


    @abstractmethod
    def run_tool(self, user: 'User', *args, **kwargs) -> AgentToolResponse:
        """
        Runs the tool with the specified arguments
        """
        pass
