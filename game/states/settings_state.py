"""
settings_state.py — Volume slider, fullscreen toggle, persistent settings.
"""
from __future__ import annotations
import pygame

from game.state_manager import BaseState
from game.constants import (
    LOGICAL_W as W, LOGICAL_H as H,
    BG, GRID_DIM, TILE, WHITE, DIM, ACCENT,
)
from utils.helpers import draw_panel
from utils.data_manager import load_settings, save_settings


class SettingsState(BaseState):
    def __init__(self, manager) -> None:
        super().__init__(manager)
        self._settings   = {}
        self._selected   = 0
        self._timer      = 0.0
        self._items      = ["VOLUME", "FULLSCREEN", "BACK"]
        self._font_title = None
        self._font_item  = None
        self._font_small = None
        self._dragging_vol = False

    def on_enter(self, **kwargs) -> None:
        self._font_title = pygame.font.SysFont("monospace", 28, bold=True)
        self._font_item  = pygame.font.SysFont("monospace", 16, bold=True)
        self._font_small = pygame.font.SysFont("monospace", 11)
        self._settings   = load_settings()
        self._selected   = 0
        self._timer      = 0.0

    def on_exit(self) -> None:
        save_settings(self._settings)

    def handle_events(self, events: list) -> None:
        for ev in events:
            if ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                    self.manager.pop()
                    return
                if ev.key in (pygame.K_UP, pygame.K_w):
                    self._selected = (self._selected - 1) % len(self._items)
                elif ev.key in (pygame.K_DOWN, pygame.K_s):
                    self._selected = (self._selected + 1) % len(self._items)
                elif ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if self._items[self._selected] == "FULLSCREEN":
                        self.manager.toggle_fullscreen()
                    elif self._items[self._selected] == "BACK":
                        self.manager.pop()
                        return
                elif ev.key in (pygame.K_LEFT, pygame.K_a):
                    if self._items[self._selected] == "VOLUME":
                        self._adjust_volume(-0.05)
                elif ev.key in (pygame.K_RIGHT, pygame.K_d):
                    if self._items[self._selected] == "VOLUME":
                        self._adjust_volume(0.05)

            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                lpos = self.manager.mouse_to_logical(ev.pos)
                # Check volume slider
                bar_rect = self._vol_bar_rect()
                if bar_rect and bar_rect.collidepoint(lpos):
                    self._dragging_vol = True
                    self._set_vol_from_mouse(lpos[0], bar_rect)
                # Check fullscreen button
                fs_rect = pygame.Rect(W//2 - 110, 310, 220, 36)
                if fs_rect.collidepoint(lpos):
                    self.manager.toggle_fullscreen()
                # Check back button
                back_rect = pygame.Rect(W//2 - 60, H - 70, 120, 32)
                if back_rect.collidepoint(lpos):
                    self.manager.pop()

            elif ev.type == pygame.MOUSEBUTTONUP:
                self._dragging_vol = False

            elif ev.type == pygame.MOUSEMOTION:
                if self._dragging_vol:
                    lpos = self.manager.mouse_to_logical(ev.pos)
                    bar_rect = self._vol_bar_rect()
                    if bar_rect:
                        self._set_vol_from_mouse(lpos[0], bar_rect)

    def _vol_bar_rect(self) -> pygame.Rect:
        return pygame.Rect(W // 2 - 100, 248, 200, 16)

    def _set_vol_from_mouse(self, mx: int, bar: pygame.Rect) -> None:
        t = max(0.0, min(1.0, (mx - bar.x) / bar.width))
        self._settings["volume"] = round(t, 2)
        if self.manager.audio:
            self.manager.audio.set_volume(t)

    def _adjust_volume(self, delta: float) -> None:
        v = max(0.0, min(1.0, self._settings.get("volume", 0.55) + delta))
        self._settings["volume"] = round(v, 2)
        if self.manager.audio:
            self.manager.audio.set_volume(v)

    def update(self, dt: float) -> None:
        self._timer += dt

    def draw(self, surf: pygame.Surface) -> None:
        if not self._font_title or not self._font_item or not self._font_small:
            return
        surf.fill(BG)
        for x in range(0, W, TILE * 2):
            pygame.draw.line(surf, GRID_DIM, (x, 0), (x, H))
        for y in range(0, H, TILE * 2):
            pygame.draw.line(surf, GRID_DIM, (0, y), (W, y))

        # Title
        title = self._font_title.render("// SETTINGS //", True, (210, 45, 75))
        surf.blit(title, (W // 2 - title.get_width() // 2, 60))
        lw = 300
        pygame.draw.line(surf, (210, 45, 75), (W//2 - lw//2, 100),
                         (W//2 + lw//2, 100), 1)

        # Main panel
        draw_panel(surf, (W//2 - 180, 120, 360, 260), alpha=200, radius=10)

        # Volume
        vol = self._settings.get("volume", 0.55)
        is_sel = (self._selected == 0)
        vol_col = WHITE if is_sel else DIM
        vol_lbl = self._font_item.render(
            f"VOLUME: {int(vol * 100)}%", True, vol_col)
        surf.blit(vol_lbl, (W // 2 - vol_lbl.get_width() // 2, 145))

        # Volume bar
        bar = self._vol_bar_rect()
        pygame.draw.rect(surf, (20, 20, 40), bar, border_radius=6)
        fill_w = int(bar.width * vol)
        if fill_w > 0:
            fill_col = (210, 45, 75) if is_sel else (100, 100, 140)
            pygame.draw.rect(surf, fill_col,
                             (bar.x, bar.y, fill_w, bar.height),
                             border_radius=6)
            # Shimmer
            shim = pygame.Surface((fill_w, bar.height // 2), pygame.SRCALPHA)
            shim.fill((255, 255, 255, 25))
            surf.blit(shim, (bar.x, bar.y))
        pygame.draw.rect(surf, (60, 60, 100), bar, 1, border_radius=6)
        # Knob
        knob_x = bar.x + fill_w
        knob_col = WHITE if is_sel else (120, 120, 160)
        pygame.draw.circle(surf, knob_col,
                           (knob_x, bar.y + bar.height // 2), 8)
        pygame.draw.circle(surf, (40, 40, 60),
                           (knob_x, bar.y + bar.height // 2), 8, 1)

        if is_sel:
            hint = self._font_small.render("< A/D or LEFT/RIGHT >", True, DIM)
            surf.blit(hint, (W//2 - hint.get_width()//2, 270))

        # Fullscreen
        is_sel_fs = (self._selected == 1)
        fs_label = "ON" if self.manager._fullscreen else "OFF"
        fs_col = WHITE if is_sel_fs else DIM
        fs_border = (210, 45, 75) if is_sel_fs else (50, 50, 80)
        fs_rect = pygame.Rect(W//2 - 110, 310, 220, 36)
        draw_panel(surf, (fs_rect.x, fs_rect.y, fs_rect.w, fs_rect.h),
                   bg_color=(12, 8, 18), border_color=fs_border,
                   alpha=220, radius=5)
        fs_txt = self._font_item.render(
            f"FULLSCREEN: {fs_label}", True, fs_col)
        surf.blit(fs_txt, (W//2 - fs_txt.get_width()//2,
                           fs_rect.y + fs_rect.h//2 - fs_txt.get_height()//2))

        # Back button
        is_sel_back = (self._selected == 2)
        bx, by, bw, bh = W // 2 - 60, H - 70, 120, 32
        bcol = (210, 45, 75) if is_sel_back else (50, 50, 80)
        draw_panel(surf, (bx, by, bw, bh), bg_color=(12, 8, 18),
                   border_color=bcol, alpha=220, radius=5)
        btxt = self._font_item.render("BACK", True, WHITE if is_sel_back else DIM)
        surf.blit(btxt, (bx + bw // 2 - btxt.get_width() // 2,
                         by + bh // 2 - btxt.get_height() // 2))

        # Bottom hint
        hint = self._font_small.render(
            "ESC Back   W/S Navigate   ENTER Toggle   F11 Fullscreen",
            True, (50, 50, 70))
        surf.blit(hint, (W // 2 - hint.get_width() // 2, H - 25))
