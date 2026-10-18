#!/usr/bin/env python3
"""
stress_bench.py — headless engine benchmark.

    python tools/stress_bench.py            # 100 300 600 1000 enemies
    python tools/stress_bench.py 500 2000   # custom crowd sizes

Keeps N enemies alive, fires weapons constantly, and reports per-frame update /
draw cost.  Uses only the public Game API so it also runs on older versions of
the game (handy for before/after comparisons).  Software rendering: compare
ratios, not absolute FPS, across machines.
"""
import os, sys, time, random, statistics as st
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.getcwd())
import pygame
pygame.init(); pygame.display.set_mode((1280, 720))
from game.game import Game

KINDS = ("standard", "hunter", "swarm", "phantom", "splitter", "berserker")
FRAMES, WARMUP = 240, 40


def run(n: int) -> None:
    random.seed(1)
    g = Game(None)
    g.meh_blocks.clear(); g.wave_mgr._break_timer = 9e9
    surf = pygame.Surface((1280, 720), pygame.SRCALPHA)
    ups, drs, kills0 = [], [], g.score
    for f in range(FRAMES):
        while len(g.enemies) < n:
            g._spawn_entity(random.choice(KINDS))
        g.hp = 3; g.perk_pending = False
        g.player.weapon_index = (f // 60) % 2          # plasma, spread
        g._logical_mouse = (random.randint(0, 1280), random.randint(0, 720))
        g.player._fire(g._logical_mouse, g.enemies, 1 / 60)
        t0 = time.perf_counter(); g.update(1 / 60); t1 = time.perf_counter()
        g.draw(surf);                                t2 = time.perf_counter()
        ups.append((t1 - t0) * 1000); drs.append((t2 - t1) * 1000)
    u, d = ups[WARMUP:], drs[WARMUP:]
    tot = [a + b for a, b in zip(u, d)]
    p95 = sorted(tot)[int(len(tot) * 0.95)]
    dust = len(getattr(g, "dust", ()))
    print(f"{n:5d} enemies | update {st.mean(u):6.2f} ms | draw {st.mean(d):6.2f} ms | "
          f"total {st.mean(tot):6.2f} ms (p95 {p95:6.2f}) -> {1000 / st.mean(tot):5.0f} FPS ceiling"
          f" | kills {g.score - kills0 > 0 and 'yes' or 'no'}, dust {dust}")


if __name__ == "__main__":
    sizes = [int(a) for a in sys.argv[1:]] or [100, 300, 600, 1000]
    for n in sizes:
        run(n)
