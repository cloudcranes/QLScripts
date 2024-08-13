#!/usr/bin/python3
# -- coding: utf-8 --
# -------------------
# @Author: cloudcranes
# @Time: 2024/06/04 21:54
# const $ = new Env("吾爱破解")
import re
from datetime import datetime
import requests
from send import send
from qinglong import ql

now = datetime.now()


# ck获取 https://www.52pojie.cn/forum.php
# ck格式 完整cookie
# wapj_data = 'htVC_2132_visitedfid=24; Hm_lvt_46d556462595ed05e05f009cdafff31a=1717219682,1717507150; htVC_2132_saltkey=g7037uws; htVC_2132_lastvisit=1717489702; wzws_sessionid=gDM2LjU2Ljg0LjE3MoJkYjFjYWGgZl8UWoE1NGU1YTQ=; Hm_lpvt_46d556462595ed05e05f009cdafff31a=1717507160; htVC_2132_seccodecSRKk=1939482.ed497f50ec2e24ff25; htVC_2132_ulastactivity=1717507149%7C0; htVC_2132_auth=aa9ddejd4OTFj8o9Fm2LYd17HhwJmNgeH6ROae23BIuTzhCS0W2Iwd5%2BQuBcrlh3lO59ZONsMpate2EGNS9eijVphOSf; htVC_2132_lastcheckfeed=2002841%7C1717507149; htVC_2132_checkfollow=1; htVC_2132_lip=36.56.84.172%2C1717507149; htVC_2132_lastact=1717507154%09misc.php%09seccode; htVC_2132_connect_is_bind=1; htVC_2132_seccodecS=1939503.27fc6acc25ca6ab0ac'


class wapj:
    def __init__(self, ck):
        self.wapjck = ck
        self.headers_1 = {
            'Host': 'www.52pojie.cn',
            'Referer': 'https://www.52pojie.cn/forum.php',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
        self.host = 'https://www.52pojie.cn'
        self.msg = '##【吾爱破解】\n'

    def get_user_info(self):
        url = self.host + '/home.php?mod=spacecp&ac=credit&showcredit=1'
        headers = self.headers_1.copy()
        headers['Cookie'] = ck
        try:
            res = requests.get(url=url, headers=headers, timeout=10)
            # 根据正则规则匹配返回的html语言，提取用户名、吾爱币(纯数字)
            # <strong class="vwmy qq"><a href="home.php?mod=space&amp;uid=2002841" target="_blank" title="访问我的空间">Alanmaster</a></strong>
            # </ul><ul class="creditl mtm bbda cl"><li class="xi1 cl"><em> 吾爱币:</em>437 CB &nbsp; <a href="home.php?mod=spacecp&amp;ac=credit&amp;op=buy" class="xi2">捐助&raquo;</a></li>
            name = re.findall(r'target="_blank" title="访问我的空间">(.*?)</a></strong>', res.text)[0]
            points = re.findall(r'吾爱币: </em>(\d+)', res.text)[0]
            # 格式化输出
            self.msg += f'用户：{name}\n'
            self.msg += f'吾爱币：{points}\n'
            return points
        except:
            self.msg += '查询吾爱币失败\n'
            return None

    def sign(self):
        url = self.host + '/home.php?mod=task&do=apply&id=2'
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 NetType/WIFI MicroMessenger/7.0.20.1781(0x6700143B) WindowsWechat(0x63090a1b) XWEB/9193 Flue',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Dest': 'document',
            'Referer': 'https://www.52pojie.cn/home.php?mod=task&do=draw&id=2&referer=https%3A%2F%2Fwww.52pojie.cn%2Fhome.php%3Fmod%3Dtask%26do%3Dapply%26id%3D2',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Cookie': ck
        }
        try:
            res = requests.get(url=url, headers=headers, timeout=10)
        except Exception as e:
            self.msg += f'签到失败 {e}\n'

    def judge_sign(self):
        url = self.host + '/forum.php'
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 NetType/WIFI MicroMessenger/7.0.20.1781(0x6700143B) WindowsWechat(0x63090a1b) XWEB/9193 Flue',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Dest': 'document',
            'Referer': 'https://www.52pojie.cn/portal.php',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Cookie': ck
        }
        try:
            res = requests.get(url=url, headers=headers, timeout=10)
            # print(res.text)
            # 根据正则规则匹配返回的html语言，判断是否签到成功
            # <a href="home.php?mod=task&amp;do=draw&amp;id=2&amp;referer=https%3A%2F%2Fwww.52pojie.cn%2Fhome.php%3Fmod%3Dtask%26do%3Dapply%26id%3D2" class="xi2">已签到</a>
            if re.findall(r'https://static.52pojie.cn/static/image/common/wbs.png', res.text):
                return True
            else:
                return False
        except Exception as e:
            print(e)
            return False

    def main(self):
        if not self.judge_sign():
            self.sign()
        else:
            self.msg += '今日已签到\n'
        self.get_user_info()


if __name__ == '__main__':
    ql = ql()
    envs = ql.get_env_by_name('wapj_data')
    for env in envs:
        ck = env['value']
        remarks = env.get('remarks', '')
        run = wapj(ck)
        run.main()
        if remarks and '@' in remarks:
            send.wxpusher(remarks.split('@')[1], run.msg)
        else:
            print('未配置wxpusher')
        print(run.msg)
