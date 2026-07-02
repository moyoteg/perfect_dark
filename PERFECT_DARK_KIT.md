# Perfect Dark Kit

**Kit version:** `KIT_VERSION` (currently **0.2.0**)  
**Port version:** `PORT_VERSION` (currently **0.1.0**, see [`RELEASE_v0.1.0.md`](RELEASE_v0.1.0.md))

The **Perfect Dark Kit** is the unified modding stack for this repository: PC port runtime, deterministic build pipelines, desktop authoring apps, and the wiki/spec layer. Kit semver tracks tooling releases; port semver tracks the game fork baseline.

## What is included

| Component | Role | Entry point |
|-----------|------|-------------|
| **PC port** | Play modded Perfect Dark | `./build/pd.arm64 --moddir mods/mod_allinone` |
| **pdmap pipeline** | Validate → build → deploy → register maps | `python3 tools/pdmap.py …` |
| **Kit Hub** | Launch all tools from one `.app` | `Perfect Dark Kit.app` |
| **Map Editor** | 3D JSON editor + Test/Play | nested in hub + `scripts/release/` |
| **Map Launcher** | Test map playtesting + learn curriculum | hub card → `./scripts/launch-map-launcher.sh` (dev) |
| **Animation Lab** | Animation catalog + parade test map | nested in hub + `scripts/release/` |
| **Asset Upgrader** | Batch texture upgrade for mods | nested in hub + `scripts/release/` |
| **Play Last Test Map** | Replay last editor Test/Play | hub card + `scripts/release/` |
| **LLM Play** | AI play adapter (sibling project) | hub card → `../llm-play/LLM Play.app` |
| **Docs** | Workflow + binary reference | [`docs/MAP_MAKING_WIKI.md`](docs/MAP_MAKING_WIKI.md) |

**BYO ROM** — no game assets are bundled. Place `pd.ntsc-final.z64` in `data/` (see [`README.md`](README.md)).

## Quick start (macOS arm64)

### 1. Prerequisites

```bash
brew install cmake sdl2 zlib python3 node
```

Provide your NTSC-final ROM and symlink at repo root (see README QUICKSTART).

### 2. Build the full kit

```bash
./scripts/build-pd-kit.sh
```

This builds:

- `./build/pd.arm64`
- `scripts/release/Perfect Dark Kit.app` (hub — **wraps all tools below**)
- `scripts/release/PD Map Editor.app`
- `scripts/release/PD Anim Lab.app`
- `scripts/release/PD Asset Upgrader.app`
- `scripts/release/Play Last Test Map.app`
- `scripts/release/kit-manifest.json`

Optional (sibling project): `../llm-play/LLM Play.app` — surfaced in the hub when built.

Child apps are copied into `Perfect Dark Kit.app/Contents/Resources/Apps/` when present in `scripts/release/`. The hub UI also exposes build, validate, scenario, setup scripts, and documentation links from `tools/pd_kit/kit.json`.

### 3. CLI launcher

```bash
./scripts/pd-kit.sh version
./scripts/pd-kit.sh open
./scripts/pd-kit.sh open map-editor
./scripts/pd-kit.sh validate my_arena testarena
./scripts/pd-kit.sh play --test-map --mod mod_allinone
```

| Command | Description |
|---------|-------------|
| `pd-kit.sh version` | Print kit + port version and support paths |
| `pd-kit.sh build` | Same as `build-pd-kit.sh` |
| `pd-kit.sh build --game-only` | CMake `pd` target only |
| `pd-kit.sh build --apps-only` | Child apps + Kit hub wrapper |
| `pd-kit.sh open` | Open **Perfect Dark Kit.app** hub (default) |
| `pd-kit.sh open kit` | Same as `open` |
| `pd-kit.sh open map-editor` | Open Map Editor directly |
| `pd-kit.sh open map-launcher` | Open Map Launcher (dev Electron or `.app` when built) |
| `pd-kit.sh open anim-lab` | Open Animation Lab `.app` |
| `pd-kit.sh open asset-upgrader` | Open Asset Upgrader `.app` |
| `pd-kit.sh open play-last-test-map` | Open Play Last Test Map `.app` |
| `pd-kit.sh open llm-play` | Open LLM Play `.app` (sibling project) |
| `pd-kit.sh validate [level …]` | Run `pdmap validate` (default: `my_arena testarena`) |
| `pd-kit.sh play [--test-map] [--mod MOD]` | Launch game with mod |

## Install order (from scratch)

1. Clone repo, checkout branch/tag.
2. Place ROM in `data/pd.ntsc-final.z64`.
3. `./scripts/build-pd-kit.sh` (or `--game-only` first, then `--apps-only`).
4. `./scripts/pd-kit.sh open map-editor` → design map → **Test / Play (T)**.
5. Read [`docs/MAP_MAKING_WIKI.md`](docs/MAP_MAKING_WIKI.md) for seg modes, simulants, troubleshooting.

Partial builds:

```bash
./scripts/build-pd-kit.sh --skip-game      # reuse existing pd.arm64
./scripts/build-map-editor-electron.sh     # Map Editor only
./scripts/build-anim-lab-electron.sh       # Animation Lab only
./scripts/build-asset-upgrader-electron.sh --build
```

## Branding and on-disk layout

Canonical manifest: [`tools/pd_kit/kit.json`](tools/pd_kit/kit.json)

