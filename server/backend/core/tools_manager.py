import ast
import hashlib
import importlib.util
import os
import sys
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel, field_validator, ConfigDict

from core.agent_tool import AgentTool
from core.directory_file_manager import DirectoryFileManager, FileObjectIgnorer

if TYPE_CHECKING:
    from core.user import User


class ToolsFileIgnorer(FileObjectIgnorer):
    def file_ignored(self, file_path: str) -> bool:
        # we only want python files
        return Path(file_path).suffix != ".py"


class ToolInfo(BaseModel):
    """
    Holds information about an agent tool
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    """The name of the tool given be either the tools manager loader or the adding a tool"""
    name: str
    """"Instance of the tool for tools that are more one shots when no state, added at runtime"""
    instance: Optional[AgentTool | None] = None
    """Class type so we can instantiate them when run allowing for a clean state if the 
        agent needs to hold state because it may be interactive. Agents are loaded into this type"""
    class_type: Optional[type[AgentTool] | None] = None
    """Cached tools definition for the agent"""
    tool_definition: dict



    @field_validator('tool_definition')
    @classmethod
    def validate_tool_definition(cls, tool_definition: dict):
        """
        Validates the tool definition has at least the minimum required properties for tools
        """
        if 'type' not in tool_definition or tool_definition['type'] != 'function':
            raise ValueError('type not in definition or is not set to function')

        if 'function' not in tool_definition:
            raise ValueError('function not in definition')

        func = tool_definition['function']
        if 'name' not in func or 'description' not in func or 'parameters' not in func:
            raise ValueError('name, description or parameters not in function definition')
        params = func['parameters']
        if 'type' not in params or params['type'] != 'object':
            raise ValueError('type not in parameters definition or is not set to object')
        if 'properties' not in params or not isinstance(params['properties'], dict):
            raise ValueError('properties not in parameters or is not a dictionary')

        # TODO: we could add more validation to validate the properties themselves

        return tool_definition


