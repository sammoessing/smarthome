"""Tests for access-code mode: control from any network, gated by a code."""

import os
from unittest import mock

import httpx
import pytest

import app.main as main_app
from app.config import Settings
from app.connect4 import SimulatedConnect4Hub


@pytest.fixture
def code_app(monkeypatch):
    monkeypatch.setattr(main_app, "hub", SimulatedConnect4Hub())
    monkeypatch.setattr(main_app.settings, "access_code", "sesame42")
    from ipaddress import ip_network

    # code mode defaults the IP gate to open
    monkeypatch.setattr(
        main_app.settings,
        "allowed_subnets",
        [ip_network("0.0.0.0/0"), ip_network("::/0")],
    )
    return main_app.app


def client_from(app, ip: str, code: str | None = None) -> httpx.AsyncClient:
    headers = {"x-access-code": code} if code is not None else {}
    transport = httpx.ASGITransport(app=app, client=(ip, 12345))
    return httpx.AsyncClient(
        transport=transport, base_url="http://connect4.local", headers=headers
    )


class TestAccessCodeGate:
    @pytest.mark.asyncio
    async def test_correct_code_works_from_any_network(self, code_app):
        # a public IP — e.g. a friend's WiFi
        async with client_from(code_app, "203.0.113.50", "sesame42") as client:
            resp = await client.get("/api/devices")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_missing_code_rejected(self, code_app):
        async with client_from(code_app, "203.0.113.50") as client:
            resp = await client.get("/api/devices")
        assert resp.status_code == 401
        assert resp.json()["error"] == "access_code_required"

    @pytest.mark.asyncio
    async def test_wrong_code_rejected(self, code_app):
        async with client_from(code_app, "203.0.113.50", "guess") as client:
            resp = await client.get("/api/devices")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_ui_and_status_load_without_code(self, code_app):
        async with client_from(code_app, "203.0.113.50") as client:
            page = await client.get("/")
            status = await client.get("/api/status")
        assert page.status_code == 200
        assert status.status_code == 200
        assert status.json()["access_code_required"] is True

    @pytest.mark.asyncio
    async def test_no_code_configured_keeps_wifi_only_behavior(self, monkeypatch):
        monkeypatch.setattr(main_app.settings, "access_code", None)
        async with client_from(main_app.app, "203.0.113.50") as client:
            resp = await client.get("/api/devices")
        assert resp.status_code == 403  # public IP still blocked by WiFi gate


class TestCodeModeSettings:
    def test_access_code_defaults_subnets_to_open(self):
        env = {"ACCESS_CODE": "sesame42"}
        with mock.patch.dict(os.environ, env, clear=False):
            os.environ.pop("ALLOWED_SUBNETS", None)
            s = Settings()
        assert s.access_code == "sesame42"
        assert any(str(n) == "0.0.0.0/0" for n in s.allowed_subnets)

    def test_explicit_subnets_still_respected_with_code(self):
        env = {"ACCESS_CODE": "sesame42", "ALLOWED_SUBNETS": "192.168.1.0/24"}
        with mock.patch.dict(os.environ, env, clear=False):
            s = Settings()
        assert [str(n) for n in s.allowed_subnets] == ["192.168.1.0/24"]

    def test_no_code_keeps_private_defaults(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ACCESS_CODE", None)
            os.environ.pop("ALLOWED_SUBNETS", None)
            s = Settings()
        assert s.access_code is None
        assert all("0.0.0.0/0" != str(n) for n in s.allowed_subnets)
