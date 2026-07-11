"""Chat orchestration against an open-source LLM served by Ollama.

Runs the standard tool-calling loop: send conversation + tool schemas to the
model, execute any tool calls it makes against the Connect4 hub, feed results
back, repeat until the model answers in plain text.
"""

import json

import httpx

from .connect4 import Connect4Hub
from .tools import TOOLS, dispatch_tool

SYSTEM_PROMPT = """\
You are the Connect4 home assistant, a friendly chatbot that controls the \
user's Connect4 smart home: lights, speakers, and TVs.

Rules:
- Use the provided tools to inspect and control devices. Call list_devices \
when you need device ids or the current state.
- When the user names a room ("the kitchen light"), match it to the right \
device. If a request is ambiguous (e.g. "turn on the light" and several \
lights exist), ask which one instead of guessing — unless they clearly mean \
all of them.
- When turning media on (playing music, watching TV), also power the device \
on if it is off.
- After acting, confirm briefly and naturally what you did. Never invent \
device state: report only what the tools returned.
- You control ONLY the Connect4 home. Politely decline anything else \
(no general web tasks, no other systems), though friendly small talk is fine.
"""

MAX_TOOL_ROUNDS = 8


class LLMError(Exception):
    pass


class OllamaChat:
    def __init__(self, base_url: str, model: str, timeout: float = 120.0):
        self.model = model
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)

    async def _chat(self, messages: list[dict]) -> dict:
        try:
            resp = await self._client.post(
                "/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "tools": TOOLS,
                    "stream": False,
                },
            )
            resp.raise_for_status()
        except httpx.ConnectError as exc:
            raise LLMError(
                f"Cannot reach Ollama at {self._client.base_url}. "
                "Is Ollama running? (https://ollama.com)"
            ) from exc
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300]
            raise LLMError(f"Ollama error {exc.response.status_code}: {detail}") from exc
        return resp.json()["message"]

    async def respond(self, hub: Connect4Hub, messages: list[dict]) -> dict:
        """Run the tool loop; returns {"reply": str, "actions": [...]}."""
        convo = [{"role": "system", "content": SYSTEM_PROMPT}, *messages]
        actions: list[dict] = []

        for _ in range(MAX_TOOL_ROUNDS):
            message = await self._chat(convo)
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                return {"reply": message.get("content", ""), "actions": actions}

            convo.append(message)
            for call in tool_calls:
                fn = call.get("function", {})
                name = fn.get("name", "")
                args = fn.get("arguments") or {}
                if isinstance(args, str):  # some models return JSON strings
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                result = await dispatch_tool(hub, name, args)
                actions.append({"tool": name, "args": args, "result": result})
                convo.append(
                    {"role": "tool", "name": name, "content": json.dumps(result)}
                )

        return {
            "reply": "I tried, but that request needed too many steps. "
            "Could you break it into smaller requests?",
            "actions": actions,
        }
