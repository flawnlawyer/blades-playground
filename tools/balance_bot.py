#!/usr/bin/env python3
"""
balance_bot.py — a heuristic bot that plays the real game headlessly, to gather
balance data (difficulty curve, what kills you, which perks help).

    python tools/balance_bot.py --runs 20 --skill average --out results.csv
    python tools/balance_bot.py --perk-test --runs 6          # paired per-perk experiment

IMPORTANT — what this is and isn't.  The bot is a *fixed, mediocre player*: it kites,
dodges, hacks and dashes by simple rules.  Numbers from it are only meaningful as
RELATIVE comparisons (wave X is a spike; perk A beats perk B for this bot).  They are
not a prediction of how a human will do.
"""
from __future__ import annotations
import argparse, csv, math, os, random, sys, time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.getcwd())
import pygame
pygame.init(); pygame.display.set_mode((1280, 720))

from game.constants import W, H, CHAIN_RANGE, BOMB_RADIUS, PLASMA_RANGE
from game.entities import ShieldDrone, Sniper
from game.game import Game
from game.perks import PERKS, roll_choices
from utils.keybinds import KEYS

# skill profile: (think-every-N-frames, chance to miss a dash/hack, dodge radius px)
SKILLS = {"novice": (8, 0.35, 70), "average": (4, 0.15, 95), "skilled": (2, 0.03, 120)}


class Keys(dict):
    def __missing__(self, k):
        return False


