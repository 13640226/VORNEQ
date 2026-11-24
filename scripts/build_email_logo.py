"""Render the VORNEQ horizontal logo to PNG for e-mail clients.

Gmail and Outlook do not render SVG, so e-mails reference this PNG.
Geometry mirrors assets/images/brand/v2/horizontal.svg (official colours
#2563EB / #0B1120). Usage: python scripts/build_email_logo.py
"""
import re
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

BLUE = (37, 99, 235, 255)
NAVY = (11, 17, 32, 255)
VIEW_W, VIEW_H = 740, 130
SCALE = 2  # output pixels per SVG unit (retina)
SS = 4  # supersampling factor
OUT = Path(__file__).resolve().parent.parent / "static" / "email" / "vorneq-logo.png"

SYMBOL = (
    "M100 230 H255 L440 600 L595 290 Q660 160 785 190 Q930 220 930 390 "
    "Q930 520 815 590 L950 720 H770 L615 565 H720 Q805 565 805 390 "
    "Q805 315 750 315 Q700 315 660 395 L440 810 Z"
)
GLYPHS = [
    (0, "M0 0 H18 L40 64 L62 0 H80 L49 90 H31 Z"),
    (100, "M0 0 H80 V90 H0 Z M18 18 V72 H62 V18 Z"),
    (200, "M0 0 H80 V49 H50 L80 90 H58 L28 49 H18 V90 H0 Z M18 18 V31 H62 V18 Z"),
    (300, "M0 0 H18 L62 58 V0 H80 V90 H62 L18 32 V90 H0 Z"),
    (400, "M0 0 H80 V18 H18 V36 H65 V54 H18 V72 H80 V90 H0 Z"),
    (500, "M0 0 H80 V90 H0 Z M18 18 V72 H62 V18 Z M45 58 L88 98 H65 L33 68 Z"),
]
TOKEN = re.compile(r"[MHVLQZ]|-?\d+(?:\.\d+)?")


def flatten(d):
    tokens, i = TOKEN.findall(d), 0
    subpaths, cur, pos, cmd = [], [], (0.0, 0.0), None

    def num():
        nonlocal i
        value = float(tokens[i])
        i += 1
        return value

    while i < len(tokens):
        if tokens[i].isalpha():
            cmd = tokens[i]
            i += 1
            if cmd == "Z":
                if cur:
                    subpaths.append(cur)
                    cur = []
                continue
        if cmd == "M":
            if cur:
                subpaths.append(cur)
            pos = (num(), num())
            cur = [pos]
            cmd = "L"
        elif cmd == "H":
            pos = (num(), pos[1])
            cur.append(pos)
        elif cmd == "V":
            pos = (pos[0], num())
            cur.append(pos)
        elif cmd == "L":
            pos = (num(), num())
            cur.append(pos)
        elif cmd == "Q":
            c = (num(), num())
            e = (num(), num())
            for k in range(1, 17):
                t = k / 16
                cur.append(
                    (
                        (1 - t) ** 2 * pos[0] + 2 * (1 - t) * t * c[0] + t * t * e[0],
                        (1 - t) ** 2 * pos[1] + 2 * (1 - t) * t * c[1] + t * t * e[1],
                    )
                )
            pos = e
    if cur:
        subpaths.append(cur)
    return subpaths


def paint(canvas, d, color, scale, tx, ty):
    k = SCALE * SS
    mask = Image.new("L", canvas.size, 0)
    for sub in flatten(d):  # even-odd fill: XOR every sub-path
        layer = Image.new("L", canvas.size, 0)
        ImageDraw.Draw(layer).polygon(
            [((x * scale + tx) * k, (y * scale + ty) * k) for x, y in sub], fill=255
        )
        mask = ImageChops.difference(mask, layer)
    colored = Image.new("RGBA", canvas.size, color)
    colored.putalpha(mask)
    return Image.alpha_composite(canvas, colored)


def main():
    canvas = Image.new("RGBA", (VIEW_W * SCALE * SS, VIEW_H * SCALE * SS), (0, 0, 0, 0))
    canvas = paint(canvas, SYMBOL, BLUE, 0.13, 0, 0)
    for dx, path in GLYPHS:
        canvas = paint(canvas, path, NAVY, 1, 145 + dx, 15)
    out = canvas.resize((VIEW_W * SCALE, VIEW_H * SCALE), Image.LANCZOS)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.save(OUT, optimize=True)
    print("wrote", OUT, out.size)


if __name__ == "__main__":
    main()