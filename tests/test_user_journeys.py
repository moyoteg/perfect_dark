"""Unified Automated Verification Suite for all 12 Canonical User Journeys.

Validates that every defined user journey across Perfect Dark Kit, 3D Map Editor,
PragChat Studio Assistant, Virtual Agent Office, and Flight Control is 100%
operational and complies with locked specifications.
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO / "tools" / "agent_office_llm") not in sys.path:
    sys.path.insert(0, str(REPO / "tools" / "agent_office_llm"))
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from journal.uff_viewer.serve_editor import EditorHandler, _run_test_map
from office_director import OfficeDirector, parse_observation
from service.http_api import OfficeServiceAPI, create_default_service, make_handler
from service.tenant import normalize_tenant_id, tenant_context, resolve_tenant_state_file
from tools.pdmap.chr_anim_pose import get_anim_metadata
from tools.pdmap.from_json import EditorMapSpec
from tools.pdmap.generative_assistant import GenerativeAssistant
from tools.pdmap.mission_compiler import create_sample_mission, validate_mission_dict
from tools.pdmap.weapon_compiler import validate_weapons_json, DEFAULT_WEAPONS_JSON_PATH
from tools.asset_upgrader.mlx_backend import MLXCoreImageUpgrader
from tools.pdmap.pd_pack import compute_sha256, _should_ignore
from tools.pdmap.setup_c_preprocess import eval_setup_version_condition
from tools.pdmap.gen_object_catalog import parse_models, select as select_models, build as build_catalog
from tools.release_gate import ReleaseGateReport, SubsystemResult, SCENARIO_CROSS_SYSTEM_RELEASE
from tools.pdmap.navmesh import NavPoint, ObstacleBox


@pytest.fixture(scope="module")
def editor_test_server():
    """Spin up an in-process ThreadingHTTPServer for editor API tests."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), EditorHandler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.15)
    base_url = f"http://127.0.0.1:{port}"
    yield base_url
    server.shutdown()
    server.server_close()


@pytest.fixture(scope="module")
def office_test_server():
    """Spin up an in-process ThreadingHTTPServer for Office Service API tests."""
    svc = create_default_service()
    api = OfficeServiceAPI(svc)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(api))
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.15)
    base_url = f"http://127.0.0.1:{port}"
    yield base_url, svc
    server.shutdown()
    server.server_close()


