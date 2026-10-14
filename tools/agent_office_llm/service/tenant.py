"""Multi-tenant Office Service identity and state-path helpers.

Aligned with Flight Control's tenant → agents → runs hierarchy and seal
(isolation) pattern. See journal/agent_office/MULTI_TENANT.md.

Tenant id scopes durable state (workspace config, DMs, service snapshot,
future memory/connectors). Location (g5/ci/lab) remains a separate spatial
choice. Office ``id`` maps 1:1 to FC ``tenantId`` (or via ``fc_tenant_id``).
"""
from __future__ import annotations

import json
import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

JSON = dict[str, Any]

DEFAULT_TENANT_ID = "default"
TENANT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

_current_tenant: ContextVar[str] = ContextVar("office_tenant_id", default="")


@dataclass(frozen=True)
class TenantRecord:
    """One row from tenants.json (FC-aligned)."""

    id: str
    name: str
    display_name: str = ""
    fc_tenant_id: str = ""
    sealed: bool = True
    metadata: JSON = field(default_factory=dict)
    default_location: str = "g5"
    cast: str = "standard8"
    state_root: str | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        # frozen dataclass: use object.__setattr__
        if not self.display_name:
            object.__setattr__(self, "display_name", self.name or self.id)
        if not self.fc_tenant_id:
            object.__setattr__(self, "fc_tenant_id", self.id)


def normalize_tenant_id(raw: str | None) -> str:
    """Return a safe tenant id; empty/invalid → default."""
    value = str(raw or "").strip().lower()
    if not value:
        return DEFAULT_TENANT_ID
    if not TENANT_ID_RE.fullmatch(value):
        return DEFAULT_TENANT_ID
    return value


def resolve_tenant_id(
    *,
    header: str | None = None,
    query: str | None = None,
    env: str | None = None,
) -> str:
    """Precedence: header → query → env → default.

    Non-default tenants require an explicit selector (header/query/env).
    Silent fallback never invents another tenant's id.
    """
    for candidate in (header, query, env):
        if candidate is not None and str(candidate).strip():
            return normalize_tenant_id(candidate)
    env_val = os.environ.get("OFFICE_TENANT_ID", "").strip()
    if env_val:
        return normalize_tenant_id(env_val)
    return DEFAULT_TENANT_ID


def current_tenant_id() -> str:
    """Request ContextVar, else OFFICE_TENANT_ID, else default."""
    ctx = _current_tenant.get()
    if ctx:
        return normalize_tenant_id(ctx)
    return resolve_tenant_id()


@contextmanager
def tenant_context(tenant_id: str | None) -> Iterator[str]:
    """Bind (seal) tenant id for the duration of a request/handler."""
    tid = normalize_tenant_id(tenant_id)
    token = _current_tenant.set(tid)
    try:
        yield tid
    finally:
        _current_tenant.reset(token)


def resolve_repo_root(repo_root: str | None = None) -> Path:
    """Resolve Perfect Dark AIO repo root."""
    root = (repo_root or os.environ.get("PD_REPO_ROOT", "").strip() or "").strip()
    if root:
        return Path(root).expanduser()
    return Path(__file__).resolve().parents[3]


def resolve_agent_office_root(repo_root: str | None = None) -> Path:
    """Legacy / shared journal/agent_office directory."""
    return resolve_repo_root(repo_root) / "journal" / "agent_office"


def resolve_tenant_state_root(
    tenant_id: str | None = None,
    repo_root: str | None = None,
) -> Path:
    """Return journal/agent_office/tenants/<id> (may not exist yet)."""
    tid = normalize_tenant_id(tenant_id or current_tenant_id())
    return resolve_agent_office_root(repo_root) / "tenants" / tid


def resolve_tenants_registry_path(repo_root: str | None = None) -> Path:
    """Path to tenants.json registry."""
    override = os.environ.get("AGENT_OFFICE_TENANTS", "").strip()
    if override:
        return Path(override).expanduser()
    return resolve_agent_office_root(repo_root) / "tenants.json"


