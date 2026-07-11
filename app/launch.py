"""One-command launcher: serve the real smart home with shareable live URLs.

Run with:  python -m app.launch

Does everything the double-click launchers need:
- generates (and persists) an access code so the app is safe to expose
- prints the in-house WiFi URL with a QR code for phones
- opens a free public HTTPS tunnel (Cloudflare quick tunnel, no account)
  so the same app also works from anywhere, then prints that URL + QR
- starts the server with real-device discovery (Sonos) enabled
"""

import os
import re
import secrets
import shutil
import socket
import subprocess
import tarfile
import tempfile
import threading
import urllib.request
from pathlib import Path

PORT = int(os.environ.get("PORT", "8000"))

TUNNEL_URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")

CLOUDFLARED_ASSETS = {
    ("darwin", "arm64"): "cloudflared-darwin-arm64.tgz",
    ("darwin", "x86_64"): "cloudflared-darwin-amd64.tgz",
    ("linux", "x86_64"): "cloudflared-linux-amd64",
    ("linux", "aarch64"): "cloudflared-linux-arm64",
    ("windows", "x86_64"): "cloudflared-windows-amd64.exe",
}


def state_dir() -> Path:
    return Path(os.environ.get("CONNECT4_HOME", Path.home() / "Connect4SmartHome"))


def lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 80))  # no packets sent; just picks the LAN route
        return s.getsockname()[0]
    except OSError:
        return "localhost"
    finally:
        s.close()


def ensure_access_code() -> str:
    """Access code from env, or persisted from a previous run, or freshly made.

    The launcher always sets one: the public tunnel makes the app reachable
    from the internet, and the code is what keeps strangers out.
    """
    code = os.environ.get("ACCESS_CODE", "").strip()
    if not code:
        f = state_dir() / "access-code.txt"
        if f.exists():
            code = f.read_text().strip()
        if not code:
            code = "C4-" + secrets.token_hex(3).upper()
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(code + "\n")
    os.environ["ACCESS_CODE"] = code
    return code


def _platform_key() -> tuple[str, str]:
    import platform

    sysname = platform.system().lower()
    arch = platform.machine().lower()
    arch = {
        "amd64": "x86_64", "x64": "x86_64",
        "arm64": "arm64" if sysname == "darwin" else "aarch64",
    }.get(arch, arch)
    return sysname, arch


def find_or_fetch_cloudflared() -> str | None:
    """Locate cloudflared, downloading the single static binary if needed."""
    found = shutil.which("cloudflared")
    if found:
        return found
    key = _platform_key()
    asset = CLOUDFLARED_ASSETS.get(key)
    if asset is None:
        return None
    dest = state_dir() / "bin" / ("cloudflared.exe" if key[0] == "windows" else "cloudflared")
    if dest.exists():
        return str(dest)
    url = f"https://github.com/cloudflare/cloudflared/releases/latest/download/{asset}"
    print("  Fetching tunnel helper (first run only)...")
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            with urllib.request.urlopen(url, timeout=120) as resp:
                shutil.copyfileobj(resp, tmp)
            tmp_path = Path(tmp.name)
        if asset.endswith(".tgz"):
            with tarfile.open(tmp_path) as tar:
                member = tar.extractfile("cloudflared")
                dest.write_bytes(member.read())
            tmp_path.unlink()
        else:
            shutil.move(tmp_path, dest)
        dest.chmod(0o755)
        return str(dest)
    except Exception:
        return None


def start_tunnel(on_result) -> subprocess.Popen | None:
    """Open a quick tunnel to the local server; call on_result(url or None)."""
    exe = find_or_fetch_cloudflared()
    if exe is None:
        on_result(None)
        return None
    try:
        proc = subprocess.Popen(
            [exe, "tunnel", "--url", f"http://127.0.0.1:{PORT}", "--no-autoupdate"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
    except OSError:
        on_result(None)
        return None

    def read_output():
        announced = False
        for line in proc.stdout:
            m = TUNNEL_URL_RE.search(line)
            if m and not announced:
                announced = True
                on_result(m.group(0))
        if not announced:
            on_result(None)

    threading.Thread(target=read_output, daemon=True).start()
    return proc


def print_qr(url: str) -> None:
    try:
        import qrcode
    except ImportError:
        return
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make()
    qr.print_ascii(invert=True)


def main() -> None:
    code = ensure_access_code()
    local_url = f"http://{lan_ip()}:{PORT}"

    print()
    print("  🏠 Connect4 Home Assistant — REAL device mode")
    print(f"  🔑 Access code: {code}   (the app asks for this once per device)")
    print()
    print(f"  📶 In this house (same WiFi):  {local_url}")
    print_qr(local_url)
    print("  🌍 Opening a live link that works from anywhere...")

    def on_tunnel(url: str | None):
        if url:
            print()
            print(f"  🌍 LIVE ANYWHERE:  {url}")
            print(f"     Access code: {code}")
            print_qr(url)
            print("     This link controls the REAL devices found in this house,")
            print("     from any network, as long as this window stays open.")
        else:
            print()
            print("  (Couldn't open the public link — the WiFi URL above still")
            print("   works for every device in the house.)")

    tunnel = start_tunnel(on_tunnel)
    try:
        import uvicorn

        uvicorn.run("app.main:app", host="0.0.0.0", port=PORT, log_level="warning")
    finally:
        if tunnel is not None:
            tunnel.terminate()


if __name__ == "__main__":
    main()
