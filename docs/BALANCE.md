# Balance

How the game's difficulty was tuned, what the data does and doesn't say, and how to reproduce it.

## The tool, and its limits

`tools/balance_bot.py` plays the **real game headlessly** (it drives `Game.input_source`, the same code path as a human).
It kites, dodges bullets and sniper lasers, hacks and dashes when threatened, picks a weapon by situation, and
fights bosses with the beam. Three skill levels change how often it "thinks" and how often it misses a dodge.

**It is a fixed, mediocre player.** Results are only meaningful as *relative* comparisons (this wave is a spike;
perk A beats perk B for this bot). They are **not** a prediction of how a human will do — a human will die far
earlier in the opening waves, and the bot's habits bias which perks look useful (see below).

## Finding 1 — perk power outran enemy scaling

With **no perks** every bot died around waves 10–13: a sensible base-game curve. With a perk after **every**
wave, the same bot reached wave 24+ (my 5-minute time cap) and almost never died — by mid-game it held nearly
every perk at max while enemy scaling stayed linear.

**Change shipped:** perks are offered every **2nd** cleared wave, plus every boss wave (`game/tuning.py`, `perk_every = 2`).

| Bot skill | Perks | Runs | Died | Median wave | Reached w13 | w16 | w19 | w22 |
|---|---|---|---|---|---|---|---|---|
| novice | none (reference) | 30 | 30/30 | 10 | 3% | 0% | 0% | 0% |
| novice | **shipped** (every 2nd wave + boss waves) | 30 | 27/30 | 12 | 43% | 20% | 10% | 0% |
| average | none (reference) | 30 | 30/30 | 12 | 33% | 0% | 0% | 0% |
| average | **shipped** (every 2nd wave + boss waves) | 30 | 15/30 | 19 | 93% | 70% | 53% | 7% |
| skilled | none (reference) | 30 | 30/30 | 13 | 57% | 10% | 0% | 0% |
| skilled | **shipped** (every 2nd wave + boss waves) | 30 | 5/30 | 21 | 100% | 90% | 83% | 27% |

*(30 games per row, same seeds across rows, game-time capped at 330 s, so "median wave" for survivors is a floor.)*
Perks now clearly help (about +2 / +7 / +8 waves for novice / average / skilled), skill clearly matters,
and runs end. Raw data: `docs/balance/shipped_*.csv`, `docs/balance/noperks_*.csv`.

### Options tried and rejected
Recorded from the exploratory sweep (average bot, 30 games each, random perks):

| Configuration | Median wave | Died by wave 21 | Verdict |
|---|---|---|---|
| Perk every wave (old behaviour) | 24+ (cap) | ~7% | far too easy late |
| **Perk every 2nd wave** | **19** | **87%** | **shipped** |
| +10% enemy HP per wave after wave 8 (perks every wave) | 21 | 30% | still too easy |
| Perk every 2nd wave **+ 8% HP/wave** | 13 | 97% | too harsh: perks barely beat having none (12) |
| …plus 5% more enemies/wave | 15 (n=6, stopped) | 100% | too harsh |

> These raw CSVs were lost in a sandbox reset; the table is the summary recorded at the time. The shipped
> configuration was **re-validated from scratch** afterwards (table above). The HP/count knobs remain in
> `game/tuning.py` (set to 0) for future tuning.

## Finding 2 — what the bot is *not* threatened by

Deaths in the shipped-config runs (all skill levels): **SwarmNode 11, Teleporter 9, bullet 7, Enemy 6, Splitter 5, Hunter 4, Berserker 2, ShieldDrone 1, Sniper 1, Phantom 1**.
Almost all deaths are to basic enemies in crowds. Snipers and The Prism essentially never kill the bot, because it
dodges aimed shots well. That says the bot is good at dodging — **not** that those threats are easy for humans.
They need human playtesting.

## Finding 3 — per-perk value (paired experiment)

Each run starts with exactly one perk (nothing else is ever picked), on the **same 25 seeds** as the no-perk
baseline, so arena and spawns are identical and only the perk differs. Evolutions are compared against their own
prerequisites alone. Data: `docs/balance/perk_test.csv`; reproduce with `python tools/perk_report.py`.

```
baseline (no perks, average bot): median wave 11, mean 11.5, n=25

== base perks vs no-perk baseline (same seeds) ==
volatile               +1.88 waves  (95%: +0.72..+3.04)  W/L 12/ 5   score    +9889   helps
overclock              +1.28 waves  (95%: +0.34..+2.22)  W/L 17/ 5   score    +5621   helps
second_wind            +1.08 waves  (95%: +0.71..+1.45)  W/L 17/ 0   score    +3489   helps
pierce                 +1.00 waves  (95%: +0.17..+1.83)  W/L 15/ 4   score    +4050   helps
surge                  +0.92 waves  (95%: -0.22..+2.06)  W/L 14/ 7   score    +5005   no clear effect
repair                 +0.52 waves  (95%: +0.22..+0.82)  W/L  9/ 0   score    +1578   helps
salvage                +0.44 waves  (95%: -0.38..+1.26)  W/L  8/ 9   score     +782   no clear effect
phase_drive            -0.08 waves  (95%: -0.81..+0.65)  W/L  6/ 7   score     +610   no clear effect
arc_lattice            -0.16 waves  (95%: -0.71..+0.39)  W/L  5/ 7   score     -384   no clear effect

== evolutions vs their own prerequisites alone (same seeds) ==
cluster                +0.36 waves  (95%: -0.52..+1.24)  W/L 12/ 4   score    +1642   no clear effect
homing                 +2.16 waves  (95%: +1.28..+3.04)  W/L 19/ 2   score   +10966   helps
null_lance             +0.08 waves  (95%: -1.26..+1.42)  W/L 12/12   score     +980   no clear effect
tesla                  +0.44 waves  (95%: -0.19..+1.07)  W/L 10/ 5   score    +1813   no clear effect
void_bloom             +0.04 waves  (95%: -0.92..+1.00)  W/L 12/12   score    +1523   no clear effect
```

**Reading it carefully.**
* *Clearly help this bot:* Volatile Core, Overclock, Second Wind (won 17 of 17 paired games), Pierce, Repair, and the **Homing Bolts** evolution (the strongest single effect, +2.2 waves — worth watching).
* *"No clear effect" is not "useless".* The bot only picks Chain Zap when ≥3 enemies are close, the beam only against a nearby boss, and bombs only for dense clusters. So Arc Lattice, Tesla Coil, Null Lance, Cluster Bombs and Void Bloom mostly measure **the bot's weapon habits**. **No perk was retuned from this data.**
* With 25 games per condition, only effects of roughly ±1 wave or more are detectable.

## Reproduce

```bash
python tools/balance_bot.py --runs 30 --skill average --seconds 330 --out my_run.csv
python tools/balance_bot.py --runs 30 --skill average --policy none --out noperks.csv   # no perks at all
python tools/balance_bot.py --perk-test --runs 25 --policy none --out perk_test.csv --resume
python tools/balance_bot.py --runs 30 --tune perk_every=1 late_hp=0.05 --out sweep.csv     # try other knobs
python tools/balance_report.py my_run.csv noperks.csv
python tools/perk_report.py perk_test.csv
```
Runs are deterministic per seed. `--resume` skips games already in the CSV.

## What still needs a human

Opening-wave difficulty, how Snipers and The Prism *feel*, whether the first perk arriving after wave 2 feels too slow,
whether Homing Bolts is too strong in real play, and every "no clear effect" perk above.
