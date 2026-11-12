#!/usr/bin/env python3
"""gen_docs.py — regenerate CONSOLE.md from the console's command registry (so it can't go stale).
   python tools/gen_docs.py          (a test fails if CONSOLE.md is out of date)"""
import os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy"); os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from game.console import COMMANDS

TITLES = {"system": "System", "cheats": "Player cheats", "world": "World cheats", "perks": "Perks",
          "visual": "Visuals", "audio": "Audio", "advanced": "Advanced (get / set)"}

def render() -> str:
    groups = {}
    for c in COMMANDS.values():
        groups.setdefault(c.group, []).append(c)
    md = ["# Console & terminal control", "",
          "Open the console in-game with **`** (backquote / tilde) or **F10**. The game pauses while it is open.",
          "Run the game from a terminal and the **same commands** work typed into that terminal "
          "(`--no-terminal` disables this; `--terminal` forces it when stdin isn't a TTY).", "",
          "**Tab** completes commands and arguments, **Up/Down** browse history, **PgUp/PgDn** scroll, **Ctrl+L** clears.", "",
          "## Cheats never touch your real scores", "",
          "Any command marked **cheat** flags the run as *cheated*: an on-screen tag appears and the run is **never written** "
          "to the high-score table, the daily board, or your progression (no shards, no achievements). "
          "Visual, audio and info commands do not flag the run.",
          "(`set`/`get` flag the run only when you change `game`, `player` or `wave` values.)", ""]
    for g in TITLES:
        if g not in groups:
            continue
        md += [f"## {TITLES[g]}", "", "| Command | What it does |", "|---|---|"]
        for c in sorted(groups[g], key=lambda c: c.name):
            tag = " **(cheat)**" if c.cheat else ""
            al = f" _(alias: {', '.join(c.aliases)})_" if c.aliases else ""
            md.append(f"| `{c.name} {c.usage}`".rstrip() + f" | {c.help}{tag}{al} |")
        md.append("")
    md += ["## Examples", "", "```", "god on", "perk all", "spawn berserker 5", "boss prism 2", "wave 15", "dmg 10",
           "timescale 0.3", "bloom 1.2", "theme 3", "set player.speed_mult 1.5", "get wave", "about", "```", ""]
    return "\n".join(md)

if __name__ == "__main__":
    (ROOT / "CONSOLE.md").write_text(render())
    print(f"CONSOLE.md regenerated ({len(COMMANDS)} commands)")
