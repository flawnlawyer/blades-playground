"""
particles.py — Extended particle system.
Types: Particle (radial burst), Spark, Debris, Ring, TextPopup, DashTrail
"""
from __future__ import annotations
import math, random
import pygame


class Particle:
    """Base fire-and-forget radial burst particle."""
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


class Spark(Particle):
    """Linear fast particle with no friction — for block/explosion sparks."""
    def __init__(self, x: float, y: float, color: tuple,
                 direction: float | None = None, speed_range: tuple = (4, 10)) -> None:
        super().__init__(x, y, color, speed_range)
        if direction is not None:
            spd    = random.uniform(*speed_range)
            spread = random.uniform(-0.45, 0.45)
            self.vel = pygame.Vector2(
                math.cos(direction + spread) * spd,
                math.sin(direction + spread) * spd,
            )
        self.life     = random.uniform(0.12, 0.32)
        self.max_life = self.life
        self.r        = random.randint(1, 3)

    def update(self, dt: float) -> None:
        self.pos  += self.vel   # no friction — pure velocity
        self.life -= dt


class Debris(Particle):
    """Particle affected by gravity — tumbles downward."""
    def __init__(self, x: float, y: float, color: tuple) -> None:
        super().__init__(x, y, color, (2, 6))
        self.gravity  = random.uniform(90, 170)   # px/s²
        self.life     = random.uniform(0.45, 0.90)
        self.max_life = self.life
        self.r        = random.randint(2, 4)

    def update(self, dt: float) -> None:
        self.vel.y += self.gravity * dt
        self.pos   += self.vel * dt * 60
        self.vel   *= 0.97
        self.life  -= dt


class Ring(Particle):
    """Expanding circle outline — for chaos activation, explosions."""
    def __init__(self, x: float, y: float, color: tuple,
                 start_r: int = 10, end_r: int = 90, dur: float = 0.45) -> None:
        self.pos      = pygame.Vector2(x, y)
        self.color    = color[:3]
        self.life     = dur
        self.max_life = dur
        self.start_r  = start_r
        self.end_r    = end_r
        self.r        = start_r
        self.vel      = pygame.Vector2(0, 0)

    def update(self, dt: float) -> None:
        self.life -= dt
        t      = 1.0 - (self.life / self.max_life)
        self.r = int(self.start_r + (self.end_r - self.start_r) * t)

    @property
    def alive(self) -> bool:
        return self.life > 0

    def draw(self, surf: pygame.Surface) -> None:
        a = int(200 * max(0.0, self.life / self.max_life))
        r = self.r
        if r <= 0:
            return
        s = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color, a), (r + 2, r + 2), r, 2)
        surf.blit(s, (int(self.pos.x) - r - 2, int(self.pos.y) - r - 2))


class DashTrail(Particle):
    """Ghost afterimage at a given position for the player dash."""
    def __init__(self, x: float, y: float, color: tuple,
                 radius: int = 14) -> None:
        self.pos      = pygame.Vector2(x, y)
        self.color    = color[:3]
        self.life     = 0.22
        self.max_life = self.life
        self.r        = radius
        self.vel      = pygame.Vector2(0, 0)

    def update(self, dt: float) -> None:
        self.life -= dt

    @property
    def alive(self) -> bool:
        return self.life > 0

    def draw(self, surf: pygame.Surface) -> None:
        a = int(160 * max(0.0, self.life / self.max_life))
        r = self.r
        s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color, a), (r, r), r)
        surf.blit(s, (int(self.pos.x) - r, int(self.pos.y) - r))


class TextPopup:
    """Floating text that rises and fades — damage / score numbers."""
    def __init__(self, x: float, y: float, text: str, color: tuple,
                 font: pygame.font.Font, dur: float = 1.1) -> None:
        self.pos      = pygame.Vector2(x, y)
        self.text     = text
        self.color    = color[:3]
        self.font     = font
        self.life     = dur
        self.max_life = dur
        self.vel      = pygame.Vector2(random.uniform(-18, 18), -60)

    def update(self, dt: float) -> None:
        self.pos  += self.vel * dt
        self.vel  *= 0.94
        self.life -= dt

    @property
    def alive(self) -> bool:
        return self.life > 0

    def draw(self, surf: pygame.Surface) -> None:
        a   = int(255 * max(0.0, self.life / self.max_life))
        txt = self.font.render(self.text, True, self.color)
        txt.set_alpha(a)
        surf.blit(txt, (int(self.pos.x) - txt.get_width() // 2,
                        int(self.pos.y) - txt.get_height() // 2))
