# astrbot_plugin_starrail_profile

基于 [YueHua46 的星铁展示柜图片插件](https://github.com/YueHua46/astrbot_plugin_starrail_profile)，此版本增加 QQ 用户的 UID 绑定。查询范围为游戏内公开展示的角色。

## QQ 群命令

| 命令 | 用途 |
| --- | --- |
| `/绑定星铁 100534214` | 保存自己的默认 UID。再次绑定会替换旧值。 |
| `/我的星铁UID` | 查看自己的绑定。 |
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
