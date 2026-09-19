# Perfect Dark & PragCore Ecosystem — Comprehensive User Journeys Specification

This specification documents the **30 Canonical User Journeys (UJ-01 through UJ-30)** spanning the fifteen operational personas of the platform ecosystem:
1. **Level Designer & Visual Creator** (Creative & Spatial Authoring)
2. **Combat Simulator Player** (Gameplay, Bot Battles & High-Scale Combat)
3. **Office Walker & Operations Manager** (Diegetic Agent Presence & Monitoring)
4. **Security Officer & Risk Gatekeeper** (Human-in-the-Loop Sovereign Approvals)
5. **Fleet Commander & Swarm Operator** (Flight Control Large-Scale Management)
6. **Multimodal Voice Operator** (Hands-Free Speech Interaction & ASR)
7. **Enterprise & Organization Administrator** (Multi-Tenant Isolation & Partitioning)
8. **Technical Asset Modder & Animator** (Skeletal Rigs, Props & Weapon Viewmodels)
9. **Narrative & Campaign Designer** (Single-Player Objectives, Cutscenes & Briefings)
10. **Release Engineer & Quality Guardian** (Deterministic CI/CD, Gates & AI Navigation)
11. **Multiplayer Competitor & Netplay Host** (Over-The-Wire Mod Synchronization & Desync Prevention)
12. **Sound Designer & Audio Engineer** (Procedural Earcon & ADPCM Audio Compilation)
13. **Cinematographer & Cutscene Director** (Spline Tracks, Camera Choreography & Briefing Playback)
14. **QA Automation Engineer & Bot Simulation Lead** (Headless Emulation, Balance Telemetry & Scenario Stress)
15. **Spatial Optimization Engineer & 3D Artist** (Multi-Room Portals, PVS Occlusion & OBJ Ingestion)

---

## I. User Journey Architecture Matrix

