# Virtual Agent Office — status & next steps

> **Source of truth:** [`SPEC.md`](./SPEC.md) — all contracts, acceptance criteria, and architecture live there.  
> **Development mode:** Spec-driven — implement against SPEC sections; update SPEC when contracts change.  
> Session history: [`SESSION_NOTES.md`](./SESSION_NOTES.md)

**Run until the dream is true:** paste the single master prompt from
[`LONG_TERM_FINAL_GOAL_PROMPT.md`](./LONG_TERM_FINAL_GOAL_PROMPT.md)
(Agile loop + R0–R7 + §2.6 phenomenal demo stop condition). llm-play mirror:
[`../../../llm-play/docs/AGENT_OFFICE_MASTER_PROMPT.md`](../../../llm-play/docs/AGENT_OFFICE_MASTER_PROMPT.md).

**Projex 1.0.0 add-on:** packaged at
[`../../../../../Tooling/Projex/addons/virtual-agent-office/`](../../../../../Tooling/Projex/addons/virtual-agent-office/)
(also symlinked to `~/.projex/addons/virtual-agent-office`). In Projex → **Add-Ons & Apps → Rescan → Virtual Agent Office**.

**Last updated:** 2026-07-28 — Firebase Hosting scaffold locked ([`HOSTING.md`](./HOSTING.md)): site `pragcore-vao`, URL `vao.pragcore.com`, Auth/`tenantId` shared with FC, Firestore `vao-prod`. Prior: overnight play path + multi-tenant FC-aligned ([`MULTI_TENANT.md`](./MULTI_TENANT.md)).

## Locations

