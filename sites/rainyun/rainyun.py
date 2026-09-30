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
  python rainyun.py --mode info                      # 拉用户信息
  python rainyun.py --mode tasks                     # 任务列表
  python rainyun.py --mode sign                      # 端到端签到
  python rainyun.py --mode login                     # 账密拿 cookie (无 captcha)
  python rainyun.py --mode captcha                   # 单跑 captcha 自检 (无 sign)
  python rainyun.py --mode sign --vticket T --vrandstr R  # 强制用人工 ticket
  python rainyun.py --mode sign --no-captcha         # 跳过 captcha (调试)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ====== 迷你 CookieStore (JSONL, 替代旧 cookie_store.py) ======
@dataclass
class _CkEntry:
    email: str
    cookie: str
    status: str  # active | retired
    expire_at: int = 0
    last_used: float = 0.0


class _MiniStore:
    """单文件 JSONL cookie store. 每行 {email,cookie,status,expire_at,last_used}."""

    def __init__(self, path: Path):
        self.path = path
        self._cache: list[_CkEntry] = []
        self._loaded = False

    def _ensure(self):
        if self._loaded:
            return
        if self.path.exists():
            import json as _json
            for line in self.path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    o = _json.loads(line)
                    self._cache.append(_CkEntry(
                        email=o.get("email", o.get("username", "")),
                        cookie=o.get("cookie", ""),
                        status=o.get("status", "active"),
                        expire_at=int(o.get("expire_at", 0) or 0),
                        last_used=float(o.get("last_used", 0) or 0),
                    ))
                except Exception:
                    pass
        self._loaded = True

    def _flush(self):
        import json as _json
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            for e in self._cache:
                f.write(_json.dumps({
                    "email": e.email, "cookie": e.cookie, "status": e.status,
                    "expire_at": e.expire_at, "last_used": e.last_used,
                }, ensure_ascii=False) + "\n")

    def _ck_signature(self, cookie: str) -> str:
        """雨云用 rain-session 作为唯一身份键."""
        m = re.search(r"rain-session=([^;]+)", cookie)
        return m.group(1) if m else cookie[:80]

    def actives_for(self, email: str) -> list[_CkEntry]:
        self._ensure()
        return [e for e in self._cache if e.email.lower() == email.lower() and e.status == "active"]

    def latest_active(self, email: str) -> _CkEntry | None:
        items = self.actives_for(email)
        if not items:
            return None
        items.sort(key=lambda x: (x.last_used, x.expire_at), reverse=True)
        return items[0]

    def mark_used(self, cookie: str) -> None:
        self._ensure()
        sig = self._ck_signature(cookie)
        now = time.time()
        for e in self._cache:
            if self._ck_signature(e.cookie) == sig and e.status == "active":
                e.last_used = now
        self._flush()

    def mark_expired(self, cookie: str) -> None:
        self._ensure()
        sig = self._ck_signature(cookie)
        changed = False
        for e in self._cache:
            if self._ck_signature(e.cookie) == sig and e.status == "active":
                e.status = "retired"
                changed = True
        if changed:
            self._flush()

    def upsert(self, email: str, cookie: str, *, status: str = "active") -> _CkEntry | None:
        self._ensure()
        sig = self._ck_signature(cookie)
        for e in self._cache:
            if self._ck_signature(e.cookie) == sig:
                e.email = email or e.email
                e.status = status
                if status == "active":
                    e.last_used = time.time()
                self._flush()
                return e
        entry = _CkEntry(email=email, cookie=cookie, status=status, last_used=time.time())
        self._cache.append(entry)
        self._flush()
        return entry


# ====== 路径配置 ======
HERE = Path(__file__).resolve().parent
COOKIE_STORE_FILE = HERE / "rainyun_cookies.jsonl"
ACCOUNTS_FILE = HERE / "rainyun_accounts.txt"

BASE = "https://api.v2.rainyun.com"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
DEFAULT_LOGIN_HEADERS = {
    "User-Agent": UA,
    "Content-Type": "application/json",
    "Origin": "https://www.rainyun.com",
    "Referer": "https://www.rainyun.com/",
}
DEFAULT_SIGN_HEADERS = {
    "User-Agent": UA,
    "Content-Type": "application/json",
    "Origin": "https://www.rainyun.com",
    "Referer": "https://www.rainyun.com/",
}

