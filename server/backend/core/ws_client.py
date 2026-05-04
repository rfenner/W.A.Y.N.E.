import asyncio

from starlette.websockets import WebSocket

from core.client import Client


class WSClient(Client):
    def __init__(self, ws: WebSocket):
        super().__init__(ws.query_params.get('co', 'html'))
        self.ws: WebSocket = ws
        self._queue: asyncio.Queue = asyncio.Queue()
        self._queue_task = asyncio.create_task(self._send_queue())

    @property
    def websocket(self) -> WebSocket:
        return self.ws

    async def _send_queue(self):
        while True:
            message = await self._queue.get()
            await self.ws.v(message)
            self._queue.task_done()


    def send_output(self, msg: str):
        self._queue.put_nowait(msg)

    async def receive_input(self):
        return await self.ws.receive_text()

