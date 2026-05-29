"""
pause_state.py — Semi-transparent overlay with resume/restart/menu/quit.

Fixes:
 - Decorative line drawn correctly on SRCALPHA surface (not raw RGBA on fill)
 - Snapshot captured correctly
"""
from __future__ import annotations
import math
import pygame

from game.state_manager import BaseState
from game.constants import LOGICAL_W as W, LOGICAL_H as H, WHITE, DIM
from utils.helpers import draw_panel


_PAUSE_ITEMS = ["RESUME", "RESTART", "MAIN MENU", "QUIT"]


class PauseState(BaseState):
    def __init__(self, manager, game=None) -> None:
        super().__init__(manager)
        self._game       = game
        self._selected   = 0
        self._timer      = 0.0
        self._font_title = None
        self._font_item  = None
        self._font_small = None
        self._item_rects = []
        self._snapshot: pygame.Surface | None = None

    def on_enter(self, **kwargs) -> None:
        self._font_title = pygame.font.SysFont("monospace", 32, bold=True)
        self._font_item  = pygame.font.SysFont("monospace", 20, bold=True)
        self._font_small = pygame.font.SysFont("monospace", 11)
        self._selected   = 0
        self._timer      = 0.0

        # Capture a snapshot of the game world underneath
        if self._game:
            self._snapshot = pygame.Surface((W, H))
            self._game.draw(self._snapshot)

    def on_exit(self) -> None:
        pass

    def handle_events(self, events: list) -> None:
        for ev in events:
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    self._do_resume()
                    return
                if ev.key in (pygame.K_UP, pygame.K_w):
                    self._selected = (self._selected - 1) % len(_PAUSE_ITEMS)
                elif ev.key in (pygame.K_DOWN, pygame.K_s):
                    self._selected = (self._selected + 1) % len(_PAUSE_ITEMS)
                elif ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self._activate(self._selected)
            elif ev.type == pygame.MOUSEMOTION:
                lpos = self.manager.mouse_to_logical(ev.pos)
                for i, rect in enumerate(self._item_rects):
                    if rect.collidepoint(lpos):
                        self._selected = i
                        break
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                lpos = self.manager.mouse_to_logical(ev.pos)
                for i, rect in enumerate(self._item_rects):
                    if rect.collidepoint(lpos):
                        self._activate(i)
                        break

    def _do_resume(self) -> None:
        pygame.mouse.set_visible(False)
        self.manager.pop()

    def _activate(self, index: int) -> None:
        item = _PAUSE_ITEMS[index]
        if item == "RESUME":
            self._do_resume()
        elif item == "RESTART":
            pygame.mouse.set_visible(False)
            from game.states.play_state import PlayState
            self.manager.replace_all(PlayState(self.manager))
        elif item == "MAIN MENU":
            from game.states.menu_state import MenuState
            self.manager.replace_all(MenuState(self.manager))
        elif item == "QUIT":
            self.manager.quit()

    def update(self, dt: float) -> None:
        self._timer += dt

    def draw(self, surf: pygame.Surface) -> None:
        if self._font_title is None or self._font_item is None or self._font_small is None:
            return

        # Draw frozen game snapshot underneath
        if self._snapshot:
            surf.blit(self._snapshot, (0, 0))

        # Dark semi-transparent overlay
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 165))
        surf.blit(overlay, (0, 0))

        # Title
        cy = H // 2
        title = self._font_title.render("// PAUSED //", True, (210, 45, 75))
        surf.blit(title, (W // 2 - title.get_width() // 2, cy - 140))

        # Decorative line — drawn on SRCALPHA surface to support alpha
        line_w = 320
        line_surf = pygame.Surface((line_w, 2), pygame.SRCALPHA)
        line_surf.fill((210, 45, 75, 100))
        surf.blit(line_surf, (W // 2 - line_w // 2, cy - 95))

        # Menu items
        menu_y = cy - 70
        self._item_rects = []
        for i, item in enumerate(_PAUSE_ITEMS):
            is_sel = (i == self._selected)
            ix = W // 2 - 110
            iy = menu_y + i * 48
            iw, ih = 220, 36
            rect = pygame.Rect(ix, iy, iw, ih)
            self._item_rects.append(rect)

            if is_sel:
                gs = pygame.Surface((iw + 16, ih + 8), pygame.SRCALPHA)
                pygame.draw.rect(gs, (210, 45, 75, 28),
                                 (0, 0, iw + 16, ih + 8), border_radius=5)
                surf.blit(gs, (ix - 8, iy - 4))
                draw_panel(surf, (ix, iy, iw, ih),
                           bg_color=(20, 10, 18),
                           border_color=(210, 45, 75),
                           alpha=220, radius=5)
                col = WHITE
                ax = ix - 20 + int(math.sin(self._timer * 5) * 3)
                arr = self._font_item.render(">", True, (210, 45, 75))
                surf.blit(arr, (ax, iy + ih // 2 - arr.get_height() // 2))
            else:
                draw_panel(surf, (ix, iy, iw, ih),
                           bg_color=(8, 8, 22),
                           border_color=(40, 40, 65),
                           alpha=180, radius=5)
                col = DIM

            txt = self._font_item.render(item, True, col)
            surf.blit(txt, (ix + iw // 2 - txt.get_width() // 2,
                            iy + ih // 2 - txt.get_height() // 2))

        # Hint at bottom
        hint = self._font_small.render(
            "ESC Resume   W/S Navigate   ENTER Select",
            True, (50, 50, 70))
        surf.blit(hint, (W // 2 - hint.get_width() // 2, cy + 140))
