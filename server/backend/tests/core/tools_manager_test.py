import pytest

from core.tools_manager import ToolsManager


class TestToolsManager:
    @pytest.fixture(scope='function', autouse=True)
    def setup_teardown(self):
        yield

    def test_init(self):
        manager = ToolsManager()
        assert manager._tools == {}

    def test_definition_valid(self):
        # no type
        test_schema = {}
        assert ToolsManager._definition_valid(test_schema) is False


        # type not function
        test_schema['type'] = 'not_function'
        assert ToolsManager._definition_valid(test_schema) is False

        # no function
        test_schema['type'] = 'function'
        assert ToolsManager._definition_valid(test_schema) is False

        # name not in function
        test_schema['function'] = {}
        assert ToolsManager._definition_valid(test_schema) is False

        # description not in function
        test_schema['function']['name'] = 'test'
        assert ToolsManager._definition_valid(test_schema) is False

        # parameters not in function
        test_schema['function']['description'] = 'test description'
        assert ToolsManager._definition_valid(test_schema) is False

        # type not in parameters
        test_schema['function']['parameters'] = {}
        assert ToolsManager._definition_valid(test_schema) is False

        # type not object
        test_schema['function']['parameters']['type'] = 'not_object'
        assert ToolsManager._definition_valid(test_schema) is False

        # properties not in parameters
        test_schema['function']['parameters']['type'] = 'object'
        assert ToolsManager._definition_valid(test_schema) is False

        # properties not dict
        test_schema['function']['parameters']['properties'] = []
        assert ToolsManager._definition_valid(test_schema) is False

        # valid
        test_schema['function']['parameters']['properties'] = {}
        assert ToolsManager._definition_valid(test_schema)

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

    def test__load_tools(self):
        manager = ToolsManager()

        manager._load_tools('/app/tests/test_data/tools_manager_test')
        assert len(manager._tools) == 3

        assert any(v['instance'].__class__.__name__ == 'OneTool' for v in manager._tools.values())
        assert any(v['instance'].__class__.__name__ == 'TwoTool' for v in manager._tools.values())
        assert any(v['instance'].__class__.__name__ == 'ThreeTool' for v in manager._tools.values())
        assert any(v['instance'].__class__.__name__ != 'BadTool' for v in manager._tools.values())
        assert any(v['instance'].__class__.__name__ != 'BadImportTool' for v in manager._tools.values())
