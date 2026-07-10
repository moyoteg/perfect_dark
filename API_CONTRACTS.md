# Perfect Dark AIO — API & IPC Contracts

**Parent:** [`SPEC.md`](SPEC.md)  
**Status:** Spec-driven development source of truth (2026-07-02)  
**Scope:** Every cross-process contract in the kit — Electron IPC, local HTTP servers, manifest JSON, and game launch argv.

All servers bind **`127.0.0.1` only**. Non-localhost `Origin` headers receive **`403 { ok: false, error: "origin_not_allowed" }`**.

---

## 1. Kit Hub — Electron IPC

**Preload bridge:** `tools/pd_kit/electron/preload.js` → `window.pdKit`  
**Main handlers:** `tools/pd_kit/electron/main.js` → `registerIpc()`

### 1.1 `kit:get-info`

| Property | Value |
|----------|-------|
| Direction | Renderer → Main (invoke) |
| Args | none |
| Throws | Never — errors returned in payload |

**Success response:**

```json
{
  "name": "Perfect Dark Kit",
  "kitVersion": "0.2.0",
  "portVersion": "0.1.0",
  "repoRoot": "/absolute/path/to/repo",
  "releaseDir": "/absolute/path/to/repo/scripts/release",
  "wrappedAppsDir": "/path/to/Perfect Dark Kit.app/Contents/Resources/Apps",
  "gameBinary": {
    "path": "/absolute/path/to/build/pd.arm64",
    "built": true
  },
  "tools": [ /* toolCard[] — core_wrap tier; see §1.8 */ ],
  "moreTools": [ /* toolCard[] — optional_companion tier, built only; see §1.8 */ ],
  "actionGroups": [ /* actionGroup[] — see §1.9 */ ],
  "docs": [ /* docLink[] — see §1.10 */ ],
  "manifestBuiltAt": "2026-07-02T01:23:45Z"
}
```

**Partial failure** (repo unresolved): `tools`, `moreTools`, `actionGroups`, `docs` empty arrays; optional top-level `"error": "message"`.

### 1.2 `kit:launch-app`

| Property | Value |
|----------|-------|
| Args | `appKey: string` — key from `kit.json` `apps` (e.g. `"animLab"`) |
| Cooldown | **1200 ms** per `appKey` via `launchAllowed()` |
| Mechanism | `execFile('open', [appPath])` — never shell string |

**Responses:**

| Condition | Payload |
|-----------|---------|
| Success (`.app` exists) | `{ ok: true, path: "/…/PD Anim Lab.app" }` |
| Cooldown active | `{ ok: true, skipped: true, reason: "cooldown" }` — logged as `decision: deny_cooldown`, `scenario_id: KH-04` |
| Dev script fallback | `{ ok: true, path: "…/scripts/launch-….sh", devMode: true }` |
| Not built | `{ ok: false, error: "… is not built. Run: …" }` — logged as `launch_route: failed_not_built`, `scenario_id: KH-05` |
| `open` failure | `{ ok: false, error: "<system message>" }` |

**Resolution order for `appPath`:**

1. `Perfect Dark Kit.app/Contents/Resources/Apps/<bundleFileName>`
2. `scripts/release/<bundleFileName>`
3. `<repoRoot>/<bundleFileName>`
4. `path.resolve(repoRoot, siblingPath)` when `siblingPath` set (LLM Play)

### 1.3 `kit:launch-game`

| Property | Value |
|----------|-------|
| Args | `{ mod?: string, testMap?: boolean }` |
| Default mod | `"mod_allinone"` |
| Binary | `kit-manifest.json` → `gameBinary.path` or `build/pd.arm64` |

**Spawn:**

```bash
./build/pd.arm64 --moddir mods/<mod> [--test-map]
```

**Responses:**

| Condition | Payload |
|-----------|---------|
| Success | `{ ok: true, pid: 12345, command: "…" }` |
| Missing binary | `{ ok: false, error: "Game binary missing: …" }` |

Process is **detached** (`stdio: 'ignore'`, `unref()`).

### 1.4 `kit:run-action`

| Property | Value |
|----------|-------|
| Args | `actionKey: string` — must match `actionGroups[].actions[].key` |
| Spawn | `spawn('/bin/bash', [scriptPath, ...args], { cwd: repoRoot, env: { PD_REPO_ROOT } })` |

**Long-running / detached** when `action.longRunning === true` **except** `buildApps` and `buildFullKit` (those capture stdout).

