import requests
import time
from send import send
from qinglong import ql


class dfjs:
    def __init__(self, account):
        self.token = account
        self.msg = '##【微信小程序-东方棘市】\n'
        self.nickname = ''

    def common_post(self, url, body):
        headers = {
            'version': '1.0.13.2',
            'Content-Type': 'application/json',
            'xweb_xhr': '1',
            'token': self.token,
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/5.37.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36 MicroMessenger/6.8.0(0x16080000) NetType/WIFI MiniProgramEnv/Mac MacWechat/WMPF MacWechat/3.8.7(0x13080712) XWEB/1191',
            'Accept': 'application/json',
            'Sec-Fetch-Site': 'cross-site',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
            'Referer': 'https://servicewechat.com/wxebdf2c44a2a714c2/70/page-frame.html',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }
        response = requests.post(f'https://ys.shajixueyuan.com/api{url}', headers=headers, json=body)
        time.sleep(2)  # Wait for 2 seconds
        return response.json()

    def common_get(self, url):
        headers = {
            'version': '1.0.13.2',
            'Content-Type': 'application/json',
            'xweb_xhr': '1',
            'token': self.token,
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/5.37.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36 MicroMessenger/6.8.0(0x16080000) NetType/WIFI MiniProgramEnv/Mac MacWechat/WMPF MacWechat/3.8.7(0x13080712) XWEB/1191',
            'Accept': 'application/json',
            'Sec-Fetch-Site': 'cross-site',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
            'Referer': 'https://servicewechat.com/wxebdf2c44a2a714c2/70/page-frame.html',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }
        response = requests.get(f'https://ys.shajixueyuan.com/api{url}', headers=headers)
        time.sleep(2)  # Wait for 2 seconds
        return response.json()

    def main(self):
        print('开始签到')
        sign = self.common_post('/user_sign/sign', {})
        print(sign.get('msg', ''))
        if sign.get('msg') == '登录超时，请重新登录':
            print('登录超时，请重新登录')
            self.msg += '登录超时，请重新登录\n'
            return
        if sign.get('code') == 1:
            print(f'能量释放：{sign.get("data", {}).get("rewards_info", {}).get("energy_release", "")}')

        print('分享')
        share = self.common_post('/quest.quest/issueRewards', {"quest_id": 4})
        print(share.get('msg', ''))
        if share.get('data', {}).get('result'):
            print(share['data']['result'].get('msg', ''))

        print('关注公众号')
        follow = self.common_post('/quest.quest/issueRewards', {"quest_id": 2})
        print(follow.get('msg', ''))
        if follow.get('data', {}).get('result'):
            print(follow['data']['result'].get('msg', ''))

        print("————————————")
        print("查询积分")
        info = self.common_get('/user/info')
        self.nickname = info.get('data', {}).get('nickname', '')
        remaining_energies = info.get('data', {}).get('remaining_energies', '')
        remaining_fruits = info.get('data', {}).get('remaining_fruits', '')

        print(f'{self.nickname} 拥有能量：{remaining_energies} 果子：{remaining_fruits}\n')
        self.msg += f'{self.nickname} 拥有能量：{remaining_energies} 果子：{remaining_fruits}\n'


if __name__ == "__main__":
    ql = ql()
    envs = ql.get_env_by_name('dfjs_data')
    for env in envs:
        token = env['value']
        remarks = env.get('remarks', '')
        dfjs_obj = dfjs(token)
        dfjs_obj.main()
        if remarks and '@' in remarks:
            send.wxpusher(remarks.split('@')[1], dfjs_obj.msg)
        else:
            print('未配置wxpusher')
        print(dfjs_obj.msg)
