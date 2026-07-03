# Perfect Dark AIO — Environments

**Parent spec:** [`SPEC.md`](SPEC.md)  
**Stories / verification:** [`STORIES.md`](STORIES.md)

---

## 1. Environment overview

| Environment | Purpose | Game binary | Apps | ROM |
|-------------|---------|-------------|------|-----|
| **Local dev** | Day-to-day authoring | `cmake --build build --target pd` | `npm start` in electron dirs OR release `.app` | `data/pd.ntsc-final.z64` |
| **Release bundle** | Double-click shipping | Same path in manifest | `scripts/release/*.app` | User BYO |
| **iCloud workspace** | Synced repo clone | Same as local | Must normalize `Mobile Documents` paths | Same |

Kit v0.2 is **local-only macOS** — no hosted dev/QA/prod split.

---

## 2. Prerequisites

### 2.1 System packages

```bash
brew install cmake sdl2 zlib python3 node
```

### 2.2 Version matrix

| Requirement | Minimum | Tested | Notes |
|-------------|---------|--------|-------|
| macOS | 12+ | macOS 26 (darwin 25.x) | arm64 primary |
| Python | 3.10 | 3.11–3.14 | Servers + pdmap |
| Node | 18 LTS | 20+ | electron-builder 25 |
| Electron | 33.2.x | 33.2.1 | See crash notes §8 |
| CMake | 3.20+ | — | Game build |
| ROM | NTSC-final | `pd.ntsc-final.z64` | Not in repo |

### 2.3 First-time setup

```bash
cd /path/to/perfect_dark_jonaeru_aio
./scripts/link-rom.sh                    # BYO ROM → data/
make -j8                                 # or ./scripts/build-pd-kit.sh --game-only
./scripts/setup-asset-upgrader.sh      # optional, for upgrader
./scripts/build-pd-kit.sh --skip-game --apps-only
open scripts/release/Perfect\ Dark\ Kit.app
```

---

## 3. Environment variables (complete reference)

| Variable | Scope | Default | Purpose |
|----------|-------|---------|---------|
| `PD_REPO_ROOT` | All | Auto-discovered | Absolute repo path; overrides baked config |
| `PD_KIT_VERSION` | Display | `KIT_VERSION` file | Override version pill |
| `PD_PORT_VERSION` | Display | `PORT_VERSION` file | Override port version pill |
| `PD_PYTHON` | Electron spawn | Homebrew python3 | Force Python for servers |
| `PD_EDITOR_STATE_DIR` | Map Editor | `journal/uff_viewer/` if writable | Port file, last test |
| `PD_ANIM_LAB_STATE_DIR` | Anim Lab | `journal/anim_lab/` if writable | Port, deploy state |
| `PD_ANIM_LAB_BUNDLE_DIR` | serve_animlab | Bundled Resources path | Static UI root |
| `PDMAP_SEG_MODE` | pdmap build | procedural / empty | **`empty`** for Test/Play FPS |
| `ANIMLAB_PARADE_MAX` | animlab build | `570` | Parade grid size |
| `CMAKE_JOBS` | Game build | `8` | Parallel compile |
| `PD_KIT_ICONS_FORCE` | Icon script | unset | `1` regenerates all ICNS |
| `PYTHONPATH` | Server spawn | repo + bundle | Set by Electron main.js |

---

## 4. Path conventions

### 4.1 Repository layout

| Path | Content |
|------|---------|
| `tools/pd_kit/kit.json` | Machine manifest |
| `scripts/release/` | Shipped `.app` bundles |
| `scripts/release/kit-manifest.json` | Build audit JSON |
| `build/pd.arm64` | Game binary |
| `mods/mod_allinone/` | Deploy target |
| `data/pd.ntsc-final.z64` | ROM (symlink) |

### 4.2 iCloud normalization

Paths may appear as:

- `…/Library/Mobile Documents/com~apple~CloudDocs/…`
- `…/Library/MobileDocuments/com~apple~CloudDocs/…`

All Electron shells run:

```javascript
path.replace(/\/Library\/MobileDocuments\//g, '/Library/Mobile Documents/')
```

**Before any `fs.existsSync`, `spawn`, or `open`.**

### 4.3 User Library (kit v0.2)

| Path | Purpose |
|------|---------|
| `~/Library/Application Support/PerfectDarkKit/<id>/` | State when repo read-only |
| `~/Library/Logs/PerfectDarkKit/*.log` | Component logs |

**Component ids:** `kit-hub`, `map-editor`, `anim-lab`, `map-launcher`, `agent-office`, `asset-upgrader`, `play-last-test-map`, `llm-play`, `virtual-agent-office`.

### 4.4 Log files

