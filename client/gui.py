from PIL import Image, ImageTk
from datetime import datetime
from pathlib import Path
from tkinter import ttk
import loggerric as lr
import tkinter as tk
import sys, math, re

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
                    (48, 48), Image.Resampling.LANCZOS)
            except:
                file = 'assets/fraigl_star.png'
                self.__map_icons[specie] = Image.open(file).convert('RGBA').resize(
                    (32, 32), Image.Resampling.LANCZOS)

        self.__client_frames:dict[str, dict[str, tk.Widget]] = {}
        self.__local_coords_copy:dict[str, list] = {}
        self.__local_heatmap_copy:list[dict] = []

        self.__skin_presets:dict = {}

        self.send_tp_request_callback = None
        self.accept_tp_request_callback = None
        self.apply_skin_external_call = None
        self.parking_button_callback = None

        map_config:dict = self.__config.get('map', {})
        self.__base_map_image = Image.open(map_config.get('filename'))

        self.__migration_overlay_image = Image.open(map_config.get('migration'))
        self.__patrol_overlay_image = Image.open(map_config.get('patrol'))
        self.__sanctuary_overlay_image = Image.open(map_config.get('sanctuary'))

        self.my_client_id = ''
        self.__local_copy_clients_data:dict[str, dict] = None

        style = ttk.Style()
        style.theme_use('clam')

        self.population = {}
        self.friends = {}

        menubar = tk.Menu(self.__root)
        self.population_menu = tk.Menu(menubar, tearoff=0)
        self.friends_menu = tk.Menu(menubar, tearoff=0)
        self.heatmap_menu = tk.Menu(menubar, tearoff=0)
        
        menubar.add_cascade(label="Population", menu=self.population_menu)
        menubar.add_cascade(label="Friends", menu=self.friends_menu)
        menubar.add_cascade(label='Heatmap', menu=self.heatmap_menu)

        self.heatmap_type_var = tk.StringVar(value='Inclusive Heat')

        self.heatmap_menu.add_radiobutton(
            label='All-Inclusive Dots',
            variable=self.heatmap_type_var,
            value='All-Inclusive Dots',
            command=self.render_map
        )

        self.heatmap_menu.add_radiobutton(
            label='Aggressive Heat',
            variable=self.heatmap_type_var,
            value='Aggressive Heat',
            command=self.render_map
        )

        self.heatmap_menu.add_radiobutton(
            label='Inclusive Heat',
            variable=self.heatmap_type_var,
            value='Inclusive Heat',
            command=self.render_map
        )

        self.heatmap_menu.add_radiobutton(
            label='Individual Heat',
            variable=self.heatmap_type_var,
            value='Individual Heat',
            command=self.render_map
        )

        self.heatmap_menu.add_radiobutton(
            label='Persistant Heat',
            variable=self.heatmap_type_var,
            value='Persistant Heat',
            command=self.render_map
        )
        
        self.__root.config(menu=menubar)

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

    def _switch_heatmap_type(self, new_type:str):
        self._heatmap_type = new_type

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

    def __extract_own_coords(self) -> tuple | list:
        try:
            return self.__local_coords_copy.get(self.my_client_id or '?', [(0, 0)])[-1]
        except IndexError:
            return [(0, 0)]

    def update_map(self, coords:dict[str, list]):
        self.__local_coords_copy = coords
        self.render_map()
        self.calc_nearby_players_count(self.__extract_own_coords())

    def on_new_heatmap_coords(self, positions:list[dict]):
        self.__local_heatmap_copy = positions
        self.render_map()
        self.calc_nearby_players_count(self.__extract_own_coords())

    def is_heatmap_toggled(self) -> bool:
        return self.__heatmap_toggled_var.get()

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

    def _attempt_park(self):
        if self.parking_button_callback:
            self.parking_button_callback()

    def display_clients_information(self, clients_data:dict[str, dict]):
        self.__local_copy_clients_data = clients_data
        
        for client_id, widgets in self.__client_frames.copy().items():
            if client_id in list(clients_data.keys()): continue

            widgets['background'].grid_remove()
            del self.__client_frames[client_id]

        current_row = 0 

        for client_id, data in clients_data.items():
            if not data.get('username'): continue

            if not self.__client_frames.get(client_id):
                background = tk.Frame(self.__player_frame, highlightthickness=2,
                                      highlightbackground='#909090')

                background.grid(row=current_row, column=0, padx=10, pady=5, sticky='nsew')
                background.grid_columnconfigure([1, 3], weight=1)

                strainer = tk.Label(background, width=25)
                strainer.grid(row=0, column=0, columnspan=3, padx=0, pady=0, sticky='n')

                flair = tk.Label(background, background=data.get('color', '#000000'),
                                 width=1)
                flair.grid(row=0, column=0, sticky='nsew')

                lframe = tk.Frame(background)
                lframe.grid(row=0, column=1, padx=2, pady=2, sticky='nsew')
                lframe.grid_columnconfigure(1, weight=1)

                username_str = (f"{data.get('username', 'LOADING...')}"
                    + f" • lvl {data.get('level', '?')}")
                username = ttk.Label(lframe, text=username_str, background='#F0F0F0',
                                     width=20, font=('Seoge UI', 9, 'bold'))
                username.grid(row=0, column=0, padx=5, pady=(5, 0), sticky='nsew')

                is_prime = data.get('is_prime', False)
                prime_icon = self.__prime_star if is_prime else self.__fraigl_star
                species = ttk.Label(lframe, text=data.get('species', 'LOADING...'),
                                    font=('Seoge UI', 8), background='#F0F0F0',
                                    compound='left', image=prime_icon)
                species.grid(row=1, column=0, padx=5, pady=(0, 5), sticky='nsew')

                bones = ttk.Label(lframe, text=f"{data.get('bones', 0):,}",
                                  image=self.__bones, compound='left',
                                  font=('Seoge UI', 8), background='#F0F0F0')
                bones.grid(row=2, column=0, padx=5, pady=(0, 1), sticky='nsew')

                meat = ttk.Label(lframe, text=f"{data.get('meat', 0):,}",
                                 image=self.__meat, compound='left',
                                  font=('Seoge UI', 8), background='#F0F0F0')
                meat.grid(row=2, column=0, padx=(75, 5), pady=(0, 1), sticky='nsew')

                playtime = ttk.Label(lframe, text=data.get('playtime', '0h 0m'),
                                  image=self.__playtime, compound='left',
                                  font=('Seoge UI', 7), background='#F0F0F0')
                playtime.grid(row=3, column=0, padx=5, pady=5, sticky='nsew')

                send_btn = None
                accept_btn = None
                btn_frame = tk.Frame(lframe)
                btn_frame.grid(row=3, column=0, padx=(75, 5), pady=5, sticky='w')
                if self.my_client_id != client_id:
                    btn_frame.grid_columnconfigure([0, 1], weight=1)

                    send_btn = tk.Button(btn_frame, text='STP', width=4,
                        command=lambda cid=client_id: self.__tp_btn_send(cid))
                    send_btn.grid(row=0, column=0, padx=(0, 2), sticky='nsew')

                    accept_btn = tk.Button(btn_frame, text='ATP', width=4,
                        state='disabled',
                        command=lambda cid=client_id: self.__tp_btn_accept(cid))
                    accept_btn.grid(row=0, column=1, padx=(2, 0), sticky='nsew')
                else:
                    btn_frame.grid_columnconfigure(0, weight=1)

                    park_btn = tk.Button(btn_frame, text='PARK', width=10, command=self._attempt_park)
                    park_btn.grid(row=0, column=0, columnspan=2, padx=(2, 2), sticky='nsew')

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

                    value_lbl = ttk.Label(row_frame, text=f'{value * 100:.1f}%', width=8,
                                      background='#F1F1F1')
                    value_lbl.grid(row=0, column=2, padx=2, pady=0, sticky='nsew')

                    row_widgets[key] = {
                        'frame': row_frame, 'icon': icon, 'progress': progress,
                        'value': value_lbl
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
                
                widgets['background'].grid(row=current_row, column=0, padx=10, pady=5,
                                           sticky='nsew')

                username_str = (f"{data.get('username', 'LOADING...')}"
                    + f" • lvl {data.get('level', '?')}")
                widgets['username'].configure(text=username_str)

                is_prime = data.get('is_prime', False)
                prime_icon = self.__prime_star if is_prime else self.__fraigl_star
                widgets['species'].configure(text=data.get('species', 'LOADING...'),
                                             image=prime_icon)

                widgets['bones'].configure(text=f"{data.get('bones', 0):,}")
                widgets['meat'].configure(text=f"{data.get('meat', 0):,}")
                widgets['playtime'].configure(text=data.get('playtime', '0h 0m'))

                for key, row_widgets in widgets.get('row_widgets', {}).items():
                    val = data.get('vitals', {}).get(key)
                    if val == None:
                        val = data.get('growth', 0)
                    row_widgets['progress'].configure(value=val * 100)
                    row_widgets['value'].configure(text=f'{val * 100:.2f}%')
            
            current_row += 1

    def set_status(self, status:str, is_bad:bool=False):
        now = datetime.now()
        ts = f'{now.hour:02d}:{now.minute:02d}:{now.second:02d}'

        self.__status_bar.configure(text=f'[{ts}] {status}',
                                    foreground='red' if is_bad else 'black')

    def render_map(self, *args):
        width = self.__canvas_frame.winfo_width()
        height = self.__canvas_frame.winfo_height()

        map_img = renderer.resize_map(self.__base_map_image, width, height)
        
        bg_color = map_img.getpixel((0, 0))
        
        map_img = renderer.draw_grid(map_img, size=8)

        map_config:dict = self.__config.get('map', {})
        bounds = map_config.get('bounds', {})

        if self.is_heatmap_toggled():
            map_img = renderer.apply_heatmap(map_img, self.__local_heatmap_copy, bounds, self.heatmap_type_var.get())

        if self.__local_copy_clients_data:
            data = {}
            for client_id, client_data in self.__local_copy_clients_data.items():
                data[client_id] = {
                    'coords': self.__local_coords_copy.get(client_id, []),
                    'color': client_data.get('color', '#000000'),
                    'icon': self.__map_icons.get(client_data.get('species', 'Troodon'))
                }
        
            map_img = renderer.coordinates(map_img, data, bounds)

        if self.__migration_toggled_var.get():
            map_img = renderer.apply_overlay(map_img, self.__migration_overlay_image)
        if self.__patrol_toggled_var.get():
            map_img = renderer.apply_overlay(map_img, self.__patrol_overlay_image)
        if self.__sanctuary_toggled_var.get():
            map_img = renderer.apply_overlay(map_img, self.__sanctuary_overlay_image)

        final_map = renderer.add_letterbox(map_img, width, height, bg_color)

        self.__canvas.delete('all')
        self.__tk_image = ImageTk.PhotoImage(final_map)
        self.__canvas_image_id = self.__canvas.create_image(0, 0, anchor='nw',
                                                            image=self.__tk_image)

    def on_skin_list(self, skin_presets:dict):
        self.__skin_presets = skin_presets

        keys = list(self.__skin_presets.keys())
        self.__skin_options['values'] = keys
        if keys:
            self.__skin_options.current(0)

    def calc_nearby_players_count(self, target: dict | list | tuple | str, radius: float = 100_000.0):
        """
        Returns the number of player positions from the heatmap within `radius` units
        of the target position or client ID.
        """

        def parse_coords(pos):
            if isinstance(pos, dict):
                x = pos.get("x", 0.0)
                y = pos.get("y", pos.get("z", 0.0))
                return x, y
            elif isinstance(pos, (list, tuple)) and len(pos) >= 2:
                return pos[0], pos[1]
            return None

        if isinstance(target, str):
            target_coords = self.__local_coords_copy.get(target, [])
            target_pos = parse_coords(target_coords)
        else:
            target_pos = parse_coords(target)

        if target_pos is None:
            return 0

        tx, ty = target_pos
        nearby_count = 0

        for pos in self.__local_heatmap_copy:
            p_coords = parse_coords(pos)
            if p_coords is None:
                continue

            px, py = p_coords
            distance = math.hypot(px - tx, py - ty)

            if distance <= radius:
                nearby_count += 1

        lr.Log.debug(f'Nearby Players at: {target} (non-scaled): {nearby_count:,}')
        self.__nearby_var.set(f'Nearby Players: ~{math.ceil(nearby_count / 30)}')

    def update_population(self, population: dict):
        self.population = population.copy()

        self.species_limits = {
            'Tyrannosaurus': 15, 'Allosaurus': 25, 'Deinosuchus': 25,
            'Ceratosaurus': 38, 'Carnotaurus': 38, 'Dilophosaurus': 45,
            'Omniraptor': 40, 'Austroraptor': 45, 'Herrerasaurus': 45,
            'Troodon': 50, 'Pteranodon': 65,
            'Stegosaurus': 40, 'Triceratops': 30, 'Diabloceratops': 44,
            'Maiasaura': 38, 'Tenontosaurus': 45, 'Pachycephalosaurus': 50,
            'Dryosaurus': 70, 'Hypsilophodon': 70, 'Kentrosaurus': 50,
            'Beipiaosaurus': 70, 'Gallimimus': 55, 'Oviraptor': 60
        }

        self.population_menu.delete(0, "end")

        diets = {
            'Carnivore': ['Tyrannosaurus', 'Allosaurus', 'Deinosuchus', 'Ceratosaurus',
                          'Carnotaurus', 'Dilophosaurus', 'Omniraptor', 'Austroraptor',
                          'Herrerasaurus', 'Troodon', 'Pteranodon'],
            'Herbivore': ['Stegosaurus', 'Triceratops', 'Diabloceratops', 'Maiasaura', 
                          'Tenontosaurus', 'Pachycephalosaurus', 'Dryosaurus', 
                          'Hypsilophodon', 'Kentrosaurus'],
            'Omnivore': ['Beipiaosaurus', 'Gallimimus', 'Oviraptor']
        }

        categorized = {'Carnivore': [], 'Herbivore': [], 'Omnivore': [], 'Unknown': []}
        for dino, count in population.items():
            placed = False
            for diet_name, species_list in diets.items():
                if dino in species_list:
                    categorized[diet_name].append((dino, count))
                    placed = True
                    break
            
            if not placed:
                categorized['Unknown'].append((dino, count))

        first_section = True
        for diet_name in ['Carnivore', 'Herbivore', 'Omnivore', 'Unknown']:
            items = categorized[diet_name]
            if not items:
                continue
            
            if not first_section:
                self.population_menu.add_separator()
            first_section = False

            items.sort(key=lambda x: x[1], reverse=True)

            for dino, count in items:
                limit = self.species_limits.get(dino, '?')
                
                is_over_limit = isinstance(limit, int) and count >= limit
                label_text = f"{dino} - {count}/{limit}"

                if is_over_limit:
                    self.population_menu.add_command(label=label_text, font=("TkMenuFont", 10, "bold"))
                else:
                    self.population_menu.add_command(label=label_text)

    def _update_menu(self, old: dict, new: dict, menu):
        for key, value in new.items():
            if key not in old or old[key] != value:
                
                limit = getattr(self, 'species_limits', {}).get(key, '?')
                is_over_limit = isinstance(limit, int) and value >= limit
                label_text = f"{key} - {value}/{limit}"
                font_setting = ("TkMenuFont", 10, "bold") if is_over_limit else ("TkMenuFont", 10, "normal")

                if key not in old:
                    menu.add_command(label=label_text, font=font_setting)
                else:
                    index = self._find_menu_entry(menu, key)
                    if index is not None:
                        menu.entryconfig(index, label=label_text, font=font_setting)

        for key in old:
            if key not in new:
                index = self._find_menu_entry(menu, key)
                if index is not None:
                    menu.delete(index)

    def _find_menu_entry(self, menu, key):
        end_idx = menu.index("end")
        if end_idx is None:
            return None

        for i in range(end_idx + 1):
            if menu.type(i) == "command":
                label = menu.entrycget(i, "label")
                if label.startswith(f"{key} - "):
                    return i

        return None


    def update_friends(self, friends: dict):
        self.friends = friends.copy()

        self.friends_menu.delete(0, "end")

        online = []
        offline = []

        def parse_time_to_seconds(time_str: str) -> int:
            """Converts strings like '15m', '2h', or '1h 30m' into total seconds for sorting."""
            total_seconds = 0
            matches = re.findall(r'(\d+)\s*([smhd])', time_str.lower())
            
            if matches:
                for val, unit in matches:
                    val = int(val)
                    if unit == 's': total_seconds += val
                    elif unit == 'm': total_seconds += val * 60
                    elif unit == 'h': total_seconds += val * 3600
                    elif unit == 'd': total_seconds += val * 86400
                return total_seconds
            
            return float('inf')

        for name, status in friends.items():
            status_str = str(status)
            
            if any(char.isdigit() for char in status_str):
                offline.append((name, status_str))
            else:
                online.append((name, status_str))

        offline.sort(key=lambda x: parse_time_to_seconds(x[1]))

        online.sort(key=lambda x: x[0].lower())

        for name, status in online:
            self.friends_menu.add_command(label=f"{name} - {status}")

        if online and offline:
            self.friends_menu.add_separator()

        for name, status in offline:
            self.friends_menu.add_command(label=f"{name} - {status}")

    def __apply_skin_callback(self):
        if self.apply_skin_external_call:
            skin:dict = self.__skin_presets.get(self.__skin_options_var.get())

            def hex_to_rgb(hex_color:str) -> dict[str, int]:
                hex_color = hex_color.lstrip('#')

                if len(hex_color) == 3:
                    hex_color = ''.join(c * 2 for c in hex_color)

                return {
                    'r': int(hex_color[0:2], 16),
                    'g': int(hex_color[2:4], 16),
                    'b': int(hex_color[4:6], 16),
                }

            self.apply_skin_external_call({
                'gender': 'm' if self.__male_radio_var.get() else 'f',
                'skinVariation': int(skin.get('patternVariation', 0)),
                'pattern': int(skin.get('pattern', 0)),
                'glitchSkin': False,
                'server': 'EU'
            } | { k: hex_to_rgb(v) for k, v in skin.get('colors', {}).items()})

    def __toggle_heatmap_calback(self):
        self.render_map()

    def __toggle_migration_calback(self):
        self.render_map()

    def __toggle_patrol_calback(self):
        self.render_map()

    def __toggle_sanctuary_calback(self):
        self.render_map()

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

        sidebar_frame = tk.Frame(self, background='#b1b1b1')
        sidebar_frame.grid(row=0, column=1, sticky='nsew')
        sidebar_frame.grid_rowconfigure(0, weight=1)
        sidebar_frame.grid_columnconfigure(0, weight=1)

        self.__player_frame = tk.Frame(sidebar_frame, background='#b1b1b1')
        self.__player_frame.grid(row=0, column=0, sticky='nsew')
        self.__player_frame.grid_columnconfigure(0, weight=1)

        options_frame = tk.Frame(sidebar_frame, background='#c1c1c1')
        options_frame.grid(row=1, column=0, sticky='sew')

        self.__heatmap_toggled_var = tk.BooleanVar(value=False)
        toggle_heatmap = tk.Checkbutton(options_frame, text='Heatmap',
            background='#c1c1c1', activebackground='#c1c1c1',
            command=self.__toggle_heatmap_calback, variable=self.__heatmap_toggled_var)
        toggle_heatmap.grid(row=0, column=0, padx=10, pady=3, sticky='nsew')

        self.__skin_options_var = tk.StringVar()
        self.__skin_options = ttk.Combobox(options_frame, state='readonly', width=15,
                                           textvariable=self.__skin_options_var)
        self.__skin_options.grid(row=0, column=1, padx=(5, 1), pady=3, sticky='nsew')

        skin_apply = ttk.Button(options_frame, text='Apply Skin',
                                command=self.__apply_skin_callback)
        skin_apply.grid(row=0, column=2, padx=(1, 2), pady=3, sticky='nsew')

        self.__male_radio_var = tk.BooleanVar(value=True)
        male_radio = tk.Radiobutton(options_frame, text='M', value=1,
            background='#c1c1c1', activebackground='#c1c1c1',
            variable=self.__male_radio_var)
        male_radio.grid(row=0, column=3, padx=2, pady=3, sticky='nsew')
        female_radio = tk.Radiobutton(options_frame, text='F', value=0,
            background='#c1c1c1', activebackground='#c1c1c1',
            variable=self.__male_radio_var)
        female_radio.grid(row=0, column=4, padx=(2, 5), pady=3, sticky='nsew')

        zone_frame = tk.Frame(options_frame, background='#c1c1c1')
        zone_frame.grid(row=1, column=0, columnspan=5, padx=0, pady=0, sticky='nsew')

        self.__migration_toggled_var = tk.BooleanVar(value=False)
        toggle_migration = tk.Checkbutton(zone_frame, text='Migration',
            background='#c1c1c1', activebackground='#c1c1c1',
            command=self.__toggle_migration_calback, variable=self.__migration_toggled_var)
        toggle_migration.grid(row=0, column=0, padx=10, pady=3, sticky='nsew')

        self.__patrol_toggled_var = tk.BooleanVar(value=False)
        toggle_patrol = tk.Checkbutton(zone_frame, text='Patrol',
            background='#c1c1c1', activebackground='#c1c1c1',
            command=self.__toggle_patrol_calback, variable=self.__patrol_toggled_var)
        toggle_patrol.grid(row=0, column=1, padx=10, pady=3, sticky='nsew')

        self.__sanctuary_toggled_var = tk.BooleanVar(value=False)
        toggle_sanctuary = tk.Checkbutton(zone_frame, text='Sanctuary',
            background='#c1c1c1', activebackground='#c1c1c1',
            command=self.__toggle_sanctuary_calback, variable=self.__sanctuary_toggled_var)
        toggle_sanctuary.grid(row=0, column=2, padx=10, pady=3, sticky='nsew')

        self.__nearby_var = tk.StringVar(value='Nearby Players: ?')
        tk.Label(zone_frame, textvariable=self.__nearby_var, background='#c1c1c1').grid(row=0, column=3, padx=(20, 5), pady=3, sticky='nsew')

        self.__status_bar = tk.Label(self, background='#b1b1b1')
        self.__status_bar.grid(row=1, column=0, columnspan=2, sticky='nsew')