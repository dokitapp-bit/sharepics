"""Run once to generate PWA icons."""
from PIL import Image, ImageDraw
import os

def make_icon(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    r = int(size * 0.22)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill="#f97316")

    s = size
    pts_top    = [(s*0.5, s*0.22), (s*0.69, s*0.34), (s*0.5, s*0.47), (s*0.31, s*0.34)]
    pts_left   = [(s*0.31, s*0.34), (s*0.31, s*0.59), (s*0.5, s*0.72), (s*0.5, s*0.47)]
    pts_right  = [(s*0.69, s*0.34), (s*0.69, s*0.59), (s*0.5, s*0.72), (s*0.5, s*0.47)]

    draw.polygon([(x, y) for x, y in pts_top],   fill=(255, 255, 255, 230))
    draw.polygon([(x, y) for x, y in pts_left],  fill=(255, 255, 255, 153))
    draw.polygon([(x, y) for x, y in pts_right], fill=(255, 255, 255, 191))

    return img

out = os.path.join(os.path.dirname(__file__), "frontend/static/icons")
os.makedirs(out, exist_ok=True)

for sz in [192, 512]:
    make_icon(sz).save(os.path.join(out, f"icon-{sz}.png"), "PNG")
    print(f"  icon-{sz}.png ✓")

print("Icons generated.")
