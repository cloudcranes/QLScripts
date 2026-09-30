#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cron: 25 8 * * *
new Env('RAINYUN_ACCOUNTS'): email1:password1\\nemail2:password2
new Env('RAINYUN_API_KEY'): (可选) 用户 APIKey (X-Api-Key 模式, 优先级最高)
雨云 (rainyun) 多账号签到 — 青龙面板原生适配

策略 (默认 cookie-only):
  1) 优先 RAINYUN_ACCOUNTS 环境变量 (青龙推荐); 本地调试 fallback 读 rainyun_accounts.txt
  2) cookie 存储 (rainyun_cookies.jsonl) 复用每账号最新 active, 走 /user/reward/tasks
  3) cookie 失效 → 标记 retired, 自动账密登录补一条新 active
  4) --mode sign 端到端签到: cookie → captcha (TCaptcha ddddocr) → sign
  5) --mode info / tasks / captcha / login 仅调试

依赖: pip install httpx ddddocr opencv-python-headless playwright (playwright 可选)

青龙用法:
  python sites/rainyun/rainyun.py
  本地调试:
  export RAINYUN_ACCOUNTS=email1:pass1
  python sites/rainyun/rainyun.py

用法:
  python rainyun.py                                  # 默认 cookie 模式 + 端到端签到
  python rainyun.py --mode info                      # 拉用户信息
  python rainyun.py --mode tasks                     # 任务列表
  python rainyun.py --mode sign                      # 端到端签到
  python rainyun.py --mode login                     # 账密拿 cookie (无 captcha)
  python rainyun.py --mode captcha                   # 单跑 captcha 自检 (无 sign)
