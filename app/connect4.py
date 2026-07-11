"""Connect4 hub clients.

``SimulatedConnect4Hub`` keeps an in-memory virtual home so the app works out
of the box. ``HttpConnect4Hub`` proxies the same operations to a real Connect4
hub over REST, expecting this contract:

    GET  {hub}/devices                          -> [{device state}, ...]
    POST {hub}/devices/{device_id}/state        <- partial state to apply
                                                -> {device state}
"""

from typing import Protocol

import httpx

from .devices import TV, Device, DeviceType, Light, Speaker, default_home


class DeviceNotFound(Exception):
    def __init__(self, device_id: str):
        super().__init__(f"No Connect4 device with id '{device_id}'")
        self.device_id = device_id


class Connect4Hub(Protocol):
    async def list_devices(self) -> list[Device]: ...

    async def get_device(self, device_id: str) -> Device: ...

    async def apply(self, device_id: str, changes: dict) -> Device: ...


class SimulatedConnect4Hub:
    """In-memory Connect4 home, used by default and in tests."""

    def __init__(self, devices: list[Device] | None = None):
        self._devices: dict[str, Device] = {
            d.id: d for d in (devices if devices is not None else default_home())
        }

    async def list_devices(self) -> list[Device]:
        return list(self._devices.values())

    async def get_device(self, device_id: str) -> Device:
        try:
            return self._devices[device_id]
        except KeyError:
            raise DeviceNotFound(device_id) from None

    async def apply(self, device_id: str, changes: dict) -> Device:
        device = await self.get_device(device_id)
        updated = device.model_copy(update=changes)
        # Re-validate so out-of-range values (volume 500, brightness -3, an
        # unknown field, ...) are rejected instead of silently stored.
        updated = type(device).model_validate(updated.model_dump())
        self._devices[device_id] = updated
        return updated


class HttpConnect4Hub:
    """Client for a real Connect4 hub exposing the REST contract above."""

    _MODELS = {DeviceType.LIGHT: Light, DeviceType.SPEAKER: Speaker, DeviceType.TV: TV}

    def __init__(self, base_url: str, timeout: float = 10.0):
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)

    def _to_device(self, payload: dict) -> Device:
        model = self._MODELS[DeviceType(payload["type"])]
        return model.model_validate(payload)

    async def list_devices(self) -> list[Device]:
        resp = await self._client.get("/devices")
        resp.raise_for_status()
        return [self._to_device(d) for d in resp.json()]

    async def get_device(self, device_id: str) -> Device:
        for device in await self.list_devices():
            if device.id == device_id:
                return device
        raise DeviceNotFound(device_id)

    async def apply(self, device_id: str, changes: dict) -> Device:
        resp = await self._client.post(f"/devices/{device_id}/state", json=changes)
        if resp.status_code == 404:
            raise DeviceNotFound(device_id)
        resp.raise_for_status()
        return self._to_device(resp.json())


def make_hub(mode: str, hub_url: str | None) -> Connect4Hub:
    if mode == "http":
        if not hub_url:
            raise ValueError("CONNECT4_HUB_URL must be set when CONNECT4_MODE=http")
        return HttpConnect4Hub(hub_url)
    return SimulatedConnect4Hub()
