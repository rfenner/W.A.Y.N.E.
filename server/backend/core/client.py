from abc import ABC, abstractmethod
from enum import Enum


class ClientOutputFormat(Enum):
    HTML = "html"
    TEXT = "text"

class Client(ABC):
    def __init__(self, output_format: ClientOutputFormat|str):
        self._client_output = output_format

    @property
    def output_format(self):
        return self._client_output

    @property
    def is_html_format(self):
        return self._client_output == ClientOutputFormat.HTML

    @property
    def is_text_format(self):
        return self._client_output == ClientOutputFormat.TEXT

    @abstractmethod
    def send_output(self, msg: str):
        pass

    @abstractmethod
    async def receive_input(self):
        pass

