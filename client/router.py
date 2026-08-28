from pathlib import Path
import loggerric as lr
import socketio, sys

# Check if the program is running interpreted or PyInstaller compiled
if not getattr(sys, 'frozen', False):
    # Dynamically find the project root and add to sys.path so Python can find 'shared/'
    current_dir = Path(__file__).resolve().parent
    project_root = current_dir.parent
    
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

class Router:
    def __init__(self):
        self.__sio = socketio.Client()

        self.__sio.on('connect', self.__on_connect)
        self.__sio.on('disconnect', self.__on_disconnect)
        self.__sio.on('auth-success', self.__on_auth_success)
        self.__sio.on('client-list-updated', self.__on_client_list_updated)
        self.__sio.on('clients-data', self.__on_clients_data)

        self.client_list_updated_external_callback = None

        self.client_id = ''
        self.__clients_data = {}

    def is_connected(self) -> bool:
        return self.__sio.connected

    def get_latest_clients_data(self) -> dict:
        return self.__clients_data

    def bind_event(self, event:str, callback):
        self.__sio.on(event, callback)

    def send_client_information(self, data:dict):
        clients_data = self.__sio.call('client-information', data)
        if isinstance(clients_data, dict):
            self.__clients_data = clients_data

    def connect(self, ip:str, port:int, password:str):
        try:
            # This will raise an exception if the server rejects the connection
            self.__sio.connect(f'http://{ip}:{port}', auth={ 'password': password })
        except socketio.exceptions.ConnectionError as e:
            lr.Log.error(f'Error connecting to server: {e}', align_key=43)

    def __on_clients_data(self, data:dict):
        self.__clients_data = data

    def __on_auth_success(self, client_id:str):
        self.client_id = client_id
        lr.Log.info(f'Authentication successful, received client id {client_id}',
                    highlight=client_id)

    def __on_client_list_updated(self, new_list:dict):
        lr.Log.debug('Client list was updated!')
        self.__clients_data = new_list

        if self.client_list_updated_external_callback:
            self.client_list_updated_external_callback(self.__clients_data)

    def __on_connect(self):
        pass

    def __on_disconnect(self):
        self.client_id = ''
        lr.Log.info('Disconnected from server!')