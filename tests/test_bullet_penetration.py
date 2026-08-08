import unittest
from bullet_penetration_decal_engine import BulletPenetrationDecalEngine

class TestBulletPenetrationDecalEngine(unittest.TestCase):
    def setUp(self):
        self.engine = BulletPenetrationDecalEngine(caliber_power_factor=1.5) # Heavy caliber

    def test_impact_wood(self):
        res = self.engine.evaluate_bullet_impact("WOOD", thickness_mm=20, entry_point_xyz=(10, 5, 0))
        self.assertTrue(res["did_penetrate"]) # 30mm * 1.5 = 45mm capacity >= 20mm
        self.assertEqual(res["entry_decal_texture"], "DECAL_WOOD_SPLINTER")

if __name__ == "__main__":
    unittest.main()
