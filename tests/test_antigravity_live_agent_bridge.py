"""Tests for Antigravity Active Live Agent Attachment in Virtual Agent Office.

Runnable two ways:
    python3 tests/test_antigravity_live_agent_bridge.py
    python3 -m pytest tests/test_antigravity_live_agent_bridge.py
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "agent_office_llm"))


def _seed_synthetic_antigravity_store(root: Path) -> tuple[Path, Path]:
    db_path = root / "conversation_summaries.db"
    brain_dir = root / "brain"
    brain_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE conversation_summaries ("
        "conversation_id TEXT PRIMARY KEY, "
        "title TEXT, "
        "preview TEXT, "
        "step_count INTEGER, "
        "last_modified_time TEXT, "
        "workspace_uris TEXT, "
        "status TEXT, "
        "source TEXT, "
        "project_id TEXT, "
        "agent_name TEXT, "
        "parent_conversation_id TEXT, "
        "nesting_depth INTEGER, "
        "not_fully_idle INTEGER, "
        "killed INTEGER"
        ")"
    )

    sessions = [
        ("11111111-aaaa-4444-8888-000000000001", "Perfect Dark Kit Status", 740, "CASCADE_RUN_STATUS_RUNNING", 1, "", 0, "Compiling C port"),
        ("22222222-bbbb-4444-8888-000000000002", "LLM Play Status Check", 680, "CASCADE_RUN_STATUS_RUNNING", 1, "", 0, "Verifying VAO bridge"),
        ("33333333-cccc-4444-8888-000000000003", "SnapRack System Status", 18040, "CASCADE_RUN_STATUS_RUNNING", 1, "", 0, "Auditing telemetry"),
        ("44444444-dddd-4444-8888-000000000004", "Perfect EE2 Remake Goal", 34730, "CASCADE_RUN_STATUS_RUNNING", 1, "", 0, "Dispatching swarm"),
        ("55555555-eeee-4444-8888-000000000005", "Machine Code 3D Engine", 5880, "CASCADE_RUN_STATUS_RUNNING", 1, "", 0, "Running shader pass"),
        ("66666666-ffff-4444-8888-000000000006", "Training My Digital Replica", 5160, "CASCADE_RUN_STATUS_RUNNING", 1, "", 0, "Evaluating LoRA adapter"),
        ("77777777-1111-4444-8888-000000000007", "FixBidAI Service Status", 16465, "CASCADE_RUN_STATUS_IDLE", 0, "", 0, "Inspecting escrow ledger"),
        ("88888888-2222-4444-8888-000000000008", "AI Receptionist Assessment", 254, "CASCADE_RUN_STATUS_IDLE", 0, "", 0, "Running readiness check"),
        # Active subagents under session 4
        ("subagent-0001-4444-8888-000000000009", "", 42, "CASCADE_RUN_STATUS_RUNNING", 1, "44444444-dddd-4444-8888-000000000004", 1, "Subagent worker 1"),
        ("subagent-0002-4444-8888-000000000010", "", 19, "CASCADE_RUN_STATUS_RUNNING", 1, "44444444-dddd-4444-8888-000000000004", 1, "Subagent worker 2"),
    ]

    for idx, (cid, title, steps, status, active, parent_id, depth, tool_action) in enumerate(sessions):
        conn.execute(
            "INSERT INTO conversation_summaries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
            (
                cid,
                title,
                title,
                steps,
                f"2026-10-14T03:{50 - idx:02d}:00Z",
                "file:///Volumes/4TEx%20Dev%20main/Work",
                status,
                "agent",
                "proj-1",
                "self" if depth > 0 else "",
                parent_id,
                depth,
                active,
            ),
        )
        log_dir = brain_dir / cid / ".system_generated" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        transcript_line = {
            "step_index": steps + 5,
            "type": "PLANNER_RESPONSE",
            "status": "DONE",
            "tool_calls": [
                {
                    "name": "run_command",
                    "arguments": {
                        "toolAction": tool_action,
                        "toolSummary": tool_action,
                    },
                }
            ],
        }
        (log_dir / "transcript.jsonl").write_text(
            json.dumps(transcript_line) + "\n",
            encoding="utf-8",
        )

    conn.commit()
    conn.close()
    return db_path, brain_dir


def test_discover_and_attach_antigravity_live_agents_unit() -> None:
    """Vector 1: synthetic SQLite + transcript.jsonl attaches 8 live agents to VAO desks."""
    from service.antigravity_bridge import discover_antigravity_live_agents
    from service.http_api import create_default_service, pragchat_snapshot
    import office_director as od

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        db_path, brain_dir = _seed_synthetic_antigravity_store(root)

        disc = discover_antigravity_live_agents(
            limit=8,
            summaries_db_path=db_path,
            brain_dir=brain_dir,
            ls_info={"pid": 64443, "port": 57151, "connected": True},
        )
        assert disc["ok"] is True
        assert disc["connected"] is True
        assert disc["total_discovered"] == 8
        assert disc["active_count"] == 6
        assert disc["subagent_count"] == 2

        first = disc["agents"][0]
        assert first["cascade_id"] == "11111111-aaaa-4444-8888-000000000001"
        assert first["title"] == "Perfect Dark Kit Status"
        assert first["step_count"] == 745  # 740 + 5 from transcript.jsonl
        assert first["last_tool_action"] == "Compiling C port"
        assert "[AGY 11111111 RUN]" in first["billboard"]

        ee2 = next(a for a in disc["agents"] if a["short_id"] == "44444444")
        assert ee2["active_subagent_count"] == 2
        assert "+2sub" in ee2["billboard"]

        svc = create_default_service(reload_persisted=False)
        sync_res = svc.sync_antigravity_live_agents(
            limit=8,
            push_to_engine=False,
            summaries_db_path=str(db_path),
            brain_dir=str(brain_dir),
            ls_info={"pid": 64443, "port": 57151, "connected": True},
        )
        assert sync_res["attached_count"] == 8
        assert len(svc.attached_live_agents) == 8

        mon = svc.agent_monitor("director")
        assert mon["antigravity_live_agent"]["title"] == "Perfect Dark Kit Status"
        assert "antigravity_live:" in mon["monitor_text"]
        assert "Compiling C port" in mon["monitor_text"]

        fleet = svc.fleet_status()
        assert fleet["antigravity_connected"] is True
        assert fleet["antigravity_attached_count"] == 8
        assert fleet["antigravity_active_count"] == 6
        assert len(fleet["antigravity_live_agents"]) == 8
        assert "Perfect Dark Kit Status" in fleet["perfect_menu_text"]
        assert "LLM Play Status Check" in fleet["perfect_menu_text"]

        snap = pragchat_snapshot(svc)
        assert len(snap["antigravity_live_agents"]) == 8
        assert snap["agent_dms"][0]["antigravity_live_agent"]["short_id"] == "11111111"

        director = od.OfficeDirector(
            {"Director": od.AgentBrain({"slug": "director", "role": "Director"}, persist_memory=False)},
            client=None,
            service=svc,
        )
        billboard = director._agent_billboard("Director")
        assert billboard is not None
        assert "Perfect Dark Kit Status" in billboard


def test_http_api_antigravity_routes_and_3d_engine_push() -> None:
    """Vector 2: /antigravity/live-agents and /antigravity/sync push billboards to 3D /api/llm/act."""
    from service.http_api import OfficeServiceAPI, create_default_service

    captured_acts: list[dict] = []

    class _MockEngineHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length") or "0")
            raw = self.rfile.read(length)
            captured_acts.append(json.loads(raw.decode("utf-8")))
            resp = b'{"ok":true,"applied_tick":1}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)

        def log_message(self, *_args: object) -> None:
            return

    engine_server = ThreadingHTTPServer(("127.0.0.1", 0), _MockEngineHandler)
    engine_thread = threading.Thread(target=engine_server.serve_forever, daemon=True)
    engine_thread.start()
    engine_url = f"http://127.0.0.1:{engine_server.server_address[1]}"

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        db_path, brain_dir = _seed_synthetic_antigravity_store(root)
        os.environ["ANTIGRAVITY_SUMMARIES_DB"] = str(db_path)
        os.environ["ANTIGRAVITY_BRAIN_DIR"] = str(brain_dir)
        os.environ["ANTIGRAVITY_DISABLE_LS_PROBE"] = "1"
        try:
            api = OfficeServiceAPI(create_default_service(reload_persisted=False))
            status_get, live_body = api.get("/antigravity/live-agents")
            assert status_get == 200
            assert live_body["ok"] is True
            assert live_body["attached_count"] == 8

            status_post, sync_body = api.post(
                "/antigravity/sync",
                {"push_to_engine": True, "engine_url": engine_url},
            )
            assert status_post == 200
            assert sync_body["ok"] is True
            assert sync_body["engine_push"]["pushed_count"] == 8
            assert len(captured_acts) == 8
            first_act = captured_acts[0]["agents"][0]
            assert first_act["chrnum"] == 0x31
            assert first_act["status"] == "work"
            assert "Perfect Dark Kit Status" in first_act["billboard"]
        finally:
            os.environ.pop("ANTIGRAVITY_SUMMARIES_DB", None)
            os.environ.pop("ANTIGRAVITY_BRAIN_DIR", None)
            os.environ.pop("ANTIGRAVITY_DISABLE_LS_PROBE", None)
            engine_server.shutdown()
            engine_thread.join(timeout=2)
            engine_server.server_close()


def test_real_host_antigravity_live_agent_discovery() -> None:
    """Vector 3: verify live discovery against the host ~/.gemini/antigravity store when present."""
    from service.antigravity_bridge import discover_antigravity_live_agents

    host_db = Path(os.path.expanduser("~/.gemini/antigravity/conversation_summaries.db"))
    if not host_db.is_file():
        return
    disc = discover_antigravity_live_agents(limit=8)
    assert disc["ok"] is True
    assert disc["connected"] is True
    assert disc["total_discovered"] >= 1
    for agent in disc["agents"]:
        assert agent["cascade_id"]
        assert agent["title"]
        assert agent["billboard"].startswith("[AGY ")


if __name__ == "__main__":
    test_discover_and_attach_antigravity_live_agents_unit()
    print("PASS test_discover_and_attach_antigravity_live_agents_unit")
    test_http_api_antigravity_routes_and_3d_engine_push()
    print("PASS test_http_api_antigravity_routes_and_3d_engine_push")
    test_real_host_antigravity_live_agent_discovery()
    print("PASS test_real_host_antigravity_live_agent_discovery")
    print("\nOK")
