import unittest
from weapon_reload_animation_timer import WeaponReloadAnimationTimer

class TestWeaponReloadAnimationTimer(unittest.TestCase):
    def setUp(self):
        self.timer = WeaponReloadAnimationTimer(reload_duration_seconds=2.0)

    def test_reload_stages(self):
        # 0.4s -> EJECT
        res1 = self.timer.evaluate_reload_progress(0.4)
        self.assertEqual(res1["current_stage"], "MAGAZINE_EJECT")
        self.assertFalse(res1["is_complete"])

        # 1.0s -> INSERT
        res2 = self.timer.evaluate_reload_progress(1.0)
        self.assertEqual(res2["current_stage"], "MAGAZINE_INSERT")

        # 2.0s -> READY
        res3 = self.timer.evaluate_reload_progress(2.0)
        self.assertEqual(res3["current_stage"], "READY")
        self.assertTrue(res3["is_complete"])

if __name__ == "__main__":
    unittest.main()
