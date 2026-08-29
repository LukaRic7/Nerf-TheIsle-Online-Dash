from PIL import Image, ImageTk
from datetime import datetime
import threading, time, sys
from pathlib import Path
from tkinter import ttk
import loggerric as lr
import tkinter as tk

# Check if the program is running interpreted or PyInstaller compiled
if not getattr(sys, 'frozen', False):
    # Dynamically find the project root and add to sys.path so Python can find 'shared/'
    current_dir = Path(__file__).resolve().parent
    project_root = current_dir.parent
    
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

import renderer

class Gui(ttk.Frame):
    def __init__(self, root:tk.Tk, config:dict):
        self.__root = root
        self.__config = config

        super().__init__(self.__root)

        self.__canvas_frame:ttk.Frame = None
        self.__canvas:tk.Canvas = None
        self.__tk_image:ImageTk.PhotoImage = None
        self.__canvas_image_id:int = None
        self.__status_bar:tk.Label = None

        self.__fraigl_star = tk.PhotoImage(file='assets/fraigl_star.png').subsample(2)
        self.__prime_star = tk.PhotoImage(file='assets/prime_star.png').subsample(2)
        self.__health = tk.PhotoImage(file='assets/health.png')
        self.__stamina = tk.PhotoImage(file='assets/stamina.png')
        self.__food = tk.PhotoImage(file='assets/food.png')
        self.__water = tk.PhotoImage(file='assets/water.png')
        self.__growth = tk.PhotoImage(file='assets/growth.png')
        self.__bones = tk.PhotoImage(file='assets/bones.png').subsample(3)
        self.__meat = tk.PhotoImage(file='assets/meat.png').subsample(3)
        self.__playtime = tk.PhotoImage(file='assets/playtime.png').subsample(35)

        self.__pending_formatted = {}

        self.__map_icons:dict[str, Image.Image] = {}
        species = ['Tyrannosaurus', 'Allosaurus', 'Deinosuchus', 'Ceratosaurus',
                   'Carnotaurus', 'Dilophosaurus', 'Omniraptor', 'Austroraptor',
                   'Herrerasaurus', 'Troodon', 'Pteranodon', 'Stegosaurus',
                   'Triceratops', 'Diabloceratops', 'Maiasaura', 'Tenotosaurus',
                   'Pachycephalosaurus', 'Dryosaurus', 'Hypsilophodon', 'Kentrosaurus',
                   'Beipiaosaurus', 'Gallimimus']
        for specie in species:
            try:
                file = f'assets/{specie}.png'
                self.__map_icons[specie] = Image.open(file).convert('RGBA').resize(
                    (64, 64), Image.Resampling.LANCZOS)
            except:
                file = 'assets/fraigl_star.png'
                self.__map_icons[specie] = Image.open(file).convert('RGBA').resize(
                    (64, 64), Image.Resampling.LANCZOS)

        self.__client_frames:dict[str, dict[str, tk.Widget]] = {}
        self.__local_coords_copy:dict[str, list] = {}

        self.send_tp_request_callback = None
        self.accept_tp_request_callback = None

        map_config:dict = self.__config.get('map', {})
        self.__base_map_image = Image.open(map_config.get('filename'))

        self.my_client_id = ''
        self.__local_copy_clients_data:dict[str, dict] = None

        style = ttk.Style()
        style.theme_use('clam')

        self.__progressbar_colors = {
            'health': '#C0392B', 'stamina': '#F1C40F', 'food': '#D35400',
            'water': '#2980B9', 'growth': '#27AE60'
        }
        for name, color in self.__progressbar_colors.items():
            style.configure(f'{name}.Horizontal.TProgressbar', foreground=color,
                            bordercolor='#F1F1F1', troughbordercolor='#F1F1F1',
                            background=color, troughcolor='#F1F1F1', borderwidth=0,
                            thickness=5, relief='flat')
            style.layout(f'{name}.Horizontal.TProgressbar', [
                ('Progressbar.trough', {
                    'children': [
                        ('Progressbar.pbar', {'side': 'left', 'sticky': 'ns'})
                    ], 'sticky': 'nswe'
                })
            ])

        self.__add_widgets()
        self.render_map()

    def update_pending_teleports(self, pending_clients:list[dict]):
        for client in pending_clients:
            self.__pending_formatted[client.get('discord_id')] = client.get('request_id')

        if pending_clients:
            lr.Log.debug(f'There is {len(pending_clients)} tp requests pending.')

        pending_client_ids:dict[str, dict] = {}
        for client_id, data in self.__local_copy_clients_data.items():
            discord_id = data.get('discord_id', '')
            if discord_id in list(self.__pending_formatted.keys()):
                pending_client_ids[client_id] = {
                    'discord_id': discord_id,
                    'request_id': self.__pending_formatted.get(discord_id)
                }

        for client_id, data in pending_client_ids.items():
            if self.__client_frames[client_id]:
                self.__client_frames[client_id]['accept_btn'].configure(state='active')

    def update_map(self, coords:dict[str, list]):
        self.__local_coords_copy = coords
        self.render_map()

    def __tp_btn_send(self, btn_owner_client_id:str):
        lr.Log.debug(f'Sending teleport request to: {btn_owner_client_id}',
                     highlight=btn_owner_client_id)

        if (self.send_tp_request_callback):
            client_data = self.__local_copy_clients_data.get(btn_owner_client_id, {})
            discord_id = client_data.get('discord_id')
            if discord_id:
                response:dict = self.send_tp_request_callback(discord_id)
                message:str = response.get('message') or response.get('error')
                is_bad:bool = len(response.get('error', ''))
                if message:
                    self.set_status(message, is_bad)

    def __tp_btn_accept(self, btn_owner_client_id:str):
        lr.Log.debug(f'Accepting teleport request from: {btn_owner_client_id}',
                     highlight=btn_owner_client_id)

        client_data = self.__local_copy_clients_data.get(btn_owner_client_id)
        discord_id = client_data.get('discord_id')
        request_id = self.__pending_formatted.get(discord_id)
        
        response:dict = self.accept_tp_request_callback(request_id)
        message:str = response.get('message') or response.get('error')
        is_bad:bool = len(response.get('error', ''))
        if message:
            self.set_status(message, is_bad)

        self.__client_frames[btn_owner_client_id]['accept_btn'].configure(state='disabled')

    def display_clients_information(self, clients_data:dict[str, dict]):
        self.__local_copy_clients_data = clients_data
        for client_id, widgets in self.__client_frames.copy().items():
            if client_id in list(clients_data.keys()): continue

            widgets['background'].grid_remove()
            del self.__client_frames[client_id]

        for client_id, data in clients_data.items():
            if not self.__client_frames.get(client_id):
                if not data.get('username'): continue

                row = len(self.__client_frames)

                background = tk.Frame(self.__sidebar_frame, highlightthickness=2,
                                      highlightbackground='#909090')
                background.grid(row=row, column=0, padx=10, pady=10, sticky='nsew')
                background.grid_columnconfigure([1, 3], weight=1)

                strainer = tk.Label(background, width=25)
                strainer.grid(row=0, column=0, columnspan=3, padx=0, pady=0, sticky='n')

                flair = tk.Label(background, background=data.get('color', '#000000'),
                                 width=1)
                flair.grid(row=0, column=0, sticky='nsew')

                lframe = tk.Frame(background)
                lframe.grid(row=0, column=1, padx=2, pady=2, sticky='nsew')
                lframe.grid_columnconfigure(1, weight=1)

                username_str = (f'{data.get('username', 'LOADING...')}'
                    + f' • lvl {data.get('level', '?')}')
                username = ttk.Label(lframe, text=username_str, background='#F0F0F0',
                                     width=20, font=('Seoge UI', 9, 'bold'))
                username.grid(row=0, column=0, padx=5, pady=(5, 0), sticky='nsew')

                is_prime = data.get('is_prime', False)
                prime_icon = self.__prime_star if is_prime else self.__fraigl_star
                species = ttk.Label(lframe, text=data.get('species', 'LOADING...'),
                                    font=('Seoge UI', 8), background='#F0F0F0',
                                    compound='left', image=prime_icon)
                species.grid(row=1, column=0, padx=5, pady=(0, 5), sticky='nsew')

                bones = ttk.Label(lframe, text=f'{data.get('bones', 0):,}',
                                  image=self.__bones, compound='left',
                                  font=('Seoge UI', 8), background='#F0F0F0')
                bones.grid(row=2, column=0, padx=5, pady=(0, 1), sticky='nsew')

                meat = ttk.Label(lframe, text=f'{data.get('meat', 0):,}',
                                 image=self.__meat, compound='left',
                                  font=('Seoge UI', 8), background='#F0F0F0')
                meat.grid(row=2, column=0, padx=(75, 5), pady=(0, 1), sticky='nsew')

                playtime = ttk.Label(lframe, text=data.get('playtime', '0h 0m'),
                                  image=self.__playtime, compound='left',
                                  font=('Seoge UI', 7), background='#F0F0F0')
                playtime.grid(row=3, column=0, padx=5, pady=5, sticky='nsew')

                send_btn = None
                accept_btn = None
                if self.my_client_id != client_id:
                    btn_frame = tk.Frame(lframe)
                    btn_frame.grid(row=3, column=0, padx=(75, 5), pady=5, sticky='w')
                    btn_frame.grid_columnconfigure([0, 1], weight=1)

                    send_btn = tk.Button(btn_frame, text='STP', width=4,
                        command=lambda cid=client_id: self.__tp_btn_send(cid))
                    send_btn.grid(row=0, column=0, padx=(0, 2), sticky='nsew')

                    accept_btn = tk.Button(btn_frame, text='ATP', width=4,
                        state='disabled',
                        command=lambda cid=client_id: self.__tp_btn_accept(cid))
                    accept_btn.grid(row=0, column=1, padx=(2, 0), sticky='nsew')

                seperator = ttk.Separator(background, orient='vertical')
                seperator.grid(row=0, column=2, padx=2, pady=10, sticky='nsew')

                rframe = tk.Frame(background)
                rframe.grid(row=0, column=3, padx=2, pady=2, sticky='nsew')
                rframe.grid_columnconfigure(1, weight=1)

                row_widgets:dict[str, dict] = {}
                bars:dict = data.get('vitals', {}) | { 'growth': data.get('growth', 0) }
                for index, (key, value) in enumerate(bars.items()):
                    row_frame = tk.Frame(rframe)
                    row_frame.grid(row=index, column=0, padx=5, pady=1, sticky='nsew')
                    row_frame.grid_columnconfigure(1, weight=1)

                    icon_lookup = {
                        'health': self.__health, 'stamina': self.__stamina,
                        'food': self.__food, 'water': self.__water,
                        'growth': self.__growth
                    }

                    icon = tk.Label(row_frame, image=icon_lookup[key])
                    icon.grid(row=0, column=0, padx=2, pady=0, sticky='nsew')

                    progress = ttk.Progressbar(row_frame, value=value * 100,
                                               style=f'{key}.Horizontal.TProgressbar',
                                               mode='determinate')
                    progress.grid(row=0, column=1, padx=2, pady=0, sticky='nsew')

                    value = ttk.Label(row_frame, text=f'{value * 100:.1f}%', width=8,
                                      background='#F1F1F1')
                    value.grid(row=0, column=2, padx=2, pady=0, sticky='nsew')

                    row_widgets[key] = {
                        'frame': row_frame, 'icon': icon, 'progress': progress,
                        'value': value
                    }

                self.__client_frames[client_id] = {
                    'background': background, 'flair': flair, 'lframe': lframe,
                    'rframe': rframe, 'username': username, 'species': species,
                    'row_widgets': row_widgets, 'seperator': seperator, 'bones': bones,
                    'meat': meat, 'playtime': playtime, 'tp_btn': send_btn,
                    'accept_btn': accept_btn
                }
            else:
                widgets = self.__client_frames[client_id]

                username_str = (f'{data.get('username', 'LOADING...')}'
                    + f' • lvl {data.get('level', '?')}')
                widgets['username'].configure(text=username_str)

                is_prime = data.get('is_prime', False)
                prime_icon = self.__prime_star if is_prime else self.__fraigl_star
                widgets['species'].configure(text=data.get('species', 'LOADING...'),
                                             image=prime_icon)

                widgets['bones'].configure(text=f'{data.get('bones', 0):,}')
                widgets['meat'].configure(text=f'{data.get('meat', 0):,}')
                widgets['playtime'].configure(text=data.get('playtime', '0h 0m'))

                for key, row_widgets in widgets.get('row_widgets', {}).items():
                    val = data.get('vitals', {}).get(key)
                    if val == None:
                        val = data.get('growth', 0)
                    row_widgets['progress'].configure(value=val * 100)
                    row_widgets['value'].configure(text=f'{val * 100:.2f}%')

    def set_status(self, status:str, is_bad:bool=False):
        now = datetime.now()
        ts = f'{now.hour:02d}:{now.minute:02d}:{now.second:02d}'

        self.__status_bar.configure(text=f'[{ts}] {status}',
                                    foreground='red' if is_bad else 'black')

    def render_map(self, *args):
        width = self.__canvas_frame.winfo_width()
        height = self.__canvas_frame.winfo_height()

        map = renderer.letterbox_and_grid(self.__base_map_image, width, height)

        map_config:dict = self.__config.get('map', {})
        bounds = map_config.get('bounds', {})

        if self.__local_copy_clients_data:
            data = {}
            for client_id, client_data in self.__local_copy_clients_data.items():
                data[client_id] = {
                    'coords': self.__local_coords_copy.get(client_id, []),
                    'color': client_data.get('color', '#000000'),
                    'icon': self.__map_icons.get(client_data.get('species', 'Troodon'))
                }
        
            map = renderer.coordinates(map, data, bounds)

        self.__canvas.delete('all')
        self.__tk_image = ImageTk.PhotoImage(map)
        self.__canvas_image_id = self.__canvas.create_image(0, 0, anchor='nw',
                                                            image=self.__tk_image)

    def __add_widgets(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.__canvas_frame = ttk.Frame(self)
        self.__canvas_frame.grid(row=0, column=0, sticky='nsew')
        self.__canvas_frame.grid_rowconfigure(0, weight=1)
        self.__canvas_frame.grid_columnconfigure(0, weight=1)

        self.__canvas = tk.Canvas(self.__canvas_frame, background='black',
                                  highlightthickness=0)
        self.__canvas.grid(row=0, column=0, sticky='nsew')
        self.__canvas.bind('<Configure>', self.render_map)

        self.__sidebar_frame = tk.Frame(self, background='#b1b1b1')
        self.__sidebar_frame.grid(row=0, column=1, sticky='nsew')
        self.__sidebar_frame.grid_columnconfigure(0, weight=1)

        self.__status_bar = tk.Label(self, background='#c1c1c1')
        self.__status_bar.grid(row=1, column=0, columnspan=2, sticky='nsew')