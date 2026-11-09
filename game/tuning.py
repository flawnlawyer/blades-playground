"""
tuning.py — Balance knobs, in one place.

Read at use-time (not import-time) so tools/balance_bot.py can sweep them with
``--tune perk_every=2 late_hp=0.08``.  The values below are the shipped defaults,
chosen from bot sweeps (see CHANGELOG / tools/balance_report.py), not guesses.
"""
TUNING: dict = {
    "perk_every":  2,      # offer a perk every N cleared waves (boss waves always offer one).
                           # Was 1; bot sweeps showed a perk after EVERY wave made a perk-stacked
                           # player nearly immortal (median wave 24+ vs 12 with no perks).
    "late_start":  8,      # enemy scaling begins after this wave
    "late_hp":     0.0,    # +X enemy HP per wave past late_start  (0.08 = +8% per wave).  Off: 0.08 made
                           # perks nearly pointless (median wave 13 vs 12 with none), so it stays a knob only.
    "late_count":  0.0,    # +X enemy count per wave past late_start
}
