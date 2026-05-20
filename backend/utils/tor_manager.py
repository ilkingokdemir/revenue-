"""Lightweight Tor lifecycle + circuit rotation helper.

Purpose
-------
Lets the Booking.com scraper route ALL its traffic through a local Tor SOCKS
proxy (127.0.0.1:9050). Calling `rotate_circuit()` between scrapes asks Tor
for a new exit relay, which gives us a fresh IP address — effectively a free
"VPN rotation" that bypasses the cloud-pod IP rate-limiting Booking.com
applies to scraping calls.

Design choices
--------------
- We do NOT manage Tor lifecycle from inside FastAPI: it lives as a daemon
  started at container boot (or `ensure_tor_running` here on first import).
- `rotate_circuit()` is best-effort: if the control port is unreachable we
  log a warning and return — the scraper just re-uses whatever exit Tor
  happens to be on.
- Enabled with env var `USE_TOR_FOR_BOOKING=1`. Disabled = no behavioural
  change (direct IP scraping, identical to before).
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default values match the config we wrote to /etc/tor/torrc.d/01-rotating.conf
SOCKS_HOST = "127.0.0.1"
SOCKS_PORT = 9050
CONTROL_HOST = "127.0.0.1"
CONTROL_PORT = 9051
# hashed password for control auth (plain password: "rotateme")
_PLAIN_CONTROL_PW = "rotateme"


def tor_enabled() -> bool:
    """Whether the Booking scraper should route through Tor.

    Defaults to True if the tor binary is available, so users get the free
    IP-rotation feature out of the box. Set USE_TOR_FOR_BOOKING=0 to disable.
    """
    flag = os.environ.get("USE_TOR_FOR_BOOKING", "").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return False
    if flag in ("1", "true", "yes", "on"):
        return True
    # auto: enable if tor binary is on PATH
    return shutil.which("tor") is not None


def _socks_listening() -> bool:
    """True if something is listening on the Tor SOCKS port."""
    import socket
    try:
        with socket.create_connection((SOCKS_HOST, SOCKS_PORT), timeout=1.5):
            return True
    except OSError:
        return False


def ensure_tor_running(wait_seconds: int = 25) -> bool:
    """Make sure Tor is running. Idempotent; cheap when already running.

    Returns True if Tor SOCKS is reachable when we return.
    """
    if not shutil.which("tor"):
        logger.info("Tor binary not present — skipping Tor setup")
        return False
    if _socks_listening():
        return True
    # Write our rotation-tuned config if not present
    cfg_dir = Path("/etc/tor/torrc.d")
    cfg = cfg_dir / "01-rotating.conf"
    if not cfg.exists():
        try:
            cfg_dir.mkdir(parents=True, exist_ok=True)
            cfg.write_text(
                "SocksPort 9050\n"
                "ControlPort 9051\n"
                # hashed password for "rotateme"
                "HashedControlPassword 16:12F662BB1B79490C60E420D35690F1608E4B2D895E05A07B8C8495224C\n"
                "MaxCircuitDirtiness 30\n"
                "NewCircuitPeriod 30\n",
                encoding="utf-8",
            )
            torrc = Path("/etc/tor/torrc")
            if torrc.exists() and "%include /etc/tor/torrc.d" not in torrc.read_text():
                with torrc.open("a", encoding="utf-8") as f:
                    f.write("\n%include /etc/tor/torrc.d/*.conf\n")
        except PermissionError:
            logger.warning("Cannot write Tor config (no perms) — relying on system defaults")
    # Launch as daemon (no systemd in this container)
    try:
        # Try non-root invocation first (debian-tor user is the package default)
        subprocess.run(
            ["sudo", "-n", "-u", "debian-tor", "tor", "-f", "/etc/tor/torrc", "--runasdaemon", "1"],
            check=False, capture_output=True, timeout=15,
        )
    except Exception as e:
        logger.warning("Tor launch as debian-tor failed: %s", e)
    # Wait for SOCKS to become reachable
    for _ in range(wait_seconds):
        if _socks_listening():
            logger.info("Tor SOCKS ready on %s:%s", SOCKS_HOST, SOCKS_PORT)
            return True
        time.sleep(1)
    logger.warning("Tor did not come up within %ss", wait_seconds)
    return False


async def ensure_tor_running_async(wait_seconds: int = 25) -> bool:
    """Async wrapper so we can call from FastAPI startup without blocking the loop."""
    return await asyncio.to_thread(ensure_tor_running, wait_seconds)


def playwright_proxy_config() -> Optional[dict]:
    """Return the Playwright proxy config dict for Tor, or None if disabled."""
    if not tor_enabled():
        return None
    if not _socks_listening():
        return None
    return {"server": f"socks5://{SOCKS_HOST}:{SOCKS_PORT}"}


async def rotate_circuit(timeout: float = 5.0) -> bool:
    """Ask Tor for a new circuit (= new exit IP). Best-effort; returns success bool."""
    if not tor_enabled() or not _socks_listening():
        return False
    try:
        # Use stem to send the NEWNYM signal
        from stem import Signal
        from stem.control import Controller

        def _send():
            with Controller.from_port(address=CONTROL_HOST, port=CONTROL_PORT) as ctrl:
                ctrl.authenticate(password=_PLAIN_CONTROL_PW)
                ctrl.signal(Signal.NEWNYM)
                return True

        ok = await asyncio.wait_for(asyncio.to_thread(_send), timeout=timeout)
        if ok:
            logger.info("Tor NEWNYM signal sent — new circuit requested")
        return bool(ok)
    except Exception as e:
        logger.warning("Tor NEWNYM failed: %s", e)
        return False
