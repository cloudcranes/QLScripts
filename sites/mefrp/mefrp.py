"""
cron: 50 8 * * *
new Env('MEFRP_USER_TOKEN'): MEFRP 个人页 /api/auth/user-token 抓 Bearer (sk-...)
new Env('REMOTE_CHROME_CDP'): (可选) http://127.0.0.1:9222 — 用远程 Chrome 跑 ESA slide; 不填则本地 headless chromium

MEFRP (MeFrp.com) 多账号签到 — 青龙面板原生适配

策略:
  1) 优先 MEFRP_USER_TOKEN 环境变量 (青龙推荐)
  2) 调用 /3rdparty/captcha?client=smartapi 触发 ESA WAF slide, 用 headless chromium (或远程 CDP) 跑过
  3) 拿 base64 字符串 → 解码出 token||client → 截取 token 部分
  4) POST /api/auth/user/sign (Bearer) → 完成每日签到

依赖: pip install playwright requests
        playwright install chromium
"""
from __future__ import annotations

import argparse
import base64
import logging
import os
import re
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from _pretty import ACCOUNT, CAPTCHA, DONE, FAIL, GIFT, TRAFFIC, WARN
from ql_notify import send_sync


bot_machine = "https://www.mefrp.com/3rdparty/captcha?client=smartapi"
sign_url = "https://api.mefrp.com/api/auth/user/sign"
userinfo_url = "https://api.mefrp.com/api/auth/user/info"
DEFAULT_USER_TOKEN = ""