| Condition | Payload |
|-----------|---------|
| Sync success | `{ ok: true, code: 0, output: "<last 4000 chars stdout+stderr>" }` |
| Sync failure | `{ ok: false, code: N, output: "…" }` |
| Detached | `{ ok: true, pid: N, detached: true }` |
| `requiresGame` unmet | `{ ok: false, error: "Game binary not built. Use Build Game first." }` |
| Unknown key | `{ ok: false, error: "Unknown action: …" }` |

### 1.5 `kit:open-doc`

Opens file via `shell.openPath(docPath)` where `docPath = join(repoRoot, docs[].path)`.

| Condition | Payload |
|-----------|---------|
| Success | `{ ok: true, path: "…" }` |
| Missing | `{ ok: false, error: "Doc not found: …" }` |
| Unknown key | `{ ok: false, error: "Unknown doc: …" }` |

### 1.6 `kit:reveal-path`

| Condition | Payload |
|-----------|---------|
| Exists | `{ ok: true }` + `shell.showItemInFolder` |
| Missing | `{ ok: false, error: "Path not found" }` |

### 1.7 `kit:build-kit`

Alias for `kit:run-action('buildApps')` → `./scripts/build-pd-kit.sh --skip-game --apps-only`.

### 1.8 `toolCard` object (in `kit:get-info.tools[]` or `moreTools[]`)

| Field | Type | Semantics |
|-------|------|-----------|
| `key` | string | Manifest app key |
| `title` | string | `productName` |
| `shortTitle` | string | Hub card heading |
| `description` | string | Card body |
| `category` | string | `"authoring"` \| `"companion"` |
| `hubSurfaceTier` | string | `"core_wrap"` (in `tools[]`) \| `"optional_companion"` (in `moreTools[]`) |
| `optional` | boolean | Missing build is non-fatal |
| `built` | boolean | `.app` exists **or** dev script available |
| `devMode` | boolean | No `.app`; launching via `devLaunchScript` |
| `wrapped` | boolean | Copy exists under hub `Resources/Apps/` |
| `path` | string | Resolved `.app` or dev script path |
| `buildScript` | string \| null | Hint for rebuild |

**Visibility:** `tools[]` lists every `kitHub.wraps` entry. `moreTools[]` lists `kitHub.moreTools` entries **only when `built === true`**. Normative rules: [`docs/spec/KIT_HUB.md`](docs/spec/KIT_HUB.md).

### 1.9 `actionGroup` object

Mirrors `kit.json` `actionGroups[]` with fields: `id`, `title`, `actions[]` each having `key`, `shortTitle`, `description`, `script`, `args`, `requiresGame`, `longRunning`.

### 1.10 `docLink` object

| Field | Type |
|-------|------|
| `key` | string |
| `title` | string |
| `path` | string — repo-relative |
| `exists` | boolean — `fs.existsSync(join(repoRoot, path))` |

---

## 2. Anim Lab — Electron preload

**File:** `journal/anim_lab/electron/preload.js`  
**Bridge:** `window.animLabAPI`

| Method | Behavior |
|--------|----------|
| `getServerPort()` | Returns active port string from main process |
| `ensureServer()` | Invokes main to run `ensureBootstrap()`; returns port |

Main process IPC: `anim-lab:get-port`, `anim-lab:ensure-server` (see `main.js`).

---

## 3. Anim Lab — HTTP (`serve_animlab.py`)

**Host:** `127.0.0.1`  
**Port range:** **8776–8795** (`--auto-port` scans upward)  
**State file:** `<stateDir>/.anim_lab_server.port`  
**Service id:** `"anim-lab"` in `/api/health`

### 3.1 `GET /api/health`

```json
{
  "ok": true,
  "service": "anim-lab",
  "port": 8776,
  "repoRoot": "/path/to/repo",
  "binaryFound": true,
  "binaryPath": "/path/to/build/pd.arm64",
  "romid": "<ROMID constant>",
  "stageAnimlab": "<STAGE_ANIMLAB constant>",
  "bootFlags": { "animlab": "--test-animlab", "uff": "--test-map" },
  "bundleDir": "/path/to/bundle or null",
  "docs": "docs/CHARACTER_ANIMATIONS.md"
}
```

Electron health probe requires: `ok === true` **and** `service === 'anim-lab'`. When reusing servers, optional `bundleDir` match prevents cross-bundle confusion.

### 3.2 `GET /api/status`

