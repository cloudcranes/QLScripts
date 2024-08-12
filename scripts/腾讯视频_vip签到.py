import json
import requests
from send import send


# txspCookie 腾讯视频app 进入签到页面的Cookie
# txspRefreshCookie 腾讯视频网页NewRefresh接口中(https://pbaccess.video.qq.com/trpc.video_account_login.web_login_trpc.WebLoginTrpc/NewRefresh) 的数据，用来刷新Cookie中的vqq_vusession
# txspRefreshBody json格式，eg:
# {"data":{"errcode":0,"err_msg":"","vuserid":"xx","vusession":"xxx","head":"xxx","nick":"DDD","next_refresh_time":"6594","access_token":"xxxx","appid":"xxx","openid":"xxx","refresh_token":"xxxx"},"ret":0,"msg":""}

class run:
    def __init__(self, txspCookie, txspRefreshCookie, txspRefreshBody):
        self.txspCookie = txspCookie
        self.txspRefreshCookie = txspRefreshCookie
        self.txspRefreshBody = txspRefreshBody
        # 从txspRefreshCookie中获取nick
        self.nick = self.txspRefreshCookie.split('qq_nick=')[1].split(';')[0]
        self.vqq_vusession = ''
        self.msg = '##【腾讯视频_vip签到】\n'
        self.check_in_score = ''
        self.sign = ''
        self.watch = ''
        self.fd = ''
        self.month_received_score = ''
        self.month_limit = ''
        self.score = ''
        self.end_time = ''
        self.level = ''
        self.base_url = 'https://vip.video.qq.com'
        self.headers = {
            'Origin': 'https://film.v.qq.com',
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6_1 like Mac OS X) AppleWebKit/537.51.1 (KHTML, like Gecko) Mobile/11A465 QQLiveBrowser/8.9.71 AppType/UN WebKitCore/WKWebView iOS GDTTangramMobSDK/4.370.6 GDTMobSDK/4.370.6 cellPhone/iPhone 11 AppBuild/25981',
            'Content-Type': 'text/plain;charset=utf-8',
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://film.video.qq.com/x/grade/?ovscroll=0&ptag=Vgrade.icon&source=page_id%3Ddefault%26pgid%3Dpage_personal_center%26page_type%3Dpersonal%26is_interactive_flag%3D1%26pg_clck_flag%3D1%26styletype%3D5%26mod_id%3Dsp_mycntr_userinfo%26sectiontype%3D1%26layouttype%3D22%26flush_num%3D0%26section_idx%3D0%26mod_title%3D%25E7%2594%25A8%25E6%2588%25B7%25E4%25BF%25A1%25E6%2581%25AF%26head_rlt_type%3Dlevel%26blocktype%3D6001%26mod_idx%3D0%26item_idx%3D2%26eid%3Dhead_rlt%26action_pos%3Djump&hidetitlebar=1&isFromJump=1&isDarkMode=0&uiType=REGULAR'
        }

    # 刷新vusession
    def refresh_vqq_vusession(self):
        url = 'https://pbaccess.video.qq.com/trpc.video_account_login.web_login_trpc.WebLoginTrpc/NewRefresh'
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Origin': 'https://v.qq.com',
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6_1 like Mac OS X) AppleWebKit/537.51.1 (KHTML, like Gecko) Mobile/11A465 QQLiveBrowser/8.9.71 AppType/UN WebKitCore/WKWebView iOS GDTTangramMobSDK/4.370.6 GDTMobSDK/4.370.6 cellPhone/iPhone 11 AppBuild/25981',
            'Content-Type': 'text/plain;charset=utf-8',
            'Cookie': self.txspRefreshCookie,
            'Referer': 'https://v.qq.com'
        }
        data = self.txspRefreshBody
        response = requests.post(url, headers=headers, data=json.dumps(data)).json()
        # print(response)
        if response['ret'] == 0:
            self.vqq_vusession = response['data']['vusession']
            # 替换原有cookie中的vusession和vqq_vusession
            self.cookies = self.txspCookie.replace('vusession=', 'vusession=' + self.vqq_vusession + ';')
            print(f'vusession refresh success: {self.vqq_vusession}')
        else:
            print(f'vusession refresh failed: {response["msg"]}')

    # 签到奖励
    def sign_in(self):
        url = self.base_url + '/rpc/trpc.new_task_system.task_system.TaskSystem/CheckIn?rpc_data=%7B%7D'
        headers = self.headers
        headers['Cookie'] = self.cookies
        data = {}
        response = requests.get(url, headers=headers, data=json.dumps(data)).json()
        if response['ret'] == 0:
            self.check_in_score = response['check_in_score']
            print(f'签到成功 获得 {response["check_in_score"]}分')
        else:
            print(f'签到失败: {response["err_msg"]}')

    # 赠送奖励
    def give_award(self):
        url = self.base_url + '/rpc/trpc.new_task_system.task_system.TaskSystem/ProvideAward?rpc_data=%7B%22task_id%22%3A12%7D'
        headers = self.headers
        headers['Cookie'] = self.cookies
        data = {"task_id": 12}
        response = requests.get(url, headers=headers, data=json.dumps(data)).json()
        if response["err_msg"] == "OK":
            print('赠送奖励获取成功')
        else:
            print(f'赠送奖励获取失败: {response["err_msg"]}')

    # 每日观看60分钟奖励
    def daily_watch(self):
        url = self.base_url + '/rpc/trpc.new_task_system.task_system.TaskSystem/ProvideAward?rpc_data=%7B%22task_id%22%3A1%7D'
        headers = self.headers
        headers['Cookie'] = self.cookies
        data = {"task_id": 1}
        response = requests.get(url, headers=headers, data=json.dumps(data)).json()
        if response["err_msg"] == "OK":
            print('每日观看60分钟奖励获取成功')
        else:
            print(f'每日观看60分钟奖励获取失败: {response["err_msg"]}')

    # 获取会员有效期
    def vip_validity(self):
        url = self.base_url + '/rpc/trpc.query_vipinfo.vipinfo.QueryVipInfo/GetVipUserInfoH5'
        headers = self.headers
        headers['Cookie'] = self.cookies
        data = {"geticon": 1, "viptype": "svip|sports|qquvip", "platform": 7}
        response = requests.post(url, headers=headers, data=json.dumps(data)).json()
        if response["result"].get("msg") == "OK":
            self.end_time = response["endTime"]
            self.score = response["score"]
            self.level = response["level"]
        else:
            print(f'获取会员有效期失败: {response["result"]["msg"]}')

    # 任务日志
    def task_log(self):
        url = self.base_url + '/rpc/trpc.new_task_system.task_system.TaskSystem/ReadTaskList?rpc_data=%7B%22business_id%22%3A%221%22%2C%22platform%22%3A5%7D'
        headers = self.headers
        headers['Cookie'] = self.cookies
        data = {"business_id": "1", "platform": 5}
        response = requests.get(url, headers=headers, data=json.dumps(data)).json()
        if response["ret"] == 0:
            tasks = response["task_list"]
            # 寻找task_maintitle为VIP会员每日签到奖励的task_subtitle的值
            for task in tasks:
                if task["task_maintitle"] == "VIP会员每日签到":
                    self.sign = task["task_subtitle"]
                elif task["task_maintitle"] == "手机看视频":
                    self.watch = task["task_subtitle"]
                elif task["task_maintitle"] == "赠送好友福袋":
                    self.fd = task["task_subtitle"]
                else:
                    continue
            limit_info = response["limit_info"]
            self.month_received_score = limit_info["month_received_score"]
            self.month_limit = limit_info["month_limit"]

    def main(self):
        self.refresh_vqq_vusession()
        self.sign_in()
        self.give_award()
        self.daily_watch()
        self.task_log()
        self.vip_validity()
        self.msg += (f'用户名：{self.nick}\n'
                     f'有效期：{self.end_time}\n'
                     f'会员等级：{self.level}\n'
                     f'目前积分：{self.score}\n'
                     f'本月积分：{self.month_received_score}/({self.month_limit})\n'
                     f'每日签到：{self.sign} - {self.check_in_score}\n'
                     f'视频观看：{self.watch}\n'
                     f'赠送福袋：{self.fd}')
        with open(f'config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
            for user in config['txsp_vip']:
                if user['txspRefreshCookie'] == self.txspRefreshCookie:
                    user['username'] = self.nick
        with open(f'config.json', 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)


if __name__ == '__main__':
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    for user in config['txsp_vip']:
        txspCookie = user['txspCookie']
        txspRefreshCookie = user['txspRefreshCookie']
        txspRefreshBody = user['txspRefreshBody']
        run = run(txspCookie, txspRefreshCookie, txspRefreshBody)
        run.main()
        if user['wxpusher_uid']:
            send.wxpusher(user['wxpusher_uid'], run.msg)
        else:
            print('未配置WxPusher，取消微信推送')
        print(run.msg)
