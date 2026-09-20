"""Tests for PragChat Platform Integration in the Perfect Dark Kit Map Editor.

Validates the first-party PragChat contract endpoints:
- GET /pragchat/manifest (Resource Schemas: MapResource, PadResource, PlaySession, StudioWorkspaceSnapshot)
- GET /pragchat/resources (Alias to manifest)
- GET /pragchat/snapshot (Live editor workspace projection)
- POST /api/chat-generate (PragChat tool execution seam for natural language level synthesis and demystification)

Strictly adheres to:
- Universal PragProduct Building Block Mandate
- Universal Calibrated Zero-Emoji Standard
- Locked Specs & Zero Test Assertion Tampering
"""

from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
import pytest

from journal.uff_viewer.serve_editor import EditorHandler, pragchat_manifest, pragchat_snapshot
from tools.pdmap.from_json import EditorMapSpec
from tools.pdmap.validate import validate_mapdef


def assert_no_emojis(text: str) -> None:
    """Enforce the Universal Calibrated Zero-Emoji Standard."""
    for ch in text:
        code = ord(ch)
        is_emoji = (
            (0x1F600 <= code <= 0x1F64F)
            or (0x1F300 <= code <= 0x1F5FF)
            or (0x1F680 <= code <= 0x1F6FF)
            or (0x1F900 <= code <= 0x1F9FF)
            or (0x1FA00 <= code <= 0x1FAFF)
            or (0x2600 <= code <= 0x26FF)
            or (0x2700 <= code <= 0x27BF)
        )
        assert not is_emoji, f"Unicode emoji {ch!r} (U+{code:04X}) detected in text: {text!r}"


