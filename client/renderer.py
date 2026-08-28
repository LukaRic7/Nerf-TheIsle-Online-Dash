from PIL import Image, ImageDraw

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

def letterbox_and_grid(image:Image.Image, width:int, height:int, grid_size:int=8) -> Image.Image:
    base_width, base_height = image.size
    scale_factor = min(width / base_width, height / base_height)
    new_size = (int(base_width * scale_factor), int(base_height * scale_factor))
    
    resized = image.resize(new_size, Image.Resampling.LANCZOS)
    resized = resized.convert('RGBA')

    letterboxing_color = resized.getpixel((0, 0))

    resized = draw_grid(resized, size=grid_size)

    canvas = Image.new('RGBA', (width, height), letterboxing_color)

    paste_x = (width - new_size[0]) // 2
    paste_y = (height - new_size[1]) // 2

    canvas.paste(resized, (paste_x, paste_y), resized)

    return canvas