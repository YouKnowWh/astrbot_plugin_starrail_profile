import importlib
import sys
import unittest
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root.parent))
showcase = importlib.import_module(root.name + ".showcase")


class ShowcaseTests(unittest.TestCase):
    def test_character_with_partial_gear_preserves_real_rolls_and_empty_slots(self):
        raw = {
            "id": "42",
            "rank": 0,
            "level": 70,
            "statistics": [{"field": "spd", "display": "138"}],
            "light_cone": {"id": "9", "rank": 2, "level": 60},
            "relics": [
                {
                    "name": "测试遗器",
                    "level": 0,
                    "main_affix": {"name": "攻击力", "display": "5%"},
                    "sub_affix": [{"name": "速度", "display": "2"}],
                }
            ],
        }
        snapshot = showcase.describe_showcase(
            {"player": {"uid": 123}, "characters": [raw, {"id": "43"}]}, "123"
        )
        first, second = snapshot["角色"]
        self.assertEqual(first["面板合计"], {"spd": "138"})
        self.assertEqual(first["装备光锥"]["叠影"], 2)
        self.assertEqual(first["装备遗器"][0]["副词条"], ["速度 2"])
        self.assertEqual(first["装备遗器"][0]["主词条"], "攻击力 5%")
        self.assertEqual(first["星魂"], 0)
        self.assertIsNone(second["装备光锥"])
        self.assertEqual(second["装备遗器"], [])

    def test_rejects_wrong_uid_and_empty_showcase(self):
        with self.assertRaisesRegex(ValueError, "账户"):
            showcase.describe_showcase(
                {"player": {"uid": "1"}, "characters": [{"id": "42"}]}, "2"
            )
        with self.assertRaisesRegex(ValueError, "公开展示"):
            showcase.describe_showcase({"player": {"uid": "1"}, "characters": []}, "1")
