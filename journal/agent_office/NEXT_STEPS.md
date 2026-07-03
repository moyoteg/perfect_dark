# Virtual Agent Office — status & next steps

> **Source of truth:** [`SPEC.md`](./SPEC.md) — all contracts, acceptance criteria, and architecture live there.  
> **Development mode:** Spec-driven — implement against SPEC sections; update SPEC when contracts change.  
> Session history: [`SESSION_NOTES.md`](./SESSION_NOTES.md)

**Last updated:** 2026-07-02 — SPEC created; lobby mode + static retail doors/lifts.

## Locations

| Variant | Stage | Geometry | Launch |
|---------|-------|----------|--------|
| **dataDyne G5** | `0x83` `STAGE_AGENT_OFFICE` | ROM `bg_depo` | `./scripts/play-agent-office.sh` |
| **Carrington Institute** | `0x84` `STAGE_AGENT_OFFICE_CI` | ROM `bg_dish` | `./scripts/play-agent-office-ci.sh` |

Both variants: eight `TEAM_NONCOMBAT` agents, Z-target HUD status lines, tagged lobby
console, **retail doors in MP setup (static/deactivated)**, Electron location picker.
CI also includes **two retail lift assemblies** (visual + collision; not rideable).

See [`SPEC.md` §7](./SPEC.md#7-spawn--lobby-model) for pad tables and [`SPEC.md` §8](./SPEC.md#8-door--lift-model) for door/lift contracts.

## Quick launch

```bash
cmake --build build --target pd_headers -j8   # after lang JSON edits
cmake --build build --target pd -j8           # after C changes (lang.c, player.c, …)
./scripts/play-agent-office.sh
./scripts/play-agent-office-ci.sh
./scripts/launch-agent-office-app.sh
```

Validate / deploy only:

```bash
python3 tools/pdmap.py validate agent_office
python3 tools/pdmap.py validate agent_office_ci
python3 tools/pdmap.py build agent_office --deploy
python3 tools/pdmap.py build agent_office_ci --deploy
```

Automated checks (no game): [`SPEC.md` §13](./SPEC.md#13-verification--test-plan)

```bash
python3 tests/test_agent_office_ailist.py
```

## Done (baseline v1 — see SPEC §2 acceptance criteria)

- [x] G5 + CI maps with retail geometry overlay (`SKIP_SEG/TILES/PADS`)
- [x] Eight agents, Z-target examine, console (Z) interact
- [x] Relaunch loop fix (pgrep guards, no `open -na`, Electron `launchInFlight`)
- [x] hudmsg SIGSEGV fix (lang banks + `aiShowHudmsg` null guard)
- [x] CPU freeze fix (deactivated doors + `doorTick` skip in `propobj.c`)
- [x] `g_Stages[92]` size sync
- [x] G5 spawn ground snap; CI Y≈460 fall-through → lobby spawns
- [x] Lobby mode redesign
- [x] Door sibling root cause; **restored static doors** + CI lifts
- [x] Peaceful explore default (`--solo`, `bootmp.c` weapon clear)
- [x] Electron app with G5/CI location picker + combat-sims opt-in
- [x] MP menu human-readable arena names (`lang.c` sentinels)
- [x] Custom G5 console/Comms copy; lang auto-deploy in play scripts
- [x] Kit Hub actions for G5 + CI; `PERFECT_DARK_KIT.md` section
- [x] Proximity greeting on Security (`greet_text`, ailist regression test)
- [x] **SPEC.md** — comprehensive product + engineering spec

## Live LLM conversation layer (Phase 2 — [`LLM_CONVERSATION_LAYER.md`](./LLM_CONVERSATION_LAYER.md))

Static briefing NPCs → per-character LLM agents you can approach and talk to.

- [x] Build spec: [`LLM_CONVERSATION_LAYER.md`](./LLM_CONVERSATION_LAYER.md)
- [x] Runnable scaffold: `tools/agent_office_llm/` (`--dry-run`)
- [x] **C1** engine: `/observe` emits `agents[]` — `port/src/llm_observe.c` **(written; needs build)**
- [x] **C2** engine: `/act` accepts `agents[].say` — `port/src/llm_bridge.c` **(written; needs build)**
- [x] **C3** brain: llm-play backend replies (`--llm`) + director → `OfficeService.dispatch`
- [ ] **C4** voice: wire `voice_pipeline/` (ASR in, TTS out)
- [ ] **C5** memory + `face_player` + world events

## Vision control plane (Phase 3–4 — [`VISION_AND_PRODUCT.md`](./VISION_AND_PRODUCT.md))

3D interface for managing AI agents; office = control plane; Slack-anchored tools.

- [x] Vision & product spec: [`VISION_AND_PRODUCT.md`](./VISION_AND_PRODUCT.md) (system design, roadmap P0–P7)
- [x] **Office Service core** — `tools/agent_office_llm/service/`: tasks, event bus, connector
  gateway (autonomy + audit), dispatch, human-present approvals, Slack round-trip. **11/11 tests**
  (`tests/test_office_service.py`)
- [ ] Real MCP connectors behind the gateway (Slack first) — swap stub `.call` bodies
- [x] Director → Office Service wiring (engage/utterance → `Task`) [C3]
- [ ] HTTP API + webhook ingress for remote/Slack dispatch (P6)
- [ ] Status billboards / inspect panel in-world (P2 client)

## Fixes this pass (SPEC_AUDIT)

- [x] **F1** spawn/agent pad collision — repointed alts (G5 `0x07`, CI `0x02`); SPEC §7 + AC-6.5
- [x] **F3** null-guard `hudmsgCreateWithColour` variants (`chraicommands.c`)

## Next steps (open — track against SPEC §14)

- [ ] **In-game verify:** F1 spawn pads walkable; menu names, copy, greeter (SPEC V-1–V-9)
- [ ] **In-game verify:** C1/C2 — observe shows `agents[]`, `/act agents[].say` shows a HUD line
- [ ] **In-game verify:** static door meshes G5 + CI (SPEC V-5, V-8)
- [ ] Openable doors + briefing wing access (SPEC §14 Phase 3)
- [ ] Functional CI elevators (SPEC §14 Phase 4)

When a contract changes, update **`SPEC.md` first**, then this checklist.