```json
{ "ok": true, "games": { "12345": true, "12346": false } }
```

Maps detached game PIDs to running state; dead PIDs pruned.

### 3.3 `GET /api/catalog`

Query: `?stubs=0|1` (default stubs excluded).

Returns `full_catalog_payload()` from `tools.pdmap.anim_catalog` plus `"ok": true`.

### 3.4 `GET /api/animations`

| Query param | Default | Purpose |
|-------------|---------|---------|
| `search` | `""` | Substring filter |
| `category` | `""` | Category id |
| `limit` | `80` | Max rows |
| `namedOnly` | `1` | Exclude unnamed stubs |

```json
{
  "ok": true,
  "search": "",
  "category": null,
  "count": 42,
  "animations": [ /* enriched rows */ ],
  "categories": { "guard": "Guard", "…": "…" }
}
```

### 3.5 `GET /api/preview-geometry`

Returns `animlab_preview_geometry()` from `tools.pdmap.anim_layout_geometry`.

### 3.6 `GET /api/play-config`

Play/deploy defaults: mod choices, scenario list, map presets (`animlab`, `uff`), sim difficulties, last deploy snapshot.

### 3.7 `GET /api/showcase`

Parade guard / animation table for UI showcase panel.

### 3.8 Static files

| Path | File |
|------|------|
| `/`, `/index.html` | `anim_lab.html` |
| `/<rel>` | Under `LAB_DIR` with `..` rejected → 403 |

### 3.9 POST endpoints

All accept JSON body; invalid JSON → **400** `{ ok: false, error: "invalid_json: …" }`.

| Path | Purpose | Key payload fields |
|------|---------|-------------------|
| `/api/build` | pdmap build only | `level`, `seg`, `deploy` |
| `/api/play` | Launch game | mod, scenario, flags |
| `/api/launch` | Build + optional play | `map`, `build`, `play`, deploy opts |
| `/api/replay` | Re-run last launch script | — |
| `/api/build-play` | Legacy alias → `_launch()` | same as launch |

Failure → **500** with `{ ok: false, error: "…" }` unless handler sets `ok: false` in body (still 500).

### 3.10 Map presets (server-side)

| Key | Boot flag | Stage |
|-----|-----------|-------|
| `animlab` | `--test-animlab` | `STAGE_ANIMLAB` |
| `uff` | `--test-map` | uff slot |

---

## 4. Map Editor — HTTP (`serve_editor.py`)

**Host:** `127.0.0.1`  
**Port range:** **8765–8775** (`--auto-port`)  
**State file:** `<stateDir>/.editor_server.port`  
**Service id:** `"uff-editor"` in `/api/health`

### 4.1 `GET /api/health`

```json
{
  "ok": true,
  "service": "uff-editor",
  "port": 8765,
  "repoRoot": "/path/to/repo",
  "binaryFound": true,
  "binaryPath": "/path/to/build/pd.arm64"
}
```

Bundled builds may also expose `bundleHash` (pass-11 cache busting) when generated viewer embeds hash — compare in UI against embedded constant.

### 4.2 `GET /api/status`

Same shape as Anim Lab §3.2.

### 4.3 `POST /api/test-map`

Primary editor Test/Play pipeline. Body: editor JSON + options (see `test_map.py` / `_play_params_from_opts`).

| Field | Type | Default |
|-------|------|---------|
| `numSims` | int | 8 |
| `simDifficulty` | int | 2 (Normal) |
| `loadout` | int[] | weapon ids |
| `buildOnly` | bool | skip game spawn |
| `segMode` | string | respects `PDMAP_SEG_MODE` env |

Invokes `test_map.py` pipeline: validate → build → deploy to test slot → optional `pd.arm64 --test-map`.

### 4.4 Static files

| Path | File |
|------|------|
| `/`, `/index.html` | `uff_map.html` |

### 4.5 Map persistence (UI contract)

The editor UI calls `/api/maps` CRUD when a maps router is present. **Current `serve_editor.py` ships Test/Play + static only**; Save falls back to **LocalStorage** key `pdmap_editor_<name>` with explicit status when server CRUD unavailable (see `journal/uff_viewer/README.md`). Future work: wire maps handler into `serve_editor.py` — track in SPEC §10.

---

## 5. Shared Python path module

**File:** `tools/pd_kit/paths.py`

