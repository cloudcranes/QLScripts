# QLScripts — 青龙自用签到脚本

5 个独立签到脚本, 每个脚本头部自带 `cron:` 与 `new Env(...)` 元注释, 直接放进青龙面板 `/ql/scripts/` 即可。

## 站点一览

| 站点 | 脚本 | cron | 环境变量 |
|---|---|---|---|
| iKuuu VPN | `sites/ikuuu/ikuuu.py` | `35 8 * * *` | `IKUUU_ACCOUNTS` (email:pass 多行) |
| JMComic | `sites/jmcomic/jmcomic_checkin.py` | `25 8 * * *` | `JMCOMIC_ACCOUNTS` (user:pass 多行) |
| 雨云 (rainyun) | `sites/rainyun/rainyun.py` | `25 8 * * *` | `RAINYUN_ACCOUNTS` (email:pass 多行) + `RAINYUN_API_KEY` (可选) |
| MEFRP | `sites/mefrp/mefrp.py` | `50 8 * * *` | `MEFRP_USER_TOKEN` (Bearer sk-...) + `REMOTE_CHROME_CDP` (可选) |
| 百度贴吧 | `sites/tieba/tieba.py` | `45 8 * * *` | `Tieba_BDUSS` + `Tieba_STOKEN` (浏览器 Cookie) |

每个脚本文件首行注释自带青龙面板识别格式: `cron:` + `new Env(...)`, 拉脚本时面板自动识别。

## 青龙面板拉取

```bash
# 1. 一次性 git clone 到 /ql/scripts/
cd /ql/scripts
git clone https://github.com/cloudcranes/QLScripts.git cloudcranes
ln -s cloudcranes/sites/ikuuu/ikuuu.py ikuuu.py
ln -s cloudcranes/sites/jmcomic/jmcomic_checkin.py jmcomic.py
ln -s cloudcranes/sites/rainyun/rainyun.py rainyun.py
ln -s cloudcranes/sites/mefrp/mefrp.py mefrp.py
ln -s cloudcranes/sites/tieba/tieba.py tieba.py
```

或直接在面板 "订阅管理" 加 `https://github.com/cloudcranes/QLScripts.git` 拉取。

## 青龙面板配置 (推荐)

1. 面板 "定时任务" → 新建, 1 个站 1 个任务
2. **脚本路径**: `python sites/<domain>/<domain>.py` 或上面建好的软链
3. **定时规则**: 见上表 cron
4. **环境变量**: 添加对应 `<DOMAIN>_*`, 多账号用 `\\n` 分隔 (青龙界面 `\n` 会被转义)

```bash
# 雨云
RAINYUN_ACCOUNTS = "alanmaster.amy@gmail.com:xg363034"
```

```bash
# iKuuu
IKUUU_ACCOUNTS = "qpwo10qpwo@gmail.com:cxd89851718\n2521543680@qq.com:xg363034"
```

```bash
# JMComic
JMCOMIC_ACCOUNTS = "Alanmaster:xg363034\nqpwo10qpwo:zxd119cs"
```

```bash
# MEFRP — Bearer token, 单账号
MEFRP_USER_TOKEN = "sk-eyJ..."
REMOTE_CHROME_CDP = "http://192.168.1.107:9222"   # 可选, 不填走本地 headless
```

```bash
# 百度贴吧 — 浏览器登录 https://tieba.baidu.com, F12 抓 BDUSS + STOKEN
Tieba_BDUSS = "..."
Tieba_STOKEN = "..."
```

## 依赖安装

在青龙面板 "依赖管理" 装:

```
httpx curl_cffi requests        # 通用
ddddocr opencv-python-headless playwright    # 雨云 TCaptcha + mefrp 浏览器过 slide
playwright-stealth faker    # iKuuu login 模式 (可选, cookie-only 模式不需要)
```

playwright 装完后还要 `playwright install chromium` (rainyun 降级策略 + mefrp 主流程都需要)。

## 本地调试 (无青龙)

```powershell
# Windows PowerShell
$env:IKUUU_ACCOUNTS = "email1:pass1`nemail2:pass2"
$env:PYTHONIOENCODING = "utf-8"
python sites\ikuuu\ikuuu.py
```

## 凭据 / cookie 文件

- `*_accounts.txt`: 本地调试 fallback (一行 `username:password`)
- `*_cookies.jsonl`: cookie 复用存储 (脚本自动维护)
- 均已在 `.gitignore` 中, 严禁入库

## 目录结构

```
sites/
├── ikuuu/
│   ├── ikuuu.py
│   ├── ikuuu_accounts.txt          # 模板 (不传 git)
│   ├── ikuuu_cookies.jsonl         # 运行时生成
│   └── ikuuu_cookies.txt           # legacy 兜底
├── jmcomic/
│   ├── jmcomic_checkin.py
│   ├── jmcomic_accounts.txt        # 模板 (不传 git)
│   ├── checkin_state.json          # 运行时生成
│   ├── _pretty.py                  # 兼容层
│   └── ql_notify.py                # 兼容层
├── rainyun/
│   ├── rainyun.py
│   ├── tcaptcha_solver.py
│   ├── rainyun_accounts.txt        # 模板 (不传 git)
│   └── rainyun_cookies.jsonl        # 运行时生成
├── mefrp/
│   ├── mefrp.py                    # 浏览器过 ESA slide + 每日签到
│   ├── _pretty.py                  # 兼容层
│   └── ql_notify.py                # 兼容层
└── tieba/
    ├── tieba.py                    # 百度贴吧多吧批量签到 (基于 acoolbook/ym 改造)
    └── ql_notify.py                # 兼容层
```

## 升级

```bash
cd /ql/scripts/cloudcranes
git pull
```

脚本逻辑变更会被拉取, 但 `accounts.txt` / `cookies.jsonl` 是 .gitignore, 不会覆盖本地凭据。