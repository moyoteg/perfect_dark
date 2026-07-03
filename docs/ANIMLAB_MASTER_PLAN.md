# Anim Lab — Master Organization Plan

**Canonical requirements & acceptance:** [`ANIMLAB_SPEC.md`](ANIMLAB_SPEC.md) — SDD contract (FR/NFR/AC); **§1.2 baselines are authoritative for live counts** after each reconcile. This doc is the **layout contract** only (coordinates, rooms, palette).

Canonical layout contract for **STAGE_ANIMLAB** (`tools/pdmap/anim_*`, `museum_layout.py`, `builders.py`) and the **Animation Lab** UI (`journal/anim_lab/anim_lab.html`).

Related: [`ANIMLAB_VISION.md`](ANIMLAB_VISION.md) (north star — start here), [`CHARACTER_ANIMATIONS.md`](CHARACTER_ANIMATIONS.md) (animation study guide + build commands), [`MAP_MAKING_WIKI.md`](MAP_MAKING_WIKI.md).

---

## Current state (as built today)

Snapshot from `tools/pdmap/*.py` modules — rebuild with `python3 tools/pdmap.py build animlab --seg --deploy`.

### Spawn hub (room 1)

| Item | Value |
|------|-------|
| Player spawn | pad **0** at **(0, 10, −2200)** |
| Spawn plaza clearance | ±500 u (never carved) |
| Portal ring | 8 compass arches at **800 u** radius |
| Full-tour cycler | pad **171** at **(600, −2200)** — gold carpet |
| Corridor half-width | 250 u (500 u walkable spines) |

### Wings — content counts & anchors

| Compass | Wing | Count | Centre (x, z) | Tile room(s) | Module owner |
|---------|------|-------|---------------|--------------|--------------|
| **N** | Animation districts | **170** guard-playable slots (12 sub-zones) | grid origin **(−2250, −900)** | **2–13** | `anim_catalog.py`, `anim_parade.py` |
| **SW** | Props gallery (curated furniture) | **8** hub props + **4** corridor + **16** vignettes | **(−2200, −3000)** | **1** | `anim_props.py` |
| **W** | Object catalog (showcase scale) | **352** StdObjects, **7** tag districts | hub **(−21000, −26500)** | **14–15, 20–24** | `anim_props.py`, `museum_layout.py` |
| **WSW** | Solo campaign world | **25** footprint islands | origin **(−15800, −8800)**, gate **(−4200, −5200)** | **18** | `anim_levels.py`, `level_footprints.py` |
| **E** | MP / Combat Simulator world | **26** islands | origin **(21800, −3200)**, gate **(9200, −2800)** | **18** | `anim_levels.py` |
| **NE** | Dev & extras annex | **40** islands | origin **(15200, 11800)**, gate **(5200, 3600)** | **18** | `anim_levels.py` |
| **NW** | True-scale yard | **352** models — **163** normal + **189** mega | normal **(15000, −20000)**, mega **(−29000, −29000)** | **16–17** | `anim_props.py`, `museum_layout.py` |
| **SE** | Character gallery | **24** mannequins | **(5500, −4500)** | **19** | `anim_characters.py` |

**Animation district breakdown (170 slots today):**

| District | Anims | Sub-zones | Grid centre (x, z) |
|----------|-------|-----------|-------------------|
| movement | 1 | 1 | (−2250, −900) |
| social | 12 | 1 | (−750, −900) |
| combat | 11 | 1 | (750, −900) |
| react | 9 | 1 | (2250, −900) |
| death | 14 | 1 | (−2250, 300) |
| computer | 10 | 1 | (−750, 300) |
| use | 4 | 1 | (750, 300) |
| other | 8 | 1 | (2250, 300) |
| weapon | 101 | 4 | (−1500, 1500) |
| cutscene | 0 | — | layout reserved, row 3–4 span empty |

**Object catalog tag districts (352 total, 7 active):**