| Function | Returns |
|----------|---------|
| `kit_manifest()` | Parsed `kit.json` |
| `kit_version()` | `KIT_VERSION` file or `PD_KIT_VERSION` env |
| `port_version()` | `PORT_VERSION` file or `PD_PORT_VERSION` env |
| `kit_log_file(component)` | `~/Library/Logs/PerfectDarkKit/<logFile>` |
| `kit_support_dir(component)` | `~/Library/Application Support/PerfectDarkKit/<id>/` |
| `resolve_anim_lab_state_dir(repo)` | Writable `journal/anim_lab` or support dir |
| `resolve_editor_state_dir(repo)` | Writable `journal/uff_viewer` or support dir |

---

## 6. Release manifest — `kit-manifest.json`

**Generated by:** `write_kit_release_manifest()` in `scripts/pd-kit-common.sh`  
**Locations:** `scripts/release/kit-manifest.json`, baked in hub `Resources/`

```json
{
  "name": "Perfect Dark Kit",
  "kitVersion": "0.2.0",
  "portVersion": "0.1.0",
  "builtAt": "2026-07-02T01:23:45Z",
  "repoRoot": "/absolute/repo",
  "releaseDir": "/absolute/repo/scripts/release",
  "gameBinary": {
    "path": "/absolute/repo/build/pd.arm64",
    "built": true
  },
  "apps": {
    "kitHub": {
      "productName": "Perfect Dark Kit",
      "bundleFileName": "Perfect Dark Kit.app",
      "built": true,
      "path": "…/scripts/release/Perfect Dark Kit.app",
      "wrappedApps": {
        "mapEditor": true,
        "animLab": true,
        "mapLauncher": false,
        "…": false
      }
    },
    "mapEditor": { "…": "…" }
  }
}
```

**Never hand-edit.** Regenerate via `./scripts/build-pd-kit.sh`.

---

## 7. Game launch argv contract

**Binary:** `build/pd.arm64` (arm64 macOS PC port)

| Flag | Purpose |
|------|---------|
| `--moddir mods/<name>` | Load mod stack |
| `--test-map` | Boot last-deployed uff / editor test slot |
| `--test-animlab` | Boot animlab parade stage |
| `--solo` | Agent office peaceful mode |
| `--boot-stage 0x83` / `0x84` | Agent office G5 / CI |
| `--with-bots` | Agent office combat sims |
| `--scenario-N` | MP scenario index |

Full agent office matrix: [`journal/agent_office/SPEC.md`](journal/agent_office/SPEC.md).

---

## 8. Environment variables (API-relevant)

| Variable | Affects |
|----------|---------|
| `PD_REPO_ROOT` | All servers + Electron repo discovery |
| `PD_KIT_VERSION` / `PD_PORT_VERSION` | Version pills |
| `PD_PYTHON` | Electron python spawn |
| `PD_ANIM_LAB_STATE_DIR` | Anim lab port/deploy state |
| `PD_EDITOR_STATE_DIR` | Editor port/last-test state |
| `PD_ANIM_LAB_BUNDLE_DIR` | Bundled lab static root |
| `PDMAP_SEG_MODE` | `empty` for Test/Play viewport (no near-plane sheet) |
| `ANIMLAB_PARADE_MAX` | Parade grid size (default 570) |
| `CMAKE_JOBS` | Game build parallelism |

Full table: [`ENVIRONMENTS.md`](ENVIRONMENTS.md) §3.

---

## 9. Error code catalog

| Code / string | Layer | Meaning | User action |
|---------------|-------|---------|-------------|
| `origin_not_allowed` | HTTP | Non-localhost Origin | Use 127.0.0.1 URL |
| `invalid_json` | HTTP | Malformed POST body | Fix client payload |
| `cooldown` | IPC | Hub launch debounced | Wait 1.2 s |
| `Game binary missing` | IPC | No `pd.arm64` | Run Build Game |
| `Unknown action` | IPC | Bad actionKey | Check kit.json |
| `Timed out waiting for /api/health` | Electron | Server failed to bind | Check log, port range |
| `serve_animlab.py exited` | Electron | Python crash | Read anim-lab.log |
| `Unhandled rejection:` | Electron log | Pre-fix crash class | Update to hardened main.js |
| `EXC_BREAKPOINT` | macOS crash | Electron 33 fatal rejection | Same as above |

---

## 10. Revision history

| Date | Change |
|------|--------|
| 2026-07-02 | Initial detailed API contract (IPC schemas, HTTP tables, manifest, errors) |
