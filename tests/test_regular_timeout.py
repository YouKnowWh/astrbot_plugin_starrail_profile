import asyncio
import importlib
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root.parent))
advisor = importlib.import_module(root.name + ".advisor")
regular = importlib.import_module(root.name + ".regular")


class RegularTimeoutTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.client = advisor.Advisor(self.temp.name)

    async def test_stalled_first_refresh_and_concurrent_lookup(self):
        entered = asyncio.Event()
        cancelled = asyncio.Event()

        async def stalled(old):
            entered.set()
            try:
                await asyncio.Future()
            finally:
                cancelled.set()

        with (
            patch.object(regular, "refresh", stalled),
            patch.object(regular, "REFRESH_SECONDS", 0.4),
        ):
            first = asyncio.create_task(self.client.regular("希儿", 6))
            await asyncio.wait_for(entered.wait(), 1)
            second = await asyncio.wait_for(self.client.regular("于夜色中"), 0.2)
            self.assertIn("S1", second["叠影效果"])
            self.assertEqual(second["资料状态"], "更新中，使用随包资料")
            result = await asyncio.wait_for(first, 1)
            self.assertTrue(cancelled.is_set())
            self.assertEqual(result["资料状态"], "刷新失败，使用随包资料")
            self.assertIsNone(result["上次核对"])
            self.assertEqual(result["名称"], "希儿")
            self.assertTrue((await self.client.regular("希儿"))["刷新失败沿用缓存"])

    async def test_legacy_expired_snapshot_survives_external_cancellation(self):
        saved = regular.bundled()
        at = int(time.time()) - 86400
        with self.client.snapshots.connect() as db:
            db.execute(
                "INSERT INTO snapshots VALUES (?, ?, ?)",
                ("regular", at, json.dumps(saved)),
            )
        entered = asyncio.Event()

        async def stalled(old):
            entered.set()
            await asyncio.Future()

        with patch.object(regular, "refresh", stalled):
            task = asyncio.create_task(self.client.regular("希儿"))
            await asyncio.wait_for(entered.wait(), 1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        with patch.object(regular, "refresh", side_effect=OSError("offline")):
            result = await self.client.regular("希儿")
        self.assertEqual(result["资料状态"], "刷新失败，使用本地缓存")
        self.assertEqual(result["上次核对"], advisor.checked_at(at))
        with patch.object(regular, "refresh", return_value=saved):
            restored = advisor.Advisor(self.temp.name)
            result = await restored.regular("希儿")
            self.assertFalse(result["刷新失败沿用缓存"])
        with patch.object(
            regular,
            "refresh",
            side_effect=AssertionError("fresh cache made a network request"),
        ):
            await advisor.Advisor(self.temp.name).regular("希儿")

    async def test_new_revision_requires_all_tables_before_publishing(self):
        old = regular.bundled()
        meta = {
            "sha": "a" * 40,
            "commit": {"committer": {"date": "2026-11-20T00:00:00Z"}},
        }

        async def tables(session, url):
            if "/commits/" in url:
                return meta
            self.assertIn(meta["sha"], url)
            return old[Path(url).stem]

        with patch.object(regular, "fetch_json", tables):
            fresh = await regular.refresh(old)
        self.assertEqual(fresh["sha"], meta["sha"])
        self.assertEqual(regular.lookup(fresh, "希儿")["名称"], "希儿")

        cancelled = asyncio.Event()

        async def partial(session, url):
            if "/commits/" in url:
                return meta
            if url.endswith("/nickname.json"):
                raise OSError("missing table")
            try:
                await asyncio.Future()
            finally:
                cancelled.set()

        with patch.object(regular, "fetch_json", partial):
            result = await self.client.regular("希儿")
        self.assertTrue(cancelled.is_set())
        self.assertIn(old["sha"], result["来源"])
        self.assertTrue(result["刷新失败沿用缓存"])
