#!/usr/bin/env python3
"""Render an HTML document to PDF by driving the system Chromium (Edge/Chrome)
headlessly via the Chrome DevTools Protocol (CDP).

No browser is bundled and no GTK is required: the app relies on Microsoft Edge,
which ships with Windows 10/11 (Chrome is used if found instead). This gives
Chromium-quality rendering of the shared templates.

Public surface:
    find_browser() -> str | None
    html_to_pdf(html, out_path, base_dir, manifest, browser_path, timeout=30.0)
    ChromiumNotFoundError
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

try:  # pure-python, bundled by PyInstaller
    import websocket  # type: ignore
except Exception:  # pragma: no cover - import guard for dev environments
    websocket = None


class ChromiumNotFoundError(RuntimeError):
    """Raised when no Edge/Chrome browser can be located."""


# --------------------------------------------------------------------------- #
# Browser discovery
# --------------------------------------------------------------------------- #
def _standard_browser_paths() -> list[str]:
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        rf"{pf86}\Microsoft\Edge\Application\msedge.exe",
        rf"{pf}\Microsoft\Edge\Application\msedge.exe",
        rf"{pf}\Google\Chrome\Application\chrome.exe",
        rf"{pf86}\Google\Chrome\Application\chrome.exe",
    ]
    if local:
        candidates.append(rf"{local}\Google\Chrome\Application\chrome.exe")
    return candidates


def _registry_browser_paths() -> list[str]:
    """Read browser locations from the Windows 'App Paths' registry keys."""
    paths: list[str] = []
    try:
        import winreg  # Windows-only; absent on WSL/dev
    except Exception:
        return paths
    subkeys = [
        r"Software\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe",
        r"Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
    ]
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for sub in subkeys:
            try:
                with winreg.OpenKey(root, sub) as k:
                    val, _ = winreg.QueryValueEx(k, None)
                    if val:
                        paths.append(val)
            except OSError:
                continue
    return paths


def find_browser() -> str | None:
    """Locate an Edge/Chrome executable, or return None if none is found.

    Order: MD2PDF_BROWSER env var -> PATH -> standard install dirs -> registry.
    """
    env = os.environ.get("MD2PDF_BROWSER")
    if env and Path(env).is_file():
        return env

    for name in ("msedge", "chrome"):
        found = shutil.which(name)
        if found:
            return found

    for p in _standard_browser_paths() + _registry_browser_paths():
        if p and Path(p).is_file():
            return p
    return None


# --------------------------------------------------------------------------- #
# Manifest -> printToPDF parameter mapping (pure, unit-testable off Windows)
# --------------------------------------------------------------------------- #
# Named page sizes in inches (portrait): (width, height).
PAPER_INCHES: dict[str, tuple[float, float]] = {
    "A3": (11.69, 16.54),
    "A4": (8.27, 11.69),
    "A5": (5.83, 8.27),
    "LETTER": (8.5, 11.0),
    "LEGAL": (8.5, 14.0),
}

_UNIT_TO_INCH = {
    "in": 1.0,
    "cm": 1.0 / 2.54,
    "mm": 1.0 / 25.4,
    "pt": 1.0 / 72.0,
    "px": 1.0 / 96.0,
}


def parse_len_in(token: str) -> float:
    """Parse a single CSS length (e.g. '2cm', '18mm', '0.5in', '12pt') to inches."""
    token = token.strip().lower()
    for unit, factor in _UNIT_TO_INCH.items():
        if token.endswith(unit):
            return float(token[: -len(unit)].strip()) * factor
    # bare number: treat as pixels (CSS default reference unit here)
    return float(token) * _UNIT_TO_INCH["px"]


def parse_margin_in(shorthand: str) -> dict[str, float]:
    """Parse a CSS margin shorthand (1-4 lengths) into inches per side.

    1 value: all; 2: V H; 3: T H B; 4: T R B L.
    """
    parts = [parse_len_in(p) for p in shorthand.split()]
    if len(parts) == 1:
        t = r = b = left = parts[0]
    elif len(parts) == 2:
        t = b = parts[0]
        r = left = parts[1]
    elif len(parts) == 3:
        t, b = parts[0], parts[2]
        r = left = parts[1]
    else:
        t, r, b, left = parts[0], parts[1], parts[2], parts[3]
    return {"top": t, "right": r, "bottom": b, "left": left}


def paper_in(size: str) -> tuple[float, float]:
    """Resolve a page size string to (width, height) in inches.

    Accepts a named size (A4/Letter/...) or two CSS lengths ('210mm 297mm').
    """
    key = size.strip().upper()
    if key in PAPER_INCHES:
        return PAPER_INCHES[key]
    toks = size.split()
    if len(toks) == 2:
        return parse_len_in(toks[0]), parse_len_in(toks[1])
    if len(toks) == 1:
        v = parse_len_in(toks[0])
        return v, v
    return PAPER_INCHES["A4"]


_FOOTER_TEMPLATE = (
    '<div style="width:100%; font-size:9pt; color:#666; text-align:center; '
    'margin:0; padding:0;"><span class="pageNumber"></span></div>'
)
_EMPTY_BOX = "<div></div>"


def print_params(manifest: dict) -> dict:
    """Build Page.printToPDF params from a template manifest.

    preferCSSPageSize is False so our explicit paper/margins are authoritative
    and the footer (page numbers) renders deterministically; Chromium ignores
    the CSS @page margin box regardless.
    """
    page = manifest.get("page", {})
    w, h = paper_in(page.get("size", "A4"))
    m = parse_margin_in(page.get("margin", "2cm"))
    page_numbers = bool(page.get("page_numbers", False))
    return {
        "paperWidth": w,
        "paperHeight": h,
        "marginTop": m["top"],
        "marginBottom": m["bottom"],
        "marginLeft": m["left"],
        "marginRight": m["right"],
        "printBackground": True,  # striped tables, th, pre, codehilite backgrounds
        "scale": 1.0,
        "preferCSSPageSize": False,
        "displayHeaderFooter": page_numbers,
        "headerTemplate": _EMPTY_BOX,  # suppress Chromium's default date/title header
        "footerTemplate": _FOOTER_TEMPLATE if page_numbers else _EMPTY_BOX,
    }


# --------------------------------------------------------------------------- #
# CDP driver
# --------------------------------------------------------------------------- #
def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _inject_base(html: str, base_dir: Path) -> str:
    """Insert a <base> tag so relative resources (images) resolve from the
    original markdown directory even though the HTML lives in a temp file.
    Path.as_uri() produces a proper file:/// URL with spaces URL-encoded."""
    base_uri = base_dir.resolve().as_uri().rstrip("/") + "/"
    tag = f'<base href="{base_uri}">'
    lower = html.lower()
    idx = lower.find("<head>")
    if idx != -1:
        pos = idx + len("<head>")
        return html[:pos] + "\n" + tag + html[pos:]
    return tag + html


