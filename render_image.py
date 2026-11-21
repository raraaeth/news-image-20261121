#!/usr/bin/env python3
"""Render one day's world news as a single-page broadsheet image.

Reads the editorial content from stories.json (kept next to this file) and
paints a 1024x1024 PNG front page: masthead, a night-sky illustration for
the lead story, the lead itself, then a column of boxed side stories, each
with a small pictogram tile.  Output is written to entry.png.
"""

import json
import math
import random
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
PAGE = 1024
MARGIN = 30
CONTENT_W = PAGE - 2 * MARGIN

PAPER = (243, 234, 216)
NAVY = (26, 41, 73)
NAVY_DEEP = (18, 29, 54)
INK = (40, 40, 46)
CRIMSON = (176, 32, 26)
GOLD = (232, 178, 60)

SERIF_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
SANS = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
SANS_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"


@lru_cache(maxsize=None)
def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def text_w(draw: ImageDraw.ImageDraw, s: str, f) -> float:
    return draw.textlength(s, font=f)


def tracked_w(draw, s: str, f, tracking: int) -> float:
    return sum(text_w(draw, ch, f) for ch in s) + tracking * max(0, len(s) - 1)


def draw_tracked(draw, x, y, s, f, fill, tracking):
    """Draw letter-spaced text starting at x; return the end x."""
    cx = x
    for ch in s:
        draw.text((cx, y), ch, font=f, fill=fill)
        cx += text_w(draw, ch, f) + tracking
    return cx - tracking


def draw_tracked_centre(draw, cx, y, s, f, fill, tracking):
    w = tracked_w(draw, s, f, tracking)
    draw_tracked(draw, cx - w / 2, y, s, f, fill, tracking)


def wrap_words(draw, s: str, f, max_w: float) -> list[str]:
    """Greedy word wrap; a single over-long word still gets its own line."""
    lines: list[str] = []
    current = ""
    for word in s.split():
        trial = word if not current else current + " " + word
        if current and text_w(draw, trial, f) > max_w:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return lines


def shrink_to_fit(draw, s: str, path: str, size: int, max_w: float, floor: int):
    """Largest font at or below `size` whose rendering of s fits max_w."""
    while size > floor and text_w(draw, s, font(path, size)) > max_w:
        size -= 2
    return font(path, size)


# --------------------------------------------------------------------------
# Lead illustration: a night sky, missile trails and a city silhouette.
# --------------------------------------------------------------------------

SKY_STOPS = [
    (0.00, (16, 18, 44)),
    (0.45, (43, 30, 66)),
    (0.75, (104, 47, 58)),
    (1.00, (196, 96, 52)),
]


def sky_colour(t: float):
    for (t0, c0), (t1, c1) in zip(SKY_STOPS, SKY_STOPS[1:]):
        if t0 <= t <= t1:
            k = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            return tuple(round(a + (b - a) * k) for a, b in zip(c0, c1))
    return SKY_STOPS[-1][1]


def bezier(p0, p1, p2, steps=60):
    pts = []
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        pts.append((
            u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
            u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1],
        ))
    return pts


