#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cron: 35 8 * * *
new Env('IKUUU_ACCOUNTS'): email1:password1\\nemail2:password2
new Env('IKUUU_COOKIE'): (可选) PHPSESSID=...; uid=...; key=...; email=...; expire_in=... (单账号 fallback)
new Env('IKUUU_BROWSER_HOST'): (login 模式) 远程浏览器 host (默认 192.168.1.107:9222)
iKuuu VPN 多账号签到 — 青龙面板原生适配

混合策略 (默认 cookie-only):
  1) 优先 IKUUU_ACCOUNTS 环境变量 (青龙推荐); 本地调试 fallback 读 ikuuu_accounts.txt
  2) cookie 存储 (ikuuu_cookies.jsonl) 复用每账号最新 active, 走 /user/checkin
  3) cookie 失效 (响应非 JSON / ret 错误) → 标记 expired, 自动账密登录补一条
  4) --mode login 强制账密模式 (远程浏览器 + 极验)

依赖:
  pip install httpx playwright-stealth faker   (仅 login 模式)

青龙用法:
  拉脚本到 /ql/scripts/ikuuu.py → 面板配置 cron + IKUUU_ACCOUNTS 环境变量即可
  本地调试:
  export IKUUU_ACCOUNTS=email1:pass1
  python ikuuu.py