| Component | File |
|-----------|------|
| Hub | `kit-hub.log` |
| Map Editor | `map-editor.log` |
| Anim Lab | `anim-lab.log` |
| Asset Upgrader | `asset-upgrader.log` |
| Agent Office | `virtual-agent-office.log` |
| Play Last Test Map | `play-last-test-map.log` |
| LLM Play | `llm-play.log` |

**Format:** `[YYYY-MM-DD HH:MM:SS] [component] message`

### 4.5 Legacy migration

| Legacy | Replacement |
|--------|-------------|
| `~/Library/Application Support/PerfectDarkMapEditor/` | `…/PerfectDarkKit/map-editor/` |
| `~/Library/Application Support/PerfectDarkAnimLab/` | `…/PerfectDarkKit/anim-lab/` |
| `~/Library/Logs/PerfectDarkMapEditor.log` | `…/PerfectDarkKit/map-editor.log` |
| `~/Library/Logs/PerfectDarkAnimLab.log` | `…/PerfectDarkKit/anim-lab.log` |

Migration rule: if kit dir **empty** and legacy **non-empty**, read legacy until first write to kit path.

---

## 5. Running modes

### 5.1 Hub (release)

```bash
open "scripts/release/Perfect Dark Kit.app"
# or
./scripts/pd-kit.sh open
```

### 5.2 Individual app (release)

```bash
./scripts/pd-kit.sh open map-editor
./scripts/pd-kit.sh open anim-lab
./scripts/pd-kit.sh open kit-hub
```

Valid keys match `kit.json` app keys (see SPEC §13.5).

### 5.3 Electron dev (live sources)

```bash
export PD_REPO_ROOT="/absolute/path/to/repo"

cd journal/anim_lab/electron && npm start
cd journal/uff_viewer/electron && npm start
cd tools/pd_kit/electron && npm start
```

Dev mode: Anim Lab **prefers repo** `journal/anim_lab/` over bundled copy when `!app.isPackaged`.

### 5.4 Python servers only (no Electron)

```bash
python3 journal/uff_viewer/serve_editor.py --port 8765 --auto-port
python3 journal/anim_lab/serve_animlab.py --port 8776 --auto-port
# Browser: http://127.0.0.1:8765/ or :8776/
```

### 5.5 Game only

```bash
./build/pd.arm64 --moddir mods/mod_allinone
./build/pd.arm64 --moddir mods/mod_allinone --test-map
./build/pd.arm64 --moddir mods/mod_allinone --test-animlab
```

---

## 6. Build commands

| Target | Command | Duration (typical) |
|--------|---------|------------------|
| Full kit | `./scripts/build-pd-kit.sh` | 10–30 min (with game) |
| Apps only | `./scripts/build-pd-kit.sh --skip-game --apps-only` | 3–8 min |
| Game only | `./scripts/build-pd-kit.sh --game-only` | 5–15 min |
| Map Editor | `./scripts/build-map-editor-electron.sh` | 1–2 min |
| Anim Lab | `./scripts/build-anim-lab-electron.sh` | 1–2 min |
| Hub only | `./scripts/build-pd-kit-launcher-electron.sh` | 1–2 min |
| Icons force | `PD_KIT_ICONS_FORCE=1 ./scripts/pd-kit-icons.sh all` | ~30 s |

**Flags:**

| Flag | Effect |
|------|--------|
| `--game-only` | cmake pd target only |
| `--apps-only` | Skip cmake |
| `--skip-game` | Skip cmake if binary exists |
| `--no-symlink` | No repo-root `.app` symlink |

---

## 7. Logging & debugging

### 7.1 Tail logs during repro

```bash
tail -f ~/Library/Logs/PerfectDarkKit/kit-hub.log
tail -f ~/Library/Logs/PerfectDarkKit/anim-lab.log
tail -f ~/Library/Logs/PerfectDarkKit/map-editor.log
```

### 7.2 Healthy patterns

| App | Good signal | Bad signal |
|-----|-------------|------------|
| Anim Lab | One `=== electron anim-lab start ===` per launch | Multiple starts same second |
| Anim Lab | One `Starting serve_animlab.py` OR port reuse | 5+ spawns on 8776–8795 |
| Map Editor | One server bind on 8765–8775 | Timeout error in dialog |
| Hub | One `Launch animLab:` per click | 5+ identical lines in 1 s |
| Hub | No `Unhandled rejection:` | Rejection then crash |
| All | `REPO_ROOT=` logged at startup | `repo root not resolved` |

### 7.3 Grep one-liners (release QA)

