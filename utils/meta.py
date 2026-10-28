"""
meta.py — Between-run progression: shards, permanent upgrades, loadouts, achievements.

Pure functions over a plain dict (persisted by utils.data_manager), so the rules are
easy to test.  Design rules:
  * Shards are only earned on CLEAN runs (no cheats, not stress mode).
  * Daily runs ignore every upgrade/loadout, so the daily board stays level.
  * Nothing here can make a run impossible — upgrades are small, permanent nudges.
"""
from __future__ import annotations
import copy

from game.perks import PERKS

WEAPON_NAMES = ["PLASMA BOLT", "VOID SPREAD", "CHAIN ZAP", "NULL BEAM", "CHAOS BOMB"]
WEAPON_COSTS = [0, 150, 250, 400, 400]            # weapon 0 (plasma) is free

# id: (name, description, [cost per level])
UPGRADES: dict[str, tuple] = {
    "vitality":  ("VITALITY",    "+1 starting HP per level",              [300, 600]),
    "quickstep": ("QUICKSTEP",   "+1 dash charge",                        [400]),
    "reserves":  ("RESERVES",    "Start each run with +25% chaos energy per level", [200, 400]),
    "magnet":    ("MAGNET",      "Fragments are collected from further away", [150, 300]),
    "arsenal":   ("ARSENAL",     "+1 maximum Chaos Bomb",                 [250]),
}

# Perks you may start a run with (base perks only — never evolutions)
STARTER_PERKS = [k for k, p in PERKS.items() if not p.evolution]
STARTER_COSTS = {k: (600 if k == "second_wind" else 250) for k in STARTER_PERKS}

ACHIEVEMENT_BONUS = 100
# id: (name, description, predicate(run_stats) -> bool)
ACHIEVEMENTS: dict[str, tuple] = {
    "first_contact":   ("FIRST CONTACT",   "Reach wave 2",                      lambda s: s["wave"] >= 2),
    "breaker":         ("BREAKER",         "Reach wave 5",                      lambda s: s["wave"] >= 5),
    "architects_end":  ("ARCHITECT'S END", "Defeat The Architect",              lambda s: "THE ARCHITECT" in s["bosses"]),
    "prism_shattered": ("PRISM SHATTERED", "Defeat The Prism",                  lambda s: "THE PRISM" in s["bosses"]),
    "unstoppable":     ("UNSTOPPABLE",     "Reach a x20 kill streak",           lambda s: s["max_streak"] >= 20),
    "chaos_incarnate": ("CHAOS INCARNATE", "Trigger Chaos Mode 3 times in a run", lambda s: s["chaos"] >= 3),
    "untouchable":     ("UNTOUCHABLE",     "Reach wave 5 without taking damage", lambda s: s["wave"] >= 5 and s["hits"] == 0),
    "collector":       ("COLLECTOR",       "Hold 8 perk stacks at once",        lambda s: s["perk_stacks"] >= 8),
    "daily_driver":    ("DAILY DRIVER",    "Reach wave 3 in a Daily Run",       lambda s: s["daily"] and s["wave"] >= 3),
    "centurion":       ("CENTURION",       "Defeat 100 enemies in one run",     lambda s: s["kills"] >= 100),
}

DEFAULT_META: dict = {
    "shards": 0, "upgrades": {}, "weapons": [0], "perks": [],
    "loadout": {"weapon": 0, "perk": None}, "achievements": [],
    "stats": {"runs": 0, "kills": 0, "best_wave": 0, "best_score": 0, "bosses": 0, "seconds": 0},
}


def normalise(raw) -> dict:
    """Merge saved data over the defaults and drop anything invalid (corrupt/edited files)."""
    m = copy.deepcopy(DEFAULT_META)
    if not isinstance(raw, dict):
        return m
    def _int(v, lo=0, hi=10 ** 9):
        return v if isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi else None
    if (v := _int(raw.get("shards"))) is not None:
        m["shards"] = v
    if isinstance(raw.get("upgrades"), dict):
        for k, lvl in raw["upgrades"].items():
            if k in UPGRADES and (l := _int(lvl, 0, len(UPGRADES[k][2]))) is not None and l > 0:
                m["upgrades"][k] = l
    if isinstance(raw.get("weapons"), list):
        m["weapons"] = sorted({0} | {w for w in raw["weapons"] if _int(w, 0, 4) is not None})
    if isinstance(raw.get("perks"), list):
        m["perks"] = [k for k in dict.fromkeys(raw["perks"]) if isinstance(k, str) and k in STARTER_PERKS]
    if isinstance(raw.get("achievements"), list):
        m["achievements"] = [k for k in dict.fromkeys(raw["achievements"]) if isinstance(k, str) and k in ACHIEVEMENTS]
    if isinstance(raw.get("stats"), dict):
        for k in m["stats"]:
            if (v := _int(raw["stats"].get(k))) is not None:
                m["stats"][k] = v
    lo = raw.get("loadout") if isinstance(raw.get("loadout"), dict) else {}
    if lo.get("weapon") in m["weapons"]:
        m["loadout"]["weapon"] = lo["weapon"]
    if lo.get("perk") in m["perks"]:
        m["loadout"]["perk"] = lo["perk"]
    return m