"""
import argparse
import asyncio
import json
import os
import random
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
            for line in self.path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    o = __import__("json").loads(line)
                    self._cache.append(_CkEntry(
                        email=o.get("email", ""),
                        cookie=o.get("cookie", ""),
                        status=o.get("status", "active"),
                        expire_at=int(o.get("expire_at", 0) or 0),
                        last_used=float(o.get("last_used", 0) or 0),
                    ))
                except Exception:
                    pass
        self._loaded = True

    def _flush(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            for e in self._cache:
                f.write(__import__("json").dumps({
                    "email": e.email, "cookie": e.cookie, "status": e.status,
                    "expire_at": e.expire_at, "last_used": e.last_used,
                }, ensure_ascii=False) + "\n")

    def _ck_signature(self, cookie: str) -> str:
        m = re.search(r"PHPSESSID=([^;]+)", cookie)
        return m.group(1) if m else cookie[:80]

    def migrate_from_legacy(self, legacy_path: Path) -> int:
        import re as _re
        if not legacy_path.exists():
            return 0
        self._ensure()
        existing_sigs = {self._ck_signature(e.cookie) for e in self._cache}
        added = 0
        for line in legacy_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            sig = self._ck_signature(line)
            if sig in existing_sigs:
                continue
            m = _re.search(r"email=([^;]+)", line)
            email = m.group(1).replace("%40", "@") if m else "legacy"
            self._cache.append(_CkEntry(email=email, cookie=line, status="active"))
            existing_sigs.add(sig)
            added += 1
        if added:
            self._flush()
        return added

    def actives_for(self, email: str) -> list[_CkEntry]:
        self._ensure()
        return [e for e in self._cache if e.email == email and e.status == "active"]

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


import re  # noqa: E402  (re used by _MiniStore)

STORE = _MiniStore(Path(__file__).with_name("ikuuu_cookies.jsonl"))
LEGACY_COOKIE_FILE_AT_TOP = Path(__file__).with_name("ikuuu_cookies.txt")
_migrated_top = STORE.migrate_from_legacy(LEGACY_COOKIE_FILE_AT_TOP)
if _migrated_top > 0:
    print(f"📦 从 {LEGACY_COOKIE_FILE_AT_TOP.name} 迁移 {_migrated_top} 条 cookie 到 store")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

BASE_DOMAINS = [
    "ikuuu.top", "ikuuu.one", "ikuuu.pw", "ikuuu.dev", "ikuuu.me",
    "ikuuu.fyi", "ikuuu.win", "ikuuu.eu", "ikuuu.uk", "ikuuu.nl",
    "ikuuu.de", "ikuuu.ch", "ikuuu.art", "ikuuu.boo", "ikuuu.ltd",
    "ikuuu.org", "ikuuu.live", "ikuuu.bar",
]
DEFAULT_BROWSER_HOST = "192.168.1.107"
DEFAULT_BROWSER_PORT = 9222

UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]
LOCALE_POOL = ["zh-CN", "zh-TW", "en-US", "en-GB"]
TZ_POOL = ["Asia/Shanghai", "Asia/Hong_Kong", "Asia/Tokyo", "Europe/London"]
VIEWPORTS = [(1280, 800), (1366, 768), (1440, 900), (1536, 864), (1920, 1080)]

ACCOUNTS_FILE = Path(__file__).with_name("ikuuu_accounts.txt")


def load_accounts() -> list[dict]:
    accounts: list[dict] = []
    if ACCOUNTS_FILE.exists():
        for line in ACCOUNTS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            e, p = line.split(":", 1)
            accounts.append({"email": e.strip(), "password": p.strip()})
    if accounts:
        return accounts
    env = os.environ.get("IKUUU_ACCOUNTS", "").strip()
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


def _urllib_checkin(cookie_str: str, timeout: int = 20) -> dict:
    headers = {
        "User-Agent": UA,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Cookie": cookie_str,
    }
    last_err = None
    for dom in BASE_DOMAINS:
        url = f"https://{dom}/user/checkin"
        req = urllib.request.Request(url, data=b"", headers={**headers, "Referer": f"https://{dom}/"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return {"status": resp.status, "body": resp.read().decode("utf-8", "ignore"), "domain": dom}
        except urllib.error.HTTPError as e:
            return {"status": e.code, "body": e.read().decode("utf-8", "ignore"), "domain": dom}
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            continue
    return {"status": 0, "body": last_err or "all-domain-fail", "domain": "-"}


def _httpx_checkin(cookie_str: str, timeout: int = 20) -> dict:
    try:
        import httpx
    except Exception:
        return _urllib_checkin(cookie_str, timeout)
    last_err = None
    for dom in BASE_DOMAINS:
        try:
            with httpx.Client(
                timeout=httpx.Timeout(float(timeout), connect=8.0),
                headers={
                    "User-Agent": UA,
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": f"https://{dom}/",
                    "Cookie": cookie_str,
                },
            ) as client:
                resp = client.post(f"https://{dom}/user/checkin")
            return {"status": resp.status_code, "body": resp.text, "domain": dom}
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            continue
    return {"status": 0, "body": last_err or "all-domain-fail", "domain": "-"}


async def httpx_async_checkin(cookie_str: str) -> dict:
    try:
        import httpx
    except Exception:
        return _urllib_checkin(cookie_str)
    last_err = None
    for dom in BASE_DOMAINS:
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(15.0, connect=8.0),
                headers={
                    "User-Agent": UA,
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": f"https://{dom}/",
                    "Cookie": cookie_str,
                },
            ) as client:
                resp = await client.post(f"https://{dom}/user/checkin")
            return {"status": resp.status_code, "body": resp.text, "domain": dom}
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            continue
    return {"status": 0, "body": last_err or "all-domain-fail", "domain": "-"}


def _is_signin_ok(body: str) -> tuple[bool, str]:
    body = (body or "").lstrip()
    if not body.startswith("{"):
        return False, body[:120]
    try:
        data = json.loads(body)
    except Exception:
        return False, body[:120]
    ret = data.get("ret")
    msg = data.get("msg", "")
    traffic = data.get("traffic") or data.get("trafficInfo") or ""
    return ret in (0, 1), f"ret={ret} {msg} {traffic}".strip()


async def cookie_signin(accounts: list[dict], one_cookie: str | None = None) -> dict:
    targets = []
    for acc in accounts:
        email = acc["email"]
        if one_cookie:
            cookie = one_cookie
        else:
            entry = STORE.latest_active(email)
            if entry is None:
                print(f"⚠ {email} 无 active cookie, 跳过")
                continue
            cookie = entry.cookie
        targets.append((email, cookie))
    if not targets:
        return {"ok": 0, "fail": 0, "details": []}
    results = await asyncio.gather(*[
        _signin_one(email, cookie) for email, cookie in targets
    ])
    ok = sum(1 for r in results if r["ok"])
    fail = len(results) - ok
    print(f"\n=== 汇总 ===")
    print(f"✅ 成功 {ok} / ❌ 失败 {fail}")
    for r in results:
        print(f"  {'✅' if r['ok'] else '❌'} {r['email']}: {r['msg']}")
    return {"ok": ok, "fail": fail, "details": results}


async def _signin_one(email: str, cookie: str) -> dict:
    r = await httpx_async_checkin(cookie)
    ok, msg = _is_signin_ok(r["body"])
    if ok:
        STORE.mark_used(cookie)
    else:
        STORE.mark_expired(cookie)
    return {"email": email, "ok": ok, "msg": msg or r["body"][:120], "domain": r["domain"]}


def make_profile(seed: int) -> dict:
    rng = random.Random(seed)
    return {
        "ua": rng.choice(UA_POOL),
        "viewport": rng.choice(VIEWPORTS),
        "locale": rng.choice(LOCALE_POOL),
        "tz": rng.choice(TZ_POOL),
    }


async def connect_remote_browser(host: str, port: int):
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp(f"http://{host}:{port}")
    return pw, browser


async def login_and_signin_one(account: dict, profile: dict, host: str, port: int) -> tuple[bool, str]:
    from playwright_stealth import Stealth
    email, pwd = account["email"], account["password"]
    print(f"[{email}] 连远程浏览器 {host}:{port} (TZ={profile['tz']})")
    pw, browser = await connect_remote_browser(host, port)
    try:
        ctx = await browser.new_context(
            viewport={"width": profile["viewport"][0], "height": profile["viewport"][1]},
            user_agent=profile["ua"],
            locale=profile["locale"],
            timezone_id=profile["tz"],
        )
        await Stealth().apply_stealth_async(ctx)
        page = await ctx.new_page()
        try:
            login_url = None
            for dom in BASE_DOMAINS:
                url = f"https://{dom}/auth/login"
                try:
                    resp = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    if resp and resp.status == 200:
                        login_url = url
                        break
                except Exception:
                    continue
            if not login_url:
                return False, "no-domain"
            await page.fill('#email', email, timeout=10000)
            await page.fill('#password', pwd, timeout=10000)
            await page.wait_for_timeout(1500)
            try:
                await page.locator('.geetest_tip').first.click(force=True, timeout=5000)
            except Exception:
                pass
            ready = False
            for i in range(30):
                await page.wait_for_timeout(2000)
                ready = await page.evaluate(
                    "() => !!(window.Captcha && window.Captcha.isReady && window.Captcha.isReady())"
                )
                if ready:
                    print(f"[{email}] 极验通过 ({(i+1)*2}s)")
                    break
            if not ready:
                return False, "captcha-timeout"
            await page.click('button.login', timeout=5000)
            logged = False
            for i in range(20):
                await page.wait_for_timeout(1000)
                if "/auth/login" not in page.url and "/user" in page.url:
                    logged = True
                    break
                if i == 8:
                    try:
                        await page.click('button.login', timeout=2000)
                    except Exception:
                        pass
            if not logged:
                return False, "login-fail"
            cookies = await ctx.cookies()
            parts = []
            for c in cookies:
                v = c.get("value")
                if v:
                    parts.append(f"{c['name']}={v}")
            cookie_str = "; ".join(parts)
            if cookie_str:
                STORE.upsert(email, cookie_str, status="active")
                print(f"[{email}] cookie 已入 store")
            ok = False
            last_msg = ""
            for dom in BASE_DOMAINS:
                try:
                    rp = await ctx.new_page()
                    resp = await rp.request.post(
                        f"https://{dom}/user/checkin",
                        headers={"X-Requested-With": "XMLHttpRequest"},
                    )
                    body = await resp.text()
                    await rp.close()
                    if body.lstrip().startswith("{"):
                        data = json.loads(body)
                        msg = data.get("msg", "")
                        last_msg = f"[{dom}] ret={data.get('ret')} msg={msg}"
                        if data.get("ret") in (0, 1):
                            ok = True
                            break
                except Exception:
                    continue
            await ctx.close()
            return ok, last_msg or "all-domain-fail"
        except Exception as e:
            return False, f"exception:{type(e).__name__}: {e}"
    finally:
        try:
            await pw.stop()
        except Exception:
            pass


async def login_mode(accounts: list[dict], host: str, port: int) -> dict:
    seed = int(time.time())
    print(f"账号数: {len(accounts)}, 远程浏览器: {host}:{port}, 轮换种子: {seed}")
    order = list(enumerate(accounts))
    rng = random.Random(seed)
    rng.shuffle(order)
    ok_count = 0
    for idx, (orig_idx, acc) in enumerate(order, 1):
        email = acc["email"]
        print(f"\n=== [{idx}/{len(order)}] {email} ===")
        base_seed = seed + orig_idx * 7919
        for attempt in range(2):
            profile = make_profile(base_seed + attempt * 1009 + hash(email) % 1000)
            ok, msg = await login_and_signin_one(acc, profile, host, port)
            print(f"[{email}] {msg}")
            if ok:
                ok_count += 1
                break
            if "captcha-timeout" in msg:
                print(f"[{email}] 第{attempt+1}次 captcha-timeout, 换指纹重试...")
                await asyncio.sleep(random.uniform(5, 15))
                continue
            break
        else:
            print(f"[{email}] 重试耗尽")
        if idx < len(order):
            await asyncio.sleep(random.uniform(20, 60))
    print(f"\n=== 汇总 ===\n✅ 成功 {ok_count} / ❌ 失败 {len(accounts) - ok_count}")
    return {"ok": ok_count, "fail": len(accounts) - ok_count}


def parse_args():
    p = argparse.ArgumentParser(description="iKuuu 多账号签到")
    p.add_argument("--mode", choices=["cookie", "login"], default="cookie",
                   help="cookie = 用本地 cookie 签到 (默认); login = 强制账密登录")
    p.add_argument("--host", default=DEFAULT_BROWSER_HOST, help="远程 Chrome 地址 (login 模式)")
    p.add_argument("--port", type=int, default=DEFAULT_BROWSER_PORT, help="远程 Chrome 端口 (login 模式)")
    p.add_argument("--account", default=None, help="仅跑指定账号 email")
    p.add_argument("--cookie", default=None, help="用临时 cookie (不入库) 跑一次签到")
    p.add_argument("--no-notify", action="store_true", help="静默模式 (青龙面板)")
    p.add_argument("--shuffle-seed", type=int, default=None, help="随机种子")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    accounts = load_accounts()
    if args.account:
        accounts = [a for a in accounts if a["email"] == args.account]
        if not accounts:
            print(f"❌ 账号 {args.account} 不在 ikuuu_accounts.txt")
            return 1
    if not args.no_notify:
        print(f"📋 账号数 {len(accounts)}, mode={args.mode}")
    if args.mode == "login":
        ok = asyncio.run(login_mode(accounts, args.host, args.port))
        return 0 if ok["fail"] == 0 else 1
    if not args.no_notify:
        actives_total = sum(len(STORE.actives_for(a["email"])) for a in accounts)
        print(f"📦 cookie store active 数: {actives_total}")
    result = asyncio.run(cookie_signin(accounts, one_cookie=args.cookie or os.environ.get("IKUUU_COOKIE")))
    return 0 if result["fail"] == 0 else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())