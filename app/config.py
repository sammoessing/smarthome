"""Application configuration, sourced from environment variables."""

import os
from dataclasses import dataclass, field
from ipaddress import IPv4Network, IPv6Network, ip_network

# Loopback + RFC1918 private ranges: a request can only originate from these
# when the client is on the local network (home WiFi/LAN).
DEFAULT_ALLOWED_SUBNETS = (
    "127.0.0.0/8",
    "::1/128",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
)


def _parse_subnets(raw: str) -> list[IPv4Network | IPv6Network]:
    return [ip_network(s.strip()) for s in raw.split(",") if s.strip()]


@dataclass
class Settings:
    ollama_url: str = field(
        default_factory=lambda: os.environ.get("OLLAMA_URL", "http://localhost:11434")
    )
    ollama_model: str = field(
        default_factory=lambda: os.environ.get("OLLAMA_MODEL", "llama3.1")
    )
    allowed_subnets: list[IPv4Network | IPv6Network] = field(
        default_factory=lambda: _parse_subnets(
            os.environ.get("ALLOWED_SUBNETS", ",".join(DEFAULT_ALLOWED_SUBNETS))
        )
    )
    required_ssid: str | None = field(
        default_factory=lambda: os.environ.get("REQUIRED_SSID") or None
    )
    connect4_mode: str = field(
        default_factory=lambda: os.environ.get("CONNECT4_MODE", "simulated")
    )
    connect4_hub_url: str | None = field(
        default_factory=lambda: os.environ.get("CONNECT4_HUB_URL") or None
    )


settings = Settings()