def resolve_tenant_state_file(
    filename: str,
    *,
    tenant_id: str | None = None,
    repo_root: str | None = None,
) -> Path:
    """Resolve a durable state file under the sealed tenant.

    For ``default``, prefer ``tenants/default/<file>`` when present (file or
    symlink); otherwise fall back to the legacy ``journal/agent_office/<file>``
    so current single-tenant installs keep working without migration.

    Non-default tenants never read another tenant's root (no cross-tenant bleed).
    """
    name = str(filename or "").strip().lstrip("/")
    if not name or name != Path(name).name:
        raise ValueError(f"invalid tenant state filename: {filename!r}")
    tid = normalize_tenant_id(tenant_id or current_tenant_id())
    tenant_path = resolve_tenant_state_root(tid, repo_root) / name
    if tid != DEFAULT_TENANT_ID:
        return tenant_path
    if tenant_path.exists() or tenant_path.is_symlink():
        return tenant_path
    return resolve_agent_office_root(repo_root) / name


def ensure_tenant_state_root(
    tenant_id: str | None = None,
    repo_root: str | None = None,
) -> Path:
    """Create tenants/<id>/ (and memory/) if missing; return the root."""
    root = resolve_tenant_state_root(tenant_id, repo_root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "memory").mkdir(exist_ok=True)
    (root / "connectors").mkdir(exist_ok=True)
    return root


def ensure_default_tenant_symlinks(repo_root: str | None = None) -> Path:
    """Optional migrate: tenants/default/* → symlink legacy files when absent.

    Safe no-op if links/files already exist. Does not move or delete legacy files.
    """
    root = ensure_tenant_state_root(DEFAULT_TENANT_ID, repo_root)
    legacy = resolve_agent_office_root(repo_root)
    for name in (
        "workspace_config.json",
        "dm_threads.json",
        "office_service_state.json",
        "slack_oauth.json",
    ):
        dest = root / name
        src = legacy / name
        if dest.exists() or dest.is_symlink():
            continue
        if src.exists():
            dest.symlink_to(src.resolve())
    return root


def parse_tenant_record(raw: JSON) -> TenantRecord:
    """Pure validation for one tenants.json row (FC-aligned fields)."""
    if not isinstance(raw, dict):
        raise ValueError("tenant row must be an object")
    raw_id = str(raw.get("id") or "").strip()
    if not raw_id:
        raise ValueError("tenant.id is required")
    tid = normalize_tenant_id(raw_id)
    name = str(raw.get("name") or raw.get("display_name") or tid).strip() or tid
    display = str(raw.get("display_name") or name).strip() or name
    fc_id_raw = str(raw.get("fc_tenant_id") or tid).strip() or tid
    fc_id = normalize_tenant_id(fc_id_raw)
    sealed_raw = raw.get("sealed", True)
    sealed = True if sealed_raw is None else bool(sealed_raw)
    meta = raw.get("metadata")
    metadata: JSON = dict(meta) if isinstance(meta, dict) else {}
    return TenantRecord(
        id=tid,
        name=name,
        display_name=display,
        fc_tenant_id=fc_id,
        sealed=sealed,
        metadata=metadata,
        default_location=str(raw.get("default_location") or "g5").strip() or "g5",
        cast=str(raw.get("cast") or "standard8").strip() or "standard8",
        state_root=str(raw["state_root"]).strip() if raw.get("state_root") else None,
        notes=str(raw.get("notes") or ""),
    )


def default_tenants_registry() -> list[TenantRecord]:
    """Built-in registry when tenants.json is missing."""
    return [
        TenantRecord(
            id=DEFAULT_TENANT_ID,
            name="Default Office",
            display_name="Default Office",
            fc_tenant_id=DEFAULT_TENANT_ID,
            sealed=True,
            metadata={"migration": True},
            default_location="g5",
            cast="standard8",
            state_root="journal/agent_office/tenants/default",
            notes="Migration wrapper for pre-multi-tenant state",
        )
    ]


