"""Public Chinese HoYoLAB Currency Wars season and community lineups."""

import re

from .cache import request_json

BASE = "https://act-api-takumi.miyoushe.com/event/rpgcurrencywar/game/"
HEADERS = {"x-rpc-currencywar-tourn": "tourn", "x-rpc-platform": "pc"}
GUIDE = "https://act.miyoushe.com/sr/event/currency-wars/index.html#/lineup/"


LEGACY_GUIDE = (
    "https://act.miyoushe.com/sr/event/e20241220rpg-3Tii9M/index.html#/lineup/"
)


def current_source(plan):
    """Upgrade links in snapshots saved by v1.0.0, including offline snapshots."""
    source = plan["来源"]
    if source.startswith(LEGACY_GUIDE):
        return {**plan, "来源": GUIDE + source.removeprefix(LEGACY_GUIDE)}
    return plan


def api(path, payload=None):
    envelope = request_json(BASE + path, payload, HEADERS)
    if envelope.get("retcode") != 0 or not isinstance(envelope.get("data"), dict):
        raise ValueError("米游社数据暂不可用")
    return envelope["data"]


def names(rows):
    return [
        r.get("name") or r.get("title") for r in rows if r.get("name") or r.get("title")
    ]


def refresh(_previous):
    d = api("config?game=hkrpg")
    if not all(
        d.get(k)
        for k in (
            "role_list",
            "trait_info_list",
            "equipment_list",
            "season_id",
            "rpg_game_big_version",
            "sub_season_id",
        )
    ):
        raise ValueError("赛季资料不完整")
    props = {
        r["property_type"]: r["name"] for r in d["role_property_list"] if r["name"]
    }

    def clean(text):
        text = re.sub(
            r"<property type=([^ >]+)[^>]*>",
            lambda m: props.get(m[1], m[1]),
            text or "",
        )
        return re.sub(r"<[^>]+>", "", text).replace(r"\n", "\n")

    entries = []
    traits = {}
    for r in d["role_list"]:
        if r.get("is_hide"):
            continue
        skills = [
            {
                "位置": s["front_back_type"],
                "名称": s["name"],
                "星级效果": {
                    str(t["star"]): clean(t["desc"]) for t in s["skill_stars"]
                },
            }
            for s in r["skills"]
        ]
        entries.append(
            {
                "分类": "员工",
                "名称": r["name"],
                "id": r["id"],
                "费用": r["rarity"],
                "位置": r["front_back_type"],
                "羁绊": names(r["trait_details"]),
                "技能": skills,
            }
        )
        for t in r["trait_details"]:
            trait = traits.setdefault(
                t["id"],
                {
                    "分类": "羁绊",
                    "id": t["id"],
                    "名称": t["name"],
                    "效果": clean(t["desc"]),
                    "员工": [],
                },
            )
            trait["员工"].append(r["name"])
    entries.extend(traits.values())
    for category, key in (
        ("装备", "equipment_list"),
        ("投资策略", "fight_augment_list"),
        ("投资环境", "portal_list"),
        ("主角光环", "spot_light_list"),
    ):
        for r in d.get(key, []):
            item = {
                "分类": category,
                "id": r["id"],
                "名称": r.get("name") or r.get("title"),
                "效果": clean(r.get("desc")),
            }
            if r.get("compose_list"):
                item["合成配方"] = [
                    names(recipe["childrens"]) for recipe in r["compose_list"]
                ]
            entries.append(item)
    return {
        "version": str(d["rpg_game_big_version"]),
        "season": str(d["season_id"]),
        "sub": str(d["sub_season_id"]),
        "entries": entries,
    }


def lookup(data, query):
    key = query.strip()
    if not 1 <= len(key) <= 60:
        raise ValueError("请提供要查询的员工、羁绊、装备、策略、环境或光环名称")
    exact = [r for r in data["entries"] if key in (r["id"], r["名称"])]
    if exact:
        return {"条目": exact}
    hits = [r for r in data["entries"] if key in r["名称"] or key == r["分类"]]
    return {
        "候选": [f"{r['名称']}（{r['分类']}，{r['id']}）" for r in hits[:24]],
        "匹配数": len(hits),
    }


def guides(data, role_id):
    result = api(
        "lineup/index",
        {
            "game": "hkrpg",
            "page": "1",
            "limit": "10",
            "lineup_type": "Tourn",
            "order": "Hot",
            "role_ids": [role_id] if role_id else [],
            "trait_ids": [],
            "match_change_job": False,
            "match_hard": False,
            "next_page_token": "",
        },
    )
    output = []
    for row in result["list"]:
        plan = row["tourn_detail"]
        if (
            plan.get("is_expired")
            or plan.get("is_sub_expired")
            or str(plan.get("season_id")) != data["season"]
            or str(plan.get("sub_season_id")) != data["sub"]
            or str(plan.get("rpg_game_big_version")) != data["version"]
        ):
            continue
        stages = []
        listed = set()
        for stage in plan["role_stages"]:
            roles = stage["front_roles"] + stage["back_roles"]
            listed.update(str(r["id"]) for r in roles)
            stages.append(
                {
                    "阶段": stage["stage"],
                    "前台": names(stage["front_roles"]),
                    "后台": names(stage["back_roles"]),
                    "主力装备": {
                        r["name"]: names(r.get("first_equipments") or [])
                        for r in roles
                        if r.get("is_carry")
                    },
                }
            )
        if role_id and role_id not in listed:
            continue
        output.append(
            {
                "标题": row["title"][:140],
                "运营思路": (row["description"] or "")[:1600],
                "阵容": stages,
                "投资环境": names(plan["portals"]),
                "优先策略": names(plan["first_fight_augments"]),
                "装备顺序": names(plan["order_compose"]),
                "来源": GUIDE + row["id"],
            }
        )
        if len(output) == 3:
            break
    return output
