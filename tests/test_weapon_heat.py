import unittest
from weapon_heat_dissipation_calculator import WeaponHeatDissipationCalculator

class TestWeaponHeatDissipationCalculator(unittest.TestCase):
    def setUp(self):
        self.calc = WeaponHeatDissipationCalculator(heat_per_shot=20.0, dissipation_rate_per_sec=10.0, overheat_threshold=100.0)

    def test_overheat_trigger(self):
        res = self.calc.update_weapon_heat_state(0.0, 5, 0.0) # 5 shots * 20 = 100 heat
        self.assertTrue(res["is_overheated"])
        self.assertEqual(res["heat_percentage"], 100.0)

    def test_heat_dissipation(self):
        res = self.calc.update_weapon_heat_state(50.0, 0, 2.0) # 50 heat - 20 dissipated = 30
        self.assertFalse(res["is_overheated"])
        self.assertEqual(res["current_heat"], 30.0)

if __name__ == "__main__":
    unittest.main()
