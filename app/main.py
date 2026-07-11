"""Connect4 smart home chatbot — FastAPI application."""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .config import settings
from .connect4 import make_hub
from .llm import LLMError, make_chat
from .network import WiFiGateMiddleware, effective_client_ip, wifi_status

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Connect4 Smart Home Chatbot")
app.add_middleware(WiFiGateMiddleware, settings=settings)

hub = make_hub(settings.connect4_mode, settings.connect4_hub_url)
chat = make_chat(settings)


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/status")
async def status(request: Request):
    return {
        "system": "Connect4",
        "model": chat.model,
        "hub_mode": settings.connect4_mode,
        "wifi": wifi_status(settings, effective_client_ip(request, settings)),
    }


@app.get("/api/devices")
async def devices():
    return {"devices": [d.model_dump() for d in await hub.list_devices()]}


@app.post("/api/chat")
async def chat_endpoint(body: ChatRequest):
    messages = [m.model_dump() for m in body.messages]
    try:
        return await chat.respond(hub, messages)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
