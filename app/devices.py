"""Device models for the Connect4 smart home system."""

from enum import Enum

from pydantic import BaseModel, Field


class DeviceType(str, Enum):
    LIGHT = "light"
    SPEAKER = "speaker"
    TV = "tv"


class Device(BaseModel):
    id: str
    name: str
    room: str
    type: DeviceType
    power: bool = False


class Light(Device):
    type: DeviceType = DeviceType.LIGHT
    brightness: int = Field(default=100, ge=0, le=100)
    color: str = "warm white"


class Speaker(Device):
    type: DeviceType = DeviceType.SPEAKER
    volume: int = Field(default=30, ge=0, le=100)
    playing: bool = False
    track: str | None = None


class TV(Device):
    type: DeviceType = DeviceType.TV
    volume: int = Field(default=20, ge=0, le=100)
    channel: str | None = None
    input: str = "hdmi1"


def default_home() -> list[Device]:
    """The devices in the default (simulated) Connect4 home."""
    return [
        Light(id="light-living", name="Living Room Light", room="living room"),
        Light(id="light-kitchen", name="Kitchen Light", room="kitchen"),
        Light(id="light-bedroom", name="Bedroom Light", room="bedroom"),
        Speaker(id="speaker-living", name="Living Room Speaker", room="living room"),
        Speaker(id="speaker-kitchen", name="Kitchen Speaker", room="kitchen"),
        TV(id="tv-living", name="Living Room TV", room="living room"),
        TV(id="tv-bedroom", name="Bedroom TV", room="bedroom"),
    ]
