import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root.parent))
advisor = importlib.import_module(root.name + ".advisor")
regular = importlib.import_module(root.name + ".regular")


class CatalogIndexTests(unittest.IsolatedAsyncioTestCase):
    async def test_new_catalog_replaces_index_and_preserves_shared_aliases(self):
        old = regular.bundled()
        chars = dict(old["nickname"]["characters"])
        for i in ("1102", "1005"):
            chars[i] = [*chars.get(i, []), "测试同名", "测试同名"]
        new = {**old, "nickname": {**old["nickname"], "characters": chars}}
        with tempfile.TemporaryDirectory() as path:
            client = advisor.Advisor(path)
            client.catalog.read = AsyncMock(
                side_effect=[(d, None, "测试", False) for d in (old, new, new)]
            )
            self.assertIn("结果", await client.regular("测试同名"))
            candidates = (await client.regular("测试同名"))["请确认条目"]
            self.assertEqual(len(candidates), 2)
            self.assertEqual((await client.regular("测试同"))["请确认条目"], candidates)
