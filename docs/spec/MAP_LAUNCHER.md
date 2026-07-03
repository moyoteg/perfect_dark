# Spec: PD Map Launcher

**Spec IDs:** `R-ML-01` … `R-ML-06` in [`SPEC.md`](../../SPEC.md)

---

## 1. Source paths

| Artifact | Path |
|----------|------|
| Main process | `tools/map-launcher-electron/main.js` |
| Preload | `tools/map-launcher-electron/preload.js` |
| Renderer | `tools/map-launcher-electron/renderer/app.js` |
| Curriculum manifest | `tools/map-launcher-electron/curriculum-manifest.json` |
| Manifest generator | `tools/map-launcher-electron/scripts/generate-curriculum-manifest.sh` |
| Launch script | `scripts/launch-map-launcher.sh` |
| Repo config (runtime) | `tools/map-launcher-electron/repo-config.json` (written at launch, gitignored) |
| User data dir | `~/Library/Application Support/PD Map Launcher` |
| Logs | `~/Library/Logs/PerfectDarkKit/map-launcher.log`, `map-launcher-stdio.log` |

---

## 2. App identity

| Property | Value |
|----------|-------|
| `app.setName()` | `"PD Map Launcher"` |
| Window title | `"PD Map Launcher"` |
| Dock (packaged) | `PD Map Launcher` |
| Dock (dev) | `Electron` (acceptable); icon from `assets/MapLauncherAppIcon.icns` |
| Single instance | `bindSingleInstance(app, requestFocusMainWindow)` |

---

## 3. Launch script contract (`scripts/launch-map-launcher.sh`)

**Default (macOS detached):**

```bash
printf '{"repoRoot":"%s"}\n' "$REPO_ROOT" >"$APP_DIR/repo-config.json"
open --env PD_REPO_ROOT="$REPO_ROOT" -a "$ELECTRON_APP" --args "$APP_DIR"
```

**Foreground debug:**

```bash
./scripts/launch-map-launcher.sh --foreground
# exec env PD_REPO_ROOT=… electron …
```

**Acceptance:** Electron PID alive ≥15s; stderr contains `Window ready-to-show` when logging enabled.

---

## 4. `MAP_LAUNCHERS` whitelist (exact IDs)

Only these `script` paths may be spawned from IPC. Source: `main.js` `MAP_LAUNCHERS` array.

| `id` | `script` | Default sims | `logPath` |
|------|----------|--------------|-----------|
| `matrix-battle-64` | `scripts/play-matrix-battle.sh` | 50 (`--num-sims`, max 64) | `journal/map_learn/.matrix_battle_64_test.log` |
| `matrix-laptop-sentry` | `scripts/play-matrix-laptop-sentry.sh` | 50 | `journal/map_learn/.matrix_battle_sentry_test.log` |
| `matrix-sentry-unlimited` | `scripts/play-matrix-sentry-unlimited.sh` | 50 | `journal/map_learn/.matrix_battle_sentry_inf_test.log` |
| `war-colors-sentry` | `scripts/play-conker-war-sentry.sh` | 8 (max **31**) | `journal/map_learn/.conker_war_sentry_inf_test.log` |
| `virtual-agent-office` | `scripts/play-agent-office.sh` | (per script) | per script |
| `launch-aio-mod` | `scripts/launch-perfect-dark-aio.sh` | — | `null` |
| `play-learn-step` | `scripts/play-learn-step.sh` | step positional | `journal/map_learn/.last_validation_launch.log` |
| `validate-next` | `scripts/validate-maps.sh` | args `next` | `journal/map_learn/.last_validation_launch.log` |
| `play-last-test-map` | `scripts/play-last-test-map.sh` | — | per script |

**Security:** `resolveScript()` MUST reject any path not under repo `scripts/` whitelist.

---

## 5. War Colors UI sim resolution (`resolveWarColorsSimOptions`)

| UI state | `numSims` emitted | Flags emitted |
|----------|-------------------|---------------|
| `solo=true` | **omit** `--num-sims` | `--solo` only |
| `fullBattle=true` | **31** (not 50) | `--full-battle` |
| default | 8 if invalid | `--num-sims 8` |
| `numSims > 31` | clamped to **31** | `--num-sims 31` |

**MUST NOT emit:** `--solo` + `--num-sims N` + `--full-battle` together.

---

## 6. Curriculum UI

| Constant | Value |
|----------|-------|
| `CURRICULUM_EXPECTED_COUNT` | **31** |
| Phase count | **8** |

**Phases** (`CURRICULUM_PHASES` in `main.js`):

| Phase `id` | Title | Step numbers |
|------------|-------|--------------|
| `spawns` | Spawns & Pads | 1, 2 |
| `weapons-loadout` | Weapons, Ammo & Loadout | 3, 4, 5 |
| `bots-waypoints` | Waypoints & Bots | 6 |
| `koth-ctf` | KOTH & CTF | 7, 8, 9, 10 |
| `pipeline` | Pipeline & Fixtures | 11–18 |
| `match-modes` | Match Modes (Scenarios 1–3) | 19–22 |
| `bots-launch` | Bots, Loadout & Boot Stage | 23–27 |
| `advanced` | Advanced (Hill, Seg, Hygiene, Cover) | 28–31 |

**Tab requirement:** Map Launcher tab MUST show test maps **and** curriculum steps (not Map Learning tab only).

---

## 7. Window lifecycle (must)

1. `createWindow()` before sync Python curriculum load
2. `ready-to-show` → `focusMainWindow()` (`show`, `focus`, `app.dock.show`, `center`)
3. **2.5s fallback** if `ready-to-show` never fires
4. Second instance → focus existing; print *"PD Map Launcher already running — focusing existing window."*

---

## 8. Verification

```bash
./scripts/launch-map-launcher.sh
sleep 15 && pgrep -f 'map-launcher-electron' && echo OK

# Curriculum count
python3 -c "
import json
m=json.load(open('tools/map-launcher-electron/curriculum-manifest.json'))
assert len(m['steps'])==31, len(m['steps'])
print('manifest steps:', len(m['steps']))
"
```
