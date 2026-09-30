#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JMComic 多账号签到 — 青龙面板原生适配

cron: 25 8 * * *
new Env('JMCOMIC_ACCOUNTS'): username1:password1\\nusername2:password2
new Env('JMCOMIC_FLARESOLVERR_URL'): (可选) http://127.0.0.1:8191 (过 CF challenge)
new Env('JMCOMIC_PUBLISH_PROXY'): (可选) http://127.0.0.1:7890 (让发布页可达)
new Env('JMCOMIC_CONCURRENCY'): (可选) 并发数 (默认 2)
new Env('JMCOMIC_DOMAIN_LIMIT'): (可选) 域名探测上限 (默认 5)

策略: 自动从 JM 发布页发现可用域名, 登录后调 /ajax/user_daily_sign + /ajax/ad_check.
遇 Cloudflare challenge 时优先 FlareSolverr, 无则用 curl_cffi 浏览器指纹 fallback.

依赖: pip install httpx curl_cffi

青龙用法:
  python sites/jmcomic/jmcomic_checkin.py
  本地调试:
  export JMCOMIC_ACCOUNTS=Alanmaster:xg363034
  python sites/jmcomic/jmcomic_checkin.py
"""
import argparse
import asyncio
import html
import json
import logging
import os
import random
import re
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

import httpx

try:
    from curl_cffi import requests as curl_requests
except Exception:
    curl_requests = None  # type: ignore[assignment]

APP_DIR = Path(__file__).resolve().parent
# 单脚本自洽: _pretty.py / ql_notify.py 与本文件同级, 不依赖外部 core/
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from _pretty import DOMAIN, START, WARN, account_line, kv, title
from ql_notify import dispatch_notify

logging.basicConfig(
    level=os.environ.get("JMCOMIC_LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("jmcomic")

DEFAULT_STATE_FILE = APP_DIR / "checkin_state.json"
DEFAULT_PUBLISH_URL = "https://jmcomicgo.xyz/"


@dataclass
class Account:
    username: str
    password: str

    @property
    def masked(self) -> str:
        if len(self.password) <= 2:
            return "*" * len(self.password)
        return self.password[0] + "*" * (len(self.password) - 2) + self.password[-1]


def load_accounts() -> list[Account]:
    env_accounts = os.environ.get("JMCOMIC_ACCOUNTS", "").strip()
    items: list[Account] = []
    if env_accounts:
        for line in env_accounts.splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            u, p = line.split(":", 1)
            items.append(Account(username=u.strip(), password=p.strip()))
    if not items:
        local = APP_DIR / "jmcomic_accounts.txt"
        if local.exists():
            for line in local.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or ":" not in line:
                    continue
                u, p = line.split(":", 1)
                items.append(Account(username=u.strip(), password=p.strip()))
    return items


def _user_agent() -> str:
    return os.environ.get(
        "JMCOMIC_USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    )


def _proxies(proxy: str) -> dict[str, str] | None:
    if not proxy:
        return None
    return {"http://": proxy, "https://": proxy}


async def fetch_publish_page(client: httpx.AsyncClient, url: str) -> str:
    """从发布页抓取最新可用 JM 域名."""
    try:
        r = await client.get(url, timeout=15.0, follow_redirects=True)
        r.raise_for_status()
        return r.text
    except Exception as e:
        logger.warning("%s 获取发布页失败: %s", WARN, e)
        return ""


def extract_domains(html: str) -> list[str]:
    """从发布页提取所有 https://*.something 链接 (过滤 js/css/图片)."""
    found = re.findall(r'https?://[a-zA-Z0-9.\-]+', html)
    out: list[str] = []
    seen: set[str] = set()
    skip_ext = (".js", ".css", ".png", ".jpg", ".svg", ".ico")
    for u in found:
        if any(u.lower().endswith(e) for e in skip_ext):
            continue
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