STORE = _MiniStore(COOKIE_STORE_FILE)


# ====== 账号加载 ======
def load_accounts() -> list[dict]:
    accounts: list[dict] = []
    if ACCOUNTS_FILE.exists():
        txt = ACCOUNTS_FILE.read_text(encoding="utf-8")
        for line in txt.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            e, p = line.split(":", 1)
            accounts.append({"email": e.strip(), "password": p.strip()})
    if accounts:
        return accounts
    env = os.environ.get("RAINYUN_ACCOUNTS", "").strip()
    if env:
        for l in env.splitlines():
            l = l.strip()
            if ":" in l:
                e, p = l.split(":", 1)
                accounts.append({"email": e.strip(), "password": p.strip()})
    if not accounts:
        print(f"❌ 找不到 {ACCOUNTS_FILE}")
        sys.exit(1)
    return accounts


# ====== 登录拿 cookie + csrf ======
def login_get_cookie(email: str, password: str) -> tuple[str | None, str | None]:
    """返回 (cookie_string, csrf_token). 失败 (None, None)."""
    body = json.dumps({"field": email, "password": password}).encode("utf-8")
    req = urllib.request.Request(
        BASE + "/user/login",
        data=body,
        headers=DEFAULT_LOGIN_HEADERS,
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=20)
        sc_raw = resp.headers.get_all("Set-Cookie") or []
        text = resp.read().decode("utf-8", "ignore")
        code = json.loads(text).get("code")
        if code != 200:
            return None, None
    except urllib.error.HTTPError:
        return None, None
    except Exception:
        return None, None
    pairs = []
    csrf = None
    seen_session = False
    for sc in sc_raw:
        kv = sc.split(";", 1)[0].strip()
        if not kv or "=" not in kv:
            continue
        k, v = kv.split("=", 1)
        if k == "X-CSRF-Token":
            csrf = v
        elif k == "rain-session":
            if seen_session:
                continue
            seen_session = True
        pairs.append(f"{k}={v}")
    return ("; ".join(pairs), csrf)


# ====== 签到请求 ======
def sign_with_cookie(cookie_str: str, csrf: str, vticket: str = "", vrandstr: str = "") -> dict:
    payload = {
        "task_name": "每日签到",
        "verifyCode": "",
        "vticket": vticket,
        "vrandstr": vrandstr,
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {**DEFAULT_SIGN_HEADERS, "Cookie": cookie_str, "x-csrf-token": csrf}
    req = urllib.request.Request(
        BASE + "/user/reward/tasks",
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=20)
        return {"status": resp.status, "body": resp.read().decode("utf-8", "ignore")}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "body": e.read().decode("utf-8", "ignore")}
    except Exception as e:
        return {"status": 0, "body": f"{type(e).__name__}: {e}"}


def list_tasks(cookie_str: str, csrf: str) -> list[dict]:
    headers = {**DEFAULT_SIGN_HEADERS, "Cookie": cookie_str, "x-csrf-token": csrf}
    req = urllib.request.Request(BASE + "/user/reward/tasks", headers=headers, method="GET")
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return json.loads(resp.read().decode("utf-8", "ignore")).get("data", [])
    except Exception:
        return []


def get_user_info(cookie_str: str, csrf: str) -> dict | None:
    headers = {**DEFAULT_SIGN_HEADERS, "Cookie": cookie_str, "x-csrf-token": csrf}
    req = urllib.request.Request(BASE + "/user/", headers=headers, method="GET")
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        text = resp.read().decode("utf-8", "ignore")
        return json.loads(text).get("data")
    except Exception:
        return None


# ====== Captcha 接入 ======
def get_ticket(use_ddddocr: bool = False, use_playwright: bool = False) -> tuple[str, str, str]:
    """返回 (vticket, vrandstr, method). 默认走第三方, 失败 → playwright+ddddocr(需远程 CDP)."""
    try:
        from tcaptcha_solver import solve_smart
    except Exception as e:
        print(f"⚠ 无法加载 tcaptcha_solver: {e}")
        return "", "", "fail"
    r = solve_smart(use_ddddocr=use_ddddocr, use_playwright=use_playwright)
    if r.ok:
        return r.vticket, r.vrandstr, r.method
    print(f"⚠ captcha 失败: {r.msg}")
    return "", "", "fail"


