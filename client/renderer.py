from PIL import Image, ImageDraw, ImageFilter

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

def apply_heatmap(image:Image.Image, positions:list[dict], bounds:dict) -> Image.Image:
    DOT_RADIUS = 2
    BLUR_RADIUS = 7
    THRESHOLD = 30
    MAX_OPACITY = 0.8

    if not positions:
        return image.convert('RGBA')

    w, h = image.size
    
    x_range = bounds['max-x'] - bounds['min-x']
    y_range = bounds['max-y'] - bounds['min-y']

    density = Image.new('L', (w, h), 0)
    draw = ImageDraw.Draw(density)

    for pos in positions:
        x, y = pos.get('x'), pos.get('y')
        if x is None or y is None: continue

        px = int(((x - bounds['min-x']) / x_range) * w)
        py = int(((y - bounds['min-y']) / y_range) * h)

        draw.ellipse(
            (px - DOT_RADIUS, py - DOT_RADIUS, px + DOT_RADIUS, py + DOT_RADIUS),
            fill=255
        )

    density = density.filter(ImageFilter.GaussianBlur(radius=BLUR_RADIUS))

    density = density.point(lambda p: 0 if p < THRESHOLD else int((p - THRESHOLD) * (255 / (255 - THRESHOLD))))

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

    heatmap = density.copy()
    heatmap.putpalette(palette)
    heatmap = heatmap.convert('RGBA')

    alpha = density.point(lambda p: int(p * MAX_OPACITY) if p > 0 else 0)
    heatmap.putalpha(alpha)

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