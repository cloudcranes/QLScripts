import json
import logging
import re
import requests
from datetime import datetime, timedelta
from time import sleep
from send import send
from qinglong import ql


class JMFabuye:
    def __init__(self, username, password, base_url):
        # 时间精确到秒
        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.username = username
        self.password = password
        self.base_url = base_url
        self.cookies = ''
        self.dataDailyid = ''
        self.host_url = ''
        self.msg_list = '【禁漫天堂】\n'
        self.headers_1 = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-User': '?1',
            'Sec-Fetch-Dest': 'document',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Sec-ch-ua-platform': 'Windows',
            'Sec-ch-ua-mobile': '?0',
            'Cache-Control': 'max-age=0',
            'Upgrade-insecure-requests': '1',
            'Accept-Encoding': 'gzip, deflate, br'
        }
        self.headers_2 = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
            'Sec-ch-ua-mobile': '?0',
            'X-Requested-With': 'XMLHttpRequest'
        }

    def print_now(self, msg):
        logging.info(msg)

    def get_wall_url(self):
        try:
            response = requests.get(self.base_url)
            response.encoding = 'utf-8'
            html_content = response.text

            # 使用正则表达式搜索`</span></strong></span><br />`后的域名
            pattern = r'</span></strong></span><br />(.*?)(?=<\/p>)'
            matches = re.findall(pattern, html_content, re.DOTALL)
            # 去除空格和换行符
            matches = [match.strip() for match in matches]
            domain = matches[0]

            self.host_url = f'https://{domain}'
            self.print_now(f'JM最新域名: {self.host_url}')
        except Exception as e:
            self.print_now(f'获取JM域名失败: {e}')

    def home_page(self):
        response = requests.get(self.host_url)
        response.encoding = 'utf-8'
        html = response.text
        # 使用正则表达式搜索`data-dailyid`属性值，舍弃其他属性值
        pattern = r'data-dailyid="(\d+)"'
        matches = re.findall(pattern, html, re.DOTALL)
        if matches:
            self.dataDailyid = matches[0]
            self.print_now(f'获取daily_id成功: {self.dataDailyid}')
        else:
            self.print_now(f'获取daily_id失败 {html}')

    def click_ad(self):
        url = f'{self.host_url}/ajax/ad_check'
        headers = self.headers_2
        headers['Referer'] = f'{self.host_url}/'
        headers['Origin'] = f'{self.host_url}'
        headers['Cookie'] = self.cookies
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            self.print_now(f'获取广告成功: {response.json()["msg"]}')
        else:
            self.print_now(f'获取广告失败: {response.text}')

    def login(self):
        login_url = f'{self.host_url}/login'
        headers = self.headers_1
        headers['Referer'] = f'{self.host_url}/'
        headers['Origin'] = f'{self.host_url}'

        payload = f'username={self.username}&password={self.password}&id_remember=on&submit_login=1'
        try:
            response = requests.post(login_url, headers=headers, data=payload)
            if response.status_code == 200:
                # 获取登录成功后的set-cookies,提取其中的key-value对，按照key1=value1;key2=value2的形式保存
                cookies = dict(response.cookies)
                cookies = ';'.join([f'{k}={v}' for k, v in cookies.items()])
                self.cookies = json.dumps(cookies)
                self.print_now(f'登录成功: {self.username}')
            else:
                self.print_now(f'登录失败: {response.status_code}')
        except Exception as e:
            self.print_now(f'登录失败: {e}')

    def sign(self):
        # 签到
        sign_url = f'{self.host_url}/ajax/user_daily_sign'
        headers = self.headers_2
        headers['Referer'] = f'{self.host_url}/'
        headers['Origin'] = f'{self.host_url}'
        headers['Cookie'] = self.cookies
        payload = f'daily_id={self.dataDailyid}&oldstep=1'
        try:
            response = requests.post(sign_url, headers=headers, data=payload)
            self.print_now(f'签到成功: {response.json()["msg"]}')
            self.msg_list += f'签到成功: {response.json()["msg"]}\n'
        except Exception as e:
            self.print_now(f'签到失败: {e}')
            self.msg_list += f'签到失败: {e}\n'

    def get_user_info(self):
        # 获取用户信息
        user_info_url = f'{self.host_url}/user'
        headers = self.headers_2
        headers['Referer'] = f'{self.host_url}/'
        headers['Origin'] = f'{self.host_url}'
        headers['Cookie'] = self.cookies
        response = requests.get(user_info_url, headers=headers)
        # with open('../user_info.html', 'w', encoding='utf-8') as f:
        #     f.write(response.text)
        # 解析用户信息 ，使用正则表达式
        # 标题、等级、经验、收藏、金币
        title = \
        re.findall(r'<div class="header-profile-row-value user-current-title">(.+?)</div>', response.text, re.DOTALL)[0]
        level = \
        re.findall(r'<div class="header-profile-row-value">\s*(\d+)\s*<span class="header-profile-exp"', response.text,
                   re.DOTALL)[0]
        experience = re.findall(r'<span class="header-profile-exp">\((.+?)\)</span>', response.text, re.DOTALL)[0]
        collection = re.findall(r'<div class="header-profile-row-value">(.*?)</div>', response.text)
        gold = re.findall(r'<div class="header-profile-row-value ">(\d+)', response.text, re.DOTALL)[0]
        name = re.findall(r'<div class="header-profile-row-name">(.*?)</div>', response.text, re.DOTALL)

        self.print_now(f'账号：{self.username}\n'
                       f'称号：{title}\n'
                       f'等级：{level}\n'
                       f'经验：{experience}\n'
                       f'JCoins：{gold}\n'
                       f'{name[2]}:{collection[1]}  {name[3]}:{collection[2]}  {name[4]}:{collection[3]}')
        self.msg_list += f'账号：{self.username}\n' \
                        f'称号：{title}\n' \
                        f'等级：{level}\n' \
                        f'经验：{experience}\n' \
                        f'JCoins：{gold}\n' \
                        f'{name[2]}:{collection[1]}  {name[3]}:{collection[2]}  {name[4]}:{collection[3]}'


if __name__ == '__main__':
    ql = ql()
    envs = ql.get_env_by_name('jmtt_data')
    base_url_list = ql.get_env_by_name('jmtt_base_url')
    base_url = base_url_list[0]['value']
    for env in envs:
        username = env['value'].split('username=')[1].split('&')[0]
        password = env['value'].split('password=')[1].split('&')[0]
        wxpusher_uid = env.get('remarks', None)
        # 实例化禁漫天堂类
        fabuye = JMFabuye(username, password, base_url)
        fabuye.print_now(f'开始执行: {username}')
        # 获取域名
        fabuye.get_wall_url()
        # 访问首页
        fabuye.home_page()
        # 登录
        fabuye.login()
        # 签到
        fabuye.sign()
        # 点击广告
        for i in range(6):
            fabuye.click_ad()
            sleep(1)
        # 获取用户信息
        fabuye.get_user_info()
        # 发送通知
        if wxpusher_uid and '@' in wxpusher_uid:
            send.wxpusher(wxpusher_uid.split('@')[1], fabuye.msg_list)
        else:
            print('未配置WxPusher UID，取消微信推送')
        print(fabuye.msg_list)
