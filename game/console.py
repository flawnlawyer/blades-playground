"""
console.py — In-game command console + terminal control.

  * Press ` (backquote / tilde) or F10 in-game to open the console (the game
    pauses while it is open).
  * Run with a terminal attached and the SAME commands work from the terminal
    you launched the game from (disable with --no-terminal).

Design rules
  * Commands are a registry of small functions (see the @command decorator) — no
    eval/exec anywhere.  `get`/`set` only touch existing int/float/bool/str
    attributes reachable from a fixed set of roots.
  * Anything that changes the run's difficulty or state flags the run as CHEATED:
    it is never written to the high-score table or the daily board.
"""
from __future__ import annotations
import ast
import queue
import shlex
import sys
import threading

import pygame

from game.constants import LOGICAL_W as W, LOGICAL_H as H, STREAK_RESET_TIME
from game.perks import PERKS
from utils.helpers import alpha_rect

KIND_COLORS = {
    "info":  (205, 210, 230), "ok":    (90, 230, 160), "err": (255, 95, 105),
    "cheat": (255, 175, 70),  "input": (130, 255, 205), "dim": (120, 126, 152),
}

ENEMY_TYPES = ("standard", "hunter", "swarm", "phantom", "berserker",
               "teleporter", "shield_drone", "splitter", "sniper")
_TYPE_ALIASES = {"basic": "standard", "drone": "shield_drone", "shield": "shield_drone",
                 "tele": "teleporter", "zerk": "berserker"}
BOSS_KINDS = ("architect", "prism")


class CommandError(Exception):
    """A user-facing, non-crashing command failure."""


# ── Registry ─────────────────────────────────────────────────────────────────

class Command:
    def __init__(self, name, fn, usage, help, group, cheat, needs_game, aliases, complete):
        self.name, self.fn, self.usage, self.help = name, fn, usage, help
        self.group, self.cheat, self.needs_game = group, cheat, needs_game
        self.aliases, self.complete = tuple(aliases), complete


COMMANDS: dict[str, Command] = {}
_ALIAS: dict[str, str] = {}


def command(name, usage="", help="", group="system", cheat=False,
            needs_game=True, aliases=(), complete=None):
    def deco(fn):
        COMMANDS[name] = Command(name, fn, usage, help, group, cheat, needs_game, aliases, complete)
        for a in aliases:
            _ALIAS[a] = name
        return fn
    return deco


def resolve(name: str) -> Command | None:
    name = name.lower()
    return COMMANDS.get(_ALIAS.get(name, name))


class Ctx:
    """What a command function receives."""
    def __init__(self, console: "Console") -> None:
        self.console, self.manager, self.game = console, console.manager, console.game
        self._cheat = False

    def ok(self, m):   self.console.print(m, "ok")
    def info(self, m): self.console.print(m, "info")
    def dim(self, m):  self.console.print(m, "dim")

    @property
    def player(self):
        return self.game.player


# ── Argument helpers ─────────────────────────────────────────────────────────

def _num(args, i, lo, hi, name="value", default=None, integer=False):
    if i >= len(args):
        if default is not None:
            return default
        raise CommandError(f"missing {name}")
    try:
        v = float(args[i])
    except ValueError:
        raise CommandError(f"{name} must be a number, got '{args[i]}'")
    if not lo <= v <= hi:
        raise CommandError(f"{name} must be between {lo:g} and {hi:g}")
    return int(v) if integer else v


def _flag(args, i, current: bool) -> bool:
    """on/off/true/false/1/0 — or toggle when omitted."""
    if i >= len(args):
        return not current
    v = args[i].lower()
    if v in ("on", "true", "1", "yes"):
        return True
    if v in ("off", "false", "0", "no"):
        return False
    raise CommandError("expected on or off")


def _enemy_type(s: str) -> str:
    s = _TYPE_ALIASES.get(s.lower(), s.lower())
    if s not in ENEMY_TYPES:
        raise CommandError(f"unknown enemy type '{s}'. types: {', '.join(ENEMY_TYPES)}")
    return s


