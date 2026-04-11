from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket, WebSocketDisconnect

from core.connection_manager import WSConnectionManager
from core.repo_registry import RepositoryRegistry

@asynccontextmanager
async def lifespan(app:FastAPI):
    RepositoryRegistry.load_repositories()
    yield

app = FastAPI(lifespan=lifespan)


@app.websocket("/ws")
async def ws(ws: WebSocket):
    client = await WSConnectionManager.connect(ws)
    try:
        while True:
            await client.receive_query()

    except WebSocketDisconnect:
        await WSConnectionManager.disconnect(ws)
    return {"message": "Hello World"}

#has to be mounted last
app.mount("/", StaticFiles(directory="static", html=True), name="static")