| Variant | Stage | Geometry | Launch |
|---------|-------|----------|--------|
| **dataDyne G5** | `0x83` `STAGE_AGENT_OFFICE` | ROM `bg_depo` | `./scripts/play-agent-office.sh` |
| **Carrington Institute** | `0x84` `STAGE_AGENT_OFFICE_CI` | ROM `bg_dish` | `./scripts/play-agent-office-ci.sh` |
| **Masonic blank office (lab)** | `0x85` `STAGE_AGENT_OFFICE_LAB` | mod ±5000 marker-floor box | `./scripts/play-masonic-office-sandbox.sh` (`pd.office`) |

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
- [x] **C1** engine: `/observe` emits `agents[]` — `port/src/llm_observe.c` (rebuild done 2026-07-27)
- [x] **C2** engine: `/act` accepts `agents[].say` — `port/src/llm_bridge.c` (rebuild done 2026-07-27)
- [x] **C3** brain: llm-play backend replies (`--llm`) + director → `OfficeService.dispatch`
- [x] **Kit launch:** Virtual Agent Office app has Start/Stop Live Director controls; Kit Hub has start/stop actions
- [x] **R1 presence:** `/act agents[].status` = `work|idle|talk` → `MA_AGENT_*`; observe reports `status`/`talking`/`player_dist`/`role_hint`; director seeds work, talk on approach, work on leave (`tests/test_office_director_presence.py`)
- [x] **FIX `/act agents[]` mutex deadlock (2026-07-27):** nested `g_LlmMutex` → `llmAgentSetStatusLocked` / `llmAgentEnqueueSayLocked` ([`FIX_2026-07-27_act_agents_mutex_deadlock.md`](./FIX_2026-07-27_act_agents_mutex_deadlock.md)); smoke agents act ~1–2ms on `:8782`
- [x] **FIX absolute `player.pitch` (2026-07-28):** tick-applied pitch reset + look_y±40 + office savedir no DualSense/mouse ([`FIX_2026-07-27_pitch_absolute_reset.md`](./FIX_2026-07-27_pitch_absolute_reset.md))
- [x] **Morning one-shot launch:** `llm-play/scripts/play-vao-morning.sh` (service + `pd.office` lab; optional director)
- [x] **C4 voice (partial):** director `listen_player` (env/stdin) + `speak` (spatial_tts / macOS say); Whisper ASR file path still open
- [x] **C5 memory:** per-agent memory files already on brains; face_player in C2/R1
- [x] **R3 diegetic monitors (service):** `GET /agents/:id/monitor` + fleet `embodied_agents[].monitor_text` + `perfect_menu_text`
- [x] **R4 HTTP API:** Office Service HTTP + Slack webhook/OAuth paths ship; real Slack when token installed
- [x] **R5 Flight Control client:** `flight-control/src/swarm/office-service-client.ts` + `/api/office/{health,fleet,embodied,dispatch}`
- [x] **C4 full ASR (code):** mic/`AGENT_OFFICE_ASR_WAV` → llm-play `voice_pipeline/asr.py` Whisper (`listen_player`); fixture + director tests PASS
- [x] **R3 Perfect Menu bind (code):** bridge polls `/fleet`, `g_OfficePerfectMenuDialog` + console (Z) HUD lines from `perfect_menu_text`
- [x] **R3 Perfect Menu relink:** `cmake --build build --target pd -j8` succeeded; `_g_OfficePerfectMenuDialog` / marquee / bridge symbols in binary
- [x] **R3 in-game visual verify (floor/bridge):** durable office floor PNGs — `llm-play/docs/recordings/vao-1.4.2/game/` (windowID; bridge `perfect_menu_text` overlay; crash-stable lobby)
- [x] **R3 Perfect Menu dialog PNG:** `BOOT_OPEN_CONSOLE=1` on lab `pd.office` — `llm-play/docs/recordings/vao-overnight-20260727/game/perfect-menu-dialog.png` shows Perfect Menu + live `Virtual Agent Office` / `live desks` (2026-07-28)
- [x] **R3 office boot crash fix:** null-guard W2S in `chrIsTargetAimingAtMe` + office HUD ticks (`tests/test_office_dm_hud_tick_guards_null_camera`)
- [x] **R5 service E2E:** FC-style `POST /dispatch` → Ops `monitor_text` + `perfect_menu_text` (live during office session; PD typing juice still open)
- [x] **R6 host polish:** llm-play Office mode polls `:8791`; manager-facing hint/chip copy (“you walk the floor as manager”)
- [x] **R6 resilience UX:** Office chip tooltip shows fleet/approvals/perfect_menu/ASR degrade; pending approvals → `On·N` warn state
- [x] **R7 dual lobbies:** G5 + CI map variants already ship as separate stages
- [x] **R4 real Slack E2E:** live OAuth + PragCredentials connector gateway (`slack_connector`, `pagerduty_connector`, `github_connector`) with stage/approve Comms post and deterministic offline fallback (`tests/test_slack_api.py`, `tests/test_office_hardening_r7_multitenant.py`)
- [x] **R5 full PD E2E:** FC dispatch → PD typing + dual approval verified (`tests/test_office_examine_bridge.py`, `tests/test_office_api_regression.py`, `tests/test_office_multitenant_stress.py`)
- [x] **R7 social bus (service):** `POST /social/route` + `GET /social/feed` (g5↔ci rumor/guard_report/handoff via EventBus)
- [x] **R7 FC social proxy:** `flight-control` `OfficeServiceClient.socialRoute/socialFeed` + `/api/office/social/{route,feed}`
- [x] **R7 in-world social bus:** PD/director live background ticker (`OfficeDirector._tick_social_bus`, earshot perception slicing `slice_observation_for_agent`, and `/act` billboard projection)
- [x] **§2.6 pitchable phenomenal demo:** 269/269 tests green across tri-pillar platforms, high-fidelity screen recording (`walkthrough.mp4`), multi-viewport screenshots, and verified in-game frames (`office-floor-typing.png`, `perfect-menu-dialog.png`, `security-z-approval.png`)

## Vision control plane (Phase 3–4 — [`VISION_AND_PRODUCT.md`](./VISION_AND_PRODUCT.md))

3D interface for managing AI agents; office = control plane; Slack-anchored tools.

- [x] Vision & product spec: [`VISION_AND_PRODUCT.md`](./VISION_AND_PRODUCT.md) (system design, roadmap P0–P7)
- [x] **Office Service core** — `tools/agent_office_llm/service/`: tasks, event bus, connector
  gateway (autonomy + audit), dispatch, human-present approvals, Slack round-trip. **11/11 tests**
  (`tests/test_office_service.py`)
- [x] Real MCP/HTTP connectors behind the gateway (`slack_connector`, `pagerduty_connector`, `github_connector`) with PragCredentials resolution and offline simulation fallback
- [x] Director → Office Service wiring (engage/utterance → `Task`) [C3]
- [x] HTTP API + webhook ingress for remote/Slack dispatch (P6) (`tests/test_office_service_http_api.py`, `tests/test_office_multitenant_stress.py`)
- [x] Status billboards / inspect panel in-world (`OfficeDirector._agent_billboard` + `/agents/:id/monitor`)

## Fixes this pass (SPEC_AUDIT)

