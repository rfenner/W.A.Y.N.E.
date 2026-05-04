import pytest

from core.client import Client, ClientOutputFormat


class ClientTestTest(Client):
    def __init__(self, output_format: ClientOutputFormat):
        super().__init__(output_format)
        self.output = ''
        self.input = 'Test'

    def send_output(self, msg: str):
        self.output = msg

    async def receive_input(self):
        return self.input

class TestClient:
    @pytest.mark.asyncio
    async def test_client_text(self):
        client = ClientTestTest(ClientOutputFormat.TEXT)
        assert client.output_format == ClientOutputFormat.TEXT
        assert client.is_html_format is False
        assert client.is_text_format is True
        client.send_output('hello')
        assert client.output == 'hello'
        assert await client.receive_input() == 'Test'

    def test_client_html(self):
        client = ClientTestTest(ClientOutputFormat.HTML)
        assert client.output_format == ClientOutputFormat.HTML
        assert client.is_html_format is True
        assert client.is_text_format is False
