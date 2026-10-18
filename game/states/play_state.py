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
    def __init__(self, manager, daily: bool = False) -> None:
        super().__init__(manager)
        self._game = None
        self.daily = daily

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_enter(self, **kwargs) -> None:
        # Always create a fresh game on enter (handles restart)
        if self._game is None:
            from game.game import Game
            from utils import daily as _daily
            seed = _daily.seed_for(_daily.today()) if self.daily else None
            self._game = Game(self.manager, seed=seed)
            if self.daily:
                self._game.daily_date = _daily.today()
            self._game.stress_target = getattr(self.manager, "stress", 0)
        self._game.music.start()                    # idempotent; keeps playing through pause / perk screens
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
            self._game.music.stop()
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

                if event.key == pygame.K_F3:
                    game.show_debug = not game.show_debug

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
        clk = self.manager.clock
        self._game.debug_info = [f"FPS {clk.get_fps():5.1f}   frame {clk.get_time():3d} ms"]
        if not self._game.game_over:
            self._game.update(dt)

        # Wave cleared -> offer a perk (game is frozen while the picker is open)
        if self._game.perk_pending and not self._game.game_over:
            self._game.perk_pending = False
            from game.states.perk_state import PerkState
            self.manager.push(PerkState(self.manager, self._game))
            return

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
