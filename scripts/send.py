import json

import requests


class send:
    def __init__(self):
        self.url = None
        self.bot_id = None
        self.to_user = None
        self._config()
    # 千寻微信框架
    def _config(self):
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        self.url = config['wechat']['http_url']
        self.bot_id = config['wechat']['bot_id']
        self.to_user = config['wechat']['to_user']

    def text(self, message: str) -> None:
        url = f"{self.url}/DaenWxHook/httpapi/?wxid={self.bot_id}"
        data = json.dumps({
            "type": "Q0001",
            "data": {
                "wxid": self.to_user,
                "msg": message
            }})
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, data=data, headers=headers)
        print(f"状态码:{response.json()['code']} 响应数据:{response.json()['msg']}")

    def img(self, img_path: str) -> None:
        url = f"{self.url}/DaenWxHook/httpapi/?wxid={self.bot_id}"
        data = json.dumps({
            "type": "Q0010",
            "data": {
                "wxid": self.to_user,
                "path": img_path
            }})
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, data=data, headers=headers)
        print(f"状态码:{response.json()['code']} 响应数据:{response.json()['msg']}")

    def share_link(self, title: str, content: str, jumpUrl: str, img_path: str, app=''):
        url = f"{self.url}/DaenWxHook/httpapi/?wxid={self.bot_id}"
        data = json.dumps({
            "type": "Q0012",
            "data": {
                "wxid": self.to_user,
                "title": title,
                "content": content,
                "jumpUrl": jumpUrl,
                "img_path": img_path,
                "app": app
            }})
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, data=data, headers=headers)
        print(f"状态码:{response.json()['code']} 响应数据:{response.json()['msg']}")
    # wxpusher
    def wxpusher(uid: str, content: str) -> None:
        url = "https://wxpusher.zjiecode.com/api/send/message"
        # 自行前往官网获取appToken
        appToken = ""
        data = json.dumps({
            "appToken": appToken,
            "content": content,
            "contentType": 3,
            "uids": [uid],
            "verifyPayType": 0
        })
        headers = {
            "Content-Type": "application/json"
        }
        response = requests.post(url, data=data, headers=headers)
        try:
            if response.json()['code'] == 1000:
                if response.json()['data'][0]['code'] == 1000:
                    print(response.json()['data'][0]['status'])
                else:
                    print(response.json()['data'][0]['status'])
        except json.JSONDecodeError:
            print("发送失败")
