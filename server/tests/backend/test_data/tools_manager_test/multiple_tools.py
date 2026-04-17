from core.agent_tool import AgentTool


class TwoTool(AgentTool):
    def tools_definition(self) -> dict:
        return {
            'type': 'function',
            'function': {
                'name': 'TwoTool',
                'description': 'Test Two description',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'test': {'type': 'string', 'description': 'Test description'},
                    }
                }
            }

        }

    def run_tool(self, *args, **kwargs) -> dict:
        return {'result':'TwoTool Ran'}

class ThreeTool(AgentTool):
    def tools_definition(self) -> dict:
        return {
            'type': 'function',
            'function': {
                'name': 'ThreeTool',
                'description': 'Test Three description',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'test': {'type': 'string', 'description': 'Test description'},
                    }
                }
            }

        }

    def run_tool(self, *args, **kwargs) -> dict:
        return {'result': 'ThreeTool Ran'}
