from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel

from core.agent_tool import AgentTool, AgentToolResponse
from core.tools_manager import ToolsManager, ToolInfo
from tests.conftest import ClientTestOutput

from core.user import User


class ToolManagerAgentTestToolModel(BaseModel):
    name: str


class ToolManagerAgentTestTool(AgentTool):
    """
    Tool manager test tool
    """
    tool_definition = None

    def __init__(self, name: str):
        super().__init__(name)
        self.response: AgentToolResponse | None = None
        self.validate_arguments = None

    @classmethod
    def _generate_parameters(cls) -> dict:
        if cls.tool_definition is None:
            return ToolManagerAgentTestToolModel.model_json_schema()
        return cls.tool_definition

    # noinspection PyMethodOverriding
    def run_tool(self, user: 'User', name, **kwargs) -> AgentToolResponse:
        if self.validate_arguments:
            self.validate_arguments(name, **kwargs)
        if self.response:
            return self.response
        return AgentToolResponse(
            message='Test Message'
        )


class TestToolInfo:
    def test_validate(self):
        test_schema = {}
        with pytest.raises(ValueError, match='type not in definition or is not set to function'):
            ToolInfo(
                name='Test',
                tool_definition=test_schema,
            )

        # type not function
        test_schema['type'] = 'not_function'
        with pytest.raises(ValueError, match='type not in definition or is not set to function'):
            ToolInfo(
                name='Test',
                tool_definition=test_schema,
            )

        # no function
        test_schema['type'] = 'function'
        with pytest.raises(ValueError, match='function not in definition'):
            ToolInfo(
                name='Test',
                tool_definition=test_schema,
            )

        # name not in function
        test_schema['function'] = {}
        with pytest.raises(ValueError, match='name, description or parameters not in function definition'):
            ToolInfo(
                name='Test',
                tool_definition=test_schema,
            )

        # description not in function
        test_schema['function']['name'] = 'test'
        with pytest.raises(ValueError, match='name, description or parameters not in function definition'):
            ToolInfo(
                name='Test',
                tool_definition=test_schema,
            )

        # parameters not in function
        test_schema['function']['description'] = 'test description'
        with pytest.raises(ValueError, match='name, description or parameters not in function definition'):
            ToolInfo(
                name='Test',
                tool_definition=test_schema,
            )

        # type not in parameters
        test_schema['function']['parameters'] = {}
        with pytest.raises(ValueError, match='type not in parameters definition or is not set to object'):
            ToolInfo(
                name='Test',
                tool_definition=test_schema,
            )

        # type not object
        test_schema['function']['parameters']['type'] = 'not_object'
        with pytest.raises(ValueError, match='type not in parameters definition or is not set to object'):
            ToolInfo(
                name='Test',
                tool_definition=test_schema,
            )

        # properties not in parameters
        test_schema['function']['parameters']['type'] = 'object'
        with pytest.raises(ValueError, match='properties not in parameters or is not a dictionary'):
            ToolInfo(
                name='Test',
                tool_definition=test_schema,
            )

        # properties not dict
        test_schema['function']['parameters']['properties'] = []
        with pytest.raises(ValueError, match='properties not in parameters or is not a dictionary'):
            ToolInfo(
                name='Test',
                tool_definition=test_schema,
            )

        # valid
        test_schema['function']['parameters']['properties'] = {}
        tool_info = ToolInfo(
            name='Test',
            tool_definition=test_schema,
        )


