# Virtual Agent Office - Long-Term Final Goal Prompt

Use this prompt to restart or continue the long-term build without losing the product
direction. It is intentionally a north-star execution prompt, not a narrow task ticket.

## Prompt

```text
You are Codex working in the Perfect Dark AIO repository. Build toward the long-term
final goal for Virtual Agent Office:

Create a fully usable 3D game interface for managing AI agents. The player should open
Perfect Dark Kit, launch Virtual Agent Office, walk around a peaceful pre-mission lobby,
approach embodied AI agents at their desks, talk to them, inspect their work, assign
tasks, approve risky actions, and see real tool activity reflected in-world. The office
is the control plane.

Core product law:
- Use lobby walk-around / pre-mission hub mode as the primary experience.
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
1. Perfect Dark Kit opens Virtual Agent Office cleanly.
2. The player chooses dataDyne G5 or Carrington Institute from the Agent Office app.
3. Each office boots as a peaceful lobby hub with eight TEAM_NONCOMBAT agents:
   Director, Orchestrator, Research, Code, QA, Security, Ops, and Comms.
4. The player can walk to any agent, engage it by proximity or Z-target, and get a
   role-specific live response.
5. Each agent has a body, desk/home pad, role, brain, memory, voice identity, tool
   permissions, autonomy policy, and auditable action log.
6. The Office Director sidecar observes player + agent state, routes engagement to the
   right brain, posts agent utterances/status back into the game, and never breaks the
   static fallback when offline.
7. Voice works end to end: push-to-talk or proximity listen, ASR transcript, per-agent
   LLM reply, TTS playback, HUD/status fallback.
8. The Office Service is persistent and headless-capable. The 3D game is one client,
   not the only brain. Closing the game must not destroy task state, memory, events,
   approvals, or audit logs.
9. The Connector Gateway lets agents operate real tools through safe, audited MCP
   connector calls. Start with Slack as the anchor through Comms, then GitHub for
   Code/QA, PagerDuty/Datadog for Ops, Notion/docs/web for Research, and routing/task
   tools for Orchestrator.
10. Side-effecting tool actions default to ask-approval. Approvals should be cleared
    by an explicit human-present interaction in the office, especially through Security,
    or by authenticated remote approval when the headless service is enabled.
11. The console becomes mission control: fleet overview, queued/blocked/done states,
    pending approvals, recent events, and dispatch-to-room.
12. Agents show legible in-world state: idle, working, blocked, waiting for approval,
    done, or error. Use status billboards, HUD panels, monitor text, animation/posture,
    and console summaries as the engine allows.
13. Slack round-trip works: inbound Slack events surface through Comms; outbound Slack
    posts are drafted, approved, sent, and audited; remote Slack commands can dispatch
    work into the office.
14. The system is resilient. If an LLM backend, connector, voice component, or sidecar
    fails, the office degrades to visible status and static fallback behavior. The game
    must not crash or freeze.
15. G5 and CI eventually become multiple offices/teams with cross-office routing rather
    than crowded single-room scale.

Build roadmap to respect:
- P0 Static office: lobby, two variants, eight non-combat NPCs, Z-target, console,
  greeter, launchers. Preserve this.
- P1 Live brains: per-agent llm-play brains, engage to talk, voice in/out.
- P2 Real state: /observe agents[], /act agents[].say/status/face_player, status
  billboards, inspect panels.
- P3 Dispatch: Office Service tasks, queue, interrupt, hand-off, event bus, memory,
  approvals, audit.
- P4 Tools, Slack first: real connector gateway integration, Comms round-trip, safe
  approvals.
- P5 Fleet ops: Ops with PagerDuty/Datadog, Code/QA with GitHub and CI, Research with
  docs/web, Security as approval and policy desk.
- P6 Persistent remote control: HTTP API, webhook ingress, Slack remote dispatch,
  replayable event/audit history.
- P7 Multi-office: G5 and CI as separate teams/workspaces, cross-office routing and
  clear spatial scale.

Pitchable P4 demo definition:
Launch Perfect Dark Kit, open Virtual Agent Office, enter the peaceful G5 or CI lobby,
walk to Ops, and hear/see Ops report a real runtime signal. Walk to Comms and see real
Slack threads that need attention. Ask Comms to draft a reply, approve it in-world, and
confirm the message posts to Slack with an audit entry. The player managed real agents
and real tools by walking a room.

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
- Do not replace the spatial office with a normal dashboard or chat app.
- Do not require the user to leave the room for core management actions.
- Do not allow unaudited side-effecting connector calls.
- Do not break static Agent Office behavior when live AI is offline.

When in doubt, choose the path that makes this statement more true:
"I manage my AI workforce by walking into an office, reading the room, talking to the
right agent, and approving real work in a spatial, auditable, embodied control plane."
```

## Short Version

```text
Build Virtual Agent Office into a peaceful pre-mission lobby control plane for real AI
agents. The player should walk up to embodied agents, talk to them, dispatch work,
approve risky actions, and see real Slack/GitHub/Ops activity reflected in-world.
Combat Sim is only an optional stress test. Preserve P0 lobby behavior while advancing
P1-P7: live brains, voice, state billboards, Office Service dispatch, connector gateway,
Slack round-trip, persistent remote control, and multi-office routing. Verify end to
end and commit scoped slices.
```
