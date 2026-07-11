"""Tests for proxy-aware WiFi gating and the OpenAI-compatible LLM client."""

import json
from ipaddress import ip_network

import httpx
import pytest

import app.main as main_app
from app.config import Settings
from app.connect4 import SimulatedConnect4Hub
from app.llm import OpenAICompatChat, make_chat


def make_settings(**overrides) -> Settings:
    s = Settings()
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


class TestProxyHeaderGate:
    """On Vercel the TCP peer is the proxy; the real caller is in
    X-Forwarded-For. The gate only trusts it when TRUST_PROXY_HEADER is on."""

    @pytest.fixture
    def proxied_app(self, monkeypatch):
        monkeypatch.setattr(main_app, "hub", SimulatedConnect4Hub())
        monkeypatch.setattr(main_app.settings, "trust_proxy_header", True)
        monkeypatch.setattr(
            main_app.settings,
            "allowed_subnets",
            [ip_network("198.51.100.7/32")],  # "home public IP"
        )
        return main_app.app

    def proxy_client(self, app, forwarded_for: str) -> httpx.AsyncClient:
        transport = httpx.ASGITransport(app=app, client=("203.0.113.1", 443))
        return httpx.AsyncClient(
            transport=transport,
            base_url="http://x.vercel.app",
            headers={"x-forwarded-for": forwarded_for},
        )

    @pytest.mark.asyncio
    async def test_request_from_home_public_ip_allowed(self, proxied_app):
        async with self.proxy_client(proxied_app, "198.51.100.7") as client:
            resp = await client.get("/api/devices")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_request_from_elsewhere_blocked(self, proxied_app):
        async with self.proxy_client(proxied_app, "203.0.113.99") as client:
            resp = await client.get("/api/devices")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_header_ignored_when_not_trusted(self, monkeypatch):
        monkeypatch.setattr(main_app.settings, "trust_proxy_header", False)
        transport = httpx.ASGITransport(app=main_app.app, client=("203.0.113.1", 443))
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://x.local",
            # Spoofed header must NOT bypass the gate when trust is off.
            headers={"x-forwarded-for": "192.168.1.5"},
        ) as client:
            resp = await client.get("/api/devices")
        assert resp.status_code == 403


class TestOpenAICompatChat:
    @pytest.mark.asyncio
    async def test_tool_loop_against_mock_api(self):
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            calls.append(body)
            if not any(m.get("role") == "tool" for m in body["messages"]):
                message = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "set_light",
                                # OpenAI-style: arguments as a JSON string
                                "arguments": json.dumps(
                                    {"device_id": "light-bedroom", "power": True}
                                ),
                            },
                        }
                    ],
                }
            else:
                message = {"role": "assistant", "content": "Bedroom light is on."}
            return httpx.Response(200, json={"choices": [{"message": message}]})

        chat = OpenAICompatChat("https://mock.api/v1", "key", "llama-3.1-8b-instant")
        chat._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://mock.api/v1"
        )

        hub = SimulatedConnect4Hub()
        result = await chat.respond(
            hub, [{"role": "user", "content": "bedroom light on"}]
        )

        assert result["reply"] == "Bedroom light is on."
        assert result["actions"][0]["result"]["ok"] is True
        assert (await hub.get_device("light-bedroom")).power is True
        # second request carried the tool result back with the call id
        tool_msg = next(m for m in calls[1]["messages"] if m["role"] == "tool")
        assert tool_msg["tool_call_id"] == "call_1"


class TestMakeChat:
    def test_defaults_to_ollama(self):
        chat = make_chat(make_settings(openai_api_key=None))
        assert type(chat).__name__ == "OllamaChat"

    def test_api_key_selects_hosted_provider(self):
        chat = make_chat(make_settings(openai_api_key="sk-x", openai_model="m"))
        assert isinstance(chat, OpenAICompatChat)
        assert chat.model == "m"
