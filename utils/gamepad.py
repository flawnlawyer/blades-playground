"""
gamepad.py — Game-controller input via SDL's standardised GameController API
(Xbox / PlayStation / Switch pads all report the same layout).

Everything here degrades to a no-op when no pad is connected or the API is
unavailable, so the keyboard+mouse game never depends on it.

Layout:  left stick move · right stick aim · RT fire · A dash · X hack ·
         LB / RB previous / next weapon · Start pause · D-pad + A/B menus.
"""
from __future__ import annotations
import pygame

DEADZONE = 0.25


def _ax(name: str):
    return getattr(pygame, name, None)


class Gamepad:
    def __init__(self) -> None:
        self.ctrl      = None
        self.enabled   = True
        self.deadzone  = DEADZONE
        self.aiming    = False          # True while the right stick (not the mouse) is aiming
        self._ctl      = None
        try:
            from pygame._sdl2 import controller
            self._ctl = controller
            controller.init()
            self.open_first()
        except Exception:
            self._ctl = None

    # ── device management ────────────────────────────────────────────────────

    def open_first(self) -> None:
        self.ctrl = None
        if self._ctl is None:
            return
        try:
            for i in range(self._ctl.get_count()):
                if self._ctl.is_controller(i):
                    self.ctrl = self._ctl.Controller(i)
                    return
        except Exception:
            self.ctrl = None

    @property
    def connected(self) -> bool:
        return self.enabled and self.ctrl is not None

    def handle_device_event(self, ev) -> None:
        added, removed = _ax("CONTROLLERDEVICEADDED"), _ax("CONTROLLERDEVICEREMOVED")
        if added is not None and ev.type == added and self.ctrl is None:
            self.open_first()
        elif removed is not None and ev.type == removed:
            self.open_first()

    # ── analog reads ─────────────────────────────────────────────────────────

    def _axis(self, axis_name: str) -> float:
        a = _ax(axis_name)
        if not self.connected or a is None:
            return 0.0
        try:
            return self.ctrl.get_axis(a) / 32767.0
        except Exception:
            return 0.0

    def _stick(self, x_name: str, y_name: str) -> pygame.Vector2:
        v = pygame.Vector2(self._axis(x_name), self._axis(y_name))
        mag = v.length()
        if mag < self.deadzone:
            return pygame.Vector2()
        scaled = min(1.0, (mag - self.deadzone) / (1.0 - self.deadzone))   # rescale past the deadzone
        return v / mag * scaled

    def move_vector(self) -> pygame.Vector2:
        return self._stick("CONTROLLER_AXIS_LEFTX", "CONTROLLER_AXIS_LEFTY")

    def aim_vector(self) -> pygame.Vector2:
        return self._stick("CONTROLLER_AXIS_RIGHTX", "CONTROLLER_AXIS_RIGHTY")

    def fire(self) -> bool:
        return self._axis("CONTROLLER_AXIS_TRIGGERRIGHT") > 0.3

    def button(self, name: str) -> bool:
        b = _ax(name)
        if not self.connected or b is None:
            return False
        try:
            return bool(self.ctrl.get_button(b))
        except Exception:
            return False

    def rumble(self, strength: float = 0.6, ms: int = 120) -> None:
        if not self.connected:
            return
        try:
            self.ctrl.rumble(strength, strength, ms)
        except Exception:
            pass


# Button -> menu key translation (so every existing menu works with a pad, untouched)
def menu_key_for_button(button: int, in_game: bool) -> int | None:
    m = {
        _ax("CONTROLLER_BUTTON_DPAD_UP"):    pygame.K_UP,
        _ax("CONTROLLER_BUTTON_DPAD_DOWN"):  pygame.K_DOWN,
        _ax("CONTROLLER_BUTTON_DPAD_LEFT"):  pygame.K_LEFT,
        _ax("CONTROLLER_BUTTON_DPAD_RIGHT"): pygame.K_RIGHT,
        _ax("CONTROLLER_BUTTON_START"):      pygame.K_ESCAPE,
    }
    if not in_game:                          # in-game, A/B are dash/hack — not menu keys
        m[_ax("CONTROLLER_BUTTON_A")] = pygame.K_RETURN
        m[_ax("CONTROLLER_BUTTON_B")] = pygame.K_ESCAPE
    return m.get(button)
