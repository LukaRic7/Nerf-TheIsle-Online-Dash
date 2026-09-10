from PIL import Image, ImageDraw, ImageFilter
import loggerric as lr
import math, colorsys

def draw_grid(image:Image.Image, size:int=8) -> Image.Image:
    width, height = image.size
    cell_width = width / size
    cell_height = height / size
    color = (255, 255, 255, 128)

    overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Draw vertical lines
    for c in range(size + 1):
        x = int(c * cell_width) - int(c == size)
        draw.line((x, 0, x, height), fill=color, width=1)
    
    # Draw horizontal lines
    for r in range(size + 1):
        y = int(r * cell_height) - int(c == size)
        draw.line((0, y, width, y), fill=color, width=1)
    
    # Draw columns (letters)
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for c in range(size):
        letter = alphabet[c % 26]
        draw.text((int(c * cell_width) + 15, 5), letter, fill=color)
    
    # Draw rows (numbers)
    for r in range(size):
        draw.text((5, int(r * cell_height) + 15), str(r + 1), fill=color)

    return Image.alpha_composite(image, overlay)

def apply_overlay(image:Image.Image, overlay:Image.Image) -> Image.Image:
    overlay_resized = overlay.resize(image.size)

    return Image.alpha_composite(image, overlay_resized)

def resize_map(image: Image.Image, width: int, height: int) -> Image.Image:
    base_width, base_height = image.size
    scale_factor = min(width / base_width, height / base_height)
    new_size = (int(base_width * scale_factor), int(base_height * scale_factor))
    
    resized = image.resize(new_size, Image.Resampling.LANCZOS)
    return resized.convert('RGBA')

def add_letterbox(image: Image.Image, width: int, height: int, bg_color: tuple) -> Image.Image:
    canvas = Image.new('RGBA', (width, height), bg_color)
    
    paste_x = (width - image.width) // 2
    paste_y = (height - image.height) // 2
    
    canvas.paste(image, (paste_x, paste_y), image)
    return canvas

