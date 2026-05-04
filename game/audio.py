"""
audio.py — Procedural SFX + ambient drone engine.
All sounds synthesised at runtime with NumPy. Zero audio files.
"""
from __future__ import annotations
import math, random
import numpy as np
import pygame

from game.constants import MASTER_VOLUME

SR = 44_100   # sample rate


# ── Low-level synthesis helpers ───────────────────────────────────────────────

def _make(samples: np.ndarray) -> pygame.mixer.Sound:
    s = np.clip(samples, -1.0, 1.0)
    s = (s * 32767).astype(np.int16)
    stereo = np.ascontiguousarray(np.column_stack([s, s]))
    return pygame.sndarray.make_sound(stereo)


def _env(sig: np.ndarray, attack: float = 0.01, release: float = 0.05) -> np.ndarray:
    n = len(sig)
    a = max(1, int(SR * attack))
    r = max(1, int(SR * release))
    env = np.ones(n, dtype=np.float32)
    if a < n: env[:a]  = np.linspace(0, 1, a)
    if r < n: env[-r:] = np.linspace(1, 0, r)
    return sig * env


def _sine(freq: float, dur: float, amp: float = 1.0) -> np.ndarray:
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    return (np.sin(2 * np.pi * freq * t) * amp).astype(np.float32)


def _noise(dur: float, amp: float = 1.0) -> np.ndarray:
    return np.random.uniform(-amp, amp, int(SR * dur)).astype(np.float32)


def _sweep(f0: float, f1: float, dur: float, amp: float = 1.0) -> np.ndarray:
    n    = int(SR * dur)
    freq = np.linspace(f0, f1, n, dtype=np.float64)
    phase = np.cumsum(freq) / SR
    return (np.sin(2 * np.pi * phase) * amp).astype(np.float32)


# ── Sound builders ────────────────────────────────────────────────────────────

def _build_hack():
    dur = 0.12
    return _make(_env(_sweep(300, 900, dur, 0.55) + _noise(dur, 0.08), 0.004, 0.04))

def _build_fragment_collect():
    notes = [440.0, 554.37, 659.26]
    gap   = np.zeros(int(SR * 0.02), dtype=np.float32)
    parts = []
    for f in notes:
        parts.append(_env(_sine(f, 0.08, 0.65), 0.005, 0.028))
        parts.append(gap)
    return _make(np.concatenate(parts))

def _build_enemy_stun():
    dur = 0.18
    return _make(_env(_sweep(800, 200, dur, 0.50) + _noise(dur, 0.20), 0.002, 0.06))

def _build_chaos_activate():
    dur = 0.42
    sig = _sweep(100, 800, dur, 0.45) + _sweep(200, 1600, dur, 0.22) + _noise(dur, 0.05)
    return _make(_env(sig, 0.01, 0.10))

def _build_player_hit():
    dur = 0.22
    return _make(_env(_sine(80, dur, 0.75) + _noise(dur, 0.30), 0.002, 0.09))

def _build_meh_destroy():
    dur = 0.10
    return _make(_env(_noise(dur, 0.85) + _sine(200, dur, 0.28), 0.001, 0.04))

def _build_meh_hack():
    s1 = _env(_sine(520, 0.04, 0.55), 0.003, 0.01)
    s2 = _env(_sine(660, 0.06, 0.55), 0.003, 0.02)
    return _make(np.concatenate([s1, np.zeros(int(SR * 0.01), np.float32), s2]))

def _build_game_over():
    dur = 0.80
    return _make(_env(_sweep(400, 60, dur, 0.60) + _noise(dur, 0.14), 0.01, 0.15))

def _build_chaos_end():
    notes = [660.0, 440.0, 260.0]
    return _make(np.concatenate([_env(_sine(f, 0.07, 0.50), 0.004, 0.025) for f in notes]))

# ── New sounds ────────────────────────────────────────────────────────────────

