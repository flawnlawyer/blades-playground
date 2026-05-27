"""
play_state.py — Wraps the existing Game class as a state.
Handles ESC → PauseState, game-over → GameOverState.

Fixes:
 - Stop audio drone on exit so it doesn't bleed into menus
 - Properly create fresh Game on restart (not guarded by _game is None)
"""
from __future__ import annotations
import pygame

from game.state_manager import BaseState


class PlayState(BaseState):
    def __init__(self, manager) -> None:
        super().__init__(manager)
        self._game = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_enter(self, **kwargs) -> None:
        # Always create a fresh game on enter (handles restart)
        if self._game is None:
            from game.game import Game
            self._game = Game(self.manager)
        # Re-start drone in case we're returning from pause
        if self._game.audio and not self._game.audio.muted:
            self._game.audio.update_drone(
                self._game.player.energy / self._game.player.max_energy,
                self._game.player.chaos_mode)
        pygame.mouse.set_visible(False)

    def on_exit(self) -> None:
        # Always stop the ambient drone so it doesn't bleed into menus
        if self._game and self._game.audio:
            self._game.audio.stop_drone()
        pygame.mouse.set_visible(True)

    # ── Events ────────────────────────────────────────────────────────────────

    def handle_events(self, events: list) -> None:
        if self._game is None:
            return
        game = self._game

        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if game.game_over:
                        from game.states.menu_state import MenuState
                        self.manager.replace_all(MenuState(self.manager))
                    else:
                        from game.states.pause_state import PauseState
                        pygame.mouse.set_visible(True)
                        self.manager.push(PauseState(self.manager, game))
                    return

                if event.key == pygame.K_SPACE and not game.game_over:
                    game._do_hack()

                if event.key == pygame.K_m:
                    game.audio.toggle_mute()

                if event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                    if not game.game_over:
                        if game.player.trigger_dash(pygame.key.get_pressed()):
                            game.audio.dash()

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, dt: float) -> None:
        if self._game is None:
            return

        # Translate real mouse → logical coordinates
        # Use setattr to avoid strict type-checking on Game._logical_mouse
        setattr(self._game, "_logical_mouse", self.manager.mouse_to_logical())
        if not self._game.game_over:
            self._game.update(dt)

        # Transition to game-over screen exactly once
        if self._game.game_over and not self._game._gameover_handled:
            self._game._gameover_handled = True
            from game.states.gameover_state import GameOverState
            pygame.mouse.set_visible(True)
            self.manager.push(GameOverState(
                self.manager,
                score=self._game.score,
                wave=self._game.wave_mgr.wave,
                time=self._game.run_time,
                game=self._game))

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self, surf: pygame.Surface) -> None:
        if self._game:
            self._game.draw(surf)
