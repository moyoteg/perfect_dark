"""HTTP API for the Virtual Agent Office control plane.

This is the host-facing seam for Projex/PragChat. The Perfect Dark 3D office,
PragChat, and any remote/webhook clients should all talk to the same OfficeService
state instead of building separate task, approval, memory, or audit stores.

The module is stdlib-only so it can run anywhere the existing service tests run.
It intentionally exposes a small, explicit JSON API rather than a framework server;
production can wrap the same service in FastAPI/Cloud Run/etc. later without changing
the control-plane contract.
"""
from __future__ import annotations

import argparse
import json
import threading
from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Increase listen queue backlog to prevent macOS connection reset (ECONNRESET) during concurrent bursts
ThreadingHTTPServer.request_queue_size = 128
from typing import Any
from urllib.parse import parse_qs, urlparse

from .connectors import (
    ConnectorGateway,
    github_connector,
    github_stub,
    pagerduty_connector,
    pagerduty_stub,
    slack_connector,
)
from .models import Agent, Approval, AuditEntry, Autonomy, Event, Task, _id
from .office_service import Action, OfficeService
from .dm_threads import (
    DmThreadAppendStatus,
    DmThreadMarkReadStatus,
    DmThreadReadStatus,
    VALID_AGENT_IDS,
    compute_dm_thread_unread,
    format_dm_unread_notification_stub,
    format_dm_visor_rail_lines,
    format_dm_visor_rail_text,
    format_dm_visor_scrollback_lines,
    format_dm_visor_scrollback_text,
    format_visor_compose_picker_text,
    format_security_connector_picker_huds_text,
    format_security_connector_picker_text,
    project_comms_connector_stage,
    project_visor_compose_target,
    project_security_connector_hud,
    sum_dm_threads_unread,
    dm_thread_append_outcome,
    dm_thread_mark_read_outcome,
    dm_thread_read_outcome,
    format_dm_thread_tail_for_hud,
    list_dm_threads_for_member,
    merge_persisted_dm_tails,
    parse_walk_up_dm_append_request,
    walk_up_dm_hud_outcome,
)
from .dm_tts import DmTtsSpeakStatus, project_dm_tts_speak_json
from .slack_api import (
    SlackEventsIngestStatus,
    SlackOutboundPostStatus,
    slack_events_ingest_outcome,
    slack_outbound_post_outcome,
)
from .slack_oauth import (
    SlackOAuthBeginStatus,
    SlackOAuthCompleteStatus,
    SlackOAuthDenySecurityStatus,
    SlackOAuthDisconnectStatus,
    SlackOAuthInstallStatus,
    slack_oauth_approve_security_outcome,
    slack_oauth_begin_install_outcome,
    slack_oauth_complete_install_outcome,
    slack_oauth_deny_security_outcome,
    slack_oauth_disconnect_outcome,
    slack_oauth_pending_security_approval_outcome,
    slack_oauth_status_outcome,
)
from .tenant import (
    DEFAULT_TENANT_ID,
    current_tenant_id,
    ensure_tenant_state_root,
    is_registered_tenant,
    load_tenants_registry,
    office_id_for_fc_tenant,
    parse_tenant_record,
    resolve_tenant_state_root,
    resolve_tenants_registry_path,
    serialize_tenant_record,
    tenant_context,
    tenant_from_headers_and_query,
    tenant_registry_enforced,
)
from .workspace_config import (
    ChannelActivityStatus,
    ChannelMarkReadStatus,
    WorkspaceConfigLoadStatus,
    WorkspaceConfigMergeStatus,
    channel_activity_from_event_outcome,
    emit_workspace_lifecycle_log,
    general_channel_summary_stub,
    increment_channel_unread,
    load_workspace_config_outcome,
    mark_channel_read_outcome,
    merge_workspace_config_outcome,
    slack_channels_view,
)

JSON = dict[str, Any]

_CORS_ALLOW_HEADERS = (
    "Content-Type, X-Office-Tenant, X-Slack-Request-Timestamp, X-Slack-Signature"
)


@dataclass(frozen=True)
class HtmlResponse:
    """Browser-facing HTML payload for OAuth redirect callbacks (Pass 27)."""

    status: int
    body: str
    content_type: str = "text/html; charset=utf-8"


def _slack_oauth_callback_html(complete_outcome: Any) -> HtmlResponse:
    """Render a minimal success/error page after Slack browser redirect."""
    status = complete_outcome.status
    if status == SlackOAuthCompleteStatus.INSTALLED:
        team = complete_outcome.install.team_name if complete_outcome.install else "Slack workspace"
        body = (
            "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
            "<title>Virtual Agent Office — Slack connected</title>"
            "<style>body{font-family:system-ui,sans-serif;background:#0a1018;color:#e8eef5;"
            "display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}"
            ".card{max-width:28rem;padding:2rem;border:1px solid #2a3544;border-radius:12px}"
            "h1{font-size:1.25rem;margin:0 0 .5rem}p{margin:0;color:#9fb0c3}</style></head>"
            f"<body><div class=\"card\"><h1>Connected to {team}</h1>"
            "<p>Return to Virtual Agent Office — the Comms desk will refresh automatically.</p>"
            "</div></body></html>"
        )
        return HtmlResponse(status=int(HTTPStatus.OK), body=body)
    if status == SlackOAuthCompleteStatus.AWAITING_SECURITY_APPROVAL:
        approval_id = ""
        if complete_outcome.install and complete_outcome.install.security_approval_id:
            approval_id = complete_outcome.install.security_approval_id
        body = (
            "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
            "<title>Virtual Agent Office — Security approval required</title>"
            "<style>body{font-family:system-ui,sans-serif;background:#101018;color:#e8eef5;"
            "display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}"
            ".card{max-width:28rem;padding:2rem;border:1px solid #3a3544;border-radius:12px}"
            "h1{font-size:1.25rem;margin:0 0 .5rem}p{margin:0 0 .75rem;color:#b0b8c8}"
            "code{font-size:.85rem;color:#f0c674}</style></head>"
            "<body><div class=\"card\"><h1>Authorization received</h1>"
            "<p>Slack OAuth succeeded, but Security must approve bot token use before "
            "the workspace connects.</p>"
            "<p>Walk to the Security desk in Virtual Agent Office and approve the pending "
            "Slack connector request.</p>"
            f"<p>Approval id: <code>{approval_id}</code></p>"
            "</div></body></html>"
        )
        return HtmlResponse(status=int(HTTPStatus.OK), body=body)
    error = complete_outcome.error or "OAuth callback failed"
    body = (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        "<title>Virtual Agent Office — Slack connect failed</title>"
        "<style>body{font-family:system-ui,sans-serif;background:#1a1010;color:#fde8e8;"
        "display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}"
        ".card{max-width:28rem;padding:2rem;border:1px solid #5a3030;border-radius:12px}"
        "h1{font-size:1.25rem;margin:0 0 .5rem}p{margin:0;color:#f0b8b8}</style></head>"
        f"<body><div class=\"card\"><h1>Could not connect Slack</h1>"
        f"<p>{error}</p><p>Close this tab and retry from Virtual Agent Office.</p>"
        "</div></body></html>"
    )
    http_status = HTTPStatus.BAD_REQUEST
    if status == SlackOAuthCompleteStatus.NOT_PENDING:
        http_status = HTTPStatus.CONFLICT
    elif status == SlackOAuthCompleteStatus.INVALID:
        http_status = HTTPStatus.INTERNAL_SERVER_ERROR
    elif status == SlackOAuthCompleteStatus.TOKEN_EXCHANGE_FAILED:
        http_status = HTTPStatus.BAD_GATEWAY
    return HtmlResponse(status=int(http_status), body=body)


