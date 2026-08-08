#!/usr/bin/env python3
"""
Game Mod Engine Swarm - Weapon Rate of Fire RPM & Shot Cooldown Delay Calculator
Production-Grade Python Feature Module
"""

import time

class WeaponFiringRateRpmCalculator:
    def __init__(self, tick_rate_hz=60.0):
        self.tick_rate = tick_rate_hz

    def calculate_cooldown_seconds_and_ticks(self, rounds_per_minute):
        """Calculates inter-shot delay seconds and frame tick count from RPM."""
        if rounds_per_minute <= 0.0:
            raise ValueError("rounds_per_minute must be strictly positive")

        seconds_per_shot = round(60.0 / float(rounds_per_minute), 4)
        ticks_per_shot = int(round(seconds_per_shot * self.tick_rate))
        if ticks_per_shot < 1:
            ticks_per_shot = 1

        actual_rpm = round((60.0 * self.tick_rate) / float(ticks_per_shot), 2)

        return {
            "requested_rpm": rounds_per_minute,
            "seconds_per_shot": seconds_per_shot,
            "ticks_per_shot": ticks_per_shot,
            "tick_rate_hz": self.tick_rate,
            "actual_quantized_rpm": actual_rpm,
            "calculated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
