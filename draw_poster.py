#!/usr/bin/env python3
"""Draw "The World Today" — 21 November 2026. Pure stdlib: bitmap fonts from
fontdata.py, PNG encoded with zlib/struct. Deterministic: same bytes every run.
Layout (1024x1024): masthead, 3 hero panels, markets ticker, 20-story numbered
grid, dotted world map with 12 numbered pins, "Also on" list, sources footer.
"""
import struct
import zlib

import fontdata

W, H = 1024, 1024
PAPER = (250, 246, 236)
INK = (20, 20, 20)
RED = (180, 35, 24)
NAVY = (27, 42, 74)
MAPBLUE = (58, 90, 124)
LIGHT = (233, 226, 210)
GREY = (120, 116, 106)

# ---------------------------------------------------------------- fonts
FONTS = {}
for _name, _blob, _widths in (("REG", fontdata.REG_BLOB, fontdata.REG_WIDTHS),
                              ("BOLD", fontdata.BOLD_BLOB, fontdata.BOLD_WIDTHS)):
    import base64 as _b64
    _blob_b = _b64.b64decode("".join(_blob))
    _w = _b64.b64decode("".join(_widths))
    _glyphs = {}
    _i = 0
    for _idx, _ch in enumerate(fontdata.CHARSET):
        _gw = _blob_b[_i]
        _gh = _blob_b[_i + 1]
        _i += 2
        _nb = (_gw * _gh + 7) // 8 if _gh else 0
        _glyphs[_ch] = (_gw, _gh, _blob_b[_i:_i + _nb])
        _i += _nb
    FONTS[_name] = (_glyphs, _w)


def text_width(s, font="REG", scale=1):
    glyphs, _w = FONTS[font]
    total = 0
    for ch in s:
        g = glyphs.get(ch)
        if g is None:
            total += 4 * scale
        else:
            total += (g[0] + 1) * scale
    return total - scale if total else 0


def wrap(s, font, scale, max_w):
    """Greedy word wrap; returns list of lines that fit max_w."""
    words = s.split(" ")
    lines = []
    cur = ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if text_width(trial, font, scale) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            # hard-split a word that alone is too long
            while text_width(word, font, scale) > max_w and len(word) > 1:
                cut = len(word)
                while cut > 1 and text_width(word[:cut], font, scale) > max_w:
                    cut -= 1
                lines.append(word[:cut])
                word = word[cut:]
            cur = word
    if cur:
        lines.append(cur)
    return lines


# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)
        for i in range(0, w * h * 3, 3):
            self.px[i] = bg[0]
            self.px[i + 1] = bg[1]
            self.px[i + 2] = bg[2]

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i] = c[0]
            self.px[i + 1] = c[1]
            self.px[i + 2] = c[2]

    def rect(self, x, y, w, h, c):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.set(xx, yy, c)

    def hline(self, x, y, w, c):
        for xx in range(x, x + w):
            self.set(xx, y, c)

    def vline(self, x, y, h, c):
        for yy in range(y, y + h):
            self.set(x, yy, c)

    def line(self, x0, y0, x1, y1, c):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.set(x0, y0, c)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def circle(self, cx, cy, r, c):
        import math
        for deg in range(0, 360):
            a = math.radians(deg)
            self.set(int(cx + r * math.cos(a)), int(cy + r * math.sin(a)), c)

    def disc(self, cx, cy, r, c):
        for yy in range(cy - r, cy + r + 1):
            for xx in range(cx - r, cx + r + 1):
                if (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r:
                    self.set(xx, yy, c)

    def ring(self, cx, cy, r, c, thick=1):
        for t in range(thick):
            self.circle(cx, cy, r - t, c)

    def text(self, x, y, s, font="REG", scale=1, color=INK):
        glyphs, _w = FONTS[font]
        cx = x
        for ch in s:
            g = glyphs.get(ch)
            if g is None:
                cx += 4 * scale
                continue
            gw, gh, bits = g
            if gh:
                for gy in range(gh):
                    for gx in range(gw):
                        bit = (bits[(gy * gw + gx) // 8] >> (7 - (gy * gw + gx) % 8)) & 1
                        if bit:
                            for sy in range(scale):
                                for sx in range(scale):
                                    self.set(cx + gx * scale + sx, y + gy * scale + sy, color)
            cx += (gw + 1) * scale
        return cx

    def text_center(self, cx, y, s, font="REG", scale=1, color=INK):
        self.text(cx - text_width(s, font, scale) // 2, y, s, font, scale, color)

    def para(self, x, y, s, font, scale, max_w, color=INK, leading=14):
        lines = wrap(s, font, scale, max_w)
        for i, ln in enumerate(lines):
            self.text(x, y + i * leading, ln, font, scale, color)
        return len(lines)

    def to_png(self):
        raw = bytearray()
        stride = self.w * 3
        for y in range(self.h):
            raw.append(0)
            raw.extend(self.px[y * stride:(y + 1) * stride])
        comp = zlib.compress(bytes(raw), 9)

        def chunk(typ, data):
            c = struct.pack(">I", len(data)) + typ + data
            return c + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)

        ihdr = struct.pack(">IIBBBBB", self.w, self.h, 8, 2, 0, 0, 0)
        return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
                + chunk(b"IDAT", comp) + chunk(b"IEND", b""))


# ---------------------------------------------------------------- world map
# 44 rows x 96 cols, '#' = land. Equirectangular, lat 75..-55, lon -180..180.
MAP = [
    "                ############    #########          #####        ################################",
    "              ################# ##########        ######    ####################################",
    "   #######################################                 #####################################",
    "   ############################## #######          #############################################",
    "    ##############################        ###    ###############################################",
    "     ############################## ##        ##################################################",
    "               #####################          ##################################################",
    "               #####################          ##################################################",
    "                ####################         ###################################################",
    "               ################              ###########################################        ",
    "               ################              ############  ############################         ",
    "               ################              ##########################################         ",
    "               #################             ####################         #############         ",
    "               ##################            ########################################           ",
    "               ###################           ########################################           ",
    "               ###################           ########################################           ",
    "               ###################           ########################################           ",
    "                  ################           ########################################           ",
    "                    ##############         ###############        ###################           ",
    "                       ####                ###     #########            #############           ",
    "                        ####               ####   ############          #############           ",
    "                         ####              #####   ###########     #### #############           ",
    "                           ##              ####     ##########           #############          ",
    "                           ########        ###    ##########             #############          ",
    "                           #########              ##########             #############          ",
    "                           #############          ##########             ##############         ",
    "                           ###########             #########             ##############         ",
    "                           ###########             #########             #############          ",
    "                           ###########             ########              ##############         ",
    "                           ###########              #######                        #####        ",
    "                           ###########              ##########                ###########       ",
    "                           ###########              ##########                ###########       ",
    "                           ###########              #######                   ###########       ",
    "                           ##########               #######                   ###########       ",
    "                           #########                #######                    ##########       ",
    "                           ########                  #####                     ##########     ##",
    "                           #######                   ####                      ##########     ##",
    "                           ######                                               ########      ##",
    "                           #####                                                 ######       ##",
    "                           ####                                                               ##",
    "                           ###                                                                ##",
    "                           ##                                                                   ",
    "                           ##                                                                   ",
    "                           ##                                                                   ",
]


def map_xy(lat, lon, x0, y0, mw, mh):
    col = (lon + 180.0) / 360.0 * 96.0
    row = (75.0 - lat) / 130.0 * 44.0
    return int(x0 + col / 96.0 * mw), int(y0 + row / 44.0 * mh)


# ---------------------------------------------------------------- stories
# heroes: (kicker, headline, body, figure)
HEROES = [
    ("CLIMATE \u00b7 ANTALYA, TURKEY",
     "COP31 slips into overtime",
     "Nearly 200 nations haggle past the deadline in Antalya. The slimmed draft drops every mention of fossil fuels \u2014 and a $120bn target.",
     "1.8\u00b0C"),
    ("MIDDLE EAST \u00b7 RIYADH",
     "Riyadh: three missiles downed",
     "Saudi defences stop the 01:53 barrage, the second strike in days after the tallest tower was hit. Houthis warn airlines away.",
     "3 DOWN"),
    ("DISASTER \u00b7 JUNIN, PERU",
     "M6.7 quake shakes Peru's Andes",
     "The tremor strikes 129 km deep near Junin at 19:09 local. Buildings sway in the capital, but no deaths or major damage are reported.",
     "M6.7"),
]

# grid: (number, region, headline, body) — headline <= 2 lines, body <= 2 lines at 209 px
GRID = [
    (4, "UKRAINE", "Russia fires 400+ drones, 110 missiles",
     "Three Kyiv bridges hit; at least 8 killed."),
    (5, "POLAND", "Two Russian missiles land in Poland",
     "Tusk: deliberate provocation; NATO: grave."),
    (6, "THE HAGUE", "UN court: Myanmar guilty of genocide",
     "First time The Hague holds a state liable."),
    (7, "MARKETS", "S&P 500 falls 3.7% into correction",
     "Nasdaq wipes out 2026 gain; Nvidia -14%."),
    (8, "CHINA", "Trump, Xi, Putin meet in Shenzhen",
     "First trilateral: no nuclear war, ever."),
    (9, "BRUSSELS", "UK and EU sign biggest post-Brexit deal",
     "Food, carbon markets, youth mobility."),
    (10, "SPACE", "BepiColombo reaches Mercury orbit",
     "Eight-year ESA-JAXA voyage ends at last."),
    (11, "PHILIPPINES", "Air Niugini 767 lands in Davao",
     "Engine fire alert; all 146 aboard safe."),
    (12, "GAZA", "Israeli strikes kill six in Gaza",
     "Floods swamp tents; settlers attack farms."),
    (13, "GULF", "Two tankers hit mines off Hormuz",
     "Fires at sea; a third tanker hit earlier."),
    (14, "DENMARK", "Denmark expels Russian attache",
     "Alleged plot to kill rapper near Copenhagen."),
    (15, "GERMANY", "Merz, Qatar emir sign defence pact",
     "Doha pledges 15bn euros more investment."),
    (16, "TECH", "Anthropic falls 11% after debut",
     "A wake-up call for the whole AI trade."),
    (17, "HEALTH", "Pill makes pancreatic tumours vanish",
     "One in 12 patients clear in early trial."),
    (18, "LOS ANGELES", "Man guilty of starting Palisades fire",
     "LA jury convicts over the deadly blaze."),
    (19, "NIGERIA", "Funeral boat capsizes in Nigeria",
     "Four dead, two children; 300 feared lost."),
    (20, "SENEGAL", "21 dead as migrant boat sinks off Senegal",
     "One rescued off Loumpoul; search goes on."),
    (21, "BRUSSELS", "EU approves 1bn euros more for Ukraine",
     "Drones and air defence top the package."),
    (22, "IRAQ", "Iraqi troops enter militia stronghold",
     "Jurf al-Sakhar taken after a deal."),
    (23, "NEW YORK", "19 years for Sikh-leader murder plot",
     "New York sentences Indian man."),
]

# also on: (number, headline) — one line each at 294 px
ALSO = [
    (24, "Las Vegas GP qualifying, 03:00"),
    (25, "Haiti: Salvadoran troops hit by blast"),
    (26, "Tanzania: Lissu convicted of sedition"),
    (27, "Cyclone Xavier nears Cook Islands"),
    (28, "Honda, Toyota recall 1.6m cars"),
    (29, "Trump: Iran wants a deal"),
    (30, "Japan buys 8m barrels Saudi crude"),
    (31, "EU summons Russia's envoy"),
    (32, "NTSB: upkeep doomed Kamaka Air"),
    (33, "Oil rises on Iran war fears"),
    (34, "Zelensky: Crimea bridge 'won't remain'"),
    (35, "Nepal ends flood-victim search"),
    (36, "UAE condemns Houthi strikes"),
]

# map pins: (story number, lat, lon). Pin 1 is nudged NW of Antalya so it does
# not sit on top of pin 9 (Gaza) on this scale.
PINS = [
    (1, 39.5, 27.0), (2, 24.7, 46.7), (3, -11.1, -75.9), (4, 50.5, 30.5),
    (5, 50.0, 22.0), (6, 52.1, 4.3), (7, 22.5, 114.1), (8, 7.1, 125.6),
    (9, 31.5, 34.5), (19, 4.8, 6.1), (20, 15.4, -16.5), (24, 36.2, -115.1),
]

TICKER = ("S&P 500 -3.70%  \u00b7  NASDAQ -5.28%  \u00b7  NIKKEI -5.06%  \u00b7  "
          "KOSPI -5.21%  \u00b7  BRENT ~$90  \u00b7  NVIDIA -14%  \u00b7  ANTHROPIC -11%")

TIMELINE = ("00:09 PERU QUAKE  \u00b7  01:53 RIYADH ALERT  \u00b7  "
           "03:00 LAS VEGAS QUALIFYING  \u00b7  12:08 DAVAO LANDING  \u00b7  "
           "18:24 BEPICOLOMBO BURN")


# ---------------------------------------------------------------- drawing
def draw_hero_art(cv, x, y, w, h, kind):
    """Small geometric illustration at the bottom of a hero panel.
    Art box is (x, y, w, h); keep every stroke inside it."""
    import math
    if kind == 0:  # COP31: globe + rising arrow + sun
        cx, cy, r = x + 50, y + 30, 26
        cv.circle(cx, cy, r, NAVY)
        cv.circle(cx, cy, r - 5, NAVY)
        for dy in (-12, 0, 12):
            half = int(math.sqrt(max(0, r * r - dy * dy)))
            cv.line(cx - half, cy + dy, cx + half, cy + dy, NAVY)
        # rising temperature arrow
        ax = x + 118
        cv.line(ax, y + 52, ax + 40, y + 16, RED)
        cv.line(ax + 40, y + 16, ax + 28, y + 16, RED)
        cv.line(ax + 40, y + 16, ax + 40, y + 28, RED)
        cv.text(ax + 50, y + 8, "1.8\u00b0C", "BOLD", 2, RED)
        cv.text(ax + 50, y + 34, "HOTTER", "BOLD", 1, INK)
        cv.text(ax + 50, y + 48, "THAN 1850s", "BOLD", 1, INK)
    elif kind == 1:  # Riyadh: radar arcs + missile trails
        cx, cy = x + 40, y + 50
        for rr in (14, 24, 34):
            cv.circle(cx, cy, rr, MAPBLUE)
        cv.line(cx, cy, cx + 32, cy - 32, MAPBLUE)
        cv.line(cx, cy, cx + 42, cy - 10, MAPBLUE)
        for mx, my in ((x + 150, y + 12), (x + 185, y + 26), (x + 220, y + 8)):
            cv.disc(mx, my, 3, RED)
            cv.line(mx, my, mx - 26, my + 18, RED)
        cv.text(x + 140, y + 38, "3 INTERCEPTED", "BOLD", 1, RED)
        cv.text(x + 140, y + 52, "01:53 ALERT", "BOLD", 1, INK)
    else:  # Peru: seismic zigzag + mountains
        cv.line(x + 8, y + 34, x + 60, y + 34, NAVY)
        pts = [(60, 0), (72, -20), (84, 12), (96, -26), (108, 6), (120, -14),
               (132, 4), (144, -8), (156, 0)]
        for (dx0, dy0), (dx1, dy1) in zip(pts, pts[1:]):
            cv.line(x + 60 + dx0, y + 34 + dy0,
                    x + 60 + dx1, y + 34 + dy1, RED)
        cv.line(x + 216, y + 62, x + 252, y + 28, NAVY)
        cv.line(x + 252, y + 28, x + 288, y + 62, NAVY)
        cv.line(x + 252, y + 28, x + 244, y + 42, NAVY)
        cv.line(x + 244, y + 42, x + 262, y + 38, NAVY)
        cv.text(x + 8, y + 48, "129 KM DEEP", "BOLD", 1, INK)


def draw():
    cv = Canvas(W, H, PAPER)
    # masthead
    cv.text_center(512, 10, "SATURDAY, 21 NOVEMBER 2026  \u00b7  36 STORIES  \u00b7  7 REGIONS  \u00b7  EVERY FIGURE ATTRIBUTED",
                   "BOLD", 1, GREY)
    cv.text_center(512, 26, "THE WORLD TODAY", "BOLD", 4, INK)
    cv.rect(24, 76, 976, 3, RED)
    cv.rect(24, 81, 976, 1, INK)

    # hero panels
    hx = [24, 353, 682]
    for i, (kicker, head, body, fig) in enumerate(HEROES):
        x = hx[i]
        cv.rect(x, 90, 317, 200, (255, 255, 255))
        cv.rect(x, 90, 317, 1, INK)
        cv.rect(x, 289, 317, 1, INK)
        cv.text(x + 10, 98, "%d  %s" % (i + 1, kicker), "BOLD", 1, RED)
        n = cv.para(x + 10, 116, head, "BOLD", 2, 297, INK, leading=26)
        by = 116 + n * 26 + 4
        cv.para(x + 10, by, body, "REG", 1, 297, INK, leading=14)
        draw_hero_art(cv, x + 10, 224, 297, 64, i)

    # markets ticker
    cv.rect(24, 298, 976, 26, INK)
    cv.text_center(512, 305, TICKER, "BOLD", 1, (250, 246, 236))

    # numbered grid: 4 cols x 5 rows
    gx0, gy0 = 24, 332
    cw, ch = 235, 68
    for idx, (num, region, head, body) in enumerate(GRID):
        col, row = idx % 4, idx // 4
        x = gx0 + col * (cw + 12)
        y = gy0 + row * ch
        cv.hline(x, y, cw, LIGHT)
        cv.text(x, y + 4, "%02d" % num, "BOLD", 1, RED)
        cv.text(x + 26, y + 4, region, "BOLD", 1, GREY)
        n = cv.para(x + 26, y + 18, head, "BOLD", 1, 209, INK, leading=12)
        cv.para(x + 26, y + 18 + n * 12, body, "REG", 1, 209, INK, leading=12)

    # dotted world map
    mx0, my0, mw, mh = 24, 700, 620, 224
    cv.text(24, 680, "THE WORLD \u2014 12 PLACES", "BOLD", 1, INK)
    cv.text(24 + 300, 680, "EACH NUMBER IS A STORY ON THIS PAGE", "REG", 1, GREY)
    for r, row in enumerate(MAP):
        for c, ch in enumerate(row):
            if ch == "#":
                px = mx0 + int((c + 0.5) / 96.0 * mw)
                py = my0 + int((r + 0.5) / 44.0 * mh)
                cv.disc(px, py, 2, MAPBLUE)
    for num, lat, lon in PINS:
        px, py = map_xy(lat, lon, mx0, my0, mw, mh)
        cv.disc(px, py, 9, RED)
        cv.ring(px, py, 9, (255, 255, 255), 1)
        label = str(num)
        cv.text(px - text_width(label, "BOLD", 1) // 2, py - 6, label, "BOLD", 1, (255, 255, 255))

    # also on
    ax0 = 676
    cv.text(ax0, 680, "ALSO ON", "BOLD", 1, INK)
    cv.rect(ax0, 696, 324, 1, INK)
    ay = 704
    for n, h in ALSO:
        cv.text(ax0, ay, "%02d" % n, "BOLD", 1, RED)
        cv.text(ax0 + 30, ay, h, "REG", 1, INK)
        ay += 16

    # footer
    cv.rect(24, 932, 976, 2, INK)
    cv.text_center(512, 944, "SOURCES: BBC \u00b7 REUTERS \u00b7 AP \u00b7 AL JAZEERA \u00b7 THE GUARDIAN \u00b7 AFP \u00b7 PBS \u00b7 ONE TURN",
                   "BOLD", 1, INK)
    cv.text_center(512, 962, TIMELINE, "REG", 1, INK)
    cv.text_center(512, 980, "EVERY FIGURE ATTRIBUTED  \u00b7  DATE-CHECKED 21 NOV 2026  \u00b7  36 STORIES  \u00b7  7 REGIONS",
                   "BOLD", 1, RED)
    cv.text_center(512, 998, "THE WORLD TODAY \u2014 THE PICTURE OF SATURDAY'S NEWS",
                   "REG", 1, GREY)
    return cv


def main():
    cv = draw()
    png = cv.to_png()
    import os
    out = os.environ.get("MAKEFUN_OUTPUT_DIR", "out")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "entry.png"), "wb") as f:
        f.write(png)
    print("wrote entry.png", len(png), "bytes")


if __name__ == "__main__":
    main()
