from __future__ import annotations
import math, random
import pygame

from game.constants import (
    W, H,
    MEH_COL, MEH_HACKED, FRAG_COL, ENEMY_COL, WHITE, DIM,
    MEH_DEFAULT_HP,
    ENEMY_SPEED_MIN, ENEMY_SPEED_MAX, ENEMY_CHASE_DIST, ENEMY_RADIUS,
    ENEMY_STUN_DURATION,
)
from utils.helpers import glow_circle


# ── Meh Block ─────────────────────────────────────────────────────────────────

class MehBlock:
    SIZE = 38

    def __init__(self, x: float, y: float) -> None:
        self.rect       = pygame.Rect(int(x), int(y), self.SIZE, self.SIZE)
        self.hp         = MEH_DEFAULT_HP
        self.hacked     = False
        self.hack_timer = 0.0
        self._glitch    = [0, 0]
        self._glitch_cd = random.uniform(0.5, 2.0)

    def update(self, dt: float) -> None:
        self._glitch_cd -= dt
        if self._glitch_cd <= 0:
            self._glitch_cd = random.uniform(0.8, 3.0)
            self._glitch    = [random.randint(-2, 2), random.randint(-2, 2)]

        if self.hacked:
            self.hack_timer -= dt
            if self.hack_timer <= 0:
                self.hacked = False

    def hack(self, duration: float = 3.5) -> None:
        self.hacked     = True
        self.hack_timer = duration

    @property
    def center(self) -> pygame.Vector2:
        return pygame.Vector2(self.rect.centerx, self.rect.centery)

    def draw(self, surf: pygame.Surface, font: pygame.font.Font) -> None:
        col = MEH_HACKED if self.hacked else MEH_COL
        r   = self.rect.move(self._glitch)

        pygame.draw.rect(surf, col, r, border_radius=5)

        # Random scanline stripe
        stripe = pygame.Surface((r.width, 3), pygame.SRCALPHA)
        stripe.fill((*WHITE, 16))
        surf.blit(stripe, (r.x, r.y + random.randint(0, r.height - 3)))

        pygame.draw.rect(surf, (*WHITE, 28), r, 1, border_radius=5)

        label = font.render(">>" if self.hacked else "meh", True, (20, 20, 35))
        surf.blit(label, (r.x + 7, r.y + 13))


# ── Fragment ──────────────────────────────────────────────────────────────────

class Fragment:
    RADIUS = 9

    def __init__(self, x: float, y: float, text: str) -> None:
        self.pos     = pygame.Vector2(x, y)
        self.text    = text
        self.radius  = self.RADIUS
        self._float  = random.uniform(0, math.tau)
        self._pulse  = 0.0
        self.rect    = pygame.Rect(
            int(x) - self.radius, int(y) - self.radius,
            self.radius * 2,      self.radius * 2,
        )

    def update(self, dt: float) -> None:
        self._float += dt * 2.2
        self._pulse += dt * 3.5

    def draw(self, surf: pygame.Surface) -> None:
        oy = math.sin(self._float) * 5
        cx = int(self.pos.x)
        cy = int(self.pos.y + oy)
        pr = self.radius + abs(math.sin(self._pulse)) * 4

        glow_circle(surf, FRAG_COL, (cx, cy), int(pr) + 8, 35)
        pygame.draw.circle(surf, FRAG_COL, (cx, cy), self.radius)
        pygame.draw.circle(surf, WHITE,    (cx, cy), self.radius, 1)
        self.rect.center = (cx, cy)


# ── Enemy ─────────────────────────────────────────────────────────────────────

class Enemy:
    def __init__(self, x: float, y: float) -> None:
        self.pos        = pygame.Vector2(x, y)
        self.speed      = random.uniform(ENEMY_SPEED_MIN, ENEMY_SPEED_MAX)
        self.radius     = ENEMY_RADIUS
        self.rect       = pygame.Rect(
            int(x) - self.radius, int(y) - self.radius,
            self.radius * 2,      self.radius * 2,
        )
        self.stunned    = False
        self.stun_timer = 0.0
        self._wander    = pygame.Vector2(
            random.uniform(-1, 1), random.uniform(-1, 1)
        ).normalize()
        self._wander_cd = 0.0
        self._glitch    = [0, 0]
        self._phase     = random.uniform(0, math.tau)

    def update(self, dt: float, player_pos: pygame.Vector2) -> None:
        self._phase += dt * 4

        # Random glitch offset
        if random.random() < 0.04:
            self._glitch = [random.randint(-3, 3), random.randint(-3, 3)]
        else:
            self._glitch = [0, 0]

        if self.stunned:
            self.stun_timer -= dt
            if self.stun_timer <= 0:
                self.stunned = False
            return

        dist = (player_pos - self.pos).length()
        if dist < ENEMY_CHASE_DIST:
            direction  = (player_pos - self.pos).normalize()
            self.pos  += direction * self.speed * 1.6
        else:
            self._wander_cd -= dt
            if self._wander_cd <= 0:
                self._wander_cd = random.uniform(1.0, 2.5)
                self._wander = pygame.Vector2(
                    random.uniform(-1, 1), random.uniform(-1, 1)
                ).normalize()
            self.pos += self._wander * self.speed

        self.pos.x = max(self.radius, min(W - self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(H - self.radius, self.pos.y))
        self.rect.center = (int(self.pos.x), int(self.pos.y))

    def stun(self) -> None:
        self.stunned    = True
        self.stun_timer = ENEMY_STUN_DURATION

    def draw(self, surf: pygame.Surface) -> None:
        col = (80, 80, 100) if self.stunned else ENEMY_COL
        cx  = int(self.pos.x) + self._glitch[0]
        cy  = int(self.pos.y) + self._glitch[1]

        if not self.stunned:
            gr = self.radius + int(abs(math.sin(self._phase)) * 5)
            glow_circle(surf, ENEMY_COL, (cx, cy), gr, 30)

        pts = [(cx, cy - self.radius), (cx + self.radius, cy),
               (cx, cy + self.radius), (cx - self.radius, cy)]
        pygame.draw.polygon(surf, col, pts)
        pygame.draw.polygon(surf, WHITE, pts, 1)
