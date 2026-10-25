"""
controls_state.py — Rebind keyboard controls (two slots per action) and see the gamepad layout.

ENTER on a slot -> "press a key"; ESC cancels; BACKSPACE/DELETE clears the slot.
A key can only trigger one action: binding a key that is already used moves it, and
the screen tells you what it took it from.  Reserved keys (ESC, `, F3, F10, F11, ENTER)
can't be bound so you can never lock yourself out.
"""
from __future__ import annotations
import pygame

from game.state_manager import BaseState
from game.constants import LOGICAL_W as W, LOGICAL_H as H, BG, GRID_DIM, TILE, WHITE, DIM, ACCENT, CHAOS_COL
from utils import settings as S
from utils.keybinds import KEYS, ACTIONS, LABELS
from utils.helpers import draw_panel, alpha_rect

PANEL = pygame.Rect(W // 2 - 360, 110, 720, 470)
PAD_HELP = ("GAMEPAD   left stick move   right stick aim   RT fire   A dash   X hack   "
            "LB/RB or D-pad L/R weapon   START pause")


class ControlsState(BaseState):
    def __init__(self, manager) -> None:
        super().__init__(manager)
        self.sel   = 0           # row index: 0..len(ACTIONS)-1, then RESET, then BACK
        self.slot  = 0
        self.wait  = False       # True while waiting for a key press
        self.msg   = ""
        self.msg_t = 0.0
        self._rects: list = []
        self._f_title = self._f_row = self._f_small = None

    ROW_RESET = len(ACTIONS)
    ROW_BACK  = len(ACTIONS) + 1

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def on_enter(self, **kw) -> None:
        self._f_title = pygame.font.SysFont("monospace", 28, bold=True)
        self._f_row   = pygame.font.SysFont("monospace", 15, bold=True)
        self._f_small = pygame.font.SysFont("monospace", 11)
        self.sel, self.slot, self.wait = 0, 0, False
        pygame.mouse.set_visible(True)

    def on_exit(self) -> None:
        self._save()

    def _save(self) -> None:
        s = S.load()
        s["keybinds"] = KEYS.to_dict()
        S.save(s)

    def _say(self, text: str) -> None:
        self.msg, self.msg_t = text, 2.4

    # ── actions ───────────────────────────────────────────────────────────────

    def bind(self, key: int) -> None:
        action = ACTIONS[self.sel]
        try:
            taken = KEYS.rebind(action, self.slot, key)
        except ValueError as exc:
            self._say(f"{exc} — pick another key"); return
        self.wait = False
        name = pygame.key.name(key).upper()
        self._say(f"{name} -> {LABELS[action]}" + (f"   (taken from {LABELS[taken]})" if taken else ""))
        self._save()

    def activate(self) -> None:
        if self.sel < len(ACTIONS):
            self.wait = True
            self._say("PRESS A KEY  (ESC cancels, BACKSPACE clears)")
        elif self.sel == self.ROW_RESET:
            KEYS.reset(); self._save(); self._say("CONTROLS RESET TO DEFAULTS")
        else:
            self.manager.pop()

    # ── input ─────────────────────────────────────────────────────────────────

    def handle_events(self, events: list) -> None:
        for ev in events:
            if ev.type == pygame.KEYDOWN:
                if self.wait:                                   # capture mode: next key is the binding
                    if ev.key == pygame.K_ESCAPE:
                        self.wait = False; self._say("CANCELLED")
                    elif ev.key in (pygame.K_BACKSPACE, pygame.K_DELETE):
                        KEYS.rebind(ACTIONS[self.sel], self.slot, None)
                        self.wait = False; self._say("SLOT CLEARED"); self._save()
                    else:
                        self.bind(ev.key)
                    continue
                if ev.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                    self.manager.pop(); return
                elif ev.key in (pygame.K_UP, pygame.K_w):
                    self.sel = (self.sel - 1) % (len(ACTIONS) + 2)
                elif ev.key in (pygame.K_DOWN, pygame.K_s):
                    self.sel = (self.sel + 1) % (len(ACTIONS) + 2)
                elif ev.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
                    self.slot = 1 - self.slot
                elif ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.activate()
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and not self.wait:
                p = self.manager.mouse_to_logical(ev.pos)
                for i, (row, slots) in enumerate(self._rects):
                    for sl, r in enumerate(slots):
                        if r.collidepoint(p):
                            self.sel, self.slot = i, sl; self.activate(); return
                    if row.collidepoint(p):
                        self.sel = i; self.activate(); return

    def update(self, dt: float) -> None:
        if self.msg_t > 0:
            self.msg_t -= dt

    # ── drawing ───────────────────────────────────────────────────────────────

    def draw(self, surf: pygame.Surface) -> None:
        if not self._f_title:
            return
        surf.fill(BG)
        for x in range(0, W, TILE * 2):
            pygame.draw.line(surf, GRID_DIM, (x, 0), (x, H))
        for y in range(0, H, TILE * 2):
            pygame.draw.line(surf, GRID_DIM, (0, y), (W, y))
        title = self._f_title.render("// CONTROLS //", True, (210, 45, 75))
        surf.blit(title, (W // 2 - title.get_width() // 2, 40))
        draw_panel(surf, PANEL, alpha=205, radius=10)
        f = self._f_row
        h = f.render("ACTION", True, ACCENT); surf.blit(h, (PANEL.x + 24, PANEL.y + 8))
        for sl, label in enumerate(("PRIMARY", "SECONDARY")):
            t = f.render(label, True, ACCENT); surf.blit(t, (PANEL.x + 330 + sl * 190, PANEL.y + 8))

        self._rects = []
        rows = ACTIONS + ["__reset", "__back"]
        for i, key in enumerate(rows):
            y = PANEL.y + 34 + i * 29
            row = pygame.Rect(PANEL.x + 10, y, PANEL.w - 20, 27)
            sel = i == self.sel
            if sel:
                alpha_rect(surf, (210, 45, 75), row, 34, 5); pygame.draw.rect(surf, (210, 45, 75), row, 1, border_radius=5)
            slots = []
            if key in ACTIONS:
                surf.blit(f.render(LABELS[key], True, WHITE if sel else (190, 190, 215)), (row.x + 14, row.y + 5))
                for sl in range(2):
                    r = pygame.Rect(PANEL.x + 320 + sl * 190, y + 2, 170, 23)
                    slots.append(r)
                    active = sel and self.slot == sl
                    waiting = active and self.wait
                    draw_panel(surf, r, bg_color=(40, 22, 10) if waiting else (10, 10, 28),
                               border_color=CHAOS_COL if waiting else ((210, 45, 75) if active else (45, 45, 70)),
                               alpha=230, radius=4)
                    txt = "PRESS A KEY..." if waiting else KEYS.name(key, sl)
                    t = f.render(txt, True, CHAOS_COL if waiting else (WHITE if KEYS.map[key][sl] is not None else (90, 90, 115)))
                    surf.blit(t, (r.centerx - t.get_width() // 2, r.centery - t.get_height() // 2))
            else:
                label = "RESET TO DEFAULTS" if key == "__reset" else "BACK"
                t = f.render(label, True, WHITE if sel else (190, 190, 215))
                surf.blit(t, (row.centerx - t.get_width() // 2, row.y + 5))
            self._rects.append((row, slots))

        if self.msg_t > 0:
            m = f.render(self.msg, True, (255, 220, 120)); surf.blit(m, (W // 2 - m.get_width() // 2, PANEL.bottom + 14))
        pad = self._f_small.render(PAD_HELP, True, (110, 115, 150)); surf.blit(pad, (W // 2 - pad.get_width() // 2, PANEL.bottom + 44))
        hint = self._f_small.render("UP/DOWN select   LEFT/RIGHT switch slot   ENTER rebind   BACKSPACE clear   ESC back", True, (60, 60, 85))
        surf.blit(hint, (W // 2 - hint.get_width() // 2, H - 26))
