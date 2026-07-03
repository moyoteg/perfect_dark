# Perfect Dark AIO — User Stories

**Parent spec:** [`SPEC.md`](SPEC.md)  
**API detail:** [`API_CONTRACTS.md`](API_CONTRACTS.md)  
**Verification commands:** [`ENVIRONMENTS.md`](ENVIRONMENTS.md) §6

Acceptance criteria IDs (`AC-*`) **must** appear in PR descriptions and agent task lists. Each criterion includes **procedure**, **pass/fail signals**, and **negative cases** where applicable.

---

## How to verify a story

1. Read the AC id in this file.
2. Run the **Procedure** steps exactly (release `.app` unless marked dev).
3. Grep logs per **Pass signals**; any **Fail signal** is a blocker.
4. Run **Negative case** when present — must not crash or duplicate spawn.
5. Reference AC id in commit/PR: `Fixes AC-ANIM-1.1`.

---

## Hub — Perfect Dark Kit

### US-HUB-1 — Single entry point

**As a** macOS mod author,  
**I want** one hub app that lists every kit tool,  
**So that** I don’t hunt for `.app` bundles in Finder.

| ID | Acceptance criterion | Procedure | Pass | Fail |
|----|---------------------|-----------|------|------|
| AC-HUB-1.1 | Hub reads `kit.json` and renders all `kitHub.wraps` entries | Open hub; count tool cards | 7 cards: Map Editor, Map Launcher, Anim Lab, Agent Office, Asset Upgrader, Replay Test, LLM Play | Missing card for non-optional app |
| AC-HUB-1.2 | Each card shows built / optional / dev badge | Inspect badges on each card | Built apps: `Available` or `Wrapped in kit`; optional missing: `Optional — not built` | Generic error with no badge |
| AC-HUB-1.3 | Hub survives ≥30 s idle | Launch hub; wait 30 s without interaction | Process alive; no crash dialog | `EXC_BREAKPOINT` or hub quit |

**Log check:** `tail -f ~/Library/Logs/PerfectDarkKit/kit-hub.log` — no `Unhandled rejection:` during AC-HUB-1.3.

---

### US-HUB-2 — Safe app launch

**As a** hub user clicking **Open Anim Lab**,  
**I want** only one child app instance to start,  
**So that** the hub and Anim Lab don’t spawn duplicate servers.

| ID | Acceptance criterion | Procedure | Pass | Fail |
|----|---------------------|-----------|------|------|
| AC-HUB-2.1 | 1200 ms cooldown per `appKey` | Double-click Open Anim Lab rapidly (5× in 1 s) | Log shows ≤1 `Launch animLab:` per 1.2 s; IPC returns `skipped: true` for rest | 5+ `Launch animLab:` in 1 s |
| AC-HUB-2.2 | Renderer disables button while pending | Click once; observe button during invoke | Button disabled until IPC returns | Multiple concurrent invokes |
| AC-HUB-2.3 | Failed `open` returns error object | Rename Anim Lab.app temporarily; click Open | Hub shows error status; `{ ok: false, error }`; hub alive | Hub crash |
| AC-HUB-2.4 | Wrapped apps resolve from Resources/Apps | Build full kit; launch Anim Lab from hub on machine without release copy | Opens wrapped path under hub `.app` | Falls back incorrectly when wrap exists |

**Negative case AC-HUB-2.N1:** Hammer-click Open Anim Lab for 10 s — hub and macOS must not spawn >1 Anim Lab process per 1.2 s window.

---

### US-HUB-3 — Pipeline actions

**As a** kit operator,  
**I want** to run build/validate/scenario scripts from the hub,  
**So that** I don’t switch to Terminal for routine tasks.

| ID | Acceptance criterion | Procedure | Pass | Fail |
|----|---------------------|-----------|------|------|
| AC-HUB-3.1 | All `actionGroups` appear | Scroll hub action sections | 4 sections: Build, Validate & Learn, Scenarios & Launch, Setup & Utilities; 18 actions total | Missing group or action |
| AC-HUB-3.2 | `requiresGame` disables when binary missing | Remove/rename `build/pd.arm64`; refresh hub | Play Matrix Battle, validateNext, etc. disabled | Enabled actions spawn failing scripts silently |
| AC-HUB-3.3 | Long-running vs sync feedback | Run `validateStatus` (sync) then `rebuildMapEditor` (detached) | Sync shows output tail; detached shows "started in background" | UI hang with no status |

**Action count reference:** see [`SPEC.md`](SPEC.md) §19.

---

### US-HUB-4 — Play from hub

**As a** player with a built binary,  
**I want** Play and Test Map buttons in the hub,  
**So that** I can smoke-test without the map editor.

