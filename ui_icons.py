"""Small, font-independent transport icons in the current theme color."""
from PIL import Image, ImageDraw


def transport_icon(kind, color, size=22):
    scale = 4
    image = Image.new('RGBA', (24 * scale, 24 * scale))
    draw = ImageDraw.Draw(image)
    def line(points, width=2):
        draw.line([(int(x*scale), int(y*scale)) for x, y in points], fill=color, width=width*scale, joint='curve')
    def polygon(points):
        draw.polygon([(int(x*scale), int(y*scale)) for x, y in points], fill=color)
    def rectangle(box):
        draw.rounded_rectangle(tuple(int(v*scale) for v in box), radius=scale, fill=color)
    if kind == 'play':
        polygon([(7, 4), (20, 12), (7, 20)])
    elif kind == 'pause':
        rectangle((6, 4, 10, 20))
        rectangle((14, 4, 18, 20))
    elif kind == 'stop':
        rectangle((5, 5, 19, 19))
    elif kind in ('next', 'previous'):
        if kind == 'next':
            polygon([(5, 5), (16, 12), (5, 19)])
            rectangle((17, 5, 20, 19))
        else:
            polygon([(19, 5), (8, 12), (19, 19)])
            rectangle((4, 5, 7, 19))
    elif kind == 'shuffle':
        line([(3, 6), (7, 6), (16, 18), (21, 18)])
        line([(3, 18), (7, 18), (10, 14)])
        line([(14, 10), (17, 6), (21, 6)])
        line([(18, 3), (21, 6), (18, 9)])
        line([(18, 15), (21, 18), (18, 21)])
    elif kind in ('repeat', 'repeat_one'):
        line([(4, 10), (4, 6), (20, 6), (17, 3)])
        line([(17, 9), (20, 6)])
        line([(20, 14), (20, 18), (4, 18), (7, 21)])
        line([(7, 15), (4, 18)])
        if kind == 'repeat_one':
            line([(10, 11), (12, 10), (12, 15)])
    elif kind == 'add':
        line([(12, 4), (12, 20)])
        line([(4, 12), (20, 12)])
    elif kind == 'search':
        draw.ellipse((4*scale, 4*scale, 16*scale, 16*scale), outline=color, width=2*scale)
        line([(15, 15), (21, 21)])
    elif kind == 'library':
        for y in (6, 12, 18):
            line([(3, y), (5, y)])
            line([(9, y), (21, y)])
    elif kind == 'back':
        line([(14,5),(7,12),(14,19)],3)
        line([(7,12),(21,12)],3)
    elif kind == 'cloud':
        draw.ellipse((5*scale,5*scale,16*scale,16*scale),fill=color)
        draw.ellipse((11*scale,8*scale,22*scale,19*scale),fill=color)
        draw.ellipse((2*scale,10*scale,13*scale,19*scale),fill=color)
        rectangle((7,12,18,19))
    elif kind == 'menu':
        for y in (6, 12, 18):
            line([(4, y), (20, y)])
    elif kind == 'volume':
        polygon([(3,9),(7,9),(12,5),(12,19),(7,15),(3,15)])
        line([(16,8),(19,12),(16,16)])
    elif kind == 'minus':
        line([(5, 12), (19, 12)])
    elif kind == 'settings':
        import math
        teeth = []
        for i in range(32):
            a = math.pi * (i - .5) / 16
            radius = 9.5 if i % 4 in (1, 2) else 7.2
            teeth.append((12 + radius * math.cos(a), 12 + radius * math.sin(a)))
        polygon(teeth)
        draw.ellipse((8.5*scale, 8.5*scale, 15.5*scale, 15.5*scale), fill=(0, 0, 0, 0))
    return image.resize((size, size), Image.Resampling.LANCZOS)
