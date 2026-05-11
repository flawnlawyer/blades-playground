"""
state_manager.py — Pushdown-automaton state machine with fade transitions,
logical-resolution scaling, fullscreen toggle, and letterboxed rendering.

All states render to a fixed 1280×720 logical surface.  The manager scales
that surface to fit whatever window size the user has chosen, adding
black letterbox bars as needed.

Usage:
    manager = StateManager(screen)
    manager.push(LoadingState(manager))
    manager.run()
"""
from __future__ import annotations
import pygame

from game.constants import LOGICAL_W, LOGICAL_H, MIN_W, MIN_H, FPS


class BaseState:
    """All game states inherit from this interface."""

    def __init__(self, manager: StateManager) -> None:
        self.manager = manager

    def on_enter(self, **kwargs) -> None:  pass
    def on_exit(self)            -> None:  pass
    def handle_events(self, events: list) -> None: pass
    def update(self, dt: float)  -> None:  pass
    def draw(self, surf: pygame.Surface) -> None: pass


# ── Fade transition ────────────────────────────────────────────────────────────

class FadeTransition:
    def __init__(self, duration: float = 0.35) -> None:
        self.duration  = duration
        self._timer    = 0.0
        self._phase    = "idle"   # idle | out | in
        self._callback = None
        self._surf     = None

    def start(self, callback) -> None:
        self._timer    = 0.0
        self._phase    = "out"
        self._callback = callback

    def update(self, dt: float) -> None:
        if self._phase == "idle":
            return
        self._timer += dt
        if self._phase == "out" and self._timer >= self.duration:
            if self._callback:
                self._callback()
                self._callback = None
            self._phase = "in"
            self._timer = 0.0
        elif self._phase == "in" and self._timer >= self.duration:
            self._phase = "idle"

    def draw(self, surf: pygame.Surface) -> None:
        if self._phase == "idle":
            return
        t = min(1.0, self._timer / self.duration)
        a = int(255 * t) if self._phase == "out" else int(255 * (1.0 - t))
        if a > 0:
            ov = pygame.Surface(surf.get_size())
            ov.fill((0, 0, 0))
            ov.set_alpha(a)
            surf.blit(ov, (0, 0))

    @property
    def active(self) -> bool:
        return self._phase != "idle"


# ── StateManager ──────────────────────────────────────────────────────────────

class StateManager:
    def __init__(self, screen: pygame.Surface) -> None:
        self.screen     = screen
        self.clock      = pygame.time.Clock()
        self._stack: list[BaseState] = []
        self.transition = FadeTransition(0.30)
        self._quitting  = False

        # Logical rendering surface (fixed internal resolution)
        self.logical_surface = pygame.Surface(
            (LOGICAL_W, LOGICAL_H), pygame.SRCALPHA)

        # Fullscreen state
        self._fullscreen   = False
        self._windowed_size = (screen.get_width(), screen.get_height())

        # Shared resources
        self.logo: pygame.Surface | None = None
        self.audio = None   # set by main.py after construction

        # Scaling cache
        self._update_scaling()

    # ── Scaling helpers ───────────────────────────────────────────────────────

    def _update_scaling(self) -> None:
        """Recalculate the scale factor and letterbox offsets."""
        sw, sh = self.screen.get_size()
        scale_x = sw / LOGICAL_W
        scale_y = sh / LOGICAL_H
        self._scale = min(scale_x, scale_y)
        scaled_w = int(LOGICAL_W * self._scale)
        scaled_h = int(LOGICAL_H * self._scale)
        self._offset_x = (sw - scaled_w) // 2
        self._offset_y = (sh - scaled_h) // 2
        self._scaled_size = (scaled_w, scaled_h)

    def mouse_to_logical(self, real_pos: tuple = None) -> tuple[int, int]:
        """Convert real screen mouse position → logical coordinates."""
        if real_pos is None:
            real_pos = pygame.mouse.get_pos()
        rx, ry = real_pos
        lx = (rx - self._offset_x) / self._scale
        ly = (ry - self._offset_y) / self._scale
        # Clamp to logical bounds
        lx = max(0, min(LOGICAL_W, int(lx)))
        ly = max(0, min(LOGICAL_H, int(ly)))
        return (lx, ly)

    def scale_and_blit(self) -> None:
        """Scale the logical surface to the real screen with letterboxing."""
        self.screen.fill((0, 0, 0))
        scaled = pygame.transform.smoothscale(
            self.logical_surface, self._scaled_size)
        self.screen.blit(scaled, (self._offset_x, self._offset_y))

    # ── Fullscreen toggle ─────────────────────────────────────────────────────

    def toggle_fullscreen(self) -> None:
        if self._fullscreen:
            # Restore windowed
            self.screen = pygame.display.set_mode(
                self._windowed_size, pygame.RESIZABLE)
            self._fullscreen = False
        else:
            # Save current windowed size, go fullscreen
            self._windowed_size = (
                self.screen.get_width(), self.screen.get_height())
            self.screen = pygame.display.set_mode(
                (0, 0), pygame.FULLSCREEN)
            self._fullscreen = True
        self._update_scaling()

    # ── Stack operations ──────────────────────────────────────────────────────

    def push(self, state: BaseState, **kwargs) -> None:
        def do():
            self._stack.append(state)
            state.on_enter(**kwargs)
        if self._stack:
            self.transition.start(do)
        else:
            do()

    def pop(self, **kwargs) -> None:
        def do():
            if self._stack:
                self._stack[-1].on_exit()
                self._stack.pop()
            if self._stack:
                self._stack[-1].on_enter(**kwargs)
        self.transition.start(do)

    def switch(self, state: BaseState, **kwargs) -> None:
        def do():
            if self._stack:
                self._stack[-1].on_exit()
                self._stack.pop()
            self._stack.append(state)
            state.on_enter(**kwargs)
        self.transition.start(do)

    def replace_all(self, state: BaseState, **kwargs) -> None:
        """Clear the entire stack and push a fresh state."""
        def do():
            for s in reversed(self._stack):
                s.on_exit()
            self._stack.clear()
            self._stack.append(state)
            state.on_enter(**kwargs)
        self.transition.start(do)

    def quit(self) -> None:
        self._quitting = True

    @property
    def current(self) -> BaseState | None:
        return self._stack[-1] if self._stack else None

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        while self._stack and not self._quitting:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)

            events = pygame.event.get()
            for ev in events:
                if ev.type == pygame.QUIT:
                    self._quitting = True
                elif ev.type == pygame.VIDEORESIZE:
                    if not self._fullscreen:
                        w = max(MIN_W, ev.w)
                        h = max(MIN_H, ev.h)
                        self.screen = pygame.display.set_mode(
                            (w, h), pygame.RESIZABLE)
                        self._update_scaling()
                elif ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_F11:
                        self.toggle_fullscreen()

            if self.current and not self.transition.active:
                self.current.handle_events(events)
                self.current.update(dt)

            # Clear logical surface and let the current state draw
            self.logical_surface.fill((0, 0, 0, 0))
            if self.current:
                self.current.draw(self.logical_surface)

            # Draw transition fade on top of logical surface
            self.transition.update(dt)
            self.transition.draw(self.logical_surface)

            # Scale to real screen
            self.scale_and_blit()
            pygame.display.flip()
