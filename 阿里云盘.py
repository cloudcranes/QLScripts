import json
import logging
import os

import requests

from quantum import api

refresh_url = "https://auth.aliyundrive.com/v2/account/token"
sign_url = "https://member.aliyundrive.com/v1/activity/sign_in_list"
reward_url = "https://member.aliyundrive.com/v1/activity/sign_in_reward"
# 阿里云盘账号
# 阿里云盘账号的refresh_token，在https://alist.nn.ci/zh/guide/drivers/aliyundrive.html获取
refresh_token = os.environ.get("ALIYUN_REFRESH_TOKEN")

# 日志配置
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class AliyunNetdisk(object):
    def __init__(self):
        self.id = ""
        self.refresh_url = refresh_url
        self.sign_url = sign_url
        self.reward_url = reward_url
        self.refresh_token = refresh_token
        self.access_token = ""
        self.nick_name = ""
        self.device_id = ""
        self.msg = "【阿里云盘签到】\n"

    def refresh(self):
        url = self.refresh_url
        headers = {
            "content-type": "application/json"
        }
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token
        }
        try:
            r = requests.post(url, headers=headers, data=json.dumps(data))
            print(r.status_code)
            if r.status_code == 200:
                self.access_token = r.json()["access_token"]
                self.nick_name = r.json()["nick_name"]
                self.device_id = r.json()["device_id"]
                self.msg += f"账号 {self.nick_name} 刷新成功\n"
                logger.info(f"{self.nick_name} 刷新成功")
            elif r.status_code == 400:
                logger.info(f"refresh_token {self.refresh_token} 已失效")
                self.msg += f"refresh_token {self.refresh_token} 已失效，请重新获取\n"
        except Exception as e:
            logger.error(f"refresh_token {self.refresh_token} 刷新失败 {e}")
            self.msg += f"refresh_token {self.refresh_token} 刷新失败 {e}\n"

    def sign(self):
        url = self.sign_url
        headers = {
            "content-type": "application/json",
            "authorization": "Bearer " + self.access_token
        }
        data = {
            "isReward": False
        }
        try:
            r = requests.post(url, headers=headers, data=json.dumps(data))
            if r.json()["success"]:
                self.id = r.json()["result"]["signInCount"]
                o = self.id - 1
                self.msg += (f"账号 {self.nick_name} 签到成功\n"
                             f"{r.json()['result']['signInLogs'][o]['calendarChinese']}\n"
                             f"{r.json()['result']['signInLogs'][o]['reward']['notice']}\n")
                logger.info(f"{self.nick_name} 签到成功\n"
                            f"{r.json()['result']['signInLogs'][o]['calendarChinese']}\n"
                            f"{r.json()['result']['signInLogs'][o]['reward']['notice']}\n")
            else:
                logger.info(f"{self.nick_name} 签到失败")
                self.msg += f"账号 {self.nick_name} 签到失败\n"
                self.msg += r.text
        except Exception as e:
            logger.error(f"账号 {self.nick_name} 签到失败 {e}")
            self.msg += f"账号 {self.nick_name} 签到失败 {e}\n"
            self.msg += r.text

    def reward(self):
        url = self.reward_url
        headers = {
            "content-type": "application/json",
            "authorization": "Bearer " + self.access_token,
            "x-device-id": self.device_id
        }
        data = {
            "signInDay": self.id
        }
        r = requests.post(url, headers=headers, data=json.dumps(data))
        # print(r.text)
        if r.status_code == 200:
            self.msg += f"账号 {self.nick_name} 奖励领取成功\n"
            self.msg += f"{r.json()['result']['description']}\n"
            logger.info(f"{self.nick_name} 奖励领取成功 {r.json()['result']['description']}")
        else:
            self.msg += f"账号 {self.nick_name} 奖励领取失败 {r.json()['message']}"
            logger.info(f"账号 {self.nick_name} 奖励领取失败 {r.json()['message']}")


def main():
    api_instance = api()
    aliyun = AliyunNetdisk()
    aliyun.refresh()
    if not aliyun.access_token:
        api_instance.send(aliyun.msg)
        return
    aliyun.sign()
    aliyun.reward()
    api_instance.send(aliyun.msg)


if __name__ == '__main__':
    main()
