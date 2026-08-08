#!/usr/bin/env python3
"""
Perfect Dark AIO Mod - Weapon Damage & Armor Penetration Engine
Production-Grade Python Feature Module
"""

import time

class WeaponDamageCalculator:
    def __init__(self):
        self.weapons = {
            "FALCON2": {"base_damage": 25.0, "armor_penetration": 0.30, "headshot_multiplier": 2.5},
            "CMP150": {"base_damage": 18.0, "armor_penetration": 0.40, "headshot_multiplier": 2.0},
            "AR31": {"base_damage": 32.0, "armor_penetration": 0.65, "headshot_multiplier": 3.0},
            "SUPER_DRAGON": {"base_damage": 45.0, "armor_penetration": 0.80, "headshot_multiplier": 3.5},
            "FAR_SIGHT": {"base_damage": 100.0, "armor_penetration": 1.00, "headshot_multiplier": 5.0}
        }

    def calculate_hit_damage(self, weapon_name, body_part="TORSO", target_armor=50.0):
        """Computes net damage dealt to target HP considering body part multipliers and armor reduction."""
        weapon = self.weapons.get(weapon_name.upper())
        if not weapon:
            raise KeyError(f"Unknown weapon name: {weapon_name}")

        base = weapon["base_damage"]
        headshot_mult = weapon["headshot_multiplier"]
        pen = weapon["armor_penetration"]

        # Body part damage scaling
        if body_part == "HEAD":
            damage = base * headshot_mult
        elif body_part == "LIMBS":
            damage = base * 0.75
        else: # TORSO
            damage = base

        # Armor mitigation calculation
        effective_armor = max(0.0, target_armor * (1.0 - pen))
        net_damage = max(1.0, damage - (effective_armor * 0.5))

        return {
            "weapon_name": weapon_name.upper(),
            "body_part": body_part,
            "raw_damage": round(damage, 2),
            "effective_armor": round(effective_armor, 2),
            "net_damage": round(net_damage, 2),
            "calculated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
