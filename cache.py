"""On-demand, atomic snapshots shared by all chats of one bot."""

import hashlib
import json
import logging
import os
import sqlite3
import time
from http.client import IncompleteRead, RemoteDisconnected
from pathlib import Path
from threading import Lock
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

log = logging.getLogger(__name__)


def request_json(url, payload=None, headers=None):
    hdr = {"User-Agent": "AstrBot-HSR-Advisor/1.0", "Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        hdr["Content-Type"] = "application/json"
    hdr.update(headers or {})
    request = Request(url, data=data, headers=hdr)
    for attempt in range(2):
        try:
            with urlopen(request, timeout=10) as response:
                raw = response.read(16 * 1024 * 1024 + 1)
            break
        except HTTPError as exc:
            if attempt or exc.code not in (502, 503, 504):
                raise
        except (TimeoutError, URLError, IncompleteRead, RemoteDisconnected):
            if attempt:
                raise
    if len(raw) > 16 * 1024 * 1024:
        raise ValueError("数据响应超出预期大小")
    return json.loads(raw)


class Snapshots:
    def __init__(self, directory):
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        self.db = os.fspath(path / "catalog-v1.sqlite3")
        self.locks = [Lock() for _ in range(16)]
        self.retry_after = {}
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS snapshots (name TEXT PRIMARY KEY, checked INTEGER, body TEXT)"
            )

    def connect(self):
        return sqlite3.connect(self.db, timeout=10)

    def read(self, key, ttl, fetch):
        lock = self.locks[hashlib.sha256(key.encode()).digest()[0] % len(self.locks)]
        with lock, self.connect() as db:
            row = db.execute(
                "SELECT checked, body FROM snapshots WHERE name=?", (key,)
            ).fetchone()
            now = int(time.time())
            old = json.loads(row[1]) if row else None
            if row and 0 <= now - row[0] < ttl:
                return old, row[0], False
            if now < self.retry_after.get(key, 0):
                if row:
                    return old, row[0], True
                raise ValueError("上游暂不可用，稍后重试")
            try:
                fresh = fetch(old)
            except Exception as exc:
                self.retry_after[key] = now + 60
                log.warning("Could not refresh %s: %s", key, exc)
                if row:
                    return old, row[0], True
                raise ValueError("暂时无法读取上游，当前没有可用缓存") from exc
            checked = int(time.time())
            db.execute(
                "INSERT OR REPLACE INTO snapshots VALUES (?, ?, ?)",
                (
                    key,
                    checked,
                    json.dumps(fresh, ensure_ascii=False, separators=(",", ":")),
                ),
            )
            self.retry_after.pop(key, None)
            return fresh, checked, False
