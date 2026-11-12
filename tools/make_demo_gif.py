#!/usr/bin/env python3
"""
make_demo_gif.py — render docs/demo.gif: the balance bot playing the real game (Prism boss intro + fight).
   python tools/make_demo_gif.py          (needs Pillow)
It is the bot playing, not a human — the README says so.
"""
import os, random, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy"); os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.getcwd()); sys.path.insert(0, "tools")
import pygame
import balance_bot as bb
from PIL import Image

SECONDS, FPS, SIZE = 9.0, 12, (512, 288)
g = bb.make_game(2024, {"overclock": 2, "pierce": 1, "volatile": 1, "arc_lattice": 1})
g.input_source = bb.Bot(random.Random(7), "skilled")
g.set_wave(10)                                              # -> The Prism, intro cinematic included
g.renderer.set_theme(2); g.renderer._fade = 0
surf = pygame.Surface((1280, 720), pygame.SRCALPHA)
frames, dt, step = [], 1 / 30, round(30 / FPS)
for i in range(int(SECONDS * 30)):
    g.hp = max(g.hp, 2)                                    # keep the bot alive for the clip
    g.update(dt)
    if g.perk_pending:
        g.perk_pending = False
    if i % step == 0:
        g.draw(surf)
        rgb = pygame.Surface((1280, 720)); rgb.blit(surf, (0, 0))
        img = Image.frombytes("RGB", (1280, 720), pygame.image.tostring(rgb, "RGB")).resize(SIZE, Image.LANCZOS)
        frames.append(img.quantize(colors=96, method=Image.MEDIANCUT, dither=Image.NONE))
os.makedirs("docs", exist_ok=True)
frames[0].save("docs/demo.gif", save_all=True, append_images=frames[1:], duration=int(1000 / FPS), loop=0, optimize=True)
print(f"docs/demo.gif: {len(frames)} frames, {os.path.getsize('docs/demo.gif') / 1e6:.2f} MB")
