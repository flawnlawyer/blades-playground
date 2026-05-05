"""
renderer.py — Background, post-process, and visual FX layer.
New: vignette, CRT scanlines, parallax debris, shockwave flash.
"""
from __future__ import annotations
import random, math
import pygame

from game.constants import (
    W, H, TILE,
    BG, GRID_DIM, GRID_BRIGHT, WHITE, CHAOS_COL,
)
from utils.helpers import alpha_rect


class Renderer:
    def __init__(self) -> None:
        self._glitch_lines: list[tuple] = []
        self._glitch_cd   = random.uniform(1.0, 3.0)
        self._vignette    = self._make_vignette()
        self._scanlines   = self._make_scanlines()
        self._debris      = [_DebrisParticle() for _ in range(22)]
        self._flash_timer = 0.0
        self._flash_color = (255, 0, 0)

    # ── Pre-baked surfaces ────────────────────────────────────────────────────

    @staticmethod
    def _make_vignette() -> pygame.Surface:
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        cx, cy = W // 2, H // 2
        for r in range(max(W, H), 0, -4):
            t = r / max(W, H)
            a = int(max(0, (1.0 - t * 1.6)) * 110)
            if a <= 0:
                continue
            pygame.draw.ellipse(s, (0, 0, 0, a),
                                (cx - r, cy - int(r * 0.6),
                                 r * 2, int(r * 1.2)), 3)
        return s

    @staticmethod
    def _make_scanlines() -> pygame.Surface:
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        for y in range(0, H, 3):
            pygame.draw.line(s, (0, 0, 0, 14), (0, y), (W, y))
        return s

    # ── Per-frame update ──────────────────────────────────────────────────────

    def update(self, dt: float, chaos_mode: bool) -> None:
        # Glitch lines
        self._glitch_cd -= dt
        if self._glitch_cd <= 0:
            self._glitch_cd = random.uniform(
                0.35 if chaos_mode else 1.0, 4.0)
            count = random.randint(3, 10) if chaos_mode else random.randint(1, 5)
            self._glitch_lines = [
                (random.randint(0, H),
                 random.randint(40, W),
                 (random.randint(0, 60),
                  random.randint(0, 255),
                  random.randint(150, 255)))
                for _ in range(count)
            ]
        elif random.random() < (0.18 if chaos_mode else 0.08):
            self._glitch_lines = []

        # Parallax debris
        for d in self._debris:
            d.update(dt)

        # Flash decay
        if self._flash_timer > 0:
            self._flash_timer -= dt

    # ── Draw calls ────────────────────────────────────────────────────────────

    def draw_background(self, surf: pygame.Surface, chaos_mode: bool) -> None:
        surf.fill(BG)

        # Parallax debris (background layer)
        for d in self._debris:
            d.draw(surf)

        # Grid
        for x in range(0, W, TILE):
            col = GRID_BRIGHT if x % (TILE * 4) == 0 else GRID_DIM
            pygame.draw.line(surf, col, (x, 0), (x, H))
        for y in range(0, H, TILE):
            col = GRID_BRIGHT if y % (TILE * 4) == 0 else GRID_DIM
            pygame.draw.line(surf, col, (0, y), (W, y))

        # Chaos world pulse blobs
        if chaos_mode:
            for _ in range(6):
                cx = random.randint(0, W)
                cy = random.randint(0, H)
                alpha_rect(surf, (255, 160, 0), (cx - 180, cy - 180, 360, 360), 4)

    def draw_glitch_lines(self, surf: pygame.Surface) -> None:
        for (y, width, col) in self._glitch_lines:
            pygame.draw.rect(surf, col, (0, y, width, 2))

    def draw_chromatic(self, surf: pygame.Surface) -> None:
        r_s = pygame.Surface((W, H), pygame.SRCALPHA)
        r_s.fill((255, 0, 0, 12))
        surf.blit(r_s, (5, 0))
        b_s = pygame.Surface((W, H), pygame.SRCALPHA)
        b_s.fill((0, 0, 255, 12))
        surf.blit(b_s, (-5, 0))

    def draw_vignette(self, surf: pygame.Surface) -> None:
        surf.blit(self._vignette, (0, 0))

    def draw_scanlines(self, surf: pygame.Surface) -> None:
        surf.blit(self._scanlines, (0, 0))

    def draw_flash(self, surf: pygame.Surface) -> None:
        if self._flash_timer <= 0:
            return
        a = int(180 * min(1.0, self._flash_timer / 0.12))
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((*self._flash_color, a))
        surf.blit(ov, (0, 0))

    def trigger_flash(self, color: tuple = (255, 0, 0), dur: float = 0.12) -> None:
        self._flash_timer = dur
        self._flash_color = color[:3]


# ── Background debris dots (parallax) ────────────────────────────────────────

class _DebrisParticle:
    def __init__(self) -> None:
        self._reset(True)

    def _reset(self, randomize: bool = False) -> None:
        self.x     = random.uniform(0, W)
        self.y     = random.uniform(0, H) if randomize else -4.0
        self.speed = random.uniform(8, 28)
        self.r     = random.choice([1, 1, 1, 2])
        self.alpha = random.randint(25, 70)
        self.col   = random.choice([(60, 60, 100), (40, 40, 80), (80, 80, 130)])

    def update(self, dt: float) -> None:
        self.y += self.speed * dt
        if self.y > H + 4:
            self._reset()

    def draw(self, surf: pygame.Surface) -> None:
        s = pygame.Surface((self.r * 2, self.r * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.col, self.alpha), (self.r, self.r), self.r)
        surf.blit(s, (int(self.x) - self.r, int(self.y) - self.r))
