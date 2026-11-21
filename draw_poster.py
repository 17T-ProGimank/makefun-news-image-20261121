"""Draw "The World Today" -- a one-page newspaper poster summing up the
world news of Saturday 21 November 2026.

Pure Python 3 standard library: no network, no third-party packages.
Renders text from embedded 1-bit bitmap glyphs (fontdata.py), draws a
dotted world map from hand-written continent outlines, and writes a
deterministic PNG (fixed zlib level, no timestamps) to the output path.

Stories were compiled on 21 Nov 2026 from wire reports (BBC News,
France 24, CBS News, El Pais, The Guardian, Al Jazeera, Reuters, PBS
NewsHour, Sky News, The Japan Times, Yonhap, UPI, Middle East Eye,
The National, Euronews, The Straits Times, The Hindu). Every figure
below is stated as the reporting outlets reported it.
"""

import base64
import math
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fontdata import FONTS  # noqa: E402

# ---------------------------------------------------------------- canvas

W, H = 1024, 1024
PAPER = (247, 243, 234)
INK = (26, 26, 26)
RED = (176, 42, 32)
NAVY = (31, 58, 95)
GRAY = (112, 110, 102)
RULE = (178, 172, 158)
MAP_BG = (233, 237, 239)
LAND = (96, 106, 116)
TICKER_BG = (22, 22, 22)
WHITE = (255, 255, 255)


class Canvas:
    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)
        self.fill_rect(0, 0, w, h, bg)

    def set(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i], self.px[i + 1], self.px[i + 2] = color

    def fill_rect(self, x, y, w, h, color):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        r, g, b = color
        for yy in range(y0, y1):
            base = (yy * self.w + x0) * 3
            for xx in range(x0, x1):
                i = base + (xx - x0) * 3
                self.px[i], self.px[i + 1], self.px[i + 2] = r, g, b

    def hline(self, x, y, w, color):
        self.fill_rect(x, y, w, 1, color)

    def vline(self, x, y, h, color):
        self.fill_rect(x, y, 1, h, color)

    def fill_circle(self, cx, cy, r, color):
        for dy in range(-r, r + 1):
            dx = int(math.sqrt(r * r - dy * dy))
            self.hline(cx - dx, cy + dy, 2 * dx + 1, color)

    def circle(self, cx, cy, r, color):
        # Midpoint circle outline, 1 px.
        x, y, d = 0, r, 1 - r
        pts = []
        while x <= y:
            pts += [(cx + x, cy + y), (cx - x, cy + y), (cx + x, cy - y),
                    (cx - x, cy - y), (cx + y, cy + x), (cx - y, cy + x),
                    (cx + y, cy - x), (cx - y, cy - x)]
            if d < 0:
                d += 2 * x + 3
            else:
                d += 2 * (x - y) + 5
                y -= 1
            x += 1
        for px, py in pts:
            self.set(px, py, color)


# ---------------------------------------------------------------- fonts

_GLYPH_CACHE = {}


def _glyph(font_name, ch):
    key = (font_name, ch)
    g = _GLYPH_CACHE.get(key)
    if g is None:
        raw = FONTS[font_name]["glyphs"].get(ch)
        if raw is None:
            raw = FONTS[font_name]["glyphs"].get("?")
        head, _, b64 = raw.partition(":")
        w, h, dx, dy, adv = (int(v) for v in head.split(","))
        bits = base64.b64decode(b64) if b64 else b""
        g = (w, h, dx, dy, adv, bits)
        _GLYPH_CACHE[key] = g
    return g


def text_width(font_name, text):
    return sum(_glyph(font_name, ch)[4] for ch in text)


def draw_text(cv, font_name, x, y_top, text, color):
    """Draw text; y_top is the top of the font's em box."""
    baseline = y_top + FONTS[font_name]["ascent"]
    pen = x
    for ch in text:
        w, h, dx, dy, adv, bits = _glyph(font_name, ch)
        if w and h:
            gx = pen + dx
            gy = baseline + dy
            for row in range(h):
                for col in range(w):
                    bit = row * w + col
                    if bits[bit >> 3] >> (7 - (bit & 7)) & 1:
                        cv.set(gx + col, gy + row, color)
        pen += adv
    return pen


def draw_text_centered(cv, font_name, cx, y_top, text, color):
    draw_text(cv, font_name, cx - text_width(font_name, text) // 2,
              y_top, text, color)


