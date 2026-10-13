import math
from functools import lru_cache

import pygame


# ── Sprite caches ─────────────────────────────────────────────────────────────
# Every glow / particle / panel used to allocate a fresh Surface on every draw
# call (hundreds per frame).  These caches build each sprite once and reuse it.
# Cached surfaces are shared: callers must only blit them, never draw onto them.

@lru_cache(maxsize=8192)
def _q_cached(color: tuple, step: int) -> tuple:
    return tuple(min(255, int(round(c / step)) * step) for c in color)


def _q(color: tuple, step: int = 8) -> tuple:
    """Quantise an RGB colour so continuously-varying colours share sprites."""
    return _q_cached(tuple(color[:3]), step)


def _qa(alpha: float, step: int = 16) -> int:
    """Quantise an alpha value (0-255) to a small set of levels."""
    return max(0, min(255, int(round(alpha / step)) * step))


@lru_cache(maxsize=4096)
def circle_sprite(color: tuple, radius: int, alpha: int) -> pygame.Surface:
    r = max(1, int(radius))
    s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
    pygame.draw.circle(s, (*color[:3], alpha), (r, r), r)
    return s


@lru_cache(maxsize=2048)
def ring_sprite(color: tuple, radius: int, alpha: int, width: int = 2) -> pygame.Surface:
    r = max(1, int(radius))
    s = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
    pygame.draw.circle(s, (*color[:3], alpha), (r + 2, r + 2), r, width)
    return s


@lru_cache(maxsize=512)
def _rect_sprite(w: int, h: int, color: tuple, alpha: int, radius: int) -> pygame.Surface:
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(s, (*color[:3], alpha), (0, 0, w, h), border_radius=radius)
    return s


@lru_cache(maxsize=256)
def _border_sprite(w: int, h: int, color: tuple, radius: int) -> pygame.Surface:
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(s, (*color[:3], 180), (0, 0, w, h), 2, border_radius=radius)
    return s


def fade_circle(surf: pygame.Surface, color: tuple, center: tuple,
                radius: int, alpha: float) -> None:
    """Blit a cached, alpha-quantised filled circle centred on *center*."""
    a = _qa(alpha)
    if a <= 0:
        return
    r = max(1, int(radius))
    surf.blit(circle_sprite(_q(color), r, a),
              (int(center[0]) - r, int(center[1]) - r))


def fade_ring(surf: pygame.Surface, color: tuple, center: tuple,
              radius: int, alpha: float) -> None:
    a = _qa(alpha)
    if a <= 0 or radius <= 0:
        return
    r = int(radius)
    surf.blit(ring_sprite(_q(color), r, a),
              (int(center[0]) - r - 2, int(center[1]) - r - 2))


# ── Public drawing helpers (API unchanged) ────────────────────────────────────

def glow_circle(surf: pygame.Surface, color: tuple, pos: tuple,
                radius: int, alpha: int = 50) -> None:
    """Draw a soft radial glow centred at pos."""
    r2 = int(radius) * 2
    if r2 <= 0:
        return
    surf.blit(circle_sprite(_q(color), r2, int(alpha)),
              (int(pos[0]) - r2, int(pos[1]) - r2))


def glow_circle_multi(surf: pygame.Surface, color: tuple, pos: tuple,
                      radius: int, layers: int = 3) -> None:
    """Multi-layer glow for a richer bloom effect."""
    for i in range(layers, 0, -1):
        r = radius + i * 9
        a = max(4, 38 // i)
        glow_circle(surf, color, pos, r, a)
    glow_circle(surf, color, pos, radius, 65)


def alpha_rect(surf: pygame.Surface, color: tuple, rect: tuple,
               alpha: int, radius: int = 0) -> None:
    """Draw a semi-transparent filled rectangle."""
    w, h = int(rect[2]), int(rect[3])
    if w <= 0 or h <= 0:
        return
    surf.blit(_rect_sprite(w, h, tuple(color[:3]), int(alpha), int(radius)),
              (int(rect[0]), int(rect[1])))


def draw_panel(surf: pygame.Surface, rect: tuple,
               bg_color: tuple = (8, 8, 22),
               border_color: tuple = (50, 50, 90),
               alpha: int = 200, radius: int = 8) -> None:
    """Translucent dark panel with border."""
    alpha_rect(surf, bg_color, rect, alpha, radius)
    w, h = int(rect[2]), int(rect[3])
    if w <= 0 or h <= 0:
        return
    surf.blit(_border_sprite(w, h, tuple(border_color), int(radius)),
              (int(rect[0]), int(rect[1])))


def rotate_points(points: list, angle: float, cx: float, cy: float) -> list:
    """Rotate (x,y) points around (cx, cy) by angle radians."""
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    result = []
    for x, y in points:
        dx, dy = x - cx, y - cy
        result.append((cx + dx * cos_a - dy * sin_a,
                       cy + dx * sin_a + dy * cos_a))
    return result


def lerp_color(c1: tuple, c2: tuple, t: float) -> tuple:
    """Linearly interpolate between two RGB colors."""
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))