| Tag | Models | Room |
|-----|--------|------|
| furniture | 28 | 14 |
| military | 35 | 15 |
| lab | 25 | 20 |
| architecture | 70 | 21 |
| ci | 10 | 22 |
| skedar | 51 | 23 |
| misc | 133 | 24 |
| eld / lip | 0 each | — (defined in `OBJECT_TAG_ORDER`, no models yet) |

**Levels (91 total):** solo 25 · MP 26 · dev 40 — all **marker-only** (coloured footprint + door-console prop; no embedded bg geometry).

**Wayfinding:** 9 carpet routes · 9 wing gates · 57 distance beacons (routes ≥3000 u, every 2000 u).

**Arena:** half-extent **±32000 u** (s16 tile vertex budget).

### Pad index chain

| Range | Owner |
|-------|-------|
| 0 | Player spawn |
| 1–170 | Parade grid guards |
| 171 | Full-tour cycler |
| 172–908 | StdObject props (737 specs: catalog + true-scale + hub + wayfinding) |
| 909–932 | Character gallery (24) |
| 933–1023 | Level island markers (91) |

Chrnums: parade **0x50+**, tour **0x50+170**, characters after tour, levels N/A (props only).

### Room budget (24 of 25 slots used — **full**)

| Room | Purpose | Prop/chr budget |
|------|---------|-----------------|
| **1** | Hub: spawn, tour, props gallery, corridors, compass rose, wayfinding | hub props only (<30); chr tour + 0 grid |
| **2–13** | Animation guard sub-zones | ≤30 chr / room |
| **14** | Object tag: furniture | ≤200 props |
| **15** | Object tag: military | ≤200 props |
| **16** | True-scale normal wing | ≤200 props |
| **17** | True-scale mega yard | ≤200 props |
| **18** | Level megaworld (all 3 worlds) | 91 marker props |
| **19** | Character gallery | 24 chr |
| **20–24** | Object tags: lab, architecture, ci, skedar, misc | ≤200 props each |

**No spare rooms** for eld/lip tags or a second cutscene body rig without reallocation.

### Known problems (why it feels messy)

1. **Docs vs code drift** — `CHARACTER_ANIMATIONS.md` still references **571** grid slots, **26** sub-zones, and old coordinates (e.g. character gallery x≈2800). Actual grid: **170** guard-playable slots, **12** sub-zones. **570** named anims exist in ROM; **400** are excluded by `parade_guard_playable()` (CUT_*, flag08, Skedar/bike rigs).
2. **Dual object wings** — same **352** models appear in **W** (showcase-shrink catalog) and **NW** (true-scale yard). Purpose differs but navigation is easy to confuse.
3. **Marker vs real content** — level islands are pad-sized footprints + name marker; no stage warp yet. Object catalog props are real StdObjects; level “museum” is metadata-only.
4. **Room-1 collision carve** — megaworld room 18 carves room-1 floor; spines rely on `_ensure_animlab_walk_collision_floors()` to prevent fall-through while the player is still logically in room 1.
5. **NW compass ambiguity** — hub portal **NW** points to mega yard only; normal true-scale also uses NW gates. Two `gate_true_scale_*` entries share one compass wedge.
6. **Cutscene district ghost** — `PARADE_DISTRICT_LAYOUT` reserves a large cutscene grid row but **0** playable entries land there today.
7. **s16 coordinate pressure** — mega true-scale at **(−29000, −29000)** runs against ±32767 tile limits; `museum_s16_half_cap()` clamps carpets.
8. **UI hint drift** — `anim_lab.html` default hint said “props west” while code uses **SW**.
9. **Dev annex overlap** — 40 dev/test/extras stages share purpose with MP test maps; candidate for archive merge.
10. **Prop stack limit** — `cdCollectGeoForCyl` → `propnums[256]`; any room >200 StdObjects risks overflow (catalog tags must stay split).

---

## 1. Design principles

