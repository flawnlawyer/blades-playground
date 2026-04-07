# ⚔️ The Blade's Playground

> *You are a shadow navigating a world of broken code, digital ghosts, and entropy.*  
> *Hack the noise. Absorb the fragments. Survive long enough to go full chaos.*

---

![Python](https://img.shields.io/badge/Python-3.10%2B-blueviolet?style=flat-square)
![Pygame](https://img.shields.io/badge/Pygame-2.5%2B-green?style=flat-square)
![NumPy](https://img.shields.io/badge/NumPy-1.24%2B-blue?style=flat-square)
![Status](https://img.shields.io/badge/Status-v1.0%20playable-brightgreen?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-lightgrey?style=flat-square)

A dark, glitchy top-down roguelike built in Python. No game engine. No external assets. Everything — movement, combat, audio, particles — is hand-coded and runs locally.

---

## What It Is

The Blade's Playground is a fast-paced survival roguelike where you play as a shadow entity in a corrupted digital world. The loop is simple: hack broken objects to make them destructible, collect poetic code-fragments scattered across the grid, fill your energy meter, and unleash **Chaos Mode** before the corrupted entities tear you apart.

The aesthetic is intentionally raw — dark grid, chromatic aberration, glitch scanlines, particle bursts. The audio is procedurally synthesized at runtime with NumPy. No sound files. No sprite sheets. Just math and motion.

---

## Gameplay

### Core Loop
```
Move → Hack "meh blocks" → Destroy them → Fill energy → Trigger chaos → Survive
```

### Controls

| Key | Action |
|-----|--------|
| `WASD` / `↑↓←→` | Move |
| `SPACE` | Hack nearby objects / stun enemies |
| `M` | Toggle mute |
| `R` | Reboot (after game over) |
| `ESC` | Quit |

### Mechanics

**Meh Blocks** — Gray blocks scattered across the world. They can't be destroyed raw — you have to hack them first (`SPACE`), which marks them for 3.5 seconds. While hacked, walking into them deals damage and eventually destroys them, rewarding energy and score.

**Fragments** — Floating cyan orbs containing poetic code lines. Collecting one displays the line on screen, gives a large energy burst, and scores points. New fragments spawn as you collect them.

**Energy Meter** — Fills as you destroy blocks and collect fragments. When it maxes out → Chaos Mode activates.

**Chaos Mode (9 seconds)** — Speed boost. Chromatic aberration tears the screen. Meh blocks shatter on contact. Enemies die on touch. Hack range doubles. Use it aggressively.

**Enemies** — Diamond-shaped corrupted entities. They wander until you're within 220px, then chase. Hacking stuns them for 2.5s. In chaos mode, you can walk straight through them.

---

## Installation

**Requirements:** Python 3.10+, pip

```bash
# Clone
git clone https://github.com/flawnlawyer/blades-playground.git
cd blades-playground

# Install dependencies
pip install -r requirements.txt

# Run
python main.py
```

That's it. No build step. No config. Runs on Windows, macOS, Linux.

---

## Project Structure

```
blades-playground/
│
├── main.py                  # Entry point
├── requirements.txt
├── .gitignore
├── README.md
│
├── game/
│   ├── __init__.py
│   ├── constants.py         # All tuning values, colors, fragment pool
│   ├── player.py            # Player class — movement, energy, chaos state
│   ├── entities.py          # MehBlock, Fragment, Enemy
│   ├── particles.py         # Particle system
│   ├── audio.py             # Procedural SFX synthesis (NumPy)
│   ├── renderer.py          # Background grid, glitch lines, chromatic FX
│   ├── ui.py                # HUD, fragment popup, game over overlay
│   └── game.py              # Game loop, collision, state, spawn logic
│
└── utils/
    ├── __init__.py
    └── helpers.py           # glow_circle, alpha_rect, clamp
```

Each module has one job. `game.py` orchestrates — it doesn't render, synthesize, or define entities directly. You can swap any module without touching the others.

---

## Audio

All sound effects are synthesised procedurally at startup using NumPy. No `.wav` or `.mp3` files.

| Sound | Trigger | Technique |
|-------|---------|-----------|
| `hack` | SPACE pressed | Frequency sweep 300→900Hz + noise grain |
| `meh_hack` | Block hacked | Two-tone beep |
| `meh_destroy` | Block destroyed | Noise burst + low click |
| `fragment_collect` | Fragment absorbed | A4→C#5→E5 ascending arpeggio |
| `enemy_stun` | Enemy stunned | Descending sweep 800→200Hz |
| `chaos_activate` | Chaos mode on | Harmonic power surge |
| `chaos_end` | Chaos mode off | Three-note descending chime |
| `player_hit` | Hit by enemy | 80Hz thud + noise swell |
| `game_over` | HP hits zero | Descending glitch drone 400→60Hz |

Toggle mute with `M` at any time.

---

## Tuning

All gameplay values live in `game/constants.py`. Change anything without touching logic:

```python
PLAYER_SPEED        = 4.2    # base movement speed
CHAOS_DURATION      = 9.0    # seconds of chaos mode
HACK_RANGE_NORMAL   = 85     # hack radius (px)
FRAG_ENERGY_REWARD  = 22     # energy per fragment
ENEMY_SPEED_MIN     = 1.3    # enemy wander speed floor
```

---

## Roadmap

**v1.0** — current: full loop playable, all SFX, modular structure

**v2.0 — Procedural World**
- Room-based map generation with corridors and locked doors
- Fragment sets that unlock passive abilities (e.g. collect 3 → unlock dash)
- Persistent run meta: carry one fragment's ability into next run

**v3.0 — Escalation**
- Boss entity: The Architect (corrupted AI that mirrors your movement)
- Ambient music layer: generative drone that evolves with energy level
- Difficulty scaling: enemy speed + spawn rate increase per minute survived

**v4.0 — Deploy**
- WebAssembly build via Pygbag (play in browser)
- Leaderboard (local high-score persistence)
- Configurable keybindings

---

## Philosophy

This was built the same way everything I build gets built: ship a working v1 fast, then refactor only when adding v2 features. The code is modular not because modularity is virtuous in the abstract, but because it makes the next feature easier to wire in without breaking the last one.

No game engine. No asset pipeline. No bloat. Just Python doing what Python does — fast enough to be fun, expressive enough to stay weird.

---

## Author

**Ayush** (`@flawnlawyer`)  
Open-Source Developer · AI Safety Researcher · BCSIT @ Pokhara University

→ [github.com/flawnlawyer](https://github.com/flawnlawyer)

---

## License

MIT. Fork it, break it, ship something weirder.
