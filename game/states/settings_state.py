"""
settings_state.py — Settings screen: sliders, toggles, choices, and a link to the
Controls (key rebinding) screen.  Every change is saved immediately.
Keyboard (UP/DOWN, LEFT/RIGHT, ENTER), mouse (click / drag) and gamepad (via the
manager's D-pad -> arrow-key translation) all work.
"""
from __future__ import annotations
import pygame

from game.state_manager import BaseState
from game.constants import LOGICAL_W as W, LOGICAL_H as H, BG, GRID_DIM, TILE, WHITE, DIM, ACCENT
from utils import settings as S
from utils.helpers import draw_panel, alpha_rect

PANEL = pygame.Rect(W // 2 - 330, 130, 660, 500)
ROW_H = 38


class SettingsState(BaseState):
    def __init__(self, manager) -> None:
        super().__init__(manager)
        self._s        = S.normalise({})
        self._sel      = 0
        self._timer    = 0.0
        self._rects: list[pygame.Rect] = []
        self._drag     = None
        self._f_title = self._f_row = self._f_small = None
        self._rows = [
            {"k": "slider", "key": "volume",   "label": "VOLUME",         "lo": 0.0,  "hi": 1.0,  "step": 0.05, "fmt": lambda v: f"{int(v * 100)}%"},
            {"k": "toggle", "key": "music",    "label": "MUSIC"},
            {"k": "slider", "key": "shake",    "label": "SCREEN SHAKE",   "lo": 0.0,  "hi": 1.0,  "step": 0.1,  "fmt": lambda v: f"{int(v * 100)}%"},
            {"k": "toggle", "key": "hitstop",  "label": "HIT-STOP (impact freezes)"},
            {"k": "choice", "key": "bloom",    "label": "BLOOM",          "options": [n for n, _ in S.BLOOM_LEVELS]},
            {"k": "slider", "key": "vignette", "label": "VIGNETTE",       "lo": 0.0,  "hi": 1.0,  "step": 0.05, "fmt": lambda v: f"{int(v * 100)}%"},
            {"k": "action", "key": "fullscreen", "label": "FULLSCREEN"},
            {"k": "toggle", "key": "gamepad",  "label": "GAMEPAD"},
            {"k": "slider", "key": "deadzone", "label": "STICK DEADZONE", "lo": 0.05, "hi": 0.60, "step": 0.05, "fmt": lambda v: f"{int(v * 100)}%"},
            {"k": "action", "key": "controls", "label": "CONTROLS  (rebind keys)  >"},
            {"k": "action", "key": "back",     "label": "BACK"},
        ]

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def on_enter(self, **kw) -> None:
        self._f_title = pygame.font.SysFont("monospace", 28, bold=True)
        self._f_row   = pygame.font.SysFont("monospace", 15, bold=True)
        self._f_small = pygame.font.SysFont("monospace", 11)
        self._s       = S.load()
        self._sel     = 0
        pygame.mouse.set_visible(True)

    def on_exit(self) -> None:
        self._commit()

    def _commit(self) -> None:
        """Save + apply the parts that live outside a run (gamepad)."""
        S.save(self._s)
        pad = getattr(self.manager, "gamepad", None)
        if pad is not None:
            pad.enabled, pad.deadzone = self._s["gamepad"], self._s["deadzone"]

    # ── value editing ─────────────────────────────────────────────────────────

    def _adjust(self, row: dict, direction: int) -> None:
        key = row["key"]
        if row["k"] == "slider":
            v = self._s[key] + direction * row["step"]
            self._s[key] = round(max(row["lo"], min(row["hi"], v)), 3)
        elif row["k"] == "toggle":
            self._s[key] = not self._s[key]
        elif row["k"] == "choice":
            opts = row["options"]
            self._s[key] = opts[(opts.index(self._s[key]) + direction) % len(opts)]
        self._commit()

    def _activate(self, row: dict) -> None:
        if row["k"] in ("toggle", "choice"):
            self._adjust(row, 1)
        elif row["k"] == "action":
            if row["key"] == "fullscreen":
                self.manager.toggle_fullscreen()
            elif row["key"] == "controls":
                from game.states.controls_state import ControlsState
                self._commit()
                self.manager.push(ControlsState(self.manager))
            elif row["key"] == "back":
                self.manager.pop()

    def _set_slider_from_mouse(self, row: dict, rect: pygame.Rect, mx: int) -> None:
        bar_x, bar_w = rect.right - 250, 190
        t = max(0.0, min(1.0, (mx - bar_x) / bar_w))
        raw = row["lo"] + t * (row["hi"] - row["lo"])
        self._s[row["key"]] = round(round(raw / row["step"]) * row["step"], 3)
        self._s[row["key"]] = max(row["lo"], min(row["hi"], self._s[row["key"]]))
        self._commit()

    # ── input ─────────────────────────────────────────────────────────────────

    def handle_events(self, events: list) -> None:
        for ev in events:
            if ev.type == pygame.KEYDOWN:
                row = self._rows[self._sel]
                if ev.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                    self.manager.pop(); return
                elif ev.key in (pygame.K_UP, pygame.K_w):
                    self._sel = (self._sel - 1) % len(self._rows)
                elif ev.key in (pygame.K_DOWN, pygame.K_s):
                    self._sel = (self._sel + 1) % len(self._rows)
                elif ev.key in (pygame.K_LEFT, pygame.K_a):
                    self._adjust(row, -1)
                elif ev.key in (pygame.K_RIGHT, pygame.K_d):
                    self._adjust(row, 1)
                elif ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self._activate(row)
            elif ev.type == pygame.MOUSEMOTION:
                p = self.manager.mouse_to_logical(ev.pos)
                if self._drag is not None:
                    self._set_slider_from_mouse(self._rows[self._drag], self._rects[self._drag], p[0])
                else:
                    for i, r in enumerate(self._rects):
                        if r.collidepoint(p):
                            self._sel = i
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                p = self.manager.mouse_to_logical(ev.pos)
                for i, r in enumerate(self._rects):
                    if not r.collidepoint(p):
                        continue
                    self._sel, row = i, self._rows[i]
                    if row["k"] == "slider":
                        self._drag = i; self._set_slider_from_mouse(row, r, p[0])
                    else:
                        self._activate(row)
                    break
            elif ev.type == pygame.MOUSEBUTTONUP:
                self._drag = None

    def update(self, dt: float) -> None:
        self._timer += dt

    # ── drawing ───────────────────────────────────────────────────────────────

    def draw(self, surf: pygame.Surface) -> None:
        if not self._f_title:
            return
        surf.fill(BG)
        for x in range(0, W, TILE * 2):
            pygame.draw.line(surf, GRID_DIM, (x, 0), (x, H))
        for y in range(0, H, TILE * 2):
            pygame.draw.line(surf, GRID_DIM, (0, y), (W, y))
        title = self._f_title.render("// SETTINGS //", True, (210, 45, 75))
        surf.blit(title, (W // 2 - title.get_width() // 2, 54))
        pygame.draw.line(surf, (210, 45, 75), (W // 2 - 150, 96), (W // 2 + 150, 96), 1)
        draw_panel(surf, PANEL, alpha=205, radius=10)

        self._rects = []
        for i, row in enumerate(self._rows):
            rect = pygame.Rect(PANEL.x + 12, PANEL.y + 12 + i * ROW_H, PANEL.w - 24, ROW_H - 4)
            self._rects.append(rect)
            sel = i == self._sel
            if sel:
                alpha_rect(surf, (210, 45, 75), rect, 36, 5)
                pygame.draw.rect(surf, (210, 45, 75), rect, 1, border_radius=5)
            self._draw_row(surf, row, rect, sel)

        hint = self._f_small.render("UP/DOWN select   LEFT/RIGHT change   ENTER toggle/open   ESC back   (changes save instantly)",
                                    True, (60, 60, 85))
        surf.blit(hint, (W // 2 - hint.get_width() // 2, H - 26))

    def _draw_row(self, surf, row: dict, rect: pygame.Rect, sel: bool) -> None:
        f, cy = self._f_row, rect.centery
        label = f.render(row["label"], True, WHITE if sel else (190, 190, 215))
        surf.blit(label, (rect.x + 12, cy - label.get_height() // 2))
        k, key = row["k"], row["key"]
        if k == "slider":
            v = self._s[key]
            bx, bw = rect.right - 250, 190
            pygame.draw.rect(surf, (20, 20, 40), (bx, cy - 6, bw, 12), border_radius=6)
            frac = (v - row["lo"]) / (row["hi"] - row["lo"])
            if frac > 0:
                pygame.draw.rect(surf, (210, 45, 75) if sel else (100, 100, 140), (bx, cy - 6, int(bw * frac), 12), border_radius=6)
            pygame.draw.rect(surf, (60, 60, 100), (bx, cy - 6, bw, 12), 1, border_radius=6)
            pygame.draw.circle(surf, WHITE if sel else (130, 130, 165), (bx + int(bw * frac), cy), 8)
            t = f.render(row["fmt"](v), True, ACCENT)
            surf.blit(t, (rect.right - 12 - t.get_width(), cy - t.get_height() // 2))
        elif k == "toggle":
            on = self._s[key]
            t = f.render("ON" if on else "OFF", True, (0, 220, 170) if on else (120, 120, 145))
            surf.blit(t, (rect.right - 12 - t.get_width(), cy - t.get_height() // 2))
        elif k == "choice":
            t = f.render(f"<  {self._s[key]}  >", True, ACCENT)
            surf.blit(t, (rect.right - 12 - t.get_width(), cy - t.get_height() // 2))
        elif key == "fullscreen":
            on = getattr(self.manager, "_fullscreen", False)
            t = f.render("ON" if on else "OFF", True, (0, 220, 170) if on else (120, 120, 145))
            surf.blit(t, (rect.right - 12 - t.get_width(), cy - t.get_height() // 2))
