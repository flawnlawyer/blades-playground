from __future__ import annotations
import random
import pygame

from game.constants import (
    W, H, TILE,
    BG, GRID_DIM, GRID_BRIGHT, WHITE, CHAOS_COL,
)
from utils.helpers import alpha_rect


class Renderer:
    """Handles all background and post-process layer rendering."""

    def __init__(self) -> None:
        self._glitch_lines: list[tuple[int, int, tuple]] = []
        self._glitch_cd    = random.uniform(1.0, 3.0)

    def update(self, dt: float, chaos_mode: bool) -> None:
        """Tick glitch line generation."""
        self._glitch_cd -= dt
        if self._glitch_cd <= 0:
            self._glitch_cd = random.uniform(1.0 if not chaos_mode else 0.4, 4.0)
            count = random.randint(3, 9) if chaos_mode else random.randint(1, 5)
            self._glitch_lines = [
                (
                    random.randint(0, H),
                    random.randint(40, W),
                    (
                        random.randint(0, 60),
                        random.randint(0, 255),
                        random.randint(150, 255),
                    ),
                )
                for _ in range(count)
            ]
        elif random.random() < (0.15 if chaos_mode else 0.08):
            self._glitch_lines = []

    def draw_background(self, surf: pygame.Surface, chaos_mode: bool) -> None:
        surf.fill(BG)

        # Grid
        for x in range(0, W, TILE):
            col = GRID_BRIGHT if x % (TILE * 4) == 0 else GRID_DIM
            pygame.draw.line(surf, col, (x, 0), (x, H))
        for y in range(0, H, TILE):
            col = GRID_BRIGHT if y % (TILE * 4) == 0 else GRID_DIM
            pygame.draw.line(surf, col, (0, y), (W, y))

        # Chaos world pulse
        if chaos_mode:
            for _ in range(5):
                cx = random.randint(0, W)
                cy = random.randint(0, H)
                alpha_rect(surf, (255, 160, 0), (cx - 160, cy - 160, 320, 320), 5)

    def draw_glitch_lines(self, surf: pygame.Surface) -> None:
        for (y, width, col) in self._glitch_lines:
            pygame.draw.rect(surf, col, (0, y, width, 2))

    def draw_chromatic(self, surf: pygame.Surface) -> None:
        """Chromatic aberration overlay — only during chaos mode."""
        r_s = pygame.Surface((W, H), pygame.SRCALPHA)
        r_s.fill((255, 0, 0, 11))
        surf.blit(r_s, (4, 0))
        b_s = pygame.Surface((W, H), pygame.SRCALPHA)
        b_s.fill((0, 0, 255, 11))
        surf.blit(b_s, (-4, 0))