def paint_lead_art(width: int, height: int) -> Image.Image:
    art = Image.new("RGB", (width, height), SKY_STOPS[0][1])
    px = art.load()
    for row in range(height):
        colour = sky_colour(row / max(1, height - 1))
        for col in range(width):
            px[col, row] = colour

    d = ImageDraw.Draw(art, "RGBA")
    rng = random.Random(20261121)

    # Stars in the upper two thirds.
    for _ in range(90):
        sx = rng.uniform(0, width)
        sy = rng.uniform(0, height * 0.62)
        r = rng.choice([1, 1, 1, 2])
        d.ellipse([sx - r, sy - r, sx + r, sy + r],
                  fill=(255, 246, 220, rng.randint(90, 190)))

    ground = height  # skyline baseline

    # Suspension bridge behind the skyline, right of centre.
    deck_y = ground - 16
    tower_l, tower_r = width * 0.52, width * 0.86
    for tx in (tower_l, tower_r):
        d.rectangle([tx - 4, deck_y - 62, tx + 4, ground], fill=(8, 9, 18, 255))
    cable = bezier((tower_l - 130, deck_y + 4),
                   ((tower_l + tower_r) / 2, deck_y - 96),
                   (tower_r + 120, deck_y + 4))
    d.line(cable, fill=(10, 10, 20, 230), width=3)
    for frac in range(1, 10):
        bx, by = cable[frac * 6]
        d.line([bx, by, bx, deck_y], fill=(10, 10, 20, 160), width=1)
    d.line([0, deck_y, width, deck_y], fill=(8, 9, 18, 255), width=3)

    # Buildings: dark blocks of seeded widths and heights.
    bx = -6
    while bx < width:
        bw = rng.randint(26, 74)
        bh = rng.randint(14, 58)
        if rng.random() < 0.22:
            bh += rng.randint(10, 26)
        d.rectangle([bx, ground - bh, bx + bw, ground], fill=(7, 8, 16, 255))
        bx += bw + rng.randint(2, 9)

    # Missile trails arcing down onto the city, with glowing heads.
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    trails = [
        ((width * 0.10, 2), (width * 0.24, 10), (width * 0.37, height * 0.78)),
        ((width * 0.44, 0), (width * 0.55, 8), (width * 0.63, height * 0.82)),
        ((width * 0.72, 4), (width * 0.80, 12), (width * 0.84, height * 0.72)),
        ((width * 0.94, 2), (width * 0.93, 16), (width * 0.90, height * 0.66)),
    ]
    for start, ctrl, end in trails:
        path = bezier(start, ctrl, end)
        for wdt, alpha in ((7, 46), (4, 92), (2, 210)):
            gd.line(path, fill=(255, 138, 54, alpha), width=wdt)
        hx, hy = end
        gd.ellipse([hx - 9, hy - 9, hx + 9, hy + 9], fill=(255, 120, 40, 70))
        gd.ellipse([hx - 4, hy - 4, hx + 4, hy + 4], fill=(255, 196, 110, 255))
    art = Image.alpha_composite(art.convert("RGBA"), glow).convert("RGB")
    return art


# --------------------------------------------------------------------------
# Panel pictograms.  Each draws inside the tile box (x0, y0, x1, y1).
# --------------------------------------------------------------------------

def icon_diplomacy(d, box):
    x0, y0, x1, y1 = box
    cx = (x0 + x1) / 2
    # Three stars above a negotiating table.
    for dx in (-26, 0, 26):
        sx, sy = cx + dx, y0 + 22
        pts = []
        for i in range(10):
            ang = -math.pi / 2 + i * math.pi / 5
            rad = 9 if i % 2 == 0 else 4
            pts.append((sx + rad * math.cos(ang), sy + rad * math.sin(ang)))
        d.polygon(pts, fill=GOLD)
    table_top = (y0 + y1) / 2 + 4
    d.rectangle([x0 + 14, table_top, x1 - 14, table_top + 7], fill=GOLD)
    for lx in (x0 + 22, x1 - 27):
        d.rectangle([lx, table_top + 7, lx + 5, y1 - 9], fill=GOLD)


def icon_war(d, box):
    x0, y0, x1, y1 = box
    deck = y1 - 18
    # Bridge: two pylons, a deck and sagging cables.
    for tx in (x0 + 18, x1 - 22):
        d.rectangle([tx, y0 + 26, tx + 4, deck], fill=(148, 163, 189))
    d.rectangle([x0 + 8, deck, x1 - 8, deck + 4], fill=(148, 163, 189))
    d.arc([x0 + 12, y0 + 18, x1 - 12, deck + 26], start=0, end=180,
          fill=(148, 163, 189), width=2)
    # Explosion burst at mid-span.
    cx, cy = (x0 + x1) / 2, deck - 12
    for ang in range(0, 360, 30):
        a = math.radians(ang)
        r1, r2 = 4, 15 if ang % 60 == 0 else 10
        d.line([cx + r1 * math.cos(a), cy + r1 * math.sin(a),
                cx + r2 * math.cos(a), cy + r2 * math.sin(a)],
               fill=(255, 122, 40), width=3)
    d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=(255, 190, 90))
    # Smoke puff.
    d.ellipse([cx + 8, y0 + 8, cx + 30, y0 + 22], fill=(120, 122, 132))
    d.ellipse([cx + 16, y0 + 4, cx + 34, y0 + 16], fill=(120, 122, 132))