```bash
# Anim Lab single bootstrap
grep -c 'electron anim-lab start' ~/Library/Logs/PerfectDarkKit/anim-lab.log

# Hub launch storm
grep 'Launch animLab' ~/Library/Logs/PerfectDarkKit/kit-hub.log | tail -20

# Unhandled rejections (any component)
grep -i 'Unhandled rejection' ~/Library/Logs/PerfectDarkKit/*.log

# Server listening
grep -i 'listening\|PORT=' ~/Library/Logs/PerfectDarkKit/anim-lab.log | tail -5
```

### 7.4 Port occupancy

```bash
# Editor ports
for p in $(seq 8765 8775); do lsof -i :$p 2>/dev/null && echo "busy $p"; done

# Anim Lab ports
for p in $(seq 8776 8795); do lsof -i :$p 2>/dev/null && echo "busy $p"; done
```

Kill stale servers: quit app from Dock (Cmd+Q) or `pkill -f serve_animlab.py` / `serve_editor.py`.

---

## 8. Crash diagnostics

### 8.1 Electron 33 signature

| Symptom | Cause | Fix |
|---------|-------|-----|
| Crash ~3 s after launch | Unhandled promise rejection | Ensure `process.on('unhandledRejection')` logs only |
| `EXC_BREAKPOINT` main thread | Same | Use `ensureBootstrap()` mutex |
| 7× Launch animLab in 1 s | Hub cooldown missing | 1200 ms + renderer in-flight guard |
| Many Python servers | Parallel bootstrap on activate+whenReady | Single mutex pattern |

**Crash reports:** `~/Library/Logs/DiagnosticReports/` — correlate `Incident Identifier` with log timestamp.

### 8.2 iCloud placeholder files

Symptom: server starts but HTML/API 404 until files download.

**Mitigation:** `ensureLocalFile()` polls up to 12×350 ms; `fileReadable()` reads 1 byte.

### 8.3 Repo root not resolved

Symptom: Hub opens but all actions fail.

**Checks:**

1. `repo-config.json` inside `.app` points to valid path
2. Set `PD_REPO_ROOT` explicitly
3. Rebuild app from current repo path (`build-pd-kit-launcher-electron.sh` writes fresh config)

---

## 9. Troubleshooting decision tree

```
App crashes on launch?
├─ Yes, within 5 s, EXC_BREAKPOINT
│   ├─ Check log for Unhandled rejection
│   ├─ Anim Lab: count bootstrap lines → must be 1
│   └─ Rebuild with latest main.js
├─ Yes, after idle
│   └─ Check hub log for repeated Launch lines
└─ No crash, blank window
    ├─ Check server port (8765–8775 / 8776–8795)
    ├─ curl http://127.0.0.1:PORT/api/health
    └─ iCloud: wait for file download or open repo locally

Hub can't launch child?
├─ Card says Not built → run build script on card hint
├─ Optional app → expected if build skipped
└─ Wrapped false but release exists → rebuild hub wrap step

Test/Play fails?
├─ binaryFound false in /api/health → build game
├─ ROM missing → link-rom.sh
└─ pdmap validate errors → MAP_DETERMINISTIC_SPEC + wiki
```

---

## 10. Optional external dependencies

| Tool | Used by | Setup |
|------|---------|-------|
| Ollama | LLM Play | `./scripts/ensure-ollama-external-drive.sh` |
| LLM Play sibling | Hub card | Build in `../llm-play/` |
| Asset upgrader venv | Upgrader | `./scripts/setup-asset-upgrader.sh` |

---

## 11. Release checklist (pre-ship)

- [ ] `KIT_VERSION` bumped if tooling changed
- [ ] `PORT_VERSION` bumped if game fork changed
- [ ] `./scripts/build-pd-kit.sh --apps-only` exit 0
- [ ] `jq .apps.kitHub.wrappedApps scripts/release/kit-manifest.json` — expected trues
- [ ] SPEC §17 verification V-1 through V-10
- [ ] STORIES AC-HUB-1.3, AC-ANIM-1.1, AC-MAP-1.1 pass
- [ ] No `Unhandled rejection` in fresh log session
- [ ] Repo root: only hub `.app` symlink
- [ ] iCloud path smoke on target machine if applicable

---

## 12. Future: automated smoke script (roadmap)

Planned `scripts/kit-smoke.sh`:

1. Launch hub detached; sleep 5
2. Grep kit-hub.log for rejection
3. Invoke `open` on wrapped Anim Lab; sleep 8
4. Assert single bootstrap line in anim-lab.log
5. `curl` health endpoints
6. Exit non-zero on any failure

Not yet implemented — manual gates in §11 remain authoritative.

---

## Revision history

| Date | Change |
|------|--------|
| 2026-07-02 | Full env var table, troubleshooting tree, grep QA, crash matrix |
| 2026-07-02 | Initial environments doc |