def apply_heatmap(image:Image.Image, positions:list[dict], bounds:dict, heat_type:str) -> Image.Image:
    lr.Log.debug(f'Applyed Heatmap Type: {heat_type}')

    INTERNAL_RES = 350
    DOT_RADIUS = 2

    if not positions:
        return image.convert('RGBA')

    w, h = image.size

    # Calculate internal dimensions keeping the aspect ratio
    scale = INTERNAL_RES / max(w, h)
    int_w = max(1, int(w * scale))
    int_h = max(1, int(h * scale))

    x_range = bounds['max-x'] - bounds['min-x'] or 1.0
    y_range = bounds['max-y'] - bounds['min-y'] or 1.0

    # Pre-map coordinates onto internal canvas space
    mapped_positions = []
    for pos in positions:
        x, y = pos.get('x'), pos.get('y')
        if x is None or y is None:
            continue
        px = int(((x - bounds['min-x']) / x_range) * int_w)
        py = int(((y - bounds['min-y']) / y_range) * int_h)
        
        item = pos.copy()
        item['px'] = px
        item['py'] = py
        mapped_positions.append(item)

    if not mapped_positions:
        return image.convert('RGBA')

    # Shared thermal palette generator
    def get_thermal_palette():
        palette = []
        for i in range(256):
            if i < 64:
                palette.extend([0, 0, int(i * 4)])
            elif i < 128:
                palette.extend([0, int((i - 64) * 4), 255 - int((i - 64) * 4)])
            elif i < 192:
                palette.extend([int((i - 128) * 4), 255, 0])
            else:
                palette.extend([255, 255 - int((i - 192) * 4), 0])
        return palette

    # -------------------------------------------------------------------------
    # MODE 1: All-Inclusive Dots
    # -------------------------------------------------------------------------
    if heat_type == 'All-Inclusive Dots':
        overlay = Image.new('RGBA', (int_w, int_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        for item in mapped_positions:
            px, py = item['px'], item['py']
            draw.ellipse(
                (px - DOT_RADIUS, py - DOT_RADIUS, px + DOT_RADIUS, py + DOT_RADIUS),
                fill=(255, 50, 50, 220),
                outline=(255, 255, 255, 180)
            )
        overlay = overlay.resize((w, h), Image.Resampling.LANCZOS)
        return Image.alpha_composite(image.convert('RGBA'), overlay)

    # -------------------------------------------------------------------------
    # MODE 2: Individual Heat (Groups by player ID or spatial trajectory)
    # -------------------------------------------------------------------------
    elif heat_type == 'Individual Heat':
        groups = {}
        for item in mapped_positions:
            p_id = item.get('player') or item.get('player_id') or item.get('id')
            if p_id is None:
                p_id = 'default'
            groups.setdefault(p_id, []).append(item)

        # Fallback: create distance-based clusters if no explicit player ID exists
        if len(groups) == 1 and 'default' in groups and len(mapped_positions) > 1:
            groups = {}
            curr_group = 0
            groups[curr_group] = [mapped_positions[0]]
            for i in range(1, len(mapped_positions)):
                prev = mapped_positions[i - 1]
                curr = mapped_positions[i]
                dist_sq = (curr['px'] - prev['px'])**2 + (curr['py'] - prev['py'])**2
                if dist_sq > 30**2:  # Threshold jump distance between tracks
                    curr_group += 1
                groups.setdefault(curr_group, []).append(curr)

        combined = Image.new('RGBA', (int_w, int_h), (0, 0, 0, 0))
        num_groups = len(groups)

        for idx, (group_id, pts) in enumerate(groups.items()):
            # Assign distinct hue for each predicted player/group
            hue = (idx / max(1, num_groups)) % 1.0
            r, g, b = [int(c * 255) for c in colorsys.hsv_to_rgb(hue, 0.85, 1.0)]

            group_density = Image.new('L', (int_w, int_h), 0)
            draw = ImageDraw.Draw(group_density)
            for item in pts:
                px, py = item['px'], item['py']
                draw.ellipse((px - 3, py - 3, px + 3, py + 3), fill=255)

            group_density = group_density.filter(ImageFilter.GaussianBlur(radius=5))
            mask = group_density.point(lambda p: int(p * 0.75) if p > 20 else 0)

            color_layer = Image.new('RGBA', (int_w, int_h), (r, g, b, 255))
            player_layer = Image.new('RGBA', (int_w, int_h), (0, 0, 0, 0))
            player_layer.paste(color_layer, (0, 0), mask)

            combined = Image.alpha_composite(combined, player_layer)

        combined = combined.resize((w, h), Image.Resampling.LANCZOS)
        return Image.alpha_composite(image.convert('RGBA'), combined)

    # -------------------------------------------------------------------------
    # PARAMETER CONFIGURATION FOR GRADIENT HEATMAPS
    # -------------------------------------------------------------------------
    elif heat_type == 'Aggressive Heat':
        target_positions = mapped_positions
        blur_radius = 5
        threshold = 90       # High threshold isolates intense core hotspots
        max_opacity = 0.85

    elif heat_type == 'Persistant Heat':
        # Keep points that have neighboring points within a tight radius
        STATIONARY_RADIUS = 6  # Pixels in internal canvas
        MIN_NEIGHBORS = 3

        coords = [(p['px'], p['py']) for p in mapped_positions]
        stationary_positions = []

        for i, (x1, y1) in enumerate(coords):
            neighbors = sum(
                1 for j, (x2, y2) in enumerate(coords)
                if i != j and (x1 - x2)**2 + (y1 - y2)**2 <= STATIONARY_RADIUS**2
            )
            if neighbors >= MIN_NEIGHBORS:
                stationary_positions.append(mapped_positions[i])

        target_positions = stationary_positions if stationary_positions else mapped_positions
        blur_radius = 4
        threshold = 40
        max_opacity = 0.8

    else:  # Default to 'Inclusive Heat'
        target_positions = mapped_positions
        blur_radius = 7
        threshold = 30
        max_opacity = 0.8

    # -------------------------------------------------------------------------
    # DENSITY RENDERING & COLOR BLENDING
    # -------------------------------------------------------------------------
    density = Image.new('L', (int_w, int_h), 0)
    draw = ImageDraw.Draw(density)

    for item in target_positions:
        px, py = item['px'], item['py']
        draw.ellipse(
            (px - DOT_RADIUS, py - DOT_RADIUS, px + DOT_RADIUS, py + DOT_RADIUS),
            fill=255
        )

    density = density.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    density = density.point(lambda p: 0 if p < threshold else int((p - threshold) * (255 / (255 - threshold))))

    heatmap = density.copy()
    heatmap.putpalette(get_thermal_palette())
    heatmap = heatmap.convert('RGBA')

    alpha = density.point(lambda p: int(p * max_opacity) if p > 0 else 0)
    heatmap.putalpha(alpha)

    heatmap = heatmap.resize((w, h), Image.Resampling.LANCZOS)
    return Image.alpha_composite(image.convert('RGBA'), heatmap)

def coordinates(image:Image.Image, data:dict[str, dict], bounds:dict) -> Image.Image:
    overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    w, h = image.size
    
    x_range = bounds['max-x'] - bounds['min-x']
    y_range = bounds['max-y'] - bounds['min-y']

    for client_id, client_data in data.items():
        coords = []
        for coord in client_data.get('coords', []):
            # Because your data is [Y, X]
            y, x = coord 

            px = ((x - bounds['min-x']) / x_range) * w
            py = ((y - bounds['min-y']) / y_range) * h

            coords.append((px, py))

        color = client_data.get('color', '#000000')
        
        if len(coords) > 1:
            draw.line(coords, fill=color, width=2)

        for i, (px, py) in enumerate(coords):
            r = 3
            draw.ellipse((px - r, py - r, px + r, py + r), 
                         fill=color, outline='#ffffff', width=1)
            
            if i == len(coords) - 1:
                icon = client_data.get('icon')

                if icon is not None:
                    icon_x = int(px - icon.width / 2)
                    icon_y = max(0, int(py - icon.height / 2) - 20)

                    overlay.alpha_composite(icon, (icon_x, icon_y))

    return Image.alpha_composite(image, overlay)