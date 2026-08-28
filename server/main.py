from pathlib import Path
import json, sys

# ============================================= #
#  SETUP
# ============================================= #

# Attempt to import non-native packages
try:
    from aiohttp import web
    import loggerric as lr
    import socketio
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

# ============================================= #
#  CONSTANTS & GLOBALS
# ============================================= #



# ============================================= #
#  MAIN
# ============================================= #

def main():
    """
    **Main entrypoint.**
    """

    router = Router(config.get('password'))
    router.host(config.get('port'))
    
if __name__ == '__main__':
    main()