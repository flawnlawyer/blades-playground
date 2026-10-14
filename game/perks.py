"""
perks.py — Between-wave upgrades.

Perks are pure data.  Their effects are read where they matter (Player fire
rates, Game kill handling, ...) via ``perks.get(key, 0)`` — the stack count —
so adding a perk is: add an entry here, then read its stack count at the
point it should change behaviour.
"""
from __future__ import annotations
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Perk:
    key:        str
    name:       str
    desc:       str          # one line, shown on the card
    color:      tuple
    max_stacks: int = 3


PERKS: dict[str, Perk] = {p.key: p for p in [
    Perk("overclock",   "OVERCLOCK",     "Plasma & Spread fire 25% faster",           (100, 200, 255)),
    Perk("pierce",      "PIERCE",        "Plasma & Spread bolts pass through +1 enemy", (180, 100, 255)),
    Perk("arc_lattice", "ARC LATTICE",   "Chain Zap: +2 links, +40 range",            (100, 255, 180)),
    Perk("phase_drive", "PHASE DRIVE",   "+1 dash charge",                            (120, 120, 255), 2),
    Perk("surge",       "SURGE",         "Chaos Mode lasts +3 seconds",               (255, 190,   0)),
    Perk("salvage",     "SALVAGE",       "Fragments give +40% energy",                (  0, 200, 180)),
    Perk("volatile",    "VOLATILE CORE", "Kills detonate, damaging nearby enemies",   (255, 140,  40), 2),
    Perk("repair",      "REPAIR",        "Restore 1 HP",                              (210,  45,  75)),
    Perk("second_wind", "SECOND WIND",   "Once per run: survive a lethal hit",        (255, 255, 255), 1),
]}


def roll_choices(owned: dict, n: int = 3, rng: random.Random | None = None) -> list[Perk]:
    """Pick up to *n* distinct perks that are not yet at their stack cap."""
    rng = rng or random
    pool = [p for p in PERKS.values() if owned.get(p.key, 0) < p.max_stacks]
    rng.shuffle(pool)
    return pool[:n]
