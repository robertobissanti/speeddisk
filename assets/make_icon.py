"""Generate the speeddisk icon (assets/speeddisk.ico + assets/speeddisk.png). Requires Pillow."""
import os
from PIL import Image, ImageDraw

S = 1024
HERE = os.path.dirname(os.path.abspath(__file__))


def icon():
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # terminal window
    d.rounded_rectangle((40, 40, S - 40, S - 40), radius=170, fill="#161b22")
    d.rectangle((40, 230, S - 40, S - 200), fill="#0d1117")
    d.rounded_rectangle((40, 400, S - 40, S - 40), radius=170, fill="#0d1117")
    d.rectangle((40, 230, S - 40, 400), fill="#0d1117")
    d.line((40, 230, S - 40, 230), fill="#30363d", width=10)
    d.rounded_rectangle((40, 40, S - 40, S - 40), radius=170, outline="#30363d", width=24)
    for i, c in enumerate(("#ff5f56", "#ffbd2e", "#27c93f")):
        x = 170 + i * 95
        d.ellipse((x - 32, 135 - 32, x + 32, 135 + 32), fill=c)
    # history bars: write (red) and read (green) side by side
    base = S - 150
    heights = [0.35, 0.5, 0.45, 0.65, 0.6, 0.8]
    bw, gap, x0 = 52, 14, 140
    for i, h in enumerate(heights):
        for j, col in enumerate(("#ff7b72", "#7ee787")):
            x = x0 + (i * 2 + j) * (bw + gap)
            top = base - int(h * 520) - j * 30
            d.rounded_rectangle((x, top, x + bw, base), radius=14, fill=col)
    # baseline
    d.rounded_rectangle((120, base + 20, S - 120, base + 44), radius=12, fill="#79c0ff")
    return im


im = icon()
im.save(os.path.join(HERE, "speeddisk.png"))
im.save(os.path.join(HERE, "speeddisk.ico"),
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("icon written")