| Journey ID | Title | Primary Persona | System Surfaces | Core Interaction Invariants |
|---|---|---|---|---|
| **UJ-01** | **Conversational Level Synthesis** | Level Creator | 3D Map Editor, PragChat Assistant (`⌘K`) | Natural language prompt $\to$ compliant geometry & pads (`Y = 10.0`) $\to$ Three.js hot-reload $\to$ auto-saved to map library |
| **UJ-02** | **Custom Map Library & Browsing** | Creator / Player | Map Editor Drawer, `File → Open Saved…` (`⌘O`) | Multi-directory discovery (`maps/`, `map_learn/`, `mods/`) $\to$ 44-map catalog with 1-click load |
| **UJ-03** | **1-Click Instant Map Playtesting** | Level Creator | Map Editor Header, `T` Hotkey | Fast3D binary build $\to$ detached `./build/pd.arm64 --test-map` $\to$ live in-engine exploration at spawn pad 0 |
| **UJ-04** | **High-Scale Combat Sim Battle** | Combat Player | Map Launcher, `play-matrix-battle.sh` | Deploy `matrix_battle_64` (83 pads, 64 spawns) $\to$ 50 simulants, teams, dark difficulty $\to$ live battle |
| **UJ-05** | **Agent Office Clock-In & Presence** | Office Manager | `play-agent-office.sh` (dataDyne / CI) | Walk physical floor $\to$ 8 agents typing (`MA_AGENT_WORK`) $\to$ approach $\to$ halts typing, rotates to `MA_AGENT_TALK` |
| **UJ-06** | **Diegetic Monitors & Perfect Menu** | Office Manager | In-World Agent Workstation, Central Console | Stand at desk $\to$ press **Z** $\to$ N64 computer dialog renders live tasks, thoughts, and health from Office Service (:8791) |
| **UJ-07** | **Multimodal Voice Dialogue & ASR** | Voice Operator | Whisper ASR, Spatial TTS, Director | Mic speech $\to$ Whisper ASR $\to$ Director routes to agent brain $\to$ spatial audio voice reply in 3D world |
| **UJ-08** | **High-Consequence Security Gate** | Security Officer | Security Console, In-World HUD | Risky agent action staged $\to$ suspended in `PENDING_APPROVAL` $\to$ approach Security desk $\to$ **Z Approve / B Deny** |
| **UJ-09** | **Swarm Fleet Orchestration** | Fleet Commander | Flight Control Dashboard & CLI | Swarm load balancing & incident playbooks $\to$ top 8 priority agents projected into 3D desks |
| **UJ-10** | **Multi-Tenant Workspace Partitioning** | Enterprise Admin | Electron Location/Tenant Picker, CLI | Select tenant (`engineering`, `security`, `default`) $\to$ isolated memory, tasks, and audit logs under `tenants/<tenant_id>/` |
| **UJ-11** | **Character & Animation Studio Lab** | 3D Modder | Animation Lab (`anim_lab`), Asset Catalog | Skeletal rigs, bone hierarchies, animation timeline $\to$ hot-preview in 3D canvas $\to$ export & test in game |
| **UJ-12** | **Plain-Language Demystification** | Curious User | 1-Click Starter Chip (*"Explain..."*) | Sub-120ms plain-language synthesis demystifying 3D rooms, pads, compilers, and swarm architectures with zero AI slop |
| **UJ-13** | **Campaign Mission & Objectives** | Narrative Designer | `tools/pdmap/mission_compiler.py` | Objective hierarchy (Primary, Secondary, Secret), difficulty scaling, briefing text, guards $\to$ `Usetup<name>Z` |
| **UJ-14** | **Declarative Weapon & Gunplay** | Weapon Modder | `tools/pdmap/weapon_compiler.py` | `weapons.json` $\to$ procedural Rareware modeldef, ammo types, dual-wield flags, and secondary fire modes |
| **UJ-15** | **Neural Texture Upscaling (MLX)** | Remaster Artist | `tools/asset_upgrader/mlx_backend.py` | Apple Silicon MLX RealESRGAN 4x upscaler with high-fidelity Lanczos fallback preserving alpha channels |
| **UJ-16** | **Turnkey Mod Packaging & Signing** | Mod Distributor | `tools/pdmap/pd_pack.py`, `pd_mod.py` | Bundling into cryptographically verified `.pdmod` packages with SHA-256 integrity and 1-click install |
| **UJ-17** | **Heritage GoldenEye Conversion** | Retro Archivist | `goldeneye-aio`, `setup_c_preprocess.py` | Asset table ingestion, room/portal/pad remapping into Perfect Dark engine with zero C source tampering |
| **UJ-18** | **Interactive 3D Object Vitrine** | World Builder | `tools/pdmap/gen_object_catalog.py` | Parsing `constants.h` `MODEL_*` into 3D grid curriculum map with visual markdown/PNG legend |
| **UJ-19** | **Mechanical Release & Quality Gate** | Release Engineer | `tools/release_gate.py`, `make readiness` | Mechanical pre-flight verification across all subsystems with exit code 0 and 20-property compliance |
| **UJ-20** | **Procedural Navmesh & Reciprocity** | AI Programmer | `tools/pdmap/navmesh.py` | Ray-casting obstacle clipping $\to$ strict reciprocal symmetry ($A \leftrightarrow B$) $\to$ zero stuck bots |
| **UJ-21** | **Multiplayer Network Mod Sync** | Netplay Host | `port/include/net/net_automation.h` | Pre-flight hash handshake (`NET_MOD_HASH_LEN = 65`) $\to$ match verification $\to$ desync prevention |
| **UJ-22** | **Declarative Audio & SFX Synthesis** | Audio Engineer | `tools/pdmap/audio_compiler.py` | `audio.json` validation $\to$ volume bounding $[0.0, 2.0]$ $\to$ procedural laser/shotgun/shield generation |
| **UJ-23** | **Cinematic Cutscenes & Splines** | Cinematographer | `tools/pdmap/mission_compiler.py` | 30Hz camera spline interpolation $\to$ position/look_at/FOV continuity $\to$ in-engine cutscene choreography |
| **UJ-24** | **Headless Bot QA & Scenario Stress** | QA Automation Lead | `tools/pdmap/level_compiler.py` | Headless engine simulation (`--test-frames`) $\to$ KOTH, CTF, Briefcase, and Combat rules verification |
| **UJ-25** | **Multi-Room Connected Geometry** | Senior Architect | `tools/pdmap/seg.py` | Multi-room box faces $\to$ `build_multiroom_seg` $\to$ zero G_VTX validation errors $\to$ room portal boundaries |
| **UJ-26** | **Universal 3D Mesh Importer** | External 3D Artist | `tools/pdmap/mesh_to_level.py` | Wavefront OBJ parsing $\to$ bounding box triangulation $\to$ floor height detection $\to$ pad elevation ($+10.0$) |
| **UJ-27** | **Cross-Office Social Bus Routing** | Remote Team Lead | `service/social_bus.py`, `office_service.py` | Inter-office event bus $\to$ rumor and guard report propagation (`g5` $\to$ `ci`) $\to$ activity feed stream |
| **UJ-28** | **Dynamic Character Table Expansion** | Character Artist | `src/include/files.h`, `characters.json` | Expanded `NUM_FILES = 4096` $\to$ `characters.json` schema validation $\to$ runtime body/head binding |
| **UJ-29** | **Hermetic Account Pooling & LLM Lease** | Autonomous AI Lead | `service/account_pool.py` | Zero plaintext token leak $\to$ role-scoped lease checkout/checkin $\to$ provider failover routing |
| **UJ-30** | **Turnkey Unified Release Packaging** | Platform Publisher | `scripts/release/package-unified-dist.sh` | Standalone bundle generation $\to$ 5 core pillars $\to$ SHA256SUMS.txt and MANIFEST.json verification |

---

## II. Detailed Specifications & Interaction Contracts

