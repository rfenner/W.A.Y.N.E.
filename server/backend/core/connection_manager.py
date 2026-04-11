from starlette.websockets import WebSocket


class WSConnectionManager:
    _active_connections = []

    @classmethod
    async def connect(cls,ws:WebSocket)->'Client':
        # we put the import here to prevent circular references
        from core.client import Client

        await ws.accept()
        client = Client(ws)
        cls._active_connections.append(client)
        return client

    @classmethod
    async def disconnect(cls,ws:WebSocket):
        for client in cls._active_connections:
            if client.websocket == ws:
                cls._active_connections.remove(client)
                return

    @classmethod
    async def broadcast(cls, message:str):
        for client in cls._active_connections:
            await client.send_text(message)
