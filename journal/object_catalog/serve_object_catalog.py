#!/usr/bin/env python3
"""Local server for the Perfect Dark Asset Catalog.

Parent browser for props (StdObjects), weapons, and characters — searchable,
tag-filtered UI with WebGL mesh previews.

Usage (from repo root):
  python3 journal/object_catalog/serve_object_catalog.py
  python3 journal/object_catalog/serve_object_catalog.py --port 8816 --auto-port
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import traceback
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
_env_root = os.environ.get("PD_REPO_ROOT", "").strip()
ROOT = os.path.abspath(_env_root) if _env_root else os.path.dirname(os.path.dirname(HERE))
DEFAULT_PORT = 8816
PORT_MIN = 8816
PORT_MAX = 8835


def _file_readable(file_path: str) -> bool:
    try:
        with open(file_path, "rb") as fp:
            fp.read(1)
        return True
    except OSError:
        return False


def _resolve_app_dir() -> str:
    candidates: list[str] = []
    bundle = os.environ.get("PD_OBJECT_CATALOG_BUNDLE_DIR", "").strip()
    if bundle:
        candidates.append(bundle)
    candidates.append(HERE)
    repo_app = os.path.join(ROOT, "journal", "object_catalog")
    if repo_app not in candidates:
        candidates.append(repo_app)
    for candidate in candidates:
        html = os.path.join(candidate, "object_catalog.html")
        if _file_readable(html):
            return candidate
    return HERE


APP_DIR = _resolve_app_dir()

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _fallback_state_dir() -> str:
    """Writable state dir when kit path helpers are unavailable."""
    env_state = os.environ.get("PD_OBJECT_CATALOG_STATE_DIR", "").strip()
    if env_state:
        os.makedirs(env_state, exist_ok=True)
        return env_state
    repo_app = os.path.join(ROOT, "journal", "object_catalog")
    try:
        probe = os.path.join(repo_app, ".pd_kit_write_probe")
        with open(probe, "w", encoding="utf-8") as fp:
            fp.write("ok")
        os.unlink(probe)
        return repo_app
    except OSError:
        pass
    home = os.path.expanduser("~")
    fallback = os.path.join(
        home, "Library", "Application Support", "PerfectDarkKit", "object-catalog"
    )
    os.makedirs(fallback, exist_ok=True)
    return fallback


def _fallback_log_file() -> str:
    home = os.path.expanduser("~")
    log_dir = os.path.join(home, "Library", "Logs", "PerfectDarkKit")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "object-catalog.log")


try:
    from tools.pd_kit.paths import kit_log_file, resolve_object_catalog_state_dir  # noqa: E402

    LOG_FILE = str(kit_log_file("objectCatalog"))
    STATE_DIR = resolve_object_catalog_state_dir(ROOT)
except Exception:  # noqa: BLE001 — keep server bootable if kit helpers lag the branch
    LOG_FILE = _fallback_log_file()
    STATE_DIR = _fallback_state_dir()

from tools.pdmap.asset_catalog_api import (  # noqa: E402
    asset_by_id,
    full_asset_catalog_payload,
)
from tools.pdmap.object_catalog_api import (  # noqa: E402
    catalog_path,
    full_object_catalog_payload,
    museum_layout_payload,
    search_objects,
)
from tools.pdmap.prop_mesh import mesh_for_bbox_source, mesh_for_model_id  # noqa: E402
from tools.pdmap.anim_catalog import (  # noqa: E402
    full_catalog_payload as full_anim_catalog_payload,
    search_enriched as search_anims,
)

PORT_FILE = os.path.join(STATE_DIR, ".object_catalog_server.port")


def _log(message: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] [serve_object_catalog] {message}"
    print(line, file=sys.stderr)
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as fp:
            fp.write(line + "\n")
    except OSError:
        pass


def _log_traceback(message: str) -> None:
    body = traceback.format_exc()
    _log(f"{message}\n{body}")


def _localhost_origin(origin: str | None) -> bool:
    if not origin or origin == "null":
        return True
    host = urlparse(origin).hostname
    return host in ("localhost", "127.0.0.1", "::1")


def _cors_headers(handler: BaseHTTPRequestHandler) -> None:
    origin = handler.headers.get("Origin")
    if _localhost_origin(origin):
        handler.send_header("Access-Control-Allow-Origin", origin or "http://127.0.0.1")
        handler.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        handler.send_header("Access-Control-Allow-Headers", "Content-Type")
        handler.send_header("Vary", "Origin")


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, indent=2).encode("utf-8")
    handler.send_response(status)
    _cors_headers(handler)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _text_response(handler: BaseHTTPRequestHandler, status: int, body: bytes, content_type: str) -> None:
    handler.send_response(status)
    _cors_headers(handler)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _serve_html(handler: BaseHTTPRequestHandler) -> None:
    html_path = os.path.join(APP_DIR, "object_catalog.html")
    if not _file_readable(html_path):
        _json_response(handler, 500, {"ok": False, "error": f"Missing UI: {html_path}"})
        return
    with open(html_path, "rb") as fp:
        body = fp.read()
    _text_response(handler, 200, body, "text/html; charset=utf-8")


def _serve_static_file(handler: BaseHTTPRequestHandler, filename: str) -> None:
    clean_name = os.path.basename(filename)
    file_path = os.path.join(APP_DIR, clean_name)
    if not _file_readable(file_path):
        _json_response(handler, 404, {"ok": False, "error": f"Not found: {clean_name}"})
        return
    content_type = "application/octet-stream"
    if clean_name.endswith(".js"):
        content_type = "application/javascript; charset=utf-8"
    with open(file_path, "rb") as fp:
        body = fp.read()
    _text_response(handler, 200, body, content_type)


class Handler(BaseHTTPRequestHandler):
    server_version = "PDAssetCatalog/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        _log(f"{self.address_string()} {fmt % args}")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        _cors_headers(self)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = parse_qs(parsed.query)

        try:
            if path in ("/", "/index.html", "/object_catalog.html"):
                _serve_html(self)
                return

            if path in ("/mesh_viewer.js", "/mesh_shaders.inc.js"):
                _serve_static_file(self, path)
                return

            if path == "/api/health":
                bundle = os.environ.get("PD_OBJECT_CATALOG_BUNDLE_DIR", "").strip()
                _json_response(
                    self,
                    200,
                    {
                        "ok": True,
                        # Accept both names so older Electron shells keep working.
                        "service": "asset-catalog",
                        "legacyService": "object-catalog",
                        "repoRoot": ROOT,
                        "appDir": APP_DIR,
                        "bundleDir": bundle,
                        "catalogPath": str(catalog_path()),
                        "stateDir": STATE_DIR,
                    },
                )
                return

            if path == "/api/catalog":
                # Full asset catalog (props + weapons + characters).
                payload = full_asset_catalog_payload()
                _json_response(self, 200, payload)
                return

            if path == "/api/catalog/props":
                payload = full_object_catalog_payload()
                payload["ok"] = True
                _json_response(self, 200, payload)
                return

            if path == "/api/search":
                query = (qs.get("q") or qs.get("query") or [""])[0]
                tag = (qs.get("tag") or [""])[0]
                limit_raw = (qs.get("limit") or ["0"])[0]
                try:
                    limit = int(limit_raw)
                except ValueError:
                    limit = 0
                payload = search_objects(query, tag=tag, limit=limit)
                payload["ok"] = True
                _json_response(self, 200, payload)
                return

            if path == "/api/catalog/animations":
                include_stubs = (qs.get("stubs") or ["0"])[0].lower() in ("1", "true", "yes")
                try:
                    payload = full_anim_catalog_payload(include_stubs=include_stubs)
                    payload["ok"] = True
                    _json_response(self, 200, payload)
                except Exception as exc:
                    _log_traceback(f"GET /api/catalog/animations failed: {exc}")
                    _json_response(self, 500, {"ok": False, "error": str(exc)})
                return

            if path == "/api/animations":
                search = (qs.get("search") or qs.get("q") or [""])[0]
                category = (qs.get("category") or [""])[0]
                limit = int((qs.get("limit") or ["80"])[0])
                named_only = (qs.get("namedOnly") or ["1"])[0].lower() not in ("0", "false", "no")
                try:
                    rows = search_anims(
                        search=search,
                        category=category,
                        limit=limit,
                        named_only=named_only,
                    )
                    _json_response(
                        self,
                        200,
                        {
                            "ok": True,
                            "search": search,
                            "category": category or None,
                            "count": len(rows),
                            "animations": rows,
                        },
                    )
                except Exception as exc:
                    _log_traceback(f"GET /api/animations failed: {exc}")
                    _json_response(self, 500, {"ok": False, "error": str(exc)})
                return

            if path == "/api/layout":
                payload = museum_layout_payload()
                _json_response(self, 200, {"ok": True, "layout": payload})
                return

            if path == "/api/mesh" or path.startswith("/api/mesh/"):
                chr_name = (qs.get("chr") or [""])[0].strip()
                anim_raw = (qs.get("anim") or [""])[0].strip()
                frame_raw = (qs.get("frame") or [""])[0].strip()

                if chr_name and anim_raw:
                    try:
                        anim_index = int(anim_raw)
                        frame = int(frame_raw or "0")
                    except ValueError:
                        _json_response(self, 400, {"ok": False, "error": "Invalid anim or frame"})
                        return
                    from tools.pdmap.prop_mesh import mesh_for_character_anim
                    payload = mesh_for_character_anim(chr_name, anim_index, frame)
                    status = 200 if payload.get("ok") else 500
                    _json_response(self, status, payload)
                    return

                source = (qs.get("source") or qs.get("path") or [""])[0].strip()
                asset_id = (qs.get("asset") or [""])[0].strip()
                model_raw = ""
                if path.startswith("/api/mesh/"):
                    model_raw = path.split("/api/mesh/", 1)[1].strip("/")

                if asset_id:
                    asset = asset_by_id(asset_id)
                    if not asset:
                        _json_response(
                            self, 404, {"ok": False, "error": f"Unknown asset: {asset_id}"}
                        )
                        return
                    source = str(asset.get("sourcePath") or asset.get("bboxSource") or "")

                if source:
                    payload = dict(mesh_for_bbox_source(source))
                    payload["sourcePath"] = source
                    if asset_id:
                        payload["assetId"] = asset_id
                    status = 200 if payload.get("ok") else 404
                    _json_response(self, status, payload)
                    return

                if not model_raw:
                    model_raw = (qs.get("model") or qs.get("id") or [""])[0]
                try:
                    model_id = int(model_raw, 0)
                except ValueError:
                    _json_response(
                        self,
                        400,
                        {"ok": False, "error": f"Invalid model id: {model_raw!r}"},
                    )
                    return
                payload = mesh_for_model_id(model_id)
                status = 200 if payload.get("ok") else 404
                _json_response(self, status, payload)
                return

            _json_response(self, 404, {"ok": False, "error": f"Unknown path: {path}"})
        except Exception as exc:  # noqa: BLE001
            _log_traceback(f"GET {path} failed: {exc}")
            _json_response(self, 500, {"ok": False, "error": str(exc)})


def _port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _pick_port(host: str, preferred: int, auto_port: bool) -> int:
    if _port_free(host, preferred):
        return preferred
    if not auto_port:
        raise RuntimeError(f"Port {preferred} is busy (pass --auto-port)")
    for port in range(PORT_MIN, PORT_MAX + 1):
        if _port_free(host, port):
            return port
    raise RuntimeError(f"No free port in {PORT_MIN}–{PORT_MAX}")


def _write_port_file(port: int) -> None:
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(PORT_FILE, "w", encoding="utf-8") as fp:
        fp.write(str(port))


def main() -> int:
    parser = argparse.ArgumentParser(description="Perfect Dark Object Catalog server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--auto-port", action="store_true")
    args = parser.parse_args()

    port = _pick_port(args.host, args.port, args.auto_port)
    _write_port_file(port)
    _log(f"Listening on http://{args.host}:{port}/ (catalog={catalog_path()})")
    _log(f"STATE_DIR={STATE_DIR} APP_DIR={APP_DIR} PORT={port}")

    server = ThreadingHTTPServer((args.host, port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _log("Shutting down")
    finally:
        server.server_close()
        try:
            if os.path.isfile(PORT_FILE):
                os.unlink(PORT_FILE)
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