def load_tenants_registry(repo_root: str | None = None) -> list[TenantRecord]:
    """Load tenants.json; fall back to the built-in default tenant."""
    path = resolve_tenants_registry_path(repo_root)
    if not path.is_file():
        return default_tenants_registry()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_tenants_registry()
    rows = raw.get("tenants") if isinstance(raw, dict) else None
    if not isinstance(rows, list) or not rows:
        return default_tenants_registry()
    out: list[TenantRecord] = []
    for row in rows:
        try:
            out.append(parse_tenant_record(row if isinstance(row, dict) else {}))
        except ValueError:
            continue
    return out or default_tenants_registry()


def lookup_tenant_by_fc_id(
    fc_tenant_id: str | None,
    repo_root: str | None = None,
) -> TenantRecord | None:
    """Resolve FC tenantId → registry row via fc_tenant_id or id (1:1 / alias)."""
    needle = normalize_tenant_id(fc_tenant_id)
    for rec in load_tenants_registry(repo_root):
        if rec.fc_tenant_id == needle or rec.id == needle:
            return rec
    return None


def is_registered_tenant(
    tenant_id: str | None,
    repo_root: str | None = None,
) -> bool:
    """Return True if tenant_id (or fc_tenant_id alias) is in tenants.json (default always True)."""
    needle = normalize_tenant_id(tenant_id)
    if needle == DEFAULT_TENANT_ID:
        return True
    return lookup_tenant_by_fc_id(needle, repo_root) is not None


def tenant_registry_enforced(repo_root: str | None = None) -> bool:
    """Return True when unknown tenants must be rejected with HTTP 404."""
    env_flag = os.environ.get("OFFICE_ENFORCE_TENANT_REGISTRY", "").strip().lower()
    if env_flag in ("1", "true", "yes", "on"):
        return True
    if env_flag in ("0", "false", "no", "off"):
        return False
    path = resolve_tenants_registry_path(repo_root)
    if not path.is_file():
        return False
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and raw.get("enforce_registry") is True:
            return True
    except (OSError, json.JSONDecodeError):
        return False
    return False


def office_id_for_fc_tenant(
    fc_tenant_id: str | None,
    repo_root: str | None = None,
) -> str:
    """Map FC tenantId to Office Service id (alias-aware; passthrough if unknown)."""
    rec = lookup_tenant_by_fc_id(fc_tenant_id, repo_root)
    if rec:
        return rec.id
    return normalize_tenant_id(fc_tenant_id)


def serialize_tenant_record(rec: TenantRecord) -> JSON:
    """JSON projection for GET /tenants (FC-aligned)."""
    payload: JSON = {
        "id": rec.id,
        "name": rec.name,
        "display_name": rec.display_name or rec.name,
        "fc_tenant_id": rec.fc_tenant_id or rec.id,
        "sealed": bool(rec.sealed),
        "metadata": dict(rec.metadata or {}),
        "default_location": rec.default_location,
        "cast": rec.cast,
    }
    if rec.state_root:
        payload["state_root"] = rec.state_root
    if rec.notes:
        payload["notes"] = rec.notes
    return payload


def tenant_from_headers_and_query(
    headers: dict[str, str] | None,
    query: dict[str, str] | None,
    *,
    repo_root: str | None = None,
) -> str:
    """Extract tenant id from HTTP headers + query dict (resolving fc_tenant_id aliases when repo_root given)."""
    header_map = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
    raw = resolve_tenant_id(
        header=header_map.get("x-office-tenant"),
        query=(query or {}).get("tenant"),
    )
    if repo_root is not None:
        return office_id_for_fc_tenant(raw, repo_root)
    return raw