1. **One hub, eight compass purposes** — stand at spawn; each direction answers exactly one question (no overlapping “go west for props OR catalog OR solo”).
2. **Single owner per content class** — Solo / MP / Objects / Characters / Animations / True-scale each have **one** canonical district; no duplicate wings without explicit “scale mode” labelling.
3. **Visual hierarchy: Hub → District gate → Content grid** — portal ring → coloured carpet spine → gate prop → carpet interior → slot grid.
4. **Collision contract** — either **one tile room per walk path segment** OR a **unified room-1 spine** with guaranteed **Y=0** collision quads under every audited route (current hybrid approach).
5. **Marker honesty** — non-geometry wings (levels) use a distinct visual language (footprint + console marker + UI `--boot-stage` hint); never pretend to be walkable level geometry.
6. **Budget-aware** — ≤30 chr/room, ≤200 props/room, ≤24 content rooms; plan changes against the allocation table before adding wings.

---

## 2. Proposed zone map

```
                         [NW] True-scale yard
                    normal (163)     mega (189)
                              \
                               \
    [W] Object catalog -------- HUB (0,-2200) -------- [E] MP world (26)
    352 @ showcase scale          | 8 portals              crimson spine
    7 tag clusters                |                       |
         \                        |                       |
          \                  [N] Animation districts       |
           \                 170 slots / 12 zones         |
            \                     |                       |
             \                    |                       |
    [WSW] Solo world (25) ---- [SW] Props gallery (8) ----+---- [SE] Characters (24)
              gold                      cyan                   purple

                                    [NE] Dev annex (40) — optional → archive
```

### Zone contract (target steady state)

| Direction | Single purpose | Content | Keep? |
|-----------|----------------|---------|-------|
| **N** | Gameplay animation loops | Target **571** named playable* / current **170** guard-safe | Yes |
| **W** | Object catalog @ showcase scale | **352/352** models, **7** tag districts | Yes — canonical object browser |
| **WSW** | Solo story stages | **25/25** retail missions | Yes |
| **E** | Multiplayer maps | **26/26** MP + test MP arenas | Yes |
| **NE** | Internal / dev / mod | **40** today → **≤15** after archive merge | Shrink or merge |
| **SW** | Animation context props | **8** curated furniture vignettes | Yes — not a second catalog |
| **SE** | Character bodies | **24/24** roster | Yes |
| **NW** | True-scale object sizes | **352/352** @ bbox (163 normal + 189 mega) | Yes — pair with W, not merge |

\* **571 target** = 570 named ROM entries + full-tour cycler **or** expanded grid once cutscene/Skedar rigs get alternate bodies. Today `parade_guard_playable()` yields **170**; reaching 571 requires Phase 4 animation architecture (below).

### Showcase museum vs W catalog

**Merge conceptually; keep one placement.** The “showcase museum” **is** the **W** object catalog (showcase shrink via `model_showcase_extents()`). Do **not** maintain a third 352-prop wing. **NW** true-scale is the companion “actual size” yard, not a duplicate catalog UI tab.

---

## 3. Navigation system

### Hub portal ring naming

Pattern: `{COMPASS} · {Short label} · {count}`

| Compass | Portal label | Carpet hex | Gate id |
|---------|--------------|------------|---------|
| N | Animation districts | `#a78bfa` | `gate_districts` |
| SW | Props gallery | `#38bdf8` | `gate_props` |
| W | Object catalog | `#0ea5e9` | `gate_catalog` |
| WSW | Solo world · N | `#f59e0b` | `gate_solo_world` |
| E | MP world · N | `#dc2626` | `gate_mp_world` |
| NE | Dev annex · N | `#64748b` | `gate_dev_world` |
| NW | True scale | `#14b8a6` / `#0d9488` | `gate_true_scale_normal` / `_mega` |
| SE | Character gallery | `#c084fc` | `gate_characters` |

**Fix (Phase 1):** split NW portal into **NW-N** (normal) and **NW-W** (mega) signposts, or label combined portal “True scale (both yards)”.

