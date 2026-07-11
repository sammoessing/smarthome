# Connect4 Smart Home Chatbot

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2Fsammoessing%2Fsmarthome&env=OPENAI_API_KEY,ACCESS_CODE&envDescription=OPENAI_API_KEY%3A%20your%20Groq%20API%20key%20(console.groq.com).%20ACCESS_CODE%3A%20a%20secret%20of%20your%20choice%20that%20unlocks%20the%20app.&project-name=connect4-smarthome&repository-name=connect4-smarthome)

A chatbot web app that controls your **Connect4** smart home system — speakers,
lights, and TVs — using an **open-source LLM** (via [Ollama](https://ollama.com),
default model: `llama3.1`).

For safety, the app **only works while you are on your home WiFi**: every
control request is rejected unless it comes from a device on the local network
(and, optionally, unless the server itself is connected to your home SSID).

## How it works

```
Browser (chat UI)
   │  must be on home WiFi / LAN — enforced by WiFiGateMiddleware
   ▼
FastAPI backend  ──► Ollama (open-source LLM, tool calling)
   │                     │
   │  ◄── tool calls ────┘
   ▼
Connect4 hub (speakers / lights / TVs)
```

1. You type a message like *"dim the living room lights to 30% and turn on the
   kitchen speaker"*.
2. The backend sends the conversation plus a set of **device tools** to the LLM.
3. The LLM decides which tools to call (e.g. `set_light`, `control_speaker`);
   the backend executes them against the Connect4 hub and feeds the results
   back to the model.
4. The model replies in natural language with what it did.

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com) running locally with a tool-capable open-source
  model pulled:

  ```bash
  ollama pull llama3.1
  ```

## Quick start

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then open `http://<server-ip>:8000` from a device **on the same WiFi network**.

## Configuration

Configuration is via environment variables (see `.env.example`):

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.1` | Open-source model to use (must support tool calling) |
| `OPENAI_API_KEY` | *(unset)* | If set, use a hosted OpenAI-compatible API instead of Ollama |
| `OPENAI_BASE_URL` | `https://api.groq.com/openai/v1` | Hosted LLM API base URL (Groq/Together/OpenRouter) |
| `OPENAI_MODEL` | `llama-3.1-8b-instant` | Hosted open-source model name |
| `TRUST_PROXY_HEADER` | `false` | Trust `X-Forwarded-For` for the WiFi gate (needed on Vercel) |
| `ALLOWED_SUBNETS` | private + loopback ranges | Comma-separated CIDRs allowed to use the app |
| `REQUIRED_SSID` | *(unset)* | If set, the **server** must be connected to this WiFi SSID or all control is disabled |
| `ACCESS_CODE` | *(unset)* | If set, control works from **any network** but requires this code (UI asks once per device) |
| `CONNECT4_MODE` | `simulated` | `simulated` uses the built-in virtual home; `http` proxies to a real Connect4 hub |
| `CONNECT4_HUB_URL` | *(unset)* | Base URL of a real Connect4 hub (used when `CONNECT4_MODE=http`) |
| `SONOS_ENABLED` | `auto` | Discover/control Sonos on the LAN (`auto` = on locally, off on Vercel) |

## Taking it to any house ("works on whatever WiFi I'm on")

Smart home devices (Sonos, hubs, ...) are controlled over the **local
network**, so the way to control *whichever home you're in* is to run this
app on a machine that joins that WiFi — a laptop or a travel Raspberry Pi:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then everything composes on its own:

- The default WiFi gate allows any **private/LAN** client, so the app works
  on *any* WiFi you and it have joined — no per-house configuration.
- LAN discovery (default on) finds what's actually in that house: Sonos
  speakers appear automatically; a Connect4 hub is attached by pointing
  `CONNECT4_HUB_URL` at it (`CONNECT4_MODE=http`).
- Other smart home systems plug in the same way as Sonos: implement the
  small hub interface (`list_devices` / `get_device` / `apply`) and register
  the bridge with its id prefix in `app/main.py` (see `CompositeHub`).

The Vercel deployment complements this as the anywhere-demo (simulated home
+ access code), but it cannot scan whatever LAN you happen to be on — local
device control always needs the app inside the house's network.

### Two access modes

