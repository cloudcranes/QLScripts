"""雨云 TCaptcha (腾讯点选) 求解器 — 输入 (cookie, csrf), 输出 (vticket, vrandstr).

策略分层 (从可信到弱):
  1) 第三方打码服务 (txdx.wxtool.de5.net) — 参考 xlh001/Qd, 一行 GET 拿 ticket+randstr.
      无需 ddddocr, 无需浏览器, 默认走这条. 失败再降级.
  2) ddddocr 检测 + playwright headless 点击 — 当 1) 不可用时启动, 真自动打码.
      ddddocr.Det().detection(bg) 拿 3 个 bbox, 跟 sprite 拆 3 片 cv2 模板匹配拿顺序,
      playwright 进 iframe 依次点击 → submit. 拿 ticket.

为什么不全 HTTP 化: 腾讯 cap_union_new_verify 需要 TDC (collect/eks) + POW (md5 collision),
跑 env.js + tdc.js 必须 MiniRacer/Playwright JS 上下文, 单纯 httpx 不可能.

依赖: ddddocr, opencv-python-headless, playwright (可选).
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# ====== 顶常量 ======
TCAPTCHA_AID = "2039519451"
THIRD_PARTY_URL = "https://txdx.wxtool.de5.net/solve_captcha"
APP_REFERER = "https://app.rainyun.com/"
SIM_THRESHOLD = 0.20  # 模板匹配阈值 (cv2 TM_CCOEFF_NORMED)
MAX_RETRY = 3
DdddOCR_DET = None  # 懒加载


# ====== 数据结构 ======
@dataclass
class SolveResult:
    ok: bool
    vticket: str = ""
    vrandstr: str = ""
    method: str = ""  # thirdparty / playwright / manual
    positions: list[tuple[int, int]] | None = None  # 检测出的点击坐标 (调试用)
    msg: str = ""


# ====== 第三方服务 (默认) ======
def solve_via_thirdparty(aid: str = TCAPTCHA_AID, timeout: int = 25) -> SolveResult:
    """GET https://txdx.wxtool.de5.net/solve_captcha?aid=...&type=1 → {ticket, randstr}.

    type=1 表示点选式 (RainYun 用).
    """
    url = f"{THIRD_PARTY_URL}?{urllib.parse.urlencode({'aid': aid, 'type': 1})}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": APP_REFERER,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "ignore")
    except Exception as e:
        return SolveResult(ok=False, method="thirdparty", msg=f"http-error: {e}")
    try:
        data = json.loads(body)
    except Exception as e:
        return SolveResult(ok=False, method="thirdparty", msg=f"json-error: {e} body={body[:200]}")
    inner = data.get("data") or {}
    ticket = inner.get("ticket") or data.get("ticket") or ""
    randstr = inner.get("randstr") or data.get("randstr") or ""
    if ticket and randstr:
        return SolveResult(ok=True, vticket=ticket, vrandstr=randstr, method="thirdparty",
                           msg=f"thirdparty ok ticket={ticket[:20]}...")
    return SolveResult(ok=False, method="thirdparty", msg=f"empty-result body={body[:200]}")


# ====== ddddocr 检测 + 模板匹配 (给 playwright 用) ======
def _ensure_ddddocr():
    """懒加载 ddddocr 检测器. 兼容 1.5+ API:
       1.5: ddddocr.Det()
       1.6+: ddddocr.DdddOcr(det=True, ocr=False, show_ad=False)
    """
    global DdddOCR_DET
    if DdddOCR_DET is None:
        import ddddocr  # noqa
        if hasattr(ddddocr, "Det"):
            DdddOCR_DET = ddddocr.Det()
        else:
            ocr = ddddocr.DdddOcr(det=True, ocr=False, show_ad=False)
            DdddOCR_DET = ocr
    return DdddOCR_DET


def detection(image_bytes: bytes) -> list[list[int]]:
    """薄包装: 不同 ddddocr 版本的 detection() 签名不同 (1.5: 返回 [[x1,y1,x2,y2],...];
    1.6+: ocr.detection() 也同形). 统一返回 bbox 列表."""
    det = _ensure_ddddocr()
    return det.detection(image_bytes)


def detect_positions(bg_bytes: bytes, sprite_bytes: bytes) -> list[tuple[int, int]]:
    """ddddocr 找 bg 上图案 bbox + cv2 跟 sprite 3 片匹配排顺序.
    返回 [(x,y), (x,y), (x,y)] 按 sprite 顺序 (左→右).
    """
    import cv2
    import numpy as np

    det = _ensure_ddddocr()
    bboxes = det.detection(bg_bytes)
    # 统一格式: 1.6+ 可能返回 dict 列表 [{box:[x1,y1,x2,y2]}]
    norm = []
    for b in bboxes or []:
        if isinstance(b, dict):
            norm.append(tuple(b["box"]))
        else:
            norm.append(tuple(b))
    bboxes = norm
    if not bboxes or len(bboxes) < 3:
        raise RuntimeError(f"ddddocr 仅检出 {len(bboxes) if bboxes else 0} 个图案 (需 ≥3)")

    bg_arr = np.frombuffer(bg_bytes, dtype=np.uint8)
    bg_img = cv2.imdecode(bg_arr, cv2.IMREAD_COLOR)
    sp_arr = np.frombuffer(sprite_bytes, dtype=np.uint8)
    sp_img = cv2.imdecode(sp_arr, cv2.IMREAD_COLOR)
    if bg_img is None or sp_img is None:
        raise RuntimeError("bg/sprite 解码失败 (cv2.imdecode 返 None)")

    # 拆 sprite 成 3 等宽片
    w = sp_img.shape[1]
    slices = []
    for i in range(3):
        s = sp_img[:, w // 3 * i: w // 3 * (i + 1)]
        slices.append(cv2.cvtColor(s, cv2.COLOR_BGR2GRAY))

    # 每个 bbox 截出来跟 3 个 sprite 算相似度
    best_for_sprite: dict[int, tuple[float, tuple[int, int]]] = {}
    for i, (x1, y1, x2, y2) in enumerate(bboxes[:3]):  # 取前 3 个
        roi = cv2.cvtColor(bg_img[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
        # 缩放到 sprite slice 尺寸便于比较
        if roi.shape != slices[0].shape:
            roi = cv2.resize(roi, (slices[0].shape[1], slices[0].shape[0]))
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        for j, ref in enumerate(slices):
            score = float(cv2.matchTemplate(roi, ref, cv2.TM_CCOEFF_NORMED).max())
            cur = best_for_sprite.get(j)
            if cur is None or score > cur[0]:
                best_for_sprite[j] = (score, (cx, cy))

    # 按 sprite 顺序 (0,1,2) 输出坐标, 任一低于阈值就报错
    positions = []
    for j in range(3):
        score, pos = best_for_sprite.get(j, (0.0, (0, 0)))
        if score < SIM_THRESHOLD:
            raise RuntimeError(f"sprite_{j+1} 匹配度 {score:.3f} < {SIM_THRESHOLD}")
        positions.append(pos)
    return positions


def randstr_from_positions(positions: list[tuple[int, int]]) -> str:
    """构造 'x1,y1|x2,y2|x3,y3'."""
    return "|".join(f"{x},{y}" for x, y in positions)


# ====== Playwright 远程 Chrome CDP (面板主机不装 chromium) ======
def solve_via_playwright(positions: list[tuple[int, int]] | None = None,
                        timeout_ms: int = 60_000) -> SolveResult:
    """连远程 chromium (CDP), 打开 rainyun 登录页, 触发 TCaptcha, 用 positions 点 3 下,
    从 TencentCaptcha callback 拿 ticket + randstr.

    positions 可为 None (这时函数会 ddddocr 自动从 iframe bg 检), 也可外部传入.

    Returns SolveResult.
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        return SolveResult(ok=False, method="playwright", msg=f"playwright-import-fail: {e}")

    # 必须配置远程 Chrome CDP, 面板主机不装 chromium
    cdp_url = os.getenv("RAINYUN_REMOTE_CHROME_CDP", "").strip()
    if not cdp_url:
        return SolveResult(ok=False, method="playwright", msg="missing RAINYUN_REMOTE_CHROME_CDP env")

    init_script = """
    window.__captchaResult = "";
    // 拦截 TencentCaptcha 实例化, 捕获 callback
    const _origDefine = Object.defineProperty;
    """

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(cdp_url)
            ctx_opts = dict(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                locale="zh-CN",
            )
            if browser.contexts:
                ctx = browser.contexts[0]
            else:
                ctx = browser.new_context(**ctx_opts)
            page = ctx.new_page()

            # 注入全局 hook: TencentCaptcha 实例化时绑 callback 到 window
            page.add_init_script("""
            (function(){
                window.__captchaResult = '';
                const checkInterval = setInterval(function(){
                    if (window.TencentCaptcha && !window.__hooked){
                        window.__hooked = true;
                        clearInterval(checkInterval);
                        // 钩子: 监听 SDK 内部的回调. SDK 暴露全局 TencentCaptcha 类,
                        // 实际回调是 SDK 内部 iframe.postMessage 给顶层. 我们劫持 postMessage.
                        const origPM = window.postMessage.bind(window);
                        window.postMessage = function(msg, target, ...rest){
                            try {
                                if (typeof msg === 'object' && msg && (msg.ticket || msg.randstr)){
                                    window.__captchaResult = JSON.stringify(msg);
                                } else if (typeof msg === 'string' && msg.indexOf('ticket') >= 0){
                                    window.__captchaResult = msg;
                                }
                            } catch(e){}
                            return origPM(msg, target, ...rest);
                        };
                        // 监听 message 事件 (主世界收到 iframe callback)
                        window.addEventListener('message', function(ev){
                            try {
                                const d = ev.data;
                                if (d && typeof d === 'object' && (d.ticket || d.randstr)){
                                    window.__captchaResult = JSON.stringify(d);
                                }
                            } catch(e){}
                        });
                    }
                }, 200);
            })();
            """)

            page.goto("https://app.rainyun.com/auth/login", wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(2000)
            # 点登录按钮触发 TCaptcha
            try:
                # 雨云登录页通常一进入就弹 captcha, 不需要点; 若未弹, 点登录按钮触发
                btn = page.locator("button:has-text('登录'),button:has-text('Login')").first
                if btn.count() > 0:
                    btn.click(timeout=3000)
            except Exception:
                pass
            page.wait_for_timeout(3500)

            # ddddocr 从当前 bg 自动检 (如果 positions 未给)
            if not positions:
                # 抓 iframe bg 图 (dataURL)
                bg_data_url = page.evaluate("""() => {
                    const f = document.getElementById('tcaptcha_iframe_dy') || document.querySelector('iframe');
                    if (!f) return null;
                    try {
                        const doc = f.contentDocument || (f.contentWindow && f.contentWindow.document);
                        const bg = doc && (doc.getElementById('slideBg') || doc.querySelector('img'));
                        if (!bg) return null;
                        return bg.src || (bg.style && bg.style.backgroundImage) || null;
                    } catch(e){ return null; }
                }""")
                if not bg_data_url:
                    browser.close()
                    return SolveResult(ok=False, method="playwright", msg="no-bg-iframe")
                # bg_data_url 形如 "data:image/png;base64,..."
                import base64 as _b64
                if bg_data_url.startswith("data:image"):
                    b64 = bg_data_url.split(",", 1)[1]
                    bg_bytes = _b64.b64decode(b64)
                else:
                    # url → 下载
                    r = urllib.request.urlopen(bg_data_url, timeout=10)
                    bg_bytes = r.read()
                # 同样的拿 sprite
                sp_url = page.evaluate("""() => {
                    const f = document.getElementById('tcaptcha_iframe_dy') || document.querySelector('iframe');
                    if (!f) return null;
                    const doc = f.contentDocument || (f.contentWindow && f.contentWindow.document);
                    const sp = doc && doc.querySelector('#instruction img') || (doc && doc.querySelector('img[src*=\"sprite\"]'));
                    return sp && sp.src;
                }""")
                if not sp_url:
                    browser.close()
                    return SolveResult(ok=False, method="playwright", msg="no-sprite")
                if sp_url.startswith("data:image"):
                    b64 = sp_url.split(",", 1)[1]
                    sp_bytes = _b64.b64decode(b64)
                else:
                    r = urllib.request.urlopen(sp_url, timeout=10)
                    sp_bytes = r.read()
                positions = detect_positions(bg_bytes, sp_bytes)

            # 用 positions 点 (在 iframe 内, 坐标换算: bg 实际像素 672x350)
            js_positions = ",".join(f"({x},{y})" for x, y in positions)
            page.evaluate(f"""async () => {{
                const positions = [{js_positions}];
                const frame = document.getElementById('tcaptcha_iframe_dy') || document.querySelector('iframe');
                if (!frame) {{ window.__captchaResult = JSON.stringify({{err:'no-iframe'}}); return; }}
                const fwin = frame.contentWindow;
                const fdoc = fwin.document;
                const bg = fdoc.getElementById('slideBg') || fdoc.querySelector('img');
                if (!bg) {{ window.__captchaResult = JSON.stringify({{err:'no-bg'}}); return; }}
                const r = bg.getBoundingClientRect();
                // bg 显示尺寸 vs 原图尺寸缩放
                const scale_x = r.width / 672;
                const scale_y = r.height / 350;
                for (const [x,y] of positions) {{
                    const ev = new MouseEvent('click', {{
                        bubbles:true, cancelable:true, view:fwin,
                        clientX: r.left + x*scale_x,
                        clientY: r.top + y*scale_y
                    }});
                    bg.dispatchEvent(ev);
                    await new Promise(r=>setTimeout(r,500));
                }}
                await new Promise(r=>setTimeout(r,3000));
            }}""", timeout=timeout_ms)

            payload = page.evaluate("() => window.__captchaResult || ''")
            browser.close()
    except Exception as e:
        return SolveResult(ok=False, method="playwright", msg=f"playwright-fail: {e}", positions=positions)

    if not payload:
        return SolveResult(ok=False, method="playwright", msg="no-callback", positions=positions)
    try:
        d = json.loads(payload) if payload.startswith("{") else {"raw": payload}
    except Exception:
        return SolveResult(ok=False, method="playwright", msg=f"bad-callback: {payload[:200]}", positions=positions)
    if d.get("ticket") and d.get("randstr"):
        return SolveResult(ok=True, vticket=d["ticket"], vrandstr=d["randstr"], method="playwright",
                           positions=positions, msg=f"playwright ok ticket={d['ticket'][:20]}...")
    return SolveResult(ok=False, method="playwright", msg=f"callback-no-ticket: {json.dumps(d)[:200]}",
                       positions=positions)


# ====== 自动选最优策略 ======
def solve_smart(use_ddddocr: bool = False, use_playwright: bool = False) -> SolveResult:
    """优先第三方 → playwright+ddddocr(需 RAINYUN_REMOTE_CHROME_CDP) → 失败."""
    r = solve_via_thirdparty()
    if r.ok:
        return r
    print(f"  第三方失败 ({r.msg}), 降级 playwright+ddddocr ...")
    r2 = solve_via_playwright(positions=None)
    return r2


# ====== 一站式入口 ======
def solve(auto: bool = True, use_playwright: bool = False) -> SolveResult:
    """默认: 第三方 → (可选) playwright. auto=False 时只跑第三方.
    use_playwright=True: 跳过第三方, 直接 playwright headless (要求 ddddocr 已给出 positions 才能拿到 ticket).

    注意: 本函数本身不获取 bg/sprite (那一步需要外部浏览器/iframe). 默认调用方已先 solve_via_thirdparty.
    """
    if use_playwright:
        return SolveResult(ok=False, method="playwright",
                           msg="need positions, call solve_full() instead")
    return solve_via_thirdparty()


def solve_full_with_thirdparty() -> SolveResult:
    """一站式: 直接拿第三方 ticket, 返回 SolveResult. 推荐默认路径."""
    return solve_via_thirdparty()


# ====== 命令行自检 ======
def _cli_self_test():
    print("TCaptcha 求解器自检")
    print(f"  ddddocr loaded: {DdddOCR_DET is not None or 'lazy'}")
    print(f"  aid = {TCAPTCHA_AID}")
    print("调用第三方服务 ...")
    r = solve_via_thirdparty()
    print(f"  结果: ok={r.ok} method={r.method} ticket={r.vticket[:24] if r.vticket else ''}...")
    if r.msg:
        print(f"  msg: {r.msg}")
    return 0 if r.ok else 1


if __name__ == "__main__":
    sys.exit(_cli_self_test())