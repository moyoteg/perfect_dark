# Virtual Agent Office — Vision & Product Spec

**Status:** Vision source of truth (2026-07-02) · **Method:** `engineering:system-design`
**Parent contracts:** [`SPEC.md`](./SPEC.md) (shipped maps + engineering) · [`LLM_CONVERSATION_LAYER.md`](./LLM_CONVERSATION_LAYER.md) (live-agent seams) · [`../../../llm-play/VISION.md`](../../../llm-play/VISION.md)
**Audience:** build plan (self), sharable to a team.

---

## 0. The one line

> **A Slack-like agent workspace with a 3D video-game interface for managing AI agents —
> wonderfully and effectively.**

You don't read your agents' logs. You don't babysit a dozen disconnected chat tabs. You open
**Projex/PragChat**, the existing project-management and Slack-like chat host where agents live
in projects, channels, threads, mentions, and DMs. When you need embodied presence, you open the
**Perfect Dark 3D office tab** and your AI agents are *there* — at their desks, doing real work
through real tools (Slack, GitHub, Linear, PagerDuty). You stroll up to the Ops agent; it turns
and says prod is red and offers to page on-call. You glance at the Comms agent's monitor and see
the same project threads that Projex/PragChat is tracking. You drop a task on the Research
agent's desk and walk away. Managing a fleet of agents becomes **project-native, chat-native,
spatial, embodied, and legible** instead of a wall of dashboards.

The operational backbone is Projex/PragChat: project management plus Slack-like chat. The
embodied medium is a fully realized game engine (decompiled Perfect Dark). The content is your
actual work. **The office is the spatial control plane; Projex/PragChat is the project/text
control plane; both are views over the same agent system.**

---

## 1. Why this, why now

### The problem with how we manage AI agents today

Agent frameworks multiplied; the *interface* to them did not. Managing agents today means:

- **Tab sprawl** — one chat window per agent, no shared space, no peripheral awareness.
- **Log spelunking** — to know what an agent did you read a transcript or a JSON trace.
- **No presence** — you can't tell at a glance who's busy, blocked, waiting on you, or idle.
- **Flat dispatch** — kicking off work is a text box; there's no sense of *handing* a task to
  *someone* who *has* it now.
- **Context collapse** — ten agents' worth of state crammed into scrollback.

Humans are extraordinary at managing *people in a room*. We read posture, proximity, who's
huddled with whom, who just looked up. **None of that instinct is available in a text console.**

### The bet

A spatial, embodied interface turns agent management into something the human brain is already
optimized for: **walking a floor, reading a room, delegating to people at desks.** A game engine
gives us presence, line of sight, movement, voice, and a shared world essentially for free —
and Perfect Dark's decompilation hands us a AAA-atmosphere office (dataDyne G5, Carrington
Institute) already built. We are not making a game. **We are making mission control for agents,
and it happens to be the most fun agent dashboard ever shipped.**

The same system also needs a fast ordinary work surface. Projex/PragChat should supply that
surface: project/task management plus the Slack-like interface for agent channels, work threads,
unread state, mentions, approvals, and remote dispatch. The 3D office is not a replacement for
chat or project management; it is an embodied tab into the same control plane.

### Why the game engine is the right substrate (not a gimmick)

| Management need | What the engine gives, natively |
|-----------------|----------------------------------|
| Peripheral awareness of many agents | A room you can see across; status floating over each desk |
| "Who is this agent" | A body, a face, a voice, a fixed desk — identity without a label |
| Delegation that feels like handoff | Walk up, speak/drop a task, walk away |
| Interrupt / focus | Approach = focus that agent; Z-target = inspect |
| Reading agent state | Posture + animation (typing = working, turned to you = waiting) |
| Inter-agent coordination | Agents at adjacent desks, line of sight, a shared event bus |
| Situational overview | The lobby console = mission control; the floor = the fleet |

---

## 2. The core model: the office is the control plane

The product has one durable core and multiple clients. If Projex is the active app shell that
already includes PragChat and project management, it should be the host:

```
Projex/PragChat (projects + Slack-like workspace) \
Slack / webhooks / remote API                      > Office Service -> agents, tasks, tools, memory, audit
Perfect Dark 3D office tab                         /
```

The operational structure is Slack plus project management: projects, tasks, channels, threads,
mentions, agent DMs, presence, slash-style dispatch, unread/needs-you state, approvals, and
searchable history. The 3D office should mirror that structure spatially: agents at desks,
console overview, in-world approvals, monitor/result surfaces, and live voice conversations.

