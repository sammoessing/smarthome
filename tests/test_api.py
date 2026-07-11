"""End-to-end API tests: WiFi gate + chat endpoint with a fake LLM."""

import httpx
import pytest

import app.main as main_app
from app.connect4 import SimulatedConnect4Hub


class FakeOllama:
    """Stands in for OllamaChat: turns on the living room light, then replies."""

    model = "fake-llm"

    async def respond(self, hub, messages):
        result_device = await hub.apply("light-living", {"power": True})
        return {
            "reply": "Done — the living room light is on.",
            "actions": [
                {
                    "tool": "set_light",
                    "args": {"device_id": "light-living", "power": True},
                    "result": {"ok": True, "device": result_device.model_dump()},
                }
            ],
        }


@pytest.fixture
def fresh_app(monkeypatch):
    monkeypatch.setattr(main_app, "hub", SimulatedConnect4Hub())
    monkeypatch.setattr(main_app, "chat", FakeOllama())
    return main_app.app


def client_from(app, ip: str) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app, client=(ip, 12345))
    return httpx.AsyncClient(transport=transport, base_url="http://connect4.local")


class TestWiFiGate:
    @pytest.mark.asyncio
    async def test_home_wifi_client_can_chat(self, fresh_app):
        async with client_from(fresh_app, "192.168.1.20") as client:
            resp = await client.post(
                "/api/chat",
                json={"messages": [{"role": "user", "content": "lights on"}]},
            )
        assert resp.status_code == 200
        assert "living room light" in resp.json()["reply"].lower()

    @pytest.mark.asyncio
    async def test_external_client_blocked_everywhere(self, fresh_app):
        async with client_from(fresh_app, "203.0.113.50") as client:
            for path, method, body in [
                ("/api/chat", "POST", {"messages": [{"role": "user", "content": "hi"}]}),
                ("/api/devices", "GET", None),
                ("/api/status", "GET", None),
                ("/", "GET", None),
            ]:
                resp = await (
                    client.post(path, json=body) if method == "POST" else client.get(path)
                )
                assert resp.status_code == 403, path
                assert resp.json()["error"] == "not_on_home_wifi"

    @pytest.mark.asyncio
    async def test_server_off_required_ssid_disables_control(self, fresh_app, monkeypatch):
        monkeypatch.setattr(main_app.settings, "required_ssid", "HomeNet")
        monkeypatch.setattr("app.network.current_ssid", lambda: None)
        async with client_from(fresh_app, "192.168.1.20") as client:
            resp = await client.post(
                "/api/chat",
                json={"messages": [{"role": "user", "content": "lights on"}]},
            )
            assert resp.status_code == 503
            # status endpoint still reachable so the UI can explain
            status = await client.get("/api/status")
            assert status.status_code == 200
            assert status.json()["wifi"]["server_ssid_ok"] is False


class TestAPI:
    @pytest.mark.asyncio
    async def test_devices_endpoint(self, fresh_app):
        async with client_from(fresh_app, "127.0.0.1") as client:
            resp = await client.get("/api/devices")
        assert resp.status_code == 200
        assert len(resp.json()["devices"]) == 7

    @pytest.mark.asyncio
    async def test_status_endpoint(self, fresh_app):
        async with client_from(fresh_app, "10.0.0.9") as client:
            resp = await client.get("/api/status")
        body = resp.json()
        assert body["system"] == "Connect4"
        assert body["wifi"]["client_allowed"] is True

    @pytest.mark.asyncio
    async def test_chat_executes_device_action(self, fresh_app):
        async with client_from(fresh_app, "192.168.0.2") as client:
            await client.post(
                "/api/chat",
                json={"messages": [{"role": "user", "content": "lights on"}]},
            )
            devices = (await client.get("/api/devices")).json()["devices"]
        living = next(d for d in devices if d["id"] == "light-living")
        assert living["power"] is True

    @pytest.mark.asyncio
    async def test_chat_rejects_bad_payload(self, fresh_app):
        async with client_from(fresh_app, "192.168.0.2") as client:
            resp = await client.post("/api/chat", json={"messages": []})
        assert resp.status_code == 422
