import json
import logging
from datetime import datetime

import requests
from qinglong import ql
from send import send

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


class qiaqia:
    def __init__(self, auth, userId):
        self.auth = auth
        self.headers = {'Connection': 'keep-alive', 'xweb_xhr': '1',
                        'User-Agent': 'Mozilla/5.0(WindowsNT10.0;Win64;x64)AppleWebKit/537.36(KHTML,likeGecko)''Chrome/122.0.0.0Safari/537.36MicroMessenger/7.0.20.1781(0x6700143B)NetType/WIFI''MiniProgramEnv/WindowsWindowsWechat/WMPFWindowsWechat(0x63090a1b)XWEB/11177',
                        'Content-Type': 'application/json',
                        'Referer': 'https://servicewechat.com/wxc72491b6cd007333/398/page-frame.html'}
        self.userId = userId
        self.integralValue = None
        self.continueDays = None
        self.phone = None
        self.vipLevel = None
        self.totalPoint = None
        self.msg = '##【恰恰瓜子】\n'

    def _config_info(self, content):
        logging.info(content)
        self.msg += f"【{remarks.split('@')[0]}】 - {content}\n"

    def _config_error(self, content):
        logging.error(content)
        self.msg += f"【{remarks.split('@')[0]}】 - {content}\n"

    def sign_in(self):
        url = 'https://vip.qiaqiafood.com/vip/member/listUserSignLog'
        headers = self.headers
        headers['Authorization'] = self.auth
        headers['Host'] = 'vip.qiaqiafood.com'
        yearMonth = datetime.now().strftime('%Y-%m')
        data = json.dumps({
            "yearMonth": yearMonth,
            "uid": self.userId,
            "tenantId": "1"
        })
        self._config_info("签到日志如下：")
        response = requests.post(url, headers=headers, data=data).json()
        print(response)
        if response['success']:
            res = response.get('data', [])
            if res:
                for i in res:
                    self.continueDays = res.get('continueDays', None)
                    self.integralValue = res.get('integralValue', None)
                    self._config_info(f"{i.get('yearMonth')}-{i.get('dayMonth')} 签到成功，连续签到{self.continueDays}天，获得{self.integralValue}积分")
            return True
        else:
            self._config_error("签到失败")
            return False

    def get_vip_info(self):
        url = 'https://vip.qiaqiafood.com/vip/member/getVipInfo'
        headers = self.headers
        headers['Authorization'] = self.auth
        headers['Host'] = 'vip.qiaqiafood.com'
        data = json.dumps({
            "uid": self.userId,
            "tenantId": "1"
        })
        response = requests.post(url, headers=headers, data=data).json()
        if response['success']:
            res = response.get('data', [])
            if res:
                self.phone = res.get('phone', None)
                self.vipLevel = res.get('vipLevel', None)
                self.totalPoint = res.get('totalPoint', None)
                self._config_info(f"手机号：{self.phone}，等级：{self.vipLevel}，总积分：{self.totalPoint}")
        else:
            self._config_error("获取VIP信息失败")

    def points_log(self):
        url = 'https://vip.qiaqiafood.com/vip/member/point/log'
        headers = self.headers
        headers['Authorization'] = self.auth
        headers['Host'] = 'vip.qiaqiafood.com'
        data = json.dumps({
            "page": 1,
            "pageSize": 10,
            "uid": self.userId,
            "tenantId": "1"
        })
        self._config_info("积分日志如下：")
        response = requests.post(url, headers=headers, data=data).json()
        count = response.get('count', 0)
        if count > 0 and response['success']:
            res = response.get('data', [])
            for i in res:
                remark = i.get('remark', None)
                point = i.get('point', None)
                createTime = i.get('createTime', None)
                expiredTime = i.get('expiredTime', None)
                bizName = i.get('bizName', None)
                self._config_info(f"{bizName} - {remark} 积分：{point} {createTime} / {expiredTime}")
        else:
            self._config_error("积分日志为空")

    def main(self):
        if not self.sign_in():
            self._config_error("cookie失效，请重新获取")
            return
        self.get_vip_info()
        self.points_log()


if __name__ == '__main__':
    ql = ql()
    envs = ql.get_env_by_name('qiaqia_data')
    for env in envs:
        auth = env['value'].split('&')[0]
        userId = env['value'].split('&')[1]
        remarks = env['remarks']
        q = qiaqia(auth, userId)
        q.main()
        if remarks and "@" in remarks:
            send.wxpusher(remarks.split('@')[1], q.msg)
        else:
            print("未配置微信推送，请前往 https://wxpusher.zjiecode.com/ 申请并配置")
        print(q.msg)
