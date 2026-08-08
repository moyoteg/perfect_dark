#!/usr/bin/env python3
"""
Perfect Dark Swarm - Guard Vision Cone & Auditory Stealth Detection Meter Calculator
Production-Grade Python Feature Module
"""

import math
import time

class StealthDetectionMeterCalculator:
    def __init__(self, vision_angle_deg=90.0, max_vision_dist=20.0, noise_radius=10.0):
        self.vision_angle = math.radians(vision_angle_deg)
        self.max_dist = max_vision_dist
        self.noise_radius = noise_radius

    def evaluate_guard_detection(self, guard_pos_xyz, guard_facing_deg, player_pos_xyz, player_noise_level):
        """Evaluates guard visual cone and auditory detection meter increase rate."""
        gx, gy, gz = guard_pos_xyz
        px, py, pz = player_pos_xyz

        dist = math.sqrt((px - gx)**2 + (py - gy)**2 + (pz - gz)**2)
        if dist == 0:
            return {"detection_rate": 1.0, "reason": "COLLISION_IMMEDIATE_SPOT"}

        detection_rate = 0.0
        reasons = []

        # 1. Visual Detection Cone Evaluation
        if dist <= self.max_dist:
            dx = px - gx
            dz = pz - gz
            angle_to_player = math.atan2(dz, dx)
            guard_facing_rad = math.radians(guard_facing_deg)

            angle_diff = abs(angle_to_player - guard_facing_rad)
            angle_diff = (angle_diff + math.pi) % (2 * math.pi) - math.pi

            if abs(angle_diff) <= (self.vision_angle / 2.0):
                # Visual detection rate scales inversely with distance
                vis_rate = (1.0 - (dist / self.max_dist)) * 0.8
                detection_rate += vis_rate
                reasons.append("IN_VISUAL_FIELD")

        # 2. Auditory Footstep / Gunfire Noise Evaluation
        if player_noise_level > 0 and dist <= self.noise_radius:
            noise_rate = (player_noise_level / 100.0) * (1.0 - (dist / self.noise_radius)) * 0.6
            detection_rate += noise_rate
            reasons.append("AUDIBLE_NOISE_EMITTED")

        return {
            "detection_increase_rate": round(min(1.0, detection_rate), 4),
            "distance_m": round(dist, 2),
            "reasons": reasons,
            "evaluated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
