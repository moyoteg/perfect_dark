#!/usr/bin/env python3
"""Local dev server for the uff map editor — static files + test-map API.

Browsers cannot spawn ``./build/pd.arm64`` directly; this helper accepts editor
JSON over HTTP and runs ``test_map.py`` on the host machine.

Usage (from repo root):
  python3 journal/uff_viewer/serve_editor.py
  python3 journal/uff_viewer/serve_editor.py --port 8765

Then open http://127.0.0.1:8765/ and use **Test / Play** in the editor panel.
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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse, unquote

HERE = os.path.dirname(os.path.abspath(__file__))
# Bundled .app copies set PD_REPO_ROOT; default infers repo from journal/uff_viewer layout.
_env_root = os.environ.get("PD_REPO_ROOT", "").strip()
ROOT = os.path.abspath(_env_root) if _env_root else os.path.dirname(os.path.dirname(HERE))
DEFAULT_PORT = 8765

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if HERE not in sys.path:
    sys.path.insert(0, HERE)


def _writable_state_dir() -> str:
    """Persist port/pid/last-test artifacts; honor PD_EDITOR_STATE_DIR when set."""
    from tools.pd_kit.paths import resolve_editor_state_dir

    return resolve_editor_state_dir(ROOT)


STATE_DIR = _writable_state_dir()
PORT_FILE = os.path.join(STATE_DIR, ".editor_server.port")

from test_map import (  # noqa: E402
    DEFAULT_LOADOUT,
    build_shell_script,
)
from tools.pdmap.play import TEST_MAP_SLOT, detect_pd_binary, play_command  # noqa: E402
from tools.pd_kit.paths import kit_log_file  # noqa: E402

_detect_pd_binary = detect_pd_binary  # legacy alias for editor bundle
LOG_FILE = str(kit_log_file("mapEditor"))

# Track detached game processes (pid -> popen) for optional /api/status polling.
_GAME_PROCS: dict[int, subprocess.Popen[Any]] = {}
_GAME_LOCK = threading.Lock()


def _localhost_origin(origin: str | None) -> bool:
    """Allow same-origin requests and localhost browser origins only."""
    if not origin:
        return True
    host = urlparse(origin).hostname
    return host in ("localhost", "127.0.0.1", "::1")


def _cors_headers(handler: BaseHTTPRequestHandler) -> None:
    origin = handler.headers.get("Origin")
    if _localhost_origin(origin):
        handler.send_header("Access-Control-Allow-Origin", origin or "http://127.0.0.1")
        handler.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
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


def pragchat_manifest(base_url: str = "http://127.0.0.1:8765") -> dict[str, Any]:
    """Describe the Map Editor studio as standard PragChat resources."""
    return {
        "version": "editor-studio-pragchat-v1",
        "default_base_url": base_url,
        "system_prompt": (
            "You are the PragChat Studio Operator for the Perfect Dark Map & Level Studio. "
            "You help creators inspect 3D maps, explain the engine architecture, generate balanced multiplayer arenas, "
            "and deploy levels directly into the native game engine. "
            "Strict invariants: all pad heights must be Y=10 above floor level, pad indices must be contiguous 0..N-1, "
            "and multiplayer arenas must have at least 4 spawn pads."
        ),
        "resources": [
            {
                "name": "MapResource",
                "description": "A 3D level or multiplayer arena in the Perfect Dark Kit.",
                "schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "level_module": {"type": "string"},
                        "box_half": {"type": "number"},
                        "box_height": {"type": "number"},
                        "spawn_y": {"type": "number"},
                        "rooms": {"type": "array"},
                        "portals": {"type": "array"},
                        "pads": {"type": "array"},
                    },
                    "required": ["name", "pads"],
                },
                "endpoints": {
                    "list": {"method": "GET", "url": "/api/maps"},
                    "get": {"method": "GET", "url": "/api/maps/:name"},
                    "create": {"method": "POST", "url": "/api/chat-generate"},
                    "custom": [
                        {
                            "name": "synthesize",
                            "method": "POST",
                            "url": "/api/chat-generate",
                            "description": "Generate or modify an arena from natural language intent.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "prompt": {"type": "string", "description": "Creation or modification prompt."},
                                    "current_map": {"type": "object", "description": "Current map state."},
                                },
                                "required": ["prompt"],
                            },
                        }
                    ],
                },
            },
            {
                "name": "PadResource",
                "description": "A 3D anchor point for player spawns, weapon pickups, ammo crates, or scenario objectives.",
                "schema": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer"},
                        "type": {"type": "string", "enum": ["spawn", "weapon", "ammo", "scenario"]},
                        "x": {"type": "number"},
                        "y": {"type": "number"},
                        "z": {"type": "number"},
                        "room": {"type": "integer"},
                    },
                    "required": ["index", "type", "x", "y", "z"],
                },
                "endpoints": {
                    "custom": [
                        {
                            "name": "append_pad",
                            "method": "POST",
                            "url": "/api/chat-generate",
                            "description": "Add pads incrementally with automatic contiguous index and Y=10 floor offset.",
                        }
                    ],
                },
            },
            {
                "name": "PlaySession",
                "description": "A compiled binary test session running the native game engine with the active map.",
                "schema": {
                    "type": "object",
                    "properties": {
                        "ok": {"type": "boolean"},
                        "pid": {"type": "integer"},
                        "command": {"type": "string"},
                    },
                },
                "endpoints": {
                    "create": {"method": "POST", "url": "/api/test-map"},
                },
            },
            {
                "name": "StudioWorkspaceSnapshot",
                "description": "PragChat projection of active level, pad counts, server status, and generative state.",
                "schema": {"type": "object", "properties": {}},
                "endpoints": {
                    "list": {"method": "GET", "url": "/pragchat/snapshot"},
                },
            },
        ],
    }


def pragchat_snapshot() -> dict[str, Any]:
    """Render current editor state in PragChat snapshot shape."""
    maps_dir = os.path.join(STATE_DIR, "maps")
    saved_count = len(os.listdir(maps_dir)) if os.path.isdir(maps_dir) else 0
    return {
        "ok": True,
        "studio": "Perfect Dark Map Editor",
        "protocol": "editor-studio-pragchat-v1",
        "channels": [
            {
                "id": "studio-general",
                "name": "Studio General",
                "topic": "Conversational generation and level synthesis for Perfect Dark 3D arena.",
            }
        ],
        "state": {
            "server_online": True,
            "saved_maps_count": saved_count,
            "default_slot": "uff",
            "active_provider": "hybrid_grammar_llm",
        },
    }


def _play_params_from_opts(opts: dict[str, Any]) -> dict[str, Any]:
    """Extract --test-map launch knobs from editor options payload."""
    loadout = opts.get("loadout")
    if isinstance(loadout, list):
        loadout = [int(w) for w in loadout]
    else:
        loadout = None
    return {
        "num_sims": int(opts.get("numSims", 8)),
        "sim_difficulty": int(opts.get("simDifficulty", 2)),
        "loadout": loadout,
        "mp_options": int(opts.get("mpOptions", 0)),
    }

def _build_test_map_argv(json_path: str, opts: dict[str, Any], *, play: bool) -> list[str]:
    """Mirror ``buildTestCommandLine`` / ``test_map.py`` flags from editor options."""
    level = str(opts.get("level", "uff")).strip().lower()
    deploy_as = str(opts.get("deployAs", level)).strip().lower()
    cmd = [
        sys.executable,
        os.path.join(HERE, "test_map.py"),
        json_path,
        "--level",
        level,
        "--mod",
        str(opts.get("mod", "mod_allinone")),
        "--scenario",
        str(int(opts.get("scenario", 0))),
        "--write-artifacts",
    ]
    if deploy_as != level:
        cmd.extend(["--deploy-as", deploy_as])
    if opts.get("seg", True):
        cmd.append("--seg")
    else:
        cmd.append("--no-seg")
    if opts.get("deploy", True):
        cmd.append("--deploy")
    else:
        cmd.append("--no-deploy")
    if opts.get("disableTextures") or opts.get("noTextures"):
        cmd.append("--no-textures")
    if opts.get("skipValidate"):
        cmd.append("--skip-validate")
    if opts.get("rebuildGame"):
        cmd.append("--rebuild-game")
    play_params = _play_params_from_opts(opts)
    cmd.extend(["--num-sims", str(play_params["num_sims"])])
    cmd.extend(["--sim-difficulty", str(play_params["sim_difficulty"])])
    if play_params["loadout"]:
        cmd.extend(["--loadout", ",".join(str(w) for w in play_params["loadout"])])
    if play_params["mp_options"]:
        cmd.extend(["--mp-options", str(play_params["mp_options"])])
    if opts.get("backup", True):
        cmd.append("--backup")
    else:
        cmd.append("--no-backup")
    if play:
        cmd.append("--play")
    return cmd


def _run_test_map(payload: dict[str, Any]) -> dict[str, Any]:
    """Execute build (+ optional detached play) and return API JSON."""
    map_data = payload.get("map")
    if not isinstance(map_data, dict):
        return {"ok": False, "error": "Missing or invalid 'map' object in request body."}

    opts = payload.get("options") if isinstance(payload.get("options"), dict) else {}
    # Get registered level modules from src/levels/
    levels_dir = os.path.join(ROOT, "src", "levels")
    registered_levels = []
    if os.path.isdir(levels_dir):
        registered_levels = [
            f[:-3] for f in os.listdir(levels_dir)
            if f.endswith(".py") and not f.startswith("_")
        ]

    raw_level = map_data.get("level_module") or map_data.get("name") or opts.get("level") or "uff"
    raw_level = str(raw_level).strip().lower()

    # Dynamic catalog-driven resolution
    level = raw_level
    for lvl in registered_levels:
        if lvl in raw_level or raw_level in lvl:
            level = lvl
            break

    deploy_as = opts.get("deployAs")
    if not deploy_as or deploy_as == "__same__":
        deploy_as = level
    else:
        deploy_as = str(deploy_as).strip().lower()
    want_play = bool(opts.get("play", True))

    map_data = dict(map_data)
    map_data["name"] = level
    # Box geometry from editor sliders (also embedded in serializeMap JSON).
    if "half" in opts and opts["half"] is not None:
        map_data["box_half"] = float(opts["half"])
    if "height" in opts and opts["height"] is not None:
        map_data["box_height"] = float(opts["height"])
    opts = dict(opts)
    opts["level"] = level
    opts["deployAs"] = deploy_as

    pd_binary = _detect_pd_binary()
    use_test_map = deploy_as == TEST_MAP_SLOT

    # Persist beside the viewer (or Application Support when repo viewer is evicted).
    json_path = os.path.join(STATE_DIR, ".last_test.json")
    with open(json_path, "w", encoding="utf-8") as fp:
        json.dump(map_data, fp, indent=2)

    build_argv = _build_test_map_argv(json_path, opts, play=False)
    build_cmd_str = " ".join(build_argv)
    full_argv = _build_test_map_argv(json_path, opts, play=want_play)
    full_cmd_str = " ".join(full_argv)

    # Dry-run: return planned commands without shell artifacts or subprocess work.
    if opts.get("dryRun"):
        play_argv = play_command(
            mod_key=str(opts.get("mod", "mod_allinone")),
            scenario=int(opts.get("scenario", 0)),
            pd_binary=pd_binary,
            use_test_map=use_test_map and want_play,
            deploy_name=deploy_as,
            **_play_params_from_opts(opts),
        )
        return {
            "ok": True,
            "dryRun": True,
            "command": build_cmd_str,
            "fullCommand": full_cmd_str,
            "playCommand": " ".join(play_argv),
            "options": opts,
            "pid": None,
        }

    # Build shell script artifact (no-op for API, but keeps .last_test.sh in sync).
    import argparse as _argparse

    play_params = _play_params_from_opts(opts)
    loadout = play_params["loadout"] if play_params["loadout"] else list(DEFAULT_LOADOUT)
    ns = _argparse.Namespace(
        level=level,
        mod=str(opts.get("mod", "mod_allinone")),
        scenario=int(opts.get("scenario", 0)),
        seg=bool(opts.get("seg", True)),
        deploy=bool(opts.get("deploy", True)),
        skip_validate=bool(opts.get("skipValidate")),
        rebuild_game=bool(opts.get("rebuildGame")),
        play=want_play,
        verbose=False,
        write_level=False,
        dry_run=False,
        binary=None,
        write_artifacts=False,
        backup=bool(opts.get("backup", True)),
        deploy_as=deploy_as,
        num_sims=play_params["num_sims"],
        sim_difficulty=play_params["sim_difficulty"],
        loadout=loadout,
        mp_options=play_params["mp_options"],
        no_textures=bool(opts.get("disableTextures") or opts.get("noTextures")),
    )
    sh_path = os.path.join(STATE_DIR, ".last_test.sh")
    try:
        with open(sh_path, "w", encoding="utf-8") as fp:
            fp.write(build_shell_script(ns, map_data))
        os.chmod(sh_path, 0o755)
    except Exception as exc:
        _log_traceback(f"build_shell_script failed: {exc}")

    if not os.path.isfile(pd_binary) and want_play:
        return {
            "ok": False,
            "command": build_cmd_str,
            "stdout": "",
            "stderr": f"Game binary not found at {pd_binary}. Build first: cmake --build build --target pd",
            "pid": None,
            "error": "missing_binary",
        }

    try:
        proc = subprocess.run(
            build_argv,
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return {
            "ok": False,
            "command": build_cmd_str,
            "stdout": "",
            "stderr": str(exc),
            "pid": None,
            "error": "subprocess_failed",
        }

    result: dict[str, Any] = {
        "ok": proc.returncode == 0,
        "command": build_cmd_str,
        "fullCommand": full_cmd_str,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "pid": None,
        "returncode": proc.returncode,
    }

    if proc.returncode != 0:
        sys.stderr.write(f"[serve_editor] build failed with returncode {proc.returncode}\n")
        sys.stderr.write(f"[serve_editor] build stdout:\n{proc.stdout}\n")
        sys.stderr.write(f"[serve_editor] build stderr:\n{proc.stderr}\n")
        result["error"] = "build_failed"
        return result

    if not want_play:
        return result

    play_argv = play_command(
        mod_key=str(opts.get("mod", "mod_allinone")),
        scenario=int(opts.get("scenario", 0)),
        pd_binary=pd_binary,
        use_test_map=use_test_map,
        deploy_name=deploy_as,
        **_play_params_from_opts(opts),
    )
    result["playCommand"] = " ".join(play_argv)

    # Replay shortcut for Play Last Test Map.app (launch only, no rebuild).
    play_sh = os.path.join(STATE_DIR, ".last_play.sh")
    with open(play_sh, "w", encoding="utf-8") as fp:
        fp.write("#!/bin/bash\n# Generated by serve_editor — replay last Test & Play launch.\n")
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
        result["ok"] = False
        result["error"] = "launch_failed"
        result["stderr"] = (result.get("stderr") or "") + f"\nLaunch failed: {exc}"
        return result

    with _GAME_LOCK:
        _GAME_PROCS[game.pid] = game

    result["pid"] = game.pid
    result["ok"] = True
    return result


class EditorHandler(BaseHTTPRequestHandler):
    """Serve ``uff_map.html`` and editor API routes."""

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("[serve_editor] " + (fmt % args) + "\n")

    def _check_cors_preflight(self) -> bool:
        if self.command == "OPTIONS":
            self.send_response(204)
            _cors_headers(self)
            self.end_headers()
            return True
        return False

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

        path = urlparse(self.path).path

        if path == "/api/health":
            pd_binary = _detect_pd_binary()
            payload = {
                "ok": True,
                "service": "uff-editor",
                "port": self.server.server_port,  # type: ignore[attr-defined]
                "repoRoot": ROOT,
                "binaryFound": os.path.isfile(pd_binary),
                "binaryPath": pd_binary,
            }
            self.send_response(200)
            _cors_headers(self)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return

        if path == "/api/status":
            with _GAME_LOCK:
                alive = {
                    pid: proc.poll() is None
                    for pid, proc in list(_GAME_PROCS.items())
                }
                dead = [pid for pid, running in alive.items() if not running]
                for pid in dead:
                    _GAME_PROCS.pop(pid, None)
            payload = {"ok": True, "games": alive}
            self.send_response(200)
            _cors_headers(self)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return

        if path == "/api/chat-status":
            payload = {
                "ok": True,
                "status": "online",
                "provider": "hybrid_grammar_llm",
            }
            self.send_response(200)
            _cors_headers(self)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return

        if path in ("/pragchat/manifest", "/pragchat/resources"):
            port = getattr(self.server, "server_port", 8765)
            manifest = pragchat_manifest(base_url=f"http://127.0.0.1:{port}")
            self.send_response(200)
            _cors_headers(self)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(manifest, indent=2).encode("utf-8"))
            return

        if path == "/pragchat/snapshot":
            snapshot = pragchat_snapshot()
            self.send_response(200)
            _cors_headers(self)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(snapshot, indent=2).encode("utf-8"))
            return

        if path == "/api/weapons":
            weapons_json_path = os.path.join(ROOT, "mods", "mod_allinone", "weapons.json")
            custom_weapons = []
            if os.path.isfile(weapons_json_path):
                try:
                    with open(weapons_json_path, "r", encoding="utf-8") as fp:
                        data = json.load(fp)
                        if isinstance(data, list):
                            custom_weapons = data
                        elif isinstance(data, dict):
                            custom_weapons = data.get("weapons", [])
                except Exception:
                    pass
            builtin_weapons = [
                {"id": 0x02, "name": "Falcon 2", "category": "pistol"},
                {"id": 0x05, "name": "MagSec 4", "category": "pistol"},
                {"id": 0x06, "name": "Mauler", "category": "pistol"},
                {"id": 0x07, "name": "Phoenix", "category": "pistol"},
                {"id": 0x08, "name": "DY357 Magnum", "category": "pistol"},
                {"id": 0x09, "name": "DY357-LX", "category": "pistol"},
                {"id": 0x0A, "name": "CMP150", "category": "smg"},
                {"id": 0x0B, "name": "Cyclone", "category": "smg"},
                {"id": 0x0C, "name": "Callisto NTG", "category": "smg"},
                {"id": 0x0D, "name": "RC-P120", "category": "smg"},
                {"id": 0x0E, "name": "Laptop Gun", "category": "smg"},
                {"id": 0x0F, "name": "Dragon", "category": "rifle"},
                {"id": 0x10, "name": "K7 Avenger", "category": "rifle"},
                {"id": 0x11, "name": "AR34", "category": "rifle"},
                {"id": 0x12, "name": "SuperDragon", "category": "heavy"},
                {"id": 0x13, "name": "Shotgun", "category": "shotgun"},
                {"id": 0x14, "name": "Reaper", "category": "heavy"},
                {"id": 0x15, "name": "Sniper Rifle", "category": "rifle"},
                {"id": 0x16, "name": "FarSight XR-20", "category": "rifle"},
                {"id": 0x17, "name": "Devastator", "category": "heavy"},
                {"id": 0x18, "name": "Rocket Launcher", "category": "heavy"},
                {"id": 0x19, "name": "Slayer", "category": "heavy"},
                {"id": 0x1B, "name": "Crossbow", "category": "special"},
                {"id": 0x1C, "name": "Tranquilizer", "category": "special"},
            ]
            payload = {
                "ok": True,
                "builtin": builtin_weapons,
                "custom": custom_weapons,
            }
            self.send_response(200)
            _cors_headers(self)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return

        if path == "/api/entities":
            entities = [
                {"type": "door", "class": "Door", "label": "Security Door", "description": "Standard or sliding blast door with collision"},
                {"type": "turret", "class": "Autogun", "label": "Defense Turret", "description": "Automated sentry gun guarding target pad"},
                {"type": "terminal", "class": "SingleMonitor", "label": "Command Terminal", "description": "Interactive data console or monitor"},
                {"type": "hazard", "class": "GasBottle", "label": "Hazard Canister", "description": "Volatile gas bottle or explosive barrel"},
                {"type": "prop", "class": "StdObject", "label": "Interactive Prop", "description": "Standard decorative or interactive prop"},
            ]
            payload = {"ok": True, "entities": entities}
            self.send_response(200)
            _cors_headers(self)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return

        if path == "/api/maps":
            maps_dict: dict[str, dict[str, Any]] = {}
            candidate_dirs = [
                (os.path.join(STATE_DIR, "maps"), "file"),
                (os.path.join(ROOT, "journal", "map_learn", "maps"), "learned"),
                (os.path.join(ROOT, "mods", "mod_allinone", "levels"), "mod"),
            ]
            for cdir, src_label in candidate_dirs:
                if not os.path.isdir(cdir):
                    continue
                for f in sorted(os.listdir(cdir)):
                    if f.endswith(".json") and not f.startswith("."):
                        name = f[:-5]
                        if name in maps_dict:
                            continue
                        file_path = os.path.join(cdir, f)
                        pad_count = 0
                        try:
                            with open(file_path, "r", encoding="utf-8") as fp:
                                map_data = json.load(fp)
                                pads = map_data.get("pads", [])
                                if isinstance(pads, list):
                                    pad_count = len(pads)
                                elif isinstance(map_data.get("spawns"), list):
                                    pad_count = len(map_data.get("spawns", []))
                        except Exception:
                            pass
                        if pad_count == 0:
                            continue
                        maps_dict[name] = {
                            "name": name,
                            "source": src_label,
                            "padCount": pad_count,
                        }

            # Discover any standalone python level modules in src/levels/ not yet cached as JSON
            levels_dir = os.path.join(ROOT, "src", "levels")
            if os.path.isdir(levels_dir):
                for f in sorted(os.listdir(levels_dir)):
                    if f.endswith(".py") and not f.startswith("__") and f not in ("practice_common.py", "office_learn_01_door.py"):
                        name = f[:-3]
                        if name in maps_dict:
                            continue
                        maps_dict[name] = {
                            "name": name,
                            "source": "level",
                            "padCount": 16,
                        }

            maps_list = sorted(maps_dict.values(), key=lambda x: str(x["name"]))
            self.send_response(200)
            _cors_headers(self)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"maps": maps_list}).encode("utf-8"))
            return

        if path.startswith("/api/maps/"):
            name = unquote(path[len("/api/maps/"):])
            name = os.path.basename(name)
            candidate_dirs = [
                os.path.join(STATE_DIR, "maps"),
                os.path.join(ROOT, "journal", "map_learn", "maps"),
                os.path.join(ROOT, "mods", "mod_allinone", "levels"),
            ]
            file_path = None
            for cdir in candidate_dirs:
                probe = os.path.join(cdir, f"{name}.json")
                if os.path.isfile(probe):
                    file_path = probe
                    break
            if not file_path:
                py_probe = os.path.join(ROOT, "src", "levels", f"{name}.py")
                if os.path.isfile(py_probe):
                    try:
                        import importlib
                        from tools.pdmap.level_to_editor import mapdef_to_editor_json
                        mod = importlib.import_module(f"src.levels.{name}")
                        if hasattr(mod, "build"):
                            m = mod.build()
                            map_data = mapdef_to_editor_json(m)
                            self.send_response(200)
                            _cors_headers(self)
                            self.send_header("Content-Type", "application/json; charset=utf-8")
                            self.end_headers()
                            self.wfile.write(json.dumps({"map": map_data}).encode("utf-8"))
                            return
                    except Exception as exc:
                        self.send_error(500, f"Error compiling level module {name}: {exc}")
                        return
                self.send_error(404, f"Map not found: {name}")
                return
            try:
                with open(file_path, "r", encoding="utf-8") as fp:
                    map_data = json.load(fp)
                if "pads" not in map_data and "spawns" in map_data:
                    pads = []
                    idx = 0
                    for s in map_data.get("spawns", []):
                        pads.append({"index": idx, "type": "spawn", "x": s.get("x", 0), "y": s.get("y", 10), "z": s.get("z", 0), "room": s.get("room", 1)})
                        idx += 1
                    for w in map_data.get("weapons", []):
                        pads.append({"index": idx, "type": "weapon", "weapon": w.get("weapon", 1), "x": 0, "y": 10, "z": 0, "room": 1})
                        idx += 1
                    map_data["pads"] = pads
                self.send_response(200)
                _cors_headers(self)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"map": map_data}).encode("utf-8"))
            except Exception as exc:
                self.send_error(500, str(exc))
            return

        # Static files from journal/uff_viewer/
        if path in ("/", "/index.html"):
            rel = "uff_map.html"
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
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:  # noqa: N802
        if self._check_cors_preflight():
            return
        if self._reject_origin():
            return

        path = urlparse(self.path).path

        if path == "/api/chat-generate":
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b""
            try:
                payload = json.loads(raw.decode("utf-8") if raw else "{}")
            except Exception as exc:
                _json_response(self, 400, {"ok": False, "error": f"invalid_json: {exc}"})
                return

            if not isinstance(payload, dict):
                _json_response(self, 400, {"ok": False, "error": "Request body must be a JSON object"})
                return

            prompt = payload.get("prompt")
            if prompt is None or not isinstance(prompt, str):
                _json_response(self, 400, {"ok": False, "error": "Missing or invalid 'prompt' field in request body"})
                return

            current_map = payload.get("current_map")
            if current_map is not None and not isinstance(current_map, dict):
                _json_response(self, 400, {"ok": False, "error": "Invalid 'current_map' field; must be a dict or null"})
                return

            history = payload.get("history")
            if history is not None and not isinstance(history, list):
                _json_response(self, 400, {"ok": False, "error": "Invalid 'history' field; must be a list or null"})
                return

            try:
                from tools.pdmap.generative_assistant import GenerativeAssistant

                assistant = GenerativeAssistant()
                res = assistant.process_prompt(prompt, current_map, history)
            except Exception as exc:
                _log_traceback(f"POST /api/chat-generate failed: {exc}")
                _json_response(self, 500, {"ok": False, "error": str(exc)})
                return

            if isinstance(res, dict) and res.get("ok") is False:
                _json_response(self, 500, res)
                return

            if isinstance(res, dict):
                reply = res.get("reply", "")
                map_data = res.get("map")
                action = res.get("action")
            else:
                reply = str(res) if res is not None else ""
                map_data = current_map
                action = None

            response_payload: dict[str, Any] = {
                "ok": True,
                "reply": reply,
                "map": map_data,
                "action": action,
            }
            if isinstance(res, dict):
                for k, v in res.items():
                    if k not in response_payload:
                        response_payload[k] = v

            if isinstance(map_data, dict) and map_data.get("pads"):
                raw_name = str(map_data.get("name") or "synthesized_arena")
                map_slug = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in raw_name.lower())[:32]
                try:
                    maps_dir = os.path.join(STATE_DIR, "maps")
                    os.makedirs(maps_dir, exist_ok=True)
                    target_file = os.path.join(maps_dir, f"{map_slug}.json")
                    with open(target_file, "w", encoding="utf-8") as fp:
                        json.dump(map_data, fp, indent=2)
                    response_payload["saved_map_id"] = map_slug
                except Exception as save_err:
                    _log_traceback(f"Auto-save chat generated map failed: {save_err}")

            _json_response(self, 200, response_payload)
            return

        if path != "/api/test-map":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(raw.decode("utf-8") if raw else "{}")
        except json.JSONDecodeError as exc:
            _json_response(self, 400, {"ok": False, "error": f"invalid_json: {exc}"})
            return

        try:
            result = _run_test_map(payload)
        except Exception as exc:
            _log_traceback(f"POST /api/test-map failed: {exc}")
            _json_response(self, 500, {"ok": False, "error": str(exc)})
            return

        status = 200 if result.get("ok") else 500
        self.send_response(status)
        _cors_headers(self)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(result, indent=2).encode("utf-8"))

    def do_PUT(self) -> None:  # noqa: N802
        if self._check_cors_preflight():
            return
        if self._reject_origin():
            return

        path = urlparse(self.path).path
        if path.startswith("/api/maps/"):
            name = unquote(path[len("/api/maps/"):])
            name = os.path.basename(name)
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b""
            try:
                payload = json.loads(raw.decode("utf-8") if raw else "{}")
                map_data = payload.get("map")
                if not map_data:
                    self.send_response(400)
                    _cors_headers(self)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": False, "error": "missing map object"}).encode("utf-8"))
                    return
                
                maps_dir = os.path.join(STATE_DIR, "maps")
                os.makedirs(maps_dir, exist_ok=True)
                file_path = os.path.join(maps_dir, f"{name}.json")
                with open(file_path, "w", encoding="utf-8") as fp:
                    json.dump(map_data, fp, indent=2)
                
                self.send_response(200)
                _cors_headers(self)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
            except Exception as exc:
                self.send_response(500)
                _cors_headers(self)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(exc)}).encode("utf-8"))
            return
        self.send_error(404)

    def do_DELETE(self) -> None:  # noqa: N802
        if self._check_cors_preflight():
            return
        if self._reject_origin():
            return

        path = urlparse(self.path).path
        if path.startswith("/api/maps/"):
            name = unquote(path[len("/api/maps/"):])
            name = os.path.basename(name)
            file_path = os.path.join(STATE_DIR, "maps", f"{name}.json")
            if os.path.isfile(file_path):
                try:
                    os.remove(file_path)
                    self.send_response(200)
                    _cors_headers(self)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
                    return
                except Exception as exc:
                    self.send_response(500)
                    _cors_headers(self)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": False, "error": str(exc)}).encode("utf-8"))
                    return
            self.send_error(404, f"Map not found: {name}")
            return
        self.send_error(404)


def _port_bindable(host: str, port: int) -> bool:
    """Return True when ``host:port`` can be bound (port is free)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def _pick_port(host: str, start: int, *, max_tries: int = 20) -> int:
    """Choose the first bindable port in ``[start, start + max_tries)``."""
    for port in range(start, start + max_tries):
        if _port_bindable(host, port):
            return port
    raise OSError(f"No free port in range {start}-{start + max_tries - 1}")


