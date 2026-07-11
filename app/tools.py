"""Tools the LLM can call to control the Connect4 home, plus their dispatch."""

from pydantic import ValidationError

from .connect4 import Connect4Hub, DeviceNotFound
from .devices import DeviceType

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_devices",
            "description": "List every Connect4 device with its current state. "
            "Call this first when you need a device id or don't know what "
            "devices exist.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_light",
            "description": "Control a Connect4 light: power, brightness, color.",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": {"type": "string", "description": "Light device id"},
                    "power": {"type": "boolean", "description": "true=on, false=off"},
                    "brightness": {
                        "type": "integer",
                        "description": "Brightness 0-100",
                    },
                    "color": {
                        "type": "string",
                        "description": "Color name, e.g. 'warm white', 'blue'",
                    },
                },
                "required": ["device_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "control_speaker",
            "description": "Control a Connect4 speaker: power, volume, playback.",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": {"type": "string", "description": "Speaker device id"},
                    "power": {"type": "boolean", "description": "true=on, false=off"},
                    "volume": {"type": "integer", "description": "Volume 0-100"},
                    "playing": {
                        "type": "boolean",
                        "description": "true=play, false=pause",
                    },
                    "track": {
                        "type": "string",
                        "description": "Song, artist, playlist or station to play",
                    },
                },
                "required": ["device_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "control_tv",
            "description": "Control a Connect4 TV: power, volume, channel, input.",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": {"type": "string", "description": "TV device id"},
                    "power": {"type": "boolean", "description": "true=on, false=off"},
                    "volume": {"type": "integer", "description": "Volume 0-100"},
                    "channel": {
                        "type": "string",
                        "description": "Channel or app, e.g. 'HBO', 'Netflix'",
                    },
                    "input": {
                        "type": "string",
                        "description": "Input source, e.g. 'hdmi1', 'hdmi2', 'cast'",
                    },
                },
                "required": ["device_id"],
            },
        },
    },
]

_TOOL_DEVICE_TYPES = {
    "set_light": DeviceType.LIGHT,
    "control_speaker": DeviceType.SPEAKER,
    "control_tv": DeviceType.TV,
}


async def dispatch_tool(hub: Connect4Hub, name: str, args: dict) -> dict:
    """Execute one tool call and return a JSON-serializable result for the LLM."""
    if name == "list_devices":
        return {"devices": [d.model_dump() for d in await hub.list_devices()]}

    expected_type = _TOOL_DEVICE_TYPES.get(name)
    if expected_type is None:
        return {"error": f"Unknown tool '{name}'"}

    args = dict(args)
    device_id = args.pop("device_id", None)
    if not device_id:
        return {"error": "device_id is required"}
    try:
        device = await hub.get_device(device_id)
        if device.type != expected_type:
            return {
                "error": f"Device '{device_id}' is a {device.type.value}, "
                f"not a {expected_type.value}. Use the matching tool."
            }
        changes = {k: v for k, v in args.items() if v is not None}
        updated = await hub.apply(device_id, changes)
        return {"ok": True, "device": updated.model_dump()}
    except DeviceNotFound as exc:
        return {"error": str(exc)}
    except ValidationError as exc:
        return {"error": f"Invalid value: {exc.errors()[0].get('msg', str(exc))}"}
