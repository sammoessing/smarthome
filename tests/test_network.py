"""Tests for the WiFi gate."""

from app.config import Settings
from app.network import client_ip_allowed, server_ssid_ok


def make_settings(**overrides) -> Settings:
    s = Settings()
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


class TestClientIPAllowed:
    def test_loopback_allowed(self):
        assert client_ip_allowed("127.0.0.1", make_settings())

    def test_home_wifi_ranges_allowed(self):
        s = make_settings()
        assert client_ip_allowed("192.168.1.42", s)
        assert client_ip_allowed("10.0.0.5", s)
        assert client_ip_allowed("172.16.3.9", s)

    def test_public_internet_rejected(self):
        s = make_settings()
        assert not client_ip_allowed("8.8.8.8", s)
        assert not client_ip_allowed("203.0.113.10", s)

    def test_garbage_ip_rejected(self):
        assert not client_ip_allowed("not-an-ip", make_settings())
        assert not client_ip_allowed("", make_settings())

    def test_custom_subnet_restriction(self):
        from ipaddress import ip_network

        s = make_settings(allowed_subnets=[ip_network("192.168.1.0/24")])
        assert client_ip_allowed("192.168.1.7", s)
        assert not client_ip_allowed("192.168.2.7", s)
        assert not client_ip_allowed("10.0.0.1", s)


class TestServerSSID:
    def test_no_required_ssid_passes(self):
        assert server_ssid_ok(make_settings(required_ssid=None))

    def test_required_ssid_matches(self, monkeypatch):
        monkeypatch.setattr("app.network.current_ssid", lambda: "HomeNet")
        assert server_ssid_ok(make_settings(required_ssid="HomeNet"))

    def test_required_ssid_mismatch_fails(self, monkeypatch):
        monkeypatch.setattr("app.network.current_ssid", lambda: "CoffeeShop")
        assert not server_ssid_ok(make_settings(required_ssid="HomeNet"))

    def test_no_wifi_fails_when_ssid_required(self, monkeypatch):
        monkeypatch.setattr("app.network.current_ssid", lambda: None)
        assert not server_ssid_ok(make_settings(required_ssid="HomeNet"))
