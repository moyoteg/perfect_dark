# PD Map Launcher

Electron desktop app for **map playtesting** and **map learn curriculum** management in the Perfect Dark AIO repo.

## Features

### Map Launcher tab (default)
- One-click launch for whitelisted test maps:
  - Matrix Battle 64
  - Matrix Laptop Sentry
  - Matrix Sentry Unlimited
  - War Colors / Conker Sentry
  - Launch AIO Mod (retail menu)
  - Play Learn Step (curriculum)
  - Validate Next Step
  - Play Last Test Map
- **Progressive Learning Maps** — all **31** curriculum steps as individual launch cards, **grouped by phase** (same list as Map Learning tab)
- Tab badge shows loaded curriculum count (e.g. **31**)
- Per-map options (`--num-sims`, `--solo`, `--full-battle`, deploy-only, etc.)
- Game PID detection via `pgrep pd.arm64` and `journal/map_learn/.last_play.pid`
- Kill game button
- Live log tail from map-specific log files under `journal/map_learn/`

### Map Learning tab
- Same **31** progressive learning map cards (grouped by phase)
- Learn loop status (`journal/map_learn/.learn-loop.pid`, `loop.log`)
- Start / stop `scripts/map-learn-loop.sh`
- Recent learn run JSON summaries from `journal/map_learn/runs/`
- Validation status, pdmap validate, curriculum generate, pdmap learn run
- Links to `CURRICULUM.md` and `LEARN_PLAN.md`

## Curriculum loading

Steps are loaded at startup in this order:

1. **Live Python** — `tools/pdmap/learn/curriculum.py` via `curriculum_steps()` (preferred when repo root resolves)
2. **Bundled JSON** — `curriculum-manifest.json` in this directory (fallback when Python fails or repo root is missing)
3. **Filesystem scan** — `journal/map_learn/maps/learn_*.json` (last resort)

Regenerate the bundled manifest after editing `curriculum.py`:

```bash
cd tools/map-launcher-electron
npm run curriculum-manifest
# or: ./scripts/generate-curriculum-manifest.sh
```

Check `~/Library/Logs/PerfectDarkKit/map-launcher.log` for lines like `Loaded 31/31 curriculum map launchers`.

## Install & run

From the repo root:

```bash
cd tools/map-launcher-electron
npm install
npm start
```

Or use the wrapper script:

```bash
./scripts/launch-map-launcher.sh
```

From **Perfect Dark Kit** hub or CLI:

```bash
./scripts/pd-kit.sh open          # hub → Desktop Apps → Map Launcher
./scripts/pd-kit.sh open map-launcher
```

Set `PD_REPO_ROOT` if the app cannot auto-discover the repository (e.g. when launched from outside the tree).

## Verify all 31 maps appear

1. Launch the app (`./scripts/launch-map-launcher.sh` or Kit hub).
2. On the default **Map Launcher** tab, scroll past **Test Maps** — you should see **Progressive Learning Maps** with a green **31 maps** badge.
3. Eight phase sections (Spawns & Pads through Advanced) each contain step cards with **Launch** buttons.
4. Both tab buttons show a **31** badge when loading succeeded.
5. **Map Learning** tab shows the same grouped cards plus loop/validation tools.

## Security

The main process only spawns scripts listed in `main.js` (`MAP_LAUNCHERS`, dynamically built learn-step launchers, and `LEARN_ACTIONS`). Arbitrary shell commands from the renderer are not accepted.

## Logs

App supervisor log: `~/Library/Logs/PerfectDarkKit/map-launcher.log`

Map launch logs remain under `journal/map_learn/` as written by each play script.

## Requirements

- macOS arm64 (primary target; Linux should work for core launch paths)
- Built game binary: `build/pd.arm64`
- Node.js + npm for development runs
