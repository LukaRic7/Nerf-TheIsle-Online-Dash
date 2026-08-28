import socketio, socketio.exceptions, sys
from collections import deque
from pathlib import Path
from aiohttp import web
import loggerric as lr

# Check if the program is running interpreted or PyInstaller compiled
if not getattr(sys, 'frozen', False):
    # Dynamically find the project root and add to sys.path so Python can find 'shared/'
    current_dir = Path(__file__).resolve().parent
    project_root = current_dir.parent
    
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from colors import ColorManager

class Router:
    def __init__(self, password:str):
        self.__password = password

        self.__sio = socketio.AsyncServer(cors_allowed_origins='*')
        self.__app = web.Application()

        self.__sio.attach(self.__app)

        self.__sio.on('connect', self.__on_client_connect)
        self.__sio.on('disconnect', self.__on_client_disconnect)
        self.__sio.on('client-information', self.__on_client_information)
        self.__sio.on('new-client-coords', self.__on_new_client_coords)

        self.__connected_clients = set()
        self.__client_data = {}
        self.__client_coords:dict[str, deque] = {}

    def bind_event(self, event:str, callback):
        self.__sio.on(event, callback)

    def host(self, port:int):
        try:
            web.run_app(self.__app, host='0.0.0.0', port=port)
        except KeyboardInterrupt:
            lr.Log.info('Keyboard interrupt detected, quitting!')
            exit(0)

    def get_clients(self) -> dict:
        return self.__client_data

    async def __on_new_client_coords(self, client_id:str, coords:list[float, float]):
        self.__client_coords[client_id].append(coords)

        serialized = { k: list(v) for k, v in self.__client_coords.items() }

        await self.__sio.emit('update-client-map', serialized)

    async def __on_client_connect(self, client_id:str, env:dict, auth:dict):
        # Log the incoming attempt
        remote_ip = env.get('REMOTE_ADDR', 'UNKNOWN IP')
        lr.Log.debug(f'Incoming connection attempt from: {remote_ip}',
                     highlight=remote_ip)

        # Authenticate the client
        if not auth or auth.get('password') != self.__password:
            provided_pw = auth.get('password') if auth else 'None'
            lr.Log.warn(f'Rejecting client {client_id}, authentication failed!'
                        + f' Client used {provided_pw}.', 
                        highlight=[client_id, provided_pw])
            raise socketio.exceptions.ConnectionRefusedError('Incorrect password.')

        # Authentication passed
        self.__connected_clients.add(client_id)
        lr.Log.info(f'New client {client_id} connected successfully!',
                    highlight=client_id)
        
        await self.__sio.emit('auth-success', client_id, to=client_id)

        self.__client_data[client_id] = { 'color': ColorManager.occupy() }
        self.__client_coords[client_id] = deque(maxlen=5)

        await self.__sio.emit('client-list-updated', self.__client_data)
        await self.__sio.emit('clients-data', self.__client_data)
    
    async def __on_client_disconnect(self, client_id:str):
        if client_id in self.__connected_clients:
            self.__connected_clients.remove(client_id)

        ColorManager.unassign(self.__client_data[client_id]['color'])
        if client_id in self.__client_data:
            del self.__client_data[client_id]
        if client_id in self.__client_coords:
            del self.__client_coords[client_id]
        
        lr.Log.info(f'Client {client_id} was disconnected!', highlight=client_id)

        await self.__sio.emit('client-list-updated', self.__client_data)
        await self.__sio.emit('clients-data', self.__client_data)

    async def __on_client_information(self, client_id:str, data:dict):
        self.__client_data[client_id] = self.__client_data[client_id] | data

        await self.__sio.emit('clients-data', self.__client_data)
        return self.__client_data