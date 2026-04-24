from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket, WebSocketDisconnect

from config import REPOSITORIES_DIR
from core.connection_manager import WSConnectionManager
from core.repo_registry import RepositoryRegistry
from core.user import User


@asynccontextmanager
async def lifespan(app:FastAPI):
    RepositoryRegistry.load_repositories(REPOSITORIES_DIR)
    yield

app = FastAPI(lifespan=lifespan)


@app.websocket("/ws")
async def ws(ws: WebSocket):
    client = await WSConnectionManager.connect(ws)
    user = User(client)
    try:
        while True:
            await user.receive_query()

    except WebSocketDisconnect:
        await WSConnectionManager.disconnect(ws)
        del user
    return {"message": "Hello World"}

#has to be mounted last
app.mount("/", StaticFiles(directory="static", html=True), name="static")