def create_default_service(
    *,
    reload_persisted: bool = False,
    tenant_id: str | None = None,
    repo_root: str | None = None,
) -> OfficeService:
    """Build the default Office Service roster for Projex/PragChat development.

    The roster mirrors the in-world order in office_director. Tools are conservative:
    write-capable connectors default to ask-approval so host clients can prove the
    approval loop before any real connector is swapped in.

    When ``reload_persisted=True`` (production server bootstrap), pending connector
    approvals are restored from ``office_service_state.json`` sidecar (Pass 38).
    """
    gateway = ConnectorGateway()
    gateway.register(slack_connector() if repo_root is None else slack_connector(repo_root=repo_root))
    gateway.register(pagerduty_connector(repo_root=repo_root))
    gateway.register(github_connector(repo_root=repo_root))

    svc = OfficeService(gateway)
    svc.add_agent(Agent(
        id="director",
        role="Director",
        chrnum=0x31,
        tools=["slack", "github", "pagerduty"],
        autonomy={"slack": Autonomy.ASK_APPROVAL, "github": Autonomy.ASK_APPROVAL,
                  "pagerduty": Autonomy.ASK_APPROVAL},
        voice_slug="director",
    ))
    svc.add_agent(Agent(id="orchestrator", role="Orchestrator", chrnum=0x32,
                        voice_slug="orchestrator"))
    svc.add_agent(Agent(id="research", role="Research", chrnum=0x33,
                        tools=["github"], autonomy={"github": Autonomy.ACT},
                        voice_slug="research"))
    svc.add_agent(Agent(id="code", role="Code", chrnum=0x34,
                        tools=["github"], autonomy={"github": Autonomy.ASK_APPROVAL},
                        voice_slug="code"))
    svc.add_agent(Agent(id="qa", role="QA", chrnum=0x35,
                        tools=["github"], autonomy={"github": Autonomy.ACT},
                        voice_slug="qa"))
    svc.add_agent(Agent(id="security", role="Security", chrnum=0x36,
                        voice_slug="security"))
    svc.add_agent(Agent(id="ops", role="Ops", chrnum=0x37,
                        tools=["pagerduty"], autonomy={"pagerduty": Autonomy.ASK_APPROVAL},
                        voice_slug="ops"))
    svc.add_agent(Agent(id="comms", role="Comms", chrnum=0x38,
                        tools=["slack"], autonomy={"slack": Autonomy.ASK_APPROVAL},
                        voice_slug="comms"))
    if reload_persisted:
        from .service_state import try_reload_service_state

        with tenant_context(tenant_id):
            try_reload_service_state(svc, repo_root=repo_root)
    return svc


def _json_value(value: Any) -> Any:
    """Convert service dataclasses/enums into stable JSON primitives."""
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {k: _json_value(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): _json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(v) for v in value]
    return value


def serialize_agent(agent: Agent) -> JSON:
    data = _json_value(agent)
    data["autonomy"] = {k: _json_value(v) for k, v in agent.autonomy.items()}
    data["embodied"] = True
    return data


def serialize_agent_monitor(service: OfficeService, agent_id: str) -> JSON:
    """Diegetic monitor / Perfect Menu payload for one agent desk."""
    return service.agent_monitor(agent_id)


def serialize_task(task: Task) -> JSON:
    return _json_value(task)


def serialize_approval(approval: Approval) -> JSON:
    return _json_value(approval)


def serialize_event(event: Event) -> JSON:
    return _json_value(event)


def serialize_audit(entry: AuditEntry) -> JSON:
    return _json_value(entry)


def pragchat_snapshot(service: OfficeService) -> JSON:
    """Render Office Service state in the shape a Projex/PragChat host can consume.

    This is not a separate state model. It is a projection over agents/tasks/events
    so PragChat and the 3D office stay synchronized through one service core.
    """
    agents = [serialize_agent(a) for a in service.agents.values()]
    tasks = [serialize_task(t) for t in service.tasks.values()]
    approvals = [serialize_approval(a) for a in service.pending_approvals()]
    events = [serialize_event(e) for e in service.bus.history()]

    channels = [
        {
            "id": "agent-office",
            "type": "project",
            "title": "Virtual Agent Office",
            "topic": "Shared agent workspace for Perfect Dark 3D office and PragChat.",
            "linked_agent_ids": [a["id"] for a in agents],
            "task_ids": [t["id"] for t in tasks],
        },
        {
            "id": "approvals",
            "type": "approval",
            "title": "Approvals",
            "topic": "Human-present approvals staged by Security and write-capable agents.",
            "pending_approval_ids": [a["id"] for a in approvals],
        },
    ]
    agent_dms = [
        {
            "id": f"agent-{a['id']}",
            "agent_id": a["id"],
            "title": a["role"],
            "state": a["state"],
            "voice_slug": a.get("voice_slug", ""),
            "tools": a.get("tools", []),
        }
        for a in agents
    ]
    agent_dms = merge_persisted_dm_tails(agent_dms)
    threads = [
        {
            "id": f"task-{t['id']}",
            "channel_id": "agent-office",
            "subject": t["intent"],
            "task_id": t["id"],
            "agent_id": t["agent_id"],
            "status": t["status"],
            "messages": [
                {"from": t["created_by"], "text": t["intent"], "ts": t["created_at"]},
            ],
            "artifacts": t.get("artifacts", []),
        }
        for t in tasks
    ]

    return {
        "workspace": {
            "id": "virtual-agent-office",
            "title": "Virtual Agent Office",
            "host_preference": "Projex/PragChat",
            "spatial_client": "Perfect Dark 3D office tab",
        },
        "channels": channels,
        "agent_dms": agent_dms,
        "threads": threads,
        "approval_cards": approvals,
        "task_cards": tasks,
        "events": events,
        "fleet": service.fleet_status(),
    }


def pragchat_manifest(default_base_url: str = "http://127.0.0.1:8791") -> JSON:
    """Describe the Office Service as PragChat resources.

    Projex can either hard-code these resource definitions or load them at startup
    from `/pragchat/manifest`. The endpoints stay relative so the host can mount the
    service behind a local proxy without rewriting the contract.
    """
    action_schema: JSON = {
        "type": "object",
        "properties": {
            "connector": {"type": "string", "description": "Connector id, e.g. slack/github/pagerduty."},
            "action": {"type": "string", "description": "Connector action to execute or stage."},
            "args": {"type": "object", "description": "Connector-specific action arguments."},
        },
        "required": ["connector", "action"],
    }
    return {
        "version": "agent-office-pragchat-v1",
        "default_base_url": default_base_url,
        "system_prompt": (
            "You are the Projex/PragChat operator for the Virtual Agent Office. "
            "Use the Office Service resources to inspect agents, dispatch work, "
            "surface approvals, and synchronize with the Perfect Dark 3D office tab. "
            "Do not pretend write actions were completed until an approval or audit "
            "entry confirms the Office Service performed them."
        ),
        "resources": [
            {
                "name": "OfficeAgent",
                "description": "An AI agent represented in PragChat and the Perfect Dark 3D office.",
                "schema": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "role": {"type": "string"},
                        "state": {"type": "string"},
                        "chrnum": {"type": "number"},
                        "tools": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "endpoints": {
                    "list": {"method": "GET", "url": "/agents"},
                    "get": {"method": "GET", "url": "/agents/:id"},
                },
            },
            {
                "name": "OfficeTask",
                "description": "A work item assigned to an Office agent by the human, PragChat, Slack, or another agent.",
                "schema": {
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string", "description": "Agent id to dispatch to."},
                        "intent": {"type": "string", "description": "Plain-language work request."},
                        "context": {"type": "object", "description": "Optional task context."},
                        "created_by": {"type": "string", "description": "Origin, e.g. prag_chat or human."},
                    },
                    "required": ["agent_id", "intent"],
                },
                "endpoints": {
                    "list": {"method": "GET", "url": "/tasks"},
                    "get": {"method": "GET", "url": "/tasks/:id"},
                    "create": {"method": "POST", "url": "/dispatch"},
                    "custom": [
                        {
                            "name": "perform",
                            "method": "POST",
                            "url": "/tasks/:task_id/perform",
                            "description": "Run or stage connector actions for a task. Ask-approval tools return awaiting_approval.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "actions": {"type": "array", "items": action_schema},
                                },
                            },
                        },
                    ],
                },
            },
            {
                "name": "OfficeApproval",
                "description": "Human-present approval card for a write-capable connector action.",
                "schema": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "task_id": {"type": "string"},
                        "status": {"type": "string"},
                        "decided_by": {"type": "string"},
                    },
                },
                "endpoints": {
                    "list": {"method": "GET", "url": "/approvals"},
                    "get": {"method": "GET", "url": "/approvals/:id"},
                    "custom": [
                        {
                            "name": "approve",
                            "method": "POST",
                            "url": "/approvals/:approval_id/approve",
                            "description": "Approve a pending connector action after the human confirms it.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "decided_by": {"type": "string", "description": "Approver identity."},
                                },
                            },
                        },
                        {
                            "name": "deny",
                            "method": "POST",
                            "url": "/approvals/:approval_id/deny",
                            "description": "Deny a pending connector action.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "decided_by": {"type": "string", "description": "Approver identity."},
                                },
                            },
                        },
                    ],
                },
            },
            {
                "name": "OfficeEvent",
                "description": "Append-only world/chat/connector event shared by PragChat and the 3D office.",
                "schema": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "payload": {"type": "object"},
                        "source": {"type": "string"},
                        "target": {"type": "string"},
                    },
                    "required": ["type"],
                },
                "endpoints": {
                    "list": {"method": "GET", "url": "/events"},
                    "create": {"method": "POST", "url": "/events"},
                },
            },
            {
                "name": "OfficeFleetStatus",
                "description": "Current fleet health and blocked-agent summary.",
                "schema": {"type": "object", "properties": {}},
                "endpoints": {
                    "list": {"method": "GET", "url": "/fleet"},
                },
            },
            {
                "name": "OfficeWorkspaceSnapshot",
                "description": "PragChat-shaped projection of channels, agent DMs, threads, approvals, tasks, events, and fleet status.",
                "schema": {"type": "object", "properties": {}},
                "endpoints": {
                    "list": {"method": "GET", "url": "/pragchat/snapshot"},
                },
            },
        ],
    }


