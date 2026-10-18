"""
renderer.py — Background, post-process, and visual FX layer.

Performance notes
  * The background (BG colour + grid) is baked once into an opaque surface.
  * Vignette and CRT scanlines are baked into ONE overlay (one blit, not two).
  * Chromatic wash, chaos tint and hit-flash are cached plain surfaces drawn
    with set_alpha (constant-alpha blits are ~2x cheaper than per-pixel alpha).
  * Parallax debris uses cached circle sprites.
"""
from __future__ import annotations
import random
import numpy as np
import pygame

from game.constants import (
    W, H, TILE,
    BG, GRID_DIM, GRID_BRIGHT, CHAOS_COL,
    VIGNETTE_DARKEN, SCANLINE_DARKEN,
)
from utils.helpers import fade_circle


def _plain(color: tuple) -> pygame.Surface:
    """Opaque full-screen surface (display format when available)."""
    s = pygame.Surface((W, H))
    if pygame.display.get_surface() is not None:
        s = s.convert()
    s.fill(color)
    return s


class Renderer:
    def __init__(self) -> None:
        self._glitch_lines: list[tuple] = []
        self._glitch_cd   = random.uniform(1.0, 3.0)
        self._bg          = self._make_background()
        self._overlay     = self._make_overlay()
        self._debris      = [_DebrisParticle() for _ in range(22)]
        self._flash_timer = 0.0
        self._flash_color = (255, 0, 0)
        # Reusable full-screen tint surfaces (alpha set per draw)
        self._flash_surf  = _plain((255, 0, 0))
        self._chroma_surf = _plain((150, 0, 255))
        self._chaos_surf  = _plain(CHAOS_COL)

    # ── Pre-baked surfaces ────────────────────────────────────────────────────

    @staticmethod
    def _make_background() -> pygame.Surface:
        s = _plain(BG)
        for x in range(0, W, TILE):
            col = GRID_BRIGHT if x % (TILE * 4) == 0 else GRID_DIM
            pygame.draw.line(s, col, (x, 0), (x, H))
        for y in range(0, H, TILE):
            col = GRID_BRIGHT if y % (TILE * 4) == 0 else GRID_DIM
            pygame.draw.line(s, col, (0, y), (W, y))
        return s

    @staticmethod
    def _make_overlay() -> pygame.Surface:
        """Vignette + CRT scanlines baked into ONE opaque multiply-map.

        Smooth radial gradient computed with NumPy: clear in the middle, darker
        toward the corners (quadratic falloff, so the centre ~35% is untouched).
        Blitting it with BLEND_RGB_MULT is ~3.5x cheaper than per-pixel alpha.
        (The original vignette was inverted — it dimmed the centre — and stepped
        in 4px rings, which produced visible banding.)
        """
        y, x = np.ogrid[0:H, 0:W]
        d    = np.hypot((x - W / 2) / (W / 2), (y - H / 2) / (H / 2)) / np.sqrt(2.0)
        dark = np.clip((d - 0.35) / 0.65, 0.0, 1.0) ** 2 * VIGNETTE_DARKEN      # (H, W)
        mult = 255.0 * (1.0 - dark)
        mult[0::3, :] *= (255 - SCANLINE_DARKEN) / 255.0                         # scanlines
        gray = np.clip(mult, 0, 255).astype(np.uint8).T                          # -> (W, H)
        mul  = pygame.Surface((W, H))
        pygame.surfarray.blit_array(mul, np.dstack([gray, gray, gray]))
        return mul.convert() if pygame.display.get_surface() is not None else mul

    # ── Per-frame update ──────────────────────────────────────────────────────

    def update(self, dt: float, chaos_mode: bool) -> None:
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

        for d in self._debris:
            d.update(dt)

        if self._flash_timer > 0:
            self._flash_timer -= dt

    # ── Draw calls ────────────────────────────────────────────────────────────

    def draw_background(self, surf: pygame.Surface, chaos_mode: bool) -> None:
        surf.blit(self._bg, (0, 0))
        for d in self._debris:
            d.draw(surf)
        # Chaos: flickering amber world pulse (one blit instead of six)
        if chaos_mode:
            self._chaos_surf.set_alpha(random.randint(5, 13))
            surf.blit(self._chaos_surf, (0, 0))

    def draw_glitch_lines(self, surf: pygame.Surface) -> None:
        for (y, width, col) in self._glitch_lines:
            pygame.draw.rect(surf, col, (0, y, width, 2))

    def draw_chromatic(self, surf: pygame.Surface) -> None:
        self._chroma_surf.set_alpha(20)
        surf.blit(self._chroma_surf, (0, 0))

    def draw_overlay(self, surf: pygame.Surface) -> None:
        """Vignette + scanlines in a single multiply-blend blit."""
        surf.blit(self._overlay, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

    # Kept for API compatibility
    def draw_vignette(self, surf: pygame.Surface) -> None:
        self.draw_overlay(surf)

    def draw_scanlines(self, surf: pygame.Surface) -> None:
        pass

    def draw_flash(self, surf: pygame.Surface) -> None:
        if self._flash_timer <= 0:
            return
        a = int(180 * min(1.0, self._flash_timer / 0.12))
        self._flash_surf.fill(self._flash_color)
        self._flash_surf.set_alpha(a)
        surf.blit(self._flash_surf, (0, 0))

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
        fade_circle(surf, self.col, (self.x, self.y), self.r, self.alpha)