### Carpet colour standard (fixed palette)

Document in `anim_wayfinding.py` as `WING_CARPET_PALETTE` (future); until then, treat these as immutable:

| Wing | Hex | Floor layer |
|------|-----|-------------|
| Hub neutral | `#888888` | Y=0 collision |
| Compass rose | `#fbbf24` | Y=4 carpet |
| Animation N | `#a78bfa` | Y=4 carpet |
| Props SW | `#38bdf8` | Y=4 carpet |
| Catalog W | `#0ea5e9` | Y=4 carpet |
| Solo WSW | `#f59e0b` / `#b45309` corridor | Y=4 carpet |
| MP E | `#dc2626` / `#991b1b` | Y=4 carpet |
| Dev NE | `#64748b` / `#475569` | Y=4 carpet |
| True-scale NW | `#14b8a6` / `#0d9488` | Y=4 carpet |
| Characters SE | `#c084fc` | Y=4 carpet |
| Full tour | `#ffd166` | Y=4 carpet |

**Floor rule:** **Y=0** = collision quad always; **Y=4** (`marker_y`) = coloured carpet overlay (`floortype="carpet"`). Never paint carpet without a Y=0 quad beneath on walk paths.

### Distance beacons

- Emit only when route length **> 3000 u** (code: `BEACON_MIN_ROUTE_LEN = 3500` — tighten to 3000 in Phase 1 doc alignment).
- Interval: **2000 u** along spine centreline.
- Model rotation: crate/desk/console variants from `_BEACON_MODELS`.

### HUD + signpost text standard

- **In-world:** no arbitrary strings (engine limit) — colour + prop silhouette only.
- **Animation Lab UI / In-game guide panel:** `{COMPASS} → {Label} ({cardinal hint}, ~{distance} u)` — matches `hub_signpost_entries()` hint format.
- **Gate hints:** one sentence: direction + content type + count.

---

## 4. Technical architecture

### File ownership

| Module | Owns |
|--------|------|
| `anim_catalog.py` | Animation taxonomy, district grid, parade slots, hub signpost targets, room 2–13 mapping |
| `anim_parade.py` | Chr guards, ailists, pads 1–171, tour cycler |
| `anim_props.py` | All StdObjects: hub, catalog, true-scale, gates, beacons, signposts |
| `museum_layout.py` | Bbox packing, tag districts, s16 caps, `OBJECT_CATALOG_HUB_*` |
| `anim_levels.py` | Solo/MP/dev worlds, bridges, room 18, pads 931+ |
| `level_footprints.py` | Pad JSON → island half-extents |
| `anim_characters.py` | 24 mannequins, room 19, pads 907–930 |
| `anim_wayfinding.py` | Carpet routes, compass rose, gates, beacons, walk audits |
| `builders.py` | `floor_box_with_parade_zones()` — tile JSON, carve/restore collision |
| `journal/anim_lab/anim_lab.html` | Filter chips 1:1 with zones |

### Room allocation table (locked)

See **Current state → Room budget**. Changes require dropping a tag room or merging dev/solo into room 18 sub-carpets only (not recommended — prop limit).

### Prop budget per room

- Hard limit: **200** (`PARADE_PROP_MAX_PER_ROOM`) — stay ≤180 for headroom.
- Catalog tags already split 7 ways; largest tag misc **133** — safe.
- True-scale mega wing **189** props — verify `cdCollectGeoForCyl` if props cluster; may need sub-room split in future.

### Pad index ranges (stable)

| Block | Start | Count |
|-------|-------|-------|
| Spawn | 0 | 1 |
| Parade grid | 1 | `NUM_GRID_SLOTS` (170 today) |
| Tour | `PAD_SPECIAL_TOUR` | 1 |
| Props | `PARADE_PROPS_PAD_FIRST` | `len(all_parade_prop_specs())` |
| Characters | `_character_pad_first()` | 24 |
| Levels | `_level_pad_first()` | 91 |

