from collections.abc import Mapping
from unittest.mock import patch

import ollama
import pytest
from ollama import ChatResponse, Message, GenerateResponse

from config import OLLAMA_MODEL
from core.agent_tool import AgentTool
from core.tools_manager import ToolsManager
from llm.local_llm_client import LocalLLMClient
from tests.conftest import ClientTestOutput


class LocaLLMClientTestTool(AgentTool):
    def tools_definition(self) -> dict:
        return {}

    def run_tool(self, num) -> str:
        return f'test tool {num}'


class TestLocalLLMClient:
    @pytest.fixture(scope='function', autouse=True)
    def setup_teardown(self):
        self.client = ClientTestOutput()
        self.tool_manager = ToolsManager()
        self.tool_manager.add_tool('llm_test_tool', LocaLLMClientTestTool())
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

            result = llm.generate_text(self.client, 'test', capture=False)
            assert result is None
            assert '[ERROR] LLM inference failed:' in self.client.output

    def test_generate_text_exception_capture(self):
        with patch('llm.local_llm_client.ollama.Client') as mock_ollama:
            llm = LocalLLMClient()
            ollama_instance = mock_ollama.return_value
            ollama_instance.generate.return_value = Exception('Test Exception')

            result = llm.generate_text(self.client, 'test')
            assert '[ERROR] LLM inference failed:' in result

    def test_generate_text_no_stream_no_capture(self):
        with patch('llm.local_llm_client.ollama.Client') as mock_ollama:
            llm = LocalLLMClient()
            ollama_instance = mock_ollama.return_value
            ollama_instance.generate.return_value = GenerateResponse(
                response='Testing'
            )

            result = llm.generate_text(self.client, 'test', capture=False)
            assert result == ''
            assert self.client.output == 'Testing'

    def test_generate_text_no_stream_capture(self):
        with patch('llm.local_llm_client.ollama.Client') as mock_ollama:
            llm = LocalLLMClient()
            ollama_instance = mock_ollama.return_value
            ollama_instance.generate.return_value = GenerateResponse(
                response='Testing'
            )

            result = llm.generate_text(self.client, 'test')
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

        result = llm.generate_text(self.client, 'test', stream=True, capture=False)
        assert result == ''
        assert self.client.output == '[THINKING]: Thinking 1\nTesting 1\n[THINKING]: Thinking 2\nTesting 2'

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

            result = llm.generate_text(self.client, 'test', stream=True)
            assert result == 'TestingTesting 2'
            assert self.client.output == ''

    def test_chat_exception(self):
        with patch('llm.local_llm_client.ollama.Client') as mock_ollama:
            llm = LocalLLMClient()
            ollama_instance = mock_ollama.return_value
            ollama_instance.chat.return_value = Exception('Test Exception')

            result = llm.chat(self.client, [{'role': 'user', 'content': 'test'}])
            assert '[ERROR] Chat inference failed: ' in result

    def test_chat_no_stream(self):
        with patch('llm.local_llm_client.ollama.Client') as mock_ollama:
            llm = LocalLLMClient()
            ollama_instance = mock_ollama.return_value
            ollama_instance.chat.return_value = ChatResponse(message=Message(
                role='user', content='test', thinking='Thinking 1'
            ), done=True)

            messages = [{'role': 'user', 'content': 'test'}]

            result = llm.chat(self.client, messages)
            assert result is None
            assert self.client.output == '[THINKING]: Thinking 1\ntest'

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
            messages = [{'role': 'user', 'content': 'test'}]

            result = llm.chat(self.client, messages, stream=True)
            assert result is None
            assert self.client.output == 'testtest 2'

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
            messages = [{'role': 'user', 'content': 'test'}]

            result = llm.chat(self.client, messages)
            assert result is None
            assert self.client.output == 'testtest tool'
            assert len(messages) == 4
            assert messages[2] == {'content': 'test tool 1', 'role': 'tool', 'tool_name': 'llm_test_tool'}

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
                        role='user', content='test 2',
                        tool_calls=[Message.ToolCall(function=Message.ToolCall.Function(
                            name='llm_test_tool', arguments={'num': 1}
                        ))]
                    ))
                ],
                [
                    ChatResponse(message=Message(
                        role='user', content='test tool'
                    ), done=True)
                ]
            ]
            messages = [{'role': 'user', 'content': 'test'}]

            result = llm.chat(self.client, messages, stream=True)
            assert result is None
            assert self.client.output == 'test 1test 2test tool'
            assert len(messages) == 4
            assert messages[2] == {'content': 'test tool 1', 'role': 'tool', 'tool_name': 'llm_test_tool'}