### UJ-01: Conversational Level Synthesis (PragChat Studio Assistant)
- **Goal**: Creator uses natural language to build balanced, playable 3D arenas without manual vertex or pad positioning.
- **Preconditions**: Map Editor server running on `:8765` or standalone desktop bundle open.
- **Step-by-step Flow**:
  1. Creator opens the 3D Map Editor and presses `<kbd>⌘K</kbd>` (or clicks `[ PragChat ⌘K ]` in the 50px executive header).
  2. The centered frosted obsidian modal appears with live emerald pip (`● PragChat Active`).
  3. Creator inputs a prompt (e.g. *"Symmetrical 2-room sniper duel with elevated perches and shotgun pickups"*).
  4. Client dispatches `POST /api/chat-generate` with prompt, current map state, and session history.
  5. The backend spatial grammar engine synthesizes compliant geometry, rooms, portals, and pads (enforcing `Y = 10.0` floor offset and contiguous pad indices).
  6. Backend automatically persists the synthesized arena to `journal/uff_viewer/maps/<slug>.json`.
  7. Viewport immediately hot-reloads the new 3D geometry in Three.js, updates `currentMapId`, marks document clean, and displays confirmation toast.
- **Automated Verification**: `tests/test_generative_map_chat.py`, `tests/test_pragchat_editor_integration.py`.

---

### UJ-02: Custom Map Library Browsing, Management & 1-Click Load
- **Goal**: Access, inspect, and open any custom arena created across the project's history.
- **Preconditions**: Editor server active.
- **Step-by-step Flow**:
  1. Creator clicks `File → Open Saved…` (`⌘O`) in the menu bar.
  2. Client queries `GET /api/maps`.
  3. Server dynamically scans and aggregates all known map sources:
     - Primary user maps: `journal/uff_viewer/maps/`
     - Curriculum & learned maps: `journal/map_learn/maps/`
     - Mod pack stages: `mods/mod_allinone/levels/`
  4. Server deduplicates entries, filters out non-level files, and returns sorted catalog with `name`, `source`, and `padCount`.
  5. Map picker dialog displays the complete list: `matrix_battle_64`, `cyber_arena`, `sniper_duel`, `koth_facility`, `warehouse_bunker`, `full_arena`, `my_arena`, `parade_map`, etc.
  6. Creator selects an arena: client fetches `GET /api/maps/:name` and renders geometry, pads, and weapon anchors into the 3D scene.
- **Automated Verification**: `tests/test_user_journeys.py::test_journey_02_map_library_aggregation`.

---

### UJ-03: 1-Click Instant Map Playtesting (`T` Hotkey)
- **Goal**: Immediate sub-second turnaround from 3D visual editor to running in-engine gameplay.
- **Preconditions**: `pd.arm64` binary built in `build/` directory.
- **Step-by-step Flow**:
  1. Creator edits or views an arena in the 3D editor.
  2. Creator presses `T` (or clicks `Test Map`).
  3. Client dispatches `POST /api/test-map` with full level specification JSON.
  4. Server compiles Fast3D display lists, tile collision matrices, and pad headers into the `uff` slot.
  5. Server detaches game process `./build/pd.arm64 --test-map --solo` (or with bots).
  6. Native engine boots directly into the custom arena at pad 0; player immediately walks, explores, and fires weapons.
- **Automated Verification**: `tests/test_editor_entity_authoring.py::test_run_test_map_dry_run_with_entities`.

---

### UJ-04: High-Scale Combat Simulator Scenario Battle
- **Goal**: Player tests tactical AI simulant combat at scale in custom arenas with up to 64 bots.
- **Preconditions**: Native PC port binary compiled with `MPFEATURE_8BOTS` and expanded chrslot tables.
- **Step-by-step Flow**:
  1. Player launches Map Launcher or executes `./scripts/play-matrix-battle.sh`.
  2. Script invokes `python3 tools/pdmap.py build matrix_battle_64 --seg --deploy`.
  3. Maps 64 spawn pads into two opposing flanks (North team 0 vs South team 1) across a 5000x3000 box arena.
  4. Boots `./build/pd.arm64 --test-map --moddir mods/mod_allinone --scenario-0 --num-sims 50 --teams-battle --sim-difficulty 5`.
  5. 50 simulants spawn across the battle lines with custom weapon sets and engage in real-time combat.
- **Automated Verification**: `tests/test_pd_scenario_simulation.py`, `tests/test_pd_live_bot_playtest.py`.

---

### UJ-05: Virtual Agent Office Clock-In & Embodied Presence
- **Goal**: Operator enters physical office space where autonomous AI agents exist as living, reactive characters.
- **Preconditions**: Office Service running on `:8791`; native binary linked with `llm_bridge`.
- **Step-by-step Flow**:
  1. Operator launches `./scripts/play-agent-office.sh` (dataDyne G5) or `./scripts/play-agent-office-ci.sh` (Carrington Institute).
  2. Player spawns in the reception lobby facing the open bullpen floor.
  3. 8 agents sit at designated workstations executing typing animations (`MA_AGENT_WORK`).
  4. Player walks toward an agent desk (e.g. Architect at Desk 1).
  5. Proximity sensor (`pad_dist < 250 units`) triggers agent state transition: typing stops, character stands/turns head toward player, and enters `MA_AGENT_TALK` posture.
