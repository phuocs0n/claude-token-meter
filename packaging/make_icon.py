"""Draw the app icon (a gauge) with Pillow.

    python packaging/make_icon.py

Writes packaging/icon.ico (Windows) and token_meter/icon.png (window icon,
also converted to .icns by PyInstaller on macOS). Both files are committed,
so this only needs to run again when the design changes.
"""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
S = 2048  # draw large, then scale down for smooth edges


def draw() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0.04 * S, 0.04 * S, 0.96 * S, 0.96 * S), radius=0.21 * S, fill="#1e293b")

    cx, cy, r, w = S / 2, 0.58 * S, 0.32 * S, int(0.10 * S)
    box = (cx - r, cy - r, cx + r, cy + r)
    # 240° gauge from lower left, over the top, to lower right (Pillow angles run clockwise from 3 o'clock)
    for start, end, color in ((150, 232, "#10b981"), (232, 310, "#f59e0b"), (310, 390, "#ef4444")):
        d.arc(box, start, end, fill=color, width=w)

    # needle pointing up and to the right, tapered
    import math
    a = math.radians(298)
    tip = (cx + math.cos(a) * r * 0.92, cy + math.sin(a) * r * 0.92)
    n = (math.cos(a + math.pi / 2) * 0.045 * S, math.sin(a + math.pi / 2) * 0.045 * S)
    d.polygon([(cx + n[0], cy + n[1]), tip, (cx - n[0], cy - n[1])], fill="#f8fafc")
    hub = 0.075 * S
    d.ellipse((cx - hub, cy - hub, cx + hub, cy + hub), fill="#f8fafc")

    # three bars under the gauge: tokens over time
    base, bw, gap = 0.86 * S, 0.075 * S, 0.045 * S
    x0 = cx - (3 * bw + 2 * gap) / 2
    for i, h in enumerate((0.07, 0.11, 0.15)):
        x = x0 + i * (bw + gap)
        d.rounded_rectangle((x, base - h * S, x + bw, base), radius=0.02 * S, fill="#94a3b8")
    return img


def main() -> None:
    img = draw()
    png = img.resize((512, 512), Image.LANCZOS)
    png.save(ROOT / "token_meter" / "icon.png", optimize=True)
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.resize((256, 256), Image.LANCZOS).save(ROOT / "packaging" / "icon.ico", sizes=sizes)
    print("wrote token_meter/icon.png and packaging/icon.ico")


if __name__ == "__main__":
    main()
