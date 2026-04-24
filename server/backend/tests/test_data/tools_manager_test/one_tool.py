from core.agent_tool import AgentTool


class OneTool(AgentTool):
    def tools_definition(self) -> dict:
        return {
            'type': 'function',
            'function': {
                'name': 'OneTool',
                'description': 'Test One description',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'test': {'type': 'string', 'description': 'Test description'},
                    }
                }
            }

        }

    def run_tool(self, *args, **kwargs) -> dict:
        return {'result': 'OneTool Ran'}
