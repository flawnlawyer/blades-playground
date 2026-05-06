"""
state_manager.py — Pushdown-automaton state machine with fade transitions.

Usage:
    manager = StateManager(screen)
    manager.push(MenuState(manager))
    manager.run()
"""
from __future__ import annotations
import pygame


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
            dt = min(self.clock.tick(60) / 1000.0, 0.05)

            events = pygame.event.get()
            for ev in events:
                if ev.type == pygame.QUIT:
                    self._quitting = True

            if self.current and not self.transition.active:
                self.current.handle_events(events)
                self.current.update(dt)

            if self.current:
                self.current.draw(self.screen)

            self.transition.update(dt)
            self.transition.draw(self.screen)

            pygame.display.flip()
