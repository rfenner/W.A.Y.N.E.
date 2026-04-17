from abc import ABC, abstractmethod


class AgentTool(ABC):
    @abstractmethod
    def tools_definition(self)->dict:
        pass

    @abstractmethod
    def run_tool(self, *args, **kwargs) -> dict:
        pass