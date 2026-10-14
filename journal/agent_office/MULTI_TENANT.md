# Multi-tenant Virtual Agent Office

**Status:** Design + scaffold + **llm-play 1.5.0 Session picker** (default + demo tenants), **Flight Control–aligned** (2026-07-27)  
**Product analogy:** Slack multi-workspace / choosing a saved game at launch  
**Companion:** [`SPEC.md`](./SPEC.md), [`NEXT_STEPS.md`](./NEXT_STEPS.md), [`LONG_TERM_FINAL_GOAL_PROMPT.md`](./LONG_TERM_FINAL_GOAL_PROMPT.md), [`HOSTING.md`](./HOSTING.md)  
**Canonical tenancy source:** Flight Control (`PragCore/flight-control`) — Office Service / VAO **follow FC’s pattern**, not a parallel tenant shape.  
**Cloud Hosting (locked):** Firebase project `pragcore`, site `pragcore-vao`, working URL `https://pragcore-vao.web.app` (`vao.pragcore.com` pending DNS); **shared Auth + `tenantId` seal** with FC; **isolated** Firestore DB `vao-prod` — see [`HOSTING.md`](./HOSTING.md).

---

## 1. Intent (locked)

When you launch Perfect Dark office / llm-play **Office** mode / **VAO.app**, you **pick which tenancy** to enter before you walk the floor.

That tenancy scopes the management system:

| Scoped by tenant | Not reinvented |
|------------------|----------------|
| Office Service agents, tasks, approvals | Second task DB (forbidden) |
| Memory files / DM threads | Parallel combat default |
| Connector credentials + audit | Duplicate FC queue |
| Cast roster (≤8 embodied) | Separate “office product” |

**Different tenants = different companies / workspaces you walk into.**

Roles stay the same:

| Layer | Role |
|-------|------|
| Human | Walking manager in Perfect Dark |
| Office Service | Durable control plane |
| Perfect Dark | Spatial / embodied client (one sealed tenant per session) |
| Flight Control | Fleet / swarm ops — **list tenants, drill-in seals** (FC L→R) |
| Projex / PragChat | Chat + project client of the same service |

Hard laws unchanged: ≤8 embodied agents per office instance; combat never default; Office Service remains the single durable task/approval store.

**User decision (locked):** Office / VAO tenancy follows **Flight Control’s hierarchy and isolation pattern**. Hierarchy goes **left → right: tenants → agents → …**. Do not invent a parallel tenant tree.

---

## 2. Flight Control canonical model (from code)

Discovered in `PragCore/flight-control` (not invented here).

### 2.1 Hierarchy (left → right)

```
tenantId                    ← opaque string (Firebase Auth uid, or gateway key → tenantId)
  └── agents / channels     ← SwarmAgent / location branches (nyc, sf, …)
        └── runs / threads  ← DbRun (+ logs, telemetry)
              └── messages  ← console feed / telemetry events
```

| Layer | FC implementation | Key paths |
|-------|-------------------|-----------|
| **Tenant** | Firestore `tenants/{tenantId}`; SaaS gateway stamps `tenantId` on runs/telemetry | `firestore.rules`, `src/swarm/api-gateway.ts`, `src/swarm/db.ts` |
| **Agents** | Swarm registry agents; UI “Agent Instances” / location channels | `src/swarm/types.ts`, `dashboard.html`, `tui.ts` |
| **Runs / threads** | `tenants/{uid}/runs` or local `DbRun.tenantId` | `db.ts`, Firebase subscriptions |
| **Messages** | Main console / telemetry under the run | dashboard console feed |

There is **no** separate typed `Tenant` children-tree in TypeScript; isolation is **identity + namespacing**. Practical product tree for VAO:

**`tenant → agents → runs/threads → messages`** (then PD **location** as spatial overlay, orthogonal to tenant).

### 2.2 UI L→R (operator console)

FC console columns (left → right):

