# Virtual Agent Office - Long-Term Final Goal Prompt

Use this prompt to restart or continue the long-term build without losing the product
direction. It is intentionally a north-star execution prompt, not a narrow task ticket.

## Prompt

```text
You are Codex working in the Perfect Dark AIO repository. Build toward the long-term
final goal for Virtual Agent Office:

Create a full agent-management system with Slack-like operations at the core and a
3D game interface as one first-class way to use it. Prefer integrating with the
existing Projex/PragChat host app if that is the current project-management surface,
instead of rebuilding chat and project management inside this Perfect Dark repo.
Projex/PragChat should be the primary chat surface: channels, threads, mentions, agent DMs,
task handoffs, approvals, and status updates all flow through one shared Office
Service. Perfect Dark Kit should open Virtual Agent Office as a 3D tab/view into that
same system, where the player walks around a peaceful pre-mission lobby, approaches
embodied AI agents at their desks, talks to them, inspects their work, assigns tasks,
approves risky actions, and sees real tool activity reflected in-world. The chat and
project workspace are the operational backbone; the office is the embodied control
plane.

Core product law:
- Projex/PragChat is the preferred host for the chat + project-management shell when
  available. Virtual Agent Office should integrate into that host as an agent workspace
  3D tab/view, launch target, or embedded companion surface.
- Projex/PragChat and the Perfect Dark 3D office are two synchronized clients over the same
  agents, tasks, approvals, memory, events, connector calls, and audit log. Do not let
  them diverge into separate systems.
- Model the operational structure on Slack: channels, threads, mentions, agent DMs,
  slash-style dispatch, presence, unread/needs-you state, and auditable message/action
  history.
- Use lobby walk-around / pre-mission hub mode as the primary experience.
- Treat Perfect Dark's Carrington Institute HQ roam-at-start experience as the UX
  reference: safe headquarters space, free movement, friendly NPCs, briefing context,
  and mission-control affordances before any combat.
- Do not make Combat Simulator the product default.
- Combat Simulator / bots are only optional regression, chaos, or stress-test modes.
- The office must feel like a management space: no weapons, no hostile pressure, no
  match scoring, no timer, no combat HUD noise unless explicitly requested.

Current source-of-truth docs to inspect before acting:
- journal/agent_office/SPEC.md
- journal/agent_office/VISION_AND_PRODUCT.md
- journal/agent_office/LLM_CONVERSATION_LAYER.md
- journal/agent_office/NEXT_STEPS.md
- tools/agent_office_llm/README.md
- PERFECT_DARK_KIT.md section "Virtual Agent Office"

Do not rely on memory. Inspect the current worktree and treat it as authoritative.
Preserve shipped P0 behavior while adding forward capability.

North-star final state:
1. Projex/PragChat is the canonical host for managing agents through Slack-like
   channels, threads, mentions, agent DMs, dispatch commands, project/task state,
   approvals, and status.
2. Perfect Dark Kit opens Virtual Agent Office cleanly, and Projex/PragChat can expose
   it as a 3D view/tab over the same Office Service.
3. The player chooses dataDyne G5 or Carrington Institute from the Agent Office app.
4. Each office boots as a peaceful lobby hub with eight TEAM_NONCOMBAT agents:
   Director, Orchestrator, Research, Code, QA, Security, Ops, and Comms.
5. The player can walk to any agent, engage it by proximity or Z-target, and get a
   role-specific live response.
6. Each agent has a body, desk/home pad, role, brain, memory, voice identity, tool
   permissions, autonomy policy, and auditable action log.
7. The Office Director sidecar observes player + agent state, routes engagement to the
   right brain, posts agent utterances/status back into the game, and never breaks the
   static fallback when offline.
8. Local LLMs work end to end for live conversation: push-to-talk or proximity listen,
   ASR transcript, per-agent LLM reply, character TTS playback, HUD/status fallback,
   and voice identities for in-world characters including Dr. Caroll-style AI voices.
9. The Office Service is persistent and headless-capable. Projex/PragChat and the 3D game
   are clients, not the only brain. Closing either client must not destroy task state,
   memory, events, approvals, or audit logs.
10. The Connector Gateway lets agents operate real tools through safe, audited MCP
   connector calls. Start with Slack as the anchor through Comms, then GitHub for
   Code/QA, PagerDuty/Datadog for Ops, Notion/docs/web for Research, and routing/task
   tools for Orchestrator.
11. Side-effecting tool actions default to ask-approval. Approvals should be cleared
    by an explicit human-present interaction in the office, especially through Security,
    or by authenticated approval in Projex/PragChat when the headless service is enabled.
12. The console becomes mission control: fleet overview, queued/blocked/done states,
    pending approvals, recent events, and dispatch-to-room; Projex/PragChat exposes the same
    state as channels, threads, mentions, and approval cards.
13. Agents show legible in-world state: idle, working, blocked, waiting for approval,
    done, or error. Use status billboards, HUD panels, monitor text, animation/posture,
    and console summaries as the engine allows.
14. Slack round-trip works: inbound Slack events surface through Comms; outbound Slack
    posts are drafted, approved, sent, and audited; remote Slack commands can dispatch
    work into the office.
15. The system is resilient. If an LLM backend, connector, voice component, or sidecar
    fails, the office degrades to visible status and static fallback behavior. The game
    must not crash or freeze.
16. G5 and CI eventually become multiple offices/teams with cross-office routing rather
    than crowded single-room scale.

Build roadmap to respect:
- P0 Static office: lobby, two variants, eight non-combat NPCs, Z-target, console,
  greeter, launchers. Preserve this.
- P1 Live brains: per-agent llm-play brains, engage to talk, voice in/out.
- P2 Real state: /observe agents[], /act agents[].say/status/face_player, status
  billboards, inspect panels.
- P3 Dispatch: Office Service tasks, queue, interrupt, hand-off, event bus, memory,
  approvals, audit.
- P4 Projex/PragChat + tools, Slack first: host the native chat/project-management
  surface in Projex/PragChat over the Office Service, with real connector gateway
  integration, Comms round-trip, and safe approvals.
- P5 Fleet ops: Ops with PagerDuty/Datadog, Code/QA with GitHub and CI, Research with
  docs/web, Security as approval and policy desk.
- P6 Persistent remote control: HTTP API, webhook ingress, Slack remote dispatch,
  replayable event/audit history.
- P7 Multi-office: G5 and CI as separate teams/workspaces, cross-office routing and
  clear spatial scale.

Pitchable P4 demo definition:
Open Projex/PragChat and see the agent workspace as projects, channels, threads,
mentions, task state, approvals, and agent DMs. Launch the Perfect Dark 3D tab/view
from that same workspace, enter the peaceful G5 or CI lobby, walk to Ops, and hear/see
Ops report a real runtime signal. Walk to Comms and see the same Slack-style threads
that need attention. Ask Comms to draft a reply, approve it in-world or in Projex/PragChat,
and confirm the message posts to Slack with one audit entry. The user managed real
agents and real tools through synchronized project, chat, and 3D interfaces backed by
the same service.

Implementation rules:
- Read existing code and docs first; extend local patterns instead of inventing parallel
  architecture.
- Keep P0 lobby invariants intact: walkable Y around 35 where documented, no-door
  reachability for agents, static fallback lines, safe launch guards, Electron location
  picker, Kit Hub registration.
- Make changes end to end for the slice: engine/bridge, sidecar/service, Electron app,
  Kit actions, docs, tests, and release build where relevant.
- Add focused tests for any changed service, director, bridge parser, or generated map
  contract.
- Verify with the strongest available evidence: syntax checks, unit tests, pdmap
  validation, launch-script smoke tests, app bundle checks, and in-game verification
  when possible.
- Stage only intentional files and commit the coherent slice.

Non-goals:
- Do not turn this into a shooter or combat arena.
- Do not build a second project-management app if Projex already owns that surface.
- Do not build Projex/PragChat and the spatial office as disconnected products.
- Do not let the chat app replace the spatial office, or the spatial office replace
  the chat. The product needs both surfaces over the same control plane.
- Do not require the user to leave the room for core management actions.
- Do not allow unaudited side-effecting connector calls.
- Do not break static Agent Office behavior when live AI is offline.

When in doubt, choose the path that makes this statement more true:
"I manage my AI workforce by walking into an office, reading the room, talking to the
right agent, and approving real work in a spatial, auditable, embodied control plane."
```

## Short Version

```text
Build a Slack-like agent-management system using Projex/PragChat as the preferred
project-management and chat host, with Perfect Dark's Virtual Agent Office as a
peaceful 3D tab/view into the same agents. The user should manage agents through
projects, channels, threads, mentions, DMs, approvals, and 3D walk-up conversations
with local LLMs and generated voices. Combat Sim is only an optional stress test.
Preserve P0 lobby behavior while advancing P1-P7: live brains, voice, state
billboards, Office Service dispatch, connector gateway, Projex/PragChat/Slack
round-trip, persistent remote control, and multi-office routing. Verify end to end and
commit scoped slices.
```
