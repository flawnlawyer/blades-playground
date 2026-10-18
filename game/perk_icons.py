"""
perk_icons.py — Procedurally drawn icons for each perk (no image assets).
draw_perk_icon(surf, key, cx, cy, color, s) draws centred on (cx, cy); s ~ half-size.
"""
from __future__ import annotations
import math
import pygame


def _dim(c: tuple, k: float) -> tuple:
    return tuple(max(0, min(255, int(v * k))) for v in c[:3])


def draw_perk_icon(surf: pygame.Surface, key: str, cx: int, cy: int,
                   color: tuple, s: int = 26) -> None:
    d = pygame.draw
    if key == "overclock":                                   # stacked chevrons >>>
        for i in range(3):
            x = cx - s * 0.7 + i * s * 0.6
            d.lines(surf, _dim(color, 0.45 + 0.28 * i), False,
                    [(x, cy - s * 0.65), (x + s * 0.45, cy), (x, cy + s * 0.65)], 4)
    elif key == "pierce":                                    # arrow through two targets
        for x in (cx - s * 0.35, cx + s * 0.3):
            d.circle(surf, _dim(color, 0.6), (int(x), cy), int(s * 0.38), 2)
        d.line(surf, color, (cx - s, cy), (cx + s * 0.85, cy), 3)
        d.polygon(surf, color, [(cx + s, cy), (cx + s * 0.62, cy - s * 0.3), (cx + s * 0.62, cy + s * 0.3)])
    elif key == "arc_lattice":                               # three nodes joined by lightning
        n = [(cx - s * 0.85, cy + s * 0.45), (cx, cy - s * 0.55), (cx + s * 0.85, cy + s * 0.45)]
        for a, b in zip(n, n[1:]):
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            d.lines(surf, color, False, [a, (mx - 5, my + 3), (mx + 5, my - 3), b], 2)
        for p in n:
            d.circle(surf, color, (int(p[0]), int(p[1])), 6)
    elif key == "phase_drive":                               # fading afterimages
        for i, (dx, r) in enumerate(((-0.85, 5), (-0.25, 8), (0.5, 11))):
            d.circle(surf, _dim(color, 0.35 + 0.32 * i), (int(cx + dx * s), cy), r, 0 if i == 2 else 2)
        for k in (-0.35, 0.0, 0.35):
            d.line(surf, _dim(color, 0.5), (cx - s, cy + k * s), (cx - s * 0.5, cy + k * s), 1)
    elif key == "surge":                                     # lightning bolt
        pts = [(cx + 5, cy - s), (cx - s * 0.55, cy + 2), (cx - 2, cy + 2),
               (cx - 7, cy + s), (cx + s * 0.6, cy - 5), (cx + 2, cy - 5)]
        d.polygon(surf, color, pts)
    elif key == "salvage":                                   # charged cell
        d.rect(surf, color, (cx - s * 0.7, cy - s * 0.45, s * 1.35, s * 0.9), 2, border_radius=3)
        d.rect(surf, color, (cx + s * 0.65, cy - s * 0.18, 5, s * 0.36))
        for i in range(3):
            d.rect(surf, _dim(color, 0.55 + 0.2 * i),
                   (cx - s * 0.58 + i * s * 0.4, cy - s * 0.3, s * 0.3, s * 0.6))
    elif key == "volatile":                                  # detonation
        d.circle(surf, color, (cx, cy), int(s * 0.3))
        for i in range(8):
            a = math.tau * i / 8
            r0, r1 = s * 0.5, s * (1.0 if i % 2 == 0 else 0.78)
            d.line(surf, color, (cx + math.cos(a) * r0, cy + math.sin(a) * r0),
                   (cx + math.cos(a) * r1, cy + math.sin(a) * r1), 3)
    elif key == "repair":                                    # plus
        t = max(5, int(s * 0.3))
        d.rect(surf, color, (cx - t // 2, cy - s * 0.85, t, s * 1.7), border_radius=2)
        d.rect(surf, color, (cx - s * 0.85, cy - t // 2, s * 1.7, t), border_radius=2)
    elif key == "second_wind":                               # circular arrow
        r = int(s * 0.75)
        d.arc(surf, color, (cx - r, cy - r, r * 2, r * 2), 0.6, math.tau - 0.35, 3)
        ax, ay = cx + math.cos(0.6) * r, cy - math.sin(0.6) * r
        d.polygon(surf, color, [(ax + 9, ay - 2), (ax - 3, ay - 9), (ax - 2, ay + 8)])
        d.circle(surf, _dim(color, 0.7), (cx, cy), 5)
    else:                                                    # unknown perk: generic badge
        d.circle(surf, color, (cx, cy), int(s * 0.8), 2)
        d.circle(surf, color, (cx, cy), int(s * 0.3))
