"""Tests for the Office Service control plane (tools/agent_office_llm/service).

Runnable two ways:
    python3 tests/test_office_service.py
    python3 -m pytest tests/test_office_service.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "agent_office_llm"))

from service import (  # noqa: E402
    Agent, Autonomy, TaskStatus, ApprovalStatus,
    ConnectorGateway, OfficeService, PolicyError,
)
from service.connectors import slack_stub, slack_connector, pagerduty_stub, github_stub  # noqa: E402


def _office():
    gw = ConnectorGateway()
    sent: list[dict] = []
    gw.register(slack_stub(sent))
    gw.register(pagerduty_stub())
    gw.register(github_stub())
    svc = OfficeService(gw)
    svc.add_agent(Agent(id="comms", role="Comms", chrnum=0x38, tools=["slack"],
                        autonomy={"slack": Autonomy.ASK_APPROVAL}))
    svc.add_agent(Agent(id="ops", role="Ops", chrnum=0x36, tools=["pagerduty"],
                        autonomy={"pagerduty": Autonomy.ASK_APPROVAL}))
    svc.add_agent(Agent(id="research", role="Research", chrnum=0x33, tools=["slack"],
                        autonomy={"slack": Autonomy.ACT}))
    return svc, gw, sent


def test_read_action_needs_no_approval():
    svc, gw, _ = _office()
    t = svc.dispatch("ops", "check prod")
    svc.perform(t, [{"connector": "pagerduty", "action": "read_incidents", "args": {}}])
    assert t.status == TaskStatus.DONE
    assert "INC-42" in (t.artifacts[-1] if t.artifacts else "")
    assert not svc.pending_approvals()


def test_write_under_ask_approval_stages_then_executes():
    svc, gw, sent = _office()
    t = svc.dispatch("comms", "reply to marketing")
    svc.perform(t, [{"connector": "slack", "action": "post_message",
                     "args": {"channel": "#marketing", "text": "Friday."}}])
    # Blocked pending a human-present approval.
    assert t.status == TaskStatus.AWAITING_APPROVAL
    assert svc.agent("comms").state == "awaiting_approval"
    appr = svc.pending_approvals()
    assert len(appr) == 1 and not sent
    # Human approves → executes, task done, Slack actually posted, audited.
    svc.approve(appr[0].id, decided_by="moi")
    assert t.status == TaskStatus.DONE
    assert sent == [{"channel": "#marketing", "text": "Friday."}]
    assert any(a.action == "post_message" and a.human for a in gw.audit)


def test_deny_blocks_task_and_does_not_execute():
    svc, gw, sent = _office()
    t = svc.dispatch("comms", "post something")
    svc.perform(t, [{"connector": "slack", "action": "post_message", "args": {"text": "no"}}])
    appr = svc.pending_approvals()[0]
    svc.deny(appr.id, decided_by="moi")
    assert t.status == TaskStatus.BLOCKED
    assert sent == []


def test_act_autonomy_executes_writes_without_approval():
    svc, gw, sent = _office()
    # research has autonomy ACT on slack → write runs immediately, no approval.
    t = svc.dispatch("research", "post finding")
    svc.perform(t, [{"connector": "slack", "action": "post_message", "args": {"text": "found it"}}])
    assert t.status == TaskStatus.DONE
    assert sent == [{"channel": "#general", "text": "found it"}]
    assert not svc.pending_approvals()


def test_destructive_never_autonomous_even_under_act():
    gw = ConnectorGateway()
    gw.register(github_stub())
    svc = OfficeService(gw)
    svc.add_agent(Agent(id="code", role="Code", chrnum=0x34, tools=["github"],
                        autonomy={"github": Autonomy.ACT}))
    t = svc.dispatch("code", "merge pr")
    svc.perform(t, [{"connector": "github", "action": "merge", "args": {"pr": 7}}])
    # destructive is gated even at ACT autonomy → needs approval.
    assert t.status == TaskStatus.AWAITING_APPROVAL


def test_unequipped_tool_is_refused():
    gw = ConnectorGateway()
    gw.register(pagerduty_stub())
    svc = OfficeService(gw)
    a = Agent(id="qa", role="QA", chrnum=0x35, tools=[])  # not equipped with pagerduty
    svc.add_agent(a)
    try:
        gw.invoke(a, "pagerduty", "read_incidents", {})
        assert False, "expected PolicyError"
    except PolicyError:
        pass


def test_multi_step_plan_resumes_after_approval():
    svc, gw, sent = _office()
    t = svc.dispatch("comms", "read then reply")
    svc.perform(t, [
        {"connector": "slack", "action": "read_threads", "args": {}},        # read: runs
        {"connector": "slack", "action": "post_message", "args": {"text": "on it"}},  # write: gate
    ])
    assert t.status == TaskStatus.AWAITING_APPROVAL
    assert len(t.artifacts) == 1  # the read completed before the gate
    svc.approve(svc.pending_approvals()[0].id)
    assert t.status == TaskStatus.DONE
    assert sent and sent[-1]["text"] == "on it"


def test_connector_slack_live_post_after_approval_when_token_installed():
    """Pass 32: approved slack.post_message calls chat.postMessage when OAuth bot token installed."""
    import json
    import os
    import tempfile
    import threading
    import time
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from pathlib import Path

    from service.slack_oauth import SlackOAuthInstallState, SlackOAuthInstallStatus, save_slack_oauth  # noqa: WPS433

    captured: list[dict] = []

    class _Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length") or "0")
            raw = self.rfile.read(length)
            captured.append(json.loads(raw.decode("utf-8")))
            body = json.dumps({"ok": True, "ts": "8888.0001", "channel": "C_LIVE"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    post_url = f"http://127.0.0.1:{server.server_address[1]}/chat.postMessage"

    with tempfile.TemporaryDirectory() as tmp:
        oauth_path = Path(tmp) / "slack_oauth.json"
        os.environ["AGENT_OFFICE_SLACK_OAUTH"] = str(oauth_path)
        os.environ["SLACK_CHAT_POST_URL"] = post_url
        save_slack_oauth(
            SlackOAuthInstallState(
                status=SlackOAuthInstallStatus.INSTALLED,
                team_id="T_LIVE",
                team_name="Live Team",
                bot_user_id="U_BOT",
                scopes=("chat:write",),
                installed_at=time.time(),
                token_hint="live",
            ),
            bot_token="xoxb-live-token",
            repo_root=tmp,
        )
        try:
            gw = ConnectorGateway()
            stub_sent: list[dict] = []
            gw.register(slack_connector(stub_sent, repo_root=tmp))
            gw.register(pagerduty_stub())
            gw.register(github_stub())
            svc = OfficeService(gw)
            svc.add_agent(Agent(id="comms", role="Comms", chrnum=0x38, tools=["slack"],
                                autonomy={"slack": Autonomy.ASK_APPROVAL}))

            t = svc.dispatch("comms", "post release note")
            svc.perform(t, [{"connector": "slack", "action": "post_message",
                             "args": {"channel": "#release", "text": "Shipped."}}])
            assert t.status == TaskStatus.AWAITING_APPROVAL
            assert not captured and not stub_sent

            svc.approve(svc.pending_approvals()[0].id, decided_by="security")
            assert t.status == TaskStatus.DONE
            assert captured == [{"channel": "#release", "text": "Shipped."}]
            assert stub_sent == []
            assert any(a.action == "post_message" and a.human and a.result == "ok" for a in gw.audit)
        finally:
            os.environ.pop("AGENT_OFFICE_SLACK_OAUTH", None)
            os.environ.pop("SLACK_CHAT_POST_URL", None)

    server.shutdown()
    thread.join(timeout=2)
    server.server_close()


def test_connector_slack_stub_when_no_token():
    """Pass 32: without OAuth token, connector post_message stays offline stub."""
    gw = ConnectorGateway()
    sent: list[dict] = []
    gw.register(slack_connector(sent))
    svc = OfficeService(gw)
    svc.add_agent(Agent(id="comms", role="Comms", chrnum=0x38, tools=["slack"],
                        autonomy={"slack": Autonomy.ASK_APPROVAL}))
    t = svc.dispatch("comms", "offline reply")
    svc.perform(t, [{"connector": "slack", "action": "post_message",
                     "args": {"channel": "#general", "text": "Local only."}}])
    svc.approve(svc.pending_approvals()[0].id)
    assert sent == [{"channel": "#general", "text": "Local only."}]


def test_slack_round_trip_flags_comms_and_logs_event():
    svc, gw, _ = _office()
    svc.ingest_slack({"channel": "#eng", "text": "@you prod status?", "mention": True})
    assert svc.agent("comms").state == "blocked"          # needs you
    assert svc.bus.history("slack.")                      # event logged
    fs = svc.fleet_status()
    assert fs["agents"]["Comms"] == "blocked"


def test_fleet_status_and_audit_and_event_log():
    svc, gw, sent = _office()
    t = svc.dispatch("ops", "page")
    svc.perform(t, [{"connector": "pagerduty", "action": "page_oncall", "args": {}}])
    svc.approve(svc.pending_approvals()[0].id)
    fs = svc.fleet_status()
    assert fs["tasks"]["done"] == 1
    assert fs["audit_entries"] >= 1
    assert svc.bus.history("task.")                       # task lifecycle events present


def test_director_engage_dispatches_task_to_service():
    """C3: engaging an agent in the 3D director creates a Task in the control plane."""
    import office_director as od

    gw = ConnectorGateway()
    svc = OfficeService(gw)
    svc.add_agent(Agent(id="director", role="Director", chrnum=0x31, tools=[]))
    brains = {"Director": od.AgentBrain({"slug": "director", "role": "Director"})}
    director = od.OfficeDirector(brains, client=None, service=svc,
                                 role_ids={"Director": "director"})
    director.step(od.DRY_FIXTURE)  # player faces the Director in the fixture
    assert director.last_task.get("Director"), "engage should have dispatched a task"
    tid = director.last_task["Director"]
    assert svc.tasks[tid].agent_id == "director"
    assert svc.tasks[tid].created_by == "human"


def test_agent_brain_uses_llm_backend_json_reply():
    """C3: a live brain consumes the llm-play backend contract and returns HUD-safe text."""
    import office_director as od

    class FakeBackend:
        name = "fake"

        def generate(self, system_prompt: str, user_prompt: str) -> str:
            assert "Return ONLY valid JSON" in system_prompt
            assert "what are you working on" in user_prompt
            return '{"reply":"Queue is green. Ops is watching the deploy."}'

    brain = od.AgentBrain(
        {"slug": "director", "role": "Director", "system_prompt": "Stay in character."},
        backend=FakeBackend(),
    )
    assert brain.respond("what are you working on?") == "Queue is green. Ops is watching the deploy."


def test_director_dispatch_context_preserves_utterance_and_reply():
    """C3: service dispatch receives the player utterance plus the in-world reply context."""
    import office_director as od

    gw = ConnectorGateway()
    svc = OfficeService(gw)
    svc.add_agent(Agent(id="director", role="Director", chrnum=0x31, tools=[]))
    brains = {"Director": od.AgentBrain({"slug": "director", "role": "Director"})}
    director = od.OfficeDirector(
        brains,
        client=None,
        service=svc,
        role_ids={"Director": "director"},
        input_provider=lambda: "summarize the room",
    )
    director.step(od.DRY_FIXTURE)
    task = svc.tasks[director.last_task["Director"]]
    assert task.intent == "summarize the room"
    assert task.context["role"] == "Director"
    assert task.context["chrnum"] == 0x31
    assert "agent_reply" in task.context


def test_director_proximity_appends_shared_dm_thread():
    """Pass 9: proximity engage appends human + agent lines to dm_threads sidecar."""
    import os
    import tempfile
    from pathlib import Path

    import office_director as od

    from service.dm_threads import DmThreadReadStatus, dm_thread_read_outcome  # noqa: WPS433
    from service.workspace_config import merge_workspace_config  # noqa: WPS433

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AGENT_OFFICE_WORKSPACE_CONFIG"] = str(Path(tmp) / "workspace_config.json")
        os.environ["AGENT_OFFICE_DM_THREADS"] = str(Path(tmp) / "dm_threads.json")
        try:
            merge_workspace_config(
                {"location_key": "g5", "member": {"display_name": "Joanna Dark"}},
                repo_root=tmp,
            )
            brains = {"Director": od.AgentBrain({"slug": "director", "role": "Director"})}
            director = od.OfficeDirector(
                brains,
                client=None,
                input_provider=lambda: "fleet status?",
                repo_root=tmp,
            )
            director.step(od.DRY_FIXTURE)
            read = dm_thread_read_outcome("director", repo_root=tmp)
            assert read.status == DmThreadReadStatus.FOUND
            assert read.thread is not None
            messages = read.thread["messages"]
            assert len(messages) >= 2
            assert messages[0]["from"] == "human"
            assert messages[0]["text"] == "fleet status?"
            assert messages[1]["from"] == "agent"
            assert messages[1]["text"]
        finally:
            os.environ.pop("AGENT_OFFICE_WORKSPACE_CONFIG", None)
            os.environ.pop("AGENT_OFFICE_DM_THREADS", None)


def test_electron_connector_approval_renderer_wiring_present():
    """Pass 34: Electron Comms stage + Director desk connector approval UI."""
    app_js = (REPO / "tools/agent-office-electron/renderer/app.js").read_text(encoding="utf-8")
    index_html = (REPO / "tools/agent-office-electron/renderer/index.html").read_text(encoding="utf-8")
    styles_css = (REPO / "tools/agent-office-electron/renderer/styles.css").read_text(encoding="utf-8")
    assert "getConnectorApprovals" in app_js
    assert "renderConnectorApprovals" in app_js
    assert "submitConnectorStage" in app_js
    assert "approveConnectorApproval" in app_js
    assert "connectorApprovalBusy" in app_js
    assert 'id="connectorStageForm"' in index_html
    assert 'id="connectorApprovalSection"' in index_html
    assert 'id="connectorApprovalList"' in index_html
    assert ".connector-approval-card" in styles_css
    assert ".connector-stage-form" in styles_css


def test_electron_connector_approval_ipc_wiring_present():
    """Pass 34: main + preload expose connector approval IPC."""
    preload = (REPO / "tools/agent-office-electron/preload.js").read_text(encoding="utf-8")
    main_js = (REPO / "tools/agent-office-electron/main.js").read_text(encoding="utf-8")
    assert "getConnectorApprovals" in preload
    assert "approveConnectorApproval" in preload
    assert "denyConnectorApproval" in preload
    assert "dispatchConnectorTask" in preload
    assert "office:get-connector-approvals" in main_js
    assert "office:approve-connector-approval" in main_js
    assert "office:deny-connector-approval" in main_js
    assert "office:dispatch-connector-task" in main_js
    assert "/approvals" in main_js
    assert "/dispatch" in main_js


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                fails += 1
                print(f"FAIL {name}: {e}")
            except Exception as e:  # noqa: BLE001
                fails += 1
                print(f"ERROR {name}: {type(e).__name__}: {e}")
    print(f"\n{'OK' if not fails else str(fails) + ' FAILED'}")
    sys.exit(1 if fails else 0)
