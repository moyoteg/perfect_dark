#!/usr/bin/env python3
"""
FPS Weapon Mechanics Swarm - Weapon Barrel Overheat Accumulation & Dissipation Calculator
Production-Grade Python Feature Module
"""

import time

class WeaponHeatDissipationCalculator:
    def __init__(self, heat_per_shot=15.0, dissipation_rate_per_sec=25.0, overheat_threshold=100.0):
        self.heat_per_shot = heat_per_shot
        self.dissipation_rate = dissipation_rate_per_sec
        self.max_heat = overheat_threshold

    def update_weapon_heat_state(self, current_heat, shots_fired, elapsed_seconds):
        """Calculates net heat accumulation and passive cooling over time delta."""
        if current_heat < 0:
            raise ValueError("current_heat cannot be negative")
        if shots_fired < 0:
            raise ValueError("shots_fired cannot be negative")
        if elapsed_seconds < 0:
            raise ValueError("elapsed_seconds cannot be negative")

        added_heat = shots_fired * self.heat_per_shot
        dissipated_heat = elapsed_seconds * self.dissipation_rate

        net_heat = max(0.0, current_heat + added_heat - dissipated_heat)
        is_overheated = net_heat >= self.max_heat

        return {
            "initial_heat": current_heat,
            "shots_fired": shots_fired,
            "elapsed_seconds": elapsed_seconds,
            "added_heat": added_heat,
            "dissipated_heat": round(dissipated_heat, 2),
            "current_heat": round(net_heat, 2),
            "max_heat": self.max_heat,
            "is_overheated": is_overheated,
            "heat_percentage": round(min(100.0, (net_heat / self.max_heat) * 100.0), 1),
            "updated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
