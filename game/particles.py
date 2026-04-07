from __future__ import annotations
import math, random
import pygame


class Particle:
    __slots__ = ("pos", "vel", "color", "life", "max_life", "r")

    def __init__(self, x: float, y: float, color: tuple,
                 speed_range: tuple = (1, 5)) -> None:
        self.pos      = pygame.Vector2(x, y)
        angle         = random.uniform(0, math.tau)
        spd           = random.uniform(*speed_range)
        self.vel      = pygame.Vector2(math.cos(angle) * spd, math.sin(angle) * spd)
        self.color    = color[:3]
        self.life     = random.uniform(0.25, 0.70)
        self.max_life = self.life
        self.r        = random.randint(2, 5)

    def update(self, dt: float) -> None:
        self.pos  += self.vel
        self.vel  *= 0.90
        self.life -= dt

    @property
    def alive(self) -> bool:
        return self.life > 0

    def draw(self, surf: pygame.Surface) -> None:
        a = int(255 * max(0.0, self.life / self.max_life))
        r = self.r
        s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color, a), (r, r), r)
        surf.blit(s, (int(self.pos.x) - r, int(self.pos.y) - r))