def cookie_for(email: str, override: str | None) -> str | None:
    if override:
        return override
    e = STORE.latest_active(email)
    return e.cookie if e else None


def csrf_for(cookie_str: str) -> str:
    m = re.search(r"X-CSRF-Token=([^;]+)", cookie_str or "")
    return m.group(1) if m else ""


# ====== Sign 主流程 ======
def sign_one_account(acc: dict, *, vticket: str = "", vrandstr: str = "",
                     no_captcha: bool = False, override_cookie: str | None = None) -> dict:
    """单账号端到端: cookie → user info → tasks → (可签) → captcha → sign.
    返回 dict 含 ok / msg / method / points_after.
    """
    email = acc["email"]
    cookie = cookie_for(email, override_cookie)
    if not cookie:
        return {"email": email, "ok": False, "msg": "no-active-cookie", "method": "-"}
    csrf = csrf_for(cookie)

    info = get_user_info(cookie, csrf)
    if not info:
        STORE.mark_expired(cookie)
        return {"email": email, "ok": False, "msg": "user-info-401 (cookie expired)", "method": "-"}
    name = info.get("Name", "?")
    points_before = info.get("Points", 0)
    print(f"[{email}] {name} 当前积分={points_before}")

    tasks = list_tasks(cookie, csrf)
    sign_task = next((t for t in tasks if t.get("Name") == "每日签到"), None)
    if not sign_task:
        return {"email": email, "ok": False, "msg": "no-每日签到-task", "method": "-"}
    status = sign_task.get("Status")
    if status == 2:
        return {"email": email, "ok": True, "msg": f"今日已签过 (Status=2) 积分={points_before}", "method": "skip"}
    if status != 1:
        return {"email": email, "ok": False, "msg": f"任务状态 Status={status} (不可领取)", "method": "-"}

    if no_captcha:
        return {"email": email, "ok": False, "msg": "no-captcha mode (调试, 跳过签到)", "method": "skip"}

    if not vticket or not vrandstr:
        print(f"[{email}] 调 captcha solver ...")
        vticket, vrandstr, method = get_ticket()
    else:
        method = "manual"
    if not vticket or not vrandstr:
        return {"email": email, "ok": False, "msg": "captcha-fail", "method": method or "-"}

    print(f"[{email}] 提交签到 (captcha method={method}) ...")
    r = sign_with_cookie(cookie, csrf, vticket, vrandstr)
    body = r.get("body") or ""
    ok = '"code":200' in body or '"code": 200' in body
    msg = ""
    try:
        j = json.loads(body)
        msg = j.get("message") or j.get("msg") or ""
    except Exception:
        msg = body[:200]
    if ok:
        STORE.mark_used(cookie)
        info_after = get_user_info(cookie, csrf) or {}
        points_after = info_after.get("Points", points_before)
        return {"email": email, "ok": True, "msg": f"签到成功 {msg or ''} 积分 {points_before}→{points_after}",
                "method": method, "points_after": points_after}
    # 失败
    if "10004" in body:
        STORE.mark_expired(cookie)
    return {"email": email, "ok": False, "msg": f"签到失败 status={r.get('status')} body={body[:200]}",
            "method": method}


def cookie_signin_mode(accounts: list[dict], override_cookie: str | None = None) -> dict:
    """默认 cookie 模式: 只跑已有 active cookie 试签 (不带 captcha, 仅校验 cookie 还活着)."""
    ok = 0
    fail = 0
    for acc in accounts:
        email = acc["email"]
        cookie = cookie_for(email, override_cookie)
        if not cookie:
            print(f"⚠ {email} 无 active cookie")
            fail += 1
            continue
        csrf = csrf_for(cookie)
        info = get_user_info(cookie, csrf)
        if not info:
            STORE.mark_expired(cookie)
            print(f"❌ {email} cookie 已失效")
            fail += 1
            continue
        STORE.mark_used(cookie)
        print(f"✅ {email} {info.get('Name')} 积分={info.get('Points')}")
        ok += 1
    return {"ok": ok, "fail": fail}


