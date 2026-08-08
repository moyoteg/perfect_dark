import unittest
from stealth_detection_meter_calculator import StealthDetectionMeterCalculator

class TestStealthDetectionMeterCalculator(unittest.TestCase):
    def setUp(self):
        self.calc = StealthDetectionMeterCalculator(vision_angle_deg=90.0, max_vision_dist=20.0, noise_radius=10.0)

    def test_visual_detection(self):
        # Guard at (0,0,0) facing 0 deg (East), Player at (10,0,0) -> directly in front
        res = self.calc.evaluate_guard_detection((0, 0, 0), 0.0, (10, 0, 0), 0.0)
        self.assertGreater(res["detection_increase_rate"], 0.0)
        self.assertIn("IN_VISUAL_FIELD", res["reasons"])

    def test_behind_guard_quiet(self):
        # Player at (-10,0,0) -> behind guard facing East
        res = self.calc.evaluate_guard_detection((0, 0, 0), 0.0, (-10, 0, 0), 0.0)
        self.assertEqual(res["detection_increase_rate"], 0.0)

if __name__ == "__main__":
    unittest.main()
