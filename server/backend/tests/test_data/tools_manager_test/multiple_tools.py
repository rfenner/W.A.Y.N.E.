from core.agent_tool import AgentTool


class TwoTool(AgentTool):
    """
    Agent test tool two
    """
    @classmethod
    def _generate_parameters(cls) -> dict:
        return {
            'type': 'object',
            'properties': {
                'test': {'type': 'string', 'description': 'Test description'},
            }
        }

    def run_tool(self, *args, **kwargs) -> dict:
        return {'result': 'TwoTool Ran'}


class ThreeTool(AgentTool):
    """
    Agent test tool three
    """
    @classmethod
    def _generate_parameters(cls) -> dict:
        return {
            'type': 'object',
            'properties': {
                'test': {'type': 'string', 'description': 'Test description'},
            }
        }

    def run_tool(self, *args, **kwargs) -> dict:
        return {'result': 'ThreeTool Ran'}
