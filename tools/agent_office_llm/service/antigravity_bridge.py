"""Antigravity Active Live Agent Attachment Bridge for Virtual Agent Office.

Discovers active and recent Antigravity conversations from:
  1. Antigravity LanguageServerService Connect-RPC (`GetStatus` / `SearchConversations`)
  2. `~/.gemini/antigravity/conversation_summaries.db` (`conversation_summaries` table)
  3. `~/.gemini/antigravity/brain/<cascade_id>/.system_generated/logs/transcript.jsonl`

Attaches up to 8 live Antigravity sessions (plus active subagent counts) onto the 8
embodied Virtual Agent Office desks (`director` 0x31 .. `comms` 0x38) and projects
their real-time step counts, titles, and tool actions onto OfficeService monitors,
Perfect Menu text, walk-up DM replies, and the 3D engine's `/api/llm/act` billboards.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import ssl
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

DESK_ORDER: tuple[tuple[str, str, int], ...] = (
    ("director", "Director", 0x31),
    ("orchestrator", "Orchestrator", 0x32),
    ("research", "Research", 0x33),
    ("code", "Code", 0x34),
    ("qa", "QA", 0x35),
    ("security", "Security", 0x36),
    ("ops", "Ops", 0x37),
    ("comms", "Comms", 0x38),
)

_CACHED_LS_INFO: dict[str, Any] | None = None


def _default_summaries_db_path() -> Path:
    env_override = os.environ.get("ANTIGRAVITY_SUMMARIES_DB", "").strip()
    if env_override:
        return Path(env_override)
    return Path(os.path.expanduser("~/.gemini/antigravity/conversation_summaries.db"))


def _default_brain_dirs() -> list[Path]:
    env_override = os.environ.get("ANTIGRAVITY_BRAIN_DIR", "").strip()
    if env_override:
        return [Path(env_override)]
    return [
        Path(os.path.expanduser("~/.gemini/antigravity/brain")),
        Path(os.path.expanduser("~/.gemini/antigravity-cli/brain")),
    ]


def test_connect_port(port: int, csrf_token: str, timeout: float = 1.2) -> bool:
    """Verify whether `port` responds to Antigravity LanguageServerService Connect-RPC."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    headers = {
        "Content-Type": "application/json",
        "x-codeium-csrf-token": csrf_token,
        "Connect-Protocol-Version": "1",
    }
    for method in ("GetStatus", "GetAuthStatus"):
        url = f"https://127.0.0.1:{port}/exa.language_server_pb.LanguageServerService/{method}"
        req = urllib.request.Request(url, data=b"{}", headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                if resp.status == 200:
                    return True
        except Exception as exc:
            _ = exc
            continue
    return False


def discover_language_server_info(force_refresh: bool = False) -> dict[str, Any] | None:
    """Discover the running Antigravity `language_server` PID, HTTPS port, and CSRF token."""
    global _CACHED_LS_INFO
    if os.environ.get("ANTIGRAVITY_DISABLE_LS_PROBE") == "1":
        return None
    if _CACHED_LS_INFO and not force_refresh:
        if test_connect_port(int(_CACHED_LS_INFO["port"]), str(_CACHED_LS_INFO["csrf_token"])):
            return dict(_CACHED_LS_INFO)

    try:
        out = subprocess.check_output(["ps", "-eo", "pid,args"], text=True, timeout=2.5)
        for line in out.splitlines():
            if "language_server" not in line or "--csrf_token" not in line or "grep" in line:
                continue
            parts = line.strip().split()
            if not parts:
                continue
            pid = parts[0]
            m = re.search(r"--csrf_token(?:=|\s+)([^\s]+)", line)
            csrf_token = m.group(1) if m else ""
            if not csrf_token:
                continue
            try:
                lsof_out = subprocess.check_output(
                    ["lsof", "-a", "-p", pid, "-iTCP", "-sTCP:LISTEN", "-P"],
                    text=True,
                    timeout=2.5,
                )
                ports = [int(p) for p in re.findall(r":(\d+)\s+\(LISTEN\)", lsof_out)]
                for port in ports:
                    if test_connect_port(port, csrf_token):
                        _CACHED_LS_INFO = {
                            "pid": int(pid),
                            "port": int(port),
                            "csrf_token": csrf_token,
                            "connected": True,
                        }
                        return dict(_CACHED_LS_INFO)
            except Exception as exc:
                sys.stderr.write(f"WARN: antigravity_bridge lsof probe error: {exc}\n")
    except Exception as exc:
        sys.stderr.write(f"WARN: antigravity_bridge ps probe error: {exc}\n")
    return None


def call_ls_rpc(
    method: str,
    payload: dict[str, Any],
    ls_info: dict[str, Any] | None = None,
    timeout: float = 2.0,
) -> dict[str, Any] | None:
    """Invoke a Connect-RPC method on the local Antigravity LanguageServerService."""
    info = ls_info if ls_info is not None else discover_language_server_info()
    if not info or not info.get("port") or not info.get("csrf_token"):
        return None
    url = f"https://127.0.0.1:{info['port']}/exa.language_server_pb.LanguageServerService/{method}"
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    headers = {
        "Content-Type": "application/json",
        "x-codeium-csrf-token": str(info["csrf_token"]),
        "Connect-Protocol-Version": "1",
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read().decode("utf-8", errors="ignore").strip()
            return json.loads(raw) if raw else {}
    except Exception as exc:
        sys.stderr.write(f"WARN: antigravity_bridge RPC {method} error: {exc}\n")
        return None


def _extract_transcript_tail_telemetry(
    cascade_id: str,
    brain_dirs: list[Path],
    initial_step_count: int = 0,
) -> tuple[int, str, str]:
    """Read the tail of `transcript.jsonl` for `cascade_id`.

    Returns `(step_count, last_tool_action, last_step_type)`.
    """
    step_count = int(initial_step_count or 0)
    last_tool_action = ""
    last_step_type = ""
    for bdir in brain_dirs:
        tpath = bdir / cascade_id / ".system_generated" / "logs" / "transcript.jsonl"
        if not tpath.is_file():
            continue
        try:
            with open(tpath, "rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                f.seek(max(0, size - 24576), os.SEEK_SET)
                tail_bytes = f.read()
            lines = tail_bytes.decode("utf-8", errors="ignore").splitlines()
            for ln in reversed(lines):
                raw = ln.strip()
                if not raw or not raw.startswith("{"):
                    continue
                try:
                    obj = json.loads(raw)
                except Exception as parse_exc:
                    _ = parse_exc
                    continue
                step_count = max(step_count, int(obj.get("step_index") or 0))
                if not last_step_type:
                    last_step_type = str(obj.get("type") or "")
                tcs = obj.get("tool_calls") or []
                if tcs and not last_tool_action:
                    tc = tcs[-1]
                    if isinstance(tc, dict):
                        args = tc.get("arguments") or {}
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except Exception as arg_exc:
                                _ = arg_exc
                                args = {}
                        if isinstance(args, dict):
                            last_tool_action = str(
                                args.get("toolAction")
                                or args.get("toolSummary")
                                or tc.get("name")
                                or ""
                            ).strip()
                        else:
                            last_tool_action = str(tc.get("name") or "").strip()
                if last_tool_action:
                    break
        except Exception as exc:
            sys.stderr.write(f"WARN: antigravity_bridge transcript read error for {cascade_id[:8]}: {exc}\n")
        break
    return step_count, last_tool_action, last_step_type


def format_live_agent_billboard(agent_entry: dict[str, Any]) -> str:
    """Format a concise 3D HUD / billboard string for an attached Antigravity live agent."""
    short_id = str(agent_entry.get("short_id") or agent_entry.get("cascade_id", "")[:8] or "agy")
    title = str(agent_entry.get("title") or "Live Agent").strip()
    if len(title) > 34:
        title = title[:31].rstrip() + "..."
    step_count = int(agent_entry.get("step_count") or 0)
    subagents = int(agent_entry.get("active_subagent_count") or 0)
    action = str(agent_entry.get("last_tool_action") or "").strip()
    if len(action) > 28:
        action = action[:25].rstrip() + "..."
    state_tag = "RUN" if agent_entry.get("is_running") else "IDLE"
    sub_tag = f"+{subagents}sub" if subagents > 0 else ""
    base = f"[AGY {short_id} {state_tag}{sub_tag}] {title} (s{step_count})"
    if action:
        return f"{base}: {action}"[:120]
    return base[:120]


def discover_antigravity_live_agents(
    *,
    limit: int = 8,
    summaries_db_path: str | Path | None = None,
    brain_dir: str | Path | None = None,
    ls_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Discover active and recent Antigravity live agents on this host."""
    db_path = Path(summaries_db_path) if summaries_db_path is not None else _default_summaries_db_path()
    brain_dirs = [Path(brain_dir)] if brain_dir is not None else _default_brain_dirs()
    resolved_ls = ls_info if ls_info is not None else discover_language_server_info()

    rpc_by_id: dict[str, dict[str, Any]] = {}
    if resolved_ls and resolved_ls.get("connected", True) and summaries_db_path is None:
        search_res = call_ls_rpc("SearchConversations", {}, ls_info=resolved_ls)
        if isinstance(search_res, dict):
            for item in search_res.get("results") or []:
                if isinstance(item, dict):
                    cid = str(item.get("cascadeId") or "").strip()
                    if cid:
                        rpc_by_id[cid] = item

    rows_by_id: dict[str, dict[str, Any]] = {}
    active_subagents_by_parent: dict[str, list[dict[str, Any]]] = {}
    if db_path.is_file():
        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT conversation_id, title, preview, step_count, last_modified_time, "
                "workspace_uris, status, project_id, agent_name, parent_conversation_id, "
                "nesting_depth, not_fully_idle, killed "
                "FROM conversation_summaries "
                "WHERE COALESCE(killed, 0) = 0 "
                "ORDER BY COALESCE(not_fully_idle, 0) DESC, "
                "CASE WHEN status = 'CASCADE_RUN_STATUS_RUNNING' THEN 1 ELSE 0 END DESC, "
                "last_modified_time DESC LIMIT 64"
            ).fetchall()
            conn.close()
            for r in rows:
                d = dict(r)
                cid = str(d.get("conversation_id") or "").strip()
                if not cid:
                    continue
                rows_by_id[cid] = d
                parent_id = str(d.get("parent_conversation_id") or "").strip()
                if parent_id:
                    is_sub_active = bool(d.get("not_fully_idle")) or (
                        str(d.get("status") or "") == "CASCADE_RUN_STATUS_RUNNING"
                    )
                    if is_sub_active:
                        active_subagents_by_parent.setdefault(parent_id, []).append({
                            "cascade_id": cid,
                            "short_id": cid[:8],
                            "agent_name": str(d.get("agent_name") or "subagent"),
                            "step_count": int(d.get("step_count") or 0),
                            "status": str(d.get("status") or "CASCADE_RUN_STATUS_RUNNING"),
                        })
        except Exception as exc:
            sys.stderr.write(f"WARN: antigravity_bridge sqlite query error: {exc}\n")

    ordered_ids: list[str] = []
    # 1. Top-level conversations from conversation_summaries.db (already ordered by active + recency)
    for cid, d in rows_by_id.items():
        if int(d.get("nesting_depth") or 0) == 0 and not str(d.get("parent_conversation_id") or "").strip():
            ordered_ids.append(cid)
    # 2. Any top-level conversations from SearchConversations RPC not yet in ordered_ids
    for cid in rpc_by_id:
        if cid not in ordered_ids:
            ordered_ids.append(cid)
    # 3. Any remaining active subagent conversations if fewer than `limit` top-level sessions exist
    for cid in rows_by_id:
        if cid not in ordered_ids:
            ordered_ids.append(cid)

    discovered: list[dict[str, Any]] = []
    for cid in ordered_ids[: max(1, int(limit))]:
        db_row = rows_by_id.get(cid, {})
        rpc_row = rpc_by_id.get(cid, {})
        parent_id = str(db_row.get("parent_conversation_id") or "").strip()
        raw_title = (
            str(db_row.get("title") or "").strip()
            or str(rpc_row.get("title") or "").strip()
            or str(db_row.get("preview") or "").strip()
            or str(rpc_row.get("snippet") or "").strip()
        )
        if not raw_title and parent_id and parent_id in rows_by_id:
            parent_title = str(rows_by_id[parent_id].get("title") or "Parent Session").strip()
            raw_title = f"{parent_title} [Subagent {cid[:8]}]"
        if not raw_title:
            raw_title = f"Antigravity Session {cid[:8]}"

        status = str(db_row.get("status") or "CASCADE_RUN_STATUS_IDLE")
        not_fully_idle = bool(db_row.get("not_fully_idle")) or (status == "CASCADE_RUN_STATUS_RUNNING")
        step_count, last_tool_action, last_step_type = _extract_transcript_tail_telemetry(
            cid,
            brain_dirs,
            initial_step_count=int(db_row.get("step_count") or 0),
        )
        subagents = active_subagents_by_parent.get(cid, [])
        is_running = (status == "CASCADE_RUN_STATUS_RUNNING") or not_fully_idle or len(subagents) > 0
        entry: dict[str, Any] = {
            "cascade_id": cid,
            "short_id": cid[:8],
            "title": raw_title,
            "status": status,
            "is_running": is_running,
            "not_fully_idle": not_fully_idle,
            "step_count": step_count,
            "last_tool_action": last_tool_action,
            "last_step_type": last_step_type,
            "last_modified_time": str(
                rpc_row.get("lastModifiedTime") or db_row.get("last_modified_time") or ""
            ),
            "workspace_name": str(rpc_row.get("workspaceName") or ""),
            "parent_conversation_id": parent_id,
            "nesting_depth": int(db_row.get("nesting_depth") or 0),
            "active_subagent_count": len(subagents),
            "active_subagents": subagents,
        }
        entry["billboard"] = format_live_agent_billboard(entry)
        discovered.append(entry)

    ls_summary = {
        "connected": bool(resolved_ls and resolved_ls.get("port")),
        "pid": int(resolved_ls["pid"]) if resolved_ls and resolved_ls.get("pid") else None,
        "port": int(resolved_ls["port"]) if resolved_ls and resolved_ls.get("port") else None,
    }
    return {
        "ok": True,
        "connected": bool(ls_summary["connected"] or discovered),
        "language_server": ls_summary,
        "summaries_db": str(db_path),
        "active_count": sum(1 for a in discovered if a["is_running"]),
        "total_discovered": len(discovered),
        "subagent_count": sum(int(a.get("active_subagent_count") or 0) for a in discovered),
        "agents": discovered,
    }


def push_attached_agents_to_3d_engine(
    attached_by_desk: dict[str, dict[str, Any]],
    *,
    engine_url: str | None = None,
    include_say: bool = False,
    timeout: float = 0.8,
) -> dict[str, Any]:
    """Push attached Antigravity live agent presence and billboards to the 3D engine `/api/llm/act`."""
    base = (engine_url or os.environ.get("PD_LLM_URL") or "http://127.0.0.1:8780").rstrip("/")
    pushed = 0
    errors: list[str] = []
    for idx, (desk_id, item) in enumerate(attached_by_desk.items()):
        role = str(item.get("role") or desk_id.capitalize())
        chrnum = int(item.get("chrnum") or (0x31 + idx))
        action = "work" if item.get("is_running") else "idle"
        text = str(item.get("billboard") or format_live_agent_billboard(item))[:120]
        agent_obj: dict[str, Any] = {
            "chrnum": chrnum,
            "status": action,
            "billboard": text,
        }
        if include_say and idx == 0:
            agent_obj["say"] = text
        payload = json.dumps({"agents": [agent_obj]}).encode("utf-8")
        req = urllib.request.Request(
            f"{base}/api/llm/act",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    pushed += 1
        except Exception as exc:
            errors.append(f"{role}: {exc}")
    return {
        "engine_url": base,
        "pushed_count": pushed,
        "errors": errors,
    }


def attach_antigravity_agents_to_service(
    service: Any,
    *,
    limit: int = 8,
    push_to_engine: bool = False,
    engine_url: str | None = None,
    summaries_db_path: str | Path | None = None,
    brain_dir: str | Path | None = None,
    ls_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Discover live Antigravity agents and bind them onto the 8 VAO desks in `service`."""
    discovery = discover_antigravity_live_agents(
        limit=limit,
        summaries_db_path=summaries_db_path,
        brain_dir=brain_dir,
        ls_info=ls_info,
    )
    discovered_agents = discovery.get("agents") or []
    attached_by_desk: dict[str, dict[str, Any]] = {}

    for idx, (desk_id, default_role, default_chrnum) in enumerate(DESK_ORDER):
        if idx >= len(discovered_agents):
            break
        live = dict(discovered_agents[idx])
        svc_agent = service.agents.get(desk_id)
        role = svc_agent.role if svc_agent is not None else default_role
        chrnum = svc_agent.chrnum if svc_agent is not None else default_chrnum
        live["desk_id"] = desk_id
        live["role"] = role
        live["chrnum"] = chrnum
        attached_by_desk[desk_id] = live

    service.attached_live_agents = attached_by_desk
    service.antigravity_ls_info = dict(discovery.get("language_server") or {})

    engine_result = None
    if push_to_engine and attached_by_desk:
        engine_result = push_attached_agents_to_3d_engine(
            attached_by_desk,
            engine_url=engine_url,
        )

    return {
        "ok": True,
        "connected": discovery["connected"],
        "language_server": discovery["language_server"],
        "active_count": discovery["active_count"],
        "attached_count": len(attached_by_desk),
        "subagent_count": discovery["subagent_count"],
        "desks": attached_by_desk,
        "agents": list(attached_by_desk.values()),
        "engine_push": engine_result,
    }