The shipped **lobby mode** (SPEC §7 — a walkable foyer where eight agents stand at fixed pads,
Z-targetable, with a tagged console) is not a demo of a game level. **It is the first version
of the agent-management surface.** This spec reinterprets every lobby element as a management
primitive and extends it.

```
   Lobby element (shipped)          →   Management meaning (this vision)
   ─────────────────────────────────────────────────────────────────────
   Agent NPC at a fixed pad         →   A managed AI worker with a home station
   Z-target → HUD status line       →   Inspect: what is this agent doing / knows
   Briefing animation loop          →   Presence: idle vs working vs waiting
   Proximity greeting (greet_text)  →   Focus: you've engaged this agent
   Tagged lobby console (Z)         →   Mission control: fleet overview + dispatch
   TEAM_NONCOMBAT, peaceful solo    →   A management space, not a combat space
   Two variants (G5 / CI)           →   Two "offices" = two teams / workspaces
```

### The eight roles are eight agent archetypes

The shipped roster — **Director, Orchestrator, Research, Code, QA, Security, Ops, Comms** — is
not decoration. Each is an **agent archetype bound to a domain and a set of tools**:

| Agent | Domain | Operates (connectors) | You go to it to… |
|-------|--------|-----------------------|------------------|
| **Director** | Strategy / standup | (reads all) | Get the state of the fleet; set priorities |
| **Orchestrator** | Dispatch / routing | task queue, other agents | Hand off work; see what's queued/blocked |
| **Research** | Investigation | Notion/Docs, web, code search | Ask "find out X"; get a briefing |
| **Code** | Implementation | GitHub (PRs, branches) | Assign a change; review a diff |
| **QA** | Verification | GitHub checks, CI | Gate a release; see test status |
| **Security** | Guard / policy | audit, access, approvals | Approve risky actions; review who did what |
| **Ops** | Runtime | PagerDuty, Datadog, CI/CD | Check prod; page on-call; run a deploy |
| **Comms** | People / status | **Slack**, Gmail, Calendar | Triage messages; broadcast status |

The **Comms agent is the Slack liaison** — the anchor integration (§5). Ops is PagerDuty/Datadog.
Code/QA are GitHub. This is the "hybrid" model: **each agent is an autonomous LLM worker that
operates real tools on your behalf**, and you manage them through the room.

---

## 3. Management primitives — the verbs of the room

Everything you do to an agent maps to a physical interaction. This is the interaction spec.

| Verb | Physical interaction | Under the hood |
|------|---------------------|----------------|
| **Notice** | See status floating over a desk; posture/anim | `/observe` + per-agent status projected to HUD/billboard |
| **Inspect** | Z-target an agent → its current task, last action, what it knows | pull agent state; render as HUD panel |
| **Focus / engage** | Walk within range; it turns to face you | proximity (`if_distance_to_target_lt`, `GREET_RANGE`) → engage event |
| **Brief / dispatch** | Speak (mic→ASR) or drop a task at its desk | utterance/intent → agent brain → task created |
| **Interrupt / steer** | Approach a working agent; it pauses and listens | engage preempts the agent's idle/work loop |
| **Approve / deny** | Walk to Security; confirm a pending risky action | approval queue gated on a human-present interaction |
| **Hand off** | Send one agent to another's desk ("ask Ops to check") | inter-agent message on the world event bus |
| **Review** | Read an agent's output at its monitor / the console | render task result; link out to the real artifact (PR, thread) |
| **Overview** | Use the lobby console (Z) | fleet dashboard: who's busy, queued, blocked, waiting on you |

Design law: **no management action requires leaving the room or opening a menu.** The floor is
the UI. The console is the only "screen," and it's diegetic (an in-world terminal).

---

## 4. Anatomy of an agent

An agent is a folder of config + a live runtime binding. Hybrid = **brain + memory + tools +
voice + body**.

```
Agent "ops"
├── brain.json        role, persona, system prompt, model, autonomy level
├── tools[]           connectors it may operate (pagerduty, datadog, ci)  ← §5
├── memory/           rolling task log + durable knowledge (what it knows)
├── voice/config.json TTS identity (voice_pipeline)                        ← existing
├── body              chrnum, model, home pad (the desk)                   ← SPEC §7
└── policy            autonomy: suggest | ask-approval | act               ← §6 safety
```

