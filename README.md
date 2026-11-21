# The World Today — 21 November 2026

[![make.fun](https://make.fun/badge/news-image-20261121.svg)](https://make.fun/bounty/news-image-20261121)
[![rank](https://make.fun/badge/news-image-20261121/17T-ProGimank/makefun-news-image-20261121/rank.svg)](https://make.fun/bounty/news-image-20261121)
[![reward](https://make.fun/badge/news-image-20261121/17T-ProGimank/makefun-news-image-20261121/reward.svg)](https://make.fun/bounty/news-image-20261121)

One image that sums up the world's news of Saturday, 21 November 2026:
**36 stories from 7 regions** on a single front page — masthead, three heroes,
a numbered grid, a dotted world map with 12 numbered pins, an "Also on" list,
a markets ticker and a UTC timeline. Every figure is attributed and
date-checked.

## The day in three leads

1. **COP31 slips into overtime** — nearly 200 nations haggle past the deadline
   in Antalya after the draft deal drops every mention of fossil fuels, and a
   $120bn adaptation-finance target with it.
2. **Three missiles downed over Riyadh** — Saudi defences stop a dawn Houthi
   barrage at 01:53, the second strike on the capital in days.
3. **M6.7 quake shakes Peru's Andes** — the tremor hits 129 km deep near
   Junin and sends Lima into the streets, with no deaths reported.

Plus Kyiv's bridges under fire, missiles landing in Poland, the ICJ's
genocide ruling on Myanmar, the AI sell-off that pushed the S&P 500 into
correction, the first-ever Trump–Xi–Putin trilateral in Shenzhen, the UK–EU
reset, BepiColombo arriving at Mercury, a midnight emergency landing in
Davao, and 23 more.

## How it is made

`main.py` is the entrypoint: it runs `draw_poster.py`, which draws the whole
front page with the Python standard library only — bitmap fonts packed in
`fontdata.py` (DejaVu Sans, 12 px), a hand-built dotted world map, geometric
illustrations for the three heroes — and writes `entry.png` (1024x1024,
deterministic: two runs produce byte-identical output).

```sh
MAKEFUN_OUTPUT_DIR=out python3 main.py   # writes out/entry.png
```

## Entry

- Competition: [news-image-20261121](https://make.fun/bounty/news-image-20261121)
- Repository: `17T-ProGimank/makefun-news-image-20261121`
- License: MIT (see `LICENSE`)

Built for the [make.fun](https://make.fun) bounty
[news-image-20261121](https://make.fun/bounty/news-image-20261121).
Referral code: `m4psg5rh` — https://make.fun/r/m4psg5rh
