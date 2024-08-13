import json
import requests
from send import send
from qinglong import ql


class AliyunPan:
    def __init__(self, refresh_token):
        self.refresh_token = refresh_token
        self.refresh_url = 'https://auth.aliyundrive.com/v2/account/token'
        self.sign_url = 'https://member.aliyundrive.com/v1/activity/sign_in_list'
        self.reward_url = 'https://member.aliyundrive.com/v1/activity/sign_in_reward?_rx-s=mobile'
        self.headers = {'Content-Type': 'application/json'}
        self.access_token = ''
        self.nick_name = ''
        self.device_id = ''
        self.id = ''
        self.msg = '##【阿里云盘签到】\n'

    def refresh_access_token(self):
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token
        }
        response = requests.post(self.refresh_url, headers=self.headers, data=json.dumps(data))
        if response.json()['status'] == 'enabled':
            self.access_token = response.json()['access_token']
            self.nick_name = response.json()['nick_name']
            self.device_id = response.json()['device_id']
            self.msg += f'账号{self.nick_name} 刷新access_token成功\n'
        else:
            self.msg += '刷新access_token失败\n'

    def sign_in(self):
        headers = self.headers.copy()
        headers['Authorization'] = f'Bearer {self.access_token}'
        data = {'isReward': False}
        response = requests.post(self.sign_url, headers=headers, data=json.dumps(data))
        if response.json()['success']:
            self.id = response.json()['result']['signInCount']
            o = self.id - 1
            self.msg += (f'账号{self.nick_name} 签到成功 '
                         f'{response.json()["result"]["signInLogs"][o]["calendarChinese"]} '
                         f'{response.json()["result"]["signInLogs"][o]["reward"]["notice"]}\n')
        else:
            self.msg += f'账号{self.nick_name} 签到失败\n'

    def get_reward(self):
        headers = self.headers.copy()
        headers['Authorization'] = f'Bearer {self.access_token}'
        headers['x-device-id'] = self.device_id
        headers['X-Canary'] = 'client=iOS,app=adrive,version=v6.2.1'
        data = {'signInDay': self.id}
        response = requests.post(self.reward_url, headers=headers, data=json.dumps(data))
        if response.status_code == 200:
            self.msg += (f'账号{self.nick_name} 领取奖励成功\n'
                         f'{response.json()["result"]["description"]}\n')
        else:
            self.msg += f'账号{self.nick_name} 领取奖励失败 {response.json()["message"]}\n'

    def run(self):
        self.refresh_access_token()
        self.sign_in()
        self.get_reward()


if __name__ == '__main__':
    ql = ql()
    envs = ql.get_env_by_name('alyp_data')
    for env in envs:
        # token获取url https://alist.nn.ci/zh/guide/drivers/aliyundrive.html
        refresh_token = env['value']
        wxpusher_uid = env.get('remarks', '')
        aliyun = AliyunPan(refresh_token)
        aliyun.run()
        if wxpusher_uid and '@' in wxpusher_uid:
            send.wxpusher(wxpusher_uid.split('@')[1], aliyun.msg)
        else:
            print('未配置WxPusher')
        print(aliyun.msg)
