import json
import re
import requests
from send import send
from qinglong import ql


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
    msg = "##【恩山无线论坛】\n"
    ql = ql()
    envs = ql.get_env_by_name('enshan_data')
    for env in envs:
        cookie = env['value']
        remarks = env.get('remarks', '')
        res = main()
        if res:
            msg += f"{remarks}\n{res}\n"
        else:
            msg += f"{remarks}\n登录失败，请检查Cookie是否正确。\n"
        if remarks and '@' in remarks:
            send.wxpusher(remarks.split('@')[1], msg)
        else:
            print('未配置wxpusher')
        print(msg)