1. **Workspace rail** (office / ops) — org workspace icon, not a free-floating “all tenants” bag of agents  
2. **Channels** — agent instances / location branches + oversight  
3. **Thread runs**  
4. **Main console** (messages)

Default workspace: `office`; default channel: `nyc`. After auth, subscriptions are scoped to **`tenants/{uid}`** — one tenant at a time.

### 2.3 What “seal” means (product term; FC isolation pattern)

FC code does **not** use the word `sealed` as an API flag. Isolation that *does* exist:

| Mechanism | Semantics |
|-----------|-----------|
| Firestore rules | `request.auth.uid == tenantId` — no cross-tenant doc access |
| `SaasApiGateway` | API key → `tenantId`; ingest/list filtered by that id |
| Dashboard Firebase mode | Listen only under the signed-in tenant |

**VAO / Office Service adopt “seal” as the name for that pattern:**

- **List** tenants is allowed (ops / picker / `GET /tenants`).
- **Drill-in** (select / header / launch) **seals** to that tenant: default queries and PD session see **only** that tenant’s agents, tasks, approvals, memory.
- **No cross-tenant leakage** in Office Service default list/filter paths or in a Perfect Dark session.
- Cross-tenant rumor/handoff is **explicit routing only** (R7), never silent bleed.

### 2.4 Tenant id shape (FC)

| Surface | Id shape | Profile fields |
|---------|----------|----------------|
| Firestore | Auth **`uid`** | `email`, `createdAt`, optional `provider` |
| Gateway / local DB | string e.g. `tenant-receptionist-ai` | `tenantId` on runs/telemetry |
| Typed rich Tenant | **none** in FC TS today | — |

Office Service uses the same opaque string id (slug-normalized for disk). See §3.1 for registry + alias.

### 2.5 FC ↔ Office Service today vs target

| Concern | FC today | Target (this design) |
|---------|----------|----------------------|
| SaaS runs/telemetry | Filtered by `tenantId` | Unchanged |
| `OfficeServiceClient` | No tenant header | Sends `X-Office-Tenant` (= FC `tenantId`) |
| `/api/office/*` proxy | Unscoped | Forwards sealed tenant from request/env |
| Ops “list tenants” | Not a first-class Office tree | `GET /tenants` then drill-in seals |

---

## 3. Vocabulary (do not collapse)

| Term | Meaning | Slack / game analogy |
|------|---------|----------------------|
| **Tenant** | Management boundary = FC `tenantId` (company/workspace identity, state root, credentials, cast, audit) | Slack workspace / saved game slot |
| **Seal** | Enter one tenant; isolate agents/tasks/memory; no cross-tenant default reads | Signing into one Slack workspace |
| **Location** | Spatial map you walk: `g5`, `ci`, `ci_lobby`, `lab` | Which building floor plan |
| **Member profile** | Human display name + codename in that tenant | Your Slack member profile |
| **Team agents** | Eight desk NPCs (Director … Comms) under the sealed tenant | Bots / teammates |

Today’s SPEC “Workspace” label mostly meant **location**. Going forward:

- UI copy for the company picker: **Tenant** (or “Company / workspace”)
- UI copy for G5/CI/lab: **Location** (or “Office floor”)
- Prefer not to call both “workspace” without a qualifier

---

## 4. Tenant model (FC-aligned registry)

### 4.1 Record shape

Registry file: `journal/agent_office/tenants.json`

