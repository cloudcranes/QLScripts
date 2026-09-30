#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cron: 25 8 * * *
new Env('RAINYUN_ACCOUNTS'): email1:password1\\nemail2:password2
new Env('RAINYUN_API_KEY'): (可选) 用户 APIKey (X-Api-Key 模式, 优先级最高)
new Env('RAINYUN_REMOTE_CHROME_CDP'): (可选, captcha 降级需要) http://host:9222 — 远程 Chrome CDP, 面板主机不装 chromium
  在另一台机器启动: chrome.exe --headless --no-sandbox --disable-gpu --remote-debugging-port=9222
雨云 (rainyun) 多账号签到 — 青龙面板原生适配

策略 (默认 cookie-only):
  1) 优先 RAINYUN_ACCOUNTS 环境变量 (青龙推荐); 本地调试 fallback 读 rainyun_accounts.txt
  2) cookie 存储 (rainyun_cookies.jsonl) 复用每账号最新 active, 走 /user/reward/tasks
  3) cookie 失效 → 标记 retired, 自动账密登录补一条新 active
  4) --mode sign 端到端签到: cookie → captcha (第三方 API → playwright CDP+ddddocr 降级) → sign
  5) --mode info / tasks / captcha / login 仅调试

依赖: pip install httpx ddddocr opencv-python-headless playwright requests
        (不需要 playwright install chromium — playwright 路径走远程 Chrome)

青龙用法:
  拉脚本到 /ql/scripts/rainyun.py → 面板配置 cron + RAINYUN_ACCOUNTS 环境变量即可
  本地调试:
  export RAINYUN_ACCOUNTS=email1:pass1
  python rainyun.py --mode sign

用法:
  python rainyun.py                                  # 默认 cookie 模式 + 端到端签到