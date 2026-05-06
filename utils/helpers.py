import math
import pygame


def glow_circle(surf: pygame.Surface, color: tuple, pos: tuple,
                radius: int, alpha: int = 50) -> None:
    """Draw a soft radial glow centred at pos."""
    r2 = radius * 2
    s = pygame.Surface((r2 * 2, r2 * 2), pygame.SRCALPHA)
    pygame.draw.circle(s, (*color[:3], alpha), (r2, r2), r2)
    surf.blit(s, (int(pos[0]) - r2, int(pos[1]) - r2))


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
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(s, (*color[:3], alpha), (0, 0, w, h),
                     border_radius=radius)
    surf.blit(s, (int(rect[0]), int(rect[1])))


def draw_panel(surf: pygame.Surface, rect: tuple,
               bg_color: tuple = (8, 8, 22),
               border_color: tuple = (50, 50, 90),
               alpha: int = 200, radius: int = 8) -> None:
    """Translucent dark panel with border."""
    alpha_rect(surf, bg_color, rect, alpha, radius)
    s = pygame.Surface((rect[2], rect[3]), pygame.SRCALPHA)
    pygame.draw.rect(s, (*border_color, 180), (0, 0, rect[2], rect[3]),
                     2, border_radius=radius)
    surf.blit(s, (rect[0], rect[1]))


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
