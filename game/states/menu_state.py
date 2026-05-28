"""
menu_state.py — Animated main menu with logo, glitch effects,
and keyboard + mouse navigation.

Fixes:
 - Pre-baked vignette (no per-frame ellipse loops)
 - Wave break countdown visible when returning from game
"""
from __future__ import annotations
import math, random
import pygame

from game.state_manager import BaseState
from game.constants import (
    LOGICAL_W as W, LOGICAL_H as H,
    BG, GRID_DIM, GRID_BRIGHT, TILE, WHITE, DIM,
)
from utils.helpers import draw_panel


_MENU_ITEMS = ["PLAY", "HIGH SCORES", "SETTINGS", "QUIT"]

# Pre-baked vignette shared across re-entries
_vignette_cache: pygame.Surface | None = None


def _get_vignette() -> pygame.Surface:
    global _vignette_cache
    if _vignette_cache is None:
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        cx, cy = W // 2, H // 2
        steps = 28
        for i in range(steps, 0, -1):
            t = i / steps
            rx = int(cx * t * 2.2)
            ry = int(cy * t * 2.2)
            alpha = int((1.0 - t) * 105)
            if alpha <= 0 or rx <= 0 or ry <= 0:
                continue
            pygame.draw.ellipse(s, (0, 0, 0, alpha),
                                (cx - rx, cy - ry, rx * 2, ry * 2))
        _vignette_cache = s
    return _vignette_cache


