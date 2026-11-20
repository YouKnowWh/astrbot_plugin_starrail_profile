"""StarRailRes tables from one immutable revision per refresh."""

import asyncio
import gzip
import json
import logging
import re
import sqlite3
import time
from decimal import Decimal
from pathlib import Path

import aiohttp

REPO = "Mar-7th/StarRailRes"
TABLES = (
    "characters",
    "character_skills",
    "character_skill_trees",
    "character_ranks",
    "character_promotions",
    "light_cones",
    "light_cone_ranks",
    "light_cone_promotions",
    "paths",
    "elements",
    "nickname",
)


REFRESH_SECONDS = 8
log = logging.getLogger(__name__)


def bundled():
    path = Path(__file__).parent / "data" / "StarRailRes" / "regular.json.gz"
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


async def fetch_json(session, url):
    for attempt in range(2):
        try:
            async with session.get(url) as response:
                response.raise_for_status()
                body = bytearray()
                async for chunk in response.content.iter_chunked(64 * 1024):
                    body.extend(chunk)
                    if len(body) > 16 * 1024 * 1024:
                        raise ValueError("数据响应超出预期大小")
                return json.loads(body)
        except aiohttp.ClientResponseError as exc:
            if attempt or exc.status not in (502, 503, 504):
                raise
        except (
            aiohttp.ClientConnectionError,
            aiohttp.ClientPayloadError,
            TimeoutError,
        ):
            if attempt:
                raise


async def refresh(previous):
    connector = aiohttp.TCPConnector(limit=4)
    timeout = aiohttp.ClientTimeout(total=REFRESH_SECONDS, sock_connect=3)
    async with aiohttp.ClientSession(
        connector=connector,
        trust_env=True,
        timeout=timeout,
        headers={"User-Agent": "AstrBot-HSR-Advisor"},
    ) as session:
        meta = await fetch_json(
            session, f"https://api.github.com/repos/{REPO}/commits/master"
        )
        sha = meta["sha"]
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError("上游版本标识异常")
        if previous["sha"] == sha:
            return previous

        async def table(name):
            url = f"https://raw.githubusercontent.com/{REPO}/{sha}/index_min/cn/{name}.json"
            result = await fetch_json(session, url)
            if not isinstance(result, dict) or not result:
                raise ValueError(f"数据表 {name} 为空")
            return result

        # One failed table cancels its siblings; never publish a partial revision.
        async with asyncio.TaskGroup() as group:
            tables = {name: group.create_task(table(name)) for name in TABLES}
        data = {name: task.result() for name, task in tables.items()}
    for cid, char in data["characters"].items():
        if not char["name"] or cid not in data["character_promotions"]:
            raise ValueError("角色基础表不完整")
        for key, ref in (
            ("skills", "character_skills"),
            ("ranks", "character_ranks"),
            ("skill_trees", "character_skill_trees"),
        ):
            if any(i not in data[ref] for i in char[key]):
                raise ValueError(f"角色 {cid} 的 {key} 不完整")
    for lid in data["light_cones"]:
        if (
            lid not in data["light_cone_ranks"]
            or lid not in data["light_cone_promotions"]
        ):
            raise ValueError("光锥数据不完整")
    return dict(data, sha=sha, updated=meta["commit"]["committer"]["date"])


class Catalog:
    def __init__(self, snapshots):
        self.store = snapshots
        self.data = None
        self.checked = None
        self.retry_after = 0.0
        self.loading = asyncio.Lock()
        self.updating = asyncio.Lock()

    def _load_local(self):
        seed = bundled()
        try:
            with self.store.connect() as db:
                row = db.execute(
                    "SELECT checked, body FROM snapshots WHERE name='regular'"
                ).fetchone()
            if row:
                old = json.loads(row[1])
                if old["updated"] >= seed["updated"]:
                    return old, row[0]
        except (sqlite3.Error, ValueError, TypeError, KeyError) as exc:
            log.warning("Could not read cached regular catalog: %s", exc)
        return seed, None

    def _save(self, data, checked):
        body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        with self.store.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO snapshots VALUES ('regular', ?, ?)",
                (checked, body),
            )

    async def read(self):
        if self.data is None:
            async with self.loading:
                if self.data is None:
                    self.data, self.checked = await asyncio.to_thread(self._load_local)
        if self.checked is not None and 0 <= time.time() - self.checked < 6 * 3600:
            return self.data, self.checked, "可用", False

        source = "随包资料" if self.checked is None else "本地缓存"
        if time.monotonic() < self.retry_after:
            return self.data, self.checked, "刷新失败，使用" + source, True
        if self.updating.locked():
            return self.data, self.checked, "更新中，使用" + source, False

        async with self.updating:
            try:
                async with asyncio.timeout(REFRESH_SECONDS):
                    fresh = await refresh(self.data)
            except (
                TimeoutError,
                aiohttp.ClientError,
                OSError,
                ValueError,
                KeyError,
                ExceptionGroup,
            ) as exc:
                self.retry_after = time.monotonic() + 60
                detail = exc.exceptions[0] if isinstance(exc, ExceptionGroup) else exc
                log.warning(
                    "StarRailRes refresh failed (%s: %s; network budget %ss); using revision %.10s",
                    type(detail).__name__,
                    detail,
                    REFRESH_SECONDS,
                    self.data["sha"],
                )
                return self.data, self.checked, "刷新失败，使用" + source, True

            checked = int(time.time())
            try:
                await asyncio.to_thread(self._save, fresh, checked)
            except (OSError, sqlite3.Error) as exc:
                log.warning("Keeping verified regular catalog in memory: %s", exc)
            self.data, self.checked = fresh, checked
            self.retry_after = 0.0
            return fresh, checked, "可用", False


