import pytest

from agent.chat_history import ChatHistory
from agent.executor import Executor
from agent.planner import Planner
from agent.verifier import Verifier
from core.user import User
from llm.local_llm_client import LocalLLMClient
from tests.conftest import ClientTestOutput


class TestUser:
    @pytest.fixture(scope='function', autouse=True)
    def setup_teardown(self):
        self.client = ClientTestOutput()

    def test_init(self):
        user = User(self.client)

        assert user.client == self.client
        assert user.repo is None
        assert isinstance(user.chat_history, ChatHistory)
        assert user.editor is None
        assert user._repo_agents == {}
        user.send_output('test')
        assert self.client.output == 'test'
        assert isinstance(user._planner, Planner)
        assert isinstance(user._executor, Executor)
        assert isinstance(user._verifier, Verifier)
        assert isinstance(user._llm_client, LocalLLMClient)

    def test_receive_query(self):
        user = User(self.client)


