"""The WiFi gate: the app only works for clients on the home network.

Two checks:

1. Client IP must fall inside one of the allowed subnets (default: loopback +
   RFC1918 private ranges). Anything else — i.e. any request routed in from
   outside the home LAN/WiFi — is rejected with 403 before the LLM or any
   device is touched.
2. Optionally, the server itself must be connected to a specific WiFi SSID
   (``REQUIRED_SSID``), verified via ``iwgetid``. If the server drops off the
   home WiFi, all control is disabled.
"""

import subprocess
from ipaddress import ip_address

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .config import Settings


def effective_client_ip(request: Request, settings: Settings) -> str:
    """The IP the WiFi gate should judge.

    Directly on the LAN that's the TCP peer. Behind a trusted reverse proxy
    (TRUST_PROXY_HEADER=true, e.g. on Vercel) it's the first hop in
    X-Forwarded-For — the caller's public IP, which equals the home router's
    public IP exactly when the caller is on the home WiFi.
    """
    if settings.trust_proxy_header:
        forwarded = request.headers.get("x-forwarded-for", "")
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else ""


def client_ip_allowed(client_ip: str, settings: Settings) -> bool:
    """True if the client address is inside an allowed (home-network) subnet."""
    try:
        addr = ip_address(client_ip)
    except ValueError:
        return False
    return any(addr in net for net in settings.allowed_subnets)


def current_ssid() -> str | None:
    """SSID the server is connected to, or None if unknown/not on WiFi."""
    try:
        out = subprocess.run(
            ["iwgetid", "-r"], capture_output=True, text=True, timeout=5
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    ssid = out.stdout.strip()
    return ssid or None


def server_ssid_ok(settings: Settings) -> bool:
    """True if no SSID is required, or the server is on the required SSID."""
    if settings.required_ssid is None:
        return True
    return current_ssid() == settings.required_ssid


def wifi_status(settings: Settings, client_ip: str | None = None) -> dict:
    status = {
        "required_ssid": settings.required_ssid,
        "server_ssid_ok": server_ssid_ok(settings),
        "allowed_subnets": [str(n) for n in settings.allowed_subnets],
    }
    if client_ip is not None:
        status["client_ip"] = client_ip
        status["client_allowed"] = client_ip_allowed(client_ip, settings)
    return status


class WiFiGateMiddleware(BaseHTTPMiddleware):
    """Reject every request that does not originate from the home network."""

    def __init__(self, app, settings: Settings):
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next):
        client_ip = effective_client_ip(request, self.settings)
        if not client_ip_allowed(client_ip, self.settings):
            return JSONResponse(
                status_code=403,
                content={
                    "error": "not_on_home_wifi",
                    "detail": "Connect4 control is only available on your home "
                    "WiFi network. Connect to the home network and try again.",
                },
            )
        # /api/status stays reachable on the LAN even if the server has
        # dropped off the required SSID, so the UI can explain why.
        if request.url.path != "/api/status" and not server_ssid_ok(self.settings):
            return JSONResponse(
                status_code=503,
                content={
                    "error": "server_not_on_required_wifi",
                    "detail": f"The Connect4 server is not connected to the "
                    f"required WiFi network ({self.settings.required_ssid}). "
                    "Control is disabled.",
                },
            )
        return await call_next(request)