def _build_dash():
    """Short whoosh — 50→180 Hz over 60 ms."""
    dur = 0.06
    return _make(_env(_sweep(50, 180, dur, 0.70) + _noise(dur, 0.12), 0.002, 0.02))

def _build_plasma_shoot():
    dur = 0.07
    return _make(_env(_sweep(600, 1200, dur, 0.40) + _noise(dur, 0.06), 0.002, 0.03))

def _build_spread_shoot():
    dur = 0.10
    sig = np.concatenate([_sweep(400, 800, 0.05, 0.30)] * 5)[:int(SR * dur)]
    return _make(_env(sig + _noise(dur, 0.10), 0.001, 0.04))

def _build_chain_zap():
    dur = 0.20
    sig = _sweep(900, 300, dur, 0.55) + _noise(dur, 0.25)
    for _ in range(3):
        offset = random.randint(0, len(sig) - int(SR * 0.05))
        sig[offset:offset + int(SR * 0.04)] += _noise(0.04, 0.30)
    return _make(_env(sig, 0.002, 0.07))

def _build_beam_hum():
    """Short loopable beam hum — 220 Hz buzz."""
    dur = 0.15
    sig = _sine(220, dur, 0.35) + _sine(440, dur, 0.15) + _noise(dur, 0.05)
    return _make(_env(sig, 0.01, 0.05))

def _build_bomb_launch():
    dur = 0.14
    return _make(_env(_sweep(200, 120, dur, 0.55) + _noise(dur, 0.10), 0.003, 0.06))

def _build_bomb_explode():
    dur = 0.55
    sig = _noise(dur, 0.90) + _sweep(300, 40, dur, 0.60) + _sine(80, dur, 0.50)
    return _make(_env(sig, 0.001, 0.18))

def _build_wave_start():
    """Dramatic low-freq rumble + ascending tone."""
    dur = 0.60
    sig = _sweep(60, 300, dur, 0.50) + _noise(dur, 0.08) + _sine(120, dur, 0.35)
    return _make(_env(sig, 0.01, 0.20))

def _build_boss_spawn():
    """Long 800→30 Hz descent with harmonics."""
    dur = 1.0
    sig = _sweep(800, 30, dur, 0.65) + _sweep(1600, 60, dur, 0.30) + _noise(dur, 0.12)
    return _make(_env(sig, 0.005, 0.25))

def _build_boss_hit():
    """Metallic clank."""
    dur = 0.18
    return _make(_env(_sine(320, dur, 0.60) + _noise(dur, 0.40), 0.001, 0.08))

def _build_level_up():
    """Ascending major chord: C5 E5 G5."""
    notes = [523.25, 659.26, 783.99]
    parts = [_env(_sine(f, 0.10, 0.55), 0.005, 0.04) for f in notes]
    return _make(np.concatenate(parts))


# ── Ambient drone (generative loop) ───────────────────────────────────────────

def _build_ambient_drone(base_hz: float = 60.0, chaos: bool = False) -> pygame.mixer.Sound:
    """
    Generative drone that changes pitch based on energy level.
    base_hz: 60 (low energy) → 110 (full energy → chaos)
    """
    dur = 2.0   # 2-second loop
    sig = _sine(base_hz, dur, 0.25)
    sig += _sine(base_hz * 1.5, dur, 0.08)
    if chaos:
        sig += _sine(base_hz * 3, dur, 0.12)
        sig += _noise(dur, 0.04)
    return _make(sig)


# ── SoundManager ──────────────────────────────────────────────────────────────