async def check_domain(client: httpx.AsyncClient, base: str) -> dict[str, Any]:
    """探测单个域名是否可用 + 拿 CSRF."""
    try:
        r = await client.get(base + "/", timeout=12.0, follow_redirects=True)
        if r.status_code != 200:
            return {"base": base, "ok": False}
        html = r.text
        m_csrf = re.search(r'name="csrf-token"\s+content="([^"]+)"', html)
        csrf = m_csrf.group(1) if m_csrf else ""
        m_csrf2 = re.search(r'window\._csrf\s*=\s*["\']([^"\']+)["\']', html)
        if not csrf and m_csrf2:
            csrf = m_csrf2.group(1)
        if not csrf:
            m_csrf3 = re.search(r'"csrf"\s*:\s*"([^"]+)"', html)
            csrf = m_csrf3.group(1) if m_csrf3 else ""
        return {"base": base, "ok": True, "csrf": csrf, "html_len": len(html)}
    except Exception as e:
        logger.debug("domain %s 探测失败: %s", base, e)
        return {"base": base, "ok": False}


async def discover_domains(max_n: int, proxy: str = "") -> list[str]:
    """从发布页 + 域名表探测可用域名."""
    publish_url = os.environ.get("JMCOMIC_PUBLISH_URL", DEFAULT_PUBLISH_URL)
    async with httpx.AsyncClient(
        headers={"User-Agent": _user_agent()},
        proxies=_proxies(proxy),
        timeout=15.0,
        follow_redirects=True,
    ) as client:
        html = await fetch_publish_page(client, publish_url)
    candidates = extract_domains(html)
    # 兜底: 已知常用域名
    fallbacks = [
        "https://18comic.vip", "https://jmcomic-zzz.one",
        "https://jmcomic-zzz.org", "https://jmcomictt.site",
    ]
    for fb in fallbacks:
        if fb not in candidates:
            candidates.append(fb)
    candidates = candidates[:max_n]
    out: list[str] = []
    async with httpx.AsyncClient(
        headers={"User-Agent": _user_agent()},
        proxies=_proxies(proxy),
        timeout=12.0,
    ) as client:
        for base in candidates:
            res = await check_domain(client, base)
            if res.get("ok"):
                out.append(base)
                if len(out) >= 4:
                    break
    return out


def _login_payload(username: str, password: str) -> dict[str, str]:
    return {"username": username, "password": password}


async def login_via_flaresolverr(url: str, username: str, password: str, flaresolverr: str) -> dict[str, Any]:
    """FlareSolverr 代理登录 (自动过 CF challenge)."""
    try:
        payload = {
            "cmd": "request.post",
            "url": url,
            "postData": urlencode(_login_payload(username, password)),
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "User-Agent": _user_agent(),
            },
        }
        r = await httpx.AsyncClient().post(
            f"{flaresolverr.rstrip('/')}/v1",
            json=payload,
            timeout=httpx.Timeout(60.0),
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"ok": False, "reason": f"flaresolverr failed: {e}"}


async def login_with_curl_cffi(base: str, username: str, password: str, proxy: str = "") -> dict[str, Any]:
    """curl_cffi 浏览器指纹登录 (FlareSolverr 不可用时 fallback)."""
    if curl_requests is None:
        return {"ok": False, "reason": "curl_cffi not installed"}
    try:
        proxies = {"http": proxy, "https": proxy} if proxy else None
        s = curl_requests.Session(
            impersonate="chrome120",
            proxies=proxies,
            timeout=30,
        )
        s.headers.update({"User-Agent": _user_agent(), "X-Requested-With": "XMLHttpRequest"})
        r = s.post(base + "/ajax/login", data=_login_payload(username, password))
        if r.status_code != 200:
            return {"ok": False, "reason": f"status={r.status_code}"}
        try:
            data = r.json()
        except Exception:
            return {"ok": False, "reason": f"non-json: {r.text[:120]}"}
        cookies = s.cookies
        cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
        return {"ok": data.get("status") == 1, "data": data, "cookies": cookie_str}
    except Exception as e:
        return {"ok": False, "reason": f"curl_cffi failed: {e}"}