| ID | Acceptance criterion | Procedure | Pass | Fail |
|----|---------------------|-----------|------|------|
| AC-HUB-4.1 | Play launches mod_allinone | Click Play | Log: `Launch game: … --moddir mods/mod_allinone`; game window | Wrong moddir |
| AC-HUB-4.2 | Test Map adds `--test-map` | Click Test Map | Command includes `--test-map` | Missing flag |
| AC-HUB-4.3 | Buttons disabled without binary | Hide binary; refresh | Both buttons disabled | Click launches error crash |

---

## PD Map Editor

### US-MAP-1 — Author and test loop

**As a** map author,  
**I want** to edit JSON and Test/Play in one window,  
**So that** I iterate quickly on Combat Sim arenas.

| ID | Acceptance criterion | Procedure | Pass | Fail |
|----|---------------------|-----------|------|------|
| AC-MAP-1.1 | Single Python backend per bootstrap | Open Map Editor; grep map-editor.log | One server spawn sequence per app launch | Multiple serve_editor on different ports same second |
| AC-MAP-1.2 | Test/Play uses `PDMAP_SEG_MODE=empty` | Test/Play from editor; inspect build env in log | No viewport seg sheet in FPS | Full seg sheet blocking view |
| AC-MAP-1.3 | Spawn pads Y ≥ 10 | Place spawn in editor; validate | pdmap validate passes; pads at Y≥10 in export | Y≤0 pads in deployed asset |
| AC-MAP-1.4 | Setup ailist 0x1000 | Deploy test map; inspect setup binary | mp_init_simulants present | Bots fail to spawn |

**Procedure AC-MAP-1.2 detail:** Default Test/Play must set or inherit `PDMAP_SEG_MODE=empty` (see `tools/pdmap/pipeline.py`).

**Automated probe:** `python3 journal/uff_viewer/validate_edit_play.py` (requires server on 8765–8775).

---

### US-MAP-2 — Distinct identity

| ID | Acceptance criterion | Procedure | Pass | Fail |
|----|---------------------|-----------|------|------|
| AC-MAP-2.1 | productName PD Map Editor | Check Dock tooltip and window title | "PD Map Editor" | "Electron" |
| AC-MAP-2.2 | Single-instance focus | Open editor twice from Dock | Second open focuses first window | Two Dock icons / two servers |

**Ports:** Editor server **8765–8775**; health `service: uff-editor`.

---

## PD Anim Lab

### US-ANIM-1 — Reliable startup

**As a** user opening Anim Lab from Finder or the hub,  
**I want** the app to start once and show the catalog,  
**So that** it doesn’t crash after a few seconds.

| ID | Acceptance criterion | Procedure | Pass | Fail |
|----|---------------------|-----------|------|------|
| AC-ANIM-1.1 | One start marker per launch | `grep 'electron anim-lab start' ~/Library/Logs/PerfectDarkKit/anim-lab.log` after fresh open | Count +1 per launch | +2 or more same second |
| AC-ANIM-1.2 | At most one spawned server | `grep serve_animlab ~/Library/Logs/PerfectDarkKit/anim-lab.log` | One `Starting serve_animlab.py` OR reuse existing healthy port | 5+ spawns 8776–8795 |
| AC-ANIM-1.3 | Catalog within 10 s | Open app; wait for UI | `/api/catalog` loads; animation list visible | Blank window >10 s |
| AC-ANIM-1.4 | Shared ensureBootstrap | Trigger activate (Cmd+Tab away/back) within 5 s of launch | No second bootstrap in log | Parallel bootstrap lines |

**iCloud path:** Repo under `Mobile Documents` must pass AC-ANIM-1.1–1.4 (normalization in main.js).

**Negative case AC-ANIM-1.N1:** Launch from hub + double-click release `.app` within 2 s — second instance must focus first (single-instance lock), not spawn second server.

---

### US-ANIM-2 — Parade test map

| ID | Acceptance criterion | Procedure | Pass | Fail |
|----|---------------------|-----------|------|------|
| AC-ANIM-2.1 | Deploy animlab parade | UI Build & Play or POST `/api/build-play` | pdmap deploy to mod_allinone; `--test-animlab` boots | Build error 500 |
| AC-ANIM-2.2 | play-config API | `curl -s http://127.0.0.1:PORT/api/play-config \| jq .ok` | `true` + presets animlab/uff | 404 or missing presets |

---

### US-ANIM-3 — Branding

| ID | Acceptance criterion | Procedure | Pass | Fail |
|----|---------------------|-----------|------|------|
| AC-ANIM-3.1 | HTML title PD Anim Lab | View page source / tab title | Title and h1 match | "Animation Lab" only |
| AC-ANIM-3.2 | Bundle display name | Get Info on `.app` | PD Anim Lab | Electron |

