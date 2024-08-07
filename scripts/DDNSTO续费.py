import json
import re
import uuid
from datetime import datetime, timedelta
from send import send
import requests


class DDNSTO:
    def __init__(self, userid, cookie, xcsrftoken):
        self.userid = userid
        self.cookie = cookie
        self.xcsrftoken = xcsrftoken
        self.notice = ''
        self.order_id = ''
        self.headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Cookie': self.cookie,
            'Referer': 'https://www.ddnsto.com/app',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36',
            'X-CSRFToken': self.xcsrftoken,
        }

    def UTC2BJS(self, UTC):
        UTC_format = "%Y-%m-%dT%H:%M:%S.%fZ"
        BJS_format = "%Y-%m-%d %H:%M:%S"
        UTC = datetime.strptime(UTC, UTC_format)
        # 将格林威治时间+8小时变为北京时间
        BJS = UTC + timedelta(hours=8)
        BJSJ = BJS.strftime(BJS_format)
        return BJSJ

    # 获得订单号
    def get_order_id(self):
        uu_id = uuid.uuid4()
        suu_id = ''.join(str(uu_id).split('-'))
        url = 'https://www.ddnsto.com/api/user/product/orders/'
        headers = self.headers
        data = {
            'product_id': '2',
            'uuid_from_client': suu_id
        }
        response = requests.post(url, headers=headers, data=data).json()
        if response.get('application-error', None) == '超出本周免费套餐购买次数':
            self.notice += '超出本周免费套餐购买次数'
            print(response['application-error'])
        else:
            self.order_id = response['id']
            self.notice += f'订单号：{self.order_id}\n'
            self.submit_order()
            self.create_order()
            self.notice += f'----白嫖成功----\n到期时间：{self.UTC2BJS(response["active_plan"]["product_expired_at"])}\n'

    # 提交订单
    def submit_order(self):
        url = f'https://www.ddnsto.com/api/user/product/orders/{self.order_id}/'
        res = requests.get(url, headers=self.headers)
        print(res.text)

    # 创建订单
    def create_order(self):
        url = f'https://www.ddnsto.com/api/user/routers/{self.userid}/'
        headers = self.headers
        data = {
            'plan_ids_to_add': [f'{self.order_id}'],
            'server': 3
        }
        response = requests.post(url, headers=headers, data=data).json()
        if len(response['uid']) > 0:
            self.notice += f'----白嫖成功----\n到期时间：{self.UTC2BJS(response["active_plan"]["product_expired_at"])}\n'
        else:
            self.notice += f'----白嫖失败----\n'

    def main(self):
        self.get_order_id()
        return self.notice


if __name__ == '__main__':
    msg = '##【DDNSTO续费】\n'
    i = 0
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    for user in config['ddnsto']:
        i += 1
        msg += f'------- 账号{i} -------\n'
        msg += f'用户名：{user["username"]}\n'
        # 先购买一次7天免费套餐 抓包查看https://www.ddnsto.com/api/user/routers/*****/ 这个url里面的*****就是userid
        userid = user['userid']
        # 配置参数 登录https://www.ddnsto.com/app/#/devices 抓包cookie
        cookie = user['cookie']
        xcsrftoken = re.findall('csrftoken=(.*?);', cookie, re.S)[0]
        uid = user['wxpusher_uid']
        ddnsto = DDNSTO(userid, cookie, xcsrftoken)
        msg += ddnsto.main()
        print(msg)
        send.wxpusher(uid, msg)
