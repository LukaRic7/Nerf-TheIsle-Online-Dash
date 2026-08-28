import json, threading, time, sys, asyncio
from datetime import datetime, timezone
from pathlib import Path
import tkinter as tk

# ============================================= #
#  SETUP
# ============================================= #

# Attempt to import non-native packages
try:
    import loggerric as lr
    import socketio, pyperclip
except ImportError as e:
    print(f'Failed to import non-native packages: {e}')
    exit(1)

# Check if the program is running interpreted or PyInstaller compiled
if not getattr(sys, 'frozen', False):
    # Dynamically find the project root and add to sys.path so Python can find 'shared/'
    current_dir = Path(__file__).resolve().parent
    project_root = current_dir.parent
    
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

# Attempt to read the environment file
try:
    with open('env.json', 'r') as file:
        config:dict = json.load(file)
except FileNotFoundError as e:
    lr.Log.error(f'Environment file was not found: {e}', align_key=30)

# Local imports
from router import Router
from nerf import NerfAPI
from gui import Gui

# ============================================= #
#  CONSTANTS & GLOBALS
# ============================================= #

VERSION = '6.0.0'

router = Router()
nerfAPI = NerfAPI(config.get('nerf-cookie'))
root = tk.Tk()
gui = Gui(root, config)

# ============================================= #
#  FUNCTIONS
# ============================================= #

def validate_cookie():
    lr.Log.info('Validating cookie...')

    is_valid = nerfAPI.validate_cookie()
    if is_valid:
        lr.Log.info('Cookie is valid!')
        gui.set_status('Your cookie is valid!')
    else:
        lr.Log.error('Cookie is invalid!')
        gui.set_status("Your cookie is invalid! Make sure it's fresh.", is_bad=True)

def connect():
    lr.Log.info('Connecting to map server...')
    gui.set_status('Connecting to map server...')

    online:dict = config.get('online', {})
    router.connect(online.get('server-ip'), online.get('server-port'),
                   online.get('password'))

    if router.is_connected():
        gui.set_status('Connected to map server successfully!')
        lr.Log.info('Connected to map server successfully!')
    else:
        lr.Log.error("Couldn't connect to map server!")
        gui.set_status("Couldn't connect to map server!", is_bad=True)

def send_client_update():
    lr.Log.debug('Sending client information.')
    profile = nerfAPI.get_profile()
    active = nerfAPI.get_active_dino()
    playtime = nerfAPI.get_playtime()

    router.send_client_information(profile | active | { 'playtime': playtime })

def startup():
    validate_cookie()
    connect()

    if router.is_connected():
        gui.my_client_id = router.client_id
        router.client_list_updated_external_callback = gui.display_clients_information
        gui.send_tp_request_callback = nerfAPI.send_teleport
        gui.accept_tp_request_callback = nerfAPI.accept_teleports

        while True:
            send_client_update()
            gui.display_clients_information(router.get_latest_clients_data())

            teleport_requests = nerfAPI.get_pending_teleports()
            if len(teleport_requests) > 0:
                gui.update_pending_teleports(teleport_requests)

            time.sleep(5)

# ============================================= #
#  MAIN
# ============================================= #

def main():
    """
    **Main entrypoint.**
    """
    
    root.wm_title(f'Nerf TheIsle Online Dash v{VERSION}')
    root.wm_minsize(1920 // 3, 1080 // 3)
    gui.pack(fill='both', expand=True)

    threading.Thread(target=startup, daemon=True).start()

    gui.mainloop()

if __name__ == '__main__':
    main()