class Bot:
    """Implements Game.input_source: poll(game) -> (keys, mouse_pos, buttons)."""

    def __init__(self, rng: random.Random, skill: str = "average") -> None:
        self.rng = rng
        self.every, self.miss, self.dodge_r = SKILLS[skill]
        self._frame = 0
        self._keys = Keys()
        self._aim = (W / 2, H / 2)
        self._fire = False
        self._weapon_cd = 0.0
        self._bomb_cd = 0.0

    # ── perception helpers ────────────────────────────────────────────────────

    @staticmethod
    def _dist(a, b) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])

    def poll(self, g: Game):
        self._frame += 1
        if self._frame % self.every == 0:                    # decisions at a human-ish tempo
            self._think(g)
        return self._keys, self._aim, (self._fire, False, False)

    def _think(self, g: Game) -> None:
        p, pos = g.player, g.player.pos
        px, py = pos.x, pos.y
        near = [e for e in g.enemies if self._dist((px, py), e.pos) < 260]

        # ── movement vector ───────────────────────────────────────────────────
        vx = vy = 0.0
        if p.chaos_mode:                                     # contact kills in chaos: charge the nearest enemy
            tgt = min(g.enemies, key=lambda e: self._dist((px, py), e.pos), default=None)
            if tgt is not None:
                d = max(1.0, self._dist((px, py), tgt.pos)); vx, vy = (tgt.pos.x - px) / d, (tgt.pos.y - py) / d
        else:
            for e in near:
                d = max(12.0, self._dist((px, py), e.pos)); w = (2.2 if e.__class__.__name__ == "Berserker" else 1.0) * 5200 / (d * d)
                vx += (px - e.pos.x) / d * w; vy += (py - e.pos.y) / d * w
            if g.boss:
                d = max(30.0, self._dist((px, py), g.boss.pos))
                if d < 340:
                    vx += (px - g.boss.pos.x) / d * 3.0; vy += (py - g.boss.pos.y) / d * 3.0
        for b in g.enemy_bullets:                            # sidestep bullets that are heading our way
            d = self._dist((px, py), b.pos)
            if d < self.dodge_r + 40:
                rel = (px - b.pos.x, py - b.pos.y)
                if rel[0] * b.vel.x + rel[1] * b.vel.y > 0:  # moving towards us
                    sp = max(1.0, b.vel.length()); perp = (-b.vel.y / sp, b.vel.x / sp)
                    side = 1.0 if (rel[0] * perp[0] + rel[1] * perp[1]) >= 0 else -1.0
                    wgt = 4.0 * (1 - d / (self.dodge_r + 40)) + 0.5
                    vx += perp[0] * side * wgt; vy += perp[1] * side * wgt
        for e in g.enemies:                                  # step out of a sniper's laser
            if isinstance(e, Sniper) and e.aiming and not e.stunned:
                a, bpt = e.pos, e.aim
                ab = (bpt.x - a.x, bpt.y - a.y); L = math.hypot(*ab) or 1.0
                t = max(0.0, min(1.0, ((px - a.x) * ab[0] + (py - a.y) * ab[1]) / (L * L)))
                cx, cy = a.x + ab[0] * t, a.y + ab[1] * t
                dline = self._dist((px, py), (cx, cy))
                if dline < 50:
                    side = 1.0 if (px - cx) * -ab[1] + (py - cy) * ab[0] >= 0 else -1.0
                    vx += -ab[1] / L * side * 3.0; vy += ab[0] / L * side * 3.0
        margin = 90                                          # keep off the walls
        vx += max(0, margin - px) / margin * 2 - max(0, px - (W - margin)) / margin * 2
        vy += max(0, margin - py) / margin * 2 - max(0, py - (H - margin)) / margin * 2
        if not near and not p.chaos_mode:                    # calm: fetch fragments, else drift to the middle
            frag = min(g.fragments, key=lambda f: self._dist((px, py), f.pos), default=None)
            tx, ty = (frag.pos.x, frag.pos.y) if frag else (W / 2, H / 2)
            d = max(1.0, self._dist((px, py), (tx, ty))); vx += (tx - px) / d * 0.9; vy += (ty - py) / d * 0.9
        k = self._keys; k.clear()
        for ax, neg, pos_ in ((vx, "left", "right"), (vy, "up", "down")):
            if abs(ax) > 0.25:
                for key in KEYS.map[pos_ if ax > 0 else neg]:
                    if key is not None:
                        k[key] = True
                        break

        # ── aim + weapon ──────────────────────────────────────────────────────
        enemies = [e for e in g.enemies if e.shield == 0 and not getattr(e, "_dead", False)]
        pool = enemies or list(g.enemies)
        target = min(pool, key=lambda e: self._dist((px, py), e.pos), default=None)
        tpos = target.pos if target else None
        if g.boss and (tpos is None or self._dist((px, py), g.boss.pos) < self._dist((px, py), tpos) + 80):
            tpos = g.boss.pos
        self._fire = tpos is not None and self._dist((px, py), tpos) < PLASMA_RANGE
        if tpos is not None:
            self._aim = (tpos.x, tpos.y)
        if self._frame * 1 >= 0:
            self._pick_weapon(g, near)
        self._tactics(g, near, enemies)

    def _pick_weapon(self, g: Game, near: list) -> None:
        p = g.player
        if g.run_time < self._weapon_cd:
            return
        self._weapon_cd = g.run_time + 0.6
        if g.boss and p.energy > 25 and self._dist(p.pos, g.boss.pos) < 460:
            p.weapon_index = 3
        elif len(near) >= 4:
            p.weapon_index = 1
        elif len(near) >= 3 and sum(1 for e in near if self._dist(p.pos, e.pos) < CHAIN_RANGE) >= 3:
            p.weapon_index = 2
        else:
            p.weapon_index = 0

    def _tactics(self, g: Game, near: list, enemies: list) -> None:
        p = g.player
        r = self.rng.random
        close = [e for e in g.enemies if self._dist(p.pos, e.pos) < 85]
        bullets = [b for b in g.enemy_bullets if self._dist(p.pos, b.pos) < 120]
        if p.can_hack and (len(close) >= 2 or len(bullets) >= 4) and r() > self.miss:
            g._do_hack()
        danger = any(self._dist(p.pos, e.pos) < 40 and e.spawn_grace <= 0 for e in g.enemies) or \
                 any(self._dist(p.pos, b.pos) < 30 for b in g.enemy_bullets)
        if danger and p.dash_charges > 0 and not p.invulnerable and r() > self.miss:
            p.trigger_dash(self._keys)
        if p.bomb_count > 0 and g.run_time > self._bomb_cd and len(near) >= 6:
            cx = sum(e.pos.x for e in near) / len(near); cy = sum(e.pos.y for e in near) / len(near)
            if self._dist((cx, cy), p.pos) > BOMB_RADIUS * 0.8:      # don't bomb ourselves
                self._aim, p.weapon_index, self._bomb_cd = (cx, cy), 4, g.run_time + 1.5


