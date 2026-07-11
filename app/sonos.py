"""Sonos integration: discover real Sonos speakers on the local network and
expose them as Connect4 speakers.

Uses SoCo (open-source Sonos control, https://github.com/SoCo/SoCo) over UPnP,
which only works when this server runs on the same WiFi/LAN as the speakers —
a cloud deployment cannot reach them.

The app cannot stream the phone's music library itself: the user starts
playback from their phone (Sonos app / AirPlay / Spotify Connect) and this
bridge then controls it — play/pause, volume, and reporting what's playing.
"""

import asyncio
import re
import time

from .connect4 import Connect4Hub, DeviceNotFound
from .devices import Device, Speaker

SONOS_ID_PREFIX = "sonos-"


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def default_discover():
    import soco

    return soco.discover(timeout=5) or set()


class SonosBridge:
    """Discovers Sonos zones and adapts them to the Connect4 Speaker model."""

    def __init__(self, discover=default_discover, cache_ttl: float = 300.0):
        self._discover = discover
        self._zones: dict[str, object] = {}  # device_id -> soco.SoCo
        self._last_scan: float | None = None
        self._ttl = cache_ttl

    async def _ensure_scan(self, force: bool = False) -> None:
        stale = (
            self._last_scan is None
            or time.monotonic() - self._last_scan > self._ttl
        )
        if not (force or stale):
            return
        zones = await asyncio.to_thread(self._discover)
        found: dict[str, object] = {}
        for zone in zones:
            device_id = SONOS_ID_PREFIX + _slug(zone.player_name)
            if device_id in found:  # two rooms with the same name
                device_id = SONOS_ID_PREFIX + _slug(zone.uid)
            found[device_id] = zone
        self._zones = found
        self._last_scan = time.monotonic()

    def _read(self, device_id: str, zone) -> Speaker:
        transport = zone.get_current_transport_info()
        track_info = zone.get_current_track_info()
        title = track_info.get("title") or ""
        artist = track_info.get("artist") or ""
        track = f"{title} — {artist}" if title and artist else title or None
        return Speaker(
            id=device_id,
            name=f"{zone.player_name} (Sonos)",
            room=zone.player_name.lower(),
            power=True,  # Sonos speakers are always on
            volume=zone.volume,
            playing=transport.get("current_transport_state") == "PLAYING",
            track=track,
        )

    async def list_devices(self, rescan: bool = False) -> list[Speaker]:
        await self._ensure_scan(force=rescan)
        return [
            await asyncio.to_thread(self._read, device_id, zone)
            for device_id, zone in self._zones.items()
        ]

    async def get_device(self, device_id: str) -> Speaker:
        await self._ensure_scan()
        zone = self._zones.get(device_id)
        if zone is None:
            raise DeviceNotFound(device_id)
        return await asyncio.to_thread(self._read, device_id, zone)

    async def apply(self, device_id: str, changes: dict) -> Speaker:
        await self._ensure_scan()
        zone = self._zones.get(device_id)
        if zone is None:
            raise DeviceNotFound(device_id)
        # Validate ranges (volume 0-100, ...) against the Speaker model before
        # touching the real speaker.
        current = await asyncio.to_thread(self._read, device_id, zone)
        Speaker.model_validate({**current.model_dump(), **changes})
        if "track" in changes and changes["track"]:
            raise UnsupportedSonosOperation(
                "I can't start music from your library on Sonos — start it "
                "from your phone (Sonos app, AirPlay, or Spotify Connect) "
                "and I can then pause, resume, and set the volume."
            )
        await asyncio.to_thread(self._apply_sync, zone, changes)
        return await asyncio.to_thread(self._read, device_id, zone)

    @staticmethod
    def _apply_sync(zone, changes: dict) -> None:
        if "volume" in changes:
            zone.volume = changes["volume"]
        # Sonos has no power switch: treat power-off as pause.
        wants_playing = changes.get("playing")
        if changes.get("power") is False and wants_playing is None:
            wants_playing = False
        if wants_playing is True:
            zone.play()
        elif wants_playing is False:
            zone.pause()


class UnsupportedSonosOperation(Exception):
    pass


class CompositeHub:
    """Merges the base Connect4 hub with any number of discovered smart home
    systems (Sonos today; add a bridge with its own id prefix for others).

    A bridge is anything with the Connect4Hub interface (list_devices /
    get_device / apply) whose device ids share a unique prefix.
    """

    def __init__(self, base: Connect4Hub, bridges: dict[str, Connect4Hub]):
        self._base = base
        self._bridges = bridges  # id prefix -> bridge

    async def list_devices(self) -> list[Device]:
        devices = list(await self._base.list_devices())
        for bridge in self._bridges.values():
            try:
                devices.extend(await bridge.list_devices())
            except Exception:  # one system failing must not break the home
                continue
        return devices

    def _owner(self, device_id: str) -> Connect4Hub:
        for prefix, bridge in self._bridges.items():
            if device_id.startswith(prefix):
                return bridge
        return self._base

    async def get_device(self, device_id: str) -> Device:
        return await self._owner(device_id).get_device(device_id)

    async def apply(self, device_id: str, changes: dict) -> Device:
        return await self._owner(device_id).apply(device_id, changes)
