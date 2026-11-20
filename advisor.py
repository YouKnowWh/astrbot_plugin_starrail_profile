from datetime import UTC, datetime

from . import currency, regular
from .cache import Snapshots


def checked_at(timestamp):
    return datetime.fromtimestamp(timestamp, UTC).isoformat(timespec="minutes")


class Advisor:
    def __init__(self, directory):
        self.snapshots = Snapshots(directory)
        self.catalog = regular.Catalog(self.snapshots)

    async def regular(self, name, level=0, skill="", question=""):
        data, at, state, stale = await self.catalog.read()
        return {
            "来源": f"https://github.com/{regular.REPO}/tree/{data['sha']}/index_min/cn",
            "来源提交日期": data["updated"],
            "上次核对": checked_at(at) if at is not None else None,
            "资料状态": state,
            "刷新失败沿用缓存": stale,
            **regular.lookup(data, name, level, skill, question),
        }

    def currency(self, name, lineup=False):
        data, at, stale = self.snapshots.read("currency", 3600, currency.refresh)
        info = {
            "来源": currency.BASE + "config?game=hkrpg",
            "游戏版本": data["version"],
            "赛季": data["season"],
            "子赛季": data["sub"],
            "上次核对": checked_at(at),
            "刷新失败沿用缓存": stale,
        }
        if not lineup:
            return dict(info, **currency.lookup(data, name))
        rid = ""
        if name.strip():
            matches = currency.lookup(data, name)
            roles = [r for r in matches.get("条目", []) if r["分类"] == "员工"]
            if len(roles) != 1:
                return dict(info, 提示="请先确定赛季内的员工名或 ID", **matches)
            rid = str(roles[0]["id"])
        key = "/".join(("guides", data["version"], data["season"], data["sub"], rid))
        plans, fetched, old = self.snapshots.read(
            key, 3600, lambda _: currency.guides(data, rid)
        )
        return dict(
            info,
            攻略核对时间=checked_at(fetched),
            刷新失败沿用缓存=stale or old,
            当前赛季社区攻略=[currency.current_source(plan) for plan in plans],
            范围="米游社热度排序首页，最多返回三套匹配方案",
        )