class ToolsManager:
    """
    Class that handles loading and running agent tools
    """
    """Cached System loaded tools"""
    _system_tools: dict[str, ToolInfo] = {}

    def __init__(self):
        """Tools added to this instance"""
        self._tools: dict[str, ToolInfo] = {}
        """Tools that are in control the front is currently in control and once done 
            control is return to the next in the list. When empty the llm is in control"""
        self._in_control_tools: list[AgentTool] = []

    @classmethod
    def _find_tools_in_file(cls, tool_file: str) -> list:
        tools = []
        with open(tool_file, "r") as f:
            tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    if len(node.bases) == 0:
                        continue
                    for base in node.bases:
                        if isinstance(base, ast.Name) and base.id == "AgentTool":
                            tools.append(node.name)
        return tools

    @classmethod
    def _load_tools(cls, tools_path: str):
        if not os.path.exists(tools_path):
            raise FileNotFoundError(tools_path)

        scanner = DirectoryFileManager(tools_path, ignorers=[ToolsFileIgnorer()])
        scanner.scan_directory()

        # get the list of python files
        if len(scanner.file_list) == 0:
            return

        tools_to_module = {}
        # now check them to see if they have a tool(s) in them
        for file in scanner.file_list:
            tools = cls._find_tools_in_file(file)
            if len(tools) == 0:
                continue
            # we generate a unique name for the that will become part of the tool
            # name so that if we get classes with the same name they will be unique
            module_name = hashlib.sha256(str(file).encode()).hexdigest()
            tools_to_module[module_name] = {
                'path': file,
                'tools': tools
            }

        # now iterate over the list to load the tool modules and create instances of them
        for module_name, tools in tools_to_module.items():
            try:
                tools_spec = importlib.util.spec_from_file_location(module_name, tools['path'])
                tools_module = importlib.util.module_from_spec(tools_spec)
                tools_spec.loader.exec_module(tools_module)
                sys.modules[module_name] = tools_module
                for tool in tools['tools']:
                    tool_class = getattr(tools_module, tool)
                    tool_name = f'{module_name}.{tool}'
                    tool_info = ToolInfo(
                        name=tool_name,
                        class_type=tool_class,
                        tool_definition=tool_class.tools_definition(tool_name),
                    )
                    cls._system_tools[tool_name] = tool_info
            except Exception as e:
                print(f"Got an exception trying to import {tools['path']}")
                print(traceback.format_exc())

    @classmethod
    def load_tools(self, tools_path: str):
        self._load_tools('/app/tools')
        self._load_tools(tools_path)

    def _internal_add_tool(self, tool_info: ToolInfo) -> None:
        if tool_info.instance is None and tool_info.class_type is None:
            raise RuntimeError('Tool info must have either the instance or class_type set.')
        if tool_info.name in self._tools:
            raise RuntimeError(f'Tool {tool_info.name} already exists')

        self._tools[tool_info.name] = tool_info

    @property
    def is_tool_in_control(self):
        return len(self._in_control_tools) != 0

    def add_tool_instance(self, tool: AgentTool):
        if not isinstance(tool, AgentTool):
            raise RuntimeError('Tool is not an AgentTool')

        tools_def = tool.tools_definition(tool.name)
        self._internal_add_tool(
            ToolInfo(
                name=tool.name,
                instance=tool,
                tool_definition=tools_def,
            )
        )

    def add_tool_class(self, tool_name: str, tool: type[AgentTool]):
        if tool is None or not issubclass(tool, AgentTool):
            raise RuntimeError(f'Tool {tool_name} is not an AgentTool')
        tools_def = tool.tools_definition(tool_name)
        self._internal_add_tool(
            ToolInfo(
                name=tool_name,
                class_type=tool,
                tool_definition=tools_def,
            )
        )

    @property
    def get_tool_definitions(self):
        tool_defs = []
        for tool in self._tools.values():
            tool_defs.append(tool.tool_definition)
        return tool_defs

    def _find_tool(self, tool_name: str):
        if tool_name in self._tools:
            return self._tools[tool_name]
        if tool_name in self._system_tools:
            return self._system_tools[tool_name]
        return None

    @classmethod
    def _fill_missing_parameters(cls, run_parameters:list   , arguments:dict|list) -> dict:
        ret_dict={}
        # first extract all the parameters the function should have
        for param in run_parameters:
            # for a list we map the arguments into the order they appear in the
            # properties list
            if type(arguments) is list:
                ret_dict[param] = arguments.pop(0)
            elif type(arguments) is dict:
                if param in arguments:
                    ret_dict[param] = arguments[param]
                else:
                    ret_dict[param] = None
            else:
                # if not list or dict just set the first parameter to this argument
                # and everything else as none
                ret_dict[param] = arguments
                arguments = None

        # next gather the unknown ones
        if type(arguments) is list and arguments:
            ret_dict['args'] = []
            for item in arguments:
                ret_dict['args'].append(item)
        if type(arguments) is dict:
            for key, value in arguments.items():
                if key in ret_dict:
                    continue
                ret_dict[key] = value

        return ret_dict

    def _run_tool(self, user: 'User', tool: AgentTool, arguments) -> dict | None:
        """
        Core of running an agent tool
        """
        response = tool.run_tool(user, **self._fill_missing_parameters(tool.run_tool_arguments, arguments))

        if response.go_interactive:
            if response.interactive_agent is None:
                raise RuntimeError(f'go_interactive was requested by {tool.name} but no interactive agent was returned')
            if not isinstance(response.interactive_agent, AgentTool):
                raise RuntimeError(f'The interactive agent returned by {tool.name} is not an AgentTool')
            self._in_control_tools.append(response.interactive_agent)
        if response.interactive_done and self._in_control_tools:
            self._in_control_tools.pop(0)
        if response.message is not None:
            return {
                'role': 'tool',
                'tool_name': tool.name,
                'content': response.message,
            }
        return None

    def continue_tool(self, user: 'User', user_response: str) -> dict | None:
        """
        Continues running a tool that is interacting with the user
        """
        if not self._in_control_tools:
            raise RuntimeError('No tool is currently in control to continue')
        tool = self._in_control_tools[0]
        return self._run_tool(user, tool, {'user_response': user_response})

    def run_tool_call(self, user: 'User', tool_name: str, arguments) -> dict | None:
        """
        Rubs the tool requested by the llm
        """

        if self._in_control_tools:
            raise RuntimeError('Another tool is in control and we were not expecting to run a tool_call')

        tool_info = self._find_tool(tool_name)
        if tool_info is None:
            return {
                'role': 'tool',
                'tool_name': tool_name,
                'content': 'Unknown tool'
            }

        if tool_info.instance is not None:
            tool = tool_info.instance
        elif tool_info.class_type is not None:
            tool = tool_info.class_type(tool_name)
        else:
            return {
                'role': 'tool',
                'tool_name': tool_name,
                'content': "Couldn't run tool"
            }

        return self._run_tool(user, tool, arguments)