def _wait_ws_endpoint(port: int, timeout: float) -> str:
    """Poll the DevTools HTTP endpoint until the browser websocket URL is up."""
    deadline = time.time() + timeout
    url = f"http://127.0.0.1:{port}/json/version"
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                ws = data.get("webSocketDebuggerUrl")
                if ws:
                    return ws
        except Exception as e:  # not up yet
            last_err = e
            time.sleep(0.15)
    raise TimeoutError(f"Chromium DevTools did not come up on port {port}: {last_err}")


class _CDP:
    """Minimal CDP client over a single websocket connection."""

    def __init__(self, ws_url: str, timeout: float):
        self.ws = websocket.create_connection(ws_url, timeout=timeout)
        self.ws.settimeout(timeout)
        self._id = 0

    def send(self, method: str, params: dict | None = None, session_id: str | None = None):
        self._id += 1
        msg = {"id": self._id, "method": method, "params": params or {}}
        if session_id:
            msg["sessionId"] = session_id
        self.ws.send(json.dumps(msg))
        return self._id

    def wait_result(self, msg_id: int):
        """Read frames until the response for msg_id arrives; return its result."""
        while True:
            frame = json.loads(self.ws.recv())
            if frame.get("id") == msg_id:
                if "error" in frame:
                    raise RuntimeError(f"CDP error: {frame['error']}")
                return frame.get("result", {})

    def wait_event(self, method: str, session_id: str | None = None):
        while True:
            frame = json.loads(self.ws.recv())
            if frame.get("method") == method and (
                session_id is None or frame.get("sessionId") == session_id
            ):
                return frame.get("params", {})

    def call(self, method: str, params: dict | None = None, session_id: str | None = None):
        return self.wait_result(self.send(method, params, session_id))

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def html_to_pdf(
    html: str,
    out_path: Path,
    base_dir: Path,
    manifest: dict,
    browser_path: str,
    timeout: float = 30.0,
) -> None:
    """Render `html` to a PDF at `out_path` using the given Chromium browser."""
    if websocket is None:
        raise RuntimeError(
            "the 'websocket-client' package is required to drive Chromium"
        )

    out_path = Path(out_path)
    tmpdir = Path(tempfile.mkdtemp(prefix="md2pdf_"))
    html_file = tmpdir / "doc.html"
    user_data = tmpdir / "udd"
    user_data.mkdir()
    html_file.write_text(_inject_base(html, base_dir), encoding="utf-8")

    port = _free_port()
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.Popen(
        [
            browser_path,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            f"--remote-debugging-port={port}",
            "--remote-allow-origins=*",  # mandatory on Chromium >=111 or ws 403s
            f"--user-data-dir={user_data}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )

    cdp: _CDP | None = None
    try:
        ws_url = _wait_ws_endpoint(port, timeout)
        cdp = _CDP(ws_url, timeout)
        target = cdp.call("Target.createTarget", {"url": "about:blank"})
        target_id = target["targetId"]
        attach = cdp.call(
            "Target.attachToTarget", {"targetId": target_id, "flatten": True}
        )
        session_id = attach["sessionId"]

        cdp.call("Page.enable", session_id=session_id)
        nav_id = cdp.send(
            "Page.navigate", {"url": html_file.as_uri()}, session_id=session_id
        )
        cdp.wait_event("Page.loadEventFired", session_id=session_id)
        cdp.wait_result(nav_id)

        result = cdp.call("Page.printToPDF", print_params(manifest), session_id=session_id)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(base64.b64decode(result["data"]))
    finally:
        if cdp is not None:
            cdp.close()
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        shutil.rmtree(tmpdir, ignore_errors=True)
