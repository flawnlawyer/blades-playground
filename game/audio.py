"""
audio.py — Procedural SFX engine for The Blade's Playground.

All sounds are synthesised at runtime with NumPy + pygame.mixer.
No external audio files required.
"""

from __future__ import annotations
import math, random
import numpy as np
import pygame

from game.constants import MASTER_VOLUME

SR = 44100   # sample rate


# ── Low-level synthesis helpers ───────────────────────────────────────────────

def _make(samples: np.ndarray) -> pygame.mixer.Sound:
    """Float32 array [-1, 1] → pygame.mixer.Sound (stereo 16-bit)."""
    s = np.clip(samples, -1.0, 1.0)
    s = (s * 32767).astype(np.int16)
    stereo = np.ascontiguousarray(np.column_stack([s, s]))
    return pygame.sndarray.make_sound(stereo)


def _env(sig: np.ndarray, attack: float = 0.01, release: float = 0.05) -> np.ndarray:
    n = len(sig)
    a = max(1, int(SR * attack))
    r = max(1, int(SR * release))
    env = np.ones(n, dtype=np.float32)
    if a < n:
        env[:a] = np.linspace(0, 1, a)
    if r < n:
        env[-r:] = np.linspace(1, 0, r)
    return sig * env


def _sine(freq: float, dur: float, amp: float = 1.0) -> np.ndarray:
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    return np.sin(2 * np.pi * freq * t, dtype=np.float32) * amp


def _noise(dur: float, amp: float = 1.0) -> np.ndarray:
    return np.random.uniform(-amp, amp, int(SR * dur)).astype(np.float32)


def _sweep(f0: float, f1: float, dur: float, amp: float = 1.0) -> np.ndarray:
    """Linear frequency sweep (chirp)."""
    n   = int(SR * dur)
    freq = np.linspace(f0, f1, n, dtype=np.float64)
    phase = np.cumsum(freq) / SR
    return (np.sin(2 * np.pi * phase) * amp).astype(np.float32)


# ── Sound builders ────────────────────────────────────────────────────────────

def _build_hack() -> pygame.mixer.Sound:
    """Sharp digital chirp: 300 → 900 Hz + noise grain."""
    dur = 0.12
    sig = _sweep(300, 900, dur, 0.55) + _noise(dur, 0.08)
    return _make(_env(sig, 0.004, 0.04))


def _build_fragment_collect() -> pygame.mixer.Sound:
    """Ascending arpeggio: A4 → C#5 → E5, each 80 ms."""
    notes  = [440.0, 554.37, 659.26]
    parts: list[np.ndarray] = []
    gap    = np.zeros(int(SR * 0.02), dtype=np.float32)
    for f in notes:
        s = _sine(f, 0.08, 0.65)
        parts.append(_env(s, 0.005, 0.028))
        parts.append(gap)
    return _make(np.concatenate(parts))


def _build_enemy_stun() -> pygame.mixer.Sound:
    """Descending zap: 800 → 200 Hz + noise burst."""
    dur = 0.18
    sig = _sweep(800, 200, dur, 0.50) + _noise(dur, 0.20)
    return _make(_env(sig, 0.002, 0.06))


def _build_chaos_activate() -> pygame.mixer.Sound:
    """Power surge: rising harmonic stack."""
    dur = 0.42
    sig = _sweep(100, 800, dur, 0.45)
    sig += _sweep(200, 1600, dur, 0.22)
    sig += _noise(dur, 0.05)
    return _make(_env(sig, 0.01, 0.10))


def _build_player_hit() -> pygame.mixer.Sound:
    """Low-impact thud: 80 Hz sine + noise swell."""
    dur = 0.22
    sig = _sine(80, dur, 0.75) + _noise(dur, 0.30)
    return _make(_env(sig, 0.002, 0.09))


def _build_meh_destroy() -> pygame.mixer.Sound:
    """Short crunch-pop: noise + low sine click."""
    dur = 0.10
    sig = _noise(dur, 0.85) + _sine(200, dur, 0.28)
    return _make(_env(sig, 0.001, 0.04))


def _build_meh_hack() -> pygame.mixer.Sound:
    """Quick beep: two short tones (100 ms total)."""
    s1 = _env(_sine(520, 0.04, 0.55), 0.003, 0.01)
    s2 = _env(_sine(660, 0.06, 0.55), 0.003, 0.02)
    gap = np.zeros(int(SR * 0.01), dtype=np.float32)
    return _make(np.concatenate([s1, gap, s2]))


def _build_game_over() -> pygame.mixer.Sound:
    """Descending glitch drone: 400 → 60 Hz over 0.8 s."""
    dur = 0.80
    sig = _sweep(400, 60, dur, 0.60) + _noise(dur, 0.14)
    return _make(_env(sig, 0.01, 0.15))


def _build_chaos_end() -> pygame.mixer.Sound:
    """Short descending chime signalling chaos timeout."""
    notes = [660.0, 440.0, 260.0]
    parts: list[np.ndarray] = []
    for f in notes:
        s = _sine(f, 0.07, 0.50)
        parts.append(_env(s, 0.004, 0.025))
    return _make(np.concatenate(parts))


# ── SoundManager ──────────────────────────────────────────────────────────────

class SoundManager:
    """Initialise mixer once, build all sounds, expose play_* helpers."""

    def __init__(self, volume: float = MASTER_VOLUME) -> None:
        if not pygame.mixer.get_init():
            pygame.mixer.pre_init(SR, -16, 2, 512)
            pygame.mixer.init()
        self.volume  = volume
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        self._muted  = False
        self._build_all()

    def _build_all(self) -> None:
        builders = {
            "hack":             _build_hack,
            "fragment_collect": _build_fragment_collect,
            "enemy_stun":       _build_enemy_stun,
            "chaos_activate":   _build_chaos_activate,
            "chaos_end":        _build_chaos_end,
            "player_hit":       _build_player_hit,
            "meh_destroy":      _build_meh_destroy,
            "meh_hack":         _build_meh_hack,
            "game_over":        _build_game_over,
        }
        for name, fn in builders.items():
            try:
                snd = fn()
                snd.set_volume(self.volume)
                self._sounds[name] = snd
            except Exception as exc:
                print(f"[audio] Warning: could not build sound '{name}': {exc}")

    # ── Public interface ──────────────────────────────────────────────────────

    def play(self, name: str) -> None:
        if self._muted:
            return
        snd = self._sounds.get(name)
        if snd:
            snd.play()

    def toggle_mute(self) -> bool:
        self._muted = not self._muted
        return self._muted

    @property
    def muted(self) -> bool:
        return self._muted

    # Convenience shortcuts ───────────────────────────────────────────────────
    def hack(self)             -> None: self.play("hack")
    def meh_hack(self)         -> None: self.play("meh_hack")
    def fragment_collect(self) -> None: self.play("fragment_collect")
    def enemy_stun(self)       -> None: self.play("enemy_stun")
    def chaos_activate(self)   -> None: self.play("chaos_activate")
    def chaos_end(self)        -> None: self.play("chaos_end")
    def player_hit(self)       -> None: self.play("player_hit")
    def meh_destroy(self)      -> None: self.play("meh_destroy")
    def game_over(self)        -> None: self.play("game_over")