def describe(text, params):
    def replace(m):
        idx = int(m[1]) - 1
        if not 0 <= idx < len(params):
            return "〔来源缺少参数〕"
        value = Decimal(str(params[idx])) * (100 if m[2] else 1)
        return format(value.normalize(), "f") + m[2]

    return re.sub(r"#(\d+)\[\w*\](%?)", replace, text or "")


def stats80(promotion):
    return {
        k: round(v["base"] + 79 * v["step"], 4)
        for k, v in promotion["values"][-1].items()
    }


def character(d, row, level):
    cid = row["id"]
    skills = []
    for sid in row["skills"]:
        s = d["character_skills"][sid]
        if s["type"] == "MazeNormal":
            continue
        default = 6 if s["type"] == "Normal" else 10
        n = min(level or default, s["max_level"])
        params = s["params"]
        values = params[n - 1] if len(params) >= n else []
        skills.append(
            {
                "id": sid,
                "强化形态": sid.startswith("1" + cid) and len(sid) > len(cid) + 2,
                "类型": s["type_text"],
                "名称": s["name"],
                "等级": n,
                "效果": describe(s["desc"] or s["simple_desc"], values) or "来源未列出",
            }
        )
    traces = []
    for tid in row["skill_trees"]:
        node = d["character_skill_trees"][tid]
        if node["name"] and node["desc"]:
            traces.append(
                {
                    "id": tid,
                    "强化形态": tid.startswith("1" + cid) and len(tid) > len(cid) + 3,
                    "名称": node["name"],
                    "效果": describe(node["desc"], (node["params"] or [[]])[0]),
                }
            )
    ranks = []
    for base_id in row["ranks"]:
        for rid in (base_id, "1" + base_id):
            rank = d["character_ranks"].get(rid)
            if not rank:
                continue
            desc = rank["desc"]

            def linked_skill(match):
                skill = d["character_skills"].get(match[1])
                level_index = int(match[2]) - 1
                if not skill or not 0 <= level_index < len(skill["params"]):
                    return "〔来源缺少关联技能参数〕"
                return describe(skill["desc"], skill["params"][level_index])

            desc = re.sub(
                r"#\{series_ref_skill_desc:[^,]+,(\d+),(\d+)\}", linked_skill, desc
            )
            ranks.append(
                {
                    "层数": rank["rank"],
                    "名称": rank["name"],
                    "强化形态": rid != base_id,
                    "说明": desc,
                }
            )
    return {
        "属性": d["elements"][row["element"]]["name"],
        "能量上限字段": row["max_sp"],
        "80级满晋阶裸面板": stats80(d["character_promotions"][cid]),
        "技能": skills,
        "行迹能力": traces,
        "星魂": ranks,
    }


def cone(d, row):
    lid = row["id"]
    skill = d["light_cone_ranks"][lid]
    return {
        "80级满晋阶裸面板": stats80(d["light_cone_promotions"][lid]),
        "被动": skill["skill"],
        "叠影效果": {
            f"S{i}": describe(skill["desc"], p)
            for i, p in enumerate(skill["params"], 1)
        },
    }


def lookup(data, query, level=0):
    if level not in range(16):
        raise ValueError("技能等级范围为 1–15，0 表示常用等级")
    key = query.strip().casefold()
    if not 1 <= len(key) <= 60:
        raise ValueError("请提供一个角色名、光锥名或 ID")
    matches = []
    for group in ("characters", "light_cones"):
        aliases = data["nickname"].get(group, {})
        for i, row in data[group].items():
            path = data["paths"][row["path"]]["name"]
            display = row["name"].replace("{NICKNAME}", "开拓者")
            names = [
                i,
                display,
                display + "·" + path,
                path + display,
                *aliases.get(i, []),
            ]
            names = [name.casefold() for name in names if name]
            if key in names or any(key in name for name in names):
                matches.append((0 if key in names else 1, group, row, path))
    if not matches:
        return {"结果": "未收录，请使用正式中文名或 ID"}
    best = min(x[0] for x in matches)
    options = [m for m in matches if m[0] == best]
    if len(options) > 1:
        return {
            "请确认条目": [
                f"{r['name'].replace('{NICKNAME}', '开拓者')}（{p}，{r['id']}）"
                for _, _, r, p in options[:20]
            ]
        }
    _, group, row, path = options[0]
    info = character(data, row, level) if group == "characters" else cone(data, row)
    return {
        "名称": row["name"].replace("{NICKNAME}", "开拓者"),
        "id": row["id"],
        "命途": path,
        "稀有度": row["rarity"],
        **info,
    }