Voice is part of identity, not decoration. The system should support local LLM replies paired
with generated character voices, including Dr. Caroll-style AI voices for in-world characters
whose personality should feel native to Perfect Dark rather than like generic speech synthesis.

**Autonomy levels** (the safety dial, per agent per tool):

- `suggest` — the agent proposes; nothing happens without you.
- `ask-approval` — the agent stages an action; requires a human-present approval (walk to it,
  or to Security). Default for anything that writes/sends/deploys.
- `act` — the agent may execute autonomously within a declared scope (e.g. Ops may acknowledge
  a page but not resolve it).

**Presence encodes state** (posture/animation → status; the management "read"):

| Agent state | In-world tell |
|-------------|---------------|
| Idle | Standing/looking around at desk |
| Working | Typing animation, facing monitor |
| Blocked / needs you | Turned toward the aisle, status pulsing over desk |
| Awaiting approval | At Security's window / status flag |
| Done, result ready | Result on its monitor; console badge |

---

## 5. Integration model — agents that operate real tools (Slack first)

The office is worthless if the agents only talk. They must **do** — through the same connector
ecosystem the rest of the workspace uses (MCP connectors: Slack, GitHub, Linear, PagerDuty,
Datadog, Gmail, Calendar, Notion, …).

### 5.1 Binding: tools are equipped to agents

Each agent's `tools[]` lists the connectors it may operate. The agent's brain calls them through
a **Connector Gateway** (one place that holds auth, rate limits, and audit) — the agent never
holds credentials directly.

```
Agent brain (LLM)  --intent-->  Connector Gateway  --MCP-->  Slack / GitHub / PagerDuty / …
        ▲                              │
        └────────── result ───────────┘   (gateway audits every call, enforces autonomy level)
```

### 5.2 Slack — the anchor integration (the Comms agent)

Slack is the flagship external integration because it is where many real teams already are, and
it closes the loop between the office and the real team. Projex/PragChat is the product's native
project/chat surface: it should expose the same operational model even when the external Slack
connector is disabled or unavailable.

**Inbound (Slack → office):**
- New/important Slack messages surface as the **Comms agent's** state: its monitor shows the top
  threads; a mention that needs you makes Comms turn to the aisle with a "needs you" status.
- The lobby **console** aggregates: "3 Slack threads awaiting reply, 1 mention of you."

**Outbound (office → Slack):**
- You tell Comms "let the team know the build is green" → Comms drafts, shows you the message on
  its monitor, and on approval posts to the channel (autonomy `ask-approval` by default).
- Any agent can *request* a broadcast; Comms is the single sender (one audited egress to Slack).

**Round-trip (the magic):**
- A teammate in Slack types "@office what's prod status?" → the request enters as a **world
  event** → Ops composes an answer from Datadog/PagerDuty → Comms replies in-thread. You watched
  Ops walk the data to Comms. **The office answered Slack, and you saw it happen.**

**Slack as a remote control:** slash-style commands in Slack (`/office dispatch research "…"`)
create tasks in the office even when you're not "in" the game — the office is a persistent
service; the 3D view is one window onto it.

**Projex/PragChat as the native control room:** the same dispatch can happen in Projex/PragChat
through project tasks, agent DMs, team channels, approval cards, mentions, and slash-style
commands. It should show exactly the same task, approval, event, and audit state that the 3D
office renders through agents, consoles, monitors, and voice.

### 5.3 Other connectors (same pattern)

| Agent | Connector | Representative actions (autonomy) |
|-------|-----------|-----------------------------------|
| Code | GitHub | open PR (ask), comment (act), merge (ask) |
| QA | GitHub Checks / CI | read status (act), re-run (act), gate release (ask) |
| Ops | PagerDuty / Datadog | read incidents (act), ack page (ask), page on-call (ask) |
| Research | Notion / web / code search | read (act), write doc (ask) |
| Comms | Slack / Gmail / Calendar | read (act), send (ask) |
| Orchestrator | Linear / Jira | create/route issues (ask) |

**Registry-driven:** the office discovers available connectors from the workspace's MCP registry;
equipping a tool to an agent is config, not code. New connector → new capability for whichever
agent it fits.

---

## 6. System design

Applying the `engineering:system-design` framework.

### 6.1 Requirements