class OfficeServiceAPI:
    """Thread-safe request adapter around OfficeService (multi-tenant aware)."""

    def __init__(
        self,
        service: OfficeService | None = None,
        *,
        repo_root: str | None = None,
        enforce_registry: bool | None = None,
    ) -> None:
        self._services: dict[str, OfficeService] = {}
        self._lock = threading.RLock()
        self.repo_root = repo_root
        self.enforce_registry = enforce_registry
        if service is not None:
            self._services[DEFAULT_TENANT_ID] = service

    def _resolve_request_tenant(
        self,
        *,
        headers: dict[str, str] | None = None,
        query: dict[str, str] | None = None,
    ) -> tuple[str, str]:
        header_map = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
        has_explicit = bool(
            (header_map.get("x-office-tenant") or "").strip()
            or ((query or {}).get("tenant") or "").strip()
        )
        raw_tid = (
            tenant_from_headers_and_query(headers, query)
            if has_explicit
            else current_tenant_id()
        )
        canonical_tid = office_id_for_fc_tenant(raw_tid, self.repo_root)
        return raw_tid, canonical_tid

    def _is_tenant_rejected(self, raw_tid: str, path: str) -> bool:
        if path in ("/tenants", "/slack/oauth/callback"):
            return False
        enforced = (
            self.enforce_registry
            if self.enforce_registry is not None
            else tenant_registry_enforced(self.repo_root)
        )
        if not enforced:
            return False
        return not is_registered_tenant(raw_tid, self.repo_root)

    def get_service(self, tenant_id: str | None = None) -> OfficeService:
        """Resolve tenant-bound OfficeService instance (fc_tenant_id alias-aware)."""
        raw_tid = tenant_id or current_tenant_id()
        tid = office_id_for_fc_tenant(raw_tid, self.repo_root)
        with self._lock:
            if tid not in self._services:
                with tenant_context(tid):
                    svc = create_default_service(
                        reload_persisted=True,
                        tenant_id=tid,
                        repo_root=self.repo_root,
                    )
                self._services[tid] = svc
            return self._services[tid]

    @property
    def service(self) -> OfficeService:
        """Return the OfficeService instance for the active tenant_context."""
        return self.get_service()

    def get(
        self,
        path: str,
        query: dict[str, str] | None = None,
        *,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, Any] | HtmlResponse:
        raw_tid, canonical_tid = self._resolve_request_tenant(headers=headers, query=query)
        if self._is_tenant_rejected(raw_tid, path):
            return HTTPStatus.NOT_FOUND, {
                "error": f"unknown tenant: {raw_tid}",
                "status": "unknown_tenant",
                "tenant": raw_tid,
            }
        with self._lock, tenant_context(canonical_tid):
            parts = [p for p in path.strip("/").split("/") if p]
            if path == "/slack/oauth/callback":
                complete_outcome = slack_oauth_complete_install_outcome(
                    code=str((query or {}).get("code") or ""),
                    state=str((query or {}).get("state") or ""),
                )
                return _slack_oauth_callback_html(complete_outcome)
            if path == "/health":
                # sealed=true: request scope is isolated to this tenant (FC pattern).
                return HTTPStatus.OK, {
                    "ok": True,
                    "service": "virtual-agent-office",
                    "tenant": current_tenant_id(),
                    "sealed": True,
                    "tenant_state_root": str(resolve_tenant_state_root(repo_root=self.repo_root)),
                }
            if path == "/tenants":
                # Listing does not unseal fleet/tasks; drill-in via X-Office-Tenant seals.
                rows = load_tenants_registry(self.repo_root)
                return HTTPStatus.OK, {
                    "tenants": [serialize_tenant_record(r) for r in rows],
                    "active": current_tenant_id(),
                    "sealed": True,
                    "seal": (
                        "List is ops/picker only. Default fleet/task queries are sealed "
                        "to the active tenant (X-Office-Tenant / ?tenant= / OFFICE_TENANT_ID)."
                    ),
                }
            if path == "/agents":
                return HTTPStatus.OK, [serialize_agent(a) for a in self.service.agents.values()]
            if len(parts) == 3 and parts[0] == "agents" and parts[2] == "monitor":
                if parts[1] not in self.service.agents:
                    return HTTPStatus.NOT_FOUND, {"error": f"unknown agent: {parts[1]}"}
                return HTTPStatus.OK, serialize_agent_monitor(self.service, parts[1])
            if len(parts) == 2 and parts[0] == "agents":
                agent = self.service.agents.get(parts[1])
                if not agent:
                    return HTTPStatus.NOT_FOUND, {"error": f"unknown agent: {parts[1]}"}
                payload = serialize_agent(agent)
                payload["monitor"] = serialize_agent_monitor(self.service, agent.id)
                return HTTPStatus.OK, payload
            if path == "/tasks":
                return HTTPStatus.OK, [serialize_task(t) for t in self.service.tasks.values()]
            if len(parts) == 2 and parts[0] == "tasks":
                task = self.service.tasks.get(parts[1])
                if not task:
                    return HTTPStatus.NOT_FOUND, {"error": f"unknown task: {parts[1]}"}
                return HTTPStatus.OK, serialize_task(task)
            if path == "/approvals":
                return HTTPStatus.OK, [serialize_approval(a) for a in self.service.approvals.values()]
            if len(parts) == 2 and parts[0] == "approvals":
                approval = self.service.approvals.get(parts[1])
                if not approval:
                    return HTTPStatus.NOT_FOUND, {"error": f"unknown approval: {parts[1]}"}
                return HTTPStatus.OK, serialize_approval(approval)
            if path == "/events":
                return HTTPStatus.OK, [serialize_event(e) for e in self.service.bus.history()]
            if path == "/audit":
                return HTTPStatus.OK, [serialize_audit(a) for a in self.service.gateway.audit]
            if path == "/fleet":
                return HTTPStatus.OK, self.service.fleet_status()
            if path == "/hermes/status":
                return HTTPStatus.OK, self.service.hermes_director.status()
            if path == "/social/feed":
                office = (query or {}).get("office")
                tenant = (query or {}).get("tenant") or current_tenant_id()
                try:
                    limit = int((query or {}).get("limit") or 50)
                except ValueError:
                    limit = 50
                return HTTPStatus.OK, {
                    "ok": True,
                    "items": self.service.social.feed(office=office, limit=limit),
                    "posts": self.service.social.active_posts(tenant=tenant),
                    "pending_approvals": self.service.social.pending_posts(tenant=tenant),
                    "count": len(self.service.social),
                }
            if path == "/pragchat/snapshot":
                return HTTPStatus.OK, pragchat_snapshot(self.service)
            if path in ("/pragchat/manifest", "/pragchat/resources"):
                return HTTPStatus.OK, pragchat_manifest()
            if path == "/workspace/config":
                outcome = load_workspace_config_outcome()
                if outcome.status == WorkspaceConfigLoadStatus.MISSING:
                    emit_workspace_lifecycle_log(
                        outcome.run_id or "api_get",
                        "http_get_workspace_config",
                        state_before="unknown",
                        state_after="missing",
                        outcome="not_found",
                        path=outcome.path,
                    )
                    return HTTPStatus.NOT_FOUND, {"error": "workspace config not found — sign in via Electron launcher"}
                if outcome.status == WorkspaceConfigLoadStatus.INVALID:
                    emit_workspace_lifecycle_log(
                        outcome.run_id or "api_get",
                        "http_get_workspace_config",
                        state_before="present",
                        state_after="invalid",
                        outcome="invalid",
                        path=outcome.path,
                    )
                    return HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "workspace config invalid on disk"}
                emit_workspace_lifecycle_log(
                    outcome.run_id or "api_get",
                    "http_get_workspace_config",
                    state_before="present",
                    state_after="served",
                    outcome="ok",
                    path=outcome.path,
                    location_key=(outcome.document.location_key if outcome.document else ""),
                )
                return HTTPStatus.OK, outcome.config
            if path == "/slack/oauth/status":
                oauth_outcome = slack_oauth_status_outcome()
                state = oauth_outcome.state
                public = state.to_public_dict() if state else {"status": oauth_outcome.status.value, "integration": "local-first"}
                return HTTPStatus.OK, {"ok": True, **public}
            if path == "/slack/oauth/security-approval":
                pending = slack_oauth_pending_security_approval_outcome()
                state = pending.state
                if not state or state.status != SlackOAuthInstallStatus.AWAITING_SECURITY_APPROVAL:
                    return HTTPStatus.NOT_FOUND, {"error": "no Slack token use awaiting Security approval"}
                return HTTPStatus.OK, {"ok": True, **state.to_public_dict()}
            if path == "/slack/channels":
                outcome = load_workspace_config_outcome()
                config = outcome.config if outcome.status == WorkspaceConfigLoadStatus.FOUND else None
                integration = "local-first"
                oauth_outcome = slack_oauth_status_outcome()
                if oauth_outcome.state and oauth_outcome.state.status == SlackOAuthInstallStatus.INSTALLED:
                    integration = "slack"
                elif outcome.document:
                    integration = outcome.document.integration
                elif config:
                    integration = (config.get("workspace") or {}).get("integration", "local-first")
                emit_workspace_lifecycle_log(
                    outcome.run_id or "api_get",
                    "http_get_slack_channels",
                    state_before=outcome.status.value,
                    state_after="projected",
                    outcome="ok" if config else "empty",
                    channel_count=len(slack_channels_view(config)),
                )
                channels = slack_channels_view(config)
                general_summary = general_channel_summary_stub() if config else ""
                return HTTPStatus.OK, {
                    "ok": True,
                    "integration": integration,
                    "general_summary": general_summary,
                    "channels": channels,
                }
            if path == "/dm":
                ws = load_workspace_config_outcome()
                if ws.status != WorkspaceConfigLoadStatus.FOUND or not ws.document:
                    return HTTPStatus.NOT_FOUND, {"error": "workspace config not found — sign in via Electron launcher"}
                threads = list_dm_threads_for_member(ws.document.member.user_id)
                total_unread = sum_dm_threads_unread(threads)
                notification_stub = format_dm_unread_notification_stub(total_unread)
                visor_rail_lines = format_dm_visor_rail_lines(threads)
                visor_rail = format_dm_visor_rail_text(threads)
                visor_scrollback_lines = format_dm_visor_scrollback_lines(threads)
                visor_scrollback = format_dm_visor_scrollback_text(threads)
                visor_compose = project_visor_compose_target(threads)
                visor_compose_picker = format_visor_compose_picker_text(threads)
                pending_approvals = [
                    serialize_approval(a) for a in self.service.pending_approvals()
                ]
                security_connector = project_security_connector_hud(pending_approvals)
                security_connector_picker = format_security_connector_picker_text(pending_approvals)
                security_connector_picker_huds = format_security_connector_picker_huds_text(
                    pending_approvals
                )
                comms_connector_stage = project_comms_connector_stage()
                return HTTPStatus.OK, {
                    "ok": True,
                    "threads": threads,
                    "total_unread_display": total_unread,
                    "notification_stub": notification_stub,
                    "visor_rail_lines": visor_rail_lines,
                    "visor_rail": visor_rail,
                    "visor_scrollback_lines": visor_scrollback_lines,
                    "visor_scrollback": visor_scrollback,
                    "visor_compose_agent_id": visor_compose["agent_id"] if visor_compose else None,
                    "visor_compose_text": visor_compose["text"] if visor_compose else None,
                    "visor_compose_hint": visor_compose["hint"] if visor_compose else None,
                    "visor_compose_picker": visor_compose_picker,
                    "security_connector_approval_id": (
                        security_connector["approval_id"] if security_connector else None
                    ),
                    "security_connector_hud": (
                        security_connector["hud"] if security_connector else None
                    ),
                    "security_connector_picker": security_connector_picker,
                    "security_connector_picker_huds": security_connector_picker_huds,
                    "comms_connector_stage_hud": comms_connector_stage["hud"],
                    "comms_connector_stage_intent": comms_connector_stage["intent"],
                    "comms_connector_stage_channel": comms_connector_stage["channel"],
                    "comms_connector_stage_text": comms_connector_stage["text"],
                }
            if len(parts) == 2 and parts[0] == "dm":
                agent_id = parts[1]
                read_outcome = dm_thread_read_outcome(agent_id)
                if read_outcome.status == DmThreadReadStatus.UNKNOWN_AGENT:
                    emit_workspace_lifecycle_log(
                        read_outcome.run_id or "api_get",
                        "http_get_dm_thread",
                        state_before="request",
                        state_after="rejected",
                        outcome="unknown_agent",
                        agent_id=agent_id,
                    )
                    return HTTPStatus.NOT_FOUND, {"error": read_outcome.error or f"unknown agent: {agent_id}"}
                if read_outcome.status == DmThreadReadStatus.NO_MEMBER:
                    emit_workspace_lifecycle_log(
                        read_outcome.run_id or "api_get",
                        "http_get_dm_thread",
                        state_before="missing",
                        state_after="skipped",
                        outcome="no_member",
                        agent_id=agent_id,
                    )
                    return HTTPStatus.NOT_FOUND, {"error": read_outcome.error or "workspace config not found"}
                if read_outcome.status == DmThreadReadStatus.INVALID_STORE:
                    emit_workspace_lifecycle_log(
                        read_outcome.run_id or "api_get",
                        "http_get_dm_thread",
                        state_before="invalid",
                        state_after="rejected",
                        outcome="invalid_store",
                        agent_id=agent_id,
                    )
                    return HTTPStatus.INTERNAL_SERVER_ERROR, {"error": read_outcome.error or "dm_threads invalid"}
                emit_workspace_lifecycle_log(
                    read_outcome.run_id or "api_get",
                    "http_get_dm_thread",
                    state_before="loaded",
                    state_after=read_outcome.status.value,
                    outcome="ok",
                    agent_id=agent_id,
                    message_count=read_outcome.message_count,
                )
                thread_row = read_outcome.thread or {}
                unread = compute_dm_thread_unread(thread_row) if thread_row else 0
                tts_speak = project_dm_tts_speak_json(read_outcome.agent_id or agent_id, thread_row)
                if tts_speak.get("status") == DmTtsSpeakStatus.READY.value:
                    emit_workspace_lifecycle_log(
                        read_outcome.run_id or "api_get",
                        "dm_tts_speak",
                        state_before="projected",
                        state_after=tts_speak["status"],
                        outcome="ok",
                        agent_id=read_outcome.agent_id or agent_id,
                        voice_slug=tts_speak.get("voice_slug", ""),
                    )
                return HTTPStatus.OK, {
                    "ok": True,
                    "status": read_outcome.status.value,
                    "agent_id": read_outcome.agent_id,
                    "message_count": read_outcome.message_count,
                    "unread_count": unread,
                    "unread_count_display": unread,
                    "thread": read_outcome.thread,
                    "tts_speak": tts_speak,
                }
            return HTTPStatus.NOT_FOUND, {"error": f"unknown route: {path}"}

    def post(
        self,
        path: str,
        payload: JSON,
        *,
        headers: dict[str, str] | None = None,
        raw_body: bytes | None = None,
        query: dict[str, str] | None = None,
    ) -> tuple[int, Any]:
        raw_tid, canonical_tid = self._resolve_request_tenant(headers=headers, query=query)
        if self._is_tenant_rejected(raw_tid, path):
            return HTTPStatus.NOT_FOUND, {
                "error": f"unknown tenant: {raw_tid}",
                "status": "unknown_tenant",
                "tenant": raw_tid,
            }
        with self._lock, tenant_context(canonical_tid):
            parts = [p for p in path.strip("/").split("/") if p]
            try:
                if path == "/tenants":
                    rec = parse_tenant_record(payload)
                    reg_path = resolve_tenants_registry_path(self.repo_root)
                    existing = load_tenants_registry(self.repo_root)
                    updated_rows = [r for r in existing if r.id != rec.id]
                    updated_rows.append(rec)
                    enforced = (
                        self.enforce_registry
                        if self.enforce_registry is not None
                        else tenant_registry_enforced(self.repo_root)
                    )
                    reg_path.parent.mkdir(parents=True, exist_ok=True)
                    reg_doc: JSON = {
                        "version": 1,
                        "tenants": [serialize_tenant_record(r) for r in updated_rows],
                    }
                    if enforced:
                        reg_doc["enforce_registry"] = True
                    reg_path.write_text(json.dumps(reg_doc, indent=2), encoding="utf-8")
                    ensure_tenant_state_root(rec.id, self.repo_root)
                    serialized = serialize_tenant_record(rec)
                    return HTTPStatus.CREATED, {"ok": True, "tenant": serialized, **serialized}

                if path == "/dispatch":
                    task = self.service.dispatch(
                        str(payload["agent_id"]),
                        str(payload["intent"]),
                        context=payload.get("context") or {},
                        created_by=str(payload.get("created_by") or "prag_chat"),
                    )
                    # Phase 2 seed: task dispatch surfaces as #eng channel activity.
                    increment_channel_unread("eng")
                    return HTTPStatus.CREATED, serialize_task(task)

                if path == "/agents/create":
                    agent_id = str(payload.get("agent_id") or "").strip()
                    name = str(payload.get("name") or "").strip()
                    role = str(payload.get("role") or "").strip()
                    autonomy = str(payload.get("autonomy") or "ask_approval").strip()
                    if not agent_id or not name:
                        return HTTPStatus.BAD_REQUEST, {"error": "agent_id and name are required"}
                    agent = self.service.register_custom_agent(agent_id, name=name, role=role, autonomy=autonomy)
                    return HTTPStatus.CREATED, serialize_agent(agent)

                if len(parts) == 3 and parts[0] == "tasks" and parts[2] in ("cancel", "interrupt"):
                    task_id = parts[1]
                    if task_id not in self.service.tasks:
                        return HTTPStatus.NOT_FOUND, {"error": f"unknown task: {task_id}"}
                    cancelled = self.service.cancel_task(task_id, reason=str(payload.get("reason") or "user_interrupted"))
                    return HTTPStatus.OK, serialize_task(cancelled)

                if path == "/social/route":
                    # R7: cross-office rumor / guard_report / handoff.
                    rumor = self.service.social.route(
                        text=str(payload.get("text") or ""),
                        from_office=str(payload.get("from_office") or "g5"),
                        to_office=str(payload.get("to_office") or "ci"),
                        from_agent_id=str(payload.get("from_agent_id") or "security"),
                        to_agent_id=(str(payload["to_agent_id"]) if payload.get("to_agent_id") else None),
                        kind=str(payload.get("kind") or "rumor"),
                    )
                    return HTTPStatus.CREATED, rumor.as_dict()

                if path == "/social/generate":
                    goal = str(payload.get("goal") or "").strip()
                    if not goal:
                        return HTTPStatus.BAD_REQUEST, {"error": "goal is required"}
                    platforms = payload.get("platforms")
                    tenant = str(payload.get("tenant") or "").strip() or current_tenant_id()
                    posts = self.service.social.generate_posts(
                        goal=goal,
                        platforms=platforms,
                        tenant=tenant,
                        agent_id="comms",
                    )
                    return HTTPStatus.CREATED, {
                        "ok": True,
                        "tenant": tenant,
                        "agent_id": "comms",
                        "goal": goal,
                        "posts": [p.as_dict() for p in posts],
                    }

                if path == "/social/approve":
                    action_id = str(payload.get("action_id") or "").strip()
                    if not action_id:
                        return HTTPStatus.BAD_REQUEST, {"error": "action_id is required"}
                    decided_by = str(payload.get("decided_by") or "carrington_director").strip()
                    post = self.service.social.approve_post(action_id, decided_by=decided_by)
                    if post is None:
                        return HTTPStatus.NOT_FOUND, {"error": f"social post not found: {action_id}"}

                    audit_entry = AuditEntry(
                        id=_id("aud"),
                        agent_id=post.agent_id,
                        connector="social",
                        action="post_message",
                        args={
                            "action_id": post.action_id,
                            "platform": post.platform,
                            "content": post.content,
                            "goal": post.goal,
                        },
                        autonomy=Autonomy.ASK_APPROVAL,
                        human=True,
                        result="posted",
                    )
                    self.service.gateway.audit.append(audit_entry)
                    return HTTPStatus.OK, {
                        "ok": True,
                        "status": "posted",
                        "action_id": action_id,
                        "post": post.as_dict(),
                        "decided_by": decided_by,
                    }

                if len(parts) == 3 and parts[0] == "tasks" and parts[2] == "perform":
                    task = self.service.tasks[parts[1]]
                    actions = payload.get("actions") or []
                    if not isinstance(actions, list):
                        return HTTPStatus.BAD_REQUEST, {"error": "actions must be a list"}
                    updated = self.service.perform(task, actions)  # type: ignore[arg-type]
                    return HTTPStatus.OK, serialize_task(updated)

                if len(parts) == 3 and parts[0] == "approvals" and parts[2] in ("approve", "deny"):
                    decided_by = str(payload.get("decided_by") or "prag_chat")
                    if parts[2] == "approve":
                        task = self.service.approve(parts[1], decided_by=decided_by)
                    else:
                        task = self.service.deny(parts[1], decided_by=decided_by)
                    return HTTPStatus.OK, serialize_task(task)

                if path == "/slack/ingest":
                    return HTTPStatus.CREATED, serialize_event(self.service.ingest_slack(payload))

                if path == "/slack/events":
                    events_outcome = slack_events_ingest_outcome(
                        payload,
                        headers=headers,
                        raw_body=raw_body,
                    )
                    if events_outcome.status == SlackEventsIngestStatus.SIGNATURE_INVALID:
                        return HTTPStatus.UNAUTHORIZED, {"error": events_outcome.error or "invalid signature"}
                    if events_outcome.status == SlackEventsIngestStatus.VALIDATION_ERROR:
                        return HTTPStatus.BAD_REQUEST, {"error": events_outcome.error or "validation failed"}
                    if events_outcome.status == SlackEventsIngestStatus.CHALLENGE:
                        return HTTPStatus.OK, {
                            "ok": True,
                            "status": events_outcome.status.value,
                            "challenge": events_outcome.challenge,
                        }
                    if events_outcome.status == SlackEventsIngestStatus.INGESTED:
                        message = events_outcome.normalized_message or {}
                        event = self.service.ingest_slack(message)
                        return HTTPStatus.CREATED, {
                            "ok": True,
                            "status": events_outcome.status.value,
                            "event": serialize_event(event),
                            "message": message,
                        }
                    return HTTPStatus.OK, {
                        "ok": True,
                        "status": events_outcome.status.value,
                    }

                if path == "/slack/outbound/post":
                    post_outcome = slack_outbound_post_outcome(
                        channel=str(payload.get("channel") or ""),
                        text=str(payload.get("text") or ""),
                    )
                    if post_outcome.status == SlackOutboundPostStatus.VALIDATION_ERROR:
                        return HTTPStatus.BAD_REQUEST, {"error": post_outcome.error or "validation failed"}
                    if post_outcome.status == SlackOutboundPostStatus.NOT_INSTALLED:
                        return HTTPStatus.CONFLICT, {
                            "ok": False,
                            "status": post_outcome.status.value,
                            "error": post_outcome.error or "bot token not installed",
                        }
                    if post_outcome.status == SlackOutboundPostStatus.API_ERROR:
                        return HTTPStatus.BAD_GATEWAY, {
                            "ok": False,
                            "status": post_outcome.status.value,
                            "error": post_outcome.error or "chat.postMessage failed",
                        }
                    return HTTPStatus.CREATED, {
                        "ok": True,
                        "status": post_outcome.status.value,
                        "channel": post_outcome.channel,
                        "text": post_outcome.text,
                        "slack_ts": post_outcome.slack_ts,
                    }

                if path == "/slack/oauth/begin":
                    begin_outcome = slack_oauth_begin_install_outcome(
                        redirect_uri=str(payload.get("redirect_uri") or "").strip() or None,
                    )
                    if begin_outcome.status == SlackOAuthBeginStatus.ALREADY_INSTALLED:
                        return HTTPStatus.CONFLICT, {"error": begin_outcome.error or "already installed"}
                    if begin_outcome.status == SlackOAuthBeginStatus.INVALID:
                        return HTTPStatus.INTERNAL_SERVER_ERROR, {"error": begin_outcome.error or "invalid oauth store"}
                    return HTTPStatus.OK, {
                        "ok": True,
                        "status": begin_outcome.status.value,
                        "authorization_url": begin_outcome.authorization_url,
                        "state": begin_outcome.state,
                    }

                if path == "/slack/oauth/callback":
                    complete_outcome = slack_oauth_complete_install_outcome(
                        code=str(payload.get("code") or ""),
                        state=str(payload.get("state") or ""),
                    )
                    if complete_outcome.status == SlackOAuthCompleteStatus.VALIDATION_ERROR:
                        return HTTPStatus.BAD_REQUEST, {"error": complete_outcome.error or "validation failed"}
                    if complete_outcome.status == SlackOAuthCompleteStatus.NOT_PENDING:
                        return HTTPStatus.CONFLICT, {"error": complete_outcome.error or "not pending"}
                    if complete_outcome.status == SlackOAuthCompleteStatus.PENDING_MISMATCH:
                        return HTTPStatus.BAD_REQUEST, {"error": complete_outcome.error or "state mismatch"}
                    if complete_outcome.status == SlackOAuthCompleteStatus.AWAITING_SECURITY_APPROVAL:
                        install = complete_outcome.install
                        return HTTPStatus.ACCEPTED, {
                            "ok": True,
                            "status": complete_outcome.status.value,
                            "install": install.to_public_dict() if install else None,
                        }
                    if complete_outcome.status == SlackOAuthCompleteStatus.TOKEN_EXCHANGE_FAILED:
                        return HTTPStatus.BAD_GATEWAY, {"error": complete_outcome.error or "token exchange failed"}
                    if complete_outcome.status == SlackOAuthCompleteStatus.INVALID:
                        return HTTPStatus.INTERNAL_SERVER_ERROR, {"error": complete_outcome.error or "invalid oauth store"}
                    install = complete_outcome.install
                    return HTTPStatus.OK, {
                        "ok": True,
                        "status": complete_outcome.status.value,
                        "install": install.to_public_dict() if install else None,
                    }

                if path == "/slack/oauth/disconnect":
                    disconnect_outcome = slack_oauth_disconnect_outcome()
                    if disconnect_outcome.status == SlackOAuthDisconnectStatus.NOT_INSTALLED:
                        return HTTPStatus.NOT_FOUND, {"error": disconnect_outcome.error or "not installed"}
                    if disconnect_outcome.status == SlackOAuthDisconnectStatus.INVALID:
                        return HTTPStatus.INTERNAL_SERVER_ERROR, {"error": disconnect_outcome.error or "invalid oauth store"}
                    return HTTPStatus.OK, {
                        "ok": True,
                        "status": disconnect_outcome.status.value,
                    }

                if path == "/slack/oauth/security-approval/approve":
                    approve_outcome = slack_oauth_approve_security_outcome(
                        approval_id=str(payload.get("approval_id") or ""),
                        decided_by=str(payload.get("decided_by") or "human"),
                    )
                    if approve_outcome.status == SlackOAuthCompleteStatus.VALIDATION_ERROR:
                        return HTTPStatus.BAD_REQUEST, {"error": approve_outcome.error or "validation failed"}
                    if approve_outcome.status in (
                        SlackOAuthCompleteStatus.NOT_PENDING,
                        SlackOAuthCompleteStatus.PENDING_MISMATCH,
                    ):
                        return HTTPStatus.CONFLICT, {"error": approve_outcome.error or "not awaiting approval"}
                    if approve_outcome.status == SlackOAuthCompleteStatus.TOKEN_EXCHANGE_FAILED:
                        return HTTPStatus.BAD_GATEWAY, {"error": approve_outcome.error or "token exchange failed"}
                    if approve_outcome.status == SlackOAuthCompleteStatus.INVALID:
                        return HTTPStatus.INTERNAL_SERVER_ERROR, {"error": approve_outcome.error or "invalid oauth store"}
                    install = approve_outcome.install
                    return HTTPStatus.OK, {
                        "ok": True,
                        "status": approve_outcome.status.value,
                        "install": install.to_public_dict() if install else None,
                    }

                if path == "/slack/oauth/security-approval/deny":
                    deny_outcome = slack_oauth_deny_security_outcome(
                        approval_id=str(payload.get("approval_id") or ""),
                        decided_by=str(payload.get("decided_by") or "human"),
                    )
                    if deny_outcome.status == SlackOAuthDenySecurityStatus.INVALID:
                        return HTTPStatus.BAD_REQUEST, {"error": deny_outcome.error or "validation failed"}
                    if deny_outcome.status in (
                        SlackOAuthDenySecurityStatus.NOT_AWAITING,
                        SlackOAuthDenySecurityStatus.APPROVAL_MISMATCH,
                    ):
                        return HTTPStatus.CONFLICT, {"error": deny_outcome.error or "not awaiting approval"}
                    return HTTPStatus.OK, {
                        "ok": True,
                        "status": deny_outcome.status.value,
                    }

                if path == "/workspace/config":
                    outcome = merge_workspace_config_outcome(payload)
                    if outcome.status == WorkspaceConfigMergeStatus.VALIDATION_ERROR:
                        emit_workspace_lifecycle_log(
                            outcome.run_id or "api_post",
                            "http_post_workspace_config",
                            state_before="unknown",
                            state_after="rejected",
                            outcome="validation_error",
                            error_type="ValueError",
                        )
                        return HTTPStatus.BAD_REQUEST, {"error": outcome.error or "validation failed"}
                    config = outcome.config or {}
                    emit_workspace_lifecycle_log(
                        outcome.run_id or "api_post",
                        "http_post_workspace_config",
                        state_before="unknown",
                        state_after="persisted",
                        outcome="ok",
                        location_key=(config.get("workspace") or {}).get("location_key", ""),
                        member_user_id=(config.get("member") or {}).get("user_id", ""),
                        location_changed=outcome.location_changed,
                    )
                    return HTTPStatus.OK, config

                if len(parts) == 4 and parts[0] == "slack" and parts[1] == "channels" and parts[3] == "read":
                    channel_id = parts[2]
                    read_outcome = mark_channel_read_outcome(channel_id)
                    if read_outcome.status == ChannelMarkReadStatus.NO_CONFIG:
                        emit_workspace_lifecycle_log(
                            read_outcome.run_id or "api_post",
                            "http_post_slack_channel_read",
                            state_before="missing",
                            state_after="skipped",
                            outcome="no_config",
                            channel_id=channel_id,
                        )
                        return HTTPStatus.NOT_FOUND, {"error": read_outcome.error or "workspace config not found"}
                    if read_outcome.status == ChannelMarkReadStatus.NOT_FOUND:
                        emit_workspace_lifecycle_log(
                            read_outcome.run_id or "api_post",
                            "http_post_slack_channel_read",
                            state_before="loaded",
                            state_after="missing_channel",
                            outcome="not_found",
                            channel_id=channel_id,
                        )
                        return HTTPStatus.NOT_FOUND, {"error": read_outcome.error or "channel not found"}
                    emit_workspace_lifecycle_log(
                        read_outcome.run_id or "api_post",
                        "http_post_slack_channel_read",
                        state_before="loaded",
                        state_after="marked",
                        outcome="ok",
                        channel_id=channel_id,
                        unread_count=0,
                    )
                    return HTTPStatus.OK, {
                        "ok": True,
                        "status": read_outcome.status.value,
                        "channel_id": read_outcome.channel_id,
                        "unread_count_display": read_outcome.unread_count,
                    }

                if len(parts) == 3 and parts[0] == "dm" and parts[2] == "message":
                    return self._post_dm_message(parts[1], payload)

                if len(parts) == 3 and parts[0] == "dm" and parts[2] == "read":
                    agent_id = parts[1]
                    mark_outcome = dm_thread_mark_read_outcome(agent_id)
                    if mark_outcome.status == DmThreadMarkReadStatus.UNKNOWN_AGENT:
                        emit_workspace_lifecycle_log(
                            mark_outcome.run_id or "api_post",
                            "http_post_dm_mark_read",
                            state_before="request",
                            state_after="rejected",
                            outcome="unknown_agent",
                            agent_id=agent_id,
                        )
                        return HTTPStatus.NOT_FOUND, {"error": mark_outcome.error or f"unknown agent: {agent_id}"}
                    if mark_outcome.status == DmThreadMarkReadStatus.NO_MEMBER:
                        emit_workspace_lifecycle_log(
                            mark_outcome.run_id or "api_post",
                            "http_post_dm_mark_read",
                            state_before="missing",
                            state_after="skipped",
                            outcome="no_member",
                            agent_id=agent_id,
                        )
                        return HTTPStatus.NOT_FOUND, {"error": mark_outcome.error or "workspace config not found"}
                    if mark_outcome.status == DmThreadMarkReadStatus.NOT_FOUND:
                        emit_workspace_lifecycle_log(
                            mark_outcome.run_id or "api_post",
                            "http_post_dm_mark_read",
                            state_before="loaded",
                            state_after="missing_thread",
                            outcome="not_found",
                            agent_id=agent_id,
                        )
                        return HTTPStatus.NOT_FOUND, {"error": mark_outcome.error or "dm thread not found"}
                    if mark_outcome.status == DmThreadMarkReadStatus.INVALID_STORE:
                        emit_workspace_lifecycle_log(
                            mark_outcome.run_id or "api_post",
                            "http_post_dm_mark_read",
                            state_before="invalid",
                            state_after="rejected",
                            outcome="invalid_store",
                            agent_id=agent_id,
                        )
                        return HTTPStatus.INTERNAL_SERVER_ERROR, {"error": mark_outcome.error or "dm_threads invalid"}
                    emit_workspace_lifecycle_log(
                        mark_outcome.run_id or "api_post",
                        "http_post_dm_mark_read",
                        state_before="loaded",
                        state_after="marked",
                        outcome="ok",
                        agent_id=agent_id,
                        unread_count=0,
                    )
                    return HTTPStatus.OK, {
                        "ok": True,
                        "status": mark_outcome.status.value,
                        "agent_id": mark_outcome.agent_id,
                        "unread_count_display": mark_outcome.unread_count,
                        "thread": mark_outcome.thread,
                    }

                if len(parts) == 2 and parts[0] == "dm" and parts[1] in VALID_AGENT_IDS:
                    return self._post_dm_message(parts[1], payload)

                if path == "/dm/walk-up":
                    request = parse_walk_up_dm_append_request(payload)
                    if request is None:
                        return HTTPStatus.BAD_REQUEST, {"error": "invalid walk-up dm request"}
                    
                    # Semantic Spatial Voice Command & Intent Routing Execution (Pillar 3 & v2.0)
                    from .director_bridge import parse_semantic_voice_intent
                    intent_outcome = parse_semantic_voice_intent(request.text)
                    voice_action_result = None
                    if intent_outcome is not None:
                        if intent_outcome.action == "multi_dispatch":
                            dispatched_tasks = []
                            for target_agent, intent in zip(intent_outcome.target_agents, intent_outcome.intents):
                                t = self.service.dispatch(target_agent, intent, created_by="spatial_voice")
                                dispatched_tasks.append({"agent_id": target_agent, "task_id": t.id})
                            voice_action_result = {"action": "multi_dispatch", "dispatches": dispatched_tasks}
                        elif intent_outcome.action == "dispatch" and intent_outcome.target_agents:
                            target_agent = intent_outcome.target_agents[0]
                            intent = intent_outcome.intents[0] if intent_outcome.intents else "General task"
                            task = self.service.dispatch(target_agent, intent, created_by="spatial_voice")
                            voice_action_result = {"action": "dispatch", "task_id": task.id, "target_agent": target_agent}
                        elif intent_outcome.action == "create_agent" and intent_outcome.target_agents:
                            target_agent = intent_outcome.target_agents[0]
                            role = intent_outcome.intents[0] if intent_outcome.intents else "General"
                            agent = self.service.register_custom_agent(target_agent, target_agent.capitalize(), role=role)
                            voice_action_result = {"action": "create_agent", "agent_id": agent.id}
                        elif intent_outcome.action == "cancel_task" and intent_outcome.target_agents:
                            target_agent = intent_outcome.target_agents[0]
                            target_task = None
                            for t in self.service.tasks.values():
                                if t.agent_id == target_agent and t.status in ("running", "queued", "awaiting_approval"):
                                    target_task = t
                                    break
                            if target_task:
                                self.service.cancel_task(target_task.id, reason="cancelled_via_voice")
                                voice_action_result = {"action": "cancel_task", "task_id": target_task.id}

                    hud_outcome = walk_up_dm_hud_outcome(request)
                    if hud_outcome.status.value in ("unknown_agent",):
                        return HTTPStatus.NOT_FOUND, {"error": hud_outcome.error or "unknown agent"}
                    if hud_outcome.status.value in ("no_member",):
                        return HTTPStatus.NOT_FOUND, {"error": hud_outcome.error or "no member"}
                    if hud_outcome.status.value in ("validation_error",):
                        return HTTPStatus.BAD_REQUEST, {"error": hud_outcome.error or "validation failed"}
                    append = hud_outcome.append_outcome
                    if append and append.status == DmThreadAppendStatus.APPENDED:
                        event = Event.new(
                            "dm.message",
                            {
                                "agent_id": append.agent_id,
                                "thread_id": (append.thread or {}).get("id", ""),
                                "from": append.appended_from,
                                "message_count": append.message_count,
                                "stub_reply": append.stub_reply,
                                "director_live": append.director_live,
                                "source": request.source,
                            },
                            source=request.source,
                            target=append.agent_id,
                        )
                        self.service.bus.publish(event)
                    res_body = {
                        "ok": True,
                        "status": hud_outcome.status.value,
                        "agent_id": hud_outcome.agent_id,
                        "hud_text": hud_outcome.hud_text,
                        "message_count": hud_outcome.message_count,
                        "director_live": bool(
                            append and append.director_live
                        ),
                        "spatial_tts": hud_outcome.spatial_tts,
                        "thread": append.thread if append else None,
                    }
                    if voice_action_result:
                        res_body["voice_action"] = voice_action_result
                    return HTTPStatus.OK, res_body

                if path == "/events":
                    event_type = str(payload["type"])
                    event_payload = payload.get("payload") or {}
                    event = Event.new(
                        event_type,
                        event_payload if isinstance(event_payload, dict) else {},
                        source=str(payload.get("source") or "prag_chat"),
                        target=str(payload.get("target") or ""),
                    )
                    published = serialize_event(self.service.bus.publish(event))
                    activity = channel_activity_from_event_outcome(event_type, event_payload)
                    if activity.status == ChannelActivityStatus.SKIPPED:
                        return HTTPStatus.CREATED, published
                    published["channel_activity"] = {
                        "status": activity.status.value,
                        "channel_id": activity.channel_id,
                        "unread_count": activity.unread_count,
                        "delta": activity.delta,
                    }
                    return HTTPStatus.CREATED, published

                if path == "/hermes/decompose":
                    goal = str(payload.get("goal") or "")
                    if not goal:
                        return HTTPStatus.BAD_REQUEST, {"error": "missing goal in payload"}
                    result = self.service.hermes_director.decompose_goal(goal)
                    return HTTPStatus.OK, result

                if path == "/hermes/supervise":
                    result = self.service.hermes_director.evaluate_swarm_lifecycle()
                    return HTTPStatus.OK, result

                if path == "/hermes/autopilot":
                    enabled = bool(payload.get("enabled", True))
                    self.service.hermes_director.autopilot_enabled = enabled
                    return HTTPStatus.OK, {"ok": True, "autopilot_enabled": enabled}

            except KeyError as exc:
                return HTTPStatus.BAD_REQUEST, {"error": f"missing or unknown key: {exc}"}
            except ValueError as exc:
                return HTTPStatus.BAD_REQUEST, {"error": str(exc)}
            except Exception as exc:  # noqa: BLE001 - API must surface errors as JSON
                import traceback
                traceback.print_exc()
                return HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)}
            return HTTPStatus.NOT_FOUND, {"error": f"unknown route: {path}"}

    def _post_dm_message(self, agent_id: str, payload: JSON) -> tuple[int, Any]:
        """Append walk-up DM line; publish dm.message event on success."""
        append_outcome = dm_thread_append_outcome(
            agent_id,
            from_role=str(payload.get("from") or "human"),
            text=str(payload.get("text") or ""),
            stub_reply=bool(payload.get("stub_reply", True)),
        )
        if append_outcome.status == DmThreadAppendStatus.UNKNOWN_AGENT:
            emit_workspace_lifecycle_log(
                append_outcome.run_id or "api_post",
                "http_post_dm_message",
                state_before="request",
                state_after="rejected",
                outcome="unknown_agent",
                agent_id=agent_id,
            )
            return HTTPStatus.NOT_FOUND, {"error": append_outcome.error or f"unknown agent: {agent_id}"}
        if append_outcome.status == DmThreadAppendStatus.VALIDATION_ERROR:
            emit_workspace_lifecycle_log(
                append_outcome.run_id or "api_post",
                "http_post_dm_message",
                state_before="request",
                state_after="rejected",
                outcome="validation_error",
                agent_id=agent_id,
            )
            return HTTPStatus.BAD_REQUEST, {"error": append_outcome.error or "validation failed"}
        if append_outcome.status == DmThreadAppendStatus.NO_MEMBER:
            emit_workspace_lifecycle_log(
                append_outcome.run_id or "api_post",
                "http_post_dm_message",
                state_before="missing",
                state_after="skipped",
                outcome="no_member",
                agent_id=agent_id,
            )
            return HTTPStatus.NOT_FOUND, {"error": append_outcome.error or "workspace config not found"}
        if append_outcome.status == DmThreadAppendStatus.INVALID_STORE:
            emit_workspace_lifecycle_log(
                append_outcome.run_id or "api_post",
                "http_post_dm_message",
                state_before="invalid",
                state_after="rejected",
                outcome="invalid_store",
                agent_id=agent_id,
            )
            return HTTPStatus.INTERNAL_SERVER_ERROR, {"error": append_outcome.error or "dm_threads invalid"}

        event = Event.new(
            "dm.message",
            {
                "agent_id": append_outcome.agent_id,
                "thread_id": (append_outcome.thread or {}).get("id", ""),
                "from": append_outcome.appended_from,
                "message_count": append_outcome.message_count,
                "stub_reply": append_outcome.stub_reply,
            },
            source=str(payload.get("source") or "walk_up"),
            target=append_outcome.agent_id,
        )
        self.service.bus.publish(event)

        emit_workspace_lifecycle_log(
            append_outcome.run_id or "api_post",
            "http_post_dm_message",
            state_before="loaded",
            state_after="appended",
            outcome="ok",
            agent_id=append_outcome.agent_id,
            message_count=append_outcome.message_count,
            stub_reply=append_outcome.stub_reply,
        )
        thread_row = append_outcome.thread or {}
        tts_speak = project_dm_tts_speak_json(append_outcome.agent_id or agent_id, thread_row)
        if tts_speak.get("status") == DmTtsSpeakStatus.READY.value:
            emit_workspace_lifecycle_log(
                append_outcome.run_id or "api_post",
                "dm_tts_speak",
                state_before="projected",
                state_after=tts_speak["status"],
                outcome="ok",
                agent_id=append_outcome.agent_id or agent_id,
                voice_slug=tts_speak.get("voice_slug", ""),
            )
        return HTTPStatus.CREATED, {
            "ok": True,
            "status": append_outcome.status.value,
            "agent_id": append_outcome.agent_id,
            "message_count": append_outcome.message_count,
            "stub_reply": append_outcome.stub_reply,
            "director_live": append_outcome.director_live,
            "thread": append_outcome.thread,
            "tts_speak": tts_speak,
        }