def _enemy_class(t: str):
    from game import entities as E
    return {"standard": E.Enemy, "hunter": E.Hunter, "swarm": E.SwarmNode, "phantom": E.Phantom,
            "berserker": E.Berserker, "teleporter": E.Teleporter,
            "shield_drone": E.ShieldDrone, "splitter": E.Splitter, "sniper": E.Sniper}[t]


def _perk_key(s: str) -> str:
    s = s.lower().replace("-", "_")
    if s not in PERKS:
        raise CommandError(f"unknown perk '{s}'. try: perks")
    return s


_ON_OFF = ["on", "off"]


# ── Commands: system ─────────────────────────────────────────────────────────

@command("help", "[command]", "List commands, or show help for one.", needs_game=False, aliases=("?",),
         complete=lambda a, c: sorted(COMMANDS))
def _help(ctx, args):
    if args:
        cmd = resolve(args[0])
        if not cmd:
            raise CommandError(f"unknown command '{args[0]}'")
        ctx.info(f"{cmd.name} {cmd.usage}".rstrip())
        ctx.dim("  " + cmd.help + ("   [CHEAT]" if cmd.cheat else ""))
        if cmd.aliases:
            ctx.dim("  aliases: " + ", ".join(cmd.aliases))
        return
    groups: dict[str, list[str]] = {}
    for c in COMMANDS.values():
        groups.setdefault(c.group, []).append(c.name + ("*" if c.cheat else ""))
    for g in ("system", "cheats", "world", "perks", "visual", "audio", "advanced"):
        if g in groups:
            ctx.info(f"{g:9s} " + "  ".join(sorted(groups[g])))
    ctx.dim("* = cheat (flags the run, score is not saved).   help <command> for details.")


@command("clear", "", "Clear the console log.", needs_game=False, aliases=("cls",))
def _clear(ctx, args):
    ctx.console.lines.clear()


@command("echo", "<text>", "Print text.", needs_game=False)
def _echo(ctx, args):
    ctx.info(" ".join(args))


@command("quit", "", "Exit the game.", needs_game=False, aliases=("exit",))
def _quit(ctx, args):
    ctx.manager.quit()


@command("menu", "", "Return to the main menu.", needs_game=False)
def _menu(ctx, args):
    from game.states.menu_state import MenuState
    ctx.console.open = False
    ctx.manager.replace_all(MenuState(ctx.manager))


@command("restart", "", "Restart the run (keeps daily mode).", needs_game=False)
def _restart(ctx, args):
    from game.states.play_state import PlayState
    ctx.console.open = False
    ctx.manager.replace_all(PlayState(ctx.manager, daily=bool(ctx.game and ctx.game.daily)))


@command("seed", "", "Show the run's seed / daily date.")
def _seed(ctx, args):
    g = ctx.game
    ctx.info(f"seed: {g.seed}   daily: {g.daily_date}" if g.daily else "seed: none (random run)")


@command("debug", "[on|off]", "FPS / entity-count overlay (same as F3).", complete=lambda a, c: _ON_OFF)
def _debug(ctx, args):
    g = ctx.game
    g.show_debug = _flag(args, 0, g.show_debug)
    ctx.ok(f"debug overlay {'ON' if g.show_debug else 'OFF'}")


# ── Commands: player cheats ──────────────────────────────────────────────────

@command("god", "[on|off]", "Invulnerability.", group="cheats", cheat=True, aliases=("iddqd",),
         complete=lambda a, c: _ON_OFF)
def _god(ctx, args):
    g = ctx.game
    g.god = _flag(args, 0, g.god)
    ctx.ok(f"god mode {'ON' if g.god else 'OFF'}")


