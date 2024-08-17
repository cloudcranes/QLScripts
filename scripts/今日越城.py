import base64
import hashlib
import hmac
import json
import logging
import random
import time
import uuid
import requests
from urllib.parse import quote, urlparse, parse_qs
from Crypto.Cipher import PKCS1_v1_5, AES
from Crypto.PublicKey import RSA
from Crypto.Util.Padding import pad

from qinglong import ql
from send import send

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


class yuecheng:
    def __init__(self, username, password):
        self.ocr_host = "http://192.168.1.114:10049"
        self.name = username
        self.pwd = password
        self.user_id = None
        self.ua = None
        self.common_ua = None
        self.msg = ""
        self.host = "https://vapp.tmuyun.com"
        self.key = "nNo7464SYE6kUHjL"
        self.tenantId = "31"
        self.clientId = "48"
        self.signatureSalt = "FR*r!isE5W"
        self.signature_key = ""
        self.public_key = """-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQD6XO7e9YeAOs+cFqwa7ETJ+WXizPqQeXv68i5vqw9pFREsrqiBTRcg7wB0RIp3rJkDpaeVJLsZqYm5TW7FWx/iOiXFc+zCPvaKZric2dXCw27EvlH5rq+zwIPDAJHGAfnn1nmQH7wR3PCatEIb8pz5GFlTHMlluw4ZYmnOwg+thwIDAQAB
-----END PUBLIC KEY-----"""
        self.code = ""
        self.uuid = None
        self.accountId = None
        self.sessionId = None
        self.device_id = None
        self.id = None
        self.jinhuaAppId = 'K8tbWP2J0x3uCITGYEhL'
        self.jinhuaKey = '35c782a2'
        self.jinhuaToken = ''
        self.lotteryId = None

    @staticmethod
    def generate_device_code():
        device_code = ''
        chars = 'abcdef0123456789'
        for _ in range(16):
            device_code += random.choice(chars)
        return device_code

    def log_info(self, msg):
        logging.info(f"用户【{self.name}】：{msg}")

    def log_err(self, msg):
        logging.error(f"用户【{self.name}】：{msg}")

    def generate_uuid(self):
        return str(uuid.uuid4())

    def generate_random_ua(self):
        version = "1.7.0"
        uuid_value = str(uuid.uuid4())
        device_ids = [
            "M1903F2A", "M2001J2E", "M2001J2C", "M2001J1E", "M2001J1C",
            "M2002J9E", "M2102K1C", "M2101K9C", "2107119DC", "2201123C",
            "2112123AC", "2201122C", "2211133C", "2210132C", "2304FPN6DC",
            "23127PN0CC", "24031PN0DC", "23090RA98C", "2312DRA50C",
            "2312CRAD3C", "2312DRAABC", "22101316UCP", "22101316C"
        ]
        # 假设clientId是预先定义好的变量，如果未定义，请相应地添加或修改
        deviceId = random.choice(device_ids)
        device = f"Xiaomi {deviceId}"
        os = "Android"
        os_version = "11"
        os_type = "Release"
        app_version = "6.12.0"

        self.ua = f"{os.upper()};{os_version};{self.clientId};{version};1.0;null;{deviceId}"
        self.common_ua = f"{version};{uuid_value};{device};{os};{os_version};{os_type};{app_version}"
        self.uuid = uuid_value
        self.device_id = uuid_value

    def get_params(self, url):
        current_time = int(time.time() * 1000)
        uuid = self.generate_uuid()
        print(current_time)

        if '?' in url:
            url = url.split('?')[0]

        signature_base = f"{url}&&{self.sessionId}&&{uuid}&&{current_time}&&{self.signatureSalt}&&{self.tenantId}"
        signature = hashlib.sha256(signature_base.encode()).hexdigest()

        return {
            "uuid": uuid,
            "time": current_time,
            "signature": signature
        }

    def encrypt(self, data):
        public_key = "-----BEGIN PUBLIC KEY-----\n" \
                     "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQD6XO7e9YeAOs+cFqwa7ETJ+WXizPqQeXv68i5vqw9pFREsrqiBTRcg7wB0RIp3rJkDpaeVJLsZqYm5TW7FWx/iOiXFc+zCPvaKZric2dXCw27EvlH5rq+zwIPDAJHGAfnn1nmQH7wR3PCatEIb8pz5GFlTHMlluw4ZYmnOwg+thwIDAQAB\n" \
                     "-----END PUBLIC KEY-----"

        # 解码公钥
        key = RSA.importKey(public_key)

        # 创建RSA对象
        cipher = PKCS1_v1_5.new(key)

        # 进行加密并返回加密后的结果
        encrypted_data = cipher.encrypt(data.encode())
        return base64.b64encode(encrypted_data).decode()

    def aes_encrypt(self, e, r):
        key = r.encode('utf-8')  # Convert the key to bytes
        data = e.encode('utf-8')  # Convert the plaintext to bytes

        cipher = AES.new(key, AES.MODE_ECB)  # Create a new AES cipher in ECB mode
        padded_data = pad(data, AES.block_size)  # Pad the plaintext to the block size
        encrypted = cipher.encrypt(padded_data)  # Encrypt the padded plaintext

        return base64.b64encode(encrypted).decode('utf-8')  # Return the encrypted data as a base64-encoded string

    def get_body(self):
        password_encrypted = self.encrypt(self.pwd)

        # 构造原始body字符串，不进行urlencode
        raw_body = f"client_id={self.clientId}&password={password_encrypted}&phone_number={self.name}"
        str_to_sign = f"post%%/web/oauth/credential_auth?{raw_body}%%{self.uuid}%%"

        # 使用urllib.parse.quote对密码进行编码，以符合URL标准
        body = f"client_id={self.clientId}&password={quote(password_encrypted)}&phone_number={self.name}"

        # 计算HMAC-SHA256签名
        hash_digest = hmac.new(self.signature_key.encode(), str_to_sign.encode(), hashlib.sha256).digest()
        signature = hash_digest.hex()

        return {"uuid": self.uuid, "signature": signature, "body": body}

    def get_jinhua_params(self, params):
        current_time = int(time.time() * 1000)
        nonce_str = self.generate_uuid()

        config = {
            'app_id': self.jinhuaAppId,
            'device_id': self.device_id,
            'nonce_str': nonce_str,
            'source_type': 'app',
            'timestamp': current_time,
            'auth_id': self.accountId,
            'token': self.sessionId
        }

        # Update config with params
        config.update(params)

        # Sort keys and create the result string
        sorted_keys = sorted(config.keys())
        result = '&&'.join([f"{key}={config[key]}" for key in sorted_keys])
        result += '&&' + self.jinhuaKey

        # Generate the signature
        signature = hashlib.sha256(result.encode()).hexdigest()

        return {
            "uuid": nonce_str,
            "time": current_time,
            "signature": signature
        }

    def common_get(self, path):
        params = self.get_params(path)
        headers = {
            'Connection': 'Keep-Alive',
            'X-TIMESTAMP': str(params['time']),
            'X-SESSION-ID': self.sessionId,
            'X-REQUEST-ID': params['uuid'],
            'X-SIGNATURE': params['signature'],
            'X-TENANT-ID': self.tenantId,
            'X-ACCOUNT-ID': self.accountId,
            'Cache-Control': 'no-cache',
            'Accept-Encoding': 'gzip',
            'user-agent': self.common_ua,
        }
        res = requests.get(f"{self.host}{path}", headers=headers)
        if res.status_code == 200:
            return res.json()
        return None

    def common_post(self, path, body=None):
        params = self.get_params(path)
        headers = {
            'Connection': 'Keep-Alive',
            'X-TIMESTAMP': str(params['time']),
            'X-SESSION-ID': self.sessionId,
            'X-REQUEST-ID': params['uuid'],
            'X-SIGNATURE': params['signature'],
            'X-TENANT-ID': self.tenantId,
            'X-ACCOUNT-ID': self.accountId,
            'Cache-Control': 'no-cache',
            'Accept-Encoding': 'gzip',
            'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
            'user-agent': self.common_ua,
        }
        res = requests.post(f"{self.host}{path}", headers=headers, data=body)
        if res.status_code == 200:
            return res.json()
        return None

    def jihua_get(self, path, body):
        params = self.get_jinhua_params(body)
        headers = {
            'access-type': 'app',
            'access-module': 'study',
            'access-device-id': self.device_id,
            'access-auth-id': self.accountId,
            'access-api-signature': params['signature'],
            'access-nonce-str': params['uuid'],
            'authorization': self.jinhuaToken,
            'access-app-id': self.jinhuaAppId,
            'access-timestamp': str(params['time']),
            'access-api-token': self.sessionId,
            'accept': 'application/json, text/plain, */*',
            'user-agent': 'Mozilla/5.0 (Linux; Android 11; 21091116AC Build/RP1A.200720.011; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/94.0.4606.85 Mobile Safari/537.36;xsb_yuecheng;xsb_yuecheng;1.7.0;native_app;6.12.0',
            'content-type': 'application/json; charset=UTF-8',
            'origin': 'https://op-h5.cloud.jinhua.com.cn',
            'x-requested-with': 'com.zjonline.zhuji',
            'sec-fetch-site': 'same-site',
            'sec-fetch-mode': 'cors',
            'sec-fetch-dest': 'empty',
            'referer': 'https://op-h5.cloud.jinhua.com.cn/',
            'accept-encoding': 'gzip, deflate',
            'accept-language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        res = requests.get(f"https://op-api.cloud.jinhua.com.cn{path}", headers=headers)
        if res.status_code == 200:
            return res.json()
        return None

    def jihua_post(self, path, body):
        params = self.get_jinhua_params(body)
        headers = {
            'access-type': 'app',
            'access-module': 'study',
            'access-device-id': self.device_id,
            'access-auth-id': self.accountId,
            'access-api-signature': params['signature'],
            'access-nonce-str': params['uuid'],
            'authorization': self.jinhuaToken,
            'access-app-id': self.jinhuaAppId,
            'access-timestamp': str(params['time']),
            'access-api-token': self.sessionId,
            'accept': 'application/json, text/plain, */*',
            'user-agent': 'Mozilla/5.0 (Linux; Android 11; 21091116AC Build/RP1A.200720.011; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/94.0.4606.85 Mobile Safari/537.36;xsb_yuecheng;xsb_yuecheng;1.7.0;native_app;6.12.0',
            'content-type': 'application/json; charset=UTF-8',
            'origin': 'https://op-h5.cloud.jinhua.com.cn',
            'x-requested-with': 'com.zjonline.zhuji',
            'sec-fetch-site': 'same-site',
            'sec-fetch-mode': 'cors',
            'sec-fetch-dest': 'empty',
            'referer': 'https://op-h5.cloud.jinhua.com.cn/',
            'accept-encoding': 'gzip, deflate',
            'accept-language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        res = requests.post(f"https://op-api.cloud.jinhua.com.cn{path}", headers=headers, data=json.dumps(body))
        if res.status_code == 200:
            return res.json()
        return None

    def slide_post(self, body):
        headers = {
            'Content-Type': 'application/json',
        }
        res = requests.post(f"{self.ocr_host}/capcode", headers=headers, data=json.dumps(body))
        if res.status_code == 200:
            return res.json()
        return None

    def init(self):
        path = "/api/account/init"
        res = self.common_post(path, None)
        self.log_info(f"【init】：{res}")
        if res:
            if res['code'] == 0:
                self.sessionId = res['data']['session']['id']
                return True
        return False

    def gete_signature_key(self):
        path = f"/web/init?client_id={self.clientId}"
        headers = {
            'Connection': 'Keep-Alive',
            'Cache-Control': 'no-cache',
            'X-REQUEST-ID': str(uuid.uuid4()),
            'Accept-Encoding': 'gzip',
            'user-agent': self.ua,
        }
        res = requests.get(f"https://passport.tmuyun.com{path}", headers=headers)
        self.log_info(f"gete_signature_key=>{res.text}")
        if res.status_code == 200:
            rj = res.json()
            if rj['code'] == 0:
                self.signature_key = rj['data']['client']['signature_key']
                return True
        return False

    def credential_auth(self):
        path = "/web/oauth/credential_auth"
        params = self.get_body()
        headers = {
            'Connection': 'Keep-Alive',
            'X-REQUEST-ID': params['uuid'],
            'X-SIGNATURE': params['signature'],
            'Cache-Control': 'no-cache',
            'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
            'Accept-Encoding': 'gzip',
            'user-agent': self.ua,
        }
        res = requests.post(f"https://passport.tmuyun.com{path}", headers=headers, data=params['body'])
        self.log_info(f"credential_auth=>{res.text}")
        if res.status_code == 200:
            rj = res.json()
            if rj['code'] == 0:
                self.code = rj['data']['authorization_code']['code']
                return True
        return False

    def login(self):
        path = "/api/zbtxz/login"
        data = {
            "check_token": "",
            "code": self.code,
            "token": "",
            "type": -1,
            "union_id": "",
        }
        res = self.common_post(path, data)
        self.log_info(f"login=>{res}")
        if res:
            if res['code'] == 0:
                self.accountId = res['data']['session']['account_id']
                self.sessionId = res['data']['session']['id']

                self.msg += f"\n【登陆状态】：登陆成功✅"
                self.msg += f"\n【用户昵称】：{res['data']['account']['nick_name']}"
                self.msg += f"\n【用户编码】：{res['data']['account']['ref_user_code']}"
                self.msg += f"\n【绑定手机】：{res['data']['account']['mobile']}"
                self.msg += f"\n【邀请数量】：{res['data']['account']['invitation_number']}"
                # self.msg += f"\n【下载地址】：{res['data']['download_link']}"

                return True
        self.msg += f"\n【登陆状态】：登陆失败{res}"
        return False

    def config(self):
        path = "/api/minus1floor/config"
        res = self.common_get(path)
        self.log_info(f"login=>{res}")
        if res:
            if res['code'] == 0:
                url = res['data']['article_list'][2]['column_news_list'][2]['url']
                parsed_url = urlparse(url)
                query_params = parse_qs(parsed_url.query)
                result = {k: v[0] for k, v in query_params.items()}
                self.id = result['id']

    def jihua_login(self):
        res = self.jihua_post("/api/member/login", {"debug": 0, "userId": ""})
        self.log_info(f"【jihua_login】=>{res}")
        if res:
            if res['code'] == 0:
                self.jinhuaKey = res['data']['key']
                self.jinhuaToken = f"Bearer {res['data']['token']}"
                return True
        return False

    def jihua_detail(self):

        res = self.jihua_get(f"/api/study/detail?id={self.id}", {"id": self.id})
        self.log_info(f"【jihua_detail-{self.id}】=>{res}")
        if not res or res['code'] != 0:
            return False
        self.lotteryId = res['data']['lottery']['lottery_id']
        for item in res['data']['levels']:
            item_res = self.jihua_get(f"/api/study/level?id={item['id']}", {"id": item['id']})
            if not item_res or item_res['code'] != 0:
                continue
            self.msg += f"\n---------抽奖阅读----------"
            if item_res['data']['level']['task_num'] == len(item_res['data']['completedTasks']):
                self.log_info(f"{item['name']},已完成")
                self.msg += f"\n今日阅读已全部完成✅"
                continue
            for task in item_res['data']['tasks']:
                article_res = self.common_get(f"/api/article/detail?id={task['content_id']}")
                self.log_info(f'文章阅读开始：{article_res.get("message", "")}')
                read_time_res = self.common_get(
                    f"/api/article/read_time?channel_article_id={task['content_id']}&read_time=5938")
                self.log_info(f'文章阅读：{read_time_res.get("message", "")}')
                complete_res = self.jihua_post(f"/api/study/task/complete", {"id": task['id']})
                self.log_info(f'文章阅读结果：{complete_res.get("message", "")}')
                self.msg += f'\n文章[{task["id"]}]：{complete_res.get("message", "")}'
        self.msg += f"\n---------抽奖----------"
        lotter_res = self.jihua_post(f"/api/lotterybigwheel/_ac_lottery_count",
                                     {"id": self.lotteryId, "module": "study"})
        if not lotter_res or lotter_res['code'] != 0:
            return False
        self.log_info(f"当前剩余抽奖次数：{lotter_res['data']['count']}")
        self.msg += f"\n抽奖次数：{lotter_res['data']['count']}"
        for index in range(lotter_res['data']['count']):
            ac_res = self.jihua_post(f"/api/lotterybigwheel/_ac_lottery",
                                     {"id": self.lotteryId, "app_id": self.jinhuaAppId, "module": "study",
                                      "optionHash": ""})
            if not ac_res:
                continue
            if ac_res['code'] == 10000:
                self.log_info(f"本次抽奖遇到滑块，开始自动验证滑块")
                self.msg += f"本次抽奖遇到滑块，开始自动验证滑块"
                if not self.ocr_host:
                    self.log_err(f"请搭建dddocr自动滑块！请搭建ddddocr自动滑块！请搭建ddddocr自动滑块！")
                captcha_res = self.jihua_post(f"/api/captcha/get",
                                              {"activity_id": self.lotteryId, "module": "bigWheel"})
                if not captcha_res or captcha_res.get('code', None) != 0:
                    self.log_err(f"第{index}次抽奖获取验证码图片失败")
                    continue
                jigsawImageUrl = captcha_res['data']['jigsawImageUrl']
                originalImageUrl = captcha_res['data']['originalImageUrl']
                captchaToken = captcha_res['data']['token']
                secretKey = captcha_res['data']['secretKey']
                ocr_res = self.slide_post({'slidingImage': jigsawImageUrl, 'backImage': originalImageUrl})
                if not ocr_res:
                    self.log_err(f"第{index}次抽奖过滑块失败，ddddocr服务异常")
                    continue
                point = self.aes_encrypt(json.dumps({"x": ocr_res['result'], "y": 5}), secretKey)
                cap_check_res = self.jihua_post(f"/api/captcha/check",
                                                {"activity_id": self.lotteryId, "module": "bigWheel",
                                                 "cap_token": captchaToken, "point": point})
                if not cap_check_res:
                    self.log_err(f"第{index}次抽奖过滑块check失败")
                if cap_check_res['message'] == "操作成功":
                    ac_res = None
                    ac_res = self.jihua_post(f"/api/lotterybigwheel/_ac_lottery",
                                             {"id": self.lotteryId, "app_id": self.jinhuaAppId, "module": "study",
                                              "optionHash": ""})
                    if ac_res and ac_res['code'] == 0:
                        self.log_info(f"第{index}次抽奖成功，获得{ac_res['data']['title']}")
                        self.msg += f"\n第{index}次抽奖成功，获得{ac_res['data']['title']}"
                        return True
            if ac_res['code'] == 0:
                self.log_info(f"第{index}次抽奖成功，获得{ac_res['data']['title']}")
                self.msg += f"\n第{index}次抽奖成功，获得{ac_res['data']['title']}"
                return True

    def task_list(self):
        path = "/api/user_center/task?type=1&current=1&size=20"
        res = self.common_get(path)
        self.log_info(res)
        if not res:
            return False
        readFinish = True
        likeFinish = True
        shareFinish = True
        for index, task in enumerate(res['data']['list'], start=1):
            self.log_info(f"【{task['name']}】：{'已完成' if task['completed'] == 1 else '未完成'}")
            self.msg += f"\n【{task['name']}】：{'已完成' if task['completed'] == 1 else '未完成，开始去完成'}"
            if task['completed'] == 1:
                continue
            self.log_info(f"任务：{task['name']},进度：{task['finish_times']}/{task['frequency']}")
            if task['name'] == '新闻资讯阅读':
                readFinish = False
            if task['name'] == '新闻资讯点赞':
                likeFinish = False
            if task['name'] == '分享资讯给好友':
                shareFinish = False
        if not readFinish or not likeFinish or not shareFinish:
            channel_list_res = self.common_get("/api/article/channel_list?channel_id=5dbf7fdfb1985007455762fd&isDiFangHao=false&is_new=true&list_count=0&size=80")
            if not channel_list_res:
                return
            for index, article in enumerate(channel_list_res['data']['article_list']):
                id = article['id']
                if not readFinish:
                    read_res = self.common_get(
                        f"/api/article/read_time?channel_article_id={id}&is_end=true&read_time=3051")
                    if read_res.get("score_notify"):
                        self.log_info(f"阅读获得：{read_res['data']['score_notify']['integral']}积分✅")
                        self.msg += f"\n阅读文章【{id}】:获得{read_res['data']['score_notify']['integral']}积分"
                    else:
                        self.log_info(f"文章【{id}】已阅读")
                if not likeFinish:
                    like_res = self.common_post(f"/api/favorite/like", {"action": True, "id": id})
                    self.log_info(f"点赞文章【{id}】：{like_res}")
                    if like_res and like_res.get("score_notify"):
                        self.log_info(f"点赞获得：{like_res['data']['score_notify']['integral']}积分")
                        self.msg += f"\n点赞文章【{id}】:获得{like_res['data']['score_notify']['integral']}积分"
                    else:
                        self.log_info(f"文章【{id}】已点赞")
                if not shareFinish:
                    share_res = self.common_post(f"/api/user_mumber/doTask",
                                                 {"memberType": "3", "member_type": "3", "target_id": id})
                    self.log_info(f"分享文章【{id}】：{share_res}")
                    if share_res.get("score_notify"):
                        self.log_info(f"分享获得：{share_res['data']['score_notify']['integral']}积分")
                        self.msg += f"\n分享文章【{id}】:获得{share_res['data']['score_notify']['integral']}积分"
                    else:
                        self.log_info(f"文章【{id}】已分享")

    def account_detail(self):
        res = self.common_get(f"/api/user_mumber/account_detail")
        if res:
            self.msg += f"\n【积分余额】：{res['data']['rst']['total_integral']}"

    def run(self):
        self.msg = f"【账号备注】：{self.name}"
        self.generate_random_ua()
        if self.init() and self.gete_signature_key() and self.credential_auth() and self.login():
            self.config()
            if self.jihua_login():
                self.jihua_detail()
            self.msg += f"\n---------积分阅读----------"
            self.task_list()
            self.msg += f"\n---------查询资产----------"
            self.account_detail()


if __name__ == '__main__':
    ql = ql()
    envs = ql.get_env_by_name('jinriyuecheng_data')
    for env in envs:
        username = env["value"].split('&')[0]
        password = env["value"].split('&')[1]
        wxpusher_uid = env.get("remarks", None)
        run = yuecheng(username, password)
        run.run()
        if wxpusher_uid and "@" in wxpusher_uid:
            send.wxpusher(wxpusher_uid.split('@')[1], run.msg)
        else:
            print("未配置WxPusher")
        print(run.msg)
