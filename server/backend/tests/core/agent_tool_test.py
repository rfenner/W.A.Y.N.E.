from typing import TYPE_CHECKING

import pytest

from core.agent_tool import AgentTool, AgentToolResponse

if TYPE_CHECKING:
    from core.user import User


class AgentToolTestNoDoc(AgentTool):
    @classmethod
    def _generate_parameters(cls) -> dict:
        return {}

    def run_tool(self, user: 'User', *args, **kwargs) -> AgentToolResponse:
        pass

class AgentToolTestDoc(AgentTool):
    """
    Cass has a doc string
    """
    @classmethod
    def _generate_parameters(cls) -> dict:
        return {}

    # noinspection PyMethodOverriding
    def run_tool(self, user: 'User', test, *args, **kwargs) -> AgentToolResponse:
        pass


class TestAgentTool:
    def test_tool_definition(self):
        # test no doc
        with pytest.raises(RuntimeError, match="AgentToolTestNoDoc: Has no class description."):
            AgentToolTestNoDoc.tools_definition()

        assert len(AgentToolTestNoDoc.run_tool_arguments) == 0

        # test no name passed
        tool_def = AgentToolTestDoc.tools_definition()
        assert len(AgentToolTestNoDoc.run_tool_arguments) == 1
        assert AgentToolTestNoDoc.run_tool_arguments[0] == 'test'

        assert 'function' in tool_def
        assert 'type' in tool_def
        assert tool_def['type'] == 'function'
        assert tool_def['function']['name'] == AgentToolTestDoc.__name__
        assert tool_def['function']['description'] == AgentToolTestDoc.__doc__
        assert tool_def['function']['parameters'] == {}

        # test name passed
        tool_def = AgentToolTestDoc.tools_definition('test')
        assert tool_def['function']['name'] == 'test'

