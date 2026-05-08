from unittest.mock import patch

import ollama
import pytest
from ollama import ChatResponse, Message, GenerateResponse
from pydantic import BaseModel, Field

from config import OLLAMA_MODEL
from core.agent_tool import AgentTool
from core.tools_manager import ToolsManager
from core.user import User
from llm.local_llm_client import LocalLLMClient
from tests.conftest import ClientTestOutput


class LocalLLMClientTestToolNModel(BaseModel):
    num:int = Field(description='The number')

class LocaLLMClientTestTool(AgentTool):
    """
    Local llm client test tool
    """
    @classmethod
    def _generate_parameters(cls) -> dict:
        return LocalLLMClientTestToolNModel.model_json_schema()

    # noinspection PyMethodOverriding
    def run_tool(self, user, num) -> str:
        return f'test tool {num}'


class TestLocalLLMClient:
    @pytest.fixture(scope='function', autouse=True)
    def setup_teardown(self):
        self.user = User(ClientTestOutput())
        self.tool_manager = ToolsManager()
        self.tool_manager.add_tool_instance(LocaLLMClientTestTool('llm_test_tool'))
        yield

    def test_init(self):
        llm = LocalLLMClient()
        assert llm.model_name == OLLAMA_MODEL
        assert isinstance(llm.client, ollama.Client)

        llm = LocalLLMClient('test')
        assert llm.model_name == 'test'

    def test_generate_text_exception_no_capture(self):
        with patch('llm.local_llm_client.ollama.Client') as mock_ollama:
            llm = LocalLLMClient()
            ollama_instance = mock_ollama.return_value
            ollama_instance.generate.return_value = Exception('Test Exception')

            result = llm.generate_text(self.user, 'test', capture=False)
            assert result is None
            # noinspection PyUnresolvedReferences
            assert '[ERROR] LLM inference failed:' in self.user.client.output

    def test_generate_text_exception_capture(self):
        with patch('llm.local_llm_client.ollama.Client') as mock_ollama:
            llm = LocalLLMClient()
            ollama_instance = mock_ollama.return_value
            ollama_instance.generate.return_value = Exception('Test Exception')

            result = llm.generate_text(self.user, 'test')
            assert '[ERROR] LLM inference failed:' in result

    def test_generate_text_no_stream_no_capture(self):
        with patch('llm.local_llm_client.ollama.Client') as mock_ollama:
            llm = LocalLLMClient()
            ollama_instance = mock_ollama.return_value
            ollama_instance.generate.return_value = GenerateResponse(
                response='Testing'
            )

            result = llm.generate_text(self.user, 'test', capture=False)
            assert result == ''
            # noinspection PyUnresolvedReferences
            assert self.user.client.output == 'Testing'

    def test_generate_text_no_stream_capture(self):
        with patch('llm.local_llm_client.ollama.Client') as mock_ollama:
            llm = LocalLLMClient()
            ollama_instance = mock_ollama.return_value
            ollama_instance.generate.return_value = GenerateResponse(
                response='Testing'
            )

            result = llm.generate_text(self.user, 'test')
            assert result == 'Testing'

    def test_generate_text_stream_no_capture(self):
        with patch('llm.local_llm_client.ollama.Client') as mock_ollama:
            llm = LocalLLMClient()
            ollama_instance = mock_ollama.return_value
            ollama_instance.generate.return_value = [
                GenerateResponse(

                    thinking='Thinking 1',
                    response='Testing 1'
                ),
                GenerateResponse(
                    thinking='Thinking 2',
                    response='Testing 2'
                ),
            ]

        result = llm.generate_text(self.user, 'test', stream=True, capture=False)
        assert result == ''
        # noinspection PyUnresolvedReferences
        assert self.user.client.output == '[THINKING]: Thinking 1\nTesting 1\n[THINKING]: Thinking 2\nTesting 2'

    def test_generate_text_stream_capture(self):
        with patch('llm.local_llm_client.ollama.Client') as mock_ollama:
            llm = LocalLLMClient()
            ollama_instance = mock_ollama.return_value
            ollama_instance.generate.return_value = [
                GenerateResponse(
                    thinking='Thinking 1',
                    response='Testing'
                ),
                GenerateResponse(
                    thinking='Thinking 2',
                    response='Testing 2'
                ),
            ]

            result = llm.generate_text(self.user, 'test', stream=True)
            assert result == 'TestingTesting 2'
            # noinspection PyUnresolvedReferences
            assert self.user.client.output == ''

    def test_chat_exception(self):
        with patch('llm.local_llm_client.ollama.Client') as mock_ollama:
            llm = LocalLLMClient()
            ollama_instance = mock_ollama.return_value
            ollama_instance.chat.return_value = Exception('Test Exception')
            result = llm.chat(self.user, 'test')
            assert '[ERROR] Chat inference failed: ' in result

    def test_chat_no_stream(self):
        with patch('llm.local_llm_client.ollama.Client') as mock_ollama:
            llm = LocalLLMClient()
            ollama_instance = mock_ollama.return_value
            ollama_instance.chat.return_value = ChatResponse(message=Message(
                role='user', content='test', thinking='Thinking 1'
            ), done=True)

            result = llm.chat(self.user, 'test')
            assert result == []
            # noinspection PyUnresolvedReferences
            assert self.user.client.output == '[THINKING]: Thinking 1\ntest'

    def test_chat_stream(self):
        with patch('llm.local_llm_client.ollama.Client') as mock_ollama:
            llm = LocalLLMClient()
            ollama_instance = mock_ollama.return_value
            ollama_instance.chat.return_value = [
                ChatResponse(message=Message(
                    role='user', content='test'
                )),
                ChatResponse(message=Message(
                    role='user', content='test 2'
                ), done=True)
            ]

            result = llm.chat(self.user, 'test', stream=True)
            assert result == []
            # noinspection PyUnresolvedReferences
            assert self.user.client.output == 'testtest 2'

    def test_chat_no_stream_tool_call(self):
        with patch('llm.local_llm_client.ollama.Client') as mock_ollama:
            llm = LocalLLMClient(tools=self.tool_manager)
            ollama_instance = mock_ollama.return_value
            ollama_instance.chat.side_effect = [
                ChatResponse(message=Message(
                    role='user', content='test',
                    tool_calls=[Message.ToolCall(function=Message.ToolCall.Function(
                        name='llm_test_tool', arguments={'num': 1}
                    ))]
                )),
                ChatResponse(message=Message(
                    role='user', content='test tool'
                ), done=True)
            ]

            result = llm.chat(self.user, 'test')
            assert len(result) == 1
            assert result[0].function.name == 'llm_test_tool'
            assert result[0].function.arguments['num'] == 1
            # noinspection PyUnresolvedReferences
            assert len(self.user.chat_history) == 2
            assert self.user.chat_history[0] == {'content': 'test', 'role': 'user'}
            assert self.user.chat_history[1]['role'] == 'user'
            assert self.user.chat_history[1]['content'] == 'test'
            assert self.user.chat_history[1]['thinking'] == ''
            assert len(self.user.chat_history[1]['tool_calls']) == 1
            assert self.user.chat_history[1]['tool_calls'][0].function.name == 'llm_test_tool'
            assert self.user.chat_history[1]['tool_calls'][0].function.arguments['num'] == 1


    def test_chat_stream_tool_call(self):
        with patch('llm.local_llm_client.ollama.Client') as mock_ollama:
            llm = LocalLLMClient(tools=self.tool_manager)
            ollama_instance = mock_ollama.return_value
            ollama_instance.chat.side_effect = [
                [
                    ChatResponse(message=Message(
                        role='user', content='test 1'
                    )),
                    ChatResponse(message=Message(
                        role='user', thinking='thinking'
                    )),
                    ChatResponse(message=Message(
                        role='user', content='test 2',
                        tool_calls=[Message.ToolCall(function=Message.ToolCall.Function(
                            name='llm_test_tool', arguments={'num': 2}
                        ))]
                    ))
                ],
                [
                    ChatResponse(message=Message(
                        role='user', content='test tool'
                    ), done=True)
                ]
            ]

            result = llm.chat(self.user, 'test', stream=True)
            assert len(result) == 1
            assert result[0].function.name == 'llm_test_tool'
            assert result[0].function.arguments['num'] == 2
            # noinspection PyUnresolvedReferences
            assert len(self.user.chat_history) == 2
            assert self.user.chat_history[0] == {'content': 'test', 'role': 'user'}
            assert self.user.chat_history[1]['role'] == 'user'
            assert self.user.chat_history[1]['content'] == 'test 1test 2'
            assert self.user.chat_history[1]['thinking'] == 'thinking'
            assert len(self.user.chat_history[1]['tool_calls']) == 1
            assert self.user.chat_history[1]['tool_calls'][0].function.name == 'llm_test_tool'
            assert self.user.chat_history[1]['tool_calls'][0].function.arguments['num'] == 2