# ====== 入口 ======
def parse_args():
    p = argparse.ArgumentParser(description="雨云 多账号签到")
    p.add_argument("--mode", choices=["cookie", "login", "info", "tasks", "sign", "captcha"],
                   default="cookie", help="cookie=校验/刷新 active cookie; login=账密拿 cookie; info/tasks=查询; sign=端到端签到; captcha=单跑验证码")
    p.add_argument("--vticket", default="", help="人工 TCaptcha ticket (sign 模式)")
    p.add_argument("--vrandstr", default="", help="人工 TCaptcha randstr (sign 模式)")
    p.add_argument("--no-captcha", action="store_true", help="sign 模式跳过 captcha (调试, 只查到任务列表)")
    p.add_argument("--api-key", default="", help="雨云用户 APIKey (X-Api-Key 模式)")
    p.add_argument("--account", default=None, help="仅跑指定 email")
    p.add_argument("--cookie", default=None, help="临时 cookie 串 (不入库)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    accounts = load_accounts()
    if args.account:
        accounts = [a for a in accounts if a["email"].lower() == args.account.lower()]
        if not accounts:
            print(f"❌ 账号 {args.account} 不在 {ACCOUNTS_FILE.name}")
            return 1

    if args.mode == "info":
        for acc in accounts:
            ck = args.cookie or (STORE.latest_active(acc["email"]).cookie if STORE.latest_active(acc["email"]) else None)
            if not ck:
                print(f"{acc['email']}: no cookie")
                continue
            csrf = csrf_for(ck)
            info = get_user_info(ck, csrf)
            print(json.dumps(info, ensure_ascii=False, indent=2) if info else "fail")
        return 0

    if args.mode == "tasks":
        for acc in accounts:
            ck = args.cookie or (STORE.latest_active(acc["email"]).cookie if STORE.latest_active(acc["email"]) else None)
            if not ck:
                print(f"{acc['email']}: no cookie")
                continue
            csrf = csrf_for(ck)
            for t in list_tasks(ck, csrf):
                print(f"  [{t.get('Status')}] {t.get('Name')} (+{t.get('Points')})")
        return 0

    if args.mode == "login":
        for acc in accounts:
            ck, csrf = login_get_cookie(acc["email"], acc["password"])
            if not ck:
                print(f"❌ {acc['email']} 登录失败")
                continue
            STORE.upsert(acc["email"], ck, status="active")
            print(f"✅ {acc['email']} cookie 已入 store (csrf={csrf[:8]}...)")
            info = get_user_info(ck, csrf)
            if info:
                print(f"   用户={info.get('Name')} 积分={info.get('Points')}")
            print(f"   → 跑 --mode sign 自动完成签到 (captcha 自动解)")
        return 0

    if args.mode == "captcha":
        ticket, randstr, method = get_ticket()
        if ticket and randstr:
            print(f"✅ captcha ok (method={method})")
            print(f"   vticket={ticket[:40]}...")
            print(f"   vrandstr={randstr[:40]}...")
            return 0
        print("❌ captcha 失败")
        return 1

    if args.mode == "sign":
        ok = 0
        fail = 0
        for acc in accounts:
            print(f"\n=== {acc['email']} ===")
            r = sign_one_account(acc, vticket=args.vticket, vrandstr=args.vrandstr,
                                 no_captcha=args.no_captcha, override_cookie=args.cookie)
            tag = "✅" if r["ok"] else "❌"
            print(f"{tag} {r['email']}: {r['msg']}")
            if r["ok"]:
                ok += 1
            else:
                fail += 1
            if len(accounts) > 1:
                time.sleep(2)
        print(f"\n=== 汇总 ===")
        print(f"✅ 成功 {ok} / ❌ 失败 {fail}")
        return 0 if fail == 0 else 1

    # cookie 模式 (默认)
    actives_total = sum(len(STORE.actives_for(a["email"])) for a in accounts)
    print(f"📦 cookie store active 数: {actives_total}")
    res = cookie_signin_mode(accounts, override_cookie=args.cookie)
    print(f"\n=== 汇总 ===")
    print(f"✅ 成功 {res['ok']} / ❌ 失败 {res['fail']}")
    return 0 if res["fail"] == 0 else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())