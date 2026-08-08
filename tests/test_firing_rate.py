import unittest
from weapon_firing_rate_rpm_calculator import WeaponFiringRateRpmCalculator

class TestWeaponFiringRateRpmCalculator(unittest.TestCase):
    def setUp(self):
        self.calculator = WeaponFiringRateRpmCalculator(tick_rate_hz=60.0)

    def test_600_rpm(self):
        res = self.calculator.calculate_cooldown_seconds_and_ticks(600.0)

        self.assertEqual(res["seconds_per_shot"], 0.1)
        self.assertEqual(res["ticks_per_shot"], 6)
        self.assertEqual(res["actual_quantized_rpm"], 600.0)

    def test_1200_rpm(self):
        res = self.calculator.calculate_cooldown_seconds_and_ticks(1200.0)

        self.assertEqual(res["seconds_per_shot"], 0.05)
        self.assertEqual(res["ticks_per_shot"], 3)
        self.assertEqual(res["actual_quantized_rpm"], 1200.0)

if __name__ == "__main__":
    unittest.main()
