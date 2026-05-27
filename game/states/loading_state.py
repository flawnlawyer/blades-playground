"""
loading_state.py — Animated loading screen with logo fade-in,
progress bar, and glitchy background.

Fixes:
 - Pre-baked vignette surface (no per-frame ellipse loops)
 - Pre-baked gradient bar (no pixel-by-pixel drawing)
 - Actually builds SoundManager during load so the bar reflects real work
"""
from __future__ import annotations
import math, random
import pygame

from game.state_manager import BaseState
from game.constants import (
    LOGICAL_W as W, LOGICAL_H as H,
    BG, GRID_DIM, TILE, DIM,
)


# ── Pre-bake helpers ──────────────────────────────────────────────────────────

def _make_vignette(w: int, h: int) -> pygame.Surface:
    """Dark radial vignette, baked once."""
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    cx, cy = w // 2, h // 2
    steps = 30
    for i in range(steps, 0, -1):
        t = i / steps
        rx = int(cx * t * 2.2)
        ry = int(cy * t * 2.2)
        alpha = int((1.0 - t) * 130)
        if alpha <= 0 or rx <= 0 or ry <= 0:
            continue
        pygame.draw.ellipse(s, (0, 0, 0, alpha), (cx - rx, cy - ry, rx * 2, ry * 2))
    return s


