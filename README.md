## QL-Scripts-青龙自用脚本

| 序列 |         名称          |    类型    |                             链接                             |
| :--: | :-------------------: | :--------: | :----------------------------------------------------------: |
|  1   | 配置文件(config.json) |     -      | [config.json](https://github.com/cloudcranes/QLScripts/blob/main/scripts/config.json) |
|  2   |       吾爱破解        |    网站    | [吾爱破解.py](https://github.com/cloudcranes/QLScripts/blob/main/scripts/%E5%90%BE%E7%88%B1%E7%A0%B4%E8%A7%A3.py) |
|  3   |       阿里云盘        |    app     | [阿里云盘.py](https://github.com/cloudcranes/QLScripts/blob/main/scripts/%E9%98%BF%E9%87%8C%E4%BA%91%E7%9B%98.py) |
|  4   |       禁漫天堂        |    网站    | [禁漫天堂.py](https://github.com/cloudcranes/QLScripts/blob/main/scripts/%E7%A6%81%E6%BC%AB%E5%A4%A9%E5%A0%82.py) |
|  5   |     携趣代理加白      |    网站    | [携趣代理白名单管理.py](https://github.com/cloudcranes/QLScripts/blob/main/scripts/%E6%90%BA%E8%B6%A3%E4%BB%A3%E7%90%86%E7%99%BD%E5%90%8D%E5%8D%95%E7%AE%A1%E7%90%86) |
|  6   |     恩山无线论坛      |    网站    | [恩山无线论坛.py](https://github.com/cloudcranes/QLScripts/blob/main/scripts/%E6%81%A9%E5%B1%B1%E6%97%A0%E7%BA%BF%E8%AE%BA%E5%9D%9B.py) |
|  7   |      DDNSTO续费       |    网站    | [DDNSTO续费.py](https://github.com/cloudcranes/QLScripts/blob/main/scripts/DDNSTO%E7%BB%AD%E8%B4%B9.py) |
|  8   |       东方棘市        | 微信小程序 | [东方棘市.py](https://github.com/cloudcranes/QLScripts/blob/main/scripts/%E4%B8%9C%E6%96%B9%E6%A3%98%E5%B8%82.py) |

- [ ] 阿里云盘
  - [ ] nick_name：可空，脚本登陆后自动填入
  - [ ] refresh_token：必须，token获取url https://alist.nn.ci/zh/guide/drivers/aliyundrive.html
  - [ ] wxpusher_id：必须，wxpusher的用户uid
- [ ] 禁漫天堂
  - [ ] username：必须，用户登录名
  - [ ] password：必须，用户登录密码
  - [ ] cookies：可空，脚本登陆后自动填入
  - [ ] expires_time：可空，没啥用，就是提个醒
  - [ ] wxpusher_id，同上
- [ ] 携趣代理加白
  - [ ] uid：必须，携趣代理后台获取
  - [ ] ukey：必须，携趣代理后台获取
  - [ ] wxpusher_id：同上
  - [ ] white_list、last_ip：可空，脚本自动填入
- [ ] 恩山无线论坛
  - [ ] name：可控，备注名
  - [ ] cookie：必须，[恩山无线论坛](https://www.right.com.cn)首页cookie
  - [ ] wxpusher_uid：同上
- [ ] DDNSTO续费
  - [ ] username：可空，备注名
  - [ ] userid：必须，先购买一次7天免费套餐 抓包查看https://www.ddnsto.com/api/user/routers/*****/ 这个url里面的*****就是userid
  - [ ] cookie：必须，登录https://www.ddnsto.com/app/#/devices 抓包cookie
- [ ] 东方棘市
  - [ ] nickname：可空，脚本自动填入
  - [ ] token：必须，抓包https://ys.shajixueyuan.com/api 下token
  - [ ] wxpusher_uid：同上