def _write_port_file(port: int) -> None:
    with open(PORT_FILE, "w", encoding="utf-8") as fp:
        fp.write(str(port))


def _log_traceback(message: str) -> None:
    """Append a traceback to the shared editor log for Electron/shell diagnostics."""
    import traceback
    from datetime import datetime

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    body = traceback.format_exc()
    line = f"[{stamp}] [serve_editor] {message}\n{body}"
    print(line, file=sys.stderr, end="" if line.endswith("\n") else "\n")
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as fp:
            fp.write(line)
            if not line.endswith("\n"):
                fp.write("\n")
    except OSError:
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve uff map editor + test-map API.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port (default: {DEFAULT_PORT})")
    parser.add_argument(
        "--auto-port",
        action="store_true",
        help=f"If --port is busy, bind the next free port up to +19 (writes {PORT_FILE})",
    )
    args = parser.parse_args(argv)

    os.chdir(HERE)
    port = args.port
    if args.auto_port:
        port = _pick_port(args.host, args.port)
    elif not _port_bindable(args.host, port):
        print(
            f"Port {port} is already in use on {args.host}. "
            f"Stop the other process or re-run with --auto-port.",
            file=sys.stderr,
        )
        return 1

    try:
        server = ThreadingHTTPServer((args.host, port), EditorHandler)
    except OSError as exc:
        print(f"Failed to bind {args.host}:{port}: {exc}", file=sys.stderr)
        return 1

    _write_port_file(port)
    url = f"http://{args.host}:{port}/"
    print(f"uff editor server at {url}")
    print(f"PORT={port}")
    print("  GET  /api/health        — server + binary probe")
    print("  GET  /api/chat-status   — generative chat status")
    print("  POST /api/chat-generate — generative map assistant")
    print("  POST /api/test-map      — build + launch via test_map.py")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0
    finally:
        try:
            os.remove(PORT_FILE)
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        _log_traceback(f"Fatal error in serve_editor.py: {exc}")
        raise SystemExit(1) from exc