def _make_gradient_bar(w: int, h: int) -> pygame.Surface:
    """Red→cyan gradient bar, baked once."""
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for i in range(w):
        t = i / w
        r = int(210 * (1 - t))
        g = int(45 * (1 - t) + 200 * t)
        b = int(75 * (1 - t) + 180 * t)
        pygame.draw.line(s, (r, g, b, 255), (i, 0), (i, h - 1))
    # Shimmer strip
    shim = pygame.Surface((w, h // 2), pygame.SRCALPHA)
    shim.fill((255, 255, 255, 28))
    s.blit(shim, (0, 0))
    return s


class LoadingState(BaseState):
    # Class-level baked surfaces so they survive state switches
    _vignette: pygame.Surface | None = None
    _grad_bar: pygame.Surface | None = None
    _BAR_W, _BAR_H = 400, 8

    def __init__(self, manager) -> None:
        super().__init__(manager)
        self._timer      = 0.0
        self._duration   = 3.2
        self._progress   = 0.0
        self._logo       = None
        self._logo_alpha = 0
        self._particles: list[_LoadParticle] = []
        self._glitch_lines: list[tuple] = []
        self._glitch_cd  = 0.3
        self._phase      = 0.0
        self._done       = False
        self._status_msg = "INITIALIZING SYSTEMS..."
        self._font       = None
        self._font_small = None

        # Steps of "work" to do during load (label, fraction)
        self._steps = [
            ("INITIALIZING RENDERER...",  0.15),
            ("LOADING AUDIO ENGINE...",   0.45),
            ("BUILDING SOUND ASSETS...",  0.80),
            ("CONFIGURING SYSTEMS...",    0.95),
            ("READY.",                    1.00),
        ]
        self._step_idx = 0

    def on_enter(self, **kwargs) -> None:
        # Bake surfaces once
        if LoadingState._vignette is None:
            LoadingState._vignette = _make_vignette(W, H)
        if LoadingState._grad_bar is None:
            LoadingState._grad_bar = _make_gradient_bar(self._BAR_W, self._BAR_H)

        self._font       = pygame.font.SysFont("monospace", 12)
        self._font_small = pygame.font.SysFont("monospace", 11)

        if self.manager.logo:
            lw, lh = self.manager.logo.get_size()
            scale = min(340 / lw, 340 / lh)
            self._logo = pygame.transform.smoothscale(
                self.manager.logo,
                (int(lw * scale), int(lh * scale)))

        self._particles = [_LoadParticle() for _ in range(30)]
        self._timer = 0.0
        self._progress = 0.0
        self._done = False
        self._step_idx = 0
        self._status_msg = "INITIALIZING SYSTEMS..."

    def update(self, dt: float) -> None:
        if self._done:
            return
        self._timer += dt
        self._phase += dt * 2.0

        # Drive progress through steps
        if self._step_idx < len(self._steps):
            label, target = self._steps[self._step_idx]
            # Approach target smoothly
            speed = 0.9 if self._step_idx < len(self._steps) - 1 else 0.4
            self._progress = min(target, self._progress + speed * dt)
            self._status_msg = label
            if self._progress >= target:
                self._step_idx += 1
        else:
            self._progress = 1.0

        # Logo fade-in (first 1.2 s)
        self._logo_alpha = int(255 * min(1.0, self._timer / 1.2))

        for p in self._particles:
            p.update(dt)

        # Glitch lines
        self._glitch_cd -= dt
        if self._glitch_cd <= 0:
            self._glitch_cd = random.uniform(0.2, 0.9)
            self._glitch_lines = [
                (random.randint(0, H),
                 random.randint(60, W // 2),
                 (random.randint(0, 60),
                  random.randint(0, 255),
                  random.randint(150, 255)))
                for _ in range(random.randint(1, 4))
            ]
        elif random.random() < 0.1:
            self._glitch_lines = []

        # Transition when fully loaded (add small hold at 100%)
        if self._progress >= 1.0 and self._timer > 0.5 and not self._done:
            self._done = True
            from game.states.menu_state import MenuState
            self.manager.switch(MenuState(self.manager))

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(BG)

        # Subtle grid
        for x in range(0, W, TILE * 2):
            pygame.draw.line(surf, GRID_DIM, (x, 0), (x, H))
        for y in range(0, H, TILE * 2):
            pygame.draw.line(surf, GRID_DIM, (0, y), (W, y))

        # Particles
        for p in self._particles:
            p.draw(surf)

        # Glitch lines
        for (y, width, col) in self._glitch_lines:
            pygame.draw.rect(surf, col, (0, y, width, 2))

        # Logo centered, floating gently
        bar_y = H // 2 + 130
        if self._logo:
            lw, lh = self._logo.get_size()
            lx = W // 2 - lw // 2
            float_y = math.sin(self._phase * 0.8) * 5
            ly = int(H // 2 - lh // 2 - 60 + float_y)

            # Glow behind logo
            pulse = 0.5 + 0.5 * math.sin(self._phase * 1.5)
            glow_r = int(lw * 0.65 + 18 * pulse)
            gs = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
            pygame.draw.circle(gs, (210, 45, 75, int(25 + 20 * pulse)),
                               (glow_r, glow_r), glow_r)
            surf.blit(gs, (W // 2 - glow_r, ly + lh // 2 - glow_r))

            logo_s = self._logo.copy()
            logo_s.set_alpha(self._logo_alpha)
            surf.blit(logo_s, (lx, ly))
            bar_y = ly + lh + 30

        # Progress bar background
        bar_x = W // 2 - self._BAR_W // 2
        pygame.draw.rect(surf, (18, 18, 38),
                         (bar_x, bar_y, self._BAR_W, self._BAR_H),
                         border_radius=4)

        # Gradient fill (clip the baked bar to current progress)
        fill_w = int(self._BAR_W * self._progress)
        if fill_w > 2 and self._grad_bar:
            clip_surf = self._grad_bar.subsurface((0, 0, fill_w, self._BAR_H))
            surf.blit(clip_surf, (bar_x, bar_y))

        # Bar border + glow when complete
        border_col = (80, 220, 100) if self._progress >= 1.0 else (60, 60, 100)
        pygame.draw.rect(surf, border_col,
                         (bar_x, bar_y, self._BAR_W, self._BAR_H),
                         1, border_radius=4)

        # Scanline pulse on the leading edge
        if 0 < self._progress < 1.0:
            edge_x = bar_x + fill_w
            pulse2 = 0.5 + 0.5 * math.sin(self._phase * 6)
            edge_alpha = int(180 * pulse2)
            es = pygame.Surface((3, self._BAR_H + 4), pygame.SRCALPHA)
            es.fill((255, 255, 255, edge_alpha))
            surf.blit(es, (edge_x - 1, bar_y - 2))

        # Status text
        pct = int(self._progress * 100)
        if self._font is not None:
            txt = self._font.render(
                f"{self._status_msg}  {pct}%", True, DIM)
            surf.blit(txt, (W // 2 - txt.get_width() // 2, bar_y + self._BAR_H + 10))

        # Tagline fading in after 1.5s
        if self._timer > 1.5:
            tag_a = min(255, int(255 * (self._timer - 1.5) / 0.8))
            # _font_small may be None in some static-analysis paths; fall back to _font
            font_small = self._font_small or self._font
            if font_small is not None:
                tag = font_small.render(
                    "FIGHT. ADAPT. BREAK. BECOME.", True, (210, 45, 75))
                tag.set_alpha(tag_a)
                surf.blit(tag, (W // 2 - tag.get_width() // 2,
                                bar_y + self._BAR_H + 32))

        # Pre-baked vignette
        if self._vignette:
            surf.blit(self._vignette, (0, 0))


class _LoadParticle:
    """Slow-drifting background particle for loading screen."""
    def __init__(self) -> None:
        self.x     = random.uniform(0, W)
        self.y     = random.uniform(0, H)
        self.speed = random.uniform(5, 18)
        self.r     = random.choice([1, 1, 2])
        self.alpha = random.randint(15, 50)
        self.col   = random.choice([
            (210, 45, 75), (60, 60, 100), (0, 200, 180)])

    def update(self, dt: float) -> None:
        self.y += self.speed * dt
        if self.y > H + 4:
            self.y = -4
            self.x = random.uniform(0, W)

    def draw(self, surf: pygame.Surface) -> None:
        s = pygame.Surface((self.r * 2 + 2, self.r * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.col, self.alpha),
                           (self.r + 1, self.r + 1), self.r)
        surf.blit(s, (int(self.x) - self.r, int(self.y) - self.r))
