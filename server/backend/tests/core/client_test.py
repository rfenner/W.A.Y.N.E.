from core.client import Client, ClientOutputFormat


class ClientTestTest(Client):
    def __init__(self, output_format: ClientOutputFormat):
        super().__init__(output_format)
        self.output = ''

    def send_output(self, msg: str):
        self.output = msg


class TestClient:
    def test_client_text(self):
        client = ClientTestTest(ClientOutputFormat.TEXT)
        assert client.output_format == ClientOutputFormat.TEXT
        assert client.is_html_format is False
        assert client.is_text_format is True
        client.send_output('hello')
        assert client.output == 'hello'

    def test_client_html(self):
        client = ClientTestTest(ClientOutputFormat.HTML)
        assert client.output_format == ClientOutputFormat.HTML
        assert client.is_html_format is True
        assert client.is_text_format is False
