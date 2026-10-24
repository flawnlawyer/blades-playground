"""
perks.py — Between-wave upgrades, weapon evolutions and synergies.

Perks are pure data.  Their effects are read where they matter (Player fire
rates, Game kill handling, ...) via ``perks.get(key, 0)`` — the stack count —
so adding a perk is: add an entry here, then read its stack count at the
point it should change behaviour.

* EVOLUTIONS are single-stack perks that only appear in the picker once their
  `requires` perks are owned (e.g. HOMING BOLTS needs OVERCLOCK + PIERCE).
* SYNERGIES are bonuses that switch on automatically when you hold certain
  perk combinations; the picker hints which card would complete one.
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
    requires:   tuple = ()   # ((perk_key, min_stacks), ...) — all must be owned to be offered
    evolution:  bool = False


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
    # ── Evolutions ───────────────────────────────────────────────────────────
    Perk("homing",      "HOMING BOLTS",  "Plasma & Spread bolts curve toward enemies", (255, 225, 120), 1,
         requires=(("overclock", 1), ("pierce", 1)), evolution=True),
    Perk("void_bloom",  "VOID BLOOM",    "Void Spread fires 9 pellets in a wider cone", (210, 140, 255), 1,
         requires=(("overclock", 2),), evolution=True),
    Perk("tesla",       "TESLA COIL",    "Chain Zap can hit bosses, +1 damage",       (120, 255, 210), 1,
         requires=(("arc_lattice", 2),), evolution=True),
    Perk("null_lance",  "NULL LANCE",    "Null Beam is wider and hits 50% harder",    (255, 110, 160), 1,
         requires=(("surge", 1), ("salvage", 1)), evolution=True),
    Perk("cluster",     "CLUSTER BOMBS", "Chaos Bombs burst into 4 smaller blasts",   (255, 200,  70), 1,
         requires=(("volatile", 1),), evolution=True),
]}


@dataclass(frozen=True)
class Synergy:
    key:      str
    name:     str
    desc:     str
    requires: tuple          # ((perk_key, min_stacks), ...)
    color:    tuple = (255, 215, 90)


SYNERGIES: dict[str, Synergy] = {s.key: s for s in [
    Synergy("detonating_trails", "DETONATING TRAILS", "Bolts that pierce an enemy detonate on it",
            (("pierce", 1), ("volatile", 1))),
    Synergy("slipstream",        "SLIPSTREAM",        "Dashing pulls in nearby fragments",
            (("phase_drive", 1), ("salvage", 1))),
    Synergy("overcharged_arc",   "OVERCHARGED ARC",   "OVERCLOCK also speeds up Chain Zap",
            (("overclock", 1), ("arc_lattice", 1))),
    Synergy("last_stand",        "LAST STAND",        "SECOND WIND also triggers Chaos Mode",
            (("surge", 1), ("second_wind", 1))),
    Synergy("regen_matrix",      "REGEN MATRIX",      "Every 6th fragment restores 1 HP",
            (("repair", 1), ("salvage", 1))),
]}


def meets(requires: tuple, owned: dict) -> bool:
    return all(owned.get(k, 0) >= n for k, n in requires)


def active_synergies(owned: dict) -> list[Synergy]:
    return [s for s in SYNERGIES.values() if meets(s.requires, owned)]


def completing_synergies(owned: dict, key: str) -> list[Synergy]:
    """Synergies that taking *key* next would switch on (and aren't on yet)."""
    after = dict(owned); after[key] = after.get(key, 0) + 1
    return [s for s in SYNERGIES.values()
            if not meets(s.requires, owned) and meets(s.requires, after)]


def roll_choices(owned: dict, n: int = 3, rng: random.Random | None = None) -> list[Perk]:
    """Pick up to *n* distinct perks: not capped, requirements met.  When an evolution is
    available it takes one of the slots about half the time, so it is offered but not guaranteed."""
    rng = rng or random
    pool = [p for p in PERKS.values()
            if owned.get(p.key, 0) < p.max_stacks and meets(p.requires, owned)]
    rng.shuffle(pool)
    evos  = [p for p in pool if p.evolution]
    plain = [p for p in pool if not p.evolution]
    out = plain[:n]
    if evos and rng.random() < 0.5:
        out = ([evos[0]] + plain[:n - 1]) if len(plain) >= n - 1 else ([evos[0]] + plain)
    elif len(out) < n:                       # not enough plain perks left: fill with evolutions
        out += evos[:n - len(out)]
    return out[:n]