def mask_value(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 10:
        return "******"
    return f"{value[:4]}...{value[-4:]}"


class MefrpSigner:
    def __init__(self, user_token: str):
        self.user_token = user_token
        self.out_file = APP_DIR / "artifacts" / "captcha.png"
        self.out_file.parent.mkdir(parents=True, exist_ok=True)
        self.msg_lines = []
        self.logger = logging.getLogger("mefrp_sign")

    def _log(self, text: str, level: int = logging.INFO):
        self.logger.log(level, text)
        self.msg_lines.append(str(text))

    def get_token(self) -> str:
        try:
            from playwright.sync_api import TimeoutError as PWTimeoutError
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            raise RuntimeError("未安装 playwright, 无法打开验证码页面") from exc

        remote_cdp = os.getenv("REMOTE_CHROME_CDP", "").strip()
        with sync_playwright() as p:
            browser = context = None
            try:
                if remote_cdp:
                    self._log(f"使用远程 Chrome: {remote_cdp}")
                    browser = p.chromium.connect_over_cdp(remote_cdp)
                    context = browser.contexts[0] if browser.contexts else browser.new_context()
                else:
                    self._log("未配置 REMOTE_CHROME_CDP, 使用本地 headless Chromium")
                    browser = p.chromium.launch(headless=True, args=["--window-size=1920,1080"])
                    context = browser.new_context()

                context.grant_permissions(["clipboard-read", "clipboard-write"], origin="https://www.mefrp.com")
                page = context.new_page()
                page.goto(bot_machine, wait_until="domcontentloaded")
                page.wait_for_timeout(2000)

                page.screenshot(path=str(self.out_file))
                self._log(f"截图已保存: {self.out_file}")

                try:
                    captcha_btn = page.locator("div.captcha[role='button']")
                    captcha_btn.wait_for(state="visible", timeout=10000)
                    captcha_btn.click(timeout=5000)
                    page.wait_for_timeout(2500)
                except PWTimeoutError:
                    self._log("未找到验证码按钮, 可能页面结构发生变化", logging.WARNING)

                page.wait_for_timeout(2000)

                token = ""
                try:
                    copy_btn = page.locator(".n-button__content")
                    copy_btn.wait_for(state="visible", timeout=10000)
                    copy_btn.click(timeout=5000)
                    page.wait_for_timeout(1000)
                    token = page.evaluate("""
                        async () => {
                            try {
                                return await navigator.clipboard.readText();
                            } catch (e) {
                                return "";
                            }
                        }
                    """)
                    self._log(f"获取到 token: {mask_value(token)}")
                except PWTimeoutError:
                    self._log("未找到复制按钮, 可能页面结构发生变化", logging.WARNING)

                return token
            finally:
                if context:
                    context.close()
                if browser:
                    browser.close()

    def decode_captcha_token(self, raw_token: str) -> str:
        if not raw_token:
            return ""
        try:
            encoded = raw_token.split(",", 1)[1] if "," in raw_token else raw_token
            encoded = encoded.strip()
            encoded += "=" * (-len(encoded) % 4)
            try:
                decoded = base64.b64decode(encoded).decode("utf-8", errors="ignore")
            except Exception:
                decoded = base64.urlsafe_b64decode(encoded).decode("utf-8", errors="ignore")
            if "||" not in decoded:
                self._log("base64 解码成功但格式异常", logging.WARNING)
                return ""
            return decoded.split("||", 1)[0].strip()
        except Exception as e:
            self._log(f"base64 解码失败: {e}", logging.ERROR)
            return ""

    def _format_traffic(self, traffic_mb) -> str:
        try:
            value = float(traffic_mb)
        except Exception:
            return str(traffic_mb)
        if value >= 1024:
            return f"{value / 1024:.2f} GB"
        return f"{value:.0f} MB"

    def sign(self, captcha_token: str) -> bool:
        import requests
        headers = {
            "Authorization": f"Bearer {self.user_token}",
            "Content-Type": "application/json",
        }
        body = {"captchaToken": captcha_token}
        try:
            resp = requests.post(sign_url, headers=headers, json=body, timeout=15)
            try:
                data = resp.json()
            except Exception:
                data = {}
            message = str(data.get("message", ""))
            if "已签到" in message:
                self._log(f"⏭️ 签到结果: {message}")
                return True
            if resp.status_code != 200:
                self._log(f"{FAIL} 签到结果: HTTP {resp.status_code} - {resp.text[:200]}", logging.ERROR)
                return False
            api_code = data.get("code")
            message = data.get("message", "")
            if api_code == 200:
                self._log(f"{GIFT} 签到结果: {message or '成功'}")
                return True
            if api_code == 0:
                self._log(f"⏭️ 签到结果: {message or '已签到'}")
                return True
            self._log(f"{FAIL} 签到结果: code={api_code}, message={message}, raw={str(data)[:300]}", logging.ERROR)
            return False
        except Exception as e:
            self._log(f"{FAIL} 签到请求异常: {e}", logging.ERROR)
            return False

    def get_user_info(self):
        import requests
        headers = {
            "Authorization": f"Bearer {self.user_token}",
            "Content-Type": "application/json",
        }
        try:
            resp = requests.get(userinfo_url, headers=headers, timeout=15)
            try:
                data = resp.json()
            except Exception:
                self._log(f"{FAIL} 用户信息获取失败: HTTP {resp.status_code} - {resp.text[:200]}", logging.ERROR)
                return
            if resp.status_code != 200:
                self._log(f"{FAIL} 用户信息获取失败: HTTP {resp.status_code} - {str(data)[:200]}", logging.ERROR)
                return
            if data.get("code") != 200:
                self._log(f"{FAIL} 用户信息获取失败: code={data.get('code')}, message={data.get('message', '')}", logging.ERROR)
                return
            info = data.get("data") or {}
            self._log(f"{ACCOUNT} 用户信息:")
            self._log(f"👤 用户名: {info.get('username', '')}")
            self._log(f"📧 邮箱: {info.get('email', '')}")
            self._log(f"🏷️ 用户组: {info.get('friendlyGroup', info.get('group', ''))}")
            self._log(f"✅ 今日已签到: {info.get('todaySigned', False)}")
            self._log(f"{TRAFFIC} 流量: {self._format_traffic(info.get('traffic', 0))}")
            self._log(f"🚇 已用隧道数: {info.get('usedProxies', 0)}/{info.get('maxProxies', 0)}")
        except Exception as e:
            self._log(f"{FAIL} 用户信息请求异常: {e}", logging.ERROR)

    def run(self) -> bool:
        if not self.user_token:
            self._log(f"{WARN} 未配置 MEFRP_USER_TOKEN, 无法签到", logging.ERROR)
            return False
        raw_token = self.get_token()
        captcha_token = self.decode_captcha_token(raw_token)
        if captcha_token:
            ok = self.sign(captcha_token)
            self.get_user_info()
            return ok
        self._log(f"{CAPTCHA} 未获取到有效的验证码 token, 无法签到", logging.ERROR)
        return False

    @property
    def msg(self) -> str:
        return "\n".join(self.msg_lines)


def parse_args():
    parser = argparse.ArgumentParser(description="MEFRP 签到")
    parser.add_argument("--no-notify", action="store_true", help="禁用 send 通知")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    signer = MefrpSigner(user_token=os.getenv("MEFRP_USER_TOKEN", DEFAULT_USER_TOKEN).strip())
    ok = signer.run()
    print(f"\n{DONE} ===== msg =====")
    print(signer.msg)
    if not args.no_notify:
        send_sync("MEFRP 签到结果", signer.msg)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())