def icon_markets(d, box):
    x0, y0, x1, y1 = box
    # Faint grid, then a plunging line with an arrowhead.
    for gx in range(x0 + 14, x1 - 6, 16):
        d.line([gx, y0 + 10, gx, y1 - 10], fill=(52, 74, 110), width=1)
    for gy in range(y0 + 12, y1 - 8, 16):
        d.line([x0 + 10, gy, x1 - 10, gy], fill=(52, 74, 110), width=1)
    pts = [(x0 + 12, y0 + 18), (x0 + 34, y0 + 30), (x0 + 48, y0 + 24),
           (x1 - 16, y1 - 16)]
    d.line(pts, fill=(238, 84, 52), width=4)
    ex, ey = pts[-1]
    d.polygon([(ex + 2, ey + 2), (ex - 12, ey - 1), (ex - 1, ey - 12)],
              fill=(238, 84, 52))


def icon_climate(d, box):
    x0, y0, x1, y1 = box
    cx, cy, r = x0 + 36, (y0 + y1) / 2, 25
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(64, 128, 196))
    # Stylised continents.
    for blob in [(-14, -12, 11, 7), (2, -4, 9, 12), (-8, 8, 12, 6), (10, -16, 7, 5)]:
        dx, dy, wdt, hgt = blob
        d.ellipse([cx + dx, cy + dy, cx + dx + wdt, cy + dy + hgt],
                  fill=(86, 168, 96))
    # Thermometer alongside.
    tx = x1 - 22
    d.rounded_rectangle([tx, y0 + 12, tx + 9, y1 - 22], radius=4,
                        outline=(232, 232, 232), width=2)
    d.rectangle([tx + 3, cy + 2, tx + 6, y1 - 26], fill=(238, 84, 52))
    d.ellipse([tx - 3, y1 - 24, tx + 12, y1 - 9], fill=(238, 84, 52))


def icon_science(d, box):
    x0, y0, x1, y1 = box
    # A capsule pill tilted across the tile: two halves, two round end caps.
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2 + 2
    ang = math.radians(-36)
    ax = (math.cos(ang), math.sin(ang))          # unit vector along the pill
    pp = (-math.sin(ang), math.cos(ang))         # unit vector across the pill
    half, rad = 27, 13
    mid = (cx, cy)
    ends = [(cx - half * ax[0], cy - half * ax[1]),
            (cx + half * ax[0], cy + half * ax[1])]
    for tip, colour in zip(ends, [(238, 84, 52), (240, 238, 230)]):
        corners = [
            (mid[0] - rad * pp[0], mid[1] - rad * pp[1]),
            (tip[0] - rad * pp[0], tip[1] - rad * pp[1]),
            (tip[0] + rad * pp[0], tip[1] + rad * pp[1]),
            (mid[0] + rad * pp[0], mid[1] + rad * pp[1]),
        ]
        d.polygon(corners, fill=colour)
        d.ellipse([tip[0] - rad, tip[1] - rad, tip[0] + rad, tip[1] + rad],
                  fill=colour)
    # Sparkle crosses.
    for sx, sy in [(x0 + 14, y0 + 12), (x1 - 18, y0 + 16), (x1 - 14, y1 - 18)]:
        d.line([sx - 5, sy, sx + 5, sy], fill=GOLD, width=2)
        d.line([sx, sy - 5, sx, sy + 5], fill=GOLD, width=2)


ICONS = {
    "diplomacy": icon_diplomacy,
    "war": icon_war,
    "markets": icon_markets,
    "climate": icon_climate,
    "science": icon_science,
}