- **Automated Verification**: `tests/test_office_director_presence.py`, `tests/test_pd_custom_chr_deploy.py`.

---

### UJ-06: Diegetic Monitors & In-Game Perfect Menu
- **Goal**: Read live agent thoughts, tasks, and system health directly inside the 3D game world without alt-tabbing.
- **Preconditions**: Office floor active; player adjacent to agent desk or central status monolith.
- **Step-by-step Flow**:
  1. Player approaches workstation and presses **Z** (Action button).
  2. Game engine invokes `office_bridge_query_agent(agent_id)`.
  3. Bridge queries `GET http://127.0.0.1:8791/api/office/agents/:id/status`.
  4. In-game UI summons the authentic N64 green-phosphor computer dialog overlay (`menu_render_dialog`).
  5. Dialog displays: Current Goal, Sub-tasks, Thought Stream, and CPU/Memory Telemetry.
  6. Pressing **B** dismisses the monitor overlay cleanly.
- **Automated Verification**: `tests/test_office_service_http_api.py`, `tests/test_office_director_presence.py`.

---

### UJ-07: Multimodal Voice Dialogue & Spatial ASR
- **Goal**: Hands-free conversation with in-game agents using microphone voice input and spatial 3D audio output.
- **Preconditions**: CoreML Whisper ASR model loaded; Spatial Audio TTS initialized.
- **Step-by-step Flow**:
  1. Operator holds **V** key (or controller Push-to-Talk) and speaks: *"Architect, what is the status of the level compiler?"*
  2. Native audio capture buffers raw PCM and routes to `Whisper ASR` on Apple Silicon Neural Engine.
  3. Transcription emits text event into Director bridge (`POST /agent/chat`).
  4. Agent LLM generates concise response.
  5. Spatial TTS synthesizer generates procedural speech audio and positions sound source at agent's 3D head coordinates.
  6. Player hears directional audio echoing naturally off facility walls.
- **Automated Verification**: `tests/test_office_director_asr.py`, `tests/test_spatial_tts.py`.

---

### UJ-08: High-Consequence In-World Security Approval Gate
- **Goal**: Human operator reviews and signs off on high-risk autonomous agent operations inside the simulation.
- **Preconditions**: An agent stages a destructive action (e.g. database migration, external credential use).
- **Step-by-step Flow**:
  1. Background agent proposes action with risk tier `CRITICAL`.
  2. Security engine suspends execution in `PENDING_APPROVAL` status.
  3. In-game Security desk monitor flashes amber alarm pip.
  4. Red emergency strobe illuminates in the 3D office corridor.
  5. Operator walks to the Security desk, presses **Z** to examine the staged payload.
  6. Operator presses **Z to Approve** or **B to Reject**.
  7. Engine dispatches signed cryptographic decision back to Office Service; agent resumes or aborts.
- **Automated Verification**: `tests/test_office_examine_bridge.py`, `tests/test_office_service.py`.

---

### UJ-09: Sovereign Swarm Fleet Orchestration (Flight Control ↔ Office)
- **Goal**: Manage large-scale distributed agent swarms with physical office spatial embodiment.
- **Preconditions**: Flight Control active; `office-service-client.ts` configured.
- **Step-by-step Flow**:
  1. Fleet commander monitors thousands of agents across distributed nodes via Flight Control.
  2. Flight Control `OfficeServiceClient` continuously queries Office Service `/api/office/health` and `/fleet`.
  3. Top 8 priority agents project down into the 8 physical desks in Perfect Dark.
  4. When Flight Control detects an anomaly (e.g. rate limit, latency spike), Incident Playbook Engine triggers remediation.
  5. Anomaly alerts automatically propagate to the physical Ops and Security desks in 3D.
  6. Social bus (`POST /social/route`) coordinates cross-facility handoffs between dataDyne G5 and Carrington Institute.
- **Automated Verification**: `flight-control/src/swarm/__tests__/office-service-client.test.ts`.

---

### UJ-10: Multi-Tenant Workspace Partitioning
- **Goal**: Complete organizational and data isolation across teams and enterprise environments.
- **Preconditions**: Office Service HTTP API with multi-tenant header support (`X-Office-Tenant`).
- **Step-by-step Flow**:
  1. User selects tenant (e.g. `engineering`, `security`, `executive`) via launcher or CLI.
  2. Requests include `X-Office-Tenant: <tenant_id>`.
  3. Office Service routes memory, task queues, and connector leases under `tenants/<tenant_id>/`.
  4. In-engine office floor loads tenant-specific agent identities and monitors.
  5. All data structures remain strictly isolated with zero cross-tenant state bleed.
