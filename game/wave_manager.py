"""
wave_manager.py — Wave definitions, spawn scheduling, and between-wave state.
"""
from __future__ import annotations
import pygame

from game.constants import WAVE_BREAK_DURATION


# Wave definitions: list of (enemy_type_str, count) per wave
WAVE_DEFS = [
    # Wave 1
    [("standard", 4)],
    # Wave 2
    [("standard", 5), ("hunter", 2)],
    # Wave 3
    [("standard", 3), ("swarm", 4), ("hunter", 1)],
    # Wave 4
    [("standard", 2), ("hunter", 2), ("phantom", 2)],
    # Wave 5
    [("boss", 1), ("standard", 2)],
]


class WaveManager:
    def __init__(self) -> None:
        self.wave         = 0       # current wave number (1-indexed for display)
        self._timer       = 0.0
        self._break_timer = 0.0
        self._state       = "break" # "active" | "break" | "boss_dead"
        self._pending_spawns: list[tuple] = []
        self.spawn_queue: list[tuple] = []   # consumed by play_state
        self.wave_just_started = False
        self.boss_alive   = False
        self._all_dead_timer = 0.0  # small delay after all enemies die

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Call once to begin wave 1 immediately."""
        self._begin_break()

    def update(self, dt: float, enemy_count: int, boss_alive: bool) -> None:
        self.boss_alive        = boss_alive
        self.spawn_queue       = []
        self.wave_just_started = False

        if self._state == "break":
            self._break_timer -= dt
            if self._break_timer <= 0:
                self._launch_wave()

        elif self._state == "active":
            # Wave ends when all enemies are dead
            if enemy_count == 0 and not boss_alive:
                self._all_dead_timer += dt
                if self._all_dead_timer > 1.2:
                    self._all_dead_timer = 0.0
                    self._begin_break()
            else:
                self._all_dead_timer = 0.0

            # Drip-spawn pending spawns
            if self._pending_spawns:
                batch, self._pending_spawns = (
                    self._pending_spawns[:3], self._pending_spawns[3:])
                self.spawn_queue.extend(batch)

    def _begin_break(self) -> None:
        self._state       = "break"
        self._break_timer = WAVE_BREAK_DURATION

    def _launch_wave(self) -> None:
        self.wave         += 1
        self._state        = "active"
        self.wave_just_started = True
        self._pending_spawns = self._build_spawn_list()
        # Immediately queue first batch
        batch, self._pending_spawns = (
            self._pending_spawns[:3], self._pending_spawns[3:])
        self.spawn_queue.extend(batch)

    def _build_spawn_list(self) -> list[tuple]:
        spawns = []
        if self.wave <= len(WAVE_DEFS):
            defs = WAVE_DEFS[self.wave - 1]
        else:
            # Procedural scaling beyond wave 5
            n     = self.wave - len(WAVE_DEFS)
            defs  = [
                ("standard", 3 + n),
                ("hunter",   1 + n // 2),
                ("phantom",  n // 2),
                ("swarm",    n),
            ]
        for (etype, count) in defs:
            for _ in range(count):
                spawns.append((etype,))
        return spawns

    # ── Display helpers ───────────────────────────────────────────────────────

    @property
    def in_break(self) -> bool:
        return self._state == "break"

    @property
    def break_countdown(self) -> float:
        return max(0.0, self._break_timer)

    @property
    def is_boss_wave(self) -> bool:
        return self.wave == 5 or (self.wave > 5 and (self.wave - 5) % 5 == 0)