class SoundManager:
    def __init__(self, volume: float = MASTER_VOLUME) -> None:
        if not pygame.mixer.get_init():
            pygame.mixer.pre_init(SR, -16, 2, 512)
            pygame.mixer.init()
        self.volume  = volume
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        self._muted  = False
        self._drone_channel: pygame.mixer.Channel | None = None
        self._drone_hz   = 60.0
        self._chaos_drone = False
        self._build_all()
        self._start_drone()

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
            "dash":             _build_dash,
            "plasma_shoot":     _build_plasma_shoot,
            "spread_shoot":     _build_spread_shoot,
            "chain_zap":        _build_chain_zap,
            "beam_hum":         _build_beam_hum,
            "bomb_launch":      _build_bomb_launch,
            "bomb_explode":     _build_bomb_explode,
            "wave_start":       _build_wave_start,
            "boss_spawn":       _build_boss_spawn,
            "boss_hit":         _build_boss_hit,
            "level_up":         _build_level_up,
        }
        for name, fn in builders.items():
            try:
                snd = fn()
                snd.set_volume(self.volume)
                self._sounds[name] = snd
            except Exception as exc:
                print(f"[audio] Warning: could not build '{name}': {exc}")

    def _start_drone(self) -> None:
        try:
            self._drone_channel = pygame.mixer.find_channel()
            if self._drone_channel:
                drone = _build_ambient_drone(self._drone_hz, False)
                drone.set_volume(self.volume * 0.35)
                self._drone_channel.play(drone, loops=-1)
        except Exception:
            self._drone_channel = None

    def update_drone(self, energy_frac: float, chaos: bool) -> None:
        """Call every frame with energy fraction [0..1] and chaos state."""
        target_hz   = 60.0 + energy_frac * 50.0
        need_rebuild = abs(target_hz - self._drone_hz) > 5.0 or chaos != self._chaos_drone
        if not need_rebuild or not self._drone_channel:
            return
        self._drone_hz    = target_hz
        self._chaos_drone = chaos
        try:
            drone = _build_ambient_drone(target_hz, chaos)
            v = self.volume * 0.35
            if self._muted:
                v = 0.0
            drone.set_volume(v)
            self._drone_channel.play(drone, loops=-1)
        except Exception:
            pass

    def stop_drone(self) -> None:
        if self._drone_channel:
            self._drone_channel.stop()

    # ── Public ────────────────────────────────────────────────────────────────

    def play(self, name: str) -> None:
        if self._muted:
            return
        snd = self._sounds.get(name)
        if snd:
            snd.play()

    def toggle_mute(self) -> bool:
        self._muted = not self._muted
        if self._drone_channel:
            v = 0.0 if self._muted else self.volume * 0.35
            self._drone_channel.set_volume(v)
        return self._muted

    def set_volume(self, v: float) -> None:
        self.volume = max(0.0, min(1.0, v))
        for snd in self._sounds.values():
            snd.set_volume(self.volume)
        if self._drone_channel and not self._muted:
            self._drone_channel.set_volume(self.volume * 0.35)

    @property
    def muted(self) -> bool:
        return self._muted

    # Convenience shortcuts
    def hack(self)             -> None: self.play("hack")
    def meh_hack(self)         -> None: self.play("meh_hack")
    def meh_destroy(self)      -> None: self.play("meh_destroy")
    def fragment_collect(self) -> None: self.play("fragment_collect")
    def enemy_stun(self)       -> None: self.play("enemy_stun")
    def chaos_activate(self)   -> None: self.play("chaos_activate")
    def chaos_end(self)        -> None: self.play("chaos_end")
    def player_hit(self)       -> None: self.play("player_hit")
    def game_over(self)        -> None: self.play("game_over")
    def dash(self)             -> None: self.play("dash")
    def plasma_shoot(self)     -> None: self.play("plasma_shoot")
    def spread_shoot(self)     -> None: self.play("spread_shoot")
    def chain_zap(self)        -> None: self.play("chain_zap")
    def beam_hum(self)         -> None: self.play("beam_hum")
    def bomb_launch(self)      -> None: self.play("bomb_launch")
    def bomb_explode(self)     -> None: self.play("bomb_explode")
    def wave_start(self)       -> None: self.play("wave_start")
    def boss_spawn(self)       -> None: self.play("boss_spawn")
    def boss_hit(self)         -> None: self.play("boss_hit")
    def level_up(self)         -> None: self.play("level_up")