@command("hp", "<n>", "Set hit points (1-99).", group="cheats", cheat=True)
def _hp(ctx, args):
    ctx.game.hp = _num(args, 0, 1, 99, "hp", integer=True)
    ctx.ok(f"hp = {ctx.game.hp}")


@command("heal", "", "Restore HP to at least 3.", group="cheats", cheat=True)
def _heal(ctx, args):
    ctx.game.hp = max(ctx.game.hp, 3)
    ctx.ok(f"hp = {ctx.game.hp}")


@command("energy", "<0-100|full>", "Set chaos energy.", group="cheats", cheat=True,
         complete=lambda a, c: ["full"])
def _energy(ctx, args):
    p = ctx.player
    if args and args[0].lower() == "full":
        p.energy = p.max_energy
    else:
        p.energy = _num(args, 0, 0, p.max_energy, "energy")
    ctx.ok(f"energy = {p.energy:g}")


@command("chaos", "[seconds|off]", "Start (or stop) Chaos Mode.", group="cheats", cheat=True,
         complete=lambda a, c: ["off"])
def _chaos(ctx, args):
    p = ctx.player
    if args and args[0].lower() == "off":
        p.chaos_mode, p.chaos_timer = False, 0.0
        ctx.ok("chaos OFF")
        return
    secs = _num(args, 0, 1, 600, "seconds", default=10.0)
    p.energy, p.chaos_mode, p.chaos_timer = p.max_energy, True, secs
    ctx.ok(f"chaos ON for {secs:g}s")


@command("speed", "<x>", "Player speed multiplier (0.1-5).", group="cheats", cheat=True)
def _speed(ctx, args):
    ctx.player.speed_mult = _num(args, 0, 0.1, 5, "multiplier")
    ctx.ok(f"speed x{ctx.player.speed_mult:g}")


@command("dmg", "<x>", "Damage multiplier for all weapons (0.1-1000).", group="cheats", cheat=True,
         aliases=("damage",))
def _dmg(ctx, args):
    ctx.game.dmg_mult = _num(args, 0, 0.1, 1000, "multiplier")
    ctx.ok(f"damage x{ctx.game.dmg_mult:g}")


@command("firerate", "<x>", "Fire-rate multiplier (0.1-20; 2 = twice as fast).", group="cheats", cheat=True)
def _firerate(ctx, args):
    x = _num(args, 0, 0.1, 20, "multiplier")
    ctx.player.fire_mult = 1.0 / x
    ctx.ok(f"fire rate x{x:g}")


@command("infdash", "[on|off]", "Unlimited dashes.", group="cheats", cheat=True, complete=lambda a, c: _ON_OFF)
def _infdash(ctx, args):
    p = ctx.player
    p.infinite_dash = _flag(args, 0, p.infinite_dash)
    p.dash_charges = p.max_dash_charges
    ctx.ok(f"infinite dash {'ON' if p.infinite_dash else 'OFF'}")


@command("dash", "<n>", "Set current dash charges (0-10).", group="cheats", cheat=True)
def _dash(ctx, args):
    ctx.player.dash_charges = _num(args, 0, 0, 10, "charges", integer=True)
    ctx.ok(f"dash charges = {ctx.player.dash_charges}")


@command("tp", "<x> <y>", "Teleport the player (0-1280, 0-720).", group="cheats", cheat=True,
         aliases=("teleport",))
def _tp(ctx, args):
    x, y = _num(args, 0, 0, W, "x"), _num(args, 1, 0, H, "y")
    ctx.player.pos.update(x, y)
    ctx.ok(f"teleported to ({x:g}, {y:g})")


@command("weapon", "<1-5>", "Select a weapon.", group="cheats", cheat=True)
def _weapon(ctx, args):
    ctx.player.weapon_index = _num(args, 0, 1, 5, "weapon", integer=True) - 1
    ctx.ok(f"weapon {ctx.player.weapon_index + 1}")


# ── Commands: world cheats ───────────────────────────────────────────────────