async def login_with_httpx(
    client: httpx.AsyncClient, base: str, username: str, password: str
) -> dict[str, Any]:
    try:
        r = await client.post(
            base + "/ajax/login",
            data=_login_payload(username, password),
            headers={"X-Requested-With": "XMLHttpRequest"},
            timeout=15.0,
        )
        if r.status_code != 200:
            return {"ok": False, "reason": f"status={r.status_code}"}
        try:
            data = r.json()
        except Exception:
            return {"ok": False, "reason": f"non-json: {r.text[:120]}"}
        return {"ok": data.get("status") == 1, "data": data}
    except Exception as e:
        return {"ok": False, "reason": str(e)}


async def daily_sign(client: httpx.AsyncClient, base: str) -> dict[str, Any]:
    """GET /ajax/user_daily_sign."""
    try:
        r = await client.get(
            base + "/ajax/user_daily_sign",
            headers={"X-Requested-With": "XMLHttpRequest"},
            timeout=15.0,
        )
        return r.json() if r.status_code == 200 else {"status": 0, "msg": f"status={r.status_code}"}
    except Exception as e:
        return {"status": 0, "msg": str(e)}


async def ad_check(client: httpx.AsyncClient, base: str) -> dict[str, Any]:
    try:
        r = await client.get(
            base + "/ajax/ad_check",
            headers={"X-Requested-With": "XMLHttpRequest"},
            timeout=15.0,
        )
        return r.json() if r.status_code == 200 else {"status": 0, "msg": f"status={r.status_code}"}
    except Exception as e:
        return {"status": 0, "msg": str(e)}


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(path: Path, state: dict[str, Any]) -> None:
    try:
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning("save_state 失败: %s", e)


def already_checked_today(username: str, key: str, state: dict[str, Any]) -> bool:
    rec = state.get(username, {}).get(key)
    if not rec:
        return False
    try:
        d = datetime.fromisoformat(rec)
        return d.date() == datetime.now().date()
    except Exception:
        return False


def mark_checked(username: str, key: str, state: dict[str, Any]) -> None:
    state.setdefault(username, {})[key] = datetime.now().isoformat(timespec="seconds")


def build_summary(results: list[dict[str, Any]], domains: list[str]) -> str:
    ok = sum(1 for r in results if r.get("ok"))
    lines: list[str] = []
    lines.append(title("JMComic", ok, len(results)))
    lines.append(kv(DOMAIN, "发布页域名", ", ".join(domains) if domains else "-"))
    for i, r in enumerate(results, 1):
        lines.append(
            account_line(
                i,
                len(results),
                r.get("username", "?"),
                success=r.get("ok", False),
                skipped=r.get("skipped", False),
                domain=r.get("domain", "-"),
                detail=r.get("detail", "-"),
            )
        )
    return "\n".join(lines)