class TestToolsManager:
    def test_init(self, reset_restore_system_tools):
        manager = ToolsManager()
        assert manager._tools == {}
        assert manager._in_control_tools == []
        assert manager.is_tool_in_control is False

    def test__find_tools_in_file(self):
        # no tool in file
        tools = ToolsManager._find_tools_in_file('/app/tests/test_data/tools_manager_test/no_tools_in_file.py')
        assert tools == []

        # single tool in file
        tools = ToolsManager._find_tools_in_file('/app/tests/test_data/tools_manager_test/multiple_tools.py')
        assert len(tools) == 2
        assert tools == [
            'TwoTool',
            'ThreeTool'
        ]

        # multiple tools in file
        tools = ToolsManager._find_tools_in_file('/app/tests/test_data/tools_manager_test/one_tool.py')
        assert len(tools) == 1
        assert tools == [
            'OneTool',
        ]

        # finds the bad tool
        tools = ToolsManager._find_tools_in_file('/app/tests/test_data/tools_manager_test/bad_definition.py')
        assert len(tools) == 1
        assert tools == [
            'BadTool',
        ]

    def test__load_tools(self, reset_restore_system_tools):
        manager = ToolsManager()

        manager._load_tools('/app/tests/test_data/tools_manager_test')
        assert len(manager._system_tools) == 3

        assert any('OneTool' in v.name for v in manager._system_tools.values())
        assert any('TwoTool' in v.name for v in manager._system_tools.values())
        assert any('ThreeTool' in v.name for v in manager._system_tools.values())
        assert all('BadTool' not in v.name for v in manager._system_tools.values())
        assert all(v.instance is None for v in manager._system_tools.values())
        assert any(v.instance is None for v in manager._system_tools.values())
        assert any(v.instance is None for v in manager._system_tools.values())
        assert any(v.instance is None for v in manager._system_tools.values())
        assert any(v.instance is None for v in manager._system_tools.values())
        assert any(v.class_type.__name__ == 'OneTool' for v in manager._system_tools.values())
        assert any(v.class_type.__name__ == 'TwoTool' for v in manager._system_tools.values())
        assert any(v.class_type.__name__ == 'ThreeTool' for v in manager._system_tools.values())
        assert all(v.class_type.__name__ != 'BadTool' for v in manager._system_tools.values())

    def test__internal_add_tool(self):
        manager = ToolsManager()
        tool_info = ToolInfo(
            name='test',
            tool_definition=ToolManagerAgentTestTool.tools_definition()
        )
        with pytest.raises(RuntimeError, match='Tool info must have either the instance or class_type set.'):
            manager._internal_add_tool(tool_info)
        tool_info.class_type = ToolManagerAgentTestTool

        manager._internal_add_tool(tool_info)
        assert len(manager._tools) == 1
        assert manager._tools[tool_info.name] == tool_info

        with pytest.raises(RuntimeError, match='Tool test already exists'):
            manager._internal_add_tool(tool_info)

    def test_add_tool_instance(self):
        manager = ToolsManager()

        with pytest.raises(RuntimeError, match='Tool is not an AgentTool'):
            manager.add_tool_instance(None)

        tool_name = 'test'
        tool = ToolManagerAgentTestTool(tool_name)
        manager.add_tool_instance(tool)
        assert len(manager._tools) == 1
        assert manager._tools[tool.name].name == tool.name
        assert manager._tools[tool.name].instance == tool
        assert manager._tools[tool.name].class_type is None
        assert manager._tools[tool.name].tool_definition == ToolManagerAgentTestTool.tools_definition(tool_name)

    def test_add_tool_class(self):
        manager = ToolsManager()

        with pytest.raises(RuntimeError, match='Tool test is not an AgentTool'):
            manager.add_tool_class('test', None)

        tool_name = 'test'
        manager.add_tool_class(tool_name, ToolManagerAgentTestTool)
        assert len(manager._tools) == 1
        assert manager._tools[tool_name].name == tool_name
        assert manager._tools[tool_name].instance is None
        assert manager._tools[tool_name].class_type is ToolManagerAgentTestTool
        assert manager._tools[tool_name].tool_definition == ToolManagerAgentTestTool.tools_definition(tool_name)

    def test_get_tool_definition(self):
        manager = ToolsManager()
        tool1 = ToolManagerAgentTestTool(
            name='test 1',
        )
        tool2 = ToolManagerAgentTestTool(
            name='test 2',
        )
        manager.add_tool_instance(tool1)
        manager.add_tool_instance(tool2)

        tool_defs = manager.get_tool_definitions
        assert len(tool_defs) == 2
        assert tool_defs == [tool1.tools_definition(tool1.name), tool2.tools_definition(tool2.name)]

    def test__find_tool(self, reset_restore_system_tools):
        manager = ToolsManager()

        assert manager._find_tool('test') is None
        tool = ToolManagerAgentTestTool('test')
        manager.add_tool_instance(tool)
        manager._system_tools['test'] = ToolInfo(
            name='test system',
            tool_definition=ToolManagerAgentTestTool.tools_definition(),
            instance=ToolManagerAgentTestTool('test system')
        )

        found = manager._find_tool('test')
        assert found is not None
        assert found.name == 'test'

        manager._system_tools['test_system'] = manager._system_tools['test']
        found = manager._find_tool('test_system')
        assert found is not None
        assert found.name == 'test system'

    def test__fill_missing_parameters(self):
        # make sure the tools_definition for the class has run once
        # to set the run arguments
        ToolManagerAgentTestTool.tools_definition()
        run_arguments = ToolManagerAgentTestTool.run_tool_arguments()
        #test arguments is None
        arguments = ToolsManager._fill_missing_parameters(run_arguments, None)
        assert arguments == {'name':None}
        # test no arguments
        arguments = ToolsManager._fill_missing_parameters(run_arguments, {})
        assert arguments == {'name':None}

        # test arguments is dict
        arguments = ToolsManager._fill_missing_parameters(run_arguments, {'name':'test'})
        assert arguments == {'name':'test'}

        #test arguments is list
        arguments = ToolsManager._fill_missing_parameters(run_arguments, ['test'])
        assert arguments == {'name':'test'}

        # test neither list or dict
        arguments = ToolsManager._fill_missing_parameters(run_arguments, 'test')
        assert arguments == {'name':'test'}

        #test missing argument but has others dict
        arguments = ToolsManager._fill_missing_parameters(run_arguments, {'not_a_param':'test'})
        assert arguments == {'name':None, 'not_a_param':'test'}

        # test missing argument but has others list
        arguments = ToolsManager._fill_missing_parameters(run_arguments, ['test', 'test 2'])
        assert arguments == {'name': 'test', 'args': ['test 2']}

    def test__run_tool(self):
        user = User(ClientTestOutput())
        manager = ToolsManager()
        tool = ToolManagerAgentTestTool('test')
        tool.response = AgentToolResponse(
            message='Test Response'
        )

        def validate_args(name, **kwargs):
            assert name == 'test'
            assert 'response' in kwargs
            assert kwargs['response'] == 'response'

        tool.validate_arguments = validate_args
        # test just running the tool
        response = manager._run_tool(user, tool, {'name': 'test', 'response': 'response'})
        assert response == {
            'role': 'tool',
            'tool_name': 'test',
            'content': 'Test Response'
        }

        tool.validate_arguments = None
        # test no interactive agent when going interactive
        tool.response = AgentToolResponse(
            go_interactive=True
        )
        with pytest.raises(RuntimeError,
                           match=f'go_interactive was requested by {tool.name} but no interactive agent was returned'):
            manager._run_tool(user, tool, {})

        # test interactive agent isn't an AgentTool
        tool.response.interactive_agent = 'Test'
        with pytest.raises(RuntimeError, match=f'The interactive agent returned by {tool.name} is not an AgentTool'):
            manager._run_tool(user, tool, {})

        # test go interactive
        tool.response.interactive_agent = tool

        response = manager._run_tool(user, tool, {})
        assert response is None
        assert manager.is_tool_in_control is True
        assert manager._in_control_tools[0] == tool

        # test interaction done
        tool.response.message = 'Test Message'
        tool.response.go_interactive = False
        tool.response.interactive_done = True

        response = manager._run_tool(user, tool, {})
        assert response is not None
        assert response == {
            'role': 'tool',
            'tool_name': 'test',
            'content': 'Test Message'
        }
        assert manager.is_tool_in_control is False

    def test_continue_tool(self):
        user = User(ClientTestOutput())
        manager = ToolsManager()
        tool = ToolManagerAgentTestTool('test')

        # test interaction done
        tool.response = AgentToolResponse(
            message='Test Message',
            interactive_done=True
        )
        with pytest.raises(RuntimeError, match='No tool is currently in control to continue'):
            manager.continue_tool(user, 'test')

        manager._in_control_tools.append(tool)
        assert manager.is_tool_in_control is True
        response = manager.continue_tool(user, 'test')
        assert response is not None
        assert response == {
            'role': 'tool',
            'tool_name': 'test',
            'content': 'Test Message'
        }
        assert manager.is_tool_in_control is False

    def test_run_tool_call(self):
        user = User(ClientTestOutput())
        manager = ToolsManager()
        tool = ToolManagerAgentTestTool('test')

        manager._in_control_tools.append(tool)

        # test can't find tool
        with pytest.raises(RuntimeError,
                           match='Another tool is in control and we were not expecting to run a tool_call'):
            manager.run_tool_call(user, 'test', {})

        manager._in_control_tools = []

        # test tool is instance
        manager.add_tool_instance(tool)

        response = manager.run_tool_call(user, 'not_found', {})
        assert response == {
            'role': 'tool',
            'tool_name': 'not_found',
            'content': 'Unknown tool'
        }

        def validate_args(name, **kwargs):
            assert name == 'test'
            assert 'response' in kwargs
            assert kwargs['response'] == 'response'

        tool.validate_arguments = validate_args
        response = manager.run_tool_call(user, 'not_found', {'name': 'test', 'response': 'response'})
        assert response == {
            'role': 'tool',
            'tool_name': 'not_found',
            'content': 'Unknown tool'
        }

        # test tool is class type
        tool.validate_arguments = None
        tool.response = AgentToolResponse(
            message='Test Message'
        )
        manager._tools[tool.name].instance = None
        manager._tools[tool.name].class_type = ToolManagerAgentTestTool

        response = manager.run_tool_call(user, tool.name, {'name': 'test', 'response': 'response'})
        assert response is not None
        assert response == {
            'role': 'tool',
            'tool_name': 'test',
            'content': 'Test Message'
        }

        # test that neither instance nore class was set
        manager._tools[tool.name].class_type = None
        response = manager.run_tool_call(user, tool.name, {'name': 'test', 'response': 'response'})
        assert response is not None
        assert response == {
            'role': 'tool',
            'tool_name': 'test',
            'content': "Couldn't run tool"
        }
