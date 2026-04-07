import pygame


def glow_circle(surf: pygame.Surface, color: tuple, pos: tuple,
                radius: int, alpha: int = 50) -> None:
    """Draw a soft radial glow centred at pos."""
    s = pygame.Surface((radius * 4, radius * 4), pygame.SRCALPHA)
    pygame.draw.circle(s, (*color[:3], alpha), (radius * 2, radius * 2), radius * 2)
    surf.blit(s, (int(pos[0]) - radius * 2, int(pos[1]) - radius * 2))


def alpha_rect(surf: pygame.Surface, color: tuple, rect: tuple,
               alpha: int, radius: int = 0) -> None:
    """Draw a semi-transparent filled rectangle."""
    s = pygame.Surface((rect[2], rect[3]), pygame.SRCALPHA)
    pygame.draw.rect(s, (*color[:3], alpha), (0, 0, rect[2], rect[3]),
                     border_radius=radius)
    surf.blit(s, (rect[0], rect[1]))


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))
