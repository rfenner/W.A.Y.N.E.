from core.agent_tool import AgentTool


class BadTool(AgentTool):
    @classmethod
    def _generate_parameters(cls) -> dict:
        return {
            'type': 'object',
            'properties': {
                'test': {'type': 'string', 'description': 'Test description'},
            }
        }

    def run_tool(self, *args, **kwargs) -> dict:
        return {'result': 'OneTool Ran'}
