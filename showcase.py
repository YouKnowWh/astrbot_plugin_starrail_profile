"""Build model input from equipped items in a public MiHoMo showcase."""


def select(row, *keys):
    return {key: row[key] for key in keys if row.get(key) is not None}


def affix(row):
    if not row:
        return None
    name = row.get("name") or row.get("field")
    display = row.get("display")
    if not name or display is None:
        return None
    return f"{name} {display}"


def describe_character(character):
    cone = character.get("light_cone") or {}
    stats = {
        r["field"]: r["display"]
        for r in character.get("statistics") or []
        if r.get("field") and r.get("display") is not None
    }
    gear = []
    for item in character.get("relics") or []:
        gear.append(
            {
                "名称": item.get("name"),
                "套装": item.get("set_name"),
                "部位序号": item.get("type"),
                "等级": item.get("level"),
                "主词条": affix(item.get("main_affix")),
                "副词条": [
                    value
                    for sub in item.get("sub_affix") or []
                    if (value := affix(sub))
                ],
            }
        )
    return {
        "角色ID": str(character["id"]),
        "名称": character.get("name"),
        "等级": character.get("level"),
        "星魂": character.get("rank"),
        "强化形态": character.get("enhanced"),
        "命途": (character.get("path") or {}).get("name"),
        "属性": (character.get("element") or {}).get("name"),
        "装备光锥": {
            "ID": cone.get("id"),
            "名称": cone.get("name"),
            "等级": cone.get("level"),
            "叠影": cone.get("rank"),
        }
        if cone
        else None,
        "面板合计": stats,
        "技能": [
            select(s, "name", "level", "simple_desc")
            for s in character.get("skills") or []
            if s.get("type") != "MazeNormal"
        ],
        "已生效套装": [
            select(s, "name", "num", "desc") for s in character.get("relic_sets") or []
        ],
        "装备遗器": gear,
    }


def describe_showcase(data, uid):
    if str((data.get("player") or {}).get("uid") or "") != uid:
        raise ValueError("展示柜返回的账户与绑定 UID 不符，请稍后重试。")
    characters = data.get("characters")
    if not isinstance(characters, list) or not characters:
        raise ValueError("没有读到公开展示角色，请在游戏内放入展示角色并公开后再试。")
    return {
        "范围": "当前发言人已绑定 UID 的公开展示角色及已穿戴装备",
        "角色": [describe_character(c) for c in characters],
    }
