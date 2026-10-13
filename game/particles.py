"""
particles.py — Extended particle system.
Types: Particle (radial burst), Spark, Debris, Ring, TextPopup, DashTrail

All motion is frame-rate independent (scaled by dt * 60) and all drawing uses
cached sprites — no Surface is allocated per particle per frame.
"""
from __future__ import annotations
import math, random
import pygame

from utils.helpers import fade_circle, fade_ring


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
        k = dt * 60.0
        self.pos  += self.vel * k
        self.vel  *= 0.90 ** k
        self.life -= dt

    @property
    def alive(self) -> bool:
        return self.life > 0

    def draw(self, surf: pygame.Surface) -> None:
        fade_circle(surf, self.color, self.pos, self.r,
                    255 * max(0.0, self.life / self.max_life))


class Spark(Particle):
    """Linear fast particle with no friction — for block/explosion sparks."""
    __slots__ = ()

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
        self.pos  += self.vel * (dt * 60.0)   # no friction — pure velocity
        self.life -= dt


class Debris(Particle):
    """Particle affected by gravity — tumbles downward."""
    __slots__ = ("gravity",)

    def __init__(self, x: float, y: float, color: tuple) -> None:
        super().__init__(x, y, color, (2, 6))
        self.gravity  = random.uniform(90, 170)   # px/s²
        self.life     = random.uniform(0.45, 0.90)
        self.max_life = self.life
        self.r        = random.randint(2, 4)

    def update(self, dt: float) -> None:
        k = dt * 60.0
        self.vel.y += self.gravity * dt
        self.pos   += self.vel * k
        self.vel   *= 0.97 ** k
        self.life  -= dt


class Ring:
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
        # radius snapped to 4px steps to keep the ring-sprite cache small
        fade_ring(surf, self.color, self.pos, (self.r // 4) * 4 or 4,
                  200 * max(0.0, self.life / self.max_life))


class DashTrail:
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
        fade_circle(surf, self.color, self.pos, self.r,
                    160 * max(0.0, self.life / self.max_life))


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
        self._img     = font.render(text, True, self.color)   # rendered once

    def update(self, dt: float) -> None:
        self.pos  += self.vel * dt
        self.vel  *= 0.94 ** (dt * 60.0)
        self.life -= dt

    @property
    def alive(self) -> bool:
        return self.life > 0

    def draw(self, surf: pygame.Surface) -> None:
        self._img.set_alpha(int(255 * max(0.0, self.life / self.max_life)))
        surf.blit(self._img, (int(self.pos.x) - self._img.get_width() // 2,
                              int(self.pos.y) - self._img.get_height() // 2))
