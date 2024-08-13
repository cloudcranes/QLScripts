import json
import requests

class send:
    def __init__(self):
        self.appToken = ''

    # wxpusher
    def wxpusher(uid: str, content: str) -> None:
        url = "https://wxpusher.zjiecode.com/api/send/message"
        # 自行前往官网获取appToken
        appToken = self.appToken
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
