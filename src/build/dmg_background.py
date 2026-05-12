"""Generate the DMG installer background image for vitraj."""

import io
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import cairosvg

W, H = 660, 480
ICON_Y = 260
APP_X, APPS_X = 175, 485
ARROW_Y = ICON_Y + 5

BG_DARK = (13, 13, 18)
BG_MID = (18, 20, 30)


def _radial_gradient(w, h, cx, cy, radius, color, alpha_max=60):
    layer = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for r in range(int(radius), 0, -2):
        t = 1.0 - (r / radius)
        a = int(alpha_max * t * t)
        draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            fill=(*color, a)
        )
    return layer


def _draw_facets(draw, w, h, seed=42):
    rng = random.Random(seed)
    colors = [
        (75, 157, 210), (46, 118, 175), (93, 191, 215),
        (204, 41, 42), (226, 89, 81),
        (245, 216, 53), (236, 177, 25),
    ]
    for _ in range(35):
        cx = rng.randint(0, w)
        cy = rng.randint(0, h)
        size = rng.randint(40, 200)
        sides = rng.choice([3, 4, 5, 6])
        angle_off = rng.uniform(0, math.pi * 2)
        color = rng.choice(colors)
        alpha = rng.randint(3, 12)
        points = []
        for i in range(sides):
            angle = angle_off + (2 * math.pi * i / sides)
            rx = size * rng.uniform(0.6, 1.0)
            ry = size * rng.uniform(0.6, 1.0)
            points.append((cx + rx * math.cos(angle), cy + ry * math.sin(angle)))
        draw.polygon(points, fill=(*color, alpha))


def _draw_arrow(draw):
    y = ARROW_Y
    x_start = APP_X + 55
    x_end = APPS_X - 55
    shaft_y_half = 3
    head_len = 18
    head_y_half = 12

    shaft = [
        (x_start, y - shaft_y_half),
        (x_end - head_len, y - shaft_y_half),
        (x_end - head_len, y + shaft_y_half),
        (x_start, y + shaft_y_half),
    ]
    draw.polygon(shaft, fill=(255, 255, 255, 28))

    head = [
        (x_end - head_len, y - head_y_half),
        (x_end, y),
        (x_end - head_len, y + head_y_half),
    ]
    draw.polygon(head, fill=(255, 255, 255, 35))


def generate(project_dir: Path, output: Path):
    img = Image.new('RGBA', (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)

    for y in range(H):
        t = y / H
        r = int(BG_DARK[0] + (BG_MID[0] - BG_DARK[0]) * math.sin(t * math.pi))
        g = int(BG_DARK[1] + (BG_MID[1] - BG_DARK[1]) * math.sin(t * math.pi))
        b = int(BG_DARK[2] + (BG_MID[2] - BG_DARK[2]) * math.sin(t * math.pi))
        draw.line([(0, y), (W, y)], fill=(r, g, b, 255))

    facet_layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    facet_draw = ImageDraw.Draw(facet_layer)
    _draw_facets(facet_draw, W, H)
    facet_layer = facet_layer.filter(ImageFilter.GaussianBlur(radius=8))
    img = Image.alpha_composite(img, facet_layer)

    glow1 = _radial_gradient(W, H, W // 2, 80, 300, (75, 157, 210), alpha_max=25)
    img = Image.alpha_composite(img, glow1)

    glow2 = _radial_gradient(W, H, APP_X, ICON_Y, 120, (93, 191, 215), alpha_max=12)
    img = Image.alpha_composite(img, glow2)

    glow3 = _radial_gradient(W, H, APPS_X, ICON_Y, 120, (93, 191, 215), alpha_max=12)
    img = Image.alpha_composite(img, glow3)

    icon_svg = project_dir / 'src' / 'main' / 'icons' / 'src' / 'icon.svg'
    icon_size = 160
    icon_png = cairosvg.svg2png(
        url=str(icon_svg), output_width=icon_size, output_height=int(icon_size * 400 / 455)
    )
    icon_img = Image.open(io.BytesIO(icon_png)).convert('RGBA')
    icon_x = (W - icon_img.width) // 2
    icon_y = 35
    img.paste(icon_img, (icon_x, icon_y), icon_img)

    arrow_layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    arrow_draw = ImageDraw.Draw(arrow_layer)
    _draw_arrow(arrow_draw)
    img = Image.alpha_composite(img, arrow_layer)

    line_y = H - 80
    line_layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    line_draw = ImageDraw.Draw(line_layer)
    line_draw.line([(60, line_y), (W - 60, line_y)], fill=(255, 255, 255, 15), width=1)
    img = Image.alpha_composite(img, line_layer)

    label_layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    label_draw = ImageDraw.Draw(label_layer)
    try:
        font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 13)
    except (OSError, IOError):
        font = ImageFont.load_default()
    label_y = ICON_Y + 50
    for text, cx in [('vitraj', APP_X), ('Applications', APPS_X)]:
        bbox = label_draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        label_draw.text(
            (cx - tw // 2, label_y), text, font=font, fill=(255, 255, 255, 220)
        )
    img = Image.alpha_composite(img, label_layer)

    final = img.convert('RGB')
    final.save(str(output), 'PNG', optimize=True)
    return output


if __name__ == '__main__':
    project = Path(__file__).resolve().parent.parent.parent
    out = project / 'target' / 'dmg_background.png'
    out.parent.mkdir(parents=True, exist_ok=True)
    generate(project, out)
    print(f'Generated: {out} ({out.stat().st_size // 1024} KB)')
