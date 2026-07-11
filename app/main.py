"""Connect4 smart home chatbot — FastAPI application."""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .config import settings
from .connect4 import make_hub
from .llm import LLMError, OllamaChat
from .network import WiFiGateMiddleware, wifi_status

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Connect4 Smart Home Chatbot")
app.add_middleware(WiFiGateMiddleware, settings=settings)

hub = make_hub(settings.connect4_mode, settings.connect4_hub_url)
chat = OllamaChat(settings.ollama_url, settings.ollama_model)


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
    client_ip = request.client.host if request.client else None
    return {
        "system": "Connect4",
        "model": settings.ollama_model,
        "hub_mode": settings.connect4_mode,
        "wifi": wifi_status(settings, client_ip),
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