- **Automated Verification**: `tests/test_office_multitenant_stress.py`, `tests/test_office_tenant_paths.py`.

---

### UJ-11: Character & Animation Studio Lab
- **Goal**: 3D modder inspects skeletal rigs, edits keyframe curves, and tests animations in-engine.
- **Preconditions**: Animation Lab server running (`journal/anim_lab`).
- **Step-by-step Flow**:
  1. Modder opens Animation Lab surface.
  2. 3D canvas renders skeletal bone hierarchies and character models.
  3. Modder selects animation clips, scrubs the timeline, and tests posture blends.
  4. Modder exports animation data to game format (`pd_anim_encode.py`).
  5. Launches `pd.arm64 --test-anim` to verify motion in native engine with 0.00mm bone drift.
- **Automated Verification**: `tests/test_pd_anim_studio.py`, `tests/test_pd_anim_encode.py`.

---

### UJ-12: Plain-Language Demystification (Zero AI Slop)
- **Goal**: Provide instant, accessible plain-language explanations of system mechanics for regular humans.
- **Preconditions**: PragChat Assistant active.
- **Step-by-step Flow**:
  1. User clicks the 1-click starter chip: *"Explain to a regular person how all of this is very useful"*.
  2. Generative Assistant generates immediate sub-120ms response explaining 3D rooms, pads, compilers, and agent swarms in clear, relatable terms.
  3. Interface strictly obeys anti-slop guidelines: zero corporate buzzwords, zero performative telemetry, zero emojis, pure aura and clarity.
- **Automated Verification**: `tests/test_generative_map_chat.py::TestGenerativeAssistantChat::test_conversational_explanation`.

---

### UJ-13: Single-Player Campaign Mission & Objective Authoring
- **Goal**: Narrative designer authors complete single-player missions with multi-tier objectives, briefings, and enemy guards.
- **Preconditions**: `tools/pdmap/mission_compiler.py` present.
- **Step-by-step Flow**:
  1. Designer authors declarative mission JSON specifying:
     - Briefing text
     - Objective hierarchy (`enter_room`, `throw`, `holograph`) with difficulty tier gating (`agent`, `special_agent`, `perfect_agent`)
     - Enemy guard placements (`pad`, `body`, `head`, `weapon`, `team`)
  2. Compiler validates objective preconditions and contiguous pad bindings.
  3. Compiler packs `OBJTYPE_BRIEFING`, `OBJTYPE_OBJECTIVE`, and `Chr` definitions into the Rareware `Usetup<name>Z` binary stream.
  4. Compiler deploys stage files to game assets directory.
  5. Engine boots into campaign mode: objectives appear on pause screen, update in real-time on completion, and fail on critical violations.
- **Automated Verification**: `tests/test_pd_mission_compiler.py`, `tests/test_pd_mission_cli_integration.py`.

---

### UJ-14: Declarative Weapon Creation & Viewmodel Rigging
- **Goal**: Combat modder creates custom firearms with unique ballistics, dual-wield flags, and procedural Rareware modeldefs.
- **Preconditions**: `tools/pdmap/weapon_compiler.py` and `mods/mod_allinone/weapons.json` present.
- **Step-by-step Flow**:
  1. Modder defines weapon in `weapons.json` (category, damage, clip size, ammo type, fire rate, dual-wield support).
  2. Compiler runs schema validation checking ammo enum adherence and non-negative parameters.
  3. Procedural mesh compiler generates Fast3D display lists within F3DEX2 vertex load limits (`G_VTX` 16 verts/load).
  4. Compiler packs modeldef node tree (`DL_TYPE = 0x18`, `SKEL_BASIC = 0x02`) at `MODEL_VMA = 0x05000000`.
  5. In-game player equips weapon: dual-wield animations trigger correctly, HUD displays tailored ammo count, and muzzle flash registers on firing.
- **Automated Verification**: `tests/test_pd_weapon_json.py`, `tests/test_pd_weapon_viewmodel.py`.

---

### UJ-15: Neural Texture Upscaling & Asset Enhancement (MLX Core)
- **Goal**: Remaster artist enhances low-resolution N64 textures using on-device Apple Silicon GPU acceleration.
- **Preconditions**: `tools/asset_upgrader/mlx_backend.py` present.
- **Step-by-step Flow**:
  1. Modder queues batch of 32×32 or 64×64 N64 texture assets for upscaling.
  2. `MLXCoreImageUpgrader` initializes RealESRGAN model pipeline with tile size 256 on Apple Silicon Metal framework.
  3. Neural pipeline evaluates tiles in parallel, upscaling by 4× while preserving crisp edge contrasts.
  4. If headless or GPU environment is constrained, pipeline falls back gracefully to high-fidelity Lanczos resampling preserving RGBA alpha channels.
  5. Output textures saved to mod directory; game reloads enhanced textures seamlessly.
- **Automated Verification**: `tools/asset_upgrader/mlx_backend.py`, `tests/test_mesh_preview_golden.py`.

