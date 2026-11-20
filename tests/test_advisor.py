import asyncio
import importlib
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root.parent))
cache = importlib.import_module(root.name + ".cache")
regular = importlib.import_module(root.name + ".regular")
currency = importlib.import_module(root.name + ".currency")


class RefreshTests(unittest.TestCase):
    def test_expires_atomically_and_survives_failure_and_restart(self):
        with (
            tempfile.TemporaryDirectory() as path,
            patch.object(cache.time, "time") as clock,
        ):
            snapshots = cache.Snapshots(path)
            clock.return_value = 100
            read = lambda fetch: snapshots.read("test", 10, fetch)
            self.assertEqual(read(lambda _: "old"), ("old", 100, False))
            clock.return_value = 105
            self.assertEqual(read(None), ("old", 100, False))
            clock.return_value = 111

            def offline(_):
                raise OSError("offline")

            self.assertEqual(read(offline), ("old", 100, True))
            clock.return_value = 172
            self.assertEqual(
                read(lambda old: old + " updated"), ("old updated", 172, False)
            )
            self.assertEqual(
                cache.Snapshots(path).read("test", 10, None),
                ("old updated", 172, False),
            )

    def test_concurrent_first_queries_share_fetch(self):
        calls = []
        with tempfile.TemporaryDirectory() as path:
            store = cache.Snapshots(path)

            def load(_):
                calls.append(1)
                return "one"

            with ThreadPoolExecutor(6) as pool:
                results = list(
                    pool.map(lambda _: store.read("test", 60, load)[0], range(8))
                )
            self.assertEqual(results, ["one"] * 8)
            self.assertEqual(calls, [1])

    def test_first_failure_then_recovery(self):
        with (
            tempfile.TemporaryDirectory() as path,
            patch.object(cache.time, "time") as clock,
        ):
            store = cache.Snapshots(path)
            clock.return_value = 100
            with self.assertRaises(ValueError):
                store.read("test", 60, lambda _: 1 / 0)
            clock.return_value = 161
            self.assertEqual(store.read("test", 60, lambda _: 5), (5, 161, False))

    def test_transient_request_retried(self):
        with patch.object(
            cache, "urlopen", side_effect=[TimeoutError(), BytesIO(b'{"ok":true}')]
        ) as request:
            self.assertEqual(
                cache.request_json("https://example.com/test"), {"ok": True}
            )
            self.assertEqual(request.call_count, 2)

    def test_cached_lineup_link_uses_current_event_page(self):
        lineup = "6ae2e8a44dedc0ec578a8fbe"
        expected = (
            "https://act.miyoushe.com/sr/event/currency-wars/index.html#/lineup/"
            + lineup
        )
        plan = {"来源": currency.LEGACY_GUIDE + lineup, "标题": "攻略"}
        fixed = currency.current_source(plan)
        self.assertEqual(fixed, {"来源": expected, "标题": "攻略"})
        self.assertEqual(currency.current_source(fixed), fixed)

    def test_revision_reused(self):
        old = {"sha": "a" * 40}
        with patch.object(regular, "fetch_json", return_value=old) as request:
            self.assertIs(asyncio.run(regular.refresh(old)), old)
            request.assert_called_once()

    def test_multiplier_units(self):
        self.assertEqual(
            regular.describe("#1[i]% / #2[i]回合", [0.125, 2]), "12.5% / 2回合"
        )

    def test_excludes_outdated_community_guides(self):
        data = {"version": "4.7", "season": "2", "sub": "1"}
        stale = {"tourn_detail": {"rpg_game_big_version": "4.7", "season_id": "1"}}
        with patch.object(currency, "api", return_value={"list": [stale]}):
            self.assertEqual(currency.guides(data, ""), [])
