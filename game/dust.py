"""
dust.py — NumPy-vectorised particle field.

The classic Particle objects cost a Python method call per particle per frame,
which caps a scene at a few hundred.  DustField keeps *all* particles in flat
float32 arrays: emit / update / draw are each a handful of array operations, so
tens of thousands of sparks cost about the same as a few hundred objects.

Particles are drawn as additive 2x2 pixel points written straight into the
surface's pixel buffer (surfarray view) — no per-particle blit at all.
"""
from __future__ import annotations
import numpy as np
import pygame

from game.constants import W, H

_TAU = np.float32(2 * np.pi)


class DustField:
    def __init__(self, capacity: int = 12_000, seed: int | None = None) -> None:
        self.cap      = capacity
        self.n        = 0
        self._rng     = np.random.default_rng(seed)
        self.pos      = np.zeros((capacity, 2), np.float32)
        self.vel      = np.zeros((capacity, 2), np.float32)
        self.life     = np.zeros(capacity, np.float32)
        self.max_life = np.ones(capacity, np.float32)
        self.col      = np.zeros((capacity, 3), np.float32)

    def __len__(self) -> int:
        return self.n

    def clear(self) -> None:
        self.n = 0

    def emit(self, x: float, y: float, count: int, color: tuple,
             speed: tuple = (40.0, 260.0), life: tuple = (0.25, 0.8),
             angle: float | None = None, spread: float = np.pi) -> None:
        """Spawn *count* particles at once (fully vectorised)."""
        count = int(min(count, self.cap - self.n))
        if count <= 0:
            return
        i, j = self.n, self.n + count
        r = self._rng
        if angle is None:                                   # full circle
            a = r.uniform(0, _TAU, count).astype(np.float32)
        else:                                               # cone around `angle`
            a = (r.uniform(-spread, spread, count) + angle).astype(np.float32)
        s = r.uniform(speed[0], speed[1], count).astype(np.float32)
        self.pos[i:j, 0] = x
        self.pos[i:j, 1] = y
        self.vel[i:j, 0] = np.cos(a) * s
        self.vel[i:j, 1] = np.sin(a) * s
        lf = r.uniform(life[0], life[1], count).astype(np.float32)
        self.life[i:j] = lf
        self.max_life[i:j] = lf
        self.col[i:j] = color[:3]
        self.n = j

    def update(self, dt: float) -> None:
        n = self.n
        if n == 0:
            return
        life = self.life[:n] - dt
        keep = life > 0
        if not keep.all():                      # compact survivors to the front
            m = int(keep.sum())
            self.pos[:m]      = self.pos[:n][keep]
            self.vel[:m]      = self.vel[:n][keep]
            self.max_life[:m] = self.max_life[:n][keep]
            self.col[:m]      = self.col[:n][keep]
            life              = life[keep]
            n                 = m
        self.life[:n] = life
        self.pos[:n] += self.vel[:n] * np.float32(dt)
        self.vel[:n] *= np.float32(0.93 ** (dt * 60.0))     # drag
        self.n = n

    def draw(self, surf: pygame.Surface, ox: int = 0, oy: int = 0) -> None:
        n = self.n
        if n == 0:
            return
        xi = (self.pos[:n, 0] + ox).astype(np.int32)
        yi = (self.pos[:n, 1] + oy).astype(np.int32)
        ok = (xi >= 0) & (xi < W - 1) & (yi >= 0) & (yi < H - 1)
        if not ok.any():
            return
        xi, yi = xi[ok], yi[ok]
        glow = (self.life[:n] / self.max_life[:n])[ok, None]
        add  = (self.col[:n][ok] * glow).astype(np.int16)
        px   = pygame.surfarray.pixels3d(surf)          # writable view, no copy
        try:
            for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
                cur = px[xi + dx, yi + dy].astype(np.int16)
                px[xi + dx, yi + dy] = np.minimum(cur + add, 255).astype(np.uint8)
        finally:
            del px                                       # release the surface lock