- **WiFi-only mode (default):** only clients on the allowed subnets (your home
  LAN/WiFi) can use the app. Best when the server runs at home.
- **Access-code mode:** set `ACCESS_CODE=some-secret` and the app works from
  *any* network — any house's WiFi, or cellular — but every device must enter
  the code once (the UI remembers it). The IP gate defaults to open in this
  mode; set `ALLOWED_SUBNETS` too if you want both checks. Best for cloud
  deployments (Vercel) where you roam between networks.

### The WiFi gate

Two independent checks, both enforced by `app/network.py`:

1. **Client check (always on):** the requester's IP must be inside
   `ALLOWED_SUBNETS`. By default that is loopback + RFC1918 private ranges
   (`127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), i.e. your
   home LAN/WiFi. Requests from outside get **403** and the LLM is never
   invoked. Tighten it to your exact WiFi subnet, e.g.
   `ALLOWED_SUBNETS=192.168.1.0/24`.
2. **Server SSID check (optional):** set `REQUIRED_SSID=MyHomeWiFi` and the
   server verifies (via `iwgetid`) that it is actually connected to that WiFi
   network before allowing any control.

## Devices

The simulated Connect4 home ships with:

| Device | Room | Capabilities |
|---|---|---|
| Living Room Light | living room | on/off, brightness, color |
| Kitchen Light | kitchen | on/off, brightness, color |
| Bedroom Light | bedroom | on/off, brightness, color |
| Living Room Speaker | living room | on/off, volume, play/pause, track |
| Kitchen Speaker | kitchen | on/off, volume, play/pause, track |
| Living Room TV | living room | on/off, volume, channel, input |
| Bedroom TV | bedroom | on/off, volume, channel, input |

To drive real hardware, set `CONNECT4_MODE=http` and point `CONNECT4_HUB_URL`
at your hub; `app/connect4.py` documents the small REST contract it expects.

### Sonos speakers (real hardware, works today)

By default (when running locally) the app discovers Sonos speakers on the
local network (via the open-source [SoCo](https://github.com/SoCo/SoCo)
library) and lists them alongside the Connect4 devices as e.g.
"Living Room (Sonos)".
The chatbot can pause/resume them, set volume, and tell you what's playing.

Two constraints, both physics rather than code:

- **The server must be on the same WiFi as the speakers.** Sonos is
  controlled over the LAN, so a cloud (Vercel) deployment finds nothing —
  run the app on a laptop in the house instead:

  ```bash
  SONOS_ENABLED=true uvicorn app.main:app --host 0.0.0.0 --port 8000
  ```

- **Starting your phone's music is done from the phone.** Begin playback
  with the Sonos app, AirPlay, or Spotify Connect; the chatbot controls it
  from there (pause, resume, volume, now-playing).

## API

| Endpoint | Description |
|---|---|
| `GET /` | Chat UI |
| `POST /api/chat` | `{"messages": [...]}` → chatbot reply (runs tool calls) |
| `GET /api/devices` | Current state of every Connect4 device |
| `GET /api/status` | WiFi-gate status, model, hub mode |

## Deploying to Vercel

The repo is Vercel-ready (`api/index.py` + `vercel.json`). Because Vercel
can't run Ollama, deployments use a **hosted open-source LLM** through any
OpenAI-compatible API — Groq's free tier serving Llama 3.1 by default.

1. Get a free API key at [console.groq.com](https://console.groq.com).
2. Import the repo at [vercel.com/new](https://vercel.com/new) and set these
   environment variables:

   ```
   OPENAI_API_KEY=gsk_...            # your Groq key
   ACCESS_CODE=<pick-a-secret>       # works from any network, code required
   ```

   Or, to restrict to your home network instead of using a code:

   ```
   OPENAI_API_KEY=gsk_...
   TRUST_PROXY_HEADER=true           # gate on the real caller IP
   ALLOWED_SUBNETS=<home-ip>/32      # your home's public IP (whatismyip.com)
   ```

3. Deploy and open the URL. In access-code mode the UI asks for your code
   once per device; in WiFi mode it only responds from your home network.

Serverless caveats: the simulated home lives in instance memory, so device
state can reset between requests when Vercel recycles instances — fine for
trying it out. A real deployment that controls physical devices should run
at home anyway (`CONNECT4_MODE=http` needs LAN access to the hub).

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```
