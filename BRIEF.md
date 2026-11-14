# Task: make.fun food-picture-01 entry

Build main.py (Python 3.13, stdlib only) in this repo root that:
1. Writes one picture of food or drink to /output/entry.png (PNG, max 1 MiB, max 1024x1024 px)
2. Fully deterministic (two runs byte-identical)
3. NO network at runtime
4. Goal: the AI judge picks the BEST-LOOKING FOOD picture. Make food that looks delicious, appetizing, mouth-watering.

Ideas: a gourmet burger with sesame bun / sushi platter / ramen bowl with egg / pancake stack with berries & syrup. Rich colors, appetizing warm tones, detail (texture, highlights, steam). Something a food photographer would shoot.

Rules:
- main.py at repo root, stdlib only (os, math, struct, zlib etc)
- LICENSE: already provided (MIT) - do not modify
- IMPORTANT: write main.py with a tool call, then REVISE it in at least one later step (min 2 file-writing turns on main.py - refine details, add texture/highlights)
- Test with MAKEFUN_OUTPUT env var redirecting output dir; run twice, verify byte-identical (sha256)
- Commit at the end, do NOT push
