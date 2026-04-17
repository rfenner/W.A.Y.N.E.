import ast
import hashlib
import importlib.util
import os
import sys
import traceback
from pathlib import Path

from core.agent_tool import AgentTool
from core.directory_file_manager import DirectoryFileManager, FileObjectIgnorer


class ToolsFileIgnorer(FileObjectIgnorer):
    def file_ignored(self, file_path: str) -> bool:
        # we only want python files
        return Path(file_path).suffix != ".py"


class ToolsManager:
    def __init__(self):
        self._tools = {}

    @staticmethod
    def _definition_valid(tools_def:dict) -> bool:
        if 'type' not in tools_def or tools_def['type'] != 'function':
            return False

        if 'function' not in tools_def:
            return False
        func = tools_def['function']
        if 'name' not in func or 'description' not in func or 'parameters' not in func:
            return False
        params = func['parameters']
        if 'type' not in params or params['type'] != 'object':
            return False
        if 'properties' not in params or not isinstance(params['properties'], dict):
            return False

        # TODO: we could add more validation to validate the properties themselves
        return True

    @staticmethod
    def _find_tools_in_file(tool_file:str)->list:
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


    def _load_tools(self, tools_path:str):
        if not os.path.exists(tools_path):
            raise FileNotFoundError(tools_path)

        scanner = DirectoryFileManager(tools_path, ignorers=[ToolsFileIgnorer()])
        scanner.scan_directory()

        # get the list of python files
        if len(scanner.file_list) == 0:
            return

        tools_to_module={}
        # now check them to see if they have a tool(s) in them
        for file in scanner.file_list:
            tools = self._find_tools_in_file(file)
            if len(tools) == 0:
                continue
            # we generate a unique name for the that will become part of the tool
            # name so that if we get classes with the same name they will be unique
            module_name = hashlib.sha256(str(file).encode()).hexdigest()
            tools_to_module[module_name] = {
                'path':file,
                'tools':tools
            }

        # now iterate over the list to load the tool modules and create instances of them
        for module_name, tools in tools_to_module.items():
            try:
                tools_spec = importlib.util.spec_from_file_location(module_name, tools['path'])
                tools_module =importlib.util.module_from_spec(tools_spec)
                tools_spec.loader.exec_module(tools_module)
                sys.modules[module_name] = tools_module
                for tool in tools['tools']:
                    tool_class = getattr(tools_module, tool)
                    tool_instance:AgentTool = tool_class()
                    tool_def = tool_instance.tools_definition()
                    if self._definition_valid(tool_def):
                        self._tools[f'{module_name}.{tool}'] = {
                            'instance':tool_instance,
                            'tool_def':tool_def,
                        }
            except Exception as e:
                print(f"Got an exception trying to import {tools['path']}")
                print(traceback.format_exc())

    def load_tools(self, tools_path:str):
        self._load_tools('/app/tools')
        self._load_tools(tools_path)

    @property
    def get_tool_definitions(self):
        tool_defs = []
        for tools in self._tools:
            tool_defs.append(tools['tool_def'])
        return tool_defs

    def is_tool(self, tool_name:str):
        return tool_name in self._tools

    def run_tool(self, tool_name:str, **args):
        if tool_name not in self._tools:
            raise KeyError(tool_name)
        return self.tools[tool_name]['instance'](**args)