class MenuState(BaseState):
    def __init__(self, manager) -> None:
        super().__init__(manager)
        self._selected     = 0
        self._timer        = 0.0
        self._logo         = None
        self._particles    = []
        self._glitch_lines = []
        self._glitch_cd    = 1.0
        self._item_offsets = [-300.0] * len(_MENU_ITEMS)
        self._debris       = []
        self._font_item    = None
        self._font_small   = None
        self._font_tag     = None
        self._item_rects   = []

    def on_enter(self, **kwargs) -> None:
        self._font_item  = pygame.font.SysFont("monospace", 22, bold=True)
        self._font_small = pygame.font.SysFont("monospace", 11)
        self._font_tag   = pygame.font.SysFont("monospace", 13)
        self._timer      = 0.0
        self._selected   = 0
        self._item_offsets = [-300.0] * len(_MENU_ITEMS)

        if self.manager.logo:
            lw, lh = self.manager.logo.get_size()
            scale = min(280 / lw, 280 / lh)
            self._logo = pygame.transform.smoothscale(
                self.manager.logo, (int(lw * scale), int(lh * scale)))

        self._particles = [_MenuParticle() for _ in range(35)]
        self._debris    = [_MenuDebris()   for _ in range(25)]
        pygame.mouse.set_visible(True)

    def handle_events(self, events: list) -> None:
        for ev in events:
            if ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_UP, pygame.K_w):
                    self._selected = (self._selected - 1) % len(_MENU_ITEMS)
                elif ev.key in (pygame.K_DOWN, pygame.K_s):
                    self._selected = (self._selected + 1) % len(_MENU_ITEMS)
                elif ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self._activate(self._selected)
                elif ev.key == pygame.K_ESCAPE:
                    self.manager.quit()
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

    def _activate(self, index: int) -> None:
        item = _MENU_ITEMS[index]
        if item == "PLAY":
            from game.states.play_state import PlayState
            self.manager.switch(PlayState(self.manager))
        elif item == "HIGH SCORES":
            from game.states.highscores_state import HighScoresState
            self.manager.push(HighScoresState(self.manager))
        elif item == "SETTINGS":
            from game.states.settings_state import SettingsState
            self.manager.push(SettingsState(self.manager))
        elif item == "QUIT":
            self.manager.quit()

    def update(self, dt: float) -> None:
        self._timer += dt
        for i in range(len(_MENU_ITEMS)):
            delay = 0.3 + i * 0.10
            if self._timer > delay:
                t = min(1.0, (self._timer - delay) / 0.30)
                t = 1.0 - (1.0 - t) ** 3  # ease-out cubic
                self._item_offsets[i] = -300 * (1.0 - t)
            else:
                self._item_offsets[i] = -300.0
        for p in self._particles:
            p.update(dt)
        for d in self._debris:
            d.update(dt)
        self._glitch_cd -= dt
        if self._glitch_cd <= 0:
            self._glitch_cd = random.uniform(0.8, 3.0)
            self._glitch_lines = [
                (random.randint(0, H), random.randint(40, W),
                 (random.randint(0, 60), random.randint(0, 255),
                  random.randint(150, 255)))
                for _ in range(random.randint(1, 4))]
        elif random.random() < 0.06:
            self._glitch_lines = []

    def draw(self, surf: pygame.Surface) -> None:
        # Ensure fonts exist (draw may be called before on_enter)
        if self._font_item is None or self._font_small is None or self._font_tag is None:
            self._font_item  = pygame.font.SysFont("monospace", 22, bold=True)
            self._font_small = pygame.font.SysFont("monospace", 11)
            self._font_tag   = pygame.font.SysFont("monospace", 13)

        surf.fill(BG)

        # Grid
        for x in range(0, W, TILE):
            col = GRID_BRIGHT if x % (TILE * 4) == 0 else GRID_DIM
            pygame.draw.line(surf, col, (x, 0), (x, H))
        for y in range(0, H, TILE):
            col = GRID_BRIGHT if y % (TILE * 4) == 0 else GRID_DIM
            pygame.draw.line(surf, col, (0, y), (W, y))

        for d in self._debris:
            d.draw(surf)

        for (gy, gw, gc) in self._glitch_lines:
            pygame.draw.rect(surf, gc, (0, gy, gw, 2))

        for p in self._particles:
            p.draw(surf)

        # Logo with floating animation
        logo_bottom = 55
        if self._logo:
            lw, lh = self._logo.get_size()
            lx = W // 2 - lw // 2
            fy = math.sin(self._timer * 1.2) * 6
            ly = int(55 + fy)

            # Pulsing red glow behind logo
            pulse = 0.5 + 0.5 * math.sin(self._timer * 2.0)
            gr = int(lw * 0.55 + 15 * pulse)
            gs = pygame.Surface((gr * 2, gr * 2), pygame.SRCALPHA)
            pygame.draw.circle(gs, (210, 45, 75, int(18 + 14 * pulse)),
                               (gr, gr), gr)
            surf.blit(gs, (W // 2 - gr, ly + lh // 2 - gr))
            surf.blit(self._logo, (lx, ly))
            logo_bottom = ly + lh + 18

        # Tagline with occasional glitch
        tag_text = "FIGHT. ADAPT. BREAK. BECOME."
        if random.random() < 0.025:
            idx = random.randint(0, len(tag_text) - 1)
            tag_text = (tag_text[:idx] +
                        random.choice("!@#$%^&*<>") +
                        tag_text[idx + 1:])
        tag = self._font_tag.render(tag_text, True, (210, 45, 75))
        surf.blit(tag, (W // 2 - tag.get_width() // 2, logo_bottom))

        # Menu items — slide in from left
        menu_y = logo_bottom + 46
        self._item_rects = []
        for i, item in enumerate(_MENU_ITEMS):
            is_sel = (i == self._selected)
            x_off = self._item_offsets[i]
            ix = int(W // 2 - 120 + x_off)
            iy = menu_y + i * 50
            iw, ih = 240, 40
            rect = pygame.Rect(ix, iy, iw, ih)
            self._item_rects.append(rect)

            if is_sel:
                # Glow halo
                gs2 = pygame.Surface((iw + 20, ih + 10), pygame.SRCALPHA)
                pygame.draw.rect(gs2, (210, 45, 75, 22),
                                 (0, 0, iw + 20, ih + 10), border_radius=6)
                surf.blit(gs2, (ix - 10, iy - 5))
                draw_panel(surf, (ix, iy, iw, ih), bg_color=(20, 10, 18),
                           border_color=(210, 45, 75), alpha=220, radius=6)
                col = WHITE
                # Animated arrow
                ax = ix - 22 + int(math.sin(self._timer * 5) * 3)
                arr = self._font_item.render(">", True, (210, 45, 75))
                surf.blit(arr, (ax, iy + ih // 2 - arr.get_height() // 2))
            else:
                draw_panel(surf, (ix, iy, iw, ih), bg_color=(8, 8, 22),
                           border_color=(40, 40, 65), alpha=180, radius=6)
                col = DIM

            txt = self._font_item.render(item, True, col)
            surf.blit(txt, (ix + iw // 2 - txt.get_width() // 2,
                            iy + ih // 2 - txt.get_height() // 2))

        # Bottom hints
        hint = self._font_small.render(
            "W/S Navigate   ENTER Select   F11 Fullscreen   ESC Quit",
            True, (50, 50, 70))
        surf.blit(hint, (W // 2 - hint.get_width() // 2, H - 28))
        ver = self._font_small.render("v1.0.0", True, (40, 40, 60))
        surf.blit(ver, (W - 62, H - 18))

        # Pre-baked vignette
        surf.blit(_get_vignette(), (0, 0))


# ── Helper classes ─────────────────────────────────────────────────────────────

class _MenuParticle:
    def __init__(self) -> None:
        self._randomize()

    def _randomize(self) -> None:
        self.x     = random.uniform(0, W)
        self.y     = random.uniform(0, H)
        self.vx    = random.uniform(-8, 8)
        self.vy    = random.uniform(-12, -3)
        self.r     = random.choice([1, 1, 2, 2, 3])
        self.alpha = random.randint(10, 45)
        self.life  = random.uniform(3, 8)
        self.max_l = self.life
        self.col   = random.choice([
            (210, 45, 75), (0, 200, 180), (100, 80, 200),
            (255, 190, 0), (80, 180, 255)])

    def update(self, dt: float) -> None:
        self.x    += self.vx * dt
        self.y    += self.vy * dt
        self.life -= dt
        if self.life <= 0:
            self._randomize()
            self.y = H + 5

    def draw(self, surf: pygame.Surface) -> None:
        a = int(self.alpha * max(0.0, self.life / self.max_l))
        if a <= 0:
            return
        s = pygame.Surface((self.r * 2 + 2, self.r * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.col, a),
                           (self.r + 1, self.r + 1), self.r)
        surf.blit(s, (int(self.x) - self.r, int(self.y) - self.r))


class _MenuDebris:
    def __init__(self) -> None:
        self._reset(True)

    def _reset(self, randomize: bool = False) -> None:
        self.x     = random.uniform(0, W)
        self.y     = random.uniform(0, H) if randomize else -4.0
        self.speed = random.uniform(8, 28)
        self.r     = random.choice([1, 1, 1, 2])
        self.alpha = random.randint(20, 55)
        self.col   = random.choice([(60, 60, 100), (40, 40, 80), (80, 80, 130)])

    def update(self, dt: float) -> None:
        self.y += self.speed * dt
        if self.y > H + 4:
            self._reset()

    def draw(self, surf: pygame.Surface) -> None:
        s = pygame.Surface((self.r * 2, self.r * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.col, self.alpha),
                           (self.r, self.r), self.r)
        surf.blit(s, (int(self.x) - self.r, int(self.y) - self.r))
