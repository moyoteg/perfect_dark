#!/usr/bin/env python3
"""
Game Mod Engine Swarm - Weapon Bullet Penetration Material Hardness & Decal Spawn Engine
Production-Grade Python Feature Module
"""

import time

MATERIAL_HARDNESS_TABLE = {
    "GLASS": {"hardness": 1, "max_pen_depth_mm": 50, "decal": "DECAL_GLASS_CRACK"},
    "WOOD": {"hardness": 3, "max_pen_depth_mm": 30, "decal": "DECAL_WOOD_SPLINTER"},
    "CONCRETE": {"hardness": 7, "max_pen_depth_mm": 10, "decal": "DECAL_CONCRETE_CHIP"},
    "STEEL": {"hardness": 9, "max_pen_depth_mm": 5, "decal": "DECAL_METAL_SPARK"}
}

class BulletPenetrationDecalEngine:
    def __init__(self, caliber_power_factor=1.0):
        self.power = caliber_power_factor

    def evaluate_bullet_impact(self, material_type, thickness_mm, entry_point_xyz):
        """Evaluates whether bullet penetrates material wall and determines decal type."""
        if material_type not in MATERIAL_HARDNESS_TABLE:
            material_info = {"hardness": 5, "max_pen_depth_mm": 15, "decal": "DECAL_GENERIC"}
        else:
            material_info = MATERIAL_HARDNESS_TABLE[material_type]

        effective_pen_depth = material_info["max_pen_depth_mm"] * self.power
        did_penetrate = thickness_mm <= effective_pen_depth

        return {
            "material_type": material_type,
            "thickness_mm": thickness_mm,
            "effective_penetration_capacity_mm": round(effective_pen_depth, 1),
            "did_penetrate": did_penetrate,
            "entry_decal_texture": material_info["decal"],
            "exit_decal_texture": material_info["decal"] if did_penetrate else None,
            "entry_point": entry_point_xyz,
            "evaluated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