def wrap_text(font_name, text, max_w, max_lines=None):
    """Greedy word wrap; returns a list of lines (truncated with ...)."""
    words = text.split(" ")
    lines = []
    cur = ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if text_width(font_name, trial) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        # Trim the last line until the ellipsis fits.
        while lines and text_width(font_name, lines[-1] + "\u2026") > max_w:
            lines[-1] = lines[-1][:-1]
        lines[-1] = lines[-1] + "\u2026"
    return lines


def draw_paragraph(cv, font_name, x, y_top, text, max_w, color,
                   line_h, max_lines=None):
    lines = wrap_text(font_name, text, max_w, max_lines)
    for i, line in enumerate(lines):
        draw_text(cv, font_name, x, y_top + i * line_h, line, color)
    return y_top + len(lines) * line_h


# ---------------------------------------------------------------- png

def write_png(cv, path):
    raw = bytearray()
    stride = cv.w * 3
    for y in range(cv.h):
        raw.append(0)  # filter: none
        raw += cv.px[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(ctype, data):
        out = struct.pack(">I", len(data)) + ctype + data
        out += struct.pack(">I", zlib.crc32(ctype + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


# ---------------------------------------------------------------- map

# Rough continent outlines as (lon, lat) points, equirectangular.
CONTINENTS = [
    # North America
    [(-168, 66), (-150, 70), (-135, 69), (-125, 71), (-110, 73), (-95, 80),
     (-85, 76), (-80, 73), (-70, 70), (-65, 62), (-60, 55), (-55, 52),
     (-60, 47), (-65, 44), (-70, 42), (-74, 39), (-76, 35), (-80, 32),
     (-81, 26), (-84, 30), (-89, 29), (-90, 21), (-94, 18), (-97, 16),
     (-92, 15), (-86, 12), (-83, 9), (-80, 8), (-85, 11), (-90, 14),
     (-95, 16), (-100, 18), (-105, 20), (-110, 23), (-114, 28),
     (-117, 33), (-122, 37), (-124, 42), (-124, 48), (-130, 55),
     (-140, 60), (-150, 61), (-158, 58), (-165, 60), (-168, 66)],
    # Greenland
    [(-58, 64), (-52, 60), (-43, 60), (-32, 68), (-25, 70), (-22, 76),
     (-30, 80), (-45, 81), (-58, 78), (-62, 74), (-58, 64)],
    # South America
    [(-79, 9), (-77, 7), (-75, 10), (-72, 12), (-64, 11), (-60, 8),
     (-54, 6), (-51, 4), (-50, 0), (-44, -3), (-38, -5), (-35, -8),
     (-38, -15), (-40, -20), (-48, -26), (-52, -32), (-58, -35),
     (-62, -39), (-65, -43), (-68, -50), (-70, -54), (-73, -50),
     (-73, -40), (-72, -30), (-70, -20), (-76, -14), (-80, -6),
     (-81, 0), (-80, 5), (-79, 9)],
    # Africa
    [(-17, 15), (-16, 20), (-15, 27), (-10, 31), (-6, 34), (0, 36),
     (10, 37), (12, 34), (19, 32), (25, 32), (30, 31), (32, 31),
     (35, 28), (37, 22), (39, 18), (43, 12), (48, 11), (51, 12),
     (51, 10), (48, 5), (46, 0), (41, -5), (40, -10), (39, -15),
     (36, -20), (33, -26), (29, -30), (26, -34), (20, -35), (18, -32),
     (16, -28), (14, -22), (12, -18), (13, -12), (12, -6), (9, 4),
     (4, 6), (-3, 5), (-8, 5), (-13, 8), (-17, 12), (-17, 15)],
    # Eurasia
    [(-10, 36), (-9, 38), (-9, 43), (-4, 44), (-2, 47), (-1, 46),
     (-4, 48), (-1, 50), (2, 51), (4, 53), (8, 55), (8, 57),
     (12, 56), (18, 56), (21, 55), (24, 58), (28, 59), (30, 60),
     (23, 65), (28, 66), (32, 68), (40, 68), (48, 69), (55, 69),
     (62, 70), (70, 72), (78, 72), (85, 73), (95, 75), (105, 77),
     (115, 73), (125, 72), (135, 71), (145, 72), (155, 70), (165, 69),
     (170, 67), (178, 65), (173, 64), (170, 60), (162, 58), (158, 53),
     (156, 51), (150, 59), (142, 54), (141, 50), (140, 45), (138, 39),
     (135, 35), (130, 33), (127, 35), (124, 38), (122, 31), (120, 28),
     (118, 25), (114, 22), (110, 20), (108, 18), (106, 10), (104, 9),
     (101, 7), (99, 10), (97, 15), (94, 17), (92, 21), (89, 22),
     (86, 20), (82, 17), (80, 13), (77, 8), (75, 11), (73, 16),
     (70, 20), (67, 23), (64, 25), (61, 25), (58, 26), (56, 27),
     (53, 27), (50, 29), (48, 30), (44, 29), (42, 31), (40, 36),
     (36, 36), (33, 36), (30, 36), (27, 37), (26, 38), (23, 36),
     (22, 37), (19, 40), (16, 41), (14, 42), (12, 44), (9, 44),
     (7, 44), (4, 43), (2, 43), (-1, 44), (-2, 43), (-2, 37),
     (-6, 36), (-9, 37), (-10, 36)],
    # Australia
    [(114, -22), (114, -30), (116, -35), (120, -34), (124, -33),
     (128, -32), (132, -32), (135, -35), (138, -35), (140, -38),
     (145, -38), (150, -37), (153, -32), (153, -27), (150, -22),
     (146, -19), (142, -15), (142, -11), (137, -12), (135, -15),
     (132, -12), (128, -14), (124, -14), (120, -20), (114, -22)],
    # United Kingdom
    [(-5, 50), (-3, 53), (-5, 56), (-3, 58), (-1, 57), (0, 53),
     (1, 51), (-2, 51), (-4, 50), (-5, 50)],
    # Japan
    [(130, 31), (132, 33), (134, 34), (137, 35), (139, 37), (140, 39),
     (141, 41), (142, 43), (144, 44), (143, 42), (141, 40), (140, 36),
     (137, 35), (134, 34), (131, 33), (130, 31)],
    # Madagascar
    [(44, -16), (47, -15), (50, -16), (49, -19), (47, -23), (45, -25),
     (44, -22), (43, -19), (44, -16)],
    # Indonesia (key islands, simplified)
    [(95, 5), (98, 3), (101, 0), (104, -3), (106, -6), (109, -7),
     (112, -7), (115, -8), (118, -9), (121, -10), (124, -10),
     (127, -8), (130, -4), (133, -3), (136, -2), (139, -4),
     (141, -8), (138, -8), (134, -7), (131, -6), (128, -3),
     (125, 1), (122, 0), (119, 0), (116, 1), (113, 0),
     (110, 1), (107, 0), (104, 1), (100, 2), (97, 4), (95, 5)],
    # New Zealand
    [(167, -45), (169, -43), (172, -41), (174, -39), (176, -38),
     (178, -38), (176, -40), (174, -42), (171, -44), (168, -46),
     (167, -45)],
]


def _point_in_poly(lon, lat, poly):
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > lat) != (yj > lat)):
            xinters = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lon < xinters:
                inside = not inside
        j = i
    return inside


def _on_land(lon, lat):
    return any(_point_in_poly(lon, lat, poly) for poly in CONTINENTS)


# ---------------------------------------------------------------- stories

DATE_LINE = "SATURDAY, 21 NOVEMBER 2026"

HERO1 = {
    "kicker": "CONFLICT  \u00b7  KYIV, UKRAINE",
    "headline": "Russia rains 400+ drones and 110 missiles on Ukraine \u2014 two land in Poland",
    "body": ("Overnight barrage kills at least eight people in Kyiv and "
             "damages bridges and railway stations; a later strike on "
             "Kryvyi Rih wounds about 20. Warsaw calls the missiles a "
             "deliberate provocation. NATO calls it a grave violation of "
             "allied airspace and scrambles fighter jets."),
    "strip": "8 killed in Kyiv  \u00b7  Tusk: \u201cdeliberate provocation\u201d  \u00b7  NATO jets scrambled",
    "lon": 30.5, "lat": 50.5,
}

HERO2 = {
    "kicker": "JUSTICE  \u00b7  THE HAGUE",
    "headline": "World court: Myanmar guilty of Rohingya genocide",
    "body": ("The ICJ holds a state responsible for genocide for the first "
             "time; reparations ordered."),
    "lon": 4.3, "lat": 52.1,
}

HERO3 = {
    "kicker": "ECONOMY  \u00b7  NEW YORK",
    "headline": "AI rout drags S&P 500 3.7% into correction",
    "body": ("The Nasdaq erases its 2026 gains; Anthropic slides ~11% a day "
             "after its record debut. Nikkei falls 5.06%."),
    "lon": -74.0, "lat": 40.7,
}

# Stories 4-15: number, kicker, headline, body, lon, lat.
GRID = [
    (4, "POLITICS \u00b7 SHENZHEN",
     "Trump calls Putin \u201ca friend\u201d at summit with Xi",
     "Trump says Putin wants to end the war. Zelensky: \u201cHe\u2019s a killer.\u201d",
     114.1, 22.5),
    (5, "CONFLICT \u00b7 RIYADH",
     "Saudi coalition downs 3 Houthi missiles at Riyadh",
     "Third night of alerts over Riyadh; the coalition hits Hodeidah port.",
     46.7, 24.7),
    (6, "CONFLICT \u00b7 HORMUZ",
     "US\u2013Iran war grinds on as talks stall",
     "Tehran wants diplomacy with guarantees; Trump rejects its terms.",
     56.5, 26.6),
    (7, "POLITICS \u00b7 BRUSSELS",
     "UK and EU sign biggest post-Brexit deals yet",
     "Three deals on food, carbon and youth mobility; +0.5% growth a year.",
     4.4, 50.9),
    (8, "CLIMATE \u00b7 ANTALYA",
     "COP31 runs past deadline on fossil fuels",
     "The draft deal omits fossil fuels. The EU warns of a fossil summit.",
     30.7, 36.9),
    (9, "HEALTH \u00b7 LONDON",
     "Cancer pill leaves tumours undetectable in 1 in 12",
     "Trial pill daraxonrasib stops nearly every tumour growing, experts say.",
     -0.1, 51.5),
    (10, "CULTURE \u00b7 NEW YORK",
     "GTA VI takes $3.8bn on day one",
     "Rockstar\u2019s game beats every launch and single-day box-office record.",
     -74.0, 40.7),
    (11, "SPACE \u00b7 DARMSTADT",
     "BepiColombo reaches Mercury orbit",
     "The twin probes flew 10 billion km over eight years to orbit Mercury.",
     8.7, 49.9),
    (12, "DISASTER \u00b7 JUN\u00cdN, PERU",
     "Magnitude 6.7 quake shakes central Peru",
     "Strong tremor in the Andes is felt in Lima; no casualties at first.",
     -75.2, -11.2),
    (13, "TECHNOLOGY \u00b7 WASHINGTON",
     "FBI crime database reportedly hacked again",
     "CNN reports the National Crime Information Center was breached.",
     -77.0, 38.9),
    (14, "CONFLICT \u00b7 GAZA",
     "Israeli strikes kill six in Gaza",
     "Civil defence counts six dead; drones kill seven, Al Jazeera reports.",
     34.5, 31.5),
    (15, "SOCIETY \u00b7 BERLIN",
     "Gen Z protests spread across 25 countries",
     "Thousands of students march over living costs, rearmament, climate.",
     13.4, 52.5),
]

# Short items for the "Also on" column: (bold lead, rest of line).
ALSO_ON = [
    ("Palisades fire arsonist convicted \u2014",
     "12 dead, 6,800 buildings lost"),
    ("Denmark expels Russian diplomat",
     "over alleged plot to kill a rapper"),
    ("Estonia to shut five Russia crossings",
     "from 1 December"),
    ("US loses measles-free status:",
     "7,700 cases, 13 deaths"),
    ("Iraq retakes militia stronghold",
     "Jurf al-Sakhar, held 12 years"),
    ("Anthropic mathematician claims proof",
     "of the Riemann hypothesis"),
    ("Trump: ousted Nvidia chief Huang",
     "\u201cdeserves a second chance\u201d"),
    ("Bolsonaro in hospital",
     "with intestinal obstruction"),
    ("Spain votes 29 November;",
     "conservatives gain after debate"),
    ("CERN finds first evidence",
     "of an ultra-rare particle decay"),
]

TICKER = ("MARKETS   S&P 500 \u22123.7%    Nikkei \u22125.06%    "
          "Gold \u22123.98%    Bitcoin \u22124.15%    Brent crude ~$90    "
          "Nat gas +2.99%    Sensex +1.08%")

SOURCES = ("Sources: BBC News \u00b7 France 24 \u00b7 CBS News \u00b7 El Pa\u00eds "
           "\u00b7 The Guardian \u00b7 Al Jazeera \u00b7 Reuters \u00b7 PBS NewsHour "
           "\u00b7 Sky News \u00b7 The Japan Times \u00b7 Yonhap \u00b7 UPI "
           "\u00b7 Middle East Eye \u00b7 The National \u00b7 Euronews "
           "\u00b7 The Straits Times \u00b7 The Hindu. Compiled 21 November "
           "2026 from wire reports; figures as reported by the outlets named.")


# ---------------------------------------------------------------- layout

MX = 28           # left/right margin
CW = W - 2 * MX   # content width: 968


def _map_xy(lon, lat, mx, my, mw, mh):
    x = mx + (lon + 180.0) / 360.0 * mw
    y = my + (78.0 - lat) / (78.0 + 58.0) * mh
    return x, y


def _leader(cv, x0, y0, x1, y1, color):
    """Thin 1 px line from a map point to its offset number dot."""
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        cv.set(x0, y0, color)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def render(path):
    cv = Canvas(W, H, PAPER)

    # ---- masthead ------------------------------------------------------
    draw_text_centered(cv, "serif_bold_54", W // 2, 12, "THE WORLD TODAY", INK)
    cv.hline(MX, 76, CW, INK)
    cv.hline(MX, 79, CW, INK)
    draw_text(cv, "sans_10", MX, 86, "ONE DAY, ONE PAGE", GRAY)
    draw_text_centered(cv, "sans_bold_16", W // 2, 84, DATE_LINE, INK)
    right = "62 STORIES \u00b7 MOOD: UNEASY"
    draw_text(cv, "sans_10", W - MX - text_width("sans_10", right), 86,
              right, GRAY)
    cv.hline(MX, 104, CW, INK)

    # ---- heroes --------------------------------------------------------
    # Hero 1, left column.
    hx, hw = MX, 612
    draw_text(cv, "sans_bold_12", hx, 116, HERO1["kicker"], RED)
    y = draw_paragraph(cv, "sans_bold_24", hx, 134, HERO1["headline"],
                       hw, INK, 29, max_lines=3)
    y = draw_paragraph(cv, "sans_13", hx, y + 8, HERO1["body"], hw,
                       INK, 17, max_lines=5)
    cv.fill_rect(hx, 292, hw, 1, RULE)
    draw_text(cv, "sans_bold_12", hx, 300, HERO1["strip"], NAVY)

    # Divider + right column with heroes 2 and 3, laid out top to bottom
    # so nothing can overlap: the divider and hero 3 follow hero 2's end.
    rx, rw = 664, W - MX - 664
    cv.vline(652, 116, 204, RULE)
    draw_text(cv, "sans_bold_12", rx, 116, HERO2["kicker"], RED)
    y = draw_paragraph(cv, "sans_bold_18", rx, 134, HERO2["headline"],
                       rw, INK, 21, max_lines=2)
    y = draw_paragraph(cv, "sans_12", rx, y + 4, HERO2["body"], rw, INK,
                       14, max_lines=2)
    cv.hline(rx, y + 8, rw, RULE)
    y += 18
    draw_text(cv, "sans_bold_12", rx, y, HERO3["kicker"], RED)
    y = draw_paragraph(cv, "sans_bold_18", rx, y + 18, HERO3["headline"],
                       rw, INK, 21, max_lines=2)
    draw_paragraph(cv, "sans_12", rx, y + 4, HERO3["body"], rw, INK,
                   14, max_lines=2)

    cv.hline(MX, 328, CW, INK)

    # ---- world map -----------------------------------------------------
    draw_text_centered(cv, "sans_bold_12", W // 2, 338,
                       "WHERE THE DAY HAPPENED \u2014 15 STORIES ON THE MAP",
                       INK)
    map_x, map_y, map_w, map_h = MX, 356, CW, 96
    cv.fill_rect(map_x, map_y, map_w, map_h, MAP_BG)
    # Dotted landmass: even screen-space dot grid, each dot kept only
    # where its lon/lat falls on land.
    for gy in range(map_y + 3, map_y + map_h, 7):
        for gx in range(map_x + 3, map_x + map_w, 7):
            lon = (gx - map_x) / map_w * 360.0 - 180.0
            lat = 78.0 - (gy - map_y) / map_h * (78.0 + 58.0)
            if _on_land(lon, lat):
                cv.fill_circle(gx, gy, 2, LAND)
    # Numbered story dots: heroes first, then the grid. Crowded spots get
    # a small pixel offset plus a leader line from the true location, so
    # no two numbers collide (Europe and the US east coast are dense).
    dots = [(1, HERO1["lon"], HERO1["lat"], 0, 0),
            (2, HERO2["lon"], HERO2["lat"], -14, -12),
            (3, HERO3["lon"], HERO3["lat"], 16, -12)]
    dots += [(n, lon, lat, 0, 0)
             for (n, _k, _h, _b, lon, lat) in GRID]
    offsets = {9: (-22, -8), 7: (0, 14), 11: (22, 8), 15: (18, -14),
               13: (-14, 8), 10: (16, 10), 8: (22, 12), 14: (-14, 14)}
    dots = [(n, lon, lat, offsets.get(n, (0, 0))[0],
             offsets.get(n, (0, 0))[1]) for (n, lon, lat, _dx, _dy) in dots]
    for n, lon, lat, dx, dy in dots:
        x, y = _map_xy(lon, lat, map_x, map_y, map_w, map_h)
        cx, cy = int(x) + dx, int(y) + dy
        if dx or dy:
            _leader(cv, int(x), int(y), cx, cy, RED)
        cv.fill_circle(cx, cy, 8, RED)
        cv.circle(cx, cy, 8, WHITE)
        label = str(n)
        draw_text(cv, "sans_bold_12",
                  cx - text_width("sans_bold_12", label) // 2, cy - 6,
                  label, WHITE)
    draw_text(cv, "sans_10", map_x, 456,
              "Numbers match the stories below.", GRAY)
    cv.hline(MX, 470, CW, INK)

    # ---- numbered grid, stories 4-15 ----------------------------------
    draw_text(cv, "sans_bold_16", MX, 480, "THE DAY IN FULL", INK)
    right = "STORIES 4\u201315  \u00b7  EUROPE \u00b7 MIDDLE EAST \u00b7 ASIA \u00b7 AMERICAS"
    draw_text(cv, "sans_10", W - MX - text_width("sans_10", right), 484,
              right, GRAY)
    col_w = (CW - 2 * 14) // 3
    for idx, (n, kicker, headline, body, _lon, _lat) in enumerate(GRID):
        col = idx % 3
        row = idx // 3
        x = MX + col * (col_w + 14)
        y = 504 + row * 76
        # Red number tile.
        cv.fill_rect(x, y, 20, 20, RED)
        label = str(n)
        draw_text(cv, "sans_bold_12",
                  x + 10 - text_width("sans_bold_12", label) // 2, y + 4,
                  label, WHITE)
        tx = x + 28
        tw = col_w - 28
        draw_text(cv, "sans_bold_12", tx, y, kicker, RED)
        draw_paragraph(cv, "sans_bold_15", tx, y + 16, headline, tw,
                       INK, 18, max_lines=2)
        draw_paragraph(cv, "sans_12", tx, y + 50, body, tw, INK, 13,
                       max_lines=2)

    cv.hline(MX, 816, CW, INK)

    # ---- also on -------------------------------------------------------
    draw_text(cv, "sans_bold_12", MX, 826, "ALSO ON THIS DAY", RED)
    col_w2 = (CW - 20) // 2
    for idx, (lead, rest) in enumerate(ALSO_ON):
        col = idx % 2
        row = idx // 2
        x = MX + col * (col_w2 + 20)
        y = 844 + row * 17
        draw_text(cv, "sans_bold_12", x, y, "\u2022  " + lead, INK)
        lx = x + text_width("sans_bold_12", "\u2022  " + lead)
        draw_text(cv, "sans_12", lx, y, " " + rest, INK)

    # ---- markets ticker ------------------------------------------------
    cv.fill_rect(MX, 936, CW, 30, TICKER_BG)
    draw_text_centered(cv, "sans_bold_12", W // 2, 945, TICKER, WHITE)

    # ---- footer --------------------------------------------------------
    draw_paragraph(cv, "sans_10", MX, 974, SOURCES, CW, GRAY, 12,
                   max_lines=2)
    draw_text_centered(cv, "sans_bold_12", W // 2, 1004,
                       "THE WORLD TODAY  \u00b7  SATURDAY 21 NOVEMBER 2026  \u00b7  PAGE 1 OF 1",
                       INK)

    write_png(cv, path)


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    render(os.path.join(out_dir, "entry.png"))


if __name__ == "__main__":
    main()