@command("spawn", "<type> [n] [x y]", "Spawn enemies.", group="world", cheat=True,
         complete=lambda a, c: list(ENEMY_TYPES) if len(a) == 1 else [])
def _spawn(ctx, args):
    if not args:
        raise CommandError("usage: spawn <type> [n] [x y]")
    t = _enemy_type(args[0])
    n = _num(args, 1, 1, 500, "count", default=1, integer=True)
    pos = (_num(args, 2, 0, W, "x"), _num(args, 3, 0, H, "y")) if len(args) >= 4 else None
    before = len(ctx.game.enemies)
    for _ in range(n):
        if pos:
            ctx.game._spawn_entity(t, *pos)
        else:
            ctx.game._spawn_entity(t)
    ctx.ok(f"spawned {len(ctx.game.enemies) - before} x {t}")


@command("kill", "[all|type]", "Kill enemies (and the boss with 'all').", group="world", cheat=True,
         complete=lambda a, c: ["all"] + list(ENEMY_TYPES))
def _kill(ctx, args):
    if not args or args[0].lower() == "all":
        n = ctx.game.kill_all()
    else:
        n = ctx.game.kill_all(_enemy_class(_enemy_type(args[0])))
    ctx.ok(f"killed {n}")


@command("killbullets", "", "Erase all enemy bullets.", group="world", cheat=True)
def _killbullets(ctx, args):
    ctx.game._clear_bullets()
    ctx.ok("bullets cleared")


@command("freeze", "[on|off]", "Freeze enemies, boss and bullets.", group="world", cheat=True,
         complete=lambda a, c: _ON_OFF)
def _freeze(ctx, args):
    g = ctx.game
    g.freeze_enemies = _flag(args, 0, g.freeze_enemies)
    ctx.ok(f"enemies {'FROZEN' if g.freeze_enemies else 'moving'}")


@command("timescale", "<x>", "Game speed (0.1-5).", group="world", cheat=True, aliases=("ts",))
def _timescale(ctx, args):
    ctx.game.time_scale = _num(args, 0, 0.1, 5, "scale")
    ctx.ok(f"time scale x{ctx.game.time_scale:g}")


@command("wave", "<n>", "Jump to wave n (clears the arena).", group="world", cheat=True)
def _wave(ctx, args):
    n = _num(args, 0, 1, 999, "wave", integer=True)
    ctx.game.set_wave(n)
    ctx.ok(f"jumping to wave {n}")


@command("nextwave", "", "Skip to the next wave.", group="world", cheat=True, aliases=("skip",))
def _nextwave(ctx, args):
    ctx.game.set_wave(ctx.game.wave_mgr.wave + 1)
    ctx.ok(f"jumping to wave {ctx.game.wave_mgr.wave + 1}")


@command("boss", "[architect|prism] [tier]", "Spawn a boss.", group="world", cheat=True,
         complete=lambda a, c: list(BOSS_KINDS) if len(a) == 1 else [])
def _boss(ctx, args):
    kind = (args[0].lower() if args else "architect")
    if kind not in BOSS_KINDS:
        raise CommandError(f"boss kinds: {', '.join(BOSS_KINDS)}")
    tier = _num(args, 1, 0, 20, "tier", default=0, integer=True)
    ctx.game.spawn_boss(kind, tier)
    ctx.ok(f"spawned {ctx.game.boss.name} (tier {tier})")


@command("score", "<n>", "Set score.", group="world", cheat=True)
def _score(ctx, args):
    ctx.game.score = _num(args, 0, 0, 10 ** 9, "score", integer=True)
    ctx.ok(f"score = {ctx.game.score}")


@command("streak", "<n>", "Set kill streak.", group="world", cheat=True)
def _streak(ctx, args):
    g = ctx.game
    g.streak = _num(args, 0, 0, 999, "streak", integer=True)
    g.streak_timer = STREAK_RESET_TIME
    ctx.ok(f"streak = {g.streak} (x{g._streak_mult():g})")