def make_handler(api: OfficeServiceAPI) -> type[BaseHTTPRequestHandler]:
    """Create a request handler bound to an OfficeServiceAPI instance."""

    class Handler(BaseHTTPRequestHandler):
        server_version = "VirtualAgentOfficeAPI/0.1"

        def _send_json(self, status: int, payload: Any) -> None:
            data = json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
            self.send_response(int(status))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", _CORS_ALLOW_HEADERS)
            self.end_headers()
            self.wfile.write(data)

        def _send_html(self, status: int, body: str, content_type: str = "text/html; charset=utf-8") -> None:
            data = body.encode("utf-8")
            self.send_response(int(status))
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", _CORS_ALLOW_HEADERS)
            self.end_headers()
            self.wfile.write(data)

        def _send_empty(self, status: int) -> None:
            self.send_response(int(status))
            self.send_header("Content-Length", "0")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", _CORS_ALLOW_HEADERS)
            self.end_headers()

        def _tenant_id_for_request(self, query: dict[str, str] | None = None) -> str:
            header_map = {str(k): str(v) for k, v in self.headers.items()}
            return tenant_from_headers_and_query(header_map, query)

        def do_OPTIONS(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            self._send_empty(HTTPStatus.NO_CONTENT)

        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            parsed = urlparse(self.path)
            query = {key: values[0] for key, values in parse_qs(parsed.query).items() if values}
            header_map = {str(k): str(v) for k, v in self.headers.items()}
            with tenant_context(self._tenant_id_for_request(query)):
                result = api.get(parsed.path, query=query, headers=header_map)
            if isinstance(result, HtmlResponse):
                self._send_html(result.status, result.body, result.content_type)
                return
            status, payload = result
            self._send_json(status, payload)

        def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            length = int(self.headers.get("Content-Length") or "0")
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": f"invalid json: {exc}"})
                return
            if not isinstance(payload, dict):
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "request body must be an object"})
                return
            header_map = {str(k): str(v) for k, v in self.headers.items()}
            parsed = urlparse(self.path)
            query = {key: values[0] for key, values in parse_qs(parsed.query).items() if values}
            with tenant_context(self._tenant_id_for_request(query)):
                status, response = api.post(
                    parsed.path,
                    payload,
                    headers=header_map,
                    raw_body=raw,
                    query=query,
                )
            self._send_json(status, response)

        def log_message(self, fmt: str, *args: Any) -> None:
            # Keep server logs parseable and compact for launch-script tails.
            print(f"[office-api] {self.address_string()} {fmt % args}")

    return Handler


def run_server(
    service: OfficeService | OfficeServiceAPI | None = None,
    host: str = "127.0.0.1",
    port: int = 8791,
    repo_root: str | None = None,
) -> ThreadingHTTPServer:
    if isinstance(service, OfficeServiceAPI):
        api = service
    elif isinstance(service, OfficeService):
        api = OfficeServiceAPI(service, repo_root=repo_root)
    else:
        api = OfficeServiceAPI(repo_root=repo_root)
    server = ThreadingHTTPServer((host, port), make_handler(api))
    print(f"Virtual Agent Office API listening on http://{host}:{port}")
    server.serve_forever()
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Virtual Agent Office host API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8791)
    args = parser.parse_args(argv)
    run_server(create_default_service(reload_persisted=True), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
