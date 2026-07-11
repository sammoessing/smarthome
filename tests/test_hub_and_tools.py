"""Tests for the simulated Connect4 hub and the LLM tool dispatch."""

import pytest

from app.connect4 import DeviceNotFound, SimulatedConnect4Hub
from app.tools import dispatch_tool


@pytest.fixture
def hub():
    return SimulatedConnect4Hub()


class TestSimulatedHub:
    @pytest.mark.asyncio
    async def test_default_home_has_all_device_types(self, hub):
        devices = await hub.list_devices()
        types = {d.type.value for d in devices}
        assert types == {"light", "speaker", "tv"}

    @pytest.mark.asyncio
    async def test_apply_updates_state(self, hub):
        updated = await hub.apply("light-living", {"power": True, "brightness": 40})
        assert updated.power is True
        assert updated.brightness == 40
        # persisted
        again = await hub.get_device("light-living")
        assert again.brightness == 40

    @pytest.mark.asyncio
    async def test_unknown_device(self, hub):
        with pytest.raises(DeviceNotFound):
            await hub.get_device("light-garage")

    @pytest.mark.asyncio
    async def test_out_of_range_rejected(self, hub):
        with pytest.raises(Exception):
            await hub.apply("speaker-living", {"volume": 500})


class TestDispatchTool:
    @pytest.mark.asyncio
    async def test_list_devices(self, hub):
        result = await dispatch_tool(hub, "list_devices", {})
        assert len(result["devices"]) == 7

    @pytest.mark.asyncio
    async def test_set_light(self, hub):
        result = await dispatch_tool(
            hub, "set_light", {"device_id": "light-kitchen", "power": True, "color": "blue"}
        )
        assert result["ok"] is True
        assert result["device"]["color"] == "blue"

    @pytest.mark.asyncio
    async def test_control_speaker_play(self, hub):
        result = await dispatch_tool(
            hub,
            "control_speaker",
            {"device_id": "speaker-kitchen", "power": True, "playing": True, "track": "jazz"},
        )
        assert result["ok"] is True
        assert result["device"]["track"] == "jazz"

    @pytest.mark.asyncio
    async def test_control_tv(self, hub):
        result = await dispatch_tool(
            hub, "control_tv", {"device_id": "tv-bedroom", "power": True, "channel": "HBO"}
        )
        assert result["device"]["channel"] == "HBO"

    @pytest.mark.asyncio
    async def test_wrong_device_type_rejected(self, hub):
        result = await dispatch_tool(hub, "set_light", {"device_id": "tv-bedroom", "power": True})
        assert "error" in result
        light = await hub.get_device("tv-bedroom")
        assert light.power is False

    @pytest.mark.asyncio
    async def test_unknown_device_returns_error(self, hub):
        result = await dispatch_tool(hub, "set_light", {"device_id": "nope"})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_invalid_value_returns_error_not_crash(self, hub):
        result = await dispatch_tool(
            hub, "control_speaker", {"device_id": "speaker-living", "volume": 500}
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_missing_device_id(self, hub):
        result = await dispatch_tool(hub, "set_light", {})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_unknown_tool(self, hub):
        result = await dispatch_tool(hub, "launch_rocket", {"device_id": "x"})
        assert "error" in result
