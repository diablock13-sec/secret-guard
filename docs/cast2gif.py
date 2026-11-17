import json
import sys
from pathlib import Path

import pyte
from PIL import Image, ImageDraw, ImageFont

CAST, OUT = Path(sys.argv[1]), Path(sys.argv[2])
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
assert Path(FONT).exists(), f"font tidak ada: {FONT}"

lines = [ln for ln in CAST.read_text(encoding="utf-8").split("\n") if ln.strip()]
head = json.loads(lines[0])
assert head["version"] == 2
cols, rows = head["width"], head["height"]
events = [json.loads(ln) for ln in lines[1:]]
events = [e for e in events if e[1] == "o"]

font = ImageFont.truetype(FONT, 16)
cw = round(font.getlength("M"))
asc, desc = font.getmetrics()
ch = asc + desc + 2
PAD = 12
W, H = cols * cw + 2 * PAD, rows * ch + 2 * PAD
BG, FG = (24, 24, 24), (210, 210, 210)
NAMES = {
    "black": (0, 0, 0), "red": (205, 49, 49), "green": (13, 188, 121),
    "brown": (229, 229, 16), "yellow": (229, 229, 16), "blue": (36, 114, 200),
    "magenta": (188, 63, 188), "cyan": (17, 168, 205), "white": (229, 229, 229),
}


def color(value, default):
    if value == "default":
        return default
    name = value.removeprefix("bright")
    if name in NAMES:
        return NAMES[name]
    if len(value) == 6:
        try:
            return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            return default
    return default


screen = pyte.Screen(cols, rows)
stream = pyte.Stream(screen)
frames, durations = [], []
for i, (t, _, data) in enumerate(events):
    stream.feed(data)
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for y in range(rows):
        row = screen.buffer[y]
        for x in range(cols):
            c = row[x]
            if c.data.strip() == "":
                continue
            d.text((PAD + x * cw, PAD + y * ch), c.data, font=font, fill=color(c.fg, FG))
    nxt = events[i + 1][0] if i + 1 < len(events) else t + 3.0
    gap = 3.0 if i + 1 == len(events) else min(max(nxt - t, 0.1), 1.6)
    frames.append(img.convert("P", palette=Image.ADAPTIVE, colors=32))
    durations.append(int(gap * 1000))

frames[0].save(OUT, save_all=True, append_images=frames[1:], duration=durations, loop=0, optimize=True)
print(f"{OUT}: {len(frames)} frame, {W}x{H}, {OUT.stat().st_size // 1024} KB")
