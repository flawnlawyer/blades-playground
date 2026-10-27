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
from utils.keybinds import KEYS


class PlayState(BaseState):
    wants_raw_pad = True        # in-game the pad's A/X/LB/RB are actions, not menu keys

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
            from utils import settings as _settings
            _settings.apply_to_game(self._game, _settings.load())     # saved volume, bloom, shake, ...
            if self.daily:
                self._game.daily_date = _daily.today()
            elif not self._game.stress_target:                # permanent upgrades: normal runs only
                from utils import meta as _meta, data_manager as _dm
                _meta.apply_to_game(self._game, _dm.load_meta())
            self._game.stress_target = getattr(self.manager, "stress", 0)
        self._game.music.start()                    # idempotent; keeps playing through pause / perk screens
        self.manager.active_game = self._game       # lets console commands reach this run
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
        if getattr(self.manager, "active_game", None) is self._game:
            self.manager.active_game = None
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

                if KEYS.matches(event.key, "hack") and not game.game_over:
                    game._do_hack()

                if KEYS.matches(event.key, "mute"):
                    game.audio.toggle_mute()

                if event.key == pygame.K_F3:
                    game.show_debug = not game.show_debug

                if KEYS.matches(event.key, "dash"):
                    if not game.game_over:
                        if game.player.trigger_dash(pygame.key.get_pressed()):
                            game.audio.dash()

            elif event.type == getattr(pygame, "CONTROLLERBUTTONDOWN", -1) and not game.game_over:
                self._pad_button(event.button, game)

    def _pad_button(self, button: int, game) -> None:
        """Gamepad actions: A dash, X hack, LB/RB (or D-pad left/right) prev/next weapon."""
        P = pygame
        if button == getattr(P, "CONTROLLER_BUTTON_A", -2):
            if game.player.trigger_dash(P.key.get_pressed()):
                game.audio.dash()
        elif button == getattr(P, "CONTROLLER_BUTTON_X", -2):
            game._do_hack()
        elif button in (getattr(P, "CONTROLLER_BUTTON_RIGHTSHOULDER", -2),
                        getattr(P, "CONTROLLER_BUTTON_DPAD_RIGHT", -2)):
            game.player.weapon_index = (game.player.weapon_index + 1) % 5
        elif button in (getattr(P, "CONTROLLER_BUTTON_LEFTSHOULDER", -2),
                        getattr(P, "CONTROLLER_BUTTON_DPAD_LEFT", -2)):
            game.player.weapon_index = (game.player.weapon_index - 1) % 5

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, dt: float) -> None:
        if self._game is None:
            return

        # Translate real mouse → logical coordinates
        # Use setattr to avoid strict type-checking on Game._logical_mouse
        pad = getattr(self.manager, "gamepad", None)
        if pad is None or not pad.aiming:
            setattr(self._game, "_logical_mouse", self.manager.mouse_to_logical())
        player = self._game.player
        if pad is not None and pad.connected:
            player.analog = pad.move_vector()
            av = pad.aim_vector()
            if av.length_squared() > 0.09:                 # right stick takes over aiming
                pad.aiming = True
                setattr(self._game, "_logical_mouse",
                        (max(0, min(1280, player.pos.x + av.x * 240)),
                         max(0, min(720,  player.pos.y + av.y * 240))))
            self._game.pad_fire = pad.fire()
        else:
            player.analog = pygame.Vector2()
            self._game.pad_fire = False
        clk = self.manager.clock
        self._game.debug_info = [f"FPS {clk.get_fps():5.1f}   frame {clk.get_time():3d} ms"]
        if not self._game.game_over and not self.manager.console.open:     # console pauses the run
            ts = max(0.1, min(5.0, self._game.time_scale))
            self._game.update(min(dt * ts, 0.1))

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