---

### UJ-16: Turnkey Mod Packaging, Manifest Signing & Distribution
- **Goal**: Mod distributor bundles levels, characters, weapons, and scripts into cryptographically verifiable `.pdmod` packages.
- **Preconditions**: `tools/pdmap/pd_pack.py` and `tools/pdmap/pd_mod.py` present.
- **Step-by-step Flow**:
  1. Curator runs `pd_pack.py pack <mod_dir> --output <name>.pdmod`.
  2. Packager filters out ephemeral files (`.DS_Store`, `.pyc`, `__pycache__`).
  3. Generates cryptographic SHA-256 digest for every contained asset file.
  4. Embeds `manifest.json` containing version, author, checksums, and entrypoints.
  5. End-user runs `pd_pack.py install <name>.pdmod`: packager verifies SHA-256 hashes against manifest before unpacking into `mods/`.
- **Automated Verification**: `tests/test_pd_mod_pack.py`, `tests/test_pd_mod_manifest.py`.

---

### UJ-17: Cross-Title Heritage GoldenEye/Goldfinger Conversion
- **Goal**: Retro archivist converts GoldenEye 007 and Goldfinger stages into native Perfect Dark levels without modifying C engine source.
- **Preconditions**: `goldeneye-aio` assets and `tools/pdmap/setup_c_preprocess.py` available.
- **Step-by-step Flow**:
  1. Archivist selects classic stage (e.g. Facility, Surface, Runway).
  2. Preprocessor parses classic `setup.c` object declarations and coordinate spaces.
  3. Remaps weapon and prop IDs from GoldenEye constant tables to Perfect Dark equivalents (`PROP_KEYCARD` $\to$ `MODEL_KEYCARD`).
  4. Pads and portal apertures adjusted to meet Perfect Dark collision bounds and `Y = 10.0` offsets.
  5. Compiles binary stage bundle and launches in Perfect Dark with modern dual-analog controls and 60 FPS rendering.
- **Automated Verification**: `tests/test_pdmap_build_domain.py`, `tools/pdmap/setup_c_preprocess.py`.

---

### UJ-18: Interactive 3D Object Catalog & Prop Set Dressing
- **Goal**: World builder visually previews and selects from hundreds of in-game props, doors, and computer consoles.
- **Preconditions**: `tools/pdmap/gen_object_catalog.py` and `src/include/constants.h` available.
- **Step-by-step Flow**:
  1. Builder runs `gen_object_catalog.py <keywords>` (e.g. `door`, `desk`, `console`).
  2. Tool parses `constants.h` extracting all matching `MODEL_*` IDs.
  3. Generates a curriculum 3D level placing each model in a labeled 8-column grid with 700-unit spacing.
  4. Synthesizes a top-down visual map (PNG) and Markdown legend mapping (row, col) to model name and hex ID.
  5. Builder walks the 3D grid in-engine, identifies the exact desired console, and copies the ID into their custom level JSON.
- **Automated Verification**: `tools/pdmap/gen_object_catalog.py`, `tests/test_pdmap_objects.py`.

---

### UJ-19: Mechanical Release Gate & Diagnosability Quality Gate
- **Goal**: Autonomous swarm and release engineers verify 100% subsystem integrity before tagging releases or pushing code.
- **Preconditions**: `tools/release_gate.py` and test matrix present.
- **Step-by-step Flow**:
  1. Pre-commit hook or CI workflow dispatches `python3 tools/release_gate.py`.
  2. Script executes individual subsystem validation runners:
     - Account pool director (`service.account_pool`)
     - Animation Lab poses & bone hierarchies (`tools/pdmap.py validate animlab`)
     - Map binary contract & display list integrity
  3. Aggregates results into typed `ReleaseGateReport` with individual latency benchmarks and evidence lines.
  4. Asserts 20-Property Diagnosability standard ($\ge 75\%$) and emits structured JSON-line summary.
  5. Exits 0 on total nominal verification, or fails fast with exact root-cause diagnostics.
- **Automated Verification**: `tools/release_gate.py`, `tests/test_unified_release_package.py`.

---

### UJ-20: Procedural Navmesh & Reciprocal Waypoint Auto-Generation
- **Goal**: Gameplay programmer generates complex multi-room waypoint graphs for simulant bots with zero crashes.
- **Preconditions**: `tools/pdmap/navmesh.py` present.
- **Step-by-step Flow**:
  1. Programmer supplies room bounding boxes and obstacle matrices.
  2. Navmesh generator decomposes floor polygons into candidate navigation nodes.
  3. Ray-casting module evaluates line-of-sight between all candidate pairs using Liang-Barsky parametric clipping.
  4. Evaluates vertical elevation differentials ($|dY| \le 40$ units step-height limit).
  5. Enforces strict reciprocal symmetry: if node $A$ connects to node $B$, node $B$ must connect to node $A$.
  6. Prunes orphan nodes and caps maximum node degree ($\le 7$) to prevent simulant stack overflow.
  7. Packs waypoint graph into `padsZ` binary table ready for in-engine bot pathfinding.
