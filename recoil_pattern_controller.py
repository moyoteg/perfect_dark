#!/usr/bin/env python3
"""
Perfect Dark Jonaeru AIO Swarm - Dynamic Weapon Recoil Impulse & Camera Shake Controller
Production-Grade Python Feature Module
"""

import math
import time

class RecoilPatternController:
    def __init__(self, base_vertical_recoil=2.5, base_horizontal_recoil=0.8, damping_rate=5.0):
        self.base_v = base_vertical_recoil
        self.base_h = base_horizontal_recoil
        self.damping = damping_rate
        self.current_v_offset = 0.0
        self.current_h_offset = 0.0

    def fire_shot_impulse(self, shot_count_in_burst=1):
        """Applies recoil impulse scaled by continuous burst fire shot count."""
        # Scale recoil exponentially for long burst fire
        scaling = 1.0 + (math.log(max(1, shot_count_in_burst)) * 0.4)
        
        v_impulse = self.base_v * scaling
        # Alternate horizontal kick direction based on shot index parity
        h_direction = 1.0 if shot_count_in_burst % 2 == 1 else -1.0
        h_impulse = self.base_h * scaling * h_direction

        self.current_v_offset += v_impulse
        self.current_h_offset += h_impulse

        return {
            "shot_index": shot_count_in_burst,
            "impulse_applied": {"v_deg": round(v_impulse, 2), "h_deg": round(h_impulse, 2)},
            "accumulated_recoil": {"v_deg": round(self.current_v_offset, 2), "h_deg": round(self.current_h_offset, 2)}
        }

    def update_recoil_recovery(self, delta_time_sec):
        """Damps accumulated camera recoil back to zero pitch and yaw center."""
        if delta_time_sec <= 0:
            return {"v_deg": round(self.current_v_offset, 2), "h_deg": round(self.current_h_offset, 2)}

        recovery_factor = math.exp(-self.damping * delta_time_sec)
        self.current_v_offset *= recovery_factor
        self.current_h_offset *= recovery_factor

        if abs(self.current_v_offset) < 0.02:
            self.current_v_offset = 0.0
        if abs(self.current_h_offset) < 0.02:
            self.current_h_offset = 0.0

        return {
            "v_deg": round(self.current_v_offset, 2),
            "h_deg": round(self.current_h_offset, 2),
            "recovered_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