# ── Commands: perks ──────────────────────────────────────────────────────────

_PERK_KEYS = lambda a, c: list(PERKS) + (["all"] if len(a) == 1 else [])


@command("perk", "<key|all> [stacks]", "Grant a perk (up to its stack cap).", group="perks", cheat=True,
         complete=_PERK_KEYS)
def _perk(ctx, args):
    if not args:
        raise CommandError("usage: perk <key|all> [stacks]")
    keys = list(PERKS) if args[0].lower() == "all" else [_perk_key(args[0])]
    stacks = 99 if args[0].lower() == "all" else _num(args, 1, 1, 99, "stacks", default=1, integer=True)
    for k in keys:
        for _ in range(stacks):
            ctx.game.grant_perk(k)
    ctx.ok("perks: " + (", ".join(f"{k} x{n}" for k, n in ctx.game.perks.items()) or "none"))


@command("perks", "", "List all perks and your stacks.", group="perks")
def _perks(ctx, args):
    for k, p in PERKS.items():
        ctx.info(f"{k:12s} {ctx.game.perks.get(k, 0)}/{p.max_stacks}   {p.desc}")


@command("unperk", "<key>", "Remove a perk.", group="perks", cheat=True, complete=lambda a, c: list(PERKS))
def _unperk(ctx, args):
    if not args:
        raise CommandError("usage: unperk <key>")
    k = _perk_key(args[0])
    ctx.game.perks.pop(k, None)
    ctx.player.dash_charges = min(ctx.player.dash_charges, ctx.player.max_dash_charges)
    ctx.ok(f"removed {k}")


@command("clearperks", "", "Remove every perk.", group="perks", cheat=True)
def _clearperks(ctx, args):
    ctx.game.perks.clear()
    ctx.player.dash_charges = min(ctx.player.dash_charges, ctx.player.max_dash_charges)
    ctx.ok("all perks removed")


# ── Commands: visuals & audio (not cheats) ───────────────────────────────────

@command("bloom", "[on|off|0-2]", "Bloom post-effect on/off or strength.", group="visual",
         complete=lambda a, c: _ON_OFF)
def _bloom(ctx, args):
    r = ctx.game.renderer
    if args and args[0].lower() not in ("on", "off", "true", "false", "1", "0"):
        r.bloom_strength = _num(args, 0, 0, 2, "strength")
        r.bloom_enabled = r.bloom_strength > 0
    elif args and args[0] == "1":
        r.bloom_enabled = True
    else:
        r.bloom_enabled = _flag(args, 0, r.bloom_enabled)
    ctx.ok(f"bloom {'ON' if r.bloom_enabled else 'OFF'}  (strength {r.bloom_strength:g})")


@command("theme", "<0-3|auto>", "Background theme (auto = by wave).", group="visual",
         complete=lambda a, c: ["auto", "0", "1", "2", "3"])
