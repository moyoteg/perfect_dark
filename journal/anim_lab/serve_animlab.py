#!/usr/bin/env python3
"""Local dev server for the Perfect Dark Animation Lab.

Serves a lightweight UI plus APIs to build the animlab parade map, launch
``--test-animlab`` or ``--test-map``, search the animation catalog, and deploy
uff or animlab independently.

Usage (from repo root):
  python3 journal/anim_lab/serve_animlab.py
  python3 journal/anim_lab/serve_animlab.py --port 8776 --auto-port
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import socket
import subprocess
import sys
import threading
import traceback
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
_env_root = os.environ.get("PD_REPO_ROOT", "").strip()
ROOT = os.path.abspath(_env_root) if _env_root else os.path.dirname(os.path.dirname(HERE))
DEFAULT_PORT = 8776

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.pd_kit.paths import kit_log_file, resolve_anim_lab_state_dir  # noqa: E402

LOG_FILE = str(kit_log_file("animLab"))

from tools.pdmap.anim_catalog import (  # noqa: E402
    CATEGORY_META,
    full_catalog_payload,
    search_enriched,
)
from tools.pdmap.core import ROMID  # noqa: E402
from tools.pdmap.play import (  # noqa: E402
    MOD_CHOICES,
    SCENARIO_CHOICES,
    STAGE_ANIMLAB,
    detect_pd_binary,
    play_command,
)

# Registered pdmap arenas bootable from the Animation Lab UI.
MAP_PRESETS: dict[str, dict[str, Any]] = {
    "animlab": {
        "label": "Animation Lab",
        "description": "20-guard parade line — best for Combat (scenario 0)",
        "scenarios": [0],
        "bootFlag": "--test-animlab",
        "stage": STAGE_ANIMLAB,
        "hint": "Walk north from spawn toward the guard line.",
    },
    "uff": {
        "label": "UFF Arena",
        "description": "Full test arena with weapons, hill, and CTF pads",
        "scenarios": list(SCENARIO_CHOICES),
        "bootFlag": "--test-map",
        "hint": "Standard uff box arena with all MP scenarios.",
    },
}

SIM_DIFFICULTIES = {
    0: "Meat",
    1: "Easy",
    2: "Normal",
    3: "Hard",
    4: "Perfect",
    5: "Dark",
}

_GAME_PROCS: dict[int, subprocess.Popen[Any]] = {}
_GAME_LOCK = threading.Lock()
_BUILD_LOCK = threading.Lock()


def _writable_state_dir() -> str:
    return resolve_anim_lab_state_dir(ROOT)


STATE_DIR = _writable_state_dir()
PORT_FILE = os.path.join(STATE_DIR, ".anim_lab_server.port")
LAST_DEPLOY_FILE = os.path.join(STATE_DIR, "last_deploy.json")


def _log(message: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] [serve_animlab] {message}"
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
    if not origin:
        return True
    host = urlparse(origin).hostname
    return host in ("localhost", "127.0.0.1", "::1")


def _cors_headers(handler: BaseHTTPRequestHandler) -> None:
    origin = handler.headers.get("Origin")
    if _localhost_origin(origin):
        handler.send_header("Access-Control-Allow-Origin", origin or "http://127.0.0.1")
        handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
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


def _read_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length) if length else b""
    if not raw:
        return {}
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON body must be an object")
    return data


def _showcase_payload() -> list[dict[str, Any]]:
    return full_catalog_payload()["parade"]


def _build_level(level: str, *, seg: bool, deploy: bool) -> dict[str, Any]:
    level = level.strip().lower()
    if level not in ("animlab", "uff"):
        return {"ok": False, "error": f"unsupported level {level!r}; use animlab or uff"}

    cmd = [
        sys.executable,
        os.path.join(ROOT, "tools", "pdmap.py"),
        "build",
        level,
    ]
    if seg:
        cmd.append("--seg")
    if deploy:
        cmd.append("--deploy")

    cmd_str = " ".join(shlex.quote(part) for part in cmd)
    _log(f"build start: {cmd_str}")

    with _BUILD_LOCK:
        try:
            proc = subprocess.run(
                cmd,
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            return {
                "ok": False,
                "error": "subprocess_failed",
                "command": cmd_str,
                "stderr": str(exc),
            }

    ok = proc.returncode == 0
    result: dict[str, Any] = {
        "ok": ok,
        "level": level,
        "command": cmd_str,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "returncode": proc.returncode,
    }
    if not ok:
        result["error"] = "build_failed"
    else:
        _write_last_deploy(level)
    deploy_note = ""
    if level == "animlab":
        deploy_note = f"Deployed bg_animlab.* (STAGE_ANIMLAB 0x{STAGE_ANIMLAB:x}, --test-animlab)"
    elif level == "uff":
        deploy_note = "Deployed bg_uff.* (--test-map)"
    result["note"] = deploy_note
    _log(f"build {'ok' if ok else 'failed'}: {level} rc={proc.returncode}")
    return result


def _read_last_deploy() -> dict[str, Any]:
    try:
        with open(LAST_DEPLOY_FILE, encoding="utf-8") as fp:
            data = json.load(fp)
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"map": "unknown", "at": None}


def _write_last_deploy(level: str) -> None:
    payload = {"map": level, "at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")}
    try:
        with open(LAST_DEPLOY_FILE, "w", encoding="utf-8") as fp:
            json.dump(payload, fp, indent=2)
    except OSError:
        pass


def _launch_hint(level: str, scenario: int) -> str:
    preset = MAP_PRESETS.get(level, {})
    base = str(preset.get("hint") or "Use WASD + mouse in-game.")
    name = SCENARIO_CHOICES.get(scenario, f"Scenario {scenario}")
    if level == "animlab" and scenario != 0:
        return (
            f"{base} Note: animlab only wires Combat anchors — "
            f"{name} may behave oddly; use UFF Arena for scenario {scenario}."
        )
    return f"{name} on {preset.get('label', level)}. {base}"


def _play_game(payload: dict[str, Any]) -> dict[str, Any]:
    mod_key = str(payload.get("mod", "mod_allinone"))
    scenario = int(payload.get("scenario", 0))
    num_sims = int(payload.get("numSims", 0))
    sim_difficulty = int(payload.get("simDifficulty", 2))
    solo = bool(payload.get("solo", num_sims == 0))
    level = str(payload.get("level") or payload.get("map") or _read_last_deploy().get("map") or "animlab")

    if scenario not in SCENARIO_CHOICES:
        return {"ok": False, "error": f"invalid scenario {scenario}"}

    pd_binary = detect_pd_binary()
    if not os.path.isfile(pd_binary):
        return {
            "ok": False,
            "error": "missing_binary",
            "binaryPath": pd_binary,
            "stderr": f"Game binary not found at {pd_binary}. Build: cmake --build build --target pd",
        }

    if mod_key not in MOD_CHOICES:
        return {"ok": False, "error": f"unknown mod {mod_key!r}"}

    play_argv = play_command(
        mod_key=mod_key,
        scenario=scenario,
        pd_binary=pd_binary,
        level=level,
    )
    play_argv.extend(["--num-sims", str(num_sims)])
    play_argv.extend(["--sim-difficulty", str(sim_difficulty)])
    if solo:
        play_argv.append("--solo")

    cmd_str = " ".join(shlex.quote(part) for part in play_argv)
    _log(f"play launch: {cmd_str}")

    launch_meta = {
        "level": level,
        "scenario": scenario,
        "numSims": num_sims,
        "simDifficulty": sim_difficulty,
        "mod": mod_key,
        "command": cmd_str,
        "launchedAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    meta_path = os.path.join(STATE_DIR, "last_launch.json")
    try:
        with open(meta_path, "w", encoding="utf-8") as fp:
            json.dump(launch_meta, fp, indent=2)
    except OSError:
        pass

    play_sh = os.path.join(STATE_DIR, ".last_play.sh")
    with open(play_sh, "w", encoding="utf-8") as fp:
        fp.write("#!/bin/bash\n# Generated by serve_animlab — replay last launch.\n")
        fp.write("set -euo pipefail\n")
        fp.write(f'cd "{ROOT}"\n')
        fp.write("exec " + " ".join(shlex.quote(arg) for arg in play_argv) + "\n")
    os.chmod(play_sh, 0o755)

    try:
        game = subprocess.Popen(
            play_argv,
            cwd=ROOT,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        return {"ok": False, "error": "launch_failed", "command": cmd_str, "stderr": str(exc)}

    with _GAME_LOCK:
        _GAME_PROCS[game.pid] = game

    return {
        "ok": True,
        "pid": game.pid,
        "command": cmd_str,
        "scenario": scenario,
        "scenarioName": SCENARIO_CHOICES[scenario],
        "level": level,
        "hint": _launch_hint(level, scenario),
    }


def _launch(payload: dict[str, Any]) -> dict[str, Any]:
    """Optional build/deploy, then launch with scenario + sim options."""
    level = str(payload.get("map") or payload.get("level") or "animlab").strip().lower()
    build = bool(payload.get("build", True))
    play = bool(payload.get("play", True))

    if level not in MAP_PRESETS:
        return {"ok": False, "error": f"unknown map {level!r}; choose {', '.join(MAP_PRESETS)}"}

    scenario = int(payload.get("scenario", 0))
    result: dict[str, Any] = {"ok": True, "map": level, "scenario": scenario}

    if build:
        build_result = _build_level(level, seg=True, deploy=True)
        result["build"] = build_result
        if not build_result.get("ok"):
            result["ok"] = False
            result["error"] = build_result.get("error", "build_failed")
            return result
        _write_last_deploy(level)

    if not play:
        result["note"] = f"Deployed {level} without launching."
        return result

    play_payload = dict(payload)
    play_payload["level"] = level
    play_result = _play_game(play_payload)
    result["play"] = play_result
    result["playCommand"] = play_result.get("command")
    result["pid"] = play_result.get("pid")
    result["hint"] = play_result.get("hint")
    result["ok"] = bool(play_result.get("ok"))
    if not result["ok"]:
        result["error"] = play_result.get("error")
        result["stderr"] = play_result.get("stderr")
    return result


def _replay_last_launch() -> dict[str, Any]:
    play_sh = os.path.join(STATE_DIR, ".last_play.sh")
    if not os.path.isfile(play_sh):
        return {"ok": False, "error": "no_last_launch", "stderr": "No previous launch (.last_play.sh missing)."}
    try:
        game = subprocess.Popen(
            ["/bin/bash", play_sh],
            cwd=ROOT,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        return {"ok": False, "error": "launch_failed", "stderr": str(exc)}
    with _GAME_LOCK:
        _GAME_PROCS[game.pid] = game
    meta = _read_last_deploy()
    return {"ok": True, "pid": game.pid, "replayed": True, "lastDeploy": meta}


def _play_config_payload() -> dict[str, Any]:
    scenarios = [
        {"id": sid, "name": name, "flag": f"--scenario-{sid}"}
        for sid, name in sorted(SCENARIO_CHOICES.items())
    ]
    maps = [
        {
            "id": key,
            "label": preset["label"],
            "description": preset["description"],
            "scenarios": preset["scenarios"],
        }
        for key, preset in MAP_PRESETS.items()
    ]
    return {
        "ok": True,
        "scenarios": scenarios,
        "maps": maps,
        "mods": [{"id": k, "path": v} for k, v in sorted(MOD_CHOICES.items())],
        "simDifficulties": [{"id": k, "name": v} for k, v in sorted(SIM_DIFFICULTIES.items())],
        "defaults": {
            "map": "animlab",
            "scenario": 0,
            "numSims": 0,
            "simDifficulty": 2,
            "mod": "mod_allinone",
            "buildBeforeLaunch": True,
        },
        "lastDeploy": _read_last_deploy(),
        "lastLaunchPath": os.path.join(STATE_DIR, ".last_play.sh"),
    }


def _build_and_play(payload: dict[str, Any]) -> dict[str, Any]:
    """Legacy alias — prefer POST /api/launch."""
    level = str(payload.get("level") or payload.get("map") or "animlab")
    launch_payload = dict(payload)
    launch_payload["map"] = level
    launch_payload["build"] = bool(payload.get("deploy", True))
    launch_payload["play"] = bool(payload.get("play", True))
    return _launch(launch_payload)


class AnimLabHandler(BaseHTTPRequestHandler):
    """Serve anim_lab.html and Animation Lab API routes."""

    def log_message(self, fmt: str, *args: Any) -> None:
        _log(fmt % args)

    def _reject_origin(self) -> bool:
        origin = self.headers.get("Origin")
        if origin and not _localhost_origin(origin):
            _json_response(self, 403, {"ok": False, "error": "origin_not_allowed"})
            return True
        return False

    def do_OPTIONS(self) -> None:  # noqa: N802
        if self._reject_origin():
            return
        self.send_response(204)
        _cors_headers(self)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self._reject_origin():
            return

        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/api/health":
            pd_binary = detect_pd_binary()
            bundle_dir = os.environ.get("PD_ANIM_LAB_BUNDLE_DIR", "").strip()
            payload = {
                "ok": True,
                "service": "anim-lab",
                "port": self.server.server_port,  # type: ignore[attr-defined]
                "repoRoot": ROOT,
                "binaryFound": os.path.isfile(pd_binary),
                "binaryPath": pd_binary,
                "romid": ROMID,
                "stageAnimlab": STAGE_ANIMLAB,
                "bootFlags": {"animlab": "--test-animlab", "uff": "--test-map"},
                "bundleDir": bundle_dir or None,
                "docs": "docs/CHARACTER_ANIMATIONS.md",
            }
            _json_response(self, 200, payload)
            return

        if path == "/api/status":
            with _GAME_LOCK:
                alive = {
                    pid: proc.poll() is None
                    for pid, proc in list(_GAME_PROCS.items())
                }
                for pid, running in list(alive.items()):
                    if not running:
                        _GAME_PROCS.pop(pid, None)
            _json_response(self, 200, {"ok": True, "games": alive})
            return

        if path == "/api/catalog":
            include_stubs = (query.get("stubs") or ["0"])[0].lower() in ("1", "true", "yes")
            try:
                payload = full_catalog_payload(include_stubs=include_stubs)
            except Exception as exc:
                _log_traceback(f"GET /api/catalog failed: {exc}")
                _json_response(self, 500, {"ok": False, "error": str(exc)})
                return
            payload["ok"] = True
            _json_response(self, 200, payload)
            return

        if path == "/api/play-config":
            _json_response(self, 200, _play_config_payload())
            return

        if path == "/api/showcase":
            _json_response(self, 200, {"ok": True, "showcase": _showcase_payload()})
            return

        if path == "/api/animations":
            search = (query.get("search") or [""])[0]
            category = (query.get("category") or [""])[0]
            limit = int((query.get("limit") or ["80"])[0])
            named_only = (query.get("namedOnly") or ["1"])[0].lower() not in ("0", "false", "no")
            try:
                rows = search_enriched(
                    search=search,
                    category=category,
                    limit=limit,
                    named_only=named_only,
                )
            except Exception as exc:
                _log_traceback(f"GET /api/animations failed: {exc}")
                _json_response(self, 500, {"ok": False, "error": str(exc)})
                return
            _json_response(
                self,
                200,
                {
                    "ok": True,
                    "search": search,
                    "category": category or None,
                    "count": len(rows),
                    "animations": rows,
                    "categories": {k: v["title"] for k, v in CATEGORY_META.items()},
                },
            )
            return

        if path in ("/", "/index.html"):
            rel = "anim_lab.html"
        else:
            rel = path.lstrip("/")
            if ".." in rel or rel.startswith("/"):
                self.send_error(403)
                return

        file_path = os.path.join(HERE, rel)
        if not os.path.isfile(file_path):
            self.send_error(404, f"Not found: {rel}")
            return

        content_type = "application/octet-stream"
        if rel.endswith(".html"):
            content_type = "text/html; charset=utf-8"
        elif rel.endswith(".js"):
            content_type = "application/javascript; charset=utf-8"
        elif rel.endswith(".css"):
            content_type = "text/css; charset=utf-8"
        elif rel.endswith(".json"):
            content_type = "application/json; charset=utf-8"

        with open(file_path, "rb") as fp:
            data = fp.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:  # noqa: N802
        if self._reject_origin():
            return

        path = urlparse(self.path).path
        try:
            payload = _read_json_body(self)
        except (json.JSONDecodeError, ValueError) as exc:
            _json_response(self, 400, {"ok": False, "error": f"invalid_json: {exc}"})
            return

        try:
            if path == "/api/build":
                result = _build_level(
                    str(payload.get("level", "animlab")),
                    seg=bool(payload.get("seg", True)),
                    deploy=bool(payload.get("deploy", True)),
                )
            elif path == "/api/play":
                result = _play_game(payload)
            elif path == "/api/launch":
                result = _launch(payload)
            elif path == "/api/replay":
                result = _replay_last_launch()
            elif path == "/api/build-play":
                result = _build_and_play(payload)
            else:
                self.send_error(404)
                return
        except Exception as exc:
            _log_traceback(f"POST {path} failed: {exc}")
            _json_response(self, 500, {"ok": False, "error": str(exc)})
            return

        status = 200 if result.get("ok") else 500
        _json_response(self, status, result)


def _port_bindable(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def _pick_port(host: str, start: int, *, max_tries: int = 20) -> int:
    for port in range(start, start + max_tries):
        if _port_bindable(host, port):
            return port
    raise OSError(f"No free port in range {start}-{start + max_tries - 1}")


def _write_port_file(port: int) -> None:
    with open(PORT_FILE, "w", encoding="utf-8") as fp:
        fp.write(str(port))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve Animation Lab UI + build/play API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--auto-port",
        action="store_true",
        help=f"If --port is busy, bind the next free port up to +19",
    )
    args = parser.parse_args(argv)

    os.chdir(HERE)
    port = args.port
    if args.auto_port:
        port = _pick_port(args.host, args.port)
    elif not _port_bindable(args.host, port):
        print(
            f"Port {port} is already in use on {args.host}. Re-run with --auto-port.",
            file=sys.stderr,
        )
        return 1

    try:
        server = ThreadingHTTPServer((args.host, port), AnimLabHandler)
    except OSError as exc:
        print(f"Failed to bind {args.host}:{port}: {exc}", file=sys.stderr)
        return 1

    _write_port_file(port)
    url = f"http://{args.host}:{port}/"
    print(f"Animation Lab server at {url}")
    print(f"PORT={port}")
    print("  GET  /api/health       — repo + binary probe")
    print("  GET  /api/showcase     — parade guard / anim table")
    print("  GET  /api/animations   — search animation catalog")
    print("  POST /api/build-play   — build animlab + launch game")
    _log(f"listening on {args.host}:{port} repo={ROOT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
