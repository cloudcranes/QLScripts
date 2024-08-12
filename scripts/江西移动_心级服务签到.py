import json
import requests
from send import send


class run:
    def __init__(self, mobile, token):
        self.mobile = mobile
        self.token = token
        self.cookies = ''
        self.msg = '##江西移动 心级服务签到\n'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 11; M2105K81AC Build/RKQ1.200826.002; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/94.0.4606.85 Safari/537.36; unicom{version:android@11.0000,desmobile:0};devicetype{deviceBrand:Xiaomi,deviceModel:M2105K81AC}',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
            'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate',
            'Origin': 'https://wxmall.jx139.com',
            'Content-Type': 'application/json'
        }

    def login(self):
        url = 'https://wxmall.jx139.com/mo-h5-new/act/cloud-vip-v3/sign/525601'
        headers = self.headers
        headers['Referer'] = f'https://wxmall.jx139.com/mo-h5-new/floor/cloud-vip-v3/index?mobile={self.mobile}&token={self.token}'
        headers['Cookie'] = self.cookies
        response = requests.post(url, headers=headers, data='')
        self.msg += f'用户：{self.mobile} 登录结果：{response.json()['message']}\n'

    def get_cookie(self):
        url = f'https://wxmall.jx139.com/mo-h5-new/floor/cloud-vip-v3/index?mobile={self.mobile}&token={self.token}'
        headers = {'Referer': url}
        response = requests.get(url, headers=headers)
        cookies = response.cookies.get_dict()
        self.cookies = ';'.join([f'{k}={v}' for k, v in cookies.items()])
        self.msg += f'获取Cookie成功：{self.cookies}\n'

    def main(self):
        self.get_cookie()
        self.login()


if __name__ == '__main__':
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    for user in config['jxyd_xjfw_qd']:
        mobile = user['username']
        token = user['token']
        run = run(mobile, token)
        run.main()
        if user.get('wxpusher_uid'):
            send.wxpusher(user['wxpusher_uid'], run.msg)
        else:
            print('未配置wxpusher_uid')
        print(run.msg)
