# 星铁展示柜与配队顾问 · AstrBot

基于 [YueHua46 的星铁展示柜图片插件](https://github.com/YueHua46/astrbot_plugin_starrail_profile)，本版整合 [星铁顾问](https://github.com/YouKnowWh/astrbot_plugin_hsr_advisor)。群友绑定一次 UID，即可查面板图片，或让群里已有的模型根据展示角色、实际光锥和遗器给配队建议。

## QQ 群命令

| 命令 | 用途 |
| --- | --- |
| `/绑定星铁 100534214` | 保存自己的默认 UID。再次绑定会替换旧值。 |
| `/我的星铁UID` | 查看自己的绑定。 |
| `/星铁配队` 或 `/星铁配队 混沌回忆 对单` | 查询自己的公开展示柜，把角色、实际装备、套装和词条交给当前模型，生成配队及开局建议。 |
| `/星铁数据` | 检查常规资料和货币战争的来源及缓存时间。 |
| `/星铁面板` | 发送已绑定 UID 的展示柜图片。 |
| `/星铁面板 100534214` | 临时查询指定 UID，保留原绑定。 |
| `/解绑星铁` | 删除自己的绑定。 |

绑定保存在 AstrBot 数据库中，按平台实例和消息发送者 ID 隔离。机器人重启后仍可读取。同一实例在不同群里收到相同的发送者 ID 时，可沿用该绑定。UID 表示默认查询对象。英文命令分别为 `/srbind`、`/sruid`、`/srprofile`、`/srunbind`，原有 `/sr <UID>` 同样可用。

## 功能

- 通过 MiHoMo Parsed Data API 查询星穹铁道公开展示柜。
- 生成 1080x1920 二次元风格 Profile 图片。
- 支持指令触发和自然语言触发。
- 请求失败后最多自动重试 5 次。
- 使用 Playwright 渲染图片，适合 Linux 服务器部署。

## 安装

使用 AstrBot 4.29.4 或以上的 4.x 版本。只需安装本仓库的一个插件。如果装过独立版「星铁配队与货币战争顾问」，请先在插件页停用独立版，以免重复响应相同命令。已经使用本仓库 v1.1.0 的负责人直接更新即可，沿用现有绑定。

在 AstrBot WebUI 的「插件 → 从链接安装」填写下列地址。若已安装原版，请用此地址安装增强版；两个版本使用同一个插件标识。

```text
https://github.com/YouKnowWh/astrbot_plugin_starrail_profile
```

依赖：

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

Linux 部署如果缺浏览器系统依赖：

```bash
python -m playwright install --with-deps chromium
```

## 顾问如何使用展示柜

开启群聊的聊天模型并允许本插件。发送 `/星铁配队` 会带着本人的角色资料向当前模型发起请求。自然语言模式使用支持工具调用的 AstrBot 内置 Agent，在当前人格启用本插件的工具和 `hsr-showcase-advisor` 技能后，可以直接问「按我的展示柜配一队，为什么这样选光锥？」。账号未绑定或没有展示角色时，机器人会提示补齐信息。

模型接收公开角色的等级、星魂、速度等面板数据，已装备光锥的等级、叠影，以及每件遗器的等级、套装、主副词条。只用可见的装备和角色作为配队依据。展示柜之外的持有情况、仓库里未装备的遗器和当前敌方信息需要玩家补充。

常规角色和光锥资料取自 [StarRailRes](https://github.com/Mar-7th/StarRailRes)，6 小时到期后下次查询时自动检查；[货币战争赛季资料和攻略](https://act.miyoushe.com/sr/event/currency-wars/index.html)每小时按需刷新。问货币战争时可直接描述这局的商店、金币及前后台，再请机器人给下一步建议。

## 使用

```text
/srprofile 100534214
/sr 100534214
```

自然语言也可以触发：

```text
帮我查一下星铁 UID 100534214
```

## 配置

- `lang`: API 语言，默认 `cn`
- `timeout`: API 请求超时秒数，默认 `30`
- `retries`: 请求失败后的最大重试次数，默认 `5`
- `proxy`: 可选代理，例如 `http://127.0.0.1:7890`
- `use_env_proxy`: 是否使用系统环境代理
- `asset_base`: 素材镜像基础地址，默认 jsDelivr，并内置其他镜像兜底
- `asset_timeout`: 单个素材下载超时秒数，默认 `20`
- `inline_assets`: 是否将远程素材内嵌进 HTML，默认开启，建议开启以避免截图时头像/角色图空白
- `output_dir`: 报告图片输出目录
- `screenshot_timeout`: Playwright 截图超时秒数
- `browser_channel`: 可选浏览器通道，例如 `chrome`、`msedge`
- `keep_html`: 是否保留中间 HTML