---

## PD Asset Upgrader

### US-UP-1 — Batch texture upgrade

| ID | Acceptance criterion | Procedure | Pass | Fail |
|----|---------------------|-----------|------|------|
| AC-UP-1.1 | setup script creates venv | `./scripts/setup-asset-upgrader.sh` | Exit 0; venv import works | Missing deps |
| AC-UP-1.2 | Hub runAssetUpgrader | Hub → Run Upgrader CLI | Process starts on `mods/` | Script not found |
| AC-UP-1.3 | productName PD Asset Upgrader | Open .app | Correct Dock name | Generic Electron |

---

## Virtual Agent Office

Full story set: [`journal/agent_office/SPEC.md`](journal/agent_office/SPEC.md) §2 (US-1 … US-6+).

| ID | Acceptance criterion | Procedure | Pass | Fail |
|----|---------------------|-----------|------|------|
| AC-AO-HUB-1 | Hub launches Virtual Agent Office | Hub Open Agent Office | App opens from wrap or release | Error when built |
| AC-AO-HUB-2 | Scenario actions deploy correct stage | Hub → Agent Office: dataDyne G5 | Boots stage 0x83 | Wrong map |
| AC-AO-HUB-3 | CI scenario | Hub → Agent Office: Carrington | Boots stage 0x84 | Wrong map |

---

## PC port & pdmap

### US-PORT-1 — Modded play

| ID | Acceptance criterion | Procedure | Pass | Fail |
|----|---------------------|-----------|------|------|
| AC-PORT-1.1 | mod_allinone loads | `./build/pd.arm64 --moddir mods/mod_allinone` | Custom maps in MP menu | Vanilla only |
| AC-PORT-1.2 | test-map flag | Deploy via editor; `./build/pd.arm64 --test-map --moddir mods/mod_allinone` | Last deploy boots | Wrong slot |

---

### US-PDMAP-1 — Valid maps only

| ID | Acceptance criterion | Procedure | Pass | Fail |
|----|---------------------|-----------|------|------|
| AC-PDMAP-1.1 | Non-contiguous pads fail | Inject gap in pad indices; `pdmap validate` | Non-zero exit | Silent pass |
| AC-PDMAP-1.2 | Waypoint symmetrization | Asymmetric graph in JSON; build | Output pads symmetric | One-way edges |
| AC-PDMAP-1.3 | Spec matches probes | `pdmap learn run`; diff MAP_DETERMINISTIC_SPEC | No unexpected drift | Hand-edited spec |

---

## Build & release

### US-BUILD-1 — Reproducible kit output

| ID | Acceptance criterion | Procedure | Pass | Fail |
|----|---------------------|-----------|------|------|
| AC-BUILD-1.1 | apps-only build | `./scripts/build-pd-kit.sh --skip-game --apps-only` | Exit 0; hub + children in release/ | Build fail |
| AC-BUILD-1.2 | manifest fields | `jq .kitVersion,.builtAt,.apps.kitHub.wrappedApps scripts/release/kit-manifest.json` | Versions match; wrapped flags correct | Missing manifest |
| AC-BUILD-1.3 | Single root symlink | `ls -la *.app` at repo root | Only Perfect Dark Kit.app → release | Multiple child symlinks |
| AC-BUILD-1.4 | Staging pruned | After build, `ls scripts/release/*-dist` | No *-dist directories | Stale electron-dist |

---

## Story → spec traceability

| Story | Spec IDs | Detail docs |
|-------|----------|-------------|
| US-HUB-* | R-KIT-05 … R-KIT-12 | [`API_CONTRACTS.md`](API_CONTRACTS.md) §1 |
| US-MAP-* | R-PDMAP-* | [`API_CONTRACTS.md`](API_CONTRACTS.md) §4 |
| US-ANIM-* | R-KIT-08, R-KIT-09 | [`API_CONTRACTS.md`](API_CONTRACTS.md) §3 |
| US-UP-* | R-KIT-01 | `tools/asset_upgrader/` |
| US-PORT-* | R-PORT-* | [`docs/spec/CLI_AND_LIMITS.md`](docs/spec/CLI_AND_LIMITS.md) |
| US-PDMAP-* | R-PDMAP-* | [`docs/MAP_DETERMINISTIC_SPEC.md`](docs/MAP_DETERMINISTIC_SPEC.md) |
| US-BUILD-* | R-KIT-01, R-KIT-10, R-KIT-11 | [`ARCHITECTURE.md`](ARCHITECTURE.md) §9 |

---

## Revision history

| Date | Change |
|------|--------|
| 2026-07-02 | Added procedures, pass/fail signals, negative cases, traceability |
| 2026-07-02 | Initial AC ids for kit v0.2 |