**Functional**
- FR-A Manage N agents (target 8/office, matches `bot_mask`; design for more via multiple offices).
- FR-B Observe every agent's live state (task, status, last action) in-world.
- FR-C Inspect, engage, brief/dispatch, interrupt, approve, hand off, review — all spatial (§3).
- FR-D Agents operate real connectors through a gateway with per-agent/per-tool autonomy (§5).
- FR-E Projex/PragChat exposes the native surface: projects/tasks plus Slack-like channels,
  threads, mentions, agent DMs, approvals, dispatch, status, and searchable history.
- FR-F Slack round-trip: inbound surfacing + outbound send + remote dispatch (§5.2).
- FR-G Persistent office service; Projex/PragChat and the 3D client are views; headless/remote control possible.
- FR-H Voice: speak to agents (ASR), hear them (TTS), anchored to position.
- FR-I Memory: per-agent session + durable knowledge; auditable action log.

**Non-functional**
- NFR-A Real-time feel: observe loop ≥ 6 Hz; engage→response < 2 s for cached tools.
- NFR-B Local-first cognition (Ollama/MLX, `gemma3:4b` default) — offline, zero per-token cost
  for idle reasoning; cloud models optional for hard tasks.
- NFR-C Safety: no autonomous side-effecting action without the declared autonomy level; every
  connector call audited; human-present gate for `ask-approval`.
- NFR-D Determinism where it matters: world/setup reproducible (SPEC invariants); agent behavior
  intentionally not, but every run replayable from the event log.
- NFR-E Resilience: an agent brain or connector failing degrades to a status, never crashes the
  office or the game.
- NFR-F macOS-first (shipped port), Slack/connectors cross-platform via the service.

**Constraints**
- Single-developer cadence; build on the shipped maps, bridge, llm-play, voice pipeline.
- Engine is a decompiled C game; additive bridge hooks only (no rewrite). macOS `pd.arm64`.

### 6.2 High-level architecture

```
Projex/PragChat (project management + Slack-like workspace)
  projects · tasks · channels · threads · agent DMs · approval cards
        │  Office Service API / events
        ▼
Office Service (persistent, headless-capable)
  Simulation Director · Agent Brains · Task Queue · Approvals
  World Event Bus · Memory Store · Audit Log · Connector Gateway
        ▲                         │                         ▲
        │ observe/act bridge      │ MCP tool calls           │ webhooks / polls
        │                         ▼                         │
Perfect Dark 3D office tab    Slack/GitHub/Linear/...   External ingress
  G5 / CI lobby · agents       Comms-owned Slack egress   Slack events, alerts
  HUD/billboards · voice       audited connector calls    remote dispatch
```

**Projex/PragChat and the 3D client are views**, not the brain. The **Office Service** is the
durable core: it runs the director, the agent brains, the task/approval/memory/audit stores, the
event bus, and the connector gateway. This is what makes "manage from Projex/PragChat while the
game is closed," "open a 3D office tab when presence helps," and "replay a day" possible.

### 6.3 Data flow — one dispatch, end to end

```
You walk to Research → engage → say "find who owns the vault-log service"
  → Director/Orchestrator? no; you're facing Research → Research brain gets {intent, context}
  → brain plans: search code + Notion → tool intents to Gateway (autonomy: act, read-only)
  → Gateway calls MCP (code search, Notion) → results → brain summarizes
  → Office Service: task result stored, audit logged, event "research.done" on bus
  → /act: Research says the answer (TTS), monitor shows the doc link, console badge clears
  → if answer implies a change: Research hands off to Code (bus msg) → Code's desk lights up
```

### 6.4 API contracts

**Engine bridge (extends the shipped `:8780`)** — additive to `llm_bridge.c` / `llm_observe.c`:

| Endpoint | Change | Purpose |
|----------|--------|---------|
| `GET /observe` | add `agents[]` (chrnum, role, pos, facing, player_dist, state) | client & director see office agents (LLM_CONVERSATION_LAYER §3a) |
| `POST /act` | add `agents[]: {chrnum, say?, status?, face_player?, anim?}` | project utterance/status/posture onto an agent |
| `GET /health` | (unchanged) | liveness |

