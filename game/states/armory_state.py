"""
armory_state.py — Spend shards on permanent upgrades, pick a starting loadout,
and browse achievements.  Keyboard, mouse and gamepad (D-pad + A/B via the
manager's key translation) all work.
"""
from __future__ import annotations
import math
import pygame

from game.state_manager import BaseState
from game.constants import LOGICAL_W as W, LOGICAL_H as H, BG, GRID_DIM, TILE, WHITE, DIM, ACCENT, CHAOS_COL
from game.perks import PERKS
from utils import meta as M
from utils.data_manager import load_meta, save_meta
from utils.helpers import draw_panel, alpha_rect

TABS = ["UPGRADES", "LOADOUT", "ACHIEVEMENTS"]
PANEL = pygame.Rect(W // 2 - 400, 150, 800, 470)


class ArmoryState(BaseState):
    def __init__(self, manager) -> None:
        super().__init__(manager)
        self.meta   = None
        self.tab    = 0
        self.sel    = 0
        self.msg    = ""
        self.msg_t  = 0.0
        self.timer  = 0.0
        self._rects: list[pygame.Rect] = []
        self._tab_rects: list[pygame.Rect] = []
        self._f_title = self._f_row = self._f_small = self._f_big = None

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def on_enter(self, **kw) -> None:
        self._f_title = pygame.font.SysFont("monospace", 28, bold=True)
        self._f_big   = pygame.font.SysFont("monospace", 18, bold=True)
        self._f_row   = pygame.font.SysFont("monospace", 15, bold=True)
        self._f_small = pygame.font.SysFont("monospace", 12)
        self.meta = load_meta()
        self.tab = self.sel = 0
        pygame.mouse.set_visible(True)

    def on_exit(self) -> None:
        if self.meta is not None:
            save_meta(self.meta)

    # ── data ──────────────────────────────────────────────────────────────────

    def rows(self) -> list[dict]:
        m = self.meta
        if self.tab == 0:
            out = []
            for uid, (name, desc, costs) in M.UPGRADES.items():
                out.append({"kind": "upgrade", "id": uid, "label": name, "desc": desc,
                            "lvl": M.level(m, uid), "max": len(costs), "cost": M.upgrade_cost(m, uid)})
            return out
        if self.tab == 1:
            out = [{"kind": "header", "label": "STARTING WEAPON"}]
            for i, name in enumerate(M.WEAPON_NAMES):
                out.append({"kind": "weapon", "id": i, "label": name, "owned": i in m["weapons"],
                            "cost": M.WEAPON_COSTS[i], "equipped": m["loadout"]["weapon"] == i})
            out.append({"kind": "header", "label": "STARTING PERK  (daily runs ignore the loadout)"})
            out.append({"kind": "perk", "id": None, "label": "NONE", "owned": True, "cost": 0,
                        "equipped": m["loadout"]["perk"] is None, "desc": ""})
            for k in M.STARTER_PERKS:
                out.append({"kind": "perk", "id": k, "label": PERKS[k].name, "owned": k in m["perks"],
                            "cost": M.STARTER_COSTS[k], "equipped": m["loadout"]["perk"] == k,
                            "desc": PERKS[k].desc, "color": PERKS[k].color})
            return out
        out = []
        for aid, (name, desc, _p) in M.ACHIEVEMENTS.items():
            out.append({"kind": "ach", "id": aid, "label": name, "desc": desc, "done": aid in m["achievements"]})
        return out

    def _selectable(self) -> list[int]:
        return [i for i, r in enumerate(self.rows()) if r["kind"] != "header"]

    def _say(self, text: str) -> None:
        self.msg, self.msg_t = text, 2.2

    # ── actions ───────────────────────────────────────────────────────────────

    def activate(self) -> None:
        rows = self.rows()
        if not rows or not 0 <= self.sel < len(rows):
            return
        r, m = rows[self.sel], self.meta
        if r["kind"] == "upgrade":
            if r["cost"] is None:
                self._say("ALREADY MAX LEVEL")
            elif M.buy_upgrade(m, r["id"]):
                self._say(f"{r['label']} -> LEVEL {M.level(m, r['id'])}")
            else:
                self._say(f"NOT ENOUGH SHARDS  (need {r['cost']})")
        elif r["kind"] == "weapon":
            if not r["owned"]:
                if not M.buy_weapon(m, r["id"]):
                    self._say(f"NOT ENOUGH SHARDS  (need {r['cost']})")
                    return
            M.set_loadout(m, weapon=r["id"]); self._say(f"STARTING WEAPON: {r['label']}")
        elif r["kind"] == "perk":
            if not r["owned"]:
                if not M.buy_perk(m, r["id"]):
                    self._say(f"NOT ENOUGH SHARDS  (need {r['cost']})")
                    return
            M.set_loadout(m, perk=r["id"]); self._say(f"STARTING PERK: {r['label']}")
        save_meta(m)

    def _move(self, d: int) -> None:
        idx = self._selectable()
        if not idx:
            return
        pos = idx.index(self.sel) if self.sel in idx else 0
        self.sel = idx[(pos + d) % len(idx)]

    def _set_tab(self, t: int) -> None:
        self.tab = t % len(TABS)
        self.sel = (self._selectable() or [0])[0]

    # ── input ─────────────────────────────────────────────────────────────────

    def handle_events(self, events: list) -> None:
        for ev in events:
            if ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                    self.manager.pop(); return
                elif ev.key in (pygame.K_UP, pygame.K_w):
                    self._move(-1)
                elif ev.key in (pygame.K_DOWN, pygame.K_s):
                    self._move(1)
                elif ev.key in (pygame.K_LEFT, pygame.K_a, pygame.K_q):
                    self._set_tab(self.tab - 1)
                elif ev.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_e, pygame.K_TAB):
                    self._set_tab(self.tab + 1)
                elif ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.activate()
            elif ev.type == pygame.MOUSEMOTION:
                p = self.manager.mouse_to_logical(ev.pos)
                for i, r in enumerate(self._rects):
                    if r is not None and r.collidepoint(p):
                        self.sel = i
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                p = self.manager.mouse_to_logical(ev.pos)
                for t, r in enumerate(self._tab_rects):
                    if r.collidepoint(p):
                        self._set_tab(t); return
                for i, r in enumerate(self._rects):
                    if r is not None and r.collidepoint(p):
                        self.sel = i; self.activate(); break

    def update(self, dt: float) -> None:
        self.timer += dt
        if self.msg_t > 0:
            self.msg_t -= dt

    # ── drawing ───────────────────────────────────────────────────────────────

    def draw(self, surf: pygame.Surface) -> None:
        if self._f_title is None or self.meta is None:
            return
        surf.fill(BG)
        for x in range(0, W, TILE * 2):
            pygame.draw.line(surf, GRID_DIM, (x, 0), (x, H))
        for y in range(0, H, TILE * 2):
            pygame.draw.line(surf, GRID_DIM, (0, y), (W, y))
        title = self._f_title.render("// ARMORY //", True, (210, 45, 75))
        surf.blit(title, (W // 2 - title.get_width() // 2, 40))
        sh = self._f_big.render(f"SHARDS  {self.meta['shards']}", True, CHAOS_COL)
        surf.blit(sh, (W // 2 - sh.get_width() // 2, 84))

        self._tab_rects = []
        tw = PANEL.w // len(TABS)
        for i, name in enumerate(TABS):
            r = pygame.Rect(PANEL.x + i * tw, 116, tw - 6, 30)
            self._tab_rects.append(r)
            on = i == self.tab
            draw_panel(surf, r, bg_color=(22, 12, 20) if on else (10, 10, 24),
                       border_color=(210, 45, 75) if on else (45, 45, 70), alpha=225, radius=5)
            t = self._f_row.render(name, True, WHITE if on else DIM)
            surf.blit(t, (r.centerx - t.get_width() // 2, r.centery - t.get_height() // 2))

        draw_panel(surf, PANEL, alpha=205, radius=10)
        rows = self.rows()
        rh = min(40, (PANEL.h - 20) // max(1, len(rows)))
        self._rects = []
        y = PANEL.y + 10
        for i, r in enumerate(rows):
            rect = pygame.Rect(PANEL.x + 10, y, PANEL.w - 20, rh - 2)
            y += rh
            if r["kind"] == "header":
                self._rects.append(None)
                t = self._f_small.render(r["label"], True, ACCENT)
                surf.blit(t, (rect.x + 6, rect.centery - t.get_height() // 2 + 4))
                continue
            self._rects.append(rect)
            sel = i == self.sel
            if sel:
                alpha_rect(surf, (210, 45, 75), rect, 38, 5)
                pygame.draw.rect(surf, (210, 45, 75), rect, 1, border_radius=5)
            self._draw_row(surf, r, rect, sel)

        if self.msg_t > 0:
            m = self._f_row.render(self.msg, True, (255, 220, 120))
            m.set_alpha(int(255 * min(1.0, self.msg_t / 0.5)))
            surf.blit(m, (W // 2 - m.get_width() // 2, PANEL.bottom + 14))
        hint = self._f_small.render("UP/DOWN select    ENTER buy / equip    LEFT/RIGHT (or Q/E) switch tab    ESC back",
                                    True, (60, 60, 85))
        surf.blit(hint, (W // 2 - hint.get_width() // 2, H - 26))

    def _draw_row(self, surf, r: dict, rect: pygame.Rect, sel: bool) -> None:
        f, fs = self._f_row, self._f_small
        cy = rect.centery
        name_col = WHITE if sel else (200, 200, 220)
        if r["kind"] == "upgrade":
            surf.blit(f.render(r["label"], True, name_col), (rect.x + 10, cy - 9))
            surf.blit(fs.render(r["desc"], True, DIM), (rect.x + 190, cy - 6))
            for k in range(r["max"]):                                   # level pips
                c = (0, 200, 160) if k < r["lvl"] else (40, 40, 65)
                pygame.draw.circle(surf, c, (rect.right - 150 + k * 18, cy), 6)
            txt = "MAX" if r["cost"] is None else f"{r['cost']}"
            col = (0, 200, 160) if r["cost"] is None else (CHAOS_COL if self.meta["shards"] >= r["cost"] else (120, 70, 80))
            t = f.render(txt, True, col); surf.blit(t, (rect.right - 10 - t.get_width(), cy - 9))
        elif r["kind"] in ("weapon", "perk"):
            surf.blit(f.render(("> " if r["equipped"] else "  ") + r["label"], True,
                               (0, 220, 170) if r["equipped"] else name_col), (rect.x + 10, cy - 9))
            if r.get("desc"):
                surf.blit(fs.render(r["desc"], True, DIM), (rect.x + 230, cy - 6))
            if r["equipped"]:
                t, col = f.render("EQUIPPED", True, (0, 220, 170)), None
            elif r["owned"]:
                t = f.render("OWNED", True, (110, 120, 150))
            else:
                afford = self.meta["shards"] >= r["cost"]
                t = f.render(f"{r['cost']}", True, CHAOS_COL if afford else (120, 70, 80))
            surf.blit(t, (rect.right - 10 - t.get_width(), cy - 9))
        else:                                                          # achievement
            col = (0, 220, 170) if r["done"] else (95, 95, 120)
            surf.blit(f.render(("[x] " if r["done"] else "[ ] ") + r["label"], True, col), (rect.x + 10, cy - 9))
            surf.blit(fs.render(r["desc"], True, DIM), (rect.x + 260, cy - 6))
            t = fs.render(f"+{M.ACHIEVEMENT_BONUS}" if not r["done"] else "DONE", True, CHAOS_COL if not r["done"] else col)
            surf.blit(t, (rect.right - 10 - t.get_width(), cy - 6))
