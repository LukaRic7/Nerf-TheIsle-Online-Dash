from pathlib import Path
import loggerric as lr
import requests, sys

# Check if the program is running interpreted or PyInstaller compiled
if not getattr(sys, 'frozen', False):
    # Dynamically find the project root and add to sys.path so Python can find 'shared/'
    current_dir = Path(__file__).resolve().parent
    project_root = current_dir.parent
    
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

class NerfAPI:
    def __init__(self, cookie:str):
        self.__cookie = cookie

    def __fetch(self, path:str, method:str='get', payload:dict=None) -> dict:
        url = f'https://api.nerfofficial.org/{path}'
        headers = { 'Cookie': self.__cookie }

        response:requests.Response = None
        if method == 'get':
            response = requests.get(url, headers=headers)
        elif method == 'post':
            response = requests.post(url, headers=headers, json=payload)

        data:dict = response.json()

        if not response.ok:
            lr.Log.error(f'Fetch not OK: [{response.status_code}] {response.reason}',
                         highlight=str(response.status_code))
        elif not data.get('success', True):
            lr.Log.warn('Fetch did not return success!')

        return response.json()

    def validate_cookie(self) -> bool:
        data:dict = self.__fetch('api/auth/status')

        return data.get('authenticated', False)

    def get_profile(self) -> dict:
        data:dict = self.__fetch('api/auth/status').get('user', {})

        return {
            'discord_id': data.get('id', ''),
            'username': data.get('username', 'NO USERNAME'),
            'bones': data.get('bones', 0),
            'meat': data.get('meat', 0),
            'level': data.get('level', 0)
        }

    def get_active_dino(self) -> dict:
        data = self.__fetch('api/profile/active-dino')

        return {
            'species': data.get('activeDino', 'NO ACTIVE DINOSAUR'),
            'vitals': data.get('vitals', {}),
            'growth': data.get('growth', 0.0),
            'is_prime': data.get('isPrimeElder', False)
        }

    def get_playtime(self) -> str:
        data = self.__fetch('api/survival-playtime')

        hours, mins = divmod(data.get('playtime', 0) // 60, 60)

        if hours == 0: return f'{mins:.0f}m'
        else: return f'{hours:.0f}h {mins:.0f}m'

    def get_pending_teleports(self) -> dict:
        pending = self.__fetch('api/teleport-requests')
        tp_requests:list[dict] = pending.get('requests', [])

        ids = []
        for request in tp_requests:
            ids.append({ 'discord_id': request.get('requesterDiscordId'),
                                'request_id': request.get('id') })

        return ids

    def accept_teleports(self, request_id:str) -> dict:
        response = self.__fetch('api/teleport-response', 'post',
                            { 'requestId': request_id, 'accept': True })

        lr.Log.debug(f'ACCEPT TELEPORTS: {response}')

        return response

    def send_teleport(self, discord_id:str) -> dict:
        response = self.__fetch('api/teleport-request', 'post',
                                { 'targetDiscordId': discord_id, 'server': 'EU' })

        lr.Log.debug(f'SEND TELEPORT: {response}')

        return response