**Office Service API (new, localhost + optional authed remote):**

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/agents` | roster + live state (task, status, autonomy, tools) |
| `POST` | `/agents/{id}/dispatch` | create a task `{intent, context}` (also how Slack remote-dispatch enters) |
| `POST` | `/agents/{id}/interrupt` | preempt current work (engage) |
| `GET` | `/tasks` / `GET /tasks/{id}` | task queue + result |
| `GET` | `/approvals` · `POST /approvals/{id}` | pending human-present approvals; approve/deny |
| `GET` | `/events` (SSE) | world event stream (approaches, hand-offs, Slack inbound, alerts) |
| `POST` | `/events` | inbound event (webhook ingress normalizes here) |
| `GET` | `/audit` | every connector call + decision, replayable |

**Projex/PragChat client contract (new):** render Office Service state as project/task state plus
Slack-like `channels`, `threads`, `mentions`, `agent_dms`, `approval_cards`, `task_cards`, and
`event_history`. Sending a message, slash command, approval decision, project task update, or
agent DM becomes an Office Service dispatch/approval/event, not a separate chat-only state
machine.

**Connector Gateway (internal):** `invoke(agent_id, connector, action, args)` → checks autonomy
+ scope, calls MCP, records audit, returns result. One choke point for auth, rate limits, safety.

### 6.5 Data model

```
Agent    { id, role, chrnum, persona, model, tools[], autonomy{tool:level}, voice, home_pad, state }
Project  { id, name, owner?, linked_agent_ids[], status, channels[], task_ids[] }           # Projex
Channel  { id, type(team|agent|incident|project), members[], topic, linked_agent_ids[] }    # PragChat
Thread   { id, channel_id, subject, task_id?, messages[], unread_for[], mentions[] }        # PragChat
Task     { id, agent_id, intent, context, status(queued|running|blocked|awaiting_approval|done|failed),
           result, artifacts[], created_by(human|agent|prag_chat|slack), created_at }
