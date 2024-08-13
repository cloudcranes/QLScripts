import time
import requests
from qinglong import ql
from send import send


class bwcj:
    def __init__(self, ck):
        self.token = ck
        self.nickname = ''
        self.mobile = ''
        self.sign_points = ''
        self.all_points = ''
        self.time = time.strftime('%Y-%m-%d', time.localtime(time.time()))
        self.base_url = 'https://webapi2.qmai.cn'
        self.headers = {
            'qm-user-token': self.token,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a1b)XWEB/11177',
            'Referer': 'https://servicewechat.com/wxafec6f8422cb357b/185/page-frame.html'
        }
        self.msg = '##【霸王茶姬】\n'

    def main(self):
        self.get_vip_info()
        self.sign_in()
        self.get_all_points()
        self.msg += f'昵称：{self.nickname}\n'
        self.msg += f'手机号：{self.mobile}\n'
        self.msg += f'签到积分：{self.sign_points}\n'
        self.msg += f'总积分：{self.all_points}\n'
        self.msg += f'时间：{self.time}\n'

    # 每日签到
    def sign_in(self):
        url = f'{self.base_url}/web/cmk-center/sign/userSignStatistics'
        data = {
            "activityId": "947079313798000641",
            "appid": "wxafec6f8422cb357b"
        }
        response = requests.post(url, headers=self.headers, json=data).json()
        if response['code'] == 0:
            self.sign_points = response['data']['basicPoints']
        else:
            print(response)

    # 查询积分
    def get_all_points(self):
        url = f'{self.base_url}/web/cmk-center/common/getCrmAvailablePoints?appid=wxafec6f8422cb357b'
        response = requests.get(url, headers=self.headers).json()
        if response['code'] == 0:
            self.all_points = response['data']
        else:
            print(response)

    # 查询会员信息
    def get_vip_info(self):
        url = f'{self.base_url}/web/catering2-apiserver/crm/personal-info?appid=wxafec6f8422cb357b'
        response = requests.get(url, headers=self.headers).json()
        if response['code'] == '0':
            self.nickname = response['data']['name']
            self.mobile = response['data']['mobilePhone']
        else:
            print(response)

    # 登录刷新token
    # def refresh_token(self):
    #     url = f'{self.base_url}/web/seller/oauth/flash-sale-login'
    #     headers = {
    #         'Content-Type': 'application/json',
    #         'qm-from-type': 'catering',
    #         'qm-from': 'wechat',
    #         'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a1b)XWEB/11177',
    #         'Sec-fetch-site': 'cross-site',
    #         'Sec-Fetch-Mode': 'cors',
    #         'Sec-Fetch-Dest': 'empty',
    #         'Referer': 'https://servicewechat.com/wxafec6f8422cb357b/185/page-frame.html',
    #         'Accept-Language': 'zh-CN',
    #         'scene': '1145'
    #     }
    #     data = {
    #         "code": self.code,
    #         "appid": "wxafec6f8422cb357b",
    #         "flowScene": '1145'
    #     }
    #     response = requests.post(url, headers=headers, json=data).json()
    #     print(response)
    #     self.token = response['data']['token']
    #     self.headers['qm-user-token'] = self.token
    #     self.nickname = response['data']['user']['nickname']
    #     self.mobile = response['data']['user']['mobile']
    #     print(f'登录成功，用户昵称：{self.nickname}, 手机号：{self.mobile}')


if __name__ == '__main__':
    ql =ql()
    envs = ql.get_env_by_name('bwcj_data')
    for env in envs:
        wxpusher_uid = env.get('remarks', '')
        ck = env['value']
        bwcj_obj = bwcj(ck)
        bwcj_obj.main()
        if wxpusher_uid and '@' in wxpusher_uid:
            send.wxpusher(wxpusher_uid.split('@')[1], bwcj_obj.msg)
        else:
            print('未配置wxpusher_uid')
        print(bwcj_obj.msg)
