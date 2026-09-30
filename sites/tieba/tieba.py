"""
cron: 45 8 * * *
new Env('Tieba_BDUSS'): 百度 BDUSS cookie (浏览器登录 https://tieba.baidu.com 后 F12 抓 Cookie 中的 BDUSS)
new Env('Tieba_STOKEN'): 百度 STOKEN cookie (同上, 必填 — 修复了原版 STOKEN 写死的 bug)

百度贴吧 多吧批量签到 — 青龙面板原生适配

策略:
  1) 优先 Tieba_BDUSS + Tieba_STOKEN 环境变量
  2) GET /dc/common/tbs 拿 tbs
  3) GET /mo/q/newmoindex 拉关注贴吧列表 (curl 形式兜底, 因 requests 偶发触发风控)
  4) POST /c/c/forum/sign 每个贴吧签到 (md5 kw+tbs+tiebaclient!!! 签名)
  5) 重试最多 10 轮直到 rest 空
  6) send_sync 推送 (若无通知通道则静默)

依赖: pip install requests
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from hashlib import md5
from pathlib import Path

import requests
from requests import session

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

try:
    from ql_notify import send_sync as send
except ImportError:
    def send(*args, **kwargs):
        print(f"[notify noop] {args}")


HEADERS = {
    'Accept': 'text/html, */*; q=0.01',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Connection': 'keep-alive',
    'Host': 'tieba.baidu.com',
    'Referer': 'http://tieba.baidu.com/i/i/forum',
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36'
    ),
    'X-Requested-With': 'XMLHttpRequest',
}


class Tieba:
    def __init__(self):
        self.BDUSS = os.getenv("Tieba_BDUSS", "").strip()
        self.STOKEN = os.getenv("Tieba_STOKEN", "").strip()
        if not self.BDUSS:
            raise SystemExit("❌ Tieba_BDUSS 未配置, 退出")
        if not self.STOKEN:
            print("⚠ Tieba_STOKEN 未配置, 签到可能 403 — 建议补上")
        self.success_list: list[str] = []
        self.sign_list: list[str] = []
        self.fail_list: list[str] = []
        self.already: set[str] = set()
        self.rest: set[str] = set()
        self.result: dict[str, dict] = {}
        self.tbs: str = ""
        self.session = session()
        self.session.headers.update(HEADERS)

    def set_cookie(self):
        self.session.cookies.update({'BDUSS': self.BDUSS, 'STOKEN': self.STOKEN})

    def fetch_tbs(self):
        r = self.session.get('http://tieba.baidu.com/dc/common/tbs').json()
        if r.get('is_login') == 1:
            self.tbs = r['tbs']
        else:
            raise Exception('获取 tbs 错误: ' + str(r))

    def fetch_likes(self):
        max_retries = 3
        for retry in range(max_retries):
            try:
                print(f'尝试获取贴吧列表, 第 {retry + 1} 次')
                curl_cmd = [
                    'curl',
                    '-H', f'Cookie: BDUSS={self.BDUSS}; STOKEN={self.STOKEN}',
                    '-H', f'User-Agent: {HEADERS["User-Agent"]}',
                    'https://tieba.baidu.com/mo/q/newmoindex',
                ]
                result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=30)
                if result.returncode != 0:
                    raise Exception(f'curl exit={result.returncode} stderr={result.stderr[:120]}')
                r = json.loads(result.stdout)
                if r.get('no') != 0:
                    raise Exception('获取关注贴吧错误: ' + str(r))
                for forum in r.get('data', {}).get('like_forum', []):
                    if forum.get('is_sign') == 1:
                        self.already.add(forum['forum_name'])
                    else:
                        self.rest.add(forum['forum_name'])
                return
            except Exception as e:
                print(f'获取贴吧列表失败: {e}')
                if retry < max_retries - 1:
                    time.sleep(5)
        raise Exception('获取贴吧列表失败, 已达到最大重试次数')

    def sign(self, forum_name: str) -> bool:
        data = {
            'kw': forum_name,
            'tbs': self.tbs,
            'sign': md5(f'kw={forum_name}tbs={self.tbs}tiebaclient!!!'.encode('utf8')).hexdigest(),
        }
        r = self.session.post('http://c.tieba.baidu.com/c/c/forum/sign', data=data).json()
        err = str(r.get('error_code', ''))
        if err == '160002':
            print(f'"{forum_name}" 已签到')
            self.sign_list.append(forum_name)
            return True
        if err == '0':
            sign_rank = r.get("user_info", {}).get("user_sign_rank", "?")
            print(f'"{forum_name}" >>>>>> 签到成功, 您是第 {sign_rank} 个签到的用户')
            self.result[forum_name] = r
            self.success_list.append(forum_name)
            return True
        print(f'"{forum_name}" 签到失败: {r}')
        self.fail_list.append(forum_name)
        return False

    def loop(self, n: int):
        print(f'* 开始第 {n} 轮签到 *')
        rest = set()
        self.fetch_tbs()
        for forum_name in self.rest:
            if not self.sign(forum_name):
                rest.add(forum_name)
        self.rest = rest
        if n >= 10:
            self.rest = set()

    def main(self, max_round: int = 3):
        self.set_cookie()
        self.fetch_likes()
        if self.already:
            print('---------- 已经签到的贴吧 ---------')
            for forum_name in sorted(self.already):
                print(f'"{forum_name}" 已签到')
                self.sign_list.append(forum_name)
        n = 0
        while n < max_round and self.rest:
            n += 1
            self.loop(n)
        if self.rest:
            print('--------- 签到失败列表 ----------')
            for forum_name in sorted(self.rest):
                print(f'"{forum_name}" 签到失败')
        self.notify()

    def notify(self):
        msg_lines = ["贴吧签到结果:"]
        if self.success_list:
            msg_lines.append("- **签到成功贴吧**:")
            for forum in self.success_list:
                rank = self.result.get(forum, {}).get("user_info", {}).get("user_sign_rank", "?")
                msg_lines.append(f"    {forum} (第 {rank} 个)")
        if self.sign_list:
            msg_lines.append("- **已经签到的贴吧**:")
            msg_lines.append("    " + "\n    ".join(self.sign_list))
        msg_lines.append(
            f"\n共关注 {len(self.already) + len(self.success_list)} 个贴吧, "
            f"本次成功 {len(self.success_list)} 个, "
            f"失败 {len(self.fail_list)} 个, "
            f"已签过 {len(self.sign_list)} 个。"
        )
        try:
            send('Tieba_Sign', '\n'.join(msg_lines))
        except Exception as e:
            print(f"通知发送失败: {e}")


def main() -> int:
    try:
        Tieba().main(max_round=3)
    except SystemExit as e:
        print(e)
        return 1
    except Exception as e:
        print(f"❌ 贴吧签到执行失败: {e}")
        return 1
    print("\n---------- 贴吧签到执行完毕 ----------")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())