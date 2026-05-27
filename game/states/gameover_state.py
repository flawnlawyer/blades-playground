"""
gameover_state.py — Enhanced game-over screen with animated score,
stats summary, high-score entry, and replay/menu options.
"""
from __future__ import annotations
import math
import pygame

from game.state_manager import BaseState
from game.constants import (
    LOGICAL_W as W, LOGICAL_H as H,
    WHITE, DIM, ENEMY_COL, ACCENT,
)
from utils.helpers import draw_panel
from utils.data_manager import save_score, qualifies_for_leaderboard


_GO_ITEMS = ["PLAY AGAIN", "MAIN MENU"]


class GameOverState(BaseState):
    def __init__(self, manager, score=0, wave=1, time=0.0, game=None) -> None:
        super().__init__(manager)
        self._final_score  = score
        self._final_wave   = wave
        self._final_time   = time
        self._game         = game
        self._selected     = 0
        self._timer        = 0.0
        self._display_score = 0.0
        self._snapshot     = None

        # High score entry
        self._qualifies    = False
        self._entering     = False
        self._name_input   = ""
        self._saved        = False

        # Fonts
        self._font_title   = None
        self._font_large   = None
        self._font_med     = None
        self._font_small   = None
        self._item_rects   = []

    def on_enter(self, **kwargs) -> None:
        self._font_title = pygame.font.SysFont("monospace", 32, bold=True)
        self._font_large = pygame.font.SysFont("monospace", 28, bold=True)
        self._font_med   = pygame.font.SysFont("monospace", 16, bold=True)
        self._font_small = pygame.font.SysFont("monospace", 12)
        self._timer        = 0.0
        self._display_score = 0.0
        self._selected     = 0
        self._qualifies    = qualifies_for_leaderboard(self._final_score)
        self._entering     = self._qualifies
        self._name_input   = ""
        self._saved        = False

        if self._game:
            self._snapshot = pygame.Surface((W, H))
            self._game.draw(self._snapshot)

    def handle_events(self, events: list) -> None:
        for ev in events:
            if ev.type == pygame.KEYDOWN:
                if self._entering:
                    if ev.key == pygame.K_RETURN and self._name_input.strip():
                        save_score(self._name_input, self._final_score,
                                   self._final_wave, self._final_time)
                        self._entering = False
                        self._saved = True
                    elif ev.key == pygame.K_BACKSPACE:
                        self._name_input = self._name_input[:-1]
                    elif ev.key == pygame.K_ESCAPE:
                        self._entering = False
                    else:
                        if len(self._name_input) < 16 and ev.unicode.isprintable():
                            self._name_input += ev.unicode
                else:
                    if ev.key in (pygame.K_UP, pygame.K_w):
                        self._selected = (self._selected - 1) % len(_GO_ITEMS)
                    elif ev.key in (pygame.K_DOWN, pygame.K_s):
                        self._selected = (self._selected + 1) % len(_GO_ITEMS)
                    elif ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self._activate(self._selected)
                    elif ev.key == pygame.K_ESCAPE:
                        from game.states.menu_state import MenuState
                        self.manager.replace_all(MenuState(self.manager))

            elif ev.type == pygame.MOUSEMOTION and not self._entering:
                lpos = self.manager.mouse_to_logical(ev.pos)
                for i, rect in enumerate(self._item_rects):
                    if rect.collidepoint(lpos):
                        self._selected = i
                        break
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                if not self._entering:
                    lpos = self.manager.mouse_to_logical(ev.pos)
                    for i, rect in enumerate(self._item_rects):
                        if rect.collidepoint(lpos):
                            self._activate(i)
                            break

    def _activate(self, index: int) -> None:
        item = _GO_ITEMS[index]
        if item == "PLAY AGAIN":
            from game.states.play_state import PlayState
            self.manager.replace_all(PlayState(self.manager))
        elif item == "MAIN MENU":
            from game.states.menu_state import MenuState
            self.manager.replace_all(MenuState(self.manager))

    def update(self, dt: float) -> None:
        self._timer += dt
        # Animated score count-up
        if self._display_score < self._final_score:
            speed = max(50, self._final_score * 1.5)
            self._display_score = min(
                self._final_score, self._display_score + speed * dt)

    def draw(self, surf: pygame.Surface) -> None:
        if self._font_title is None or self._font_large is None or self._font_med is None or self._font_small is None:
            self.on_enter()

        # Frozen game background
        if self._snapshot:
            surf.blit(self._snapshot, (0, 0))

        # Red-tinted dark overlay
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((20, 0, 0, 170))
        surf.blit(overlay, (0, 0))

        # Red vignette pulse
        pulse = 0.5 + 0.5 * math.sin(self._timer * 2.0)
        vig_a = int(40 + 20 * pulse)
        cx, cy = W // 2, H // 2
        for r in range(max(W, H), 0, -8):
            t = r / max(W, H)
            a = int(max(0, (1.0 - t * 1.6)) * vig_a)
            if a <= 0:
                continue
            pygame.draw.ellipse(surf, (80, 0, 0, a),
                (cx - r, cy - int(r * 0.6), r * 2, int(r * 1.2)), 4)

        # Title
        assert self._font_title is not None
        title = self._font_title.render("// PROCESS TERMINATED //", True, ENEMY_COL)
        surf.blit(title, (W // 2 - title.get_width() // 2, 120))

        # Decorative line
        lw = 400
        pygame.draw.line(surf, (210, 45, 75), (W//2 - lw//2, 165),
                         (W//2 + lw//2, 165), 1)

        # Score (animated count)
        score_val = int(self._display_score)
        assert self._font_large is not None
        score_txt = self._font_large.render(f"SCORE: {score_val}", True, WHITE)
        surf.blit(score_txt, (W // 2 - score_txt.get_width() // 2, 190))

        # Stats
        t_sec = int(self._final_time)
        stats = [
            f"WAVE REACHED:  {self._final_wave}",
            f"TIME SURVIVED: {t_sec // 60:02d}:{t_sec % 60:02d}",
        ]
        assert self._font_small is not None
        for i, st in enumerate(stats):
            txt = self._font_small.render(st, True, DIM)
            surf.blit(txt, (W // 2 - txt.get_width() // 2, 235 + i * 22))

        # High score entry
        entry_y = 290
        if self._entering:
            draw_panel(surf, (W//2 - 200, entry_y, 400, 80),
                       bg_color=(12, 8, 18), border_color=(210, 45, 75),
                       alpha=220, radius=8)
            assert self._font_med is not None
            hs_txt = self._font_med.render("NEW HIGH SCORE!", True, (255, 190, 0))
            surf.blit(hs_txt, (W//2 - hs_txt.get_width()//2, entry_y + 8))

            # Input field
            inp_txt = self._name_input + ("_" if int(self._timer * 3) % 2 == 0 else "")
            inp = self._font_med.render(f"NAME: {inp_txt}", True, ACCENT)
            surf.blit(inp, (W//2 - inp.get_width()//2, entry_y + 38))

            hint = self._font_small.render("ENTER to confirm", True, DIM)
            surf.blit(hint, (W//2 - hint.get_width()//2, entry_y + 64))
            entry_y += 100
        elif self._saved:
            saved = self._font_small.render("SCORE SAVED!", True, (80, 220, 100))
            surf.blit(saved, (W//2 - saved.get_width()//2, entry_y + 5))
            entry_y += 30

        # Menu items
        menu_y = max(entry_y + 20, 380)
        self._item_rects = []
        for i, item in enumerate(_GO_ITEMS):
            is_sel = (i == self._selected)
            ix = W // 2 - 110
            iy = menu_y + i * 48
            iw, ih = 220, 36
            rect = pygame.Rect(ix, iy, iw, ih)
            self._item_rects.append(rect)

            if is_sel:
                gs = pygame.Surface((iw + 16, ih + 8), pygame.SRCALPHA)
                pygame.draw.rect(gs, (210, 45, 75, 30),
                                 (0, 0, iw + 16, ih + 8), border_radius=5)
                surf.blit(gs, (ix - 8, iy - 4))
                draw_panel(surf, (ix, iy, iw, ih), bg_color=(20, 10, 18),
                           border_color=(210, 45, 75), alpha=220, radius=5)
                col = WHITE
                ax = ix - 18 + int(math.sin(self._timer * 5) * 3)
                assert self._font_med is not None
                arr = self._font_med.render(">", True, (210, 45, 75))
                surf.blit(arr, (ax, iy + 6))
            else:
                draw_panel(surf, (ix, iy, iw, ih), bg_color=(8, 8, 22),
                           border_color=(40, 40, 65), alpha=180, radius=5)
                col = DIM

            assert self._font_med is not None
            txt = self._font_med.render(item, True, col)
            surf.blit(txt, (ix + iw//2 - txt.get_width()//2,
                            iy + ih//2 - txt.get_height()//2))

        # Bottom hint
        hint = self._font_small.render(
            "W/S Navigate   ENTER Select   ESC Menu", True, (50, 50, 70))
        surf.blit(hint, (W//2 - hint.get_width()//2, H - 30))