async def run_checkin(
    accounts: list[Account],
    state_file: Path,
    domain_limit: int,
    force: bool,
    flaresolverr_url: str,
    publish_proxy: str = "",
) -> int:
    if not accounts:
        logger.error("%s 未配置账号。请设置 JMCOMIC_ACCOUNTS", WARN)
        return 1
    domains = await discover_domains(max(1, domain_limit), proxy=publish_proxy)
    if not domains:
        logger.error("%s 未能从发布页获取 JM 域名", WARN)
        return 1
    state = load_state(state_file)
    results: list[dict[str, Any]] = []
    for acc in accounts:
        rec: dict[str, Any] = {"username": acc.username, "ok": False, "skipped": False, "detail": "-"}
        if not force and (already_checked_today(acc.username, "sign", state) or already_checked_today(acc.username, "ad", state)):
            rec["skipped"] = True
            rec["detail"] = "今日已签到，跳过重复执行"
            results.append(rec)
            logger.info("⏭ %s 今日已签过", acc.username)
            continue
        logged_in = False
        chosen_domain = domains[0]
        cookies_str = ""
        async with httpx.AsyncClient(
            headers={"User-Agent": _user_agent()},
            proxies=_proxies(publish_proxy),
            timeout=15.0,
            follow_redirects=True,
        ) as client:
            if flaresolverr_url:
                fs_resp = await login_via_flaresolverr(
                    chosen_domain + "/ajax/login", acc.username, acc.password, flaresolverr_url,
                )
                if fs_resp.get("ok") and fs_resp.get("solution", {}).get("cookies"):
                    cookies = "; ".join(
                        f"{c['name']}={c['value']}" for c in fs_resp["solution"]["cookies"]
                    )
                    cookies_str = cookies
                    logged_in = True
            if not logged_in:
                cb = await login_with_curl_cffi(
                    chosen_domain, acc.username, acc.password, publish_proxy,
                )
                if cb.get("ok") and cb.get("cookies"):
                    cookies_str = cb["cookies"]
                    logged_in = True
            if not logged_in:
                for dom in domains:
                    ht = await login_with_httpx(client, dom, acc.username, acc.password)
                    if ht.get("ok"):
                        chosen_domain = dom
                        # httpx 路径: cookies 通过 client 自动管理
                        logged_in = True
                        break
        if not logged_in:
            rec["detail"] = "登录失败"
            results.append(rec)
            continue
        # 跑签到
        async with httpx.AsyncClient(
            headers={
                "User-Agent": _user_agent(),
                "X-Requested-With": "XMLHttpRequest",
                "Cookie": cookies_str,
            },
            proxies=_proxies(publish_proxy),
            timeout=15.0,
        ) as c2:
            sign_resp = await daily_sign(c2, chosen_domain)
            ad_resp = await ad_check(c2, chosen_domain)
        rec["domain"] = chosen_domain
        sign_msg = sign_resp.get("msg", "") if isinstance(sign_resp, dict) else ""
        ad_msg = ad_resp.get("msg", "") if isinstance(ad_resp, dict) else ""
        rec["detail"] = f"sign={sign_msg!r} ad={ad_msg!r}"
        if (isinstance(sign_resp, dict) and sign_resp.get("status") == 1) or (isinstance(ad_resp, dict) and ad_resp.get("status") == 1):
            rec["ok"] = True
            mark_checked(acc.username, "sign", state)
            mark_checked(acc.username, "ad", state)
            save_state(state_file, state)
        results.append(rec)
    summary = build_summary(results, domains)
    logger.info("\n" + summary)
    try:
        await dispatch_notify("JMComic 签到结果", summary)
    except Exception as e:
        logger.debug("dispatch_notify error: %s", e)
    return 0 if all(r.get("ok") or r.get("skipped") for r in results) else 1


def resolve_path(s: str) -> Path:
    return Path(s) if s else DEFAULT_STATE_FILE


def amain() -> int:
    p = argparse.ArgumentParser(description="JMComic 多账号签到 (青龙面板)")
    p.add_argument("--once", action="store_true", help="只跑一次 (默认)")
    p.add_argument("--force", action="store_true", help="忽略今日已签到, 强制再跑")
    p.add_argument("--state-file", default="", help="签到状态持久化文件 (默认同目录 checkin_state.json)")
    p.add_argument("--domain-limit", type=int, default=int(os.environ.get("JMCOMIC_DOMAIN_LIMIT", "5")))
    return asyncio.run(
        run_checkin(
            accounts=load_accounts(),
            state_file=resolve_path(os.environ.get("JMCOMIC_STATE_FILE", "").strip() or ""),
            domain_limit=p.parse_args().domain_limit,
            force=p.parse_args().force,
            flaresolverr_url=os.environ.get("JMCOMIC_FLARESOLVERR_URL", "").strip(),
            publish_proxy=os.environ.get("JMCOMIC_PUBLISH_PROXY", "").strip(),
        )
    )


if __name__ == "__main__":
    raise SystemExit(amain())