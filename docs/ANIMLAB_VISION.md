# Anim Lab — Vision

**Requirements, acceptance, and canonical counts:** [`ANIMLAB_SPEC.md`](ANIMLAB_SPEC.md) — SDD contract (FR/NFR/AC). This document is intent only; do not cite it for baselines.

**North star:** one walkable museum world where every compass direction answers exactly one question about Perfect Dark — animations, objects, levels, and characters — without leaving STAGE_ANIMLAB.

Layout tables and coordinates: [`ANIMLAB_MASTER_PLAN.md`](ANIMLAB_MASTER_PLAN.md). Build commands: [`CHARACTER_ANIMATIONS.md`](CHARACTER_ANIMATIONS.md).

---

## Mission

Anim Lab exists so you can **study, browse, and cross-reference** the game's content in spatial context:

| Need | Where in-world |
|------|----------------|
| How does this anim look on a guard? | **N** — animation districts |
| What props sit near social/combat loops? | **SW** — curated props gallery |
| What StdObjects exist, by tag? | **W** — object catalog (showcase scale) |
| How big is this model really? | **NW** — true-scale yard (normal + mega) |
| Who is on the roster? | **SE** — character mannequins |
| Which solo / MP / dev stages exist? | **WSW / E / NE** — level footprint islands |

One spawn hub. Eight compass purposes. UI parity with in-game carpets, signposts, and counts.

---

## Mental model

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

                                    [NE] Dev annex (40)
```

**Hub → portal → gate → grid**

1. **Hub** — spawn pad 0 at `(0, -2200)`; ±500 u plaza never carved; compass rose + eight portal arches at **800 u**.
2. **Portal** — coloured carpet spine leaves the ring toward each wing (immutable palette in master plan).
3. **Gate** — wing gate prop + distance beacons on routes >3500 u (every 2000 u).
4. **Grid** — content: guard loops, StdObjects, mannequins, or level marker footprints.

Full-tour cycler pad **171** sits east of spawn (gold carpet) — cycles all guard-playable clips in one chr.

---

## What you CAN do today

- **Walk** every wing from spawn without falling through (collision restore on room-1 spines).
- **Watch** 170 guard-playable animation loops in 9 districts (+ full-tour cycler).
- **Inspect** 352 showcase-scaled objects in 7 tag districts (**W**) and the same 352 at true scale (**NW** — 163 normal + 189 mega).
- **Browse** 8 curated hub props + 16 district vignettes (**SW**).
- **Meet** 24 character mannequins on distinct rigs (**SE**).
- **Index** all 91 retail/dev stages as coloured footprint islands (**WSW** 25 · **E** 26 · **NE** 40).
- **Filter** the Parade tab by compass zone (matches signposts 1:1) and boot any stage from the UI (`--boot-stage 0xNN`).
- **Study** the full ROM catalog, interaction registry, and spatial map in `anim_lab.html` / **PD Anim Lab.app**.

## Honest limits

| Limit | Why |
|-------|-----|
| **170 / 570** guard-playable anims | 392 CUT_* ROM clips excluded (cinematic flags, Skedar/bike rigs). Cutscene district reserved; Phase 4 needs alternate bodies. |
| **Level islands = markers only** | No embedded bg geometry in one background — footprints + console prop + UI boot. In-map stage warp is Phase 3+. |
| **392 CUT_* clips** | Layout row reserved; 0 playable slots until mission chr rigs land. |
| **Room budget full** (24/24) | No spare room for eld/lip tag districts without reallocation. |
| **Dual NW gates** | Hub portal covers both yards; NW-N / NW-W sub-targets disambiguate normal vs mega. |

---

## Navigation contract

### Eight compass zones

| Compass | Label | Carpet | Content |
|---------|-------|--------|---------|
| **N** | Animation districts | `#a78bfa` | 170 guard loops, 12 sub-zones |
| **SW** | Props gallery | `#38bdf8` | 8 hub props + vignettes |
| **W** | Object catalog | `#0ea5e9` | 352 models, 7 tags |
| **WSW** | Solo world | `#f59e0b` | 25 campaign stages |
| **E** | MP world | `#dc2626` | 26 MP / combat maps |
| **NE** | Dev annex | `#64748b` | 40 dev/test stages |
| **NW** | True scale | `#14b8a6` / `#0d9488` | 352 @ bbox (163 + 189 mega) |
| **SE** | Character gallery | `#c084fc` | 24 mannequins |

