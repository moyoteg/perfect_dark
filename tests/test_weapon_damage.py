import unittest
from weapon_damage_calculator import WeaponDamageCalculator

class TestWeaponDamageCalculator(unittest.TestCase):
    def setUp(self):
        self.calc = WeaponDamageCalculator()

    def test_falcon2_headshot(self):
        res = self.calc.calculate_hit_damage("FALCON2", body_part="HEAD", target_armor=0)
        self.assertEqual(res["raw_damage"], 62.5)
        self.assertEqual(res["net_damage"], 62.5)

    def test_super_dragon_armored_torso(self):
        res = self.calc.calculate_hit_damage("SUPER_DRAGON", body_part="TORSO", target_armor=100)
        self.assertEqual(res["effective_armor"], 20.0)
        self.assertEqual(res["net_damage"], 35.0)

if __name__ == "__main__":
    unittest.main()
