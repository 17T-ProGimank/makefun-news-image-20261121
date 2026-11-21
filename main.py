"""Entrypoint: draw the 21 November 2026 world-news poster to entry.png.

Standard library only. Runs with no network and writes the same bytes
on every run.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import draw_poster

OUT_DIR = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    draw_poster.render(os.path.join(OUT_DIR, "entry.png"))


if __name__ == "__main__":
    main()