# --------------------------------------------------------------------------
# Page assembly.
# --------------------------------------------------------------------------

def build_page(data: dict) -> Image.Image:
    page = Image.new("RGB", (PAGE, PAGE), PAPER)
    d = ImageDraw.Draw(page)
    mast = data["masthead"]
    lead = data["lead"]
    x = MARGIN
    y = 16

    # Masthead.
    draw_tracked_centre(d, PAGE / 2, y, mast["kicker"],
                        font(SERIF_BOLD, 26), NAVY, 10)
    y += 40
    day_f = shrink_to_fit(d, mast["date_line_1"], SERIF_BOLD, 120, CONTENT_W, 60)
    d.text((PAGE / 2, y), mast["date_line_1"], font=day_f, fill=NAVY,
           anchor="ma")
    y += int(day_f.size * 1.04)
    date_f = shrink_to_fit(d, mast["date_line_2"], SERIF_BOLD, 80,
                           CONTENT_W, 50)
    d.text((PAGE / 2, y), mast["date_line_2"], font=date_f, fill=NAVY,
           anchor="ma")
    y += int(date_f.size * 1.06) + 4
    d.rectangle([x, y, x + CONTENT_W, y + 5], fill=NAVY)
    d.rectangle([x, y + 8, x + CONTENT_W, y + 10], fill=NAVY)
    y += 16

    # Lead illustration band.
    art_h = 76
    page.paste(paint_lead_art(CONTENT_W, art_h), (x, y))
    y += art_h + 10

    # Lead story.
    draw_tracked(d, x, y, lead["kicker"], font(SANS_BOLD, 20), CRIMSON, 7)
    y += 26
    lead_f = shrink_to_fit(d, lead["headline"], SANS_BOLD, 48, CONTENT_W, 30)
    d.text((x, y), lead["headline"], font=lead_f, fill=NAVY)
    y += int(lead_f.size * 1.08)
    body_f = font(SANS, 22)
    for line in wrap_words(d, lead["sublabel"], body_f, CONTENT_W):
        d.text((x, y), line, font=body_f, fill=INK)
        y += 26
    y += 4
    d.rectangle([x, y, x + CONTENT_W, y + 2], fill=NAVY)
    y += 10

    # Side-story panels share whatever vertical space remains.
    panels = data["panels"]
    gap = 7
    bottom = PAGE - 20
    panel_h = (bottom - y - gap * (len(panels) - 1)) // len(panels)
    tile = 92
    kick_f = font(SANS_BOLD, 16)
    head_base = 24
    panel_body_f = font(SANS, 17)

    for panel in panels:
        top = y
        d.rectangle([x, top, x + CONTENT_W, top + panel_h],
                    outline=NAVY, width=2)
        d.rectangle([x, top, x + tile, top + panel_h], fill=NAVY_DEEP)
        painter = ICONS.get(panel["id"])
        if painter is not None:
            painter(d, (x, top, x + tile, top + panel_h))
        tx = x + tile + 16
        tw = CONTENT_W - tile - 16 - 12
        ty = top + 5
        d.text((tx, ty), panel["kicker"], font=kick_f, fill=CRIMSON)
        ty += 19
        head_f = shrink_to_fit(d, panel["headline"], SANS_BOLD, head_base,
                               tw, 18)
        d.text((tx, ty), panel["headline"], font=head_f, fill=NAVY)
        ty += int(head_f.size * 1.05) + 1
        for line in wrap_words(d, panel["sublabel"], panel_body_f, tw):
            d.text((tx, ty), line, font=panel_body_f, fill=INK)
            ty += 20
        y += panel_h + gap

    return page


def main() -> None:
    with open(HERE / "stories.json", encoding="utf-8") as fh:
        data = json.load(fh)
    image = build_page(data)
    image.save(HERE / "entry.png", format="PNG", optimize=True)
    print(f"entry.png written: {image.size[0]}x{image.size[1]}")


if __name__ == "__main__":
    main()