# ── shop ─────────────────────────────────────────────────────────────────────

def level(meta: dict, uid: str) -> int:
    return meta["upgrades"].get(uid, 0)


def upgrade_cost(meta: dict, uid: str) -> int | None:
    """Cost of the next level, or None when maxed."""
    costs = UPGRADES[uid][2]
    lv = level(meta, uid)
    return None if lv >= len(costs) else costs[lv]


def _spend(meta: dict, cost: int) -> bool:
    if meta["shards"] < cost:
        return False
    meta["shards"] -= cost
    return True


def buy_upgrade(meta: dict, uid: str) -> bool:
    cost = upgrade_cost(meta, uid)
    if cost is None or not _spend(meta, cost):
        return False
    meta["upgrades"][uid] = level(meta, uid) + 1
    return True


def buy_weapon(meta: dict, idx: int) -> bool:
    if idx in meta["weapons"] or not 0 <= idx < 5 or not _spend(meta, WEAPON_COSTS[idx]):
        return False
    meta["weapons"] = sorted(meta["weapons"] + [idx])
    return True


def buy_perk(meta: dict, key: str) -> bool:
    if key in meta["perks"] or key not in STARTER_COSTS or not _spend(meta, STARTER_COSTS[key]):
        return False
    meta["perks"].append(key)
    return True


def set_loadout(meta: dict, weapon: int | None = None, perk: str | None | bool = False) -> bool:
    """Equip an UNLOCKED weapon and/or starter perk (perk=None clears it).  Returns success."""
    if weapon is not None:
        if weapon not in meta["weapons"]:
            return False
        meta["loadout"]["weapon"] = weapon
    if perk is not False:
        if perk is not None and perk not in meta["perks"]:
            return False
        meta["loadout"]["perk"] = perk
    return True


# ── runs ─────────────────────────────────────────────────────────────────────

def shards_for_run(stats: dict) -> int:
    """Score/100 + 15 per wave survived + 60 per boss.  Cheated runs earn nothing."""
    if stats.get("cheated"):
        return 0
    return int(stats["score"] // 100) + 15 * max(0, stats["wave"] - 1) + 60 * len(stats["bosses"])


def award_run(meta: dict, stats: dict) -> dict:
    """Bank a finished run.  Returns {"shards", "achievements": [(id, name)], "total"}."""
    out = {"shards": 0, "achievements": [], "total": meta["shards"]}
    if stats.get("cheated") or stats.get("stress"):
        return out
    earned = shards_for_run(stats)
    for aid, (name, _desc, pred) in ACHIEVEMENTS.items():
        if aid not in meta["achievements"] and pred(stats):
            meta["achievements"].append(aid)
            out["achievements"].append((aid, name))
            earned += ACHIEVEMENT_BONUS
    meta["shards"] += earned
    st = meta["stats"]
    st["runs"] += 1
    st["kills"] += stats["kills"]
    st["bosses"] += len(stats["bosses"])
    st["seconds"] += int(stats.get("seconds", 0))
    st["best_wave"] = max(st["best_wave"], stats["wave"])
    st["best_score"] = max(st["best_score"], stats["score"])
    out["shards"], out["total"] = earned, meta["shards"]
    return out


def apply_to_game(game, meta: dict) -> None:
    """Apply permanent upgrades + loadout to a fresh NORMAL run (never daily/stress)."""
    p = game.player
    game.hp += level(meta, "vitality")
    p.meta_dash = level(meta, "quickstep")
    p.dash_charges = p.max_dash_charges
    p.energy = min(p.max_energy * 0.99, p.max_energy * 0.25 * level(meta, "reserves"))
    p.frag_magnet = 40 * level(meta, "magnet")
    p.bomb_max = 3 + level(meta, "arsenal")
    p.bomb_count = p.bomb_max
    p.weapon_index = meta["loadout"]["weapon"]
    if meta["loadout"]["perk"]:
        game.grant_perk(meta["loadout"]["perk"])
