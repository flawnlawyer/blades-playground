"""
music.py — Generative, reactive layered music.  Zero audio files.

Five seamless loops (all exactly 8 beats @ 112 BPM = 189,000 samples) play
simultaneously on dedicated mixer channels, so they stay phase-locked forever.
The game only ever changes each layer's *volume*:

    pad    always on                          bass   whenever enemies are alive
    arp    wave >= 2, streak >= 5, or boss    drums  crowd >= 8 or boss alive
    lead   Chaos Mode only

Volumes glide (never jump), music ducks during death slow-mo, and respects mute.
"""
from __future__ import annotations
import numpy as np
import pygame

from game.audio import SR, _make

BPM        = 112
BEAT       = SR * 60 // BPM            # 23,625 samples — an exact integer
LOOP_BEATS = 8
LOOP_N     = BEAT * LOOP_BEATS         # 189,000
LAYERS     = ("pad", "bass", "arp", "drums", "lead")
_BASE_CH   = 18                         # first reserved mixer channel
_MUSIC_GAIN = 0.55

# Am | F  (4 beats each).  Frequencies in Hz.
_CHORDS = [
    {"root": 55.00,  "notes": [110.00, 130.81, 164.81, 220.00]},   # Am: A2 C3 E3 A3
    {"root": 43.65,  "notes": [87.31, 110.00, 130.81, 174.61]},    # F : F2 A2 C3 F3
]


def _t(n: int) -> np.ndarray:
    return np.arange(n, dtype=np.float64) / SR


def _edge(sig: np.ndarray, ms: float = 6.0) -> np.ndarray:
    """Fade the first/last few ms so every layer loops without a click."""
    k = max(1, int(SR * ms / 1000))
    sig[:k]  *= np.linspace(0, 1, k)
    sig[-k:] *= np.linspace(1, 0, k)
    return sig


def _place(buf: np.ndarray, start: int, snd: np.ndarray) -> None:
    end = min(len(buf), start + len(snd))
    buf[start:end] += snd[:end - start]


def _pluck(freq: float, n: int, decay: float, harmonics=(1.0, 0.35, 0.15)) -> np.ndarray:
    t   = _t(n)
    sig = sum(a * np.sin(2 * np.pi * freq * (i + 1) * t) for i, a in enumerate(harmonics))
    env = np.exp(-t * decay)
    env[:64] *= np.linspace(0, 1, 64)
    return (sig * env).astype(np.float32)


def _build_pad() -> np.ndarray:
    buf = np.zeros(LOOP_N, np.float32)
    for ci, chord in enumerate(_CHORDS):
        n   = BEAT * 4
        t   = _t(n)
        sig = np.zeros(n)
        for f in chord["notes"][:3]:
            for detune in (-0.6, 0.0, 0.6):                      # gentle chorus
                sig += np.sin(2 * np.pi * (f + detune) * t) * 0.07
        env = np.minimum(1.0, np.minimum(t / 0.5, (t[-1] - t) / 0.5))   # slow swell in/out
        _place(buf, ci * n, (sig * env).astype(np.float32))
    return _edge(buf)


