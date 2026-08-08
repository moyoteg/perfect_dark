#!/usr/bin/env python3
"""
Perfect Dark Game Mod Swarm - Weapon Reload Animation Stage & Progress Timer
Production-Grade Python Feature Module
"""

import time

class WeaponReloadAnimationTimer:
    RELOAD_STAGES = ["MAGAZINE_EJECT", "MAGAZINE_INSERT", "SLIDE_PULL", "READY"]

    def __init__(self, reload_duration_seconds=2.5):
        if reload_duration_seconds <= 0:
            raise ValueError("reload_duration_seconds must be positive")
        self.total_duration = reload_duration_seconds

    def evaluate_reload_progress(self, elapsed_seconds):
        """Determines active reload animation stage and progress percentage (0.0 - 100.0)."""
        elapsed = max(0.0, float(elapsed_seconds))
        progress_ratio = min(1.0, elapsed / self.total_duration)
        progress_pct = round(progress_ratio * 100.0, 2)

        if progress_ratio < 0.3:
            stage = "MAGAZINE_EJECT"
        elif progress_ratio < 0.7:
            stage = "MAGAZINE_INSERT"
        elif progress_ratio < 1.0:
            stage = "SLIDE_PULL"
        else:
            stage = "READY"

        is_complete = (stage == "READY")

        return {
            "elapsed_seconds": elapsed,
            "total_duration_seconds": self.total_duration,
            "progress_percentage": progress_pct,
            "current_stage": stage,
            "is_complete": is_complete,
            "evaluated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
