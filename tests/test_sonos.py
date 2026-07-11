"""Tests for the Sonos bridge, using fake SoCo zones (no real network)."""

import pytest

from app.connect4 import DeviceNotFound, SimulatedConnect4Hub
from app.sonos import CompositeHub, SonosBridge
from app.tools import dispatch_tool


class FakeZone:
    """Mimics the slice of soco.SoCo the bridge uses."""

    def __init__(self, player_name, uid="RINCON_TEST1"):
        self.player_name = player_name
        self.uid = uid
        self.volume = 25
        self._state = "PAUSED_PLAYBACK"
        self._track = {"title": "Song A", "artist": "Artist A"}
        self.calls = []

    def get_current_transport_info(self):
        return {"current_transport_state": self._state}

    def get_current_track_info(self):
        return self._track

    def play(self):
        self.calls.append("play")
        self._state = "PLAYING"

    def pause(self):
        self.calls.append("pause")
        self._state = "PAUSED_PLAYBACK"


@pytest.fixture
def zone():
    return FakeZone("Living Room")


@pytest.fixture
def bridge(zone):
    return SonosBridge(discover=lambda: {zone})


class TestSonosBridge:
    @pytest.mark.asyncio
    async def test_discovers_and_maps_speakers(self, bridge):
        devices = await bridge.list_devices()
        assert len(devices) == 1
        speaker = devices[0]
        assert speaker.id == "sonos-living-room"
        assert speaker.name == "Living Room (Sonos)"
        assert speaker.volume == 25
        assert speaker.playing is False
        assert speaker.track == "Song A — Artist A"

    @pytest.mark.asyncio
    async def test_volume_and_play(self, bridge, zone):
        updated = await bridge.apply(
            "sonos-living-room", {"volume": 55, "playing": True}
        )
        assert zone.volume == 55
        assert "play" in zone.calls
        assert updated.playing is True

    @pytest.mark.asyncio
    async def test_power_off_maps_to_pause(self, bridge, zone):
        zone.play()
        await bridge.apply("sonos-living-room", {"power": False})
        assert zone.calls[-1] == "pause"

    @pytest.mark.asyncio
    async def test_setting_track_explains_phone_flow(self, bridge):
        result = await dispatch_tool(
            CompositeHubForTest(bridge),
            "control_speaker",
            {"device_id": "sonos-living-room", "track": "my playlist"},
        )
        assert "phone" in result["error"]

    @pytest.mark.asyncio
    async def test_out_of_range_volume_rejected_before_touching_speaker(
        self, bridge, zone
    ):
        result = await dispatch_tool(
            CompositeHubForTest(bridge),
            "control_speaker",
            {"device_id": "sonos-living-room", "volume": 500},
        )
        assert "error" in result
        assert zone.volume == 25

    @pytest.mark.asyncio
    async def test_unknown_speaker(self, bridge):
        with pytest.raises(DeviceNotFound):
            await bridge.get_device("sonos-attic")

    @pytest.mark.asyncio
    async def test_duplicate_room_names_get_unique_ids(self):
        zones = {FakeZone("Den", uid="RINCON_A"), FakeZone("Den", uid="RINCON_B")}
        bridge = SonosBridge(discover=lambda: zones)
        ids = {d.id for d in await bridge.list_devices()}
        assert len(ids) == 2


def CompositeHubForTest(bridge):
    return CompositeHub(SimulatedConnect4Hub(), {"sonos-": bridge})


class TestCompositeHub:
    @pytest.mark.asyncio
    async def test_merges_base_and_sonos(self, bridge):
        hub = CompositeHubForTest(bridge)
        devices = await hub.list_devices()
        ids = {d.id for d in devices}
        assert "light-living" in ids  # base
        assert "sonos-living-room" in ids  # sonos

    @pytest.mark.asyncio
    async def test_routes_by_prefix(self, bridge, zone):
        hub = CompositeHubForTest(bridge)
        await hub.apply("sonos-living-room", {"volume": 10})
        assert zone.volume == 10
        light = await hub.apply("light-living", {"power": True})
        assert light.power is True

    @pytest.mark.asyncio
    async def test_discovery_failure_still_lists_base_devices(self):
        def boom():
            raise OSError("no network")

        hub = CompositeHub(
            SimulatedConnect4Hub(), {"sonos-": SonosBridge(discover=boom)}
        )
        devices = await hub.list_devices()
        assert len(devices) == 7  # base home intact

    @pytest.mark.asyncio
    async def test_chatbot_tool_controls_sonos(self, bridge, zone):
        hub = CompositeHubForTest(bridge)
        result = await dispatch_tool(
            hub,
            "control_speaker",
            {"device_id": "sonos-living-room", "playing": True, "volume": 40},
        )
        assert result["ok"] is True
        assert result["device"]["name"] == "Living Room (Sonos)"
        assert zone.volume == 40
        assert "play" in zone.calls