# ── running games ─────────────────────────────────────────────────────────────

def make_game(seed: int, start_perks: dict | None = None) -> Game:
    random.seed(seed)
    g = Game(None, seed=seed)
    g.meh_blocks = g.meh_blocks[:14]
    g.audio.play = lambda *a, **k: None                     # silence + speed: no mixer work in bulk runs
    g.audio.update_drone = lambda *a, **k: None
    g.music.update = lambda *a, **k: None
    for k, n in (start_perks or {}).items():
        for _ in range(n):
            g.grant_perk(k)
    return g


def run_one(seed: int, skill: str = "average", max_seconds: float = 240.0,
            start_perks: dict | None = None, perk_policy: str = "random", dt: float = 1 / 30) -> dict:
    g = make_game(seed, start_perks)
    rng = random.Random(f"bot:{seed}")
    g.input_source = Bot(rng, skill)
    wave_hits: dict[int, int] = {}
    hits0 = 0
    t0 = time.perf_counter()
    while not g.game_over and g.run_time < max_seconds:
        if g.perk_pending:
            g.perk_pending = False
            ch = roll_choices(g.perks, rng=random.Random(f"perk:{seed}:{g.wave_mgr.wave}"))
            if ch:
                g.grant_perk((rng.choice(ch) if perk_policy == "random" else ch[0]).key)
        g.update(dt)
    return {"seed": seed, "skill": skill, "wave": g.wave_mgr.wave, "seconds": round(g.run_time, 1),
            "score": g.score, "kills": g.stats["kills"], "hits": g.stats["hits"],
            "bosses": "|".join(g.stats["bosses"]), "died": int(g.game_over),
            "cause": g.last_hit or ("survived" if not g.game_over else "unknown"),
            "perks": "|".join(f"{k}x{n}" for k, n in g.perks.items()),
            "wall": round(time.perf_counter() - t0, 1)}


FIELDS = ["condition", "seed", "skill", "wave", "seconds", "score", "kills", "hits", "bosses",
          "died", "cause", "perks", "wall"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--skill", choices=list(SKILLS), default="average")
    ap.add_argument("--seconds", type=float, default=240.0, help="game-time cap per run")
    ap.add_argument("--out", default="balance_results.csv")
    ap.add_argument("--seed0", type=int, default=1000)
    ap.add_argument("--perk-test", action="store_true", help="paired experiment: start each run with one perk")
    ap.add_argument("--only", default="", help="comma list of conditions to run (perk-test)")
    a = ap.parse_args()

    conditions: list[tuple[str, dict]] = [("baseline", {})]
    if a.perk_test:
        for k, p in PERKS.items():
            if p.evolution:
                req = {r: n for r, n in p.requires}
                conditions.append((f"{k}(+prereqs)", {**req, k: 1}))
                conditions.append((f"prereqs-for-{k}", dict(req)))
            else:
                conditions.append((k, {k: 1}))
    if a.only:
        wanted = set(a.only.split(","))
        conditions = [c for c in conditions if c[0] in wanted or c[0] == "baseline"]
    new = not os.path.exists(a.out)
    with open(a.out, "a", newline="") as fh:
        w = csv.DictWriter(fh, FIELDS)
        if new:
            w.writeheader()
        for name, perks in (conditions if a.perk_test else [("baseline", {})]):
            for i in range(a.runs):
                row = run_one(a.seed0 + i, a.skill, a.seconds, perks)
                row["condition"] = name
                w.writerow(row); fh.flush()
                print(f"{name:28s} seed {row['seed']} wave {row['wave']:2d} {row['seconds']:6.1f}s "
                      f"score {row['score']:6d} {row['cause'] or '-':14s} ({row['wall']}s wall)", flush=True)


if __name__ == "__main__":
    main()
