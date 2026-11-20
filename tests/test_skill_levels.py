import importlib
import sys
import unittest
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root.parent))
regular = importlib.import_module(root.name + ".regular")


class SkillLevels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = regular.bundled()

    def rows(self, text, level=0, skill="战技"):
        result = regular.lookup(self.data, "希儿", level, skill, text)
        return [r for r in result["技能"] if not r["强化形态"]]

    def test_wrong_default_or_argument(self):
        for level in [0, 10]:
            (row,) = self.rows("希儿未强化，战技6级", level)
            self.assertEqual(row["等级"], 6)
            self.assertIn("165%", row["效果"])

    def test_distinct_levels(self):
        self.assertEqual([r["等级"] for r in self.rows("战技6级和10级")], [6, 10])
        self.assertEqual(self.rows("80级希儿，6级战技，终结技10级")[0]["等级"], 6)
        self.assertEqual(self.rows("80级希儿")[0]["等级依据"], "默认参考等级")
        self.assertNotIn("效果", self.rows("战技16级")[0])

    def test_teammate_level_does_not_override_tool_argument(self):
        self.assertEqual(self.rows("布洛妮娅战技6级，希儿呢？", 10)[0]["等级"], 10)