Approval { id, task_id, agent_id, action, args, risk, status(pending|approved|denied), decided_by }
Memory   { agent_id, session[], durable{knows[], withholds[]} }         # per LLM_CONVERSATION_LAYER §5
Event    { id, type(approach|handoff|slack.msg|alert|task.*), from, to, payload, ts }  # append-only bus
Audit    { id, agent_id, connector, action, args_hash, result_hash, autonomy, human, ts }
```

### 6.6 Deep dives

- **Dispatch & routing.** Facing an agent scopes the dispatch to it; if you address the room
  (from the console), the **Orchestrator** routes by role/tool fit. Tasks are queued per agent;
  the Orchestrator can rebalance and surface blockers.
- **Approvals (human-present gate).** Any `ask-approval` action stages an `Approval`; it can only
  be cleared by a human interaction in-world (walk to the agent, or to **Security** for a batch
  review) or an authenticated remote approve. This is the core safety UX — side effects require
  presence.
- **Event bus & hand-offs.** Append-only log; agents subscribe to relevant types (an agent sees
  only its neighbourhood + addressed messages — the sliced perception from LLM_CONVERSATION_LAYER
  §7, which is what enables realistic hand-offs and "the guard heard you").
- **Projex/PragChat ingress.** User messages, project task changes, mentions, agent DMs, slash
  commands, and approval-card decisions normalize to `Event`s; dispatch creates `Task`s and every
  write path is audited.
- **Slack ingress.** Webhooks normalize to `Event`s; the Comms agent owns Slack egress (single
  audited sender). Remote dispatch (`/office …`) is just an `Event` that creates a `Task`.
- **Idle cost control.** Agents re-plan on events, not on a busy timer; idle agents cost nothing.
  Only engaged/working agents run the model — 8 agents are cheap locally.

### 6.7 Scale & reliability

- **Per office:** 8 agents (engine `bot_mask`), one director, one gateway. Comfortably real-time
  on a local model. **Fleet scale:** more agents = **more offices** (rooms/stages), federated by
  the service — the spatial metaphor scales by architecture, not by cramming a room.
- **Failure isolation:** a brain exception → agent shows `error` status, others unaffected; a
  connector outage → tool disabled, agent degrades to `suggest`; the game never blocks on the
  service (bridge already tolerates a missing sidecar — orchestrator `_is_bridge_down`).
- **Replay:** the event + audit logs make any session reconstructable for debugging and trust.

### 6.8 Trade-offs (made explicit)

| Decision | Chosen | Why / cost |
|----------|--------|-----------|
| Brain location | Service, not engine | Persistence, remote control, replay; cost: a running sidecar |
| Cognition | Local-first (Ollama/MLX) | Offline, free idle, private; cost: weaker than frontier models — escalate hard tasks to cloud |
| Perception | Sliced per agent | Enables secrets/rumor/realistic hand-offs; cost: more plumbing than god-view |
| Safety default | `ask-approval` for side effects | Trust + auditability; cost: friction — mitigated by human-present being *fun* here |
| Scale | Multiple offices | Keeps each room legible; cost: cross-office coordination is future work |
| Native host | Projex/PragChat over Office Service | Reuses project management, chat, local model, memory, and voice surfaces; cost: must keep host and 3D state synchronized |
| Slack egress | Single sender (Comms) | One audited door; cost: Comms is a bottleneck — acceptable, it's the point |
| Engine changes | Additive bridge only | No fork rewrite; cost: some UI (billboards) constrained by engine capability |

---

## 7. A day in the office (the experience)

> You launch **Agent Office: dataDyne G5**. Ambient keyboard clatter. Eight agents at their
> desks. Over Ops's desk, a red status pulses. You walk over; Ops turns: *"Prod p99 is
> spiking — Datadog flagged it four minutes ago. Want me to page on-call?"* You say yes. Ops
> stages the page (it's `ask-approval`); a confirm floats up; you nod (press use). Ops pages;
> the audit log records it.
>
> You cross to Comms. Its monitor shows two Slack threads glowing. *"Marketing's asking when the
> feature ships. And someone @-mentioned you in #eng."* You say: "Tell marketing Friday, and
> summarize the #eng thread." Comms drafts both, shows you, you approve; it posts to Slack.
>
> At the console you pull the fleet overview: Code has a PR waiting your review; Research
> finished the ownership question and left the doc on its monitor; QA is green. You drop one
> task on Research's desk on the way out — "dig into the p99 root cause with Ops" — and Research
> walks over to Ops. You close the game. An hour later a teammate types `/office status` in
> Slack; the office answers, because it never stopped running.

That is the product: **you managed eight AI agents and three tools in ninety seconds, by walking
a room.**

---

## 8. Lobby mode as the management dashboard

The shipped lobby (SPEC §7) is the MVP surface; this vision extends it minimally:

| Shipped | Extension for management |
|---------|--------------------------|
| Agent at fixed pad | + floating status billboard (state, current task one-liner) |
| Z-target status line | + inspect panel (task, last action, tools, autonomy) |
| Console (Z) room overview | → **mission control**: fleet grid (busy/queued/blocked/waiting), dispatch-to-room |
| Proximity greeting | → engage handshake (agent pauses work, faces you, listens) |
| Peaceful solo | (unchanged) — a management space, never combat |
| One office | → multiple offices (G5 = team A, CI = team B); a door/warp between them (future) |

Crucially, **all of this rides the existing lobby-mode invariants** (Y≈35 walkable foyer,
no-door-transit reachability, retail geometry overlay). The management UX inherits the "walk up
without opening anything" law that lobby mode already enforces — which is *why* lobby mode is the
right foundation and not a full mission map.

The closest retail UX reference is Perfect Dark's Carrington Institute headquarters
walkaround at startup: a safe, navigable base where the player can orient, talk, train, and
choose the next action before entering a mission. Virtual Agent Office should inherit that
feeling of headquarters presence and readiness, then replace training/briefing content with
agent-management work.

---

## 9. Roadmap — from shipped NPCs to a control plane

Each phase is demoable and builds on the last; grounded in real components.

| Phase | Theme | Delivers | Status |
|-------|-------|----------|--------|
| **P0** | Static office | Lobby, 8 NPCs, Z-target, console, greeter, 2 variants | **shipped** · F1/F3 fixed |
| **P1** | Live brains | Per-agent LLM (llm-play), engage→talk, voice (C1–C4) | **C3 backend + dispatch written**; C4 voice open |
| **P2** | Real state | `/observe agents[]`, status billboards, inspect panel | **C1 engine written** (needs build); billboards open |
| **P3** | Dispatch | Office Service: tasks, queue, interrupt, hand-off, event bus | **built + tested** (`service/`, 9/9); C2 act-inject written |
| **P4** | Projex/PragChat + tools | Project/task UI, Slack-like native UI, Connector Gateway + autonomy + audit; Comms↔Slack round-trip | core built/tested; Projex/PragChat integration + real MCP swap open |
| **P5** | Fleet ops | Ops↔PagerDuty/Datadog, Code/QA↔GitHub; approvals via Security | gateway + stubs done; real connectors open |
| **P6** | Persistent + remote | Headless service; Slack remote-dispatch; replay | event log is replayable; HTTP API + ingress open |
| **P7** | Multi-office | G5 + CI as two teams; cross-office routing | open |

**What landed this pass:** the P3/P4 **control-plane core is real and unit-tested** —
`tools/agent_office_llm/service/` (tasks, event bus, connector gateway with autonomy +
audit, dispatch, human-present approvals, Slack round-trip). The engine seams **C1**
(observe agents) and **C2** (act utterance injection) are written additively and need an
in-engine build. **C3** is now wired: the director can use llm-play backends for per-agent
replies and turns engage/utterance events into Office Service tasks with reply context.
What remains for a live P4 demo: Projex/PragChat UI over the Office Service, voice (C4), real
MCP connectors, and in-game verification.

**Definition of done for the pitchable build (P4):** open Projex/PragChat and see the agent
workspace as projects/tasks/channels/threads/agent DMs, launch the Perfect Dark office as a 3D
tab, walk to Ops (it reports a real Datadog signal), walk to Comms (it shows the same threads
that need attention), approve a reply in-world or in Projex/PragChat, and see one audited Slack
egress. Real agents, real tools, managed through synchronized project, chat, and 3D views.

---

## 10. Success metrics

- **Legibility:** time to answer "what is my fleet doing?" — target < 5 s (one look at the room/console) vs. minutes of tab-scanning.
- **Dispatch friction:** actions to delegate a task — target ≤ 2 (approach + speak) vs. context-switch + type.
- **Trust:** % of side-effecting actions that pass through an audited, human-present approval — target 100%.
- **Presence value:** can a new observer, watching for 60 s, correctly state who's busy/blocked/waiting? (qualitative "read the room" test.)
- **Round-trip:** office answers an inbound Slack request end-to-end without you touching a terminal.
- **Surface sync:** a project task, approval, or agent message created in Projex/PragChat
  appears in the 3D office, and the equivalent in-world action appears back in Projex/PragChat,
  target < 1 s.

---

## 11. Risks & open questions

| Risk / question | Note |
|-----------------|------|
| Engine UI ceiling | Floating billboards / rich panels may strain the HUD; may need a diegetic monitor render or a companion overlay. Prototype early. |
| Novelty vs utility | The game must not add *friction* to management. Law: any action must be faster than the dashboard equivalent, or it's cut. |
| Safety of autonomy | Default `ask-approval`; human-present gate; single audited Slack egress. Never let `act` touch money/prod-destructive ops. |
| Local model capability | `gemma3:4b` is fine for triage/dispatch; escalate hard reasoning to a cloud model per task. |
| Perception scope | Sliced (neighbourhood) vs god-view per agent — sliced enables realism but more plumbing (decide before P3 hardens). |
| Spatial scale | One room caps at ~8 legibly; fleets grow by offices, not crowding. Cross-office UX is P7. |
| Who owns Slack egress | Comms as sole sender (bottleneck by design) vs. per-agent send. Start single-sender. |
| Turn-taking / voice | Push-to-talk near an agent first; always-listening later. |
| Host boundary | Prefer Projex/PragChat for project/chat UX if it owns that surface already; avoid duplicating project management inside the Perfect Dark kit. |

---

## 12. Relationship to the other docs

| Doc | Role relative to this vision |
|-----|------------------------------|
| [`SPEC.md`](./SPEC.md) | The shipped P0 contract (maps, agents, lobby, registration). This vision extends it forward. |
| [`SPEC_AUDIT.md`](./SPEC_AUDIT.md) | Conformance of P0; fix P0 (e.g. F1 spawn collision) before layering P1+. |
| [`LLM_CONVERSATION_LAYER.md`](./LLM_CONVERSATION_LAYER.md) | The P1–P2 engine/sidecar seams (observe agents, `act.say`, brains, voice) this vision builds dispatch/tools on. |
| [`../../../llm-play/VISION.md`](../../../llm-play/VISION.md) | The "world for LLMs" north star; this doc is its management-focused specialization. |
| `tools/agent_office_llm/` | The director scaffold that grows into the Office Service (§6.2). |

---

## Change log

| Date | Change |
|------|--------|
| 2026-07-02 | Initial vision & product spec — "3D game interface for managing AI agents," lobby-as-control-plane, hybrid tool-operating agents, Slack-anchored connector model, full system design + roadmap. |
