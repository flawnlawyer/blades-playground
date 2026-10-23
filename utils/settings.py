"""
settings.py — Player settings: defaults, validation, and applying them.

Stored inside the existing save file ("settings").  Everything is clamped/validated
on load so a hand-edited or corrupt file can never break the game.
"""
from __future__ import annotations

from utils import data_manager
from utils.keybinds import KEYS

BLOOM_LEVELS = [("OFF", 0.0), ("LOW", 0.30), ("MEDIUM", 0.55), ("HIGH", 0.90)]

DEFAULTS: dict = {
    "volume": 0.55, "muted": False, "music": True,
    "bloom": "MEDIUM", "vignette": 0.55, "shake": 1.0, "hitstop": True,
    "gamepad": True, "deadzone": 0.25, "keybinds": {},
}


def _clamp(v, lo, hi, default):
    return max(lo, min(hi, float(v))) if isinstance(v, (int, float)) and not isinstance(v, bool) else default


def normalise(raw) -> dict:
    s = dict(DEFAULTS); s["keybinds"] = {}
    if not isinstance(raw, dict):
        return s
    s["volume"]   = _clamp(raw.get("volume"),   0.0, 1.0, DEFAULTS["volume"])
    s["vignette"] = _clamp(raw.get("vignette"), 0.0, 1.0, DEFAULTS["vignette"])
    s["shake"]    = _clamp(raw.get("shake"),    0.0, 1.0, DEFAULTS["shake"])
    s["deadzone"] = _clamp(raw.get("deadzone"), 0.05, 0.60, DEFAULTS["deadzone"])
    for k in ("muted", "music", "hitstop", "gamepad"):
        if isinstance(raw.get(k), bool):
            s[k] = raw[k]
    if raw.get("bloom") in dict(BLOOM_LEVELS):
        s["bloom"] = raw["bloom"]
    if isinstance(raw.get("keybinds"), dict):
        s["keybinds"] = raw["keybinds"]
    return s


def load() -> dict:
    return normalise(data_manager.load_settings())


def save(s: dict) -> None:
    data_manager.save_settings(s)


def apply_global(manager, s: dict) -> None:
    """Things that live outside a run: keybinds and the gamepad."""
    KEYS.load(s["keybinds"])
    manager.gamepad.enabled  = s["gamepad"]
    manager.gamepad.deadzone = s["deadzone"]


def apply_to_game(game, s: dict) -> None:
    """Per-run presentation settings (never affects difficulty or scoring)."""
    r = game.renderer
    strength = dict(BLOOM_LEVELS)[s["bloom"]]
    r.bloom_enabled, r.bloom_strength = strength > 0, strength
    if abs(s["vignette"] - r.vignette) > 1e-6:
        r.set_vignette(s["vignette"])
    game.shake_scale      = s["shake"]
    game.hitstop_enabled  = s["hitstop"]
    game.music.disabled   = not s["music"]
    game.audio.set_volume(s["volume"])
    if s["muted"] and not game.audio.muted:
        game.audio.toggle_mute()
