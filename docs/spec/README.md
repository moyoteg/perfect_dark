# Domain specifications — map creation

Normative contracts for **custom multiplayer arena authoring** only.  
Requirement IDs: [`SPEC.md`](../../SPEC.md) (`R-MAP-*`).  
Verification stories: [`STORIES.md`](../../STORIES.md).

| File | Role |
|------|------|
| **[MAP_CREATION.md](MAP_CREATION.md)** | **Primary normative spec** — five-file contract, paths, coordinates, validation, seg modes, deploy, registration, test boot, acceptance commands |
| [CURRICULUM.md](CURRICULUM.md) | 31 learn steps: slug, module, scenario, seg mode, launch flags |
| [CLI_AND_LIMITS.md](CLI_AND_LIMITS.md) | **Appendix:** map-test CLI flags (`--test-map`, `--scenario-*`, stage hex table, coordinate contract). Kit/War Colors/Matrix argv trimmed to cross-references |

**Generated (do not hand-edit):** [`../MAP_DETERMINISTIC_SPEC.md`](../MAP_DETERMINISTIC_SPEC.md)

**Operator guides (non-normative but authoritative for workflow):**

| File | Role |
|------|------|
| [`../MAP_MAKING_WIKI.md`](../MAP_MAKING_WIKI.md) | Master workflow, checklists, troubleshooting |
| [`../MAP_CREATION.md`](../MAP_CREATION.md) | Binary layouts, intro opcodes, C wiring detail |

---

## Out of scope (see other PR branches — files retained)

These specs are **not** indexed in [`SPEC.md`](../../SPEC.md) v0.4.0-map-creation:

| File | Notes |
|------|-------|
| [WAR_COLORS.md](WAR_COLORS.md) | Retail-slot mp13 overlay, sim caps, pad probe — optional pattern only (`R-MAP-20`) |
| [MAP_LAUNCHER.md](MAP_LAUNCHER.md) | Electron Map Launcher UI + whitelist IDs — use `./scripts/play-learn-step.sh` for CLI curriculum |

Kit Hub domain spec: [`docs/spec/KIT_HUB.md`](docs/spec/KIT_HUB.md). Agent Office, LLM Play, and Anim Lab IPC remain in [`API_CONTRACTS.md`](../../API_CONTRACTS.md) and [`ARCHITECTURE.md`](../../ARCHITECTURE.md).
