#!/usr/bin/env python3
"""Entrypoint for The World Today — 21 November 2026.
Draws the front page with draw_poster.py (pure stdlib) and writes entry.png
to MAKEFUN_OUTPUT_DIR. No network, no third-party packages.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import draw_poster


def main():
    out = os.environ.get("MAKEFUN_OUTPUT_DIR", "out")
    os.makedirs(out, exist_ok=True)
    canvas = draw_poster.draw()
    png = canvas.to_png()
    path = os.path.join(out, "entry.png")
    with open(path, "wb") as f:
        f.write(png)
    print("wrote %s (%d bytes)" % (path, len(png)))


if __name__ == "__main__":
    main()