```json
{
  "version": 1,
  "tenants": [
    {
      "id": "default",
      "name": "Default Office",
      "display_name": "Default Office",
      "fc_tenant_id": "default",
      "sealed": true,
      "metadata": {
        "migration": true,
        "notes": "Pre-multi-tenant state wrapper"
      },
      "default_location": "g5",
      "cast": "standard8",
      "state_root": "journal/agent_office/tenants/default"
    }
  ]
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `id` | yes | Office Service tenant id; stable slug `[a-z0-9][a-z0-9_-]{0,63}`; reserved: `default` |
| `name` | yes* | Human label (FC-style); *scaffold accepts `display_name` as alias |
| `display_name` | no | Alias of `name` for older pickers |
| `fc_tenant_id` | no | **1:1 map to FC `tenantId`**; default = `id`. Use when FC uid/`tenant-*` differs from disk slug |
| `sealed` | no | Default `true`. Documents isolation-on-enter; all product tenants seal when drilled into |
| `metadata` | no | Free-form object (email, provider, operator notes, etc.) |
| `default_location` | no | `g5` \| `ci` \| `ci_lobby` \| `lab` |
| `cast` | no | Roster key; v1 only `standard8` |
| `state_root` | no | Override; default `journal/agent_office/tenants/<id>` |
| `notes` | no | Operator hint (also fine inside `metadata`) |

**Id mapping rule:** Office Service request scope uses `id`. Clients that speak FC’s id send `X-Office-Tenant: <fc_tenant_id>` (or `id` when they match). Registry resolves alias → Office `id` when wiring lands; until then keep `fc_tenant_id === id` for every row.

### 4.2 Per-tenant state root

```
journal/agent_office/tenants/<id>/
  workspace_config.json
  dm_threads.json
  office_service_state.json
  memory/
  connectors/
  audit/
```

**One Office Service task store per tenant** — same schema and APIs; only root path + request seal change. Do not invent a second queue.

### 4.3 Credentials scope

| Secret / install | Scope |
|------------------|-------|
| Slack bot token / OAuth install | Tenant (sealed) |
| GitHub / PagerDuty (future) | Tenant |
| Account pool leases | Tenant |
| ASR / Whisper host env | Process / machine (shared) |
| LLM API keys (host) | Process / machine unless tenant-bound later |

### 4.4 Cast roster

v1: every tenant uses the standard eight roles. Embodiment hard cap remains 8 for any PD session.

---

## 5. Launch UX

### 5.1 Recommended flow (FC-compatible tenant id)

```
Launch VAO / Office mode
        │
        ▼
  Pick Tenant ──────────► registry id (== fc_tenant_id, or documented alias)
        │                   (like choosing a Slack workspace / FC tenant)
        ▼
  Pick Location ────────► g5 / ci / ci_lobby / lab
        │
        ▼
  Confirm member profile if missing
        │
        ▼
  Enter Office → PD boots location; session is SEALED to that tenant
                 clients send X-Office-Tenant / OFFICE_TENANT_ID
