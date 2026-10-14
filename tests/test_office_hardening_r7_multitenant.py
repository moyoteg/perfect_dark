"""Horizon 3 Hardening Tests — Multi-Tenant Registry 404, Live Connectors, Earshot Slicing, R7 Social Bus & Hermes Director.

Runnable:
    python3 tests/test_office_hardening_r7_multitenant.py
    python3 -m pytest tests/test_office_hardening_r7_multitenant.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools" / "agent_office_llm"))

import office_director as od
from service import (
    Agent,
    Approval,
    Autonomy,
    ConnectorGateway,
    OfficeService,
    TaskStatus,
)
from service.connectors import github_connector, pagerduty_connector, slack_stub
from service.hermes_director import HermesDirectorAgent
from service.http_api import OfficeServiceAPI
from service.tenant import (
    is_registered_tenant,
    tenant_context,
    tenant_registry_enforced,
)


def test_tenant_registry_enforcement_and_post_tenants():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        office = root / "journal" / "agent_office"
        office.mkdir(parents=True)
        (office / "tenants.json").write_text(
            json.dumps({
                "version": 1,
                "enforce_registry": True,
                "tenants": [
                    {"id": "default", "name": "Default Office", "fc_tenant_id": "default"},
                    {"id": "acme", "name": "Acme Corp", "fc_tenant_id": "tenant-acme"},
                ],
            }),
            encoding="utf-8",
        )
        assert tenant_registry_enforced(str(root)) is True
        assert is_registered_tenant("acme", str(root)) is True
        assert is_registered_tenant("tenant-acme", str(root)) is True
        assert is_registered_tenant("rogue-tenant", str(root)) is False

        api = OfficeServiceAPI(repo_root=str(root))

        # Unknown tenant rejected with 404 when enforce_registry is enabled
        status_unknown, body_unknown = api.get(
            "/health",
            headers={"X-Office-Tenant": "rogue-tenant"},
        )
        assert status_unknown == 404
        assert body_unknown["status"] == "unknown_tenant"

        # FC alias resolves to canonical tenant id in /health
        status_alias, body_alias = api.get(
            "/health",
            headers={"X-Office-Tenant": "tenant-acme"},
        )
        assert status_alias == 200
        assert body_alias["tenant"] == "acme"

        # POST /tenants registers a new tenant and initializes its state root
        status_create, body_create = api.post(
            "/tenants",
            {"id": "nova", "name": "Nova Labs", "fc_tenant_id": "tenant-nova"},
        )
        assert status_create == 201
        assert body_create["tenant"]["id"] == "nova"
        assert is_registered_tenant("tenant-nova", str(root)) is True

        status_nova, body_nova = api.get(
            "/health",
            headers={"X-Office-Tenant": "tenant-nova"},
        )
        assert status_nova == 200
        assert body_nova["tenant"] == "nova"


def test_live_pagerduty_and_github_connectors():
    captured_reqs: list[tuple[str, str, dict]] = []

    class _MockConnectorServer(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length") or "0")
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            captured_reqs.append((self.path, self.headers.get("Authorization", ""), body))
            if "pagerduty" in self.path:
                resp = json.dumps({"status": "success", "dedup_key": "PD-LIVE-99"}).encode("utf-8")
                self.send_response(202)
            else:
                resp = json.dumps({"number": 108, "html_url": "https://github.com/org/repo/pull/108"}).encode("utf-8")
                self.send_response(201)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)

        def log_message(self, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), _MockConnectorServer)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"

    os.environ["PAGERDUTY_ROUTING_KEY"] = "pd-test-key"
    os.environ["PAGERDUTY_EVENTS_URL"] = f"{base_url}/pagerduty/enqueue"
    os.environ["GITHUB_TOKEN"] = "ghp-test-token"
    os.environ["GITHUB_API_URL"] = f"{base_url}/github"
    try:
        gw = ConnectorGateway()
        gw.register(pagerduty_connector())
        gw.register(github_connector())
        svc = OfficeService(gw)
        svc.add_agent(Agent(id="ops", role="Ops", chrnum=0x37, tools=["pagerduty"],
                            autonomy={"pagerduty": Autonomy.ACT}))
        svc.add_agent(Agent(id="code", role="Code", chrnum=0x34, tools=["github"],
                            autonomy={"github": Autonomy.ACT}))

        t_pd = svc.dispatch("ops", "page oncall")
        svc.perform(t_pd, [{"connector": "pagerduty", "action": "create_incident", "args": {"title": "DB latency"}}])
        assert t_pd.status == TaskStatus.DONE
        assert "PD-LIVE-99" in t_pd.artifacts[-1]

        t_gh = svc.dispatch("code", "open PR")
        svc.perform(t_gh, [{"connector": "github", "action": "open_pr",
                            "args": {"repo": "moyoteg/llm-play", "title": "Harden VAO", "head": "feat/vao"}}])
        assert t_gh.status == TaskStatus.DONE
        assert "108" in t_gh.artifacts[-1]
        assert len(captured_reqs) == 2
    finally:
        os.environ.pop("PAGERDUTY_ROUTING_KEY", None)
        os.environ.pop("PAGERDUTY_EVENTS_URL", None)
        os.environ.pop("GITHUB_TOKEN", None)
        os.environ.pop("GITHUB_API_URL", None)
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def test_earshot_slicing_and_social_bus_rumor_tick():
    obs = {
        "stage": 131,
        "players": [{"pos": {"x": 0.0, "y": 0.0, "z": 0.0}, "facing_deg": 0.0}],
        "agents": [
            {"chrnum": 0x31, "role": "Director", "pos": {"x": 100.0, "y": 0.0, "z": 0.0}, "visible": True},
            {"chrnum": 0x32, "role": "Orchestrator", "pos": {"x": 200.0, "y": 0.0, "z": 0.0}, "visible": False},
            {"chrnum": 0x38, "role": "Comms", "pos": {"x": 2500.0, "y": 0.0, "z": 0.0}, "visible": False},
        ],
    }
    sliced = od.slice_observation_for_agent(obs, 0x31, earshot_range=650.0)
    perceived_chrnums = {a["chrnum"] for a in sliced["agents"]}
    assert 0x31 in perceived_chrnums
    assert 0x32 in perceived_chrnums
    assert 0x38 not in perceived_chrnums

    gw = ConnectorGateway()
    svc = OfficeService(gw)
    svc.add_agent(Agent(id="director", role="Director", chrnum=0x31))
    svc.add_agent(Agent(id="security", role="Security", chrnum=0x36))
    svc.social.route(
        from_office="ci",
        to_office="g5",
        kind="guard_report",
        text="CI Lobby perimeter clear.",
        from_agent_id="security",
        to_agent_id="director",
    )

    acts: list[dict] = []

    class _Client:
        def act(self, payload: dict) -> None:
            acts.append(payload)

    with tempfile.TemporaryDirectory() as tmp:
        with tenant_context("acme"):
            brains = {
                "Director": od.AgentBrain(
                    {"slug": "director", "role": "Director", "chrnum": 0x31, "memory_file": "journal/agent_office/memory/director.md"},
                    repo_root=Path(tmp),
                ),
                "Security": od.AgentBrain(
                    {"slug": "security", "role": "Security", "chrnum": 0x36, "memory_file": "journal/agent_office/memory/security.md"},
                    repo_root=Path(tmp),
                ),
            }
            assert "tenants/acme/memory" in str(brains["Director"].memory_file)
            director = od.OfficeDirector(
                brains,
                client=_Client(),
                service=svc,
                role_ids={"Director": "director", "Security": "security"},
                repo_root=tmp,
            )
            far_obs = {
                "stage": 131,
                "players": [{"pos": {"x": -5000.0, "y": 0.0, "z": -5000.0}, "facing_deg": 0.0}],
                "agents": [
                    {"chrnum": 0x31, "role": "Director", "pos": {"x": 0.0, "y": 0.0, "z": 0.0}},
                    {"chrnum": 0x36, "role": "Security", "pos": {"x": 200.0, "y": 0.0, "z": 0.0}},
                ],
            }
            director.step(far_obs)
            assert any(role == "rumor" and "CI Lobby perimeter clear." in text for role, text in brains["Director"].memory)
            assert any(
                any("CI Lobby perimeter clear" in ag.get("say", "") for ag in a.get("agents", []))
                for a in acts
            )


def test_hermes_director_auto_approves_read_and_cancels_failed():
    gw = ConnectorGateway()
    gw.register(slack_stub([]))
    svc = OfficeService(gateway=gw)
    svc.add_agent(Agent(id="qa", role="qa", chrnum=201))
    svc.add_agent(Agent(id="comms", role="comms", chrnum=202, tools=["slack"]))
    director = HermesDirectorAgent(service=svc)

    t_read = svc.dispatch("comms", "Read threads")
    appr = Approval.new(t_read.id, "comms", "slack", "read_threads", {}, risk="read")
    svc.approvals[appr.id] = appr
    t_read.status = TaskStatus.AWAITING_APPROVAL

    t_fail = svc.dispatch("qa", "Broken build")
    t_fail.status = TaskStatus.FAILED
    t_fail.result = "exit 1"

    res = director.evaluate_swarm_lifecycle()
    assert appr.id in res["auto_approved"]
    assert t_fail.id in res["interrupted_tasks"]


if __name__ == "__main__":
    test_tenant_registry_enforcement_and_post_tenants()
    test_live_pagerduty_and_github_connectors()
    test_earshot_slicing_and_social_bus_rumor_tick()
    test_hermes_director_auto_approves_read_and_cancels_failed()
    print("ok - test_office_hardening_r7_multitenant")