- **Automated Verification**: `tests/test_pd_navmesh.py`.

---

### UJ-21: Multiplayer Network Mod Over-The-Wire Synchronization
- **Goal**: Multiplayer host and peers ensure identical level, weapon, and character checksums before match initiation to prevent desync crashes.
- **Preconditions**: `port/include/net/net_automation.h` and `port/src/net/net_automation.c` compiled into engine.
- **Step-by-step Flow**:
  1. Host packages active mod directory into `.pdmod` package with SHA-256 hash.
  2. Host executes `./build/pd.arm64 --net-mod-hash <H>`: engine emits `mod_hash_configured`.
  3. Client connects and submits its local mod package digest via `--verify-mod-hash <H>`.
  4. Engine runs `netModSyncVerify()`:
     - If hashes match: engine logs `NET_MOD_SYNC: event=hash_verified status=1` and begins peer game simulation.
     - If hashes mismatch: engine logs `NET_MOD_SYNC: event=hash_mismatch status=2` and halts network handshake with explicit mismatch telemetry.
- **Automated Verification**: `tests/test_pd_net_mod_sync.py`.

---

### UJ-22: Declarative Audio Engine & Procedural Sound Design
- **Goal**: Sound designer authors, validates, and injects custom SFX and ambient background audio without hex editing sound banks.
- **Preconditions**: `tools/pdmap/audio_compiler.py` and `mods/mod_allinone/audio.json` present.
- **Step-by-step Flow**:
  1. Designer configures `audio.json` with sound effects (`id`, `file`, `volume`, `pitch`, `loop`).
  2. Compiler enforces volume bounding within $[0.0, 2.0]$ and rejects duplicate IDs.
  3. Procedural acoustic synthesizer generates calibrated waveforms for missing assets (`generate_laser_sfx`, `generate_shotgun_sfx`, `generate_shield_sfx`, `generate_ambient_drone`).
  4. Audio compiler packages audio manifest into Rareware ADPCM tables ready for N64 sound driver playback.
- **Automated Verification**: `tests/test_pd_audio_json.py`.

---

### UJ-23: Campaign Cinematic Cutscenes & Camera Splines
- **Goal**: Cinematographer scripts dynamic in-engine camera choreography, actor movements, and briefing cinematics.
- **Preconditions**: `tools/pdmap/mission_compiler.py` cutscene compiler present.
- **Step-by-step Flow**:
  1. Director defines camera keyframes (`time`, `pos [X, Y, Z]`, `look_at [X, Y, Z]`, `fov`).
  2. Cutscene compiler evaluates spline curve at 30Hz (`interpolate_camera_spline`), producing smooth hermite transitions.
  3. Actor staging positions and animations are coupled to timeline milestones.
  4. Preview cutscene via `pdmap mission --play-cutscene <mission_id>` in headless or windowed player.
  5. Compiles cinematic track directly into `Usetup<mission>Z` cutscene header.
- **Automated Verification**: `tests/test_pd_cutscene_studio_integration.py`, `tests/test_pd_mission_cutscenes.py`.

---

### UJ-24: Headless Bot QA Playtesting & Scenario Stress Simulation
- **Goal**: QA engineer conducts automated combat scenario testing (KOTH, CTF, Briefcase) to verify bot balance and map stability.
- **Preconditions**: Native binary built with test harness support (`--test-frames`, `--scenario-X`).
- **Step-by-step Flow**:
  1. QA launches automated scenario runner against target custom level (e.g. `cyber_arena.json`).
  2. Level compiler validates objective pads (e.g. hill pad index 4, CTF base pads 2 & 5).
  3. Headless test harness boots `./build/pd.arm64 --test-map --num-sims 4 --scenario-1 --test-frames 60`.
  4. Simulants execute autonomous combat loops while the harness monitors for memory leaks, stuck states, or abnormal crashes.
  5. Test runner verifies exit code 0 and records kill/death telemetry and objective captures.
- **Automated Verification**: `tests/test_pd_scenario_simulation.py`, `tests/test_pd_live_bot_playtest.py`.

---

### UJ-25: Multi-Room Connected Level Geometry & G_VTX Optimization
- **Goal**: Senior level architect designs complex multi-room facilities with connected portals and zero Fast3D vertex buffer overruns.
- **Preconditions**: `tools/pdmap/seg.py` multiroom builder available.
- **Step-by-step Flow**:
  1. Architect defines individual room box faces and wall apertures.
  2. Multiroom segmentation compiler (`build_multiroom_seg`) generates binary room blocks.
  3. `validate_seg_g_vtx` executes structural validation:
     - Asserts vertex table loads never exceed Fast3D buffer capacity (`MAX_G_VTX = 16`).
     - Verifies face colors and texture coordinate offsets.
     - Confirms portal connection planes match between adjacent room boundaries.
  4. In-engine renderer utilizes room occlusion culling to sustain stable 60 FPS in massive environments.
