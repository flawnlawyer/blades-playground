"""Tests for the balance bot, its reports, and the integrity of the shipped balance data."""
import csv, os, subprocess, sys, tempfile, unittest
from pathlib import Path
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools"))

import balance_bot as bb                      # (initialises pygame headlessly on import)
from game.perks import PERKS
from game.tuning import TUNING


def run_tool(*args, cwd=ROOT):
    return subprocess.run([sys.executable, *args], cwd=cwd, capture_output=True, text=True, timeout=120,
                          env={**os.environ, "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"})


class BotBehaviour(unittest.TestCase):
    def test_runs_are_deterministic_per_seed(self):
        a = bb.run_one(7, "average", 20.0); b = bb.run_one(7, "average", 20.0)
        for r in (a, b): r.pop("wall")
        self.assertEqual(a, b)
        c = bb.run_one(8, "average", 20.0); c.pop("wall")
        self.assertNotEqual(a, c)

    def test_the_bot_actually_plays(self):
        g = bb.make_game(3); g.input_source = bb.Bot(__import__("random").Random(1), "average")
        x0, y0 = g.player.pos.x, g.player.pos.y
        for _ in range(180): g.update(1 / 30)
        self.assertGreater(abs(g.player.pos.x - x0) + abs(g.player.pos.y - y0), 20, "bot never moved")
        self.assertGreater(g.stats["kills"], 0, "bot never killed anything")

    def test_policy_none_takes_no_perks_and_start_perks_are_granted(self):
        r = bb.run_one(5, "average", 40.0, perk_policy="none"); self.assertEqual(r["perks"], "")
        r2 = bb.run_one(5, "average", 5.0, start_perks={"pierce": 1, "overclock": 2}, perk_policy="none")
        self.assertIn("pierce", r2["perks"]); self.assertIn("overclock", r2["perks"])

    def test_skill_levels_are_ordered(self):
        every = [bb.SKILLS[s][0] for s in ("novice", "average", "skilled")]
        self.assertTrue(every[0] > every[1] > every[2])                        # skilled thinks more often
        miss = [bb.SKILLS[s][1] for s in ("novice", "average", "skilled")]
        self.assertTrue(miss[0] > miss[1] > miss[2])

    def test_bulk_run_helpers_silence_audio_and_music(self):
        g = bb.make_game(1)
        self.assertIsNone(g.audio.play("x")); self.assertIsNone(g.music.update(0.1))


class BotCli(unittest.TestCase):
    def test_tune_resume_and_csv_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "r.csv"
            r = run_tool("tools/balance_bot.py", "--runs", "2", "--seconds", "8", "--tune", "perk_every=3", "--out", str(out))
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(out) as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(len(rows), 2)
            self.assertEqual(set(rows[0]), set(bb.FIELDS))
            r2 = run_tool("tools/balance_bot.py", "--runs", "3", "--seconds", "8", "--resume", "--out", str(out))
            self.assertEqual(r2.returncode, 0, r2.stderr)
            with open(out) as fh:
                self.assertEqual(len(list(csv.DictReader(fh))), 3)               # only the missing seed was run

    def test_tune_flag_reaches_the_game(self):
        old = dict(TUNING)
        try:
            r = run_tool("-c", "import sys; sys.argv=['x','--runs','0','--tune','perk_every=5','late_hp=0.5']; "
                                "sys.path.insert(0,'tools'); import balance_bot as b; b.main(); "
                                "from game.tuning import TUNING; print(TUNING['perk_every'], TUNING['late_hp'])")
            self.assertIn("5 0.5", r.stdout, r.stderr)
        finally:
            TUNING.clear(); TUNING.update(old)


class ReportsAndData(unittest.TestCase):
    PT = ROOT / "docs" / "balance" / "perk_test.csv"

    def test_perk_test_data_is_complete_and_paired(self):
        with open(self.PT) as fh:
            rows = list(csv.DictReader(fh))
        by = {}
        for r in rows: by.setdefault(r["condition"], set()).add(int(r["seed"]))
        self.assertEqual(len(by), 1 + len([p for p in PERKS.values() if not p.evolution]) + 2 * len([p for p in PERKS.values() if p.evolution]))
        seeds = by["baseline"]
        self.assertEqual(len(seeds), 25)
        for cond, s in by.items():
            self.assertEqual(s, seeds, f"{cond}: seeds differ from baseline (pairing would be invalid)")
        self.assertEqual(len(rows), 25 * len(by))                              # no duplicates

    def test_perk_report_covers_every_perk(self):
        r = run_tool("tools/perk_report.py")
        self.assertEqual(r.returncode, 0, r.stderr)
        for key, p in PERKS.items():
            self.assertIn(key, r.stdout, f"{key} missing from the report")

    def test_balance_report_runs_on_shipped_data(self):
        r = run_tool("tools/balance_report.py", "docs/balance/shipped_average.csv")
        self.assertEqual(r.returncode, 0, r.stderr); self.assertIn("killed by", r.stdout); self.assertIn("median", r.stdout)

    def test_shipped_data_supports_the_documented_claim(self):
        """BALANCE.md says perks help and runs end: guard the underlying numbers."""
        import statistics as st
        def med(f):
            with open(ROOT / "docs" / "balance" / f) as fh:
                return st.median(int(r["wave"]) for r in csv.DictReader(fh))
        for sk in ("novice", "average", "skilled"):
            self.assertGreater(med(f"shipped_{sk}.csv"), med(f"noperks_{sk}.csv"), sk)       # perks help
        self.assertLess(med("shipped_novice.csv"), med("shipped_average.csv"))                # skill matters
        self.assertEqual(TUNING["perk_every"], 2); self.assertIn("perk_every = 2", (ROOT / "docs" / "BALANCE.md").read_text())


if __name__ == "__main__":
    unittest.main()
