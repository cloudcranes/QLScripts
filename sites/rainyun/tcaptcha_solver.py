#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""腾讯点选 TCaptcha 求解器 (雨云 /user/reward/tasks 用).

策略 (solve_smart 顺序):
  1) 第三方 API txdx.wxtool.de5.net (xlh001/Qd 同款, 35+ GitHub 仓库标配)
  2) Playwright + ddddocr.real 真点击 (第三方挂时降级)

依赖: pip install ddddocr opencv-python-headless playwright
      playwright install chromium
"""
from __future__ import annotations

import io
import json
import re
import time
from typing import Tuple

import httpx

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
CAPTCHA_AID = "2039519451"


def _cookie_dict(cookie: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in cookie.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def solve_via_thirdparty(cookie: str) -> Tuple[str, str]:
    """调第三方 wxtool 接口. 返回 (vticket, vrandstr), 失败 ('', '')."""
    url = f"https://txdx.wxtool.de5.net/aaug.qvv?aid={CAPTCHA_AID}&cookie={cookie}"
    try:
        r = httpx.get(
            url,
            headers={"User-Agent": USER_AGENT, "Referer": "https://www.rainyun.com/"},
            timeout=20.0,
        )
        if r.status_code != 200:
            return "", ""
        try:
            data = r.json()
        except Exception:
            return "", ""
        ticket = data.get("data", {}).get("vticket") or data.get("vticket") or ""
        randstr = data.get("data", {}).get("vrandstr") or data.get("vrandstr") or ""
        return ticket, randstr
    except Exception:
        return "", ""


def solve_via_playwright(cookie: str) -> Tuple[str, str]:
    """headless chromium + ddddocr 真点选. 兜底."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return "", ""
    try:
        import ddddocr
    except Exception:
        return "", ""

    cookies = _cookie_dict(cookie)
    det = ddddocr.Det(show=False)
    rec = ddddocr.Rec(show=False)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
        )
        if cookies:
            ctx.add_cookies([{
                "name": k,
                "value": v,
                "domain": ".rainyun.com",
                "path": "/",
            } for k, v in cookies.items()])
        page = ctx.new_page()
        page.goto("https://www.rainyun.com/", wait_until="domcontentloaded", timeout=20000)
        try:
            page.wait_for_selector("#aliyunCaptcha-sliding-slider", timeout=10000)
        except Exception:
            browser.close()
            return "", ""

        # 拿背景图 + sprite 图
        try:
            bg_url = page.evaluate(
                "() => document.querySelector('#slideBg')?.style.backgroundImage"
            )
            sprite_url = page.evaluate(
                "() => document.querySelector('#instruction img')?.src"
            )
        except Exception:
            browser.close()
            return "", ""
        if not bg_url or not sprite_url:
            browser.close()
            return "", ""
        m = re.search(r'url\(["\']?(.*?)["\']?\)', bg_url)
        if m:
            bg_url = m.group(1)
        bg_bytes = io.BytesIO(httpx.get(bg_url, timeout=15.0).content).read()
        sprite_bytes = io.BytesIO(httpx.get(sprite_url, timeout=15.0).content).read()

        bboxes = det.detection(bg_bytes) or []
        if not bboxes:
            browser.close()
            return "", ""

        # 拆 sprite 三片
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(sprite_bytes))
            w, h = img.size
            sprites = [img.crop((w // 3 * i, 0, w // 3 * (i + 1), h)) for i in range(3)]
        except Exception:
            browser.close()
            return "", ""

        result: dict[str, str] = {}
        for i, (x1, y1, x2, y2) in enumerate(bboxes):
            box = bg_bytes[y1:y2, x1:x2] if hasattr(bg_bytes, "__getitem__") else None
            for j in range(3):
                sim = ddddocr_rec_similarity(rec, sprites[j], box)
                key_sim = f"sprite_{j+1}.similarity"
                key_pos = f"sprite_{j+1}.position"
                if sim > float(result.get(key_sim, 0)):
                    result[key_sim] = str(sim)
                    result[key_pos] = f"{int((x1+x2)/2)},{int((y1+y2)/2)}"

        positions = [result.get(f"sprite_{i+1}.position") for i in range(3)]
        if len(set(positions)) != 3:
            browser.close()
            return "", ""

        slider = page.locator("#aliyunCaptcha-sliding-slider")
        box = slider.bounding_box()
        if not box:
            browser.close()
            return "", ""
        sx = box["x"] + box["width"] / 2
        sy = box["y"] + box["height"] / 2
        page.mouse.move(sx, sy)
        page.mouse.down()

        # 把 3 个位置转换为相对 slider 的 offset
        for pos in positions:
            x, y = map(int, pos.split(","))
            tx = sx + x  # bg 原图 ≈ display 像素 (近似)
            ty = sy + y
            page.mouse.move(tx, ty, steps=20)
            time.sleep(0.3)
        page.mouse.up()
        time.sleep(2)

        ticket = page.evaluate("() => window.__tcaptcha_ticket || ''")
        randstr = page.evaluate("() => window.__tcaptcha_randstr || ''")
        browser.close()
        return ticket, randstr
    except Exception:
        return "", ""


def ddddocr_rec_similarity(rec, sprite_img, box_img) -> float:
    """用 ddddocr OCR 比对两图 (精灵 vs 缺口); 返回 0~1."""
    try:
        import numpy as np
        from PIL import Image
        if isinstance(sprite_img, Image.Image):
            a = np.array(sprite_img.convert("L"))
        else:
            a = np.array(Image.open(io.BytesIO(sprite_img)).convert("L"))
        if isinstance(box_img, Image.Image):
            b = np.array(box_img.convert("L"))
        elif hasattr(box_img, "shape"):
            b = np.array(Image.fromarray(box_img).convert("L"))
        else:
            b = np.array(Image.open(io.BytesIO(box_img)).convert("L"))
        if a.shape != b.shape:
            return 0.0
        diff = np.abs(a.astype(int) - b.astype(int)).mean()
        return max(0.0, 1.0 - diff / 255.0)
    except Exception:
        return 0.0


def solve_smart(cookie: str) -> Tuple[str, str]:
    """智能降级: 第三方 → playwright."""
    t, r = solve_via_thirdparty(cookie)
    if t and r:
        return t, r
    return solve_via_playwright(cookie)


if __name__ == "__main__":
    import sys
    cookie = sys.argv[1] if len(sys.argv) > 1 else ""
    if not cookie:
        print("usage: python tcaptcha_solver.py '<cookie>'")
        sys.exit(1)
    t, r = solve_smart(cookie)
    print(f"ticket: {t}")
    print(f"randstr: {r}")