| Location | Purpose |
|----------|---------|
| `~/Library/Application Support/PerfectDarkKit/map-editor/` | Map editor state when repo is not writable |
| `~/Library/Application Support/PerfectDarkKit/anim-lab/` | Animation Lab state fallback |
| `~/Library/Application Support/PerfectDarkKit/asset-upgrader/` | Reserved for upgrader UI state |
| `~/Library/Logs/PerfectDarkKit/map-editor.log` | Map Editor + `serve_editor.py` |
| `~/Library/Logs/PerfectDarkKit/map-launcher.log` | Map Launcher supervisor |
| `~/Library/Logs/PerfectDarkKit/anim-lab.log` | Animation Lab + `serve_animlab.py` |
| `~/Library/Logs/PerfectDarkKit/asset-upgrader.log` | Asset Upgrader supervisor |

When the repo is writable, dev state stays under `journal/uff_viewer/` and `journal/anim_lab/` as before.

### Legacy paths (migration)

Older builds used `PerfectDarkMapEditor` and `PerfectDarkAnimLab`. If the kit directory is empty but a legacy directory has data, tools **read from legacy** until you save into the kit path.

| Legacy | Kit replacement |
|--------|-----------------|
| `~/Library/Application Support/PerfectDarkMapEditor/` | `…/PerfectDarkKit/map-editor/` |
| `~/Library/Application Support/PerfectDarkAnimLab/` | `…/PerfectDarkKit/anim-lab/` |
| `~/Library/Logs/PerfectDarkMapEditor.log` | `…/PerfectDarkKit/map-editor.log` |
| `~/Library/Logs/PerfectDarkAnimLab.log` | `…/PerfectDarkKit/anim-lab.log` |

## Version alignment

| File | Tracks |
|------|--------|
| `KIT_VERSION` | Kit tooling semver (editors, scripts, `pd_kit` module) |
| `PORT_VERSION` | PC port / fork release baseline |
| `scripts/release/kit-manifest.json` | Generated at build time — app paths, binary presence, timestamps |

Bump **`KIT_VERSION`** when shipping kit tool changes. Bump **`PORT_VERSION`** when tagging a port release (see `RELEASE_v0.1.0.md`).

## Release layout

```
scripts/release/
├── kit-manifest.json
├── Perfect Dark Kit.app                    ← hub (wraps Apps/*)
│   └── Contents/Resources/Apps/
│       ├── PD Map Editor.app
│       ├── PD Anim Lab.app
│       ├── PD Asset Upgrader.app
│       ├── Play Last Test Map.app
│       └── LLM Play.app (when built + wrapped)
├── PD Map Editor.app
├── PD Anim Lab.app
├── PD Asset Upgrader.app
└── Play Last Test Map.app

../llm-play/LLM Play.app                      ← optional sibling project

build/pd.arm64
```

## Hub launcher surface

`Perfect Dark Kit.app` reads `tools/pd_kit/kit.json` and exposes:

| Section | Contents |
|---------|----------|
| **Game** | Play with Mod, Test Map |
| **Desktop Apps** | All `kitHub.wraps` entries (editors + companion apps) |
| **Build** | Build Apps, Build Game, Build Full Kit |
| **Validate & Learn** | pdmap validate, curriculum validation, learn step |
| **Scenarios & Launch** | AIO mod, matrix battle, reset uff, rebuild editors |
| **Setup & Utilities** | Link ROM, asset upgrader setup/CLI, Ollama setup |
| **Documentation** | Kit guide, map wiki, specs, anim reference, curriculum |

Generated manifest example fields: `kitVersion`, `portVersion`, `builtAt`, `gameBinary.built`, `apps.*.built`.

## Icons and single-instance behavior

Each kit app has a **distinct dock icon** (generated by `./scripts/pd-kit-icons.sh`):

| App | Icon source |
|-----|-------------|
| Perfect Dark Kit | `KitHubAppIcon.icns` — launcher grid |
| PD Map Editor | `MapEditorAppIcon.icns` — grid + pads |
| PD Anim Lab | `AnimLabAppIcon.icns` — film strip + play |
| PD Asset Upgrader | `AssetUpgraderAppIcon.icns` — low/high texture split |

Regenerate icons: `PD_KIT_ICONS_FORCE=1 ./scripts/pd-kit-icons.sh all`

Each Electron shell uses `requestSingleInstanceLock()` — launching the same app again focuses the existing window instead of spawning a duplicate. macOS bundle IDs are unique per app (`com.perfectdark.kit.*`).

## Shared code

| Module | Used by |
|--------|---------|
| `tools/pd_kit/paths.py` | Python servers, future CLI tools |
| `tools/pd_kit/electron_paths.js` | Electron shells (bundled into each `.app`) |
| `scripts/pd-kit-common.sh` | Build and launcher scripts |

## Related docs

- [`docs/MAP_MAKING_WIKI.md`](docs/MAP_MAKING_WIKI.md) — mapper workflow
- [`docs/MAP_DETERMINISTIC_SPEC.md`](docs/MAP_DETERMINISTIC_SPEC.md) — pdmap contracts
- [`docs/CHARACTER_ANIMATIONS.md`](docs/CHARACTER_ANIMATIONS.md) — Animation Lab
- [`tools/asset_upgrader/README.md`](tools/asset_upgrader/README.md) — texture pipeline
- [`.agents/skills/perfect-dark-workflow/SKILL.md`](.agents/skills/perfect-dark-workflow/SKILL.md) — agent quick reference