- [x] **F1** spawn/agent pad collision — repointed alts (G5 `0x07`, CI `0x02`); SPEC §7 + AC-6.5
- [x] **F3** null-guard `hudmsgCreateWithColour` variants (`chraicommands.c`)
- [x] **F4** office HUD aim SIGSEGV — null-guard W2S / skip aim until player+camera ready (`chraction.c`, `chraicommands.c`, `camera.c`; [`CRASH_2026-07-27_office_hud_aim.md`](./CRASH_2026-07-27_office_hud_aim.md))
- [x] **F5** lab `bodyAllocateChr`/`fileLoad` SIGSEGV — lab `-ma8192` blew 16MB memp; budget `-ma700` + null/OOM guards on DMA/model load ([`CRASH_2026-07-27_body_allocate_fileload.md`](./CRASH_2026-07-27_body_allocate_fileload.md))

## Next steps (open — track against SPEC §14)

- [x] **Multi-tenant design + light scaffold:** [`MULTI_TENANT.md`](./MULTI_TENANT.md); `tenants.json`; `service/tenant.py`; HTTP `/tenants` + `X-Office-Tenant`; VAO tenant select stub; `tests/test_office_tenant_paths.py`
- [x] **Multi-tenant FC alignment:** document FC L→R + seal; registry `name` / `fc_tenant_id` / `sealed` / `metadata`; FC client + `/api/office/*` forward sealed tenant; health/tenants seal semantics; path isolation tests
- [x] **VAO Firebase Hosting scaffold:** [`HOSTING.md`](./HOSTING.md) + `PragCore/vao-web/` (site `pragcore-vao` created; no Hosting deploy); Auth/`tenantId` shared with FC; Firestore DB id `vao-prod`
- [ ] **VAO Hosting next:** create Firestore `vao-prod`; deploy hosting placeholder; attach custom domain `vao.pragcore.com`; soft marketing catalog link only (see HOSTING.md §7)
- [x] **Multi-tenant next rung (FC seal wire-up):** per-tenant in-memory `OfficeService` map; resolve `fc_tenant_id` aliases on every request; registry-enforced HTTP `404` on unknown tenants + `POST /tenants` admin API; memory/account-pool under tenant root; second-tenant isolation evidence (`tests/test_office_hardening_r7_multitenant.py`)
- [ ] **Open (product):** relaunch vs Exit-to-picker for tenant switch; Slack 1:1 vs shared team (see MULTI_TENANT.md §13)
- [x] **Masonic blank-office path:** decided PARALLEL → lab `0x85`; ensure/play side-binary scripts; SPEC §16 + [`MASONIC_OFFICE_SANDBOX.md`](./MASONIC_OFFICE_SANDBOX.md)
- [x] **Lab boot smoke (≥10s):** `pd.office --boot-stage 0x85` no SIGSEGV / no memp Req:8388608 (cert race not involved)
- [x] **Lab vertical slice smoke:** PNG `llm-play/docs/recordings/vao-masonic-lab/masonic-lab-floor.png` — computer prop + `[OFFICE-BRIDGE] PERFECT_MENU_TEXT…8 DESKS` (beside cert)
- [x] **Lab floor polish:** `SEG_MODE=marker` grey floor + aisle spawn/pitch; PNGs `masonic-lab-floor.png` + `masonic-lab-perfect-menu.png` (`BOOT_OPEN_CONSOLE`)
- [ ] **In-game verify:** F1 spawn pads walkable; menu names, copy, greeter (SPEC V-1–V-9)
- [x] **In-game verify:** C1/C2 observe `agents[]` + `/act agents[].status|say` (mutex smoke 2026-07-27; HUD line still visual)
- [x] **In-game verify:** bright desk typing PNG + Security Z Approve/Deny card — morning close ACCEPT (`office-floor-typing.png` seated Ops; `security-z-approval.png` in-frame `Z Approve · B Deny`); pos warp still available ([`FIX_2026-07-28_player_pos_warp.md`](./FIX_2026-07-28_player_pos_warp.md))
- [x] **Stick translate walk:** `CONTROLMODE_PC` remap in `llm_player.c` + morning `SwapSticks=1` — smoke `stick-walk-smoke.json` dist_xz≈743 ([`FIX_2026-07-28_stick_walk_pc_remap.md`](./FIX_2026-07-28_stick_walk_pc_remap.md))
- [ ] **In-app verify:** Virtual Agent Office.app launches from Perfect Dark Kit and Start/Stop Live Director updates status
- [ ] **In-game verify:** static door meshes G5 + CI (SPEC V-5, V-8)
- [ ] Openable doors + briefing wing access (SPEC §14 Phase 3)
- [ ] Functional CI elevators (SPEC §14 Phase 4)

When a contract changes, update **`SPEC.md` first**, then this checklist.
