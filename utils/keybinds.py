"""
keybinds.py — Rebindable keyboard controls (two slots per action).

A module-level singleton `KEYS` is what the game reads; the Controls screen edits
it and persists it through utils.settings.  Fixed keys (ESC, F3, F10, F11, `) are
deliberately not rebindable.
"""
from __future__ import annotations
import pygame

_K = pygame
ACTIONS = ["up", "down", "left", "right", "dash", "hack",
           "weapon1", "weapon2", "weapon3", "weapon4", "weapon5", "mute"]

LABELS = {"up": "MOVE UP", "down": "MOVE DOWN", "left": "MOVE LEFT", "right": "MOVE RIGHT",
          "dash": "DASH", "hack": "HACK", "weapon1": "PLASMA BOLT", "weapon2": "VOID SPREAD",
          "weapon3": "CHAIN ZAP", "weapon4": "NULL BEAM", "weapon5": "CHAOS BOMB", "mute": "MUTE"}

DEFAULTS: dict[str, tuple] = {
    "up":      (_K.K_w, _K.K_UP),       "down":  (_K.K_s, _K.K_DOWN),
    "left":    (_K.K_a, _K.K_LEFT),     "right": (_K.K_d, _K.K_RIGHT),
    "dash":    (_K.K_LSHIFT, _K.K_RSHIFT), "hack": (_K.K_SPACE, None),
    "weapon1": (_K.K_1, None), "weapon2": (_K.K_2, None), "weapon3": (_K.K_3, None),
    "weapon4": (_K.K_4, None), "weapon5": (_K.K_5, None),
    "mute":    (_K.K_m, None),
}

# Never rebindable: they would lock the player out of menus/console/debug.
RESERVED = {_K.K_ESCAPE, _K.K_BACKQUOTE, _K.K_F3, _K.K_F10, _K.K_F11, _K.K_RETURN, _K.K_KP_ENTER}


class Keybinds:
    def __init__(self) -> None:
        self.map: dict[str, list] = {a: list(v) for a, v in DEFAULTS.items()}

    # ── queries ───────────────────────────────────────────────────────────────

    def pressed(self, keys, action: str) -> bool:
        """True if any slot of *action* is held.  `keys` is pygame.key.get_pressed()-like."""
        for k in self.map[action]:
            if k is not None and keys[k]:
                return True
        return False

    def matches(self, key: int, action: str) -> bool:
        return key in self.map[action]

    def actions_for(self, key: int) -> list[str]:
        return [a for a, ks in self.map.items() if key in ks]

    def name(self, action: str, slot: int) -> str:
        k = self.map[action][slot]
        return "—" if k is None else pygame.key.name(k).upper()

    # ── editing ───────────────────────────────────────────────────────────────

    def rebind(self, action: str, slot: int, key: int | None) -> str | None:
        """Bind *key* to (action, slot).  If the key is already bound elsewhere that
        binding is cleared (so a key never triggers two actions); returns the name of
        the action it was taken from, or None.  Raises ValueError for reserved keys."""
        if key is not None and key in RESERVED:
            raise ValueError(f"{pygame.key.name(key).upper()} is reserved")
        taken = None
        if key is not None:
            for a, ks in self.map.items():
                for i, k in enumerate(ks):
                    if k == key and not (a == action and i == slot):
                        ks[i] = None
                        taken = a
        self.map[action][slot] = key
        return taken

    def reset(self) -> None:
        self.map = {a: list(v) for a, v in DEFAULTS.items()}

    # ── persistence ───────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {a: list(ks) for a, ks in self.map.items()}

    def load(self, data: dict | None) -> None:
        """Merge saved bindings; ignore anything malformed or reserved."""
        self.reset()
        if not isinstance(data, dict):
            return
        for a in ACTIONS:
            ks = data.get(a)
            if isinstance(ks, list) and len(ks) == 2:
                clean = [k if (isinstance(k, int) and not isinstance(k, bool) and k not in RESERVED) else None
                         for k in ks]
                self.map[a] = clean


KEYS = Keybinds()
