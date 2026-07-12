"""Connect4 smart home chatbot — FastAPI application."""

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .config import settings
from .connect4 import make_hub
from .llm import LLMError, make_chat
from .network import WiFiGateMiddleware, effective_client_ip, wifi_status

logger = logging.getLogger("connect4")

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Connect4 Smart Home Chatbot")
app.add_middleware(WiFiGateMiddleware, settings=settings)

hub = make_hub(settings.connect4_mode, settings.connect4_hub_url)
if settings.sonos_enabled:
    from .sonos import SONOS_ID_PREFIX, CompositeHub, SonosBridge

    hub = CompositeHub(hub, {SONOS_ID_PREFIX: SonosBridge()})
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
        "sonos_enabled": settings.sonos_enabled,
        "access_code_required": settings.access_code is not None,
        "wifi": wifi_status(settings, effective_client_ip(request, settings)),
    }


@app.get("/api/ping")
async def ping():
    """Instant connectivity check: passes through every gate (WiFi gate,
    access code) but touches no devices, so it never waits on discovery."""
    return {"ok": True}


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
    except Exception as exc:
        # Any other failure (a device tool blowing up, etc.) must still come
        # back as JSON: an unhandled exception yields a plain-text 500 that
        # breaks the browser's response.json() and surfaces as a misleading
        # "could not reach the server" error instead of the real problem.
        logger.exception("chat_endpoint failed")
        raise HTTPException(status_code=500, detail=f"Something went wrong: {exc}") from exc
