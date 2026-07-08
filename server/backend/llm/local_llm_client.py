from typing import TYPE_CHECKING

import ollama
from config import OLLAMA_MODEL, OLLAMA_BASE_URL
from core.tools_manager import ToolsManager

if TYPE_CHECKING:
    from core.user import User


class LocalLLMClient:
    """
    Client for local LLM inference via Ollama.
    Uses the official ollama Python library.
    """

    def __init__(self, model:str=OLLAMA_MODEL, tools:ToolsManager=ToolsManager()):
        self.model_name = model
        self._tools = tools
        self.client = ollama.Client(host=OLLAMA_BASE_URL)

    def generate_system_text(self, prompt: str, system_prompt: str | None=None, max_tokens: int = 1024, temperature: float = 0.7) -> str:
        kwargs = {
            "model": self.model_name,
            "prompt": prompt,
            'options': {"temperature": temperature, "num_predict": max_tokens},
        }
        if system_prompt is not None:
            kwargs['system'] = system_prompt

        response = self.client.generate(**kwargs)

        return response['response']

    def generate_user_text(self, client: 'Client', prompt: str, system_prompt: str | None=None, max_tokens: int = 1024, temperature: float = 0.7, stream:bool=False, capture:bool=True):
        """
        Generates a text response from the llm model and can capture the output or send it
        directly to the client.
        client: the ws client
        prompt: the user;s prompt
        max_tokens: the maximum number of tokens to generate
        temperature: the temperature to use
        stream: whether to stream the response
        capture: whether to capture the response or send it directly to the client
        """
        try:
            kwargs = {
                "model": self.model_name,
                "prompt": prompt,
                'options':{"temperature": temperature, "num_predict": max_tokens},
                'stream':stream
            }
            if system_prompt is not None:
                kwargs['system'] = system_prompt

            response_chunk = self.client.generate(**kwargs)
            content =''
            in_thinking = False
            content_sent = False
            if stream:
                for chunk in response_chunk:
                    if chunk.thinking:
                        if not capture:
                            if content_sent:
                                client.send_output("\n")
                            content_sent = False
                            if not in_thinking:
                                in_thinking = True
                                client.send_output("[THINKING]: ")
                            client.send_output(chunk.thinking.strip())
                            if chunk.response:
                                client.send_output("\n")
                    if chunk.response:
                        content_sent = True
                        in_thinking = False
                        if not capture:
                            client.send_output(chunk.response.strip())
                        else:
                            content += chunk.response.strip()
            else:
                if not capture:
                    client.send_output(response_chunk.response.strip())
                else:
                    content = response_chunk['response'].strip()
            return content
        except Exception as e:
            if not capture:
                client.send_output(f"[ERROR] LLM inference failed: {str(e)}")
            else:
                return f"[ERROR] LLM inference failed: {str(e)}"

    def generate_text_old(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.7) -> str:
        """Generate text using local model. Returns full response string."""
        try:
            response = self.client.generate(
                model=self.model_name,
                prompt=prompt,
                options={"temperature": temperature, "num_predict": max_tokens}
            )
            return response["response"].strip()
        except Exception as e:
            return f"[ERROR] LLM inference failed: {str(e)}"

    def generate_text_stream(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.7):
        """Generate text with streaming. Yields text chunks."""
        try:
            stream = self.client.generate(
                model=self.model_name,
                prompt=prompt,
                stream=True,
                options={"temperature": temperature, "num_predict": max_tokens}
            )
            for chunk in stream:
                token = chunk.get("response", "")
                if token:
                    yield token
        except Exception as e:
            yield f"[ERROR] LLM inference failed: {str(e)}"

    def chat(self, user:'User', query:str, temperature:float=0.7, stream:bool=False):
        try:
            client = user.client
            messages = user.chat_history
            messages.append({'role':'user', 'content':query})

            kwargs = {
                "model": self.model_name,
                "messages": messages,
                "options": {"temperature": temperature},
                'stream':stream
            }
            response = self.client.chat(**kwargs)

            thinking = ''
            content = ''
            tools = []
            in_thinking = False
            content_sent = False

            if stream:
                for chunk in response:
                    done = chunk.done
                    if chunk.message.thinking:
                        thinking += chunk.message.thinking
                        if content_sent:
                            client.send_output("\n")
                            content_sent = False
                        if not in_thinking:
                            in_thinking = True
                            client.send_output("[THINKING]: ")
                        client.send_output(chunk.message.thinking.strip())
                        if chunk.message.content:
                            client.send_output("\n")
                    if chunk.message.content:
                        in_thinking = False
                        content_sent = True
                        content += chunk.message.content
                        client.send_output(chunk.message.content)
                    if chunk.message.tool_calls:
                        tools.extend(chunk.message.tool_calls)
            else:
                done = response.done
                if response.message.thinking:
                    thinking += response.message.thinking
                    client.send_output(f"[THINKING]: {response.message.thinking}")
                if response.message.content:
                    if response.message.thinking:
                        client.send_output("\n")
                    content += response.message.content
                    client.send_output(response.message.content)
                if response.message.tool_calls:
                    tools.extend(response.message.tool_calls)

            if thinking or content or tools:
                messages.append({'role':'user', 'thinking':thinking, 'content':content, 'tool_calls':tools})

            return tools

        except Exception as e:
            return f"[ERROR] Chat inference failed: {str(e)}"

    def chat_old(self, messages: list, temperature: float = 0.7, json_mode: bool = False) -> str:
        """
        Chat-style generation. Optionally enforces JSON output.
        messages: list of {"role": "...", "content": "..."} dicts
        """
        try:
            kwargs = {
                "model": self.model_name,
                "messages": messages,
                "options": {"temperature": temperature}
            }
            if json_mode:
                kwargs["format"] = "json"
            response = self.client.chat(**kwargs)
            return response["message"]["content"].strip()
        except Exception as e:
            return f"[ERROR] Chat inference failed: {str(e)}"
