# Console & terminal control

Open the console in-game with **`** (backquote / tilde) or **F10**. The game pauses while it is open.
Run the game from a terminal and the **same commands** work typed into that terminal (`--no-terminal` disables this; `--terminal` forces it when stdin isn't a TTY).

**Tab** completes commands and arguments, **Up/Down** browse history, **PgUp/PgDn** scroll, **Ctrl+L** clears.

## Cheats never touch your real scores

Any command marked **cheat** flags the run as *cheated*: an on-screen tag appears and the run is **never written** to the high-score table or the daily board. Visual, audio and info commands do not flag the run.
(`set`/`get` flag the run only when you change `game`, `player` or `wave` values.)

## System

| Command | What it does |
|---|---|
| `clear ` | Clear the console log. _(alias: cls)_ |
| `debug [on|off]` | FPS / entity-count overlay (same as F3). |
| `echo <text>` | Print text. |
| `help [command]` | List commands, or show help for one. _(alias: ?)_ |
| `menu ` | Return to the main menu. |
| `quit ` | Exit the game. _(alias: exit)_ |
| `restart ` | Restart the run (keeps daily mode). |
| `seed ` | Show the run's seed / daily date. |

## Player cheats

| Command | What it does |
|---|---|
| `chaos [seconds|off]` | Start (or stop) Chaos Mode. **(cheat)** |
| `dash <n>` | Set current dash charges (0-10). **(cheat)** |
| `dmg <x>` | Damage multiplier for all weapons (0.1-1000). **(cheat)** _(alias: damage)_ |
| `energy <0-100|full>` | Set chaos energy. **(cheat)** |
| `firerate <x>` | Fire-rate multiplier (0.1-20; 2 = twice as fast). **(cheat)** |
| `god [on|off]` | Invulnerability. **(cheat)** _(alias: iddqd)_ |
| `heal ` | Restore HP to at least 3. **(cheat)** |
| `hp <n>` | Set hit points (1-99). **(cheat)** |
| `infdash [on|off]` | Unlimited dashes. **(cheat)** |
| `speed <x>` | Player speed multiplier (0.1-5). **(cheat)** |
| `tp <x> <y>` | Teleport the player (0-1280, 0-720). **(cheat)** _(alias: teleport)_ |
| `weapon <1-5>` | Select a weapon. **(cheat)** |

## World cheats

| Command | What it does |
|---|---|
| `boss [architect|prism] [tier]` | Spawn a boss. **(cheat)** |
| `freeze [on|off]` | Freeze enemies, boss and bullets. **(cheat)** |
| `kill [all|type]` | Kill enemies (and the boss with 'all'). **(cheat)** |
| `killbullets ` | Erase all enemy bullets. **(cheat)** |
| `nextwave ` | Skip to the next wave. **(cheat)** _(alias: skip)_ |
| `score <n>` | Set score. **(cheat)** |
| `spawn <type> [n] [x y]` | Spawn enemies. **(cheat)** |
| `streak <n>` | Set kill streak. **(cheat)** |
| `timescale <x>` | Game speed (0.1-5). **(cheat)** _(alias: ts)_ |
| `wave <n>` | Jump to wave n (clears the arena). **(cheat)** |

## Perks

| Command | What it does |
|---|---|
| `clearperks ` | Remove every perk. **(cheat)** |
| `perk <key|all> [stacks]` | Grant a perk (up to its stack cap). **(cheat)** |
| `perks ` | List all perks and your stacks. |
| `unperk <key>` | Remove a perk. **(cheat)** |

## Visuals

| Command | What it does |
|---|---|
| `bloom [on|off|0-2]` | Bloom post-effect on/off or strength. |
| `shake <n>` | Trigger screen shake (0-40). |
| `theme <0-3|auto>` | Background theme (auto = by wave). |
| `vignette <0-1>` | Edge darkening (0 = off). |

## Audio

| Command | What it does |
|---|---|
| `music [on|off]` | Reactive music on/off. |
| `mute ` | Toggle mute (same as M). |
| `volume <0-1>` | Master volume. |

## Advanced (get / set)

| Command | What it does |
|---|---|
| `get [root[.attr]]` | Inspect a value, or list an object's simple attributes. |
| `set <root.attr> <value>` | Change an existing int/float/bool/str attribute (flags the run if the root is game/player/wave). |

## Examples

```
god on
perk all
spawn berserker 5
boss prism 2
wave 15
dmg 10
timescale 0.3
bloom 1.2
theme 3
set player.speed_mult 1.5
get wave
```
