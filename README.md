# ⚔️ The Blade's Playground

> *You are a shadow navigating a world of broken code, digital ghosts, and entropy.*
> *Hack the noise. Absorb the fragments. Survive long enough to go full chaos.*

---

![Python](https://img.shields.io/badge/Python-3.10%2B-blueviolet?style=flat-square)
![Pygame](https://img.shields.io/badge/Pygame-2.5%2B-green?style=flat-square)
![NumPy](https://img.shields.io/badge/NumPy-1.24%2B-blue?style=flat-square)
![Version](https://img.shields.io/badge/Version-2.0-brightgreen?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-lightgrey?style=flat-square)

A dark, glitchy top-down survival roguelike built in pure Python. No game engine. No external assets. Everything — movement, weapons, waves, audio, particles, UI — is hand-coded and runs locally.

---

## Download

**[→ Download for Windows (.exe)](https://github.com/flawnlawyer/blades-playground/releases/latest)**

No Python required. Unzip and run.

---

## What It Is

Five weapons. Five enemy types. A boss that mirrors your movement. A wave system that never stops scaling. Procedurally synthesised audio built from NumPy math at runtime — zero sound files.

The loop: hack corrupted blocks to make them destructible → collect code fragments scattered across the grid → fill your energy → trigger **Chaos Mode** → tear everything apart before it wears off. Repeat until you die.

The aesthetic is intentionally raw: dark grid, chromatic aberration, CRT scanlines, glitch lines, screen flash on hit, particle bursts on every kill. It looks broken because the world is broken.

---

## Controls

| Input | Action |
|---|---|
| `WASD` / Arrow keys | Move |
| `SHIFT` | Dash (direction-based, 2 charges) |
| `SPACE` | Hack nearby blocks / stun enemies |
| `LMB` (hold) | Fire selected weapon |
| `1` `2` `3` `4` `5` | Switch weapon |
| `M` | Toggle mute |
| `ESC` | Pause |
| `F11` | Fullscreen |

---

## Weapons

| # | Name | Fire Mode | Notes |
|---|---|---|---|
| 1 | **Plasma Bolt** | Single shot | Fast, long range |
| 2 | **Void Spread** | 5-shot cone | Wide coverage |
| 3 | **Chain Zap** | Auto-chain | Jumps between 3 nearest enemies |
| 4 | **Null Beam** | Hold to sustain | Drains energy; aim precisely |
| 5 | **Chaos Bomb** | Lob (3 charges) | 1.4s fuse, large blast radius |

---

## Enemies

| Enemy | Behaviour | Threat |
|---|---|---|
| **Standard** | Wanders, chases within range | Low |
| **Hunter** | Always chasing, fast, faces you | Medium |
| **Swarm Node** | Small, very fast, spawns in packs | Medium |
| **Phantom** | Translucent, medium speed, 3HP | High |
| **The Architect** | Boss. Mirrors your position. Phase 2: mirrors both axes, spawns Hunters | Boss |

Hack (`SPACE`) stuns all enemy types for 2.5 seconds.
In Chaos Mode, contact with any enemy instantly destroys it.

---

## Mechanics

**Meh Blocks** — Gray blocks covering the arena. Raw contact does nothing. Hack first (`SPACE` within range), then walk into them while they're glowing to deal damage. Destroying one rewards energy and score.

**Fragments** — Floating cyan orbs containing poetic code lines. Collecting one displays the line on screen, gives a large energy burst, and scores 50 points. Each fragment text appears only once per run.

**Energy Meter** — Fills by destroying blocks and collecting fragments. When it maxes out, Chaos Mode activates automatically.

**Chaos Mode (10s)** — Speed ×1.9. Chromatic aberration tears the screen. Blocks shatter on contact. Enemies die on touch. Hack range doubled. Ambient drone pitch shifts. Use it. Don't waste it.

**Dash** — 2 charges, 1.2s recharge each. Directional — dashes toward your movement input, or toward the mouse if you're standing still. Invincibility frames active during dash.

**Wave System** — Waves of enemies spawn on a 4-second break timer. Waves 1–5 follow fixed definitions scaling in enemy type and count. Wave 5 spawns The Architect. Wave 6+ procedurally generates harder compositions indefinitely.

---

## Running From Source

```bash
git clone https://github.com/flawnlawyer/blades-playground.git
cd blades-playground
pip install -r requirements.txt
python main.py
```

Runs on Windows, macOS, Linux. Python 3.10+ required.

---

## Building the Windows EXE

The release binary is built with [Nuitka](https://nuitka.net):

```bash
pip install nuitka pygame numpy
python -m nuitka --onefile --windows-disable-console \
  --include-data-dir=assets=assets \
  --include-data-dir=data=data \
  --include-package=game \
  --include-package=utils \
  main.py
```

Output: `main.exe` — single file, no Python runtime required.

---

## Project Structure

```
blades-playground/
│
├── main.py                        # Entry point + resource_path helper
├── requirements.txt
│
├── game/
│   ├── constants.py               # All tuning values, colors, fragment pool
│   ├── state_manager.py           # Pushdown automaton + fade transitions + scaling
│   ├── game.py                    # Core loop: entities, physics, collision
│   ├── player.py                  # Movement, dash, 5-weapon system, mouse aim
│   ├── entities.py                # MehBlock, Fragment, all enemy types, Projectile
│   ├── particles.py               # Particle, Spark, Ring, DashTrail, TextPopup
│   ├── wave_manager.py            # Wave definitions, spawn scheduling
│   ├── renderer.py                # Background, vignette, scanlines, flash, chromatic
│   ├── audio.py                   # Procedural SFX + ambient drone (NumPy only)
│   ├── ui.py                      # HUD, weapon bar, boss bar, wave banner
│   └── states/
│       ├── loading_state.py       # Animated logo + progress bar
│       ├── menu_state.py          # Main menu with slide-in items
│       ├── play_state.py          # Wraps Game, handles pause/gameover transitions
│       ├── pause_state.py         # Overlay pause menu
│       ├── gameover_state.py      # Score display + high score entry
│       ├── highscores_state.py    # Top-10 leaderboard table
│       └── settings_state.py      # Volume slider + fullscreen toggle
│
├── utils/
│   ├── helpers.py                 # glow_circle, alpha_rect, lerp_color, rotate_points
│   └── data_manager.py            # JSON save/load for scores and settings
│
├── assets/
│   └── logo.png
│
└── data/
    └── highscores.json            # Created on first run
```

Each module has one job. `game.py` orchestrates — it never renders or defines entities directly. The state machine handles all screen transitions with fade effects and logical-resolution scaling (fixed 1280×720 rendered to any window size with letterboxing).

---

## Audio

All 20 sounds are synthesised at startup using NumPy. Zero `.wav` or `.mp3` files anywhere.

| Sound | Trigger | Synthesis |
|---|---|---|
| `plasma_shoot` | Fire weapon 1 | Sweep 600→1200Hz |
| `spread_shoot` | Fire weapon 2 | Stacked sweeps × 5 |
| `chain_zap` | Fire weapon 3 | Sweep + noise + random crackle |
| `beam_hum` | Beam held | 220Hz buzz + harmonic |
| `bomb_launch` | Fire weapon 5 | Low sweep + noise |
| `bomb_explode` | Fuse detonates | Noise + bass sweep + sub sine |
| `dash` | SHIFT | 50→180Hz whoosh |
| `hack` | SPACE | 300→900Hz + grain |
| `chaos_activate` | Energy maxes | Harmonic surge |
| `chaos_end` | Chaos expires | Three-note descent |
| `player_hit` | Take damage | 80Hz thud + swell |
| `boss_spawn` | Wave 5 starts | 800→30Hz descent + harmonics |
| `boss_hit` | Damage The Architect | Metallic clank |
| `game_over` | HP hits zero | 400→60Hz descending drone |
| `fragment_collect` | Touch a fragment | A4→C#5→E5 arpeggio |
| `level_up` | Boss killed | C5→E5→G5 chord |
| Ambient drone | Always | Generative — pitch shifts 60→110Hz with energy level; chaos variant adds harmonics |

---

## Tuning

All gameplay values live in `game/constants.py`. Nothing is hardcoded in logic files.

```python
PLAYER_SPEED           = 4.5
CHAOS_DURATION         = 10.0    # seconds
PLAYER_DASH_CHARGES    = 2
PLAYER_DASH_CHARGE_CD  = 1.2     # seconds per recharge
HACK_RANGE_NORMAL      = 90
CHAIN_LINKS            = 3       # max chain zap targets
BOMB_RADIUS            = 130
BOSS_HP                = 15
BOSS_PHASE2_HP         = 7       # phase transition threshold
WAVE_BREAK_DURATION    = 4.0     # seconds between waves
```

---

## Philosophy

Built the same way everything I build gets built: ship a working v1 fast, fix everything in v2. The code is modular not because modularity is virtuous in the abstract, but because it makes the next feature easier to wire without breaking the last one.

No game engine. No asset pipeline. No bloat. Just Python doing what Python does — fast enough to be fun, expressive enough to stay weird.

The fragment pool is the soul of this game. Every line in it is real.

---

## Author

**Ayush** (`@flawnlawyer`)
Open-Source Developer · AI Safety Researcher · BCSIT @ Pokhara University

→ [github.com/flawnlawyer](https://github.com/flawnlawyer)

---

## License

MIT. Fork it, break it, ship something weirder.