def _build_bass() -> np.ndarray:
    buf = np.zeros(LOOP_N, np.float32)
    step = BEAT // 2                                              # 8th notes
    for i in range(LOOP_BEATS * 2):
        root = _CHORDS[i // 8]["root"]
        f    = root * (2.0 if i % 4 == 3 else 1.0)                # octave pop on the off-beat
        _place(buf, i * step, _pluck(f, step, 7.0, (1.0, 0.5, 0.25)) * 0.42)
    return _edge(buf)


def _build_arp() -> np.ndarray:
    buf  = np.zeros(LOOP_N, np.float32)
    step = BEAT // 4                                              # 16th notes
    pattern = [0, 1, 2, 3, 2, 1, 2, 3]
    for i in range(LOOP_BEATS * 4):
        notes = _CHORDS[i // 16]["notes"]
        f = notes[pattern[i % 8]] * 2.0
        _place(buf, i * step, _pluck(f, step * 2, 11.0, (1.0, 0.2)) * 0.20)
    return _edge(buf)


def _build_drums() -> np.ndarray:
    buf  = np.zeros(LOOP_N, np.float32)
    rng  = np.random.default_rng(7)
    for b in range(LOOP_BEATS):                                   # kick every beat
        n = int(SR * 0.16); t = _t(n)
        f = 50 + 90 * np.exp(-t * 28)
        kick = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 16)
        _place(buf, b * BEAT, (kick * 0.55).astype(np.float32))
        if b % 2 == 1:                                            # snare on 2 and 4
            n = int(SR * 0.14); t = _t(n)
            sn = rng.uniform(-1, 1, n) * np.exp(-t * 24) * 0.30
            _place(buf, b * BEAT, sn.astype(np.float32))
    for i in range(LOOP_BEATS * 2):                               # off-beat hats
        n = int(SR * 0.04); t = _t(n)
        h = np.diff(rng.uniform(-1, 1, n + 1)) * np.exp(-t * 90) * 0.20   # crude high-pass
        _place(buf, i * (BEAT // 2) + BEAT // 4, h.astype(np.float32))
    return _edge(buf)


def _build_lead() -> np.ndarray:
    buf  = np.zeros(LOOP_N, np.float32)
    step = BEAT // 2
    riff = [(0, 7), (0, 10), (0, 12), (0, 10), (1, 5), (1, 8), (1, 12), (1, 8),
            (0, 7), (0, 10), (0, 14), (0, 12), (1, 5), (1, 8), (1, 10), (1, 12)]
    for i, (ci, semis) in enumerate(riff):
        f = _CHORDS[ci]["notes"][0] * 4.0 * 2 ** (semis / 12.0)
        n = step; t = _t(n)
        vib = 1 + 0.004 * np.sin(2 * np.pi * 6 * t)
        saw = sum((1.0 / h) * np.sin(2 * np.pi * f * h * vib * t) for h in range(1, 6))
        env = np.exp(-t * 4.5); env[:48] *= np.linspace(0, 1, 48)
        _place(buf, i * step, (saw * env * 0.07).astype(np.float32))
    return _edge(buf)


_BUILDERS = {"pad": _build_pad, "bass": _build_bass, "arp": _build_arp,
             "drums": _build_drums, "lead": _build_lead}
_CACHE: dict[str, np.ndarray] = {}


def layer_samples() -> dict[str, np.ndarray]:
    """Synthesise (once per process) and return the raw mono loops."""
    for name in LAYERS:
        if name not in _CACHE:
            _CACHE[name] = _BUILDERS[name]()
    return _CACHE


def target_levels(enemies: int, boss: bool, chaos: bool, streak: int,
                  wave: int, dying: bool) -> dict[str, float]:
    """Pure function: game state -> per-layer volume targets in [0, 1]."""
    lv = {
        "pad":   0.75,
        "bass":  1.0 if (enemies > 0 or boss) else 0.25,
        "arp":   1.0 if (wave >= 2 or streak >= 5 or boss) else 0.0,
        "drums": 1.0 if (enemies >= 8 or boss) else (0.35 if enemies > 0 else 0.0),
        "lead":  1.0 if chaos else 0.0,
    }
    if dying:                                                     # duck everything but the pad
        lv = {k: (v * 0.2 if k != "pad" else 0.5) for k, v in lv.items()}
    return lv


class MusicEngine:
    GLIDE = 1.6        # volume units per second

    def __init__(self, audio) -> None:
        self.audio    = audio
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        self._chans:  dict[str, pygame.mixer.Channel] = {}
        self._level   = {k: 0.0 for k in LAYERS}
        self._playing = False
        self.disabled = False          # set from the MUSIC setting
        try:
            if pygame.mixer.get_init():
                if pygame.mixer.get_num_channels() < _BASE_CH + len(LAYERS):
                    pygame.mixer.set_num_channels(_BASE_CH + len(LAYERS))
                for name, mono in layer_samples().items():
                    self._sounds[name] = _make(mono)
        except Exception as exc:
            print(f"[music] disabled: {exc}")
            self._sounds = {}

    def start(self) -> None:
        if self._playing or not self._sounds or self.disabled:
            return
        for i, name in enumerate(LAYERS):
            ch = pygame.mixer.Channel(_BASE_CH + i)
            ch.set_volume(0.0)
            ch.play(self._sounds[name], loops=-1)
            self._chans[name] = ch
        self._playing = True

    def stop(self) -> None:
        for ch in self._chans.values():
            ch.stop()
        self._chans.clear()
        self._level = {k: 0.0 for k in LAYERS}
        self._playing = False

    def update(self, dt: float, **state) -> None:
        if not self._playing:
            return
        target = target_levels(**state)
        gain   = 0.0 if self.audio.muted else self.audio.volume * _MUSIC_GAIN
        step   = self.GLIDE * dt
        for name in LAYERS:
            cur = self._level[name]
            tgt = target[name]
            cur = min(tgt, cur + step) if cur < tgt else max(tgt, cur - step)
            self._level[name] = cur
            self._chans[name].set_volume(cur * gain)
