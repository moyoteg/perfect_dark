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
| **Animation Lab** | Animation catalog + parade test map | nested in hub + `scripts/release/` |
| **Asset Upgrader** | Batch texture upgrade for mods | nested in hub + `scripts/release/` |
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
- `scripts/release/Perfect Dark Kit — Map Editor.app`
- `scripts/release/Perfect Dark Kit — Animation Lab.app`
- `scripts/release/Perfect Dark Kit — Asset Upgrader.app`
- `scripts/release/kit-manifest.json`

Child apps are copied into `Perfect Dark Kit.app/Contents/Resources/Apps/` so the hub is self-contained. Repo-root symlinks are created for the hub and each tool when the build succeeds.

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
| `pd-kit.sh open anim-lab` | Open Animation Lab `.app` |
| `pd-kit.sh open asset-upgrader` | Open Asset Upgrader `.app` |
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
│       ├── Perfect Dark Kit — Map Editor.app
│       ├── Perfect Dark Kit — Animation Lab.app
│       └── Perfect Dark Kit — Asset Upgrader.app
├── Perfect Dark Kit — Map Editor.app
├── Perfect Dark Kit — Animation Lab.app
└── Perfect Dark Kit — Asset Upgrader.app

build/pd.arm64
```

Generated manifest example fields: `kitVersion`, `portVersion`, `builtAt`, `gameBinary.built`, `apps.*.built`.

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