def _theme(ctx, args):
    r = ctx.game.renderer
    if not args or args[0].lower() == "auto":
        r.theme_auto = True
        r.set_theme(min(3, ctx.game.wave_mgr.wave // 5))
        ctx.ok("theme: auto (follows the wave)")
    else:
        r.theme_auto = False
        r.set_theme(_num(args, 0, 0, 3, "theme", integer=True))
        ctx.ok(f"theme {r._theme}")


@command("vignette", "<0-1>", "Edge darkening (0 = off).", group="visual")
def _vignette(ctx, args):
    ctx.game.renderer.set_vignette(_num(args, 0, 0, 1, "amount"))
    ctx.ok(f"vignette {ctx.game.renderer.vignette:g}")


@command("shake", "<n>", "Trigger screen shake (0-40).", group="visual")
def _shake(ctx, args):
    ctx.game.shake = _num(args, 0, 0, 40, "amount")


@command("music", "[on|off]", "Reactive music on/off.", group="audio", complete=lambda a, c: _ON_OFF)
def _music(ctx, args):
    m = ctx.game.music
    on = _flag(args, 0, m._playing)
    m.start() if on else m.stop()
    ctx.ok(f"music {'ON' if on else 'OFF'}")


@command("volume", "<0-1>", "Master volume.", group="audio")
def _volume(ctx, args):
    ctx.game.audio.volume = _num(args, 0, 0, 1, "volume")
    ctx.ok(f"volume {ctx.game.audio.volume:g}")


@command("mute", "", "Toggle mute (same as M).", group="audio")
def _mute(ctx, args):
    ctx.game.audio.toggle_mute()
    ctx.ok("mute toggled")


# ── Commands: advanced get / set ─────────────────────────────────────────────

_SIMPLE = (bool, int, float, str)


def _roots(game) -> dict:
    return {"game": game, "player": game.player, "wave": game.wave_mgr,
            "renderer": game.renderer, "audio": game.audio}


def _walk(ctx, path: str, parent: bool = False):
    parts = path.split(".")
    roots = _roots(ctx.game)
    if parts[0] not in roots:
        raise CommandError(f"unknown root '{parts[0]}'. roots: {', '.join(roots)}")
    obj = roots[parts[0]]
    steps = parts[1:-1] if parent else parts[1:]
    for name in steps:
        if name.startswith("_") or not name.isidentifier() or not hasattr(obj, name):
            raise CommandError(f"no attribute '{name}'")
        obj = getattr(obj, name)
    return obj, (parts[-1] if parent else None), parts[0]


@command("get", "[root[.attr]]", "Inspect a value, or list an object's simple attributes.",
         group="advanced", complete=lambda a, c: ["game.", "player.", "wave.", "renderer.", "audio."])
def _get(ctx, args):
    if not args:
        ctx.info("roots: " + ", ".join(_roots(ctx.game)))
        return
    obj, _, _ = _walk(ctx, args[0])
    if isinstance(obj, _SIMPLE):
        ctx.info(f"{args[0]} = {obj!r}")
        return
    shown = [f"{k} = {v!r}" for k, v in sorted(vars(obj).items())
             if not k.startswith("_") and isinstance(v, _SIMPLE)]
    ctx.info("\n".join(shown) if shown else "(no simple attributes)")


@command("set", "<root.attr> <value>", "Change an existing int/float/bool/str attribute (flags the run if the root is game/player/wave).",
         group="advanced", complete=lambda a, c: ["game.", "player.", "wave.", "renderer.", "audio."])
def _set(ctx, args):
    if len(args) < 2:
        raise CommandError("usage: set <root.attr> <value>")
    parent, attr, root = _walk(ctx, args[0], parent=True)
    if attr.startswith("_") or not attr.isidentifier() or not hasattr(parent, attr):
        raise CommandError(f"no attribute '{attr}'")
    cur = getattr(parent, attr)
    if not isinstance(cur, _SIMPLE):
        raise CommandError(f"'{attr}' is not a simple value (int/float/bool/str)")
    raw = " ".join(args[1:])
    if isinstance(cur, bool):
        if raw.lower() not in ("on", "off", "true", "false", "1", "0"):
            raise CommandError("expected on/off/true/false")
        val = raw.lower() in ("on", "true", "1")
    elif isinstance(cur, str):
        val = raw
    else:
        try:
            val = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            raise CommandError(f"cannot parse '{raw}' as a number")
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            raise CommandError("expected a number")
        val = int(val) if isinstance(cur, int) and float(val).is_integer() else val
        if isinstance(cur, int) and not isinstance(val, int):
            raise CommandError(f"'{attr}' is an integer")
    setattr(parent, attr, val)
    if root in ("game", "player", "wave"):
        ctx._cheat = True
    ctx.ok(f"{args[0]} = {val!r}")


# ── The console object ───────────────────────────────────────────────────────

class Console:
    MAX_LINES = 300
    HEIGHT    = 372

    def __init__(self, manager) -> None:
        self.manager   = manager
        self.open      = False
        self.lines: list[tuple[str, str]] = []
        self.input     = ""
        self.history: list[str] = []
        self._hist_i: int | None = None
        self.scroll    = 0
        self._blink    = 0.0
        self._font     = None
        self._prev_mouse_visible = True
        self._q: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self.terminal_enabled = False
        self._echo     = False        # mirror output to the terminal while a terminal command runs
        self.print("The Blade's Playground console — type 'help'.  ` or F10 closes.", "dim", terminal=False)

    @property
    def game(self):
        return getattr(self.manager, "active_game", None)

    # ── output ────────────────────────────────────────────────────────────────

    def print(self, text, kind: str = "info", terminal: bool = True) -> None:
        for ln in str(text).split("\n"):
            self.lines.append((ln, kind))
            if terminal and self._echo:
                print(ln, flush=True)
        if len(self.lines) > self.MAX_LINES:
            del self.lines[:len(self.lines) - self.MAX_LINES]
        if self.scroll:
            self.scroll = 0

    # ── execution ─────────────────────────────────────────────────────────────

    def execute(self, line: str, source: str = "console") -> None:
        line = line.strip()
        if not line:
            return
        self._echo = source == "terminal"
        self.print(f"> {line}", "input", terminal=False)
        try:
            try:
                parts = shlex.split(line)
            except ValueError as exc:
                raise CommandError(f"parse error: {exc}")
            cmd = resolve(parts[0])
            if cmd is None:
                raise CommandError(f"unknown command '{parts[0]}' — try 'help'")
            ctx = Ctx(self)
            if cmd.needs_game and ctx.game is None:
                raise CommandError("no active game — start a run first")
            cmd.fn(ctx, parts[1:])
            if (cmd.cheat or ctx._cheat) and ctx.game is not None and not ctx.game.cheated:
                ctx.game.cheated = True
                self.print("CHEATS ENABLED — this run will not be saved to the scores.", "cheat")
        except CommandError as exc:
            self.print(str(exc), "err")
        except Exception as exc:                    # a command bug must never crash the game
            self.print(f"{type(exc).__name__}: {exc}", "err")
        finally:
            self._echo = False

    # ── terminal (stdin) bridge ───────────────────────────────────────────────

    def start_terminal(self) -> None:
        if self._thread is not None:
            return
        self.terminal_enabled = True

        def reader() -> None:
            try:
                for raw in sys.stdin:
                    raw = raw.strip()
                    if raw:
                        self._q.put(raw)
            except Exception:
                pass

        self._thread = threading.Thread(target=reader, daemon=True, name="console-stdin")
        self._thread.start()
        print("[terminal] control enabled — type commands here ('help' lists them).", flush=True)

    # ── per-frame ─────────────────────────────────────────────────────────────

    def update(self, dt: float) -> None:
        self._blink += dt
        while True:
            try:
                self.execute(self._q.get_nowait(), "terminal")
            except queue.Empty:
                break

    def toggle(self) -> None:
        self.open = not self.open
        self.scroll = 0
        self._hist_i = None
        if self.open:
            self._prev_mouse_visible = pygame.mouse.set_visible(True)
        else:
            pygame.mouse.set_visible(bool(self._prev_mouse_visible))

    # ── input ─────────────────────────────────────────────────────────────────

    def complete(self) -> None:
        text = self.input
        parts = text.split(" ")
        if len(parts) == 1:
            pool = sorted(set(COMMANDS) | set(_ALIAS))
            word, prefix = parts[0].lower(), ""
        else:
            cmd = resolve(parts[0])
            if not cmd or not cmd.complete:
                return
            try:
                pool = list(cmd.complete(parts[1:], self))
            except Exception:
                return
            word, prefix = parts[-1].lower(), " ".join(parts[:-1]) + " "
        matches = [m for m in pool if m.lower().startswith(word)]
        if not matches:
            return
        if len(matches) == 1:
            self.input = prefix + matches[0] + ("" if matches[0].endswith(".") else " ")
            return
        common = matches[0]
        for m in matches[1:]:
            while not m.lower().startswith(common.lower()):
                common = common[:-1]
        self.input = prefix + common
        self.print("  ".join(matches[:24]) + (" …" if len(matches) > 24 else ""), "dim", terminal=False)

    def handle_events(self, events: list) -> None:
        for ev in events:
            if ev.type == pygame.MOUSEWHEEL:
                self.scroll = max(0, self.scroll + ev.y * 3)
            if ev.type != pygame.KEYDOWN:
                continue
            k = ev.key
            if k == pygame.K_ESCAPE:
                self.toggle()
            elif k in (pygame.K_RETURN, pygame.K_KP_ENTER):
                line, self.input, self._hist_i = self.input, "", None
                if line.strip():
                    if not self.history or self.history[-1] != line:
                        self.history.append(line)
                    self.execute(line)
            elif k == pygame.K_BACKSPACE:
                self.input = self.input[:-1]
            elif k == pygame.K_TAB:
                self.complete()
            elif k == pygame.K_UP and self.history:
                self._hist_i = len(self.history) - 1 if self._hist_i is None else max(0, self._hist_i - 1)
                self.input = self.history[self._hist_i]
            elif k == pygame.K_DOWN and self._hist_i is not None:
                self._hist_i += 1
                if self._hist_i >= len(self.history):
                    self._hist_i, self.input = None, ""
                else:
                    self.input = self.history[self._hist_i]
            elif k == pygame.K_PAGEUP:
                self.scroll = min(max(0, len(self.lines) - 1), self.scroll + 8)
            elif k == pygame.K_PAGEDOWN:
                self.scroll = max(0, self.scroll - 8)
            elif k == pygame.K_l and ev.mod & pygame.KMOD_CTRL:
                self.lines.clear()
            elif k == pygame.K_u and ev.mod & pygame.KMOD_CTRL:
                self.input = ""
            elif ev.unicode and ev.unicode.isprintable() and len(self.input) < 200:
                self.input += ev.unicode

    # ── drawing ───────────────────────────────────────────────────────────────

    def draw(self, surf: pygame.Surface) -> None:
        if not self.open:
            return
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", 14)
        f, h = self._font, self.HEIGHT
        alpha_rect(surf, (5, 7, 16), (0, 0, W, h), 238)
        pygame.draw.line(surf, (0, 200, 160), (0, h), (W, h), 2)
        game = self.game
        tag = ("no active game" if game is None else
               "CHEATED RUN" if game.cheated else "run clean")
        head = f.render(f"CONSOLE   [{tag}]", True, (255, 175, 70) if game and game.cheated else (0, 200, 160))
        surf.blit(head, (12, 6))
        hint = f.render("TAB complete   UP/DOWN history   PGUP/PGDN scroll   ESC or ` close", True, KIND_COLORS["dim"])
        surf.blit(hint, (W - hint.get_width() - 12, 6))

        line_h = 17
        rows = (h - 58) // line_h
        end = len(self.lines) - self.scroll
        for i, (text, kind) in enumerate(self.lines[max(0, end - rows):max(0, end)]):
            surf.blit(f.render(text[:150], True, KIND_COLORS.get(kind, KIND_COLORS["info"])),
                      (12, 28 + i * line_h))
        if self.scroll:
            m = f.render(f"-- scrolled {self.scroll} lines up --", True, KIND_COLORS["dim"])
            surf.blit(m, (W - m.get_width() - 12, h - 44))

        y = h - 24
        pygame.draw.line(surf, (40, 50, 80), (8, y - 4), (W - 8, y - 4), 1)
        cursor = "_" if int(self._blink * 2) % 2 == 0 else " "
        surf.blit(f.render("> " + self.input + cursor, True, KIND_COLORS["input"]), (12, y))
