import json
import re
import requests
from send import send


def main():
    url = "https://www.right.com.cn/forum/home.php?mod=spacecp&ac=credit&showcredit=1"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36",
        "Cookie": cookie
    }
    session = requests.session()
    response = session.get(url, headers=headers)
    try:
        coin = re.findall("恩山币: </em>(.*?) &nbsp;", response.text)[0]
        point = re.findall("<em>积分: </em>(.*?)<span", response.text)[0]
        res = f"恩山币：{coin}\n积分：{point}"
        return res
    except:
        return "登录失败，请检查Cookie是否正确。"


if __name__ == '__main__':
    msg = "#【恩山无线论坛】\n"
    i = 0
    # 读取配置文件
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    for user in config["enshan"]:
        i += 1
        print(f"-------- 账号{i} 开始--------")
        msg += f"------- 账号{i} 开始-------\n"
        name = user["name"]
        print(f"用户名：{name}")
        uid = user["wxpusher_uid"]
        cookie = user["cookie"]
        msg += main() + "\n"
        msg += f"------- 账号{i} 结束-------\n"
        print(msg)
        send.wxpusher(uid, msg)