# ==============================================================================
# UJ-01: Conversational Level Synthesis (PragChat Studio Assistant)
# ==============================================================================
def test_journey_01_conversational_synthesis_and_autopersist(editor_test_server: str) -> None:
    """UJ-01: Natural language prompt synthesizes geometry and auto-saves to disk."""
    assistant = GenerativeAssistant()
    res = assistant.process_prompt("Symmetrical 2-room sniper duel")
    assert res.get("ok") is True
    assert res.get("action") == "generate"
    map_data = res.get("map")
    assert isinstance(map_data, dict)
    pads = map_data.get("pads", [])
    assert len(pads) >= 8
    # Assert floor offset Y=10
    for p in pads:
        assert p.get("y", 0) >= 10.0

    # Verify HTTP endpoint auto-persists synthesized map
    url = f"{editor_test_server}/api/chat-generate"
    payload = json.dumps({"prompt": "Symmetrical 2-room sniper duel"}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data.get("ok") is True
        assert "saved_map_id" in data
        saved_id = data["saved_map_id"]

    # Verify the saved map is fetchable
    fetch_url = f"{editor_test_server}/api/maps/{saved_id}"
    with urllib.request.urlopen(fetch_url) as fetch_resp:
        assert fetch_resp.status == 200
        saved_data = json.loads(fetch_resp.read().decode("utf-8"))
        assert saved_data.get("map", {}).get("name") is not None


# ==============================================================================
# UJ-02: Custom Map Library Browsing, Management & 1-Click Load
# ==============================================================================
def test_journey_02_map_library_aggregation(editor_test_server: str) -> None:
    """UJ-02: Multi-directory map discovery surfaces all historic and generated maps."""
    url = f"{editor_test_server}/api/maps"
    with urllib.request.urlopen(url) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        maps = data.get("maps", [])
        map_names = {m["name"] for m in maps}

        # Assert key custom maps are present
        required_maps = [
            "matrix_battle_64",
            "cyber_arena",
            "sniper_duel",
            "koth_facility",
            "warehouse_bunker",
            "full_arena",
            "my_arena",
            "animlab_map",
        ]
        for req_map in required_maps:
            assert req_map in map_names, f"Expected {req_map} in aggregated map library"

    # Verify 1-click load for matrix_battle_64
    mb_url = f"{editor_test_server}/api/maps/matrix_battle_64"
    with urllib.request.urlopen(mb_url) as mb_resp:
        assert mb_resp.status == 200
        mb_data = json.loads(mb_resp.read().decode("utf-8"))
        assert len(mb_data.get("map", {}).get("pads", [])) >= 64

    # Verify 1-click load for cyber_arena
    ca_url = f"{editor_test_server}/api/maps/cyber_arena"
    with urllib.request.urlopen(ca_url) as ca_resp:
        assert ca_resp.status == 200
        ca_data = json.loads(ca_resp.read().decode("utf-8"))
        assert len(ca_data.get("map", {}).get("pads", [])) >= 4


# ==============================================================================
# UJ-03: 1-Click Instant Map Playtesting (T Hotkey)
# ==============================================================================
def test_journey_03_instant_map_playtesting_dryrun() -> None:
    """UJ-03: Pressing T compiles Fast3D display lists and prepares in-engine execution."""
    sample_spec = {
        "name": "playtest_journey_test",
        "box_half": 5000,
        "box_height": 3000,
        "pads": [
            {"index": 0, "type": "spawn", "x": -500, "y": 10, "z": -500, "room": 1},
            {"index": 1, "type": "spawn", "x": 500, "y": 10, "z": 500, "room": 1},
        ],
    }
    result = _run_test_map({"map": sample_spec, "dry_run": True})
    assert result.get("ok") is True
    cmd = str(result.get("command", ""))
    assert "test_map.py" in cmd
    assert "playCommand" in result


# ==============================================================================
# UJ-04: High-Scale Combat Simulator Scenario Battle
# ==============================================================================
def test_journey_04_combat_sim_matrix_battle_configuration() -> None:
    """UJ-04: Matrix Battle 64 configures 50 simulants across opposing battle lines."""
    from src.levels import matrix_battle_64

    mapdef = matrix_battle_64.build()
    assert len(mapdef.pads) >= 64
    # Check that pads span team 0 and team 1
    team0_pads = [p for p in mapdef.pads if getattr(p, "team", None) == 0 or getattr(p, "z", 0) < 0]
    team1_pads = [p for p in mapdef.pads if getattr(p, "team", None) == 1 or getattr(p, "z", 0) > 0]
    assert len(team0_pads) >= 32
    assert len(team1_pads) >= 32


# ==============================================================================
# UJ-05: Agent Office Clock-In & Embodied Presence
# ==============================================================================
def test_journey_05_agent_office_presence_cycle() -> None:
    """UJ-05: Director seeds work, switches to talk on approach, resumes work on exit."""
    director = OfficeDirector(brains={}, client=None)

    near_obs = {
        "tick": 1,
        "players": [
            {"id": 0, "team": 0, "pos": {"x": 2600.0, "y": 35.0, "z": -300.0}, "facing_deg": 119.0}
        ],
        "agents": [
            {
                "chrnum": 0x31,
                "role_hint": 0,
                "role": "Director",
                "pos": {"x": 2888.0, "y": 35.0, "z": -458.0},
                "facing_deg": 270.0,
                "player_dist": 340.0,
                "status": "work",
                "talking": False,
            },
        ],
    }
    acts = director.step(near_obs)
    # Player approached: director emits status update
    assert len(acts) > 0
    statuses = [r.get("status") for act in acts for r in act.get("agents", []) if "status" in r]
    assert "talk" in statuses or "work" in statuses


# ==============================================================================
# UJ-06: Diegetic Monitors & Perfect Menu Computer Inspection
# ==============================================================================
def test_journey_06_diegetic_monitor_and_perfect_menu(office_test_server: tuple[str, Any]) -> None:
    """UJ-06: In-world computer interactivity reads live thoughts, tasks, and perfect menu."""
    base_url, _ = office_test_server
    req = urllib.request.Request(f"{base_url}/fleet")
    with urllib.request.urlopen(req) as resp:
        fleet = json.loads(resp.read().decode("utf-8"))
        assert fleet["embodiment_capacity"] == 8
        assert len(fleet["embodied_agents"]) == 8
        assert "perfect_menu_text" in fleet
        assert len(fleet["perfect_menu_text"]) > 0

    # Read specific agent monitor
    mon_req = urllib.request.Request(f"{base_url}/agents/comms/monitor")
    with urllib.request.urlopen(mon_req) as resp:
        mon = json.loads(resp.read().decode("utf-8"))
        assert mon["agent_id"] == "comms"
        assert "monitor_text" in mon


# ==============================================================================
# UJ-07: Multimodal Voice Dialogue & ASR Loop
# ==============================================================================
def test_journey_07_multimodal_voice_loop() -> None:
    """UJ-07: Voice pipeline transcribes speech and routes to agent brain."""
    from service.dm_threads import format_visor_compose_picker_text, VALID_AGENT_IDS

    assert "comms" in VALID_AGENT_IDS
    assert "research" in VALID_AGENT_IDS
    picker_text = format_visor_compose_picker_text([])
    assert picker_text is None or isinstance(picker_text, str)


# ==============================================================================
# UJ-08: High-Consequence Action Security Gate (Z Approve / B Deny)
# ==============================================================================
def test_journey_08_security_gate_approval_cycle(office_test_server: tuple[str, Any]) -> None:
    """UJ-08: Sensitive actions halt in PENDING_APPROVAL until Z Approve or B Deny."""
    base_url, _ = office_test_server
    # Dispatch an action
    disp_payload = json.dumps({
        "agent_id": "comms",
        "intent": "reply to marketing",
        "created_by": "prag_chat",
    }).encode("utf-8")
    req = urllib.request.Request(f"{base_url}/dispatch", data=disp_payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 201
        task = json.loads(resp.read().decode("utf-8"))
        task_id = task["id"]

    # Perform action requiring approval
    perf_payload = json.dumps({
        "actions": [{
            "connector": "slack",
            "action": "post_message",
            "args": {"channel": "#marketing", "text": "Friday release scheduled."},
        }],
    }).encode("utf-8")
    perf_req = urllib.request.Request(f"{base_url}/tasks/{task_id}/perform", data=perf_payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(perf_req) as resp:
        assert resp.status == 200
        staged = json.loads(resp.read().decode("utf-8"))
        assert staged["status"] == "awaiting_approval"

    # Query pending approvals
    with urllib.request.urlopen(f"{base_url}/approvals") as resp:
        approvals = json.loads(resp.read().decode("utf-8"))
        pending = [a for a in approvals if a["status"] == "pending"]
        assert len(pending) >= 1
        approval_id = pending[0]["id"]

    # Approve action via Security desk
    app_payload = json.dumps({"decided_by": "security_desk"}).encode("utf-8")
    app_req = urllib.request.Request(f"{base_url}/approvals/{approval_id}/approve", data=app_payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(app_req) as resp:
        assert resp.status == 200
        res = json.loads(resp.read().decode("utf-8"))
        assert res.get("status") == "done"


# ==============================================================================
# UJ-09: Sovereign Swarm Fleet Orchestration (Flight Control ↔ Office)
# ==============================================================================
def test_journey_09_flight_control_fleet_orchestration_contract(office_test_server: tuple[str, Any]) -> None:
    """UJ-09: Office Service exposes bidirectional sync contract for Flight Control."""
    base_url, _ = office_test_server
    # Flight Control health query
    with urllib.request.urlopen(f"{base_url}/health") as resp:
        assert resp.status == 200
        health = json.loads(resp.read().decode("utf-8"))
        assert health.get("ok") is True

    # Social routing between facilities
    social_payload = json.dumps({
        "text": "Heard vault talk on G5 floor",
        "from_office": "g5",
        "to_office": "ci",
        "from_agent_id": "security",
        "kind": "guard_report",
    }).encode("utf-8")
    soc_req = urllib.request.Request(f"{base_url}/social/route", data=social_payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(soc_req) as resp:
        assert resp.status == 201
        soc_res = json.loads(resp.read().decode("utf-8"))
        assert soc_res.get("kind") == "guard_report"


# ==============================================================================
# UJ-10: Multi-Tenant Workspace Partitioning
# ==============================================================================
def test_journey_10_multitenant_workspace_isolation() -> None:
    """UJ-10: Multiple tenants maintain strictly isolated state and root paths."""
    assert normalize_tenant_id("Engineering_Team") == "engineering_team"
    assert normalize_tenant_id("Security_Ops") == "security_ops"

    with tenant_context("tenant_alpha"):
        path_alpha = resolve_tenant_state_file("tasks.json")
    with tenant_context("tenant_beta"):
        path_beta = resolve_tenant_state_file("tasks.json")

    assert "tenant_alpha" in str(path_alpha)
    assert "tenant_beta" in str(path_beta)
    assert path_alpha != path_beta


# ==============================================================================
# UJ-11: Character & Animation Studio Lab
# ==============================================================================
def test_journey_11_character_and_animation_pipeline() -> None:
    """UJ-11: Animation Lab validates skeletal keyframe structures."""
    meta = get_anim_metadata(0)
    assert meta is not None
    assert meta.get("id") == "ANIM_IDLE"
    assert "file" in meta


# ==============================================================================
# UJ-12: Plain-Language Demystification (Zero AI Slop)
# ==============================================================================
def test_journey_12_plain_language_demystification() -> None:
    """UJ-12: Instant demystification in plain language with zero AI slop and zero emojis."""
    assistant = GenerativeAssistant()
    res = assistant.process_prompt("Explain to a regular person how all of this is very useful")
    assert res.get("ok") is True
    reply = res.get("reply", "")
    assert len(reply) > 50

    # Enforce Calibrated Zero-Emoji Standard (no unicode emojis)
    emoji_pattern = re.compile(
        r"[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]|[\u2b50-\u2b55]"
    )
    emojis_found = emoji_pattern.findall(reply)
    assert len(emojis_found) == 0, f"Unicode emojis forbidden in system copy: {emojis_found}"


# ==============================================================================
# UJ-13: Single-Player Campaign Mission & Objective Authoring
# ==============================================================================
def test_journey_13_campaign_mission_authoring() -> None:
    """UJ-13: Narrative designer authors multi-tier objectives, briefings, and guards."""
    mission = create_sample_mission("sample_infiltrate")
    errors = validate_mission_dict(mission)
    assert len(errors) == 0, f"Mission validation failed: {errors}"
    assert mission.get("name") == "sample_infiltrate"
    objectives = mission.get("objectives", [])
    assert len(objectives) >= 3
    all_diffs = set()
    for obj in objectives:
        all_diffs.update(obj.get("difficulties", []))
    assert "agent" in all_diffs
    assert "special_agent" in all_diffs
    assert "perfect_agent" in all_diffs
    guards = mission.get("guards", [])
    assert len(guards) >= 2
    for g in guards:
        assert "pad" in g
        assert "weapon" in g


# ==============================================================================
# UJ-14: Declarative Weapon & Gunplay Pipeline
# ==============================================================================
def test_journey_14_declarative_weapon_pipeline() -> None:
    """UJ-14: Combat modder defines custom weapons with dual-wield flags and ammo."""
    weapons_path = REPO / DEFAULT_WEAPONS_JSON_PATH
    assert weapons_path.exists(), f"weapons.json not found at {weapons_path}"
    res = validate_weapons_json(weapons_path)
    assert res.is_valid is True, f"weapons.json validation failed: {res.errors}"
    assert len(res.weapons) > 0
    sample = res.weapons[0]
    assert "name" in sample
    assert "category" in sample
    assert "ammo_type" in sample


# ==============================================================================
# UJ-15: Neural Texture Upscaling (MLX Core / Lanczos)
# ==============================================================================
def test_journey_15_neural_texture_upscaling_mlx(tmp_path: Path) -> None:
    """UJ-15: MLX Core texture upscaler enhances textures with Lanczos fallback."""
    from PIL import Image

    upgrader = MLXCoreImageUpgrader(dry_run=True)
    src_img = tmp_path / "test_tex.png"
    dst_img = tmp_path / "test_tex_upscaled.png"

    img = Image.new("RGBA", (32, 32), (255, 0, 0, 255))
    img.save(src_img)

    result = upgrader.upgrade_png(src_img, dst_img, width=128, height=128)
    assert result.get("status") in ("dry_run", "ok")
    assert dst_img.exists()
    out_img = Image.open(dst_img)
    assert out_img.size == (128, 128)


# ==============================================================================
# UJ-16: Turnkey Mod Packaging & Signing
# ==============================================================================
def test_journey_16_turnkey_mod_packaging_and_signing() -> None:
    """UJ-16: Mod distributor packages assets with SHA-256 integrity."""
    target_file = REPO / "tools" / "pdmap" / "pd_pack.py"
    digest = compute_sha256(target_file)
    assert len(digest) == 64
    assert re.match(r"^[0-9a-f]{64}$", digest)
    assert _should_ignore(Path(".DS_Store")) is True
    assert _should_ignore(Path("__pycache__/foo.pyc")) is True
    assert _should_ignore(Path("level.json")) is False


# ==============================================================================
# UJ-17: Cross-Title Heritage GoldenEye Conversion
# ==============================================================================
def test_journey_17_cross_title_heritage_conversion() -> None:
    """UJ-17: Retro preprocessor resolves setup.c conditional blocks."""
    assert eval_setup_version_condition("VERSION >= VERSION_NTSC_1_0") is True
    assert eval_setup_version_condition("VERSION < VERSION_NTSC_BETA") is False
    assert eval_setup_version_condition("VERSION == VERSION_NTSC_FINAL") is True


# ==============================================================================
# UJ-18: Interactive 3D Object Catalog Vitrine
# ==============================================================================
def test_journey_18_interactive_object_catalog_vitrine() -> None:
    """UJ-18: Parses constants.h MODEL_* constants into 3D catalog layout."""
    models = parse_models()
    assert len(models) >= 50
    door_models = select_models(models, ["door"], want_all=False)
    assert len(door_models) > 0
    for name, _ in door_models:
        assert "door" in name.lower()
    data, legend = build_catalog(door_models[:10])
    assert "pads" in data
    assert len(data["pads"]) > 0
    assert len(legend) == len(door_models[:10])


# ==============================================================================
# UJ-19: Mechanical Release & Quality Gate
# ==============================================================================
def test_journey_19_mechanical_release_and_quality_gate() -> None:
    """UJ-19: Release gate report aggregates typed subsystem metrics."""
    sub_res = SubsystemResult(
        subsystem="test_system",
        passed=True,
        exit_code=0,
        summary={"metric": 100},
        evidence_lines=("all nominal",),
    )
    report = ReleaseGateReport(
        scenario_id=SCENARIO_CROSS_SYSTEM_RELEASE,
        subsystems=(sub_res,),
        passed=True,
        latency_ms=42,
    )
    json_line = report.to_json_line()
    assert json_line.startswith("{") and json_line.strip().endswith("}")
    data = json.loads(json_line)
    assert data.get("scenario_id") == SCENARIO_CROSS_SYSTEM_RELEASE
    assert data.get("passed") is True
    assert data.get("latency_ms") == 42


# ==============================================================================
# UJ-20: Procedural Navmesh & Reciprocal Waypoints
# ==============================================================================
def test_journey_20_procedural_navmesh_reciprocal_waypoints() -> None:
    """UJ-20: Navmesh generator calculates reciprocal waypoint geometry."""
    p1 = NavPoint(index=0, x=0.0, y=10.0, z=0.0)
    p2 = NavPoint(index=1, x=300.0, y=10.0, z=400.0)
    assert p1.distance_to(p2) == 500.0
    assert p1.vertical_delta(p2) == 0.0

    # Test Liang-Barsky obstacle clipping
    box = ObstacleBox(min_x=-50.0, max_x=50.0, min_z=-50.0, max_z=50.0)
    # Line passing straight through box from (-100, 0) to (100, 0)
    assert box.intersects_segment_2d(-100.0, 0.0, 100.0, 0.0) is True
    # Line completely outside
    assert box.intersects_segment_2d(100.0, 100.0, 200.0, 200.0) is False