@pytest.fixture(scope="module")
def editor_server():
    """Spin up an in-process ThreadingHTTPServer with EditorHandler on an ephemeral port."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), EditorHandler)
    port = server.server_port
    th = threading.Thread(target=server.serve_forever, daemon=True)
    th.start()
    base_url = f"http://127.0.0.1:{port}"
    try:
        yield {"server": server, "port": port, "base_url": base_url}
    finally:
        server.shutdown()
        server.server_close()


class TestPragChatManifest:
    """Validate GET /pragchat/manifest and GET /pragchat/resources contracts."""

    def test_manifest_unit_function(self):
        """Verify pragchat_manifest() generator function output structure."""
        manifest = pragchat_manifest(base_url="http://127.0.0.1:8765")
        assert manifest["version"] == "editor-studio-pragchat-v1"
        assert manifest["default_base_url"] == "http://127.0.0.1:8765"
        assert isinstance(manifest["system_prompt"], str)
        assert "PragChat" in manifest["system_prompt"]
        assert "Y=10" in manifest["system_prompt"]
        assert "contiguous 0..N-1" in manifest["system_prompt"]
        assert_no_emojis(manifest["system_prompt"])

        resource_names = [r["name"] for r in manifest["resources"]]
        assert "MapResource" in resource_names
        assert "PadResource" in resource_names
        assert "PlaySession" in resource_names
        assert "StudioWorkspaceSnapshot" in resource_names

    def test_http_get_manifest(self, editor_server):
        """Verify GET /pragchat/manifest endpoint over HTTP."""
        url = f"{editor_server['base_url']}/pragchat/manifest"
        req = urllib.request.Request(url, headers={"Origin": "http://127.0.0.1:8010"})
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            assert resp.headers.get("Content-Type").startswith("application/json")
            assert resp.headers.get("Access-Control-Allow-Origin") == "http://127.0.0.1:8010"
            data = json.loads(resp.read().decode("utf-8"))

            assert data["version"] == "editor-studio-pragchat-v1"
            assert data["default_base_url"] == editor_server["base_url"]
            assert len(data["resources"]) >= 4

            map_res = next(r for r in data["resources"] if r["name"] == "MapResource")
            assert map_res["endpoints"]["list"]["url"] == "/api/maps"
            assert map_res["endpoints"]["create"]["url"] == "/api/chat-generate"

            pad_res = next(r for r in data["resources"] if r["name"] == "PadResource")
            assert "index" in pad_res["schema"]["properties"]

            play_res = next(r for r in data["resources"] if r["name"] == "PlaySession")
            assert play_res["endpoints"]["create"]["url"] == "/api/test-map"

            assert_no_emojis(json.dumps(data))

    def test_http_get_resources_alias(self, editor_server):
        """Verify GET /pragchat/resources acts as an alias to /pragchat/manifest."""
        url = f"{editor_server['base_url']}/pragchat/resources"
        with urllib.request.urlopen(url) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["version"] == "editor-studio-pragchat-v1"
            assert len(data["resources"]) >= 4


class TestPragChatSnapshot:
    """Validate GET /pragchat/snapshot contract."""

    def test_snapshot_unit_function(self):
        """Verify pragchat_snapshot() generator function output structure."""
        snap = pragchat_snapshot()
        assert snap["ok"] is True
        assert snap["studio"] == "Perfect Dark Map Editor"
        assert snap["protocol"] == "editor-studio-pragchat-v1"
        assert len(snap["channels"]) >= 1
        assert snap["channels"][0]["id"] == "studio-general"
        assert snap["state"]["server_online"] is True
        assert snap["state"]["default_slot"] == "uff"
        assert_no_emojis(json.dumps(snap))

    def test_http_get_snapshot(self, editor_server):
        """Verify GET /pragchat/snapshot endpoint over HTTP."""
        url = f"{editor_server['base_url']}/pragchat/snapshot"
        req = urllib.request.Request(url, headers={"Origin": "http://127.0.0.1:8010"})
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            assert resp.headers.get("Content-Type").startswith("application/json")
            assert resp.headers.get("Access-Control-Allow-Origin") == "http://127.0.0.1:8010"
            data = json.loads(resp.read().decode("utf-8"))

            assert data["ok"] is True
            assert data["studio"] == "Perfect Dark Map Editor"
            assert data["protocol"] == "editor-studio-pragchat-v1"
            assert "state" in data
            assert data["state"]["server_online"] is True
            assert data["state"]["active_provider"] == "hybrid_grammar_llm"
            assert_no_emojis(json.dumps(data))


class TestPragChatToolExecution:
    """Validate POST /api/chat-generate as PragChat tool execution backend."""

    def test_conversational_explainer_execution(self, editor_server):
        """Verify PragChat conversational explainer synthesis without level mutation."""
        url = f"{editor_server['base_url']}/api/chat-generate"
        payload = {
            "prompt": "Explain to a regular person how all of this is very useful",
            "current_map": {},
            "history": [],
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["ok"] is True
            assert data["action"] == "explain"
            assert data["map"] is None
            assert isinstance(data["reply"], str)
            assert "Perfect Dark Kit" in data["reply"]
            assert_no_emojis(data["reply"])

    def test_arena_synthesis_and_validation(self, editor_server):
        """Verify PragChat synthesizes a fully compliant arena passing EditorMapSpec."""
        url = f"{editor_server['base_url']}/api/chat-generate"
        payload = {
            "prompt": "Symmetrical 2-room sniper duel with elevated sniper pads",
            "current_map": {},
            "history": [],
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["ok"] is True
            assert data["action"] == "generate"
            assert_no_emojis(data["reply"])

            m = data["map"]
            assert isinstance(m, dict)
            assert len(m["rooms"]) == 2
            assert len(m["portals"]) >= 1
            assert len(m["pads"]) >= 4

            # Verify Y=10 floor offset invariant across all pads
            for p in m["pads"]:
                assert p["y"] == 10.0, f"Pad {p['index']} failed Y=10 invariant: {p['y']}"

            # Verify contiguous pad indices invariant
            indices = [p["index"] for p in m["pads"]]
            assert indices == list(range(len(m["pads"]))), f"Pad indices not contiguous: {indices}"

            # Verify compile to mapdef and run deterministic validation
            spec = EditorMapSpec.from_json(m)
            errors = validate_mapdef(spec.mapdef, tiles_room_count=spec.tiles_room_count())
            assert errors == [], f"Generated arena failed validation: {errors}"

    def test_chat_generate_error_handling(self, editor_server):
        """Verify 400 Bad Request on invalid payloads."""
        url = f"{editor_server['base_url']}/api/chat-generate"

        # Missing prompt
        req = urllib.request.Request(
            url,
            data=json.dumps({}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req)
        assert exc_info.value.code == 400

    def test_viewport_passthrough_and_action_chips(self, editor_server):
        """Verify viewport passthrough and action_chips / focus_target / verification presence."""
        url = f"{editor_server['base_url']}/api/chat-generate"
        payload = {
            "prompt": "Symmetrical 2-room sniper duel",
            "current_map": {},
            "history": [],
            "viewport": {"camera": {"x": 0.0, "y": 100.0, "z": -200.0}, "selected_room": 1},
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["ok"] is True
            assert data["action"] == "generate"
            assert "action_chips" in data
            assert isinstance(data["action_chips"], list)
            assert len(data["action_chips"]) > 0
            for chip in data["action_chips"]:
                assert isinstance(chip, (dict, str))
                label = chip["label"] if isinstance(chip, dict) else chip
                assert_no_emojis(label)
            assert "focus_target" in data
            assert isinstance(data["focus_target"], (list, dict))
            assert "verification" in data
            assert isinstance(data["verification"], dict)
            assert data["verification"]["passed"] is True
            assert "latency_ms" in data
            assert isinstance(data["latency_ms"], (int, float))
            assert data["latency_ms"] >= 0

    def test_viewport_invalid_type_rejected(self, editor_server):
        """Verify invalid viewport type returns 400 Bad Request."""
        url = f"{editor_server['base_url']}/api/chat-generate"
        payload = {
            "prompt": "Symmetrical 2-room sniper duel",
            "viewport": "invalid_string_not_dict",
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req)
        assert exc_info.value.code == 400

    def test_chat_rollback_with_previous_map(self, editor_server):
        """Verify POST /api/chat-rollback restores explicitly provided previous_map."""
        url = f"{editor_server['base_url']}/api/chat-rollback"
        prev_map = {
            "name": "rollback_target_arena",
            "level_module": "uff",
            "box_half": 5000,
            "box_height": 3000,
            "spawn_y": 10,
            "rooms": [
                {"room": 1, "name": "r1", "x0": -1000.0, "x1": 1000.0, "z0": -1000.0, "z1": 1000.0, "height": 1000.0, "floor_y": 0.0}
            ],
            "portals": [],
            "pads": [
                {"index": 0, "x": -500.0, "y": 10.0, "z": 0.0, "room": 1, "type": "spawn"},
                {"index": 1, "x": 500.0, "y": 10.0, "z": 0.0, "room": 1, "type": "spawn"},
                {"index": 2, "x": 0.0, "y": 10.0, "z": -500.0, "room": 1, "type": "spawn"},
                {"index": 3, "x": 0.0, "y": 10.0, "z": 500.0, "room": 1, "type": "spawn"},
            ],
        }
        payload = {
            "map_id": "rollback_target_arena",
            "previous_map": prev_map,
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["ok"] is True
            assert data["action"] == "rollback"
            assert data["reply"] == "Rolled back conversational mutation."
            assert data["map"]["name"] == "rollback_target_arena"
            assert len(data["map"]["pads"]) == 4
            assert "action_chips" in data
            assert isinstance(data["action_chips"], list)
            assert len(data["action_chips"]) > 0
            assert "focus_target" in data
            assert "verification" in data
            assert data["verification"]["passed"] is True
            assert "latency_ms" in data
            assert_no_emojis(data["reply"])

    def test_chat_rollback_from_draft_history(self, editor_server):
        """Verify POST /api/chat-rollback restores prior draft when called without previous_map."""
        gen_url = f"{editor_server['base_url']}/api/chat-generate"
        initial_map = {
            "name": "draft_saved_arena",
            "level_module": "uff",
            "box_half": 5000,
            "box_height": 3000,
            "spawn_y": 10,
            "rooms": [
                {"room": 1, "name": "r1", "x0": -1000.0, "x1": 1000.0, "z0": -1000.0, "z1": 1000.0, "height": 1000.0, "floor_y": 0.0}
            ],
            "portals": [],
            "pads": [
                {"index": 0, "x": -500.0, "y": 10.0, "z": 0.0, "room": 1, "type": "spawn"},
                {"index": 1, "x": 500.0, "y": 10.0, "z": 0.0, "room": 1, "type": "spawn"},
                {"index": 2, "x": 0.0, "y": 10.0, "z": -500.0, "room": 1, "type": "spawn"},
                {"index": 3, "x": 0.0, "y": 10.0, "z": 500.0, "room": 1, "type": "spawn"},
            ],
        }
        gen_payload = {
            "prompt": "add shotgun pad",
            "current_map": initial_map,
            "history": [],
        }
        gen_req = urllib.request.Request(
            gen_url,
            data=json.dumps(gen_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(gen_req) as resp:
            assert resp.status == 200
            gen_data = json.loads(resp.read().decode("utf-8"))
            assert gen_data["ok"] is True
            assert len(gen_data["map"]["pads"]) == 5

        rb_url = f"{editor_server['base_url']}/api/chat-rollback"
        rb_req = urllib.request.Request(
            rb_url,
            data=json.dumps({}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(rb_req) as resp:
            assert resp.status == 200
            rb_data = json.loads(resp.read().decode("utf-8"))
            assert rb_data["ok"] is True
            assert rb_data["action"] == "rollback"
            assert rb_data["reply"] == "Rolled back conversational mutation."
            assert rb_data["map"]["name"] == "draft_saved_arena"
            assert len(rb_data["map"]["pads"]) == 4

    def test_audit_log_generation_and_secret_scrubbing(self, editor_server):
        """Verify append-only JSONL audit log records invocations and strictly scrubs secrets."""
        url = f"{editor_server['base_url']}/api/chat-generate"
        secret_token = "sk-testsecret9876543210abcdef"
        payload = {
            "prompt": f"Bearer {secret_token} 2-room sniper duel",
            "current_map": {},
            "history": [],
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200

        from journal.uff_viewer.serve_editor import AUDIT_LOG_FILE, ROOT
        audit_paths = [AUDIT_LOG_FILE, os.path.join(ROOT, ".chat_audit.jsonl")]
        found = False
        for p in audit_paths:
            if os.path.isfile(p):
                with open(p, "r", encoding="utf-8") as fp:
                    lines = fp.readlines()
                assert len(lines) > 0
                last_record = json.loads(lines[-1].strip())
                assert "timestamp" in last_record
                assert "prompt_hash" in last_record
                assert len(last_record["prompt_hash"]) == 16
                assert "action" in last_record
                assert "latency_ms" in last_record
                assert isinstance(last_record["latency_ms"], (int, float))
                assert "verification_passed" in last_record
                assert isinstance(last_record["verification_passed"], bool)

                all_content = "".join(lines)
                assert secret_token not in all_content, "Plaintext secret leaked into audit log!"
                found = True
                break
        assert found, f"Audit log not found in any of: {audit_paths}"

    def test_recipe_template_persistence(self, editor_server):
        """Verify generating a map persists a recipe template in journal/map_learn/templates/<slug>.json."""
        url = f"{editor_server['base_url']}/api/chat-generate"
        payload = {
            "prompt": "2-room sniper duel",
            "current_map": {},
            "history": [],
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["ok"] is True
            assert data["action"] == "generate"

        from journal.uff_viewer.serve_editor import ROOT
        template_file = os.path.join(ROOT, "journal", "map_learn", "templates", "sniper_duel.json")
        assert os.path.isfile(template_file), f"Expected template file {template_file} does not exist"
        with open(template_file, "r", encoding="utf-8") as fp:
            recipe = json.load(fp)
        assert recipe["slug"] == "sniper_duel"
        assert recipe["prompt"] == "2-room sniper duel"
        assert recipe["pads_count"] >= 4
        assert recipe["rooms_count"] == 2
        assert "template" in recipe
        assert isinstance(recipe["template"], dict)
        assert recipe["template"]["name"] == "sniper_duel"
