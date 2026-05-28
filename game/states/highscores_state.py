"""
highscores_state.py — Top-10 leaderboard display with animated table.
"""
from __future__ import annotations
import math
import pygame

from game.state_manager import BaseState
from game.constants import (
    LOGICAL_W as W, LOGICAL_H as H,
    BG, GRID_DIM, TILE, WHITE, DIM, ACCENT,
)
from utils.helpers import draw_panel
from utils.data_manager import load_scores


class HighScoresState(BaseState):
    def __init__(self, manager) -> None:
        super().__init__(manager)
        self._scores     = []
        self._timer      = 0.0
        self._font_title = None
        self._font_row   = None
        self._font_head  = None
        self._font_small = None

    def on_enter(self, **kwargs) -> None:
        self._font_title = pygame.font.SysFont("monospace", 28, bold=True)
        self._font_head  = pygame.font.SysFont("monospace", 13, bold=True)
        self._font_row   = pygame.font.SysFont("monospace", 14)
        self._font_small = pygame.font.SysFont("monospace", 11)
        self._scores     = load_scores()
        self._timer      = 0.0

    def handle_events(self, events: list) -> None:
        for ev in events:
            if ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE,
                              pygame.K_RETURN):
                    self.manager.pop()
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                # Click the back button area
                lpos = self.manager.mouse_to_logical(ev.pos)
                back_rect = pygame.Rect(W // 2 - 60, H - 70, 120, 32)
                if back_rect.collidepoint(lpos):
                    self.manager.pop()

    def update(self, dt: float) -> None:
        self._timer += dt

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(BG)
        # Subtle grid
        for x in range(0, W, TILE * 2):
            pygame.draw.line(surf, GRID_DIM, (x, 0), (x, H))
        for y in range(0, H, TILE * 2):
            pygame.draw.line(surf, GRID_DIM, (0, y), (W, y))

        # Title
        # _font_title should be set in on_enter(), but guard for static analysis/runtime
        font_title = self._font_title or pygame.font.SysFont("monospace", 28, bold=True)
        title = font_title.render("// HIGH SCORES //", True, (210, 45, 75))
        surf.blit(title, (W // 2 - title.get_width() // 2, 40))

        # Decorative line
        lw = 350
        pygame.draw.line(surf, (210, 45, 75), (W//2 - lw//2, 80),
                         (W//2 + lw//2, 80), 1)

        # Table
        table_x = W // 2 - 280
        table_w = 560
        head_y  = 100

        # Panel background
        panel_h = 40 + len(self._scores) * 36 + 20
        if not self._scores:
            panel_h = 100
        draw_panel(surf, (table_x - 10, head_y - 10, table_w + 20, panel_h),
                   alpha=200, radius=8)

        # Header
        headers = [("RANK", 0), ("NAME", 60), ("SCORE", 240),
                   ("WAVE", 360), ("TIME", 440)]
        if self._font_head:
            for text, offset in headers:
                txt = self._font_head.render(text, True, ACCENT)
                surf.blit(txt, (table_x + offset, head_y))

        pygame.draw.line(surf, (50, 50, 80),
                         (table_x, head_y + 22),
                         (table_x + table_w, head_y + 22), 1)

        if not self._scores:
            if self._font_row:
                no_scores = self._font_row.render(
                    "No scores yet. Play to set a record!", True, DIM)
                surf.blit(no_scores, (W // 2 - no_scores.get_width() // 2,
                                       head_y + 40))
        else:
            for i, entry in enumerate(self._scores[:10]):
                ry = head_y + 32 + i * 36
                # Staggered fade-in
                delay = i * 0.08
                if self._timer < delay:
                    continue
                alpha = min(255, int((self._timer - delay) / 0.3 * 255))

                # Rank color
                rank_cols = [(255, 215, 0), (192, 192, 192), (205, 127, 50)]
                rcol = rank_cols[i] if i < 3 else DIM

                if self._font_row:
                    rank_txt = self._font_row.render(f"#{i+1}", True, rcol)
                    rank_txt.set_alpha(alpha)
                    surf.blit(rank_txt, (table_x, ry))

                    name_txt = self._font_row.render(
                        entry.get("name", "???")[:16], True, WHITE)
                    name_txt.set_alpha(alpha)
                    surf.blit(name_txt, (table_x + 60, ry))

                    score_txt = self._font_row.render(
                        f"{entry.get('score', 0):>7}", True, WHITE)
                    score_txt.set_alpha(alpha)
                    surf.blit(score_txt, (table_x + 240, ry))

                    wave_txt = self._font_row.render(
                        str(entry.get("wave", 0)), True, DIM)
                    wave_txt.set_alpha(alpha)
                    surf.blit(wave_txt, (table_x + 360, ry))

                    t = entry.get("time", 0)
                    time_txt = self._font_row.render(
                        f"{t // 60:02d}:{t % 60:02d}", True, DIM)
                    time_txt.set_alpha(alpha)
                    surf.blit(time_txt, (table_x + 440, ry))

                # Subtle row separator
                if i < len(self._scores) - 1:
                    sep_y = ry + 30
                    s = pygame.Surface((table_w, 1), pygame.SRCALPHA)
                    s.fill((40, 40, 60, 80))
                    surf.blit(s, (table_x, sep_y))

        # Back button
        if self._font_head:
            bx, by, bw, bh = W // 2 - 60, H - 70, 120, 32
            mouse_lpos = self.manager.mouse_to_logical()
            hover = pygame.Rect(bx, by, bw, bh).collidepoint(mouse_lpos)
            bcol = (210, 45, 75) if hover else (50, 50, 80)
            draw_panel(surf, (bx, by, bw, bh), bg_color=(12, 8, 18),
                       border_color=bcol, alpha=220, radius=5)
            btxt = self._font_head.render("BACK", True, WHITE if hover else DIM)
            surf.blit(btxt, (bx + bw // 2 - btxt.get_width() // 2,
                             by + bh // 2 - btxt.get_height() // 2))

        if self._font_small:
            hint = self._font_small.render("ESC / ENTER to go back", True, (50, 50, 70))
            surf.blit(hint, (W // 2 - hint.get_width() // 2, H - 25))
