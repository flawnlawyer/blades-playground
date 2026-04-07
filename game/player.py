from __future__ import annotations
import math
import pygame

from game.constants import (
    W, H,
    PLAYER_COL, CHAOS_COL, WHITE,
    PLAYER_SPEED, PLAYER_RADIUS, PLAYER_TRAIL_LEN,
    PLAYER_HACK_CD, PLAYER_INV_DURATION,
    PLAYER_MAX_ENERGY, CHAOS_DURATION, CHAOS_SPEED_MULT,
)
from utils.helpers import glow_circle


class Player:
    def __init__(self, x: float, y: float) -> None:
        self.pos         = pygame.Vector2(x, y)
        self.radius      = PLAYER_RADIUS
        self.energy      = 0.0
        self.max_energy  = PLAYER_MAX_ENERGY
        self.chaos_mode  = False
        self.chaos_timer = 0.0
        self.hack_cd     = 0.0
        self.inv_timer   = 0.0
        self.trail: list[pygame.Vector2] = []
        self._chaos_just_ended = False

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, keys: pygame.key.ScancodeWrapper, dt: float) -> None:
        vel = pygame.Vector2(0, 0)
        spd = PLAYER_SPEED * (CHAOS_SPEED_MULT if self.chaos_mode else 1.0)

        if keys[pygame.K_w] or keys[pygame.K_UP]:    vel.y -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:  vel.y += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  vel.x -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: vel.x += 1

        if vel.length_squared() > 0:
            vel = vel.normalize() * spd

        self.pos += vel
        self.pos.x = max(self.radius, min(W - self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(H - self.radius, self.pos.y))

        # Trail
        self.trail.append(pygame.Vector2(self.pos))
        if len(self.trail) > PLAYER_TRAIL_LEN:
            self.trail.pop(0)

        # Timers
        if self.hack_cd   > 0: self.hack_cd   -= dt
        if self.inv_timer > 0: self.inv_timer -= dt

        # Chaos countdown
        self._chaos_just_ended = False
        if self.chaos_mode:
            self.chaos_timer -= dt
            if self.chaos_timer <= 0:
                self.chaos_mode        = False
                self.energy            = 0.0
                self._chaos_just_ended = True

    # ── Energy / chaos ────────────────────────────────────────────────────────

    def add_energy(self, amt: float) -> bool:
        """Returns True if chaos mode was just triggered."""
        self.energy = min(self.max_energy, self.energy + amt)
        if self.energy >= self.max_energy and not self.chaos_mode:
            self.chaos_mode  = True
            self.chaos_timer = CHAOS_DURATION
            return True
        return False

    # ── Hack ─────────────────────────────────────────────────────────────────

    @property
    def can_hack(self) -> bool:
        return self.hack_cd <= 0

    def trigger_hack(self) -> None:
        self.hack_cd = PLAYER_HACK_CD

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self, surf: pygame.Surface) -> None:
        col = CHAOS_COL if self.chaos_mode else PLAYER_COL

        # Trail
        n = len(self.trail)
        for i, tp in enumerate(self.trail):
            t = i / max(n, 1)
            r = max(1, int(self.radius * 0.55 * t))
            a = int(170 * t)
            s = pygame.Surface((r * 2 + 1, r * 2 + 1), pygame.SRCALPHA)
            pygame.draw.circle(s, (*col, a), (r, r), r)
            surf.blit(s, (int(tp.x) - r, int(tp.y) - r))

        cx, cy = int(self.pos.x), int(self.pos.y)

        # Glow
        glow_circle(surf, col, (cx, cy), self.radius + 8, 45)

        # Body
        pygame.draw.circle(surf, col, (cx, cy), self.radius)
        pygame.draw.circle(surf, (*WHITE, 80), (cx - 4, cy - 4), 5)
        pygame.draw.circle(surf, WHITE, (cx, cy), self.radius, 1)

        # Invincibility flash ring
        if self.inv_timer > 0 and int(self.inv_timer * 10) % 2 == 0:
            pygame.draw.circle(surf, WHITE, (cx, cy), self.radius + 3, 2)