- **Automated Verification**: `tests/test_pd_multiroom_seg.py`, `tests/test_pd_multiroom_editor_integration.py`.

---

### UJ-26: Universal 3D Mesh Importer (OBJ/GLTF to Playable Stage)
- **Goal**: 3D artist converts external Wavefront OBJ or GLTF models into fully functional, playable Perfect Dark arenas.
- **Preconditions**: `tools/pdmap/mesh_to_level.py` converter available.
- **Step-by-step Flow**:
  1. Artist exports 3D architecture from Blender or Maya as standard `.obj`.
  2. `parse_mesh_geometry()` parses vertex positions and triangulates polygonal faces.
  3. `convert_mesh_to_level()` computes global spatial bounding box and detects floor height (`floor_y`).
  4. Automatically distributes spawn pads across walkable areas, enforcing exact `pad.y = floor_y + 10.0` vertical clearance.
  5. Generates boundary collision walls and exports production level JSON ready for immediate compilation.
- **Automated Verification**: `tests/test_pd_mesh_to_level.py`.

---

### UJ-27: Cross-Office Social Bus Routing & Remote Event Bridging
- **Goal**: Operations manager bridges live in-game events, agent status updates, and security alerts to external team channels.
- **Preconditions**: `service/social_bus.py` and `service/office_service.py` active.
- **Step-by-step Flow**:
  1. Security or worker agent in virtual office triggers an observation (e.g. guard report or completed build).
  2. `SocialBus.route()` serializes event payload (`text`, `from_office`, `to_office`, `kind`).
  3. Event propagates across the in-memory bus (`social.guard_report`).
  4. Office service feeds update in real-time and optionally dispatch outbound webhook to Slack/Discord bridge.
  5. Remote team members monitor office operations without opening the 3D client.
- **Automated Verification**: `tests/test_social_bus.py`, `tests/test_slack_api.py`.

---

### UJ-28: Dynamic Player & Character Table Expansion
- **Goal**: Character artist introduces new playable multiplayer characters and campaign guard skins without recompiling N64 tables.
- **Preconditions**: `src/include/files.h` (`NUM_FILES = 4096`) and `mods/mod_allinone/characters.json` present.
- **Step-by-step Flow**:
  1. Artist defines new character profile in `characters.json` (`id`, `name`, `gender`, `head_filenum`, `body_filenum`, `scale`).
  2. Dynamic file registration allows custom asset filenums up to `MAX_FILE_ID = 0x0FFF` (4095).
  3. Engine dynamically mounts custom character geometry into `g_HeadsAndBodies` and `g_MpBodies`.
  4. New character immediately appears in the Combat Simulator player setup menu with proper head-body alignment and skeleton scaling.
- **Automated Verification**: `tests/test_pd_character_registration.py`, `tests/test_pd_custom_chr_deploy.py`.

---

### UJ-29: Hermetic AI Director & Autonomous Account Pooling
- **Goal**: Autonomous AI lead manages multi-provider LLM leases for virtual office agents with zero secret leakage.
- **Preconditions**: `service/account_pool.py` and `office_director.py` active.
- **Step-by-step Flow**:
  1. Supervisor bootstraps `AccountPool` from environment credentials (`bootstrap_llm_pool_from_env`).
  2. Logger sanitizes all events, strictly redacting plaintext API tokens and environment variable values.
  3. When an agent requires an LLM inference cycle, `AccountPool` checks out a role-scoped lease.
  4. If a provider encounters rate limits or errors, the pool automatically fails over to secondary healthy accounts.
  5. Lease checkin returns token usage and latency metrics to telemetry without state pollution.
- **Automated Verification**: `tests/test_account_pool_director.py`, `tests/test_hermes_director.py`.

---

### UJ-30: Turnkey Unified Release Packaging Pipeline
- **Goal**: Platform publisher builds, audits, and seals complete distribution packages for macOS and Linux users.
- **Preconditions**: `scripts/release/package-unified-dist.sh` present.
- **Step-by-step Flow**:
  1. Publisher runs `./scripts/release/package-unified-dist.sh <dist_dir>`.
  2. Script verifies presence and packages the five core pillars:
     - `apps/Perfect Dark Kit.app` (Desktop suite)
     - `bin/pd.arm64` and `bin/pd-runner` (Native game binaries)
     - `mods/mod_allinone` and `mods/mod_allinone.pdmod` (Validated mod packs)
     - `tools/pdmap` (Level and asset toolchain)
     - Top-level documentation and quick-start guides
  3. Computes `SHA256SUMS.txt` covering every distributed file.
  4. Generates structured `MANIFEST.json` containing git commit, build timestamp, and component booleans.
  5. Verifies package zip integrity and confirms turnkey ready-to-run installation.
- **Automated Verification**: `tests/test_unified_release_package.py`, `tests/test_pd_turnkey_release_bundle.py`.

