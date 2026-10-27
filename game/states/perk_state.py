"""
perk_state.py — Pick 1 of 3 upgrades after clearing a wave.

The game is frozen underneath (snapshot).  Input is locked briefly on entry so
a held fire button / stray click can never pick a perk by accident.
"""
from __future__ import annotations
import math
import pygame

from game.state_manager import BaseState
from game.constants import LOGICAL_W as W, LOGICAL_H as H, WHITE, DIM
from utils.helpers import draw_panel, alpha_rect
from game.perk_icons import draw_perk_icon
from game.perks import completing_synergies

_CARD_W, _CARD_H, _GAP = 300, 250, 28
_INPUT_LOCK = 0.4          # seconds


class PerkState(BaseState):
    def __init__(self, manager, game) -> None:
        super().__init__(manager)
        self._game     = game
        self._choices  = list(game.perk_choices)
        self._selected = 0
        self._timer    = 0.0
        self._rects: list[pygame.Rect] = []
        self._snapshot = None
        self._f_title = self._f_name = self._f_desc = self._f_small = None

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def on_enter(self, **kwargs) -> None:
        self._f_title = pygame.font.SysFont("monospace", 28, bold=True)
        self._f_name  = pygame.font.SysFont("monospace", 18, bold=True)
        self._f_desc  = pygame.font.SysFont("monospace", 13)
        self._f_small = pygame.font.SysFont("monospace", 11)
        self._timer   = 0.0
        self._selected = 0
        pygame.mouse.set_visible(True)
        self._snapshot = pygame.Surface((W, H))
        self._game.draw(self._snapshot)
        total = len(self._choices) * _CARD_W + (len(self._choices) - 1) * _GAP
        x0 = W // 2 - total // 2
        self._rects = [pygame.Rect(x0 + i * (_CARD_W + _GAP), H // 2 - _CARD_H // 2 + 10,
                                   _CARD_W, _CARD_H) for i in range(len(self._choices))]

    # ── input ─────────────────────────────────────────────────────────────────

    def _pick(self, index: int) -> None:
        if not (0 <= index < len(self._choices)):
            return
        self._game.audio.play("perk_select")
        self._game.grant_perk(self._choices[index].key)
        pygame.mouse.set_visible(False)
        self.manager.pop()

    def handle_events(self, events: list) -> None:
        for ev in events:
            if self._timer < _INPUT_LOCK:
                continue
            if ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                    self._pick(ev.key - pygame.K_1)
                elif ev.key in (pygame.K_LEFT, pygame.K_a):
                    self._selected = (self._selected - 1) % len(self._choices)
                elif ev.key in (pygame.K_RIGHT, pygame.K_d):
                    self._selected = (self._selected + 1) % len(self._choices)
                elif ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self._pick(self._selected)
            elif ev.type == pygame.MOUSEMOTION:
                lpos = self.manager.mouse_to_logical(ev.pos)
                for i, r in enumerate(self._rects):
                    if r.collidepoint(lpos):
                        self._selected = i
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                lpos = self.manager.mouse_to_logical(ev.pos)
                for i, r in enumerate(self._rects):
                    if r.collidepoint(lpos):
                        self._pick(i)
                        break

    def update(self, dt: float) -> None:
        self._timer += dt

    # ── drawing ───────────────────────────────────────────────────────────────

    def draw(self, surf: pygame.Surface) -> None:
        if self._f_title is None or self._snapshot is None:
            return
        surf.blit(self._snapshot, (0, 0))
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 175))
        surf.blit(veil, (0, 0))

        wave = self._game.wave_mgr.wave
        title = self._f_title.render(f"// WAVE {wave} CLEARED //", True, (0, 200, 160))
        surf.blit(title, (W // 2 - title.get_width() // 2, 90))
        sub = self._f_small.render("CHOOSE AN UPGRADE", True, DIM)
        surf.blit(sub, (W // 2 - sub.get_width() // 2, 128))

        slide = min(1.0, self._timer / 0.3)
        ease  = 1 - (1 - slide) ** 3
        for i, (perk, rect) in enumerate(zip(self._choices, self._rects)):
            sel = (i == self._selected) and self._timer >= _INPUT_LOCK
            r   = rect.move(0, int((1 - ease) * 40))
            col = perk.color
            if sel:
                alpha_rect(surf, col, (r.x - 8, r.y - 8, r.w + 16, r.h + 16), 30, 12)
            draw_panel(surf, (r.x, r.y, r.w, r.h), bg_color=(14, 14, 30) if not sel else (22, 20, 40),
                       border_color=col if sel else (50, 50, 85), alpha=235, radius=8)
            owned = self._game.perks.get(perk.key, 0)
            if perk.evolution:                                    # gold frame + tag for evolutions
                pygame.draw.rect(surf, (255, 215, 90), (r.x, r.y, r.w, r.h), 2, border_radius=8)
                tag = self._f_small.render("\u2605 EVOLUTION", True, (255, 215, 90))
                surf.blit(tag, (r.centerx - tag.get_width() // 2, r.y + 12))
            key = self._f_small.render(f"[{i + 1}]", True, DIM)
            surf.blit(key, (r.x + 14, r.y + 12))
            if perk.max_stacks > 1:
                stacks = self._f_small.render(f"{owned}/{perk.max_stacks}", True, col if owned else DIM)
                surf.blit(stacks, (r.right - 14 - stacks.get_width(), r.y + 12))
            draw_perk_icon(surf, perk.key, r.centerx, r.y + 78, col, 24)
            name = self._f_name.render(perk.name, True, WHITE if sel else col)
            surf.blit(name, (r.centerx - name.get_width() // 2, r.y + 124))
            self._wrapped(surf, perk.desc, r.x + 20, r.y + 160, r.w - 40, DIM if not sel else WHITE)
            for k, syn in enumerate(completing_synergies(self._game.perks, perk.key)[:2]):
                st = self._f_small.render(f"\u2605 SYNERGY: {syn.name}", True, syn.color)
                surf.blit(st, (r.centerx - st.get_width() // 2, r.bottom - 30 + k * 13))

        hint = self._f_small.render("1 / 2 / 3 or click to choose    A / D + ENTER", True, (60, 60, 85))
        surf.blit(hint, (W // 2 - hint.get_width() // 2, self._rects[0].bottom + 30 if self._rects else H - 90))

    def _wrapped(self, surf, text, x, y, width, color) -> None:
        line, lines = "", []
        for word in text.split():
            test = f"{line} {word}".strip()
            if self._f_desc.size(test)[0] <= width:
                line = test
            else:
                lines.append(line); line = word
        lines.append(line)
        for j, ln in enumerate(lines):
            t = self._f_desc.render(ln, True, color)
            surf.blit(t, (x + (width - t.get_width()) // 2, y + j * 18))