```

PD launch picker **must** choose an FC-compatible tenant id (registry `id` / `fc_tenant_id`), never an ad-hoc parallel namespace.

### 5.2 Alternative: tenant embeds location

A tenant may set `default_location` and skip the second picker. Scaffold ships both.

### 5.3 Surfaces

| Surface | Tenant selection | Location selection |
|---------|------------------|--------------------|
| **VAO.app** (Electron) | Tenant select (stub → full); FC-compatible ids | Existing location select |
| **llm-play** Office mode | Env / prefs `OFFICE_TENANT_ID` (+ `X-Office-Tenant` on polls) | Existing office launch scripts |
| **Projex add-on** | Input `OFFICE_TENANT_ID` | Existing `OFFICE_LOCATION` |
| **CLI** | `OFFICE_TENANT_ID=acme ./scripts/play-agent-office.sh` | Script / `--boot-stage` |
| **Flight Control** | List via `/tenants` (ops); drill-in sets sealed `X-Office-Tenant` on `/api/office/*` | N/A (fleet proxy) |

Combat sims remain opt-in and never the default Enter path.

---

## 6. Office Service — tenant scope & seal

### 6.1 Identity resolution (precedence)

1. HTTP header `X-Office-Tenant: <id>`  ← preferred (FC client + llm-play)
2. Query `?tenant=<id>`
3. Env `OFFICE_TENANT_ID`
4. Default: `default`

Malformed / empty → `default`. Non-default tenants should be selected **explicitly** (header/query/env); silent fallback never invents another tenant’s paths.

Unknown id: scaffold may resolve paths under `tenants/<id>/` (lazy create on write) **or** 404 once registry enforcement lands.

### 6.2 Seal semantics (API)

| Mode | Behavior |
|------|----------|
| **Sealed request** | After identity resolution, path helpers + future per-tenant `OfficeService` map serve **only** that tenant |
| **List tenants** | `GET /tenants` — registry listing (ops / picker); does **not** unseal fleet/tasks |
| **Default queries** | `/fleet`, `/agents`, `/tasks`, `/approvals`, `/dispatch`, social feed — sealed to active tenant |
| **Health** | Echoes `tenant`, `sealed: true`, `tenant_state_root` |

Scaffold: process + request identity accepted; full per-request in-memory isolation is the next implementation rung.

### 6.3 State path resolution

```
resolve(tenant, file):
  if tenant == "default":
    prefer journal/agent_office/tenants/default/<file> if present (file or symlink)
    else legacy journal/agent_office/<file>
  else:
    journal/agent_office/tenants/<tenant>/<file>   # never default/legacy
```

Explicit env overrides (`AGENT_OFFICE_SERVICE_STATE`, …) still win.

### 6.4 API surface (scaffold + target)

| Endpoint / behavior | Scaffold | Target |
|---------------------|----------|--------|
| `GET /health` → `tenant`, `sealed` | yes | yes |
| `GET /tenants` lists registry (+ `fc_tenant_id`, `sealed`, `metadata`) | yes | yes |
| Accept `X-Office-Tenant` / `?tenant=` | yes | yes |
| CORS allow `X-Office-Tenant` | yes | yes |
| FC `OfficeServiceClient` sends tenant header | yes | yes |
| FC `/api/office/*` forwards sealed tenant | yes | yes |
| Per-tenant in-memory `OfficeService` map | yes | yes |
| Registry-enforced 404 for unknown tenants (`enforce_registry`) | yes | yes |
| Alias resolve `fc_tenant_id` → `id` | yes | yes |
| `POST /tenants` admin registration endpoint | yes | yes |
| Ops list-then-seal UI in FC dashboard | yes | yes |

---

## 7. Clients pass tenant at Launch

### 7.1 Environment contract

| Variable | Meaning |
|----------|---------|
| `OFFICE_TENANT_ID` | Active / sealed tenant (= FC `tenantId` or registry alias) |
| `OFFICE_LOCATION` | Spatial location key |
| `AGENT_OFFICE_API_PORT` | Office Service port (default `8791`) |
| `OFFICE_SERVICE_URL` | FC / clients base URL for Office Service |

### 7.2 VAO.app

1. Read `tenants.json`
2. Tenant select → persist (`vao_tenant_id`) — FC-compatible id
3. Location select
4. Fetches send `X-Office-Tenant`
5. Child env includes `OFFICE_TENANT_ID`

### 7.3 llm-play

Office mode health/fleet polls send `X-Office-Tenant` from `OFFICE_TENANT_ID` (default `default`). Prefs key suggestion: `officeTenantId`.

### 7.4 Projex

Optional `OFFICE_TENANT_ID` (default `default`) into Office Service / 3D launch env.

### 7.5 Perfect Dark bridge

C bridge stays tenant-agnostic; the **host** sealed the tenant via env/header. No second task store in-engine.

### 7.6 Flight Control client

`OfficeServiceClient` + `/api/office/*`:

- Resolve tenant: request `X-Office-Tenant` / `?tenant=` → else `OFFICE_TENANT_ID` → else `default`
- Forward `X-Office-Tenant` on every Office Service call (seal)
- May **list** via Office `GET /tenants` without unsealing fleet; drilling into a tenant sets the sealed header for subsequent fleet/dispatch

---

## 8. Flight Control navigation (product)

**Locked:** FC lands on **tenant-scoped** navigation matching the L→R model — not a vague “all tenants” default without structure.

| Step | Behavior |
|------|----------|
| 1 | Ops may **list** tenants (`GET /tenants` / future FC rail) |
| 2 | **Drill-in** seals to one `tenantId` |
| 3 | L→R under seal: **agents → threads/runs → messages** (FC console) |
| 4 | PD / VAO Enter: same sealed id; one walk session |

| Client | Tenant visibility |
|--------|-------------------|
| **Flight Control** | List all (ops); **sealed** after drill-in for fleet/dispatch |
| **Perfect Dark session** | Exactly one sealed tenant |
| **VAO / llm-play Enter** | One FC-compatible tenant before launch |

FC must not become a second task DB: it proxies Office Service. Cross-tenant social is explicit handoff only.

---

## 9. Migration

### 9.1 Default tenant wraps today

Legacy files stay valid under `tenant_id=default` until `tenants/default/` exists.

### 9.2 Optional physical migrate

```bash
mkdir -p journal/agent_office/tenants/default
# symlink or move state files into tenants/default/
```

### 9.3 Adding a second tenant

1. Append to `tenants.json` with `id`, `name`, `fc_tenant_id` (1:1 or alias), `sealed: true`
2. Create `tenants/<id>/`
3. Select in VAO / set `OFFICE_TENANT_ID` to that FC-compatible id
4. Do not copy secrets by default

---

## 10. Scaffold vs next rung

### Works today (this pass)

- FC-aligned design note (hierarchy L→R + seal semantics)
- Registry `tenants.json` with `id` / `name` / `fc_tenant_id` / `sealed` / `metadata`
- `service/tenant.py` path + id helpers
- HTTP tenant header/query; `/health` + `/tenants` (+ seal fields)
- FC `OfficeServiceClient` + `/api/office/*` forward `X-Office-Tenant`
- VAO.app stub tenant select; llm-play Office health header
- Unit tests: path isolation / no cross-tenant bleed
- Cross-links in SPEC / NEXT_STEPS / LONG_TERM

### Next implementation rung

1. Per-tenant `OfficeService` instances in one API process (hard seal in memory)
2. Resolve `fc_tenant_id` aliases on every request
3. Wire all VAO fetch helpers + director/play scripts to export `OFFICE_TENANT_ID`
4. Memory / account-pool paths under tenant root
5. FC dashboard: tenant list → drill-in seal (not unstructured global fleet)
6. Projex Launch UI tenant field
7. Registry enforcement + create-tenant admin API
8. Evidence: two tenants, isolated approvals/DMs, one PD session each

### Explicitly out of scope here

- Launching `pd.office` / combat cert churn
- bodyAllocate crash work
- Git commits
- Rewriting the task model

---

## 11. Cloud Hosting + Auth (pointer)

Locked product cloud plane (not a second tenant model):

| Surface | Choice |
|---------|--------|
| Hosting | Site `pragcore-vao` · primary URL `vao.pragcore.com` |
| Auth | Shared PragCore / FC Auth |
| Tenant IDs | Same FC `tenantId` / seal as this doc |
| Firestore | Named DB `vao-prod` only for VAO cloud docs |

Full DNS, CLI, and scaffold paths: [`HOSTING.md`](./HOSTING.md). Scaffold root: `PragCore/vao-web/`.

---

## 12. Assumptions

1. **One PD process ↔ one sealed tenant** for a session.
2. **Location stays orthogonal** to tenant.
3. **`default` is forever reserved** as the migration / solo-dev tenant id.
4. **Unknown tenant ids** allowed on disk in scaffold; product UX offers registry rows only.
5. **FC list is ops-only**; embodied PD never shows another tenant’s cast in the same session.
6. **Social bus cross-office (g5↔ci)** remains same-tenant unless an explicit handoff tool says otherwise.
7. **Office `id` ↔ FC `tenantId`** is 1:1 or a documented `fc_tenant_id` alias — never a second namespace.

---

## 13. Open questions (for product owner)

1. **Should switching tenant require a full relaunch**, or is an in-app “Exit to tenant picker” (kill PD + reset API context) acceptable in v1?
2. **May two tenants share one Slack workspace** (separate bot installs), or is 1:1 tenant↔Slack-team required?

*(FC hierarchy + seal pattern is decided; do not reopen here.)*