### Floor layers

| Layer | Y | Purpose |
|-------|---|---------|
| Collision | **0** | Walkable; arena shell grey |
| Carpet | **4** | District colour; `floortype="carpet"` |
| Pads / props | **10** | Spawn and markers (`PAD_FLOOR_OFFSET`) |

---

## 5. Phased implementation roadmap

### Phase 0 — Stabilize (mostly **done**)

- [x] Spawn plaza ±500 u preserved (`spawn_plaza_bounds()`)
- [x] Walk collision restore (`_ensure_animlab_walk_collision_floors()`)
- [x] Megaworld carve + room 18 ownership
- [x] Sub-zone chr split (rooms 2–13)
- [x] `audit_spawn_walk_paths()` / validate hook
- [x] Align beacon threshold 3500 → 3000 u (cosmetic)
- [ ] Run full walk audit in CI on `build animlab`

### Phase 1 — Consolidate layout to plan (**this doc**)

- [x] Author master zone map (`docs/ANIMLAB_MASTER_PLAN.md`)
- [x] Fix stale docs in `CHARACTER_ANIMATIONS.md` (571 → 170/570 split)
- [x] Sync UI default hint compass labels (`anim_lab.html`)
- [x] Resolve NW dual-gate signpost (normal vs mega) — combined hub portal + NW-N/NW-W subTargets + wing gates
- [x] Populate cutscene district row — reserved marker + UI (392 CUT_* ROM, Phase 4 body rigs)
- [ ] Dedupe: confirm no third object wing; tag eld/lip when models exist + room reallocation

### Phase 2 — UI parity ✅

- [x] Parade tab district chips ↔ eight compass zones 1:1
- [x] Spatial map legend uses same colours/names as `hub_signpost_entries()`
- [x] In-game guide panel shows all 8 directions with counts matching live payload
- [x] Filter persistence: `?district=__tag_furniture` deep links

### Phase 3 — Stage warp portals (partial)

- [x] Per-island `--boot-stage <hex>` smoke test button in UI (`serve_animlab.py` API)
- [ ] `add_level_megaworld_pads` → boot-stage ailist or in-map hint pads
- [ ] Optional: NE dev archive collapses to UI-only list (no in-game islands)

### Phase 4 — Optional expansions

- **571 animation target:** cutscene district with non-guard body OR relaxed filter + `CHRANIMFLAG_LOCKPOS`
- Level geometry previews (seg snippets) — high cost; keep footprints default
- eld/lip tag districts — requires room budget expansion or tag merge

---

## 6. Success criteria

You know Anim Lab is organized when:

1. **Stand at spawn** — each of **8** compass directions has **one** obvious purpose and matching portal colour.
2. **Zero fall-through** — `audit_spawn_collision_floor()` reports 0 warnings on all spines.
3. **Full accounting** — **352/352** objects · **91/91** stages · **24/24** characters · animation grid matches declared filter (170 today; 571 when Phase 4 lands).
4. **UI = world** — Animation Lab Parade filter chips match in-game zone names, colours, and counts from layout payload API.
5. **Room budget** — no room exceeds chr/prop limits; validate passes with no layout warnings.
6. **No duplicate wings** — W catalog + NW true-scale + SW curated props are clearly labelled; no third 352-pack.

---

## Appendix — Coordinate quick reference

```
Spawn:           (0, -2200)
District grid:   origin (-2250, -900), cells 1500×1200
Props gallery:   (-2200, -3000)
Object catalog:  (-21000, -26500)
True-scale norm: (15000, -20000)
True-scale mega: (-29000, -29000)
Characters:      (5500, -4500)
Solo gate:       (-4200, -5200)
MP gate:         (9200, -2800)
Dev gate:        (5200, 3600)
```

Rebuild layout payload: `python3 journal/anim_lab/serve_animlab.py` → GET `/api/parade/layout` or `/api/catalog` → `paradeLayout`.
