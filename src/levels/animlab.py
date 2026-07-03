"""Animation parade test map — registered stage ``STAGE_ANIMLAB`` (0x82)."""

from tools.pdmap.anim_catalog import (
    parade_arena_half,
    parade_district_markers,
    parade_slot_markers,
    parade_special_marker,
    parade_zone_half,
    parade_zone_markers,
)
from tools.pdmap.anim_characters import character_gallery_layout_payload
from tools.pdmap.anim_levels import level_megaworld_layout_payload
from tools.pdmap.anim_props import (
    parade_museum_layout_payload,
    parade_props_layout_payload,
    parade_true_scale_layout_payload,
    parade_vignette_layout_payload,
)
from tools.pdmap.builders import configure_animation_lab, floor_box_with_parade_zones

BOX_HALF = parade_arena_half()
BOX_HEIGHT = 3000.0
# District-level seg markers (~12 quads) — safe for bgInflate; per-slot parade
# mode (~570 quads) crashes during load.
SEG_MODE = "parade_districts"


def build():
    return configure_animation_lab(half=BOX_HALF)


def build_tiles_json():
    slots = parade_slot_markers() + [parade_special_marker()]
    layout = parade_props_layout_payload()
    museum = parade_museum_layout_payload()
    true_scale = parade_true_scale_layout_payload()
    characters = character_gallery_layout_payload()
    levels = level_megaworld_layout_payload()
    vignettes = parade_vignette_layout_payload()
    return floor_box_with_parade_zones(
        "animlab",
        half=BOX_HALF,
        y=0.0,
        slots=slots,
        zones=parade_zone_markers(),
        districts=parade_district_markers(),
        props_district=layout,
        museum_district=museum,
        true_scale_district=true_scale,
        characters_district=characters,
        levels_district=levels,
        vignette_props=vignettes,
        zone_half=parade_zone_half(),
    )
