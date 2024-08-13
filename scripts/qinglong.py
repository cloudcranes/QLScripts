import requests


class ql:
    def __init__(self):
        self.api_url = 'http://192.168.1.100:5700/open'
        self.client_id = ''
        self.client_secret = ''
        self.headers = {'Content-Type': 'application/json'}
        self.token = ''
        self.get_token()

    # 获取用户密钥
    def get_token(self):
        url = f'{self.api_url}/auth/token?client_id={self.client_id}&client_secret={self.client_secret}'
        response = requests.get(url, headers=self.headers)
        self.token = f'Bearer {response.json()["data"]["token"]}'

    # 获取所有环境变量详情
    def get_env_list(self):
        url = f'{self.api_url}/envs'
        headers = {'Authorization': self.token}
        response = requests.get(url, headers=headers)
        return response.json()['data']

    # 根据名称获取环境变量详情
    def get_env_by_name(self, name: str) -> list:
        env_list = self.get_env_list()
        matching_envs = []
        # Collect all environment variables that match the given name
        for env in env_list:
            if env['name'] == name:
                matching_envs.append(env)
        return matching_envs

    # 添加环境变量
    def add_env(self, name: str, value: str, remarks='') -> dict:
        url = f'{self.api_url}/envs'
        headers = self.headers
        headers['Authorization'] = self.token
        data = [{'name': name, 'value': value, 'remarks': remarks}]
        response = requests.post(url, headers=headers, json=data)
        return response.json()['data']

    # 更新环境变量
    def update_env(self, id: str, name: str, value: str, remarks='') -> dict:
        url = f'{self.api_url}/envs'
        headers = self.headers
        headers['Authorization'] = self.token
        data = {'id': id, 'name': name, 'value': value, 'remarks': remarks}
        response = requests.put(url, headers=headers, json=data)
        return response.json()['data']

    # 删除环境变量
    def delete_env(self, id: str) -> dict:
        url = f'{self.api_url}/envs'
        headers = self.headers
        headers['Authorization'] = self.token
        # 可填入多个id
        data = [id]
        response = requests.delete(url, headers=headers, json=data)
        return response.json()

    # 根据id获取环境变量
    def get_env_by_id(self, id: str) -> dict:
        url = f'{self.api_url}/envs/{id}'
        headers = self.headers
        headers['Authorization'] = self.token
        response = requests.get(url, headers=headers)
        return response.json()['data']

    # move
    def move_env(self, id: str) -> dict:
        url = f'{self.api_url}/envs/move'
        headers = self.headers
        headers['Authorization'] = self.token
        data = {
            'fromIndex': 0,
            'toIndex': 0,
        }
        response = requests.get(url, headers=headers, json=data)
        return response.json()['data']

    # 禁用环境变量
    def disable_env(self, id: str) -> dict:
        url = f'{self.api_url}/envs/disable'
        headers = self.headers
        headers['Authorization'] = self.token
        data = [id]
        response = requests.put(url, headers=headers, json=data)
        return response.json()

    # 启用环境变量
    def enable_env(self, id: str) -> dict:
        url = f'{self.api_url}/envs/enable'
        headers = self.headers
        headers['Authorization'] = self.token
        data = [id]
        response = requests.put(url, headers=headers, json=data)
        return response.json()

    # 修改环境变量名
    def rename_env(self, id: str, name: str) -> dict:
        url = f'{self.api_url}/envs/name'
        headers = self.headers
        headers['Authorization'] = self.token
        data = {'ids': id, 'name': name}
        response = requests.put(url, headers=headers, json=data)
        return response.json()

    # 获取配置文件列表
    def get_config_list(self) -> dict:
        url = f'{self.api_url}/configs/files'
        headers = self.headers
        headers['Authorization'] = self.token
        response = requests.get(url, headers=headers)
        return response.json()['data']

    # 获取配置文件内容
    def get_config_content(self, file_name: str) -> dict:
        url = f'{self.api_url}/configs/{file_name}'
        headers = self.headers
        headers['Authorization'] = self.token
        response = requests.get(url, headers=headers)
        return response.json()['data']

    # 保存配置文件内容
    def save_config_content(self, file_name: str, content: str) -> dict:
        url = f'{self.api_url}/configs/save'
        headers = self.headers
        headers['Authorization'] = self.token
        data = {'name': file_name, 'content': content}
        response = requests.post(url, headers=headers, json=data)
        return response.json()

    # 获取所有日志列表
    def get_log_list(self) -> dict:
        url = f'{self.api_url}/logs'
        headers = self.headers
        headers['Authorization'] = self.token
        response = requests.get(url, headers=headers)
        return response.json()['data']

    # 获取任务日志
    def get_task_log(self, dir: str, file_name: str) -> dict:
        url = f'{self.api_url}/logs/{dir}/{file_name}'
        headers = self.headers
        headers['Authorization'] = self.token
        response = requests.get(url, headers=headers)
        return response.json()['data']

    # 根据名称获取任务日志
    def get_task_log_by_name(self, log_name: str) -> dict:
        url = f'{self.api_url}/logs/{log_name}'
        headers = self.headers
        headers['Authorization'] = self.token
        response = requests.get(url, headers=headers)
        return response.json()['data']

    # 获取所有任务详情
    def get_task_list(self) -> dict:
        url = f'{self.api_url}/crons'
        headers = self.headers
        headers['Authorization'] = self.token
        response = requests.get(url, headers=headers)
        return response.json()['data']['data']

    # 新增任务
    def add_task(self, command: str, schedule: str, name: str, labels='') -> dict:
        url = f'{self.api_url}/crons'
        headers = self.headers
        headers['Authorization'] = self.token
        data = {'command': command, 'schedule': schedule, 'name': name, 'labels': labels}
        response = requests.post(url, headers=headers, json=data)
        return response.json()

    # 更新任务
    def update_task(self, id: str, command: str, schedule: str, name: str, labels='') -> dict:
        url = f'{self.api_url}/crons'
        headers = self.headers
        headers['Authorization'] = self.token
        data = {'id': id, 'command': command, 'schedule': schedule, 'name': name, 'labels': labels}
        response = requests.put(url, headers=headers, json=data)
        return response.json()

    # 删除任务
    def delete_task(self, id: str) -> dict:
        url = f'{self.api_url}/crons'
        headers = self.headers
        headers['Authorization'] = self.token
        data = [id]
        response = requests.delete(url, headers=headers, json=data)
        return response.json()

    # 根据id获取任务详情
    def get_task_by_id(self, id: str) -> dict:
        url = f'{self.api_url}/crons/{id}'
        headers = self.headers
        headers['Authorization'] = self.token
        response = requests.get(url, headers=headers)
        return response.json()['data']

    # 运行任务
    def run_task(self, id: str) -> dict:
        url = f'{self.api_url}/crons/run'
        headers = self.headers
        headers['Authorization'] = self.token
        data = [id]
        response = requests.put(url, headers=headers, json=data)
        return response.json()

    # 停止任务
    def stop_task(self, id: str) -> dict:
        url = f'{self.api_url}/crons/stop'
        headers = self.headers
        headers['Authorization'] = self.token
        data = [id]
        response = requests.put(url, headers=headers, json=data)
        return response.json()

    # 添加标签
    def add_label(self, id: str, label: str) -> dict:
        url = f'{self.api_url}/labels'
        headers = self.headers
        headers['Authorization'] = self.token
        data = {'ids': id, 'labels': label}
        response = requests.post(url, headers=headers, json=data)
        return response.json()

    # 删除标签
    def delete_label(self, id: str, label: str) -> dict:
        url = f'{self.api_url}/labels'
        headers = self.headers
        headers['Authorization'] = self.token
        data = {'ids': id, 'labels': label}
        response = requests.delete(url, headers=headers, json=data)
        return response.json()

    # 禁用任务
    def disable_task(self, id: str) -> dict:
        url = f'{self.api_url}/crons/disable'
        headers = self.headers
        headers['Authorization'] = self.token
        data = [id]
        response = requests.put(url, headers=headers, json=data)
        return response.json()

    # 启用任务
    def enable_task(self, id: str) -> dict:
        url = f'{self.api_url}/crons/enable'
        headers = self.headers
        headers['Authorization'] = self.token
        data = [id]
        response = requests.put(url, headers=headers, json=data)
        return response.json()

    # 根据id获取任务日志
    def get_task_log_by_id(self, id: str) -> dict:
        url = f'{self.api_url}/crons/{id}/log'
        headers = self.headers
        headers['Authorization'] = self.token
        response = requests.get(url, headers=headers)
        return response.json()['data']

    # 置顶任务
    def top_task(self, id: str) -> dict:
        url = f'{self.api_url}/crons/pin'
        headers = self.headers
        headers['Authorization'] = self.token
        data = [id]
        response = requests.put(url, headers=headers, json=data)
        return response.json()

    # 取消置顶任务
    def cancel_top_task(self, id: str) -> dict:
        url = f'{self.api_url}/crons/unpin'
        headers = self.headers
        headers['Authorization'] = self.token
        data = [id]
        response = requests.put(url, headers=headers, json=data)
        return response.json()

    # 系统版本
    def get_version(self) -> dict:
        url = f'{self.api_url}/system'
        headers = self.headers
        headers['Authorization'] = self.token
        response = requests.get(url, headers=headers)
        return response.json()['data']
