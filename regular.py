"""StarRailRes tables from one immutable revision per refresh."""

import re
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from .cache import request_json

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


def refresh(previous):
    meta = request_json(f"https://api.github.com/repos/{REPO}/commits/master")
    sha = meta["sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("上游版本标识异常")
    if previous and previous["sha"] == sha:
        return previous

    def table(name):
        url = f"https://raw.githubusercontent.com/{REPO}/{sha}/index_min/cn/{name}.json"
        result = request_json(url)
        if not isinstance(result, dict) or not result:
            raise ValueError(f"数据表 {name} 为空")
        return name, result

    with ThreadPoolExecutor(max_workers=4) as pool:
        data = dict(pool.map(table, TABLES))
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
