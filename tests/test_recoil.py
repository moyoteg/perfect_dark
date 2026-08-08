import unittest
from recoil_pattern_controller import RecoilPatternController

class TestRecoilPatternController(unittest.TestCase):
    def setUp(self):
        self.controller = RecoilPatternController(base_vertical_recoil=2.0, base_horizontal_recoil=1.0, damping_rate=10.0)

    def test_fire_shot_and_recover(self):
        res1 = self.controller.fire_shot_impulse(shot_count_in_burst=1)
        self.assertEqual(res1["accumulated_recoil"]["v_deg"], 2.0)
        self.assertEqual(res1["accumulated_recoil"]["h_deg"], 1.0)

        # Update recovery over 0.5s
        res2 = self.controller.update_recoil_recovery(0.5)
        self.assertEqual(res2["v_deg"], 0.0) # Should damp to zero

if __name__ == "__main__":
    unittest.main()
