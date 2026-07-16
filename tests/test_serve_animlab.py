"""Tests for the Animation Lab HTTP server and posed mesh APIs.

Runnable two ways:
    python3 tests/test_serve_animlab.py
    python3 -m pytest tests/test_serve_animlab.py
"""

from __future__ import annotations

import json
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "journal" / "anim_lab"))

from serve_animlab import AnimLabHandler


class _TestServer:
    def __init__(self) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), AnimLabHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def __enter__(self) -> "_TestServer":
        self.thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()

    def get(self, path: str) -> object:
        with urllib.request.urlopen(self.base + path, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    def get_status(self, path: str) -> tuple[int, object | None]:
        req = urllib.request.Request(self.base + path)
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                body = response.read().decode("utf-8")
                return response.status, json.loads(body) if body else None
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8")
            payload = json.loads(raw) if raw else None
            return exc.code, payload


def test_api_health():
    with _TestServer() as server:
        data = server.get("/api/health")
        assert data["ok"] is True
        assert data["service"] == "anim-lab"


def test_api_animations():
    with _TestServer() as server:
        data = server.get("/api/animations?limit=5")
        assert data["ok"] is True
        assert "animations" in data
        assert len(data["animations"]) <= 5


def test_api_mesh_valid():
    with _TestServer() as server:
        # Request valid Joanna Dark posed mesh
        status, data = server.get_status("/api/mesh?chr=dark_combat&anim=1&frame=0")
        assert status == 200
        assert data["ok"] is True
        assert data["chr"] == "dark_combat"
        assert data["anim"] == 1
        assert data["frame"] == 0
        assert "positions" in data
        assert "indices" in data
        assert data["vertexCount"] > 0


def test_api_mesh_invalid_character():
    with _TestServer() as server:
        # Request non-existent character model
        status, data = server.get_status("/api/mesh?chr=nonexistent_body_name&anim=1&frame=0")
        assert status == 404 or status == 200  # API returns error in payload or status code
        assert data["ok"] is False
        assert "error" in data


def test_api_mesh_invalid_anim_fallback():
    with _TestServer() as server:
        # Invalid animation index should fallback to bind pose or return valid mesh payload
        status, data = server.get_status("/api/mesh?chr=dark_combat&anim=99999&frame=0")
        assert status == 200 or status == 400 or status == 404
        if status == 200:
            assert "positions" in data
            assert data["vertexCount"] > 0


if __name__ == "__main__":
    test_api_health()
    test_api_animations()
    test_api_mesh_valid()
    test_api_mesh_invalid_character()
    test_api_mesh_invalid_anim_fallback()
    print("ok")