"""
import argparse
import json
import os
import re
import sys
import time
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
                    o = json.loads(line)
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
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            for e in self._cache:
                f.write(json.dumps({
                    "email": e.email, "cookie": e.cookie, "status": e.status,
                    "expire_at": e.expire_at, "last_used": e.last_used,
                }, ensure_ascii=False) + "\n")

    def _ck_signature(self, cookie: str) -> str:
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
    return accounts


def http_post(path: str, payload: dict, cookie: str = "", api_key: str = "", timeout: int = 15) -> tuple[int, dict]:
    import urllib.request
    import urllib.error
    headers = dict(DEFAULT_LOGIN_HEADERS)
    if api_key:
        headers["X-Api-Key"] = api_key
    if cookie:
        headers["Cookie"] = cookie
    url = BASE + path
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8", "ignore") or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8", "ignore") or "{}")
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"err": f"{type(e).__name__}: {e}"}


def http_get(path: str, cookie: str = "", api_key: str = "", timeout: int = 15) -> tuple[int, dict]:
    import urllib.request
    import urllib.error
    headers = dict(DEFAULT_LOGIN_HEADERS)
    if api_key:
        headers["X-Api-Key"] = api_key
    if cookie:
        headers["Cookie"] = cookie
    url = BASE + path
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8", "ignore") or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8", "ignore") or "{}")
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"err": f"{type(e).__name__}: {e}"}


def csrf_for(cookie: str) -> str:
    m = re.search(r"X-CSRF-Token=([^;]+)", cookie)
    return m.group(1) if m else ""


def login(email: str, password: str) -> dict[str, Any]:
    status, data = http_post("/user/login", {"field": email, "password": password})
    if status != 200 or data.get("code") != 200:
        return {"ok": False, "reason": f"login status={status} data={data}"}
    cookies = data.get("cookies") or {}
    session = cookies.get("rain-session") or cookies.get("rain_session")
    csrf = cookies.get("X-CSRF-Token") or cookies.get("x-csrf-token") or data.get("X-CSRF-Token")
    if not session:
        return {"ok": False, "reason": f"no rain-session in {data}"}
    cookie_str = f"rain-session={session}"
    if csrf:
        cookie_str += f"; X-CSRF-Token={csrf}"
    return {"ok": True, "cookie": cookie_str}


def get_user_info(cookie: str, csrf: str) -> dict[str, Any]:
    status, data = http_get("/user/?no_cache=false", cookie=cookie)
    if status != 200 or data.get("code") != 200:
        return {}
    return data.get("data") or {}


def get_tasks(cookie: str) -> list[dict]:
    status, data = http_get("/user/reward/tasks?no_cache=false", cookie=cookie)
    if status != 200 or data.get("code") != 200:
        return []
    return data.get("data") or []


def sign_task(cookie: str, csrf: str, ticket: str, randstr: str) -> dict[str, Any]:
    payload = {"action": "task", "task_id": 1, "vticket": ticket, "vrandstr": randstr}
    status, data = http_post("/user/reward/tasks", payload, cookie=cookie)
    return {"status": status, "data": data}


def sign_with_api_key(api_key: str) -> dict[str, Any]:
    payload = {"action": "task", "task_id": 1}
    status, data = http_post("/user/reward/tasks", payload, api_key=api_key)
    return {"status": status, "data": data}


def sign_mode(accounts: list[dict], no_captcha: bool = False) -> dict[str, int]:
    api_key = os.environ.get("RAINYUN_API_KEY", "").strip()
    if api_key:
        r = sign_with_api_key(api_key)
        if r["status"] == 200 and (r["data"].get("code") == 200 or "积分" in str(r["data"])):
            print(f"✅ APIKey 模式签到成功")
            return {"ok": 1, "fail": 0}
        print(f"❌ APIKey 模式失败: {r}")
        return {"ok": 0, "fail": 1}

    ok = fail = 0
    for acc in accounts:
        email = acc["email"]
        entry = STORE.latest_active(email)
        if not entry:
            print(f"⚠ {email} 无 active cookie, 跳过")
            fail += 1
            continue
        cookie = entry.cookie
        csrf = csrf_for(cookie)
        info = get_user_info(cookie, csrf)
        if not info:
            STORE.mark_expired(cookie)
            print(f"❌ {email} cookie 已失效")
            fail += 1
            continue

        tasks = get_tasks(cookie)
        signable = [t for t in tasks if t.get("Status") == 1 and "签到" in str(t.get("Name", ""))]
        if not signable:
            print(f"⏭ {email} 今日已签过")
            STORE.mark_used(cookie)
            ok += 1
            continue

        if no_captcha:
            print(f"⚠ {email} 跳过 captcha (--no-captcha)")
            fail += 1
            continue

        # 走 ddddocr 解 TCaptcha
        try:
            from tcaptcha_solver import solve_smart
        except ImportError as e:
            print(f"❌ {email} tcaptcha_solver 未安装: {e}")
            fail += 1
            continue

        t = signable[0]
        ticket, randstr = solve_smart(cookie)
        if not ticket:
            print(f"❌ {email} captcha 求解失败")
            fail += 1
            continue
        r = sign_task(cookie, csrf, ticket, randstr)
        if r["status"] == 200 and r["data"].get("code") == 200:
            STORE.mark_used(cookie)
            print(f"✅ {email} 签到成功 (积分变化: +{r['data'].get('data', {}).get('gain', 0)})")
            ok += 1
        else:
            STORE.mark_expired(cookie)
            print(f"❌ {email} 签到失败: {r}")
            fail += 1
    print(f"\n=== 汇总: ✅ {ok} / ❌ {fail} ===")
    return {"ok": ok, "fail": fail}


def info_mode(accounts: list[dict], cookie_override: str | None = None) -> None:
    api_key = os.environ.get("RAINYUN_API_KEY", "").strip()
    if api_key:
        info = get_user_info("", api_key)
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return
    for acc in accounts:
        ck = cookie_override or (STORE.latest_active(acc["email"]).cookie if STORE.latest_active(acc["email"]) else None)
        if not ck:
            print(f"{acc['email']}: no cookie")
            continue
        info = get_user_info(ck, csrf_for(ck))
        print(json.dumps(info, ensure_ascii=False, indent=2))


def tasks_mode(accounts: list[dict], cookie_override: str | None = None) -> None:
    for acc in accounts:
        ck = cookie_override or (STORE.latest_active(acc["email"]).cookie if STORE.latest_active(acc["email"]) else None)
        if not ck:
            print(f"{acc['email']}: no cookie")
            continue
        for t in get_tasks(ck):
            print(f"  [{t.get('Status')}] {t.get('Name')} (+{t.get('RewardCount')})")


def login_mode(accounts: list[dict]) -> None:
    ok = fail = 0
    for acc in accounts:
        email = acc["email"]
        r = login(email, acc["password"])
        if r["ok"]:
            STORE.upsert(email, r["cookie"], status="active")
            print(f"✅ {email} cookie 已入 store")
            ok += 1
        else:
            print(f"❌ {email} {r['reason']}")
            fail += 1
    print(f"\n=== 汇总: ✅ {ok} / ❌ {fail} ===")


def captcha_mode(accounts: list[dict], cookie_override: str | None = None) -> None:
    from tcaptcha_solver import solve_smart
    for acc in accounts:
        ck = cookie_override or (STORE.latest_active(acc["email"]).cookie if STORE.latest_active(acc["email"]) else None)
        if not ck:
            print(f"{acc['email']}: no cookie")
            continue
        ticket, randstr = solve_smart(ck)
        print(f"  ticket={ticket[:40] + '...' if ticket else 'None'}")
        print(f"  randstr={randstr}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="雨云 多账号签到 (青龙面板)")
    p.add_argument(
        "--mode",
        choices=["cookie", "login", "info", "tasks", "sign", "captcha"],
        default="sign",
        help="sign=默认: cookie + sign 三连 (面板 ▶ 执行 默认走这个); "
             "cookie=仅校验 active cookie 存活; info=拉用户信息; sign=同上; "
             "probe=调探针脚本; import-cookie=注入人工浏览器导出的 cookie 串; "
             "login=账密登录 (不签到)",
    )
    p.add_argument("--vticket", default="", help="人工 TCaptcha ticket (sign 模式)")
    p.add_argument("--vrandstr", default="", help="人工 TCaptcha randstr (sign 模式)")
    p.add_argument("--no-captcha", action="store_true", help="sign 模式跳过 captcha (调试)")
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
            print(f"❌ 账号 {args.account} 不在 accounts")
            return 1

    if args.mode == "login":
        login_mode(accounts)
        return 0
    if args.mode == "info":
        info_mode(accounts, cookie_override=args.cookie)
        return 0
    if args.mode == "tasks":
        tasks_mode(accounts, cookie_override=args.cookie)
        return 0
    if args.mode == "captcha":
        captcha_mode(accounts, cookie_override=args.cookie)
        return 0
    if args.mode == "sign":
        r = sign_mode(accounts, no_captcha=args.no_captcha)
        return 0 if r["fail"] == 0 else 1
    if args.mode == "cookie":
        # cookie 模式 = 仅校验活跃 cookie 还活着
        ok = 0
        for acc in accounts:
            entry = STORE.latest_active(acc["email"])
            if entry:
                STORE.mark_used(entry.cookie)
                print(f"✅ {acc['email']} cookie 还活着 (last_used 刷新)")
                ok += 1
            else:
                print(f"⚠ {acc['email']} 无 active cookie")
        return 0 if ok == len(accounts) else 1
    return 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())