Signpost text pattern: `{COMPASS} → {Label} ({cardinal hint}, ~{distance} u)` — mirrored in Animation Lab **In-game guide** panel and Parade compass chips.

### UI parity rules

- Parade tab **compass chips** = `hub_signpost_entries()` (names, colours, counts).
- Spatial map **legend** uses the same palette and labels.
- Animation **district** chips appear only when **N** is selected (sub-zones within the north wing).
- Object **tag** chips appear when **W** is selected.

---

## Content accounting

| Content class | Live / Target | Notes |
|---------------|---------------|-------|
| Guard-playable animations | **170 / 570** | 570 named in ROM; 571 target = full grid + tour or Phase 4 expansion |
| StdObjects (showcase **W**) | **352 / 352** | 7 active tag districts |
| StdObjects (true-scale **NW**) | **352 / 352** | 163 normal wing + 189 mega yard |
| Level stages (all worlds) | **91 / 91** | 25 solo · 26 MP · 40 dev — marker islands |
| Character mannequins | **24 / 24** | Story + MP roster bodies |
| Hub props + vignettes | **8 + 16** | SW wing — not a second catalog |
| Cutscene district | **0 / 392** | Reserved grid; ROM clips catalogued, not playable |

---

## Roadmap (Phase 0–4)

### Phase 0 — Stabilize ✅ (mostly done)

- [x] Spawn plaza ±500 u preserved
- [x] Walk collision restore (`_ensure_animlab_walk_collision_floors`)
- [x] Megaworld carve + room 18 ownership
- [x] Sub-zone chr split (rooms 2–13)
- [x] Walk / collision audit hooks
- [ ] Full walk audit in CI on `build animlab`

### Phase 1 — Consolidate layout ✅ (mostly done)

- [x] Master zone map (`ANIMLAB_MASTER_PLAN.md`)
- [x] Docs aligned (170/570 split in `CHARACTER_ANIMATIONS.md`)
- [x] UI compass hint labels synced
- [x] NW dual-gate signpost (NW-N / NW-W sub-targets)
- [x] Cutscene district reserved + UI note
- [ ] Confirm no third object wing; eld/lip tags when models + rooms exist

### Phase 2 — UI parity ✅ (this slice)

- [x] Parade compass chips ↔ eight hub signposts 1:1
- [x] Spatial map legend = signpost names/colours
- [x] In-game guide: all 8 directions + live counts
- [x] Filter deep links (`?compass=N`, `?district=__tag_furniture`)

### Phase 3 — Stage warp (partial)

- [x] UI **Boot stage** button per level island (`--boot-stage 0xNN` via serve_animlab API)
- [ ] In-map warp pads / ailist triggers from islands
- [ ] Optional: NE dev annex UI-only collapse (no in-game islands)

### Phase 4 — Optional expansions

- [ ] **571 animation target** — cutscene district with mission bodies or relaxed filter
- [ ] Level geometry previews (seg snippets) — high cost; footprints stay default
- [ ] eld/lip tag districts — room budget expansion

---

## Success picture

> **Stand at spawn. Walk any direction. Find content. Don't die.**

You know Anim Lab is working when:

1. Each of **8** compass directions has **one** obvious purpose and matching portal colour.
2. **Zero fall-through** — collision audit reports 0 warnings on all spines.
3. **Full accounting** — 352/352 objects · 91/91 stages · 24/24 characters · animation grid matches declared filter.
4. **UI = world** — Parade filters match zone names, colours, and counts from the layout API.
5. **No duplicate wings** — W catalog + NW true-scale + SW curated props are clearly labelled.

---

## Quick start

```bash
# Build + deploy megaworld
python3 tools/pdmap.py build animlab --seg --deploy --mod mod_allinone

# Play in-world
./build/pd.arm64 --test-animlab --moddir mods/mod_allinone --solo

# Animation Lab UI
python3 journal/anim_lab/serve_animlab.py
# or: ./scripts/build-anim-lab-electron.sh && open "PD Anim Lab.app"
```

Spawn: `(0, -2200)` · Portal ring: **800 u** · Arena: **±32000 u**
