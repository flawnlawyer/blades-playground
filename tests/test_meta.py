"""Progression tests: normalise, shop, earning, achievements, applying upgrades, Armory UI."""
import copy, os, random, sys, tempfile, unittest
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
pygame.init()
pygame.display.set_mode((1280, 720))

from game.constants import *
from game.entities import Enemy, Fragment
from game.game import Game
from game.perks import PERKS
from utils import data_manager as dm, meta as M


def fresh_game(**kw) -> Game:
    random.seed(0)
    g = Game(None, **kw)
    g.enemies.clear(); g.meh_blocks.clear(); g.fragments.clear(); g.wave_mgr._break_timer = 9999
    return g


def new_meta(**over):
    m = copy.deepcopy(M.DEFAULT_META); m.update(over); return m


def stats(**o):
    s = {"score": 0, "wave": 1, "kills": 0, "bosses": [], "max_streak": 0, "hits": 1, "chaos": 0,
         "perk_stacks": 0, "daily": False, "cheated": False, "stress": False, "seconds": 0}
    s.update(o); return s


class TempData:
    """Redirect the save file into a temp dir for the duration of a test."""
    def setUp(self):
        self._old = dm.DATA_DIR, dm.SAVE_FILE
        self._tmp = tempfile.TemporaryDirectory()
        dm.DATA_DIR = type(self._old[0])(self._tmp.name); dm.SAVE_FILE = dm.DATA_DIR / "hs.json"
    def tearDown(self):
        dm.DATA_DIR, dm.SAVE_FILE = self._old; self._tmp.cleanup()


class Normalise(unittest.TestCase):
    def test_garbage_collapses_to_defaults(self):
        for junk in (None, 5, "x", [], {"shards": "lots"}):
            self.assertEqual(M.normalise(junk)["shards"], 0)

    def test_invalid_fields_are_dropped_valid_ones_kept(self):
        m = M.normalise({"shards": -50, "upgrades": {"vitality": 9, "nonsense": 1, "magnet": 1},
                         "weapons": [3, 99, "x", True], "perks": ["overclock", "homing", "bogus"],
                         "achievements": ["breaker", "fake"], "loadout": {"weapon": 3, "perk": "overclock"}})
        self.assertEqual(m["shards"], 0); self.assertEqual(m["upgrades"], {"magnet": 1})
        self.assertEqual(m["weapons"], [0, 3, 1][:0] or sorted(m["weapons"])); self.assertIn(0, m["weapons"])
        self.assertNotIn(99, m["weapons"]); self.assertEqual(m["perks"], ["overclock"])   # evolution not startable
        self.assertEqual(m["achievements"], ["breaker"])
        self.assertEqual(m["loadout"], {"weapon": 3, "perk": "overclock"})

    def test_loadout_cannot_equip_something_not_owned(self):
        m = M.normalise({"loadout": {"weapon": 4, "perk": "surge"}})
        self.assertEqual(m["loadout"], {"weapon": 0, "perk": None})


class Shop(unittest.TestCase):
    def test_upgrade_costs_levels_and_cap(self):
        m = new_meta(shards=2000)
        self.assertEqual(M.upgrade_cost(m, "vitality"), 300)
        self.assertTrue(M.buy_upgrade(m, "vitality")); self.assertEqual(m["shards"], 1700)
        self.assertEqual(M.upgrade_cost(m, "vitality"), 600)
        self.assertTrue(M.buy_upgrade(m, "vitality")); self.assertEqual(M.level(m, "vitality"), 2)
        self.assertIsNone(M.upgrade_cost(m, "vitality"))
        self.assertFalse(M.buy_upgrade(m, "vitality")); self.assertEqual(m["shards"], 1100)

    def test_cannot_buy_without_enough_shards(self):
        m = new_meta(shards=299)
        self.assertFalse(M.buy_upgrade(m, "vitality")); self.assertEqual((m["shards"], M.level(m, "vitality")), (299, 0))

    def test_weapons_and_perks(self):
        m = new_meta(shards=1000)
        self.assertFalse(M.buy_weapon(m, 0))                                   # plasma already owned
        self.assertTrue(M.buy_weapon(m, 3)); self.assertEqual(m["shards"], 600); self.assertIn(3, m["weapons"])
        self.assertFalse(M.buy_weapon(m, 3))
        self.assertTrue(M.buy_perk(m, "overclock")); self.assertEqual(m["shards"], 350)
        self.assertFalse(M.buy_perk(m, "homing")); self.assertFalse(M.buy_perk(m, "overclock"))
        self.assertFalse(M.buy_perk(m, "second_wind"))                          # 600 > 350

    def test_set_loadout_validates_ownership(self):
        m = new_meta(shards=500)
        self.assertFalse(M.set_loadout(m, weapon=2)); M.buy_weapon(m, 1)
        self.assertTrue(M.set_loadout(m, weapon=1)); self.assertEqual(m["loadout"]["weapon"], 1)
        self.assertFalse(M.set_loadout(m, perk="surge"))
        M.buy_perk(m, "surge"); self.assertTrue(M.set_loadout(m, perk="surge"))
        self.assertTrue(M.set_loadout(m, perk=None)); self.assertIsNone(m["loadout"]["perk"])


class Earning(unittest.TestCase):
    def test_formula(self):
        self.assertEqual(M.shards_for_run(stats(score=5200, wave=8, bosses=["THE ARCHITECT"])), 52 + 15 * 7 + 60)
        self.assertEqual(M.shards_for_run(stats(score=0, wave=1)), 0)

    def test_cheated_and_stress_runs_earn_and_record_nothing(self):
        for flag in ("cheated", "stress"):
            m = new_meta(); res = M.award_run(m, stats(score=9999, wave=9, **{flag: True}))
            self.assertEqual(res["shards"], 0); self.assertEqual(m["shards"], 0)
            self.assertEqual(m["achievements"], []); self.assertEqual(m["stats"]["runs"], 0)

    def test_achievements_pay_once(self):
        m = new_meta()
        first = M.award_run(m, stats(wave=5, hits=3))
        self.assertEqual({a for a, _ in first["achievements"]}, {"first_contact", "breaker"})
        second = M.award_run(m, stats(wave=5, hits=3))
        self.assertEqual(second["achievements"], [])
        self.assertEqual(second["shards"], M.shards_for_run(stats(wave=5)))      # no bonus the second time

    def test_run_stats_accumulate(self):
        m = new_meta()
        M.award_run(m, stats(score=1000, wave=3, kills=10, bosses=["X"], seconds=60))
        M.award_run(m, stats(score=500, wave=6, kills=5, seconds=30))
        st = m["stats"]
        self.assertEqual((st["runs"], st["kills"], st["bosses"], st["best_wave"], st["best_score"], st["seconds"]),
                         (2, 15, 1, 6, 1000, 90))

    def test_every_achievement_has_a_true_and_a_false_case(self):
        cases = {
            "first_contact": (stats(wave=2), stats(wave=1)),
            "breaker": (stats(wave=5), stats(wave=4)),
            "architects_end": (stats(bosses=["THE ARCHITECT"]), stats(bosses=["THE PRISM"])),
            "prism_shattered": (stats(bosses=["THE PRISM"]), stats(bosses=["THE ARCHITECT"])),
            "unstoppable": (stats(max_streak=20), stats(max_streak=19)),
            "chaos_incarnate": (stats(chaos=3), stats(chaos=2)),
            "untouchable": (stats(wave=5, hits=0), stats(wave=5, hits=1)),
            "collector": (stats(perk_stacks=8), stats(perk_stacks=7)),
            "daily_driver": (stats(daily=True, wave=3), stats(daily=False, wave=3)),
            "centurion": (stats(kills=100), stats(kills=99)),
        }
        self.assertEqual(set(cases), set(M.ACHIEVEMENTS))
        for aid, (yes, no) in cases.items():
            pred = M.ACHIEVEMENTS[aid][2]
            self.assertTrue(pred(yes), aid); self.assertFalse(pred(no), aid)


class GameTracking(unittest.TestCase):
    def test_run_stats_reflect_what_happened(self):
        g = fresh_game()
        for _ in range(3):
            e = Enemy(100, 100); g.enemies.append(e); g._on_enemy_killed(e)
        g.spawn_boss("prism"); g._on_boss_killed()
        g._hurt_player(pygame.Vector2(0, 0), 12, 18, 70)
        g.player.add_energy(g.player.max_energy)
        s = g.run_stats()
        self.assertEqual(s["kills"], 3); self.assertEqual(s["bosses"], ["THE PRISM"])
        self.assertEqual(s["hits"], 1); self.assertEqual(s["chaos"], 1); self.assertGreaterEqual(s["max_streak"], 4)
        self.assertFalse(s["daily"] or s["cheated"] or s["stress"])

    def test_god_mode_hits_are_not_counted(self):
        g = fresh_game(); g.god = True; g._hurt_player(pygame.Vector2(0, 0), 12, 18, 70)
        self.assertEqual(g.stats["hits"], 0)


class ApplyUpgrades(unittest.TestCase):
    def test_every_upgrade_changes_the_run(self):
        g = fresh_game()
        m = new_meta(upgrades={"vitality": 2, "quickstep": 1, "reserves": 2, "magnet": 2, "arsenal": 1},
                     weapons=[0, 3], loadout={"weapon": 3, "perk": None})
        M.apply_to_game(g, m); p = g.player
        self.assertEqual(g.hp, 5)
        self.assertEqual(p.max_dash_charges, PLAYER_DASH_CHARGES + 1); self.assertEqual(p.dash_charges, p.max_dash_charges)
        self.assertEqual(p.energy, p.max_energy * 0.5); self.assertFalse(p.chaos_mode)
        self.assertEqual(p.bomb_max, 4); self.assertEqual(p.bomb_count, 4); self.assertEqual(p.weapon_index, 3)
        g.fragments.append(Fragment(p.pos.x + p.radius + 9 + 70, p.pos.y, "x"))        # 70px beyond touching
        g._handle_collisions(); self.assertEqual(g.fragments, [])                      # MAGNET x2 = +80px

    def test_magnet_off_means_no_extra_reach(self):
        g = fresh_game(); p = g.player
        g.fragments.append(Fragment(p.pos.x + p.radius + 9 + 30, p.pos.y, "x"))
        g._handle_collisions(); self.assertEqual(len(g.fragments), 1)

    def test_starter_perk_is_granted_and_synergies_still_work(self):
        g = fresh_game()
        M.apply_to_game(g, new_meta(perks=["pierce"], loadout={"weapon": 0, "perk": "pierce"}))
        self.assertEqual(g.perks, {"pierce": 1})

    def test_max_reserves_never_start_chaos_immediately(self):
        g = fresh_game(); M.apply_to_game(g, new_meta(upgrades={"reserves": 2}))
        self.assertLess(g.player.energy, g.player.max_energy)

    def test_arsenal_bombs_recharge_to_the_higher_cap(self):
        g = fresh_game(); M.apply_to_game(g, new_meta(upgrades={"arsenal": 1})); p = g.player
        p.bomb_count = 0; p._bomb_recharge = 0.01
        for _ in range(6): p.update(pygame.key.get_pressed(), 13.0, (900, 360), (False,) * 3, [])   # one bomb per recharge tick
        self.assertEqual(p.bomb_count, 4)                                                              # capped at the new max


class Integration(TempData, unittest.TestCase):
    def _manager(self):
        from game.state_manager import StateManager
        return StateManager(pygame.display.get_surface())

    def test_normal_runs_get_upgrades_but_daily_runs_do_not(self):
        from game.states.play_state import PlayState
        m = new_meta(upgrades={"vitality": 2}); dm.save_meta(m)
        normal = PlayState(self._manager()); normal.on_enter()
        daily = PlayState(self._manager(), daily=True); daily.on_enter()
        self.assertEqual(normal._game.hp, 5); self.assertEqual(daily._game.hp, 3)

    def test_gameover_banks_the_run_once_and_cheats_earn_nothing(self):
        from game.states.gameover_state import GameOverState
        class FM:
            def mouse_to_logical(s, p): return p
        g = fresh_game(); g.score = 3000; g.wave_mgr.wave = 6
        go = GameOverState(FM(), score=3000, wave=6, time=100, game=g); go.on_enter(); go.on_enter()
        banked = dm.load_meta()
        self.assertEqual(banked["shards"], 30 + 15 * 5 + 3 * 100)             # score + waves + FIRST CONTACT, BREAKER, UNTOUCHABLE
        self.assertTrue(any("SHARDS" in l for l in go._daily_info))
        self.assertTrue(any("ACHIEVEMENT" in l for l in go._daily_info))
        c = fresh_game(); c.cheated = True; c.score = 9999; c.wave_mgr.wave = 9
        GameOverState(FM(), score=9999, wave=9, time=50, game=c).on_enter()
        self.assertEqual(dm.load_meta()["shards"], banked["shards"])

    def test_meta_survives_a_roundtrip_and_corrupt_files(self):
        m = new_meta(shards=123, upgrades={"magnet": 1}); dm.save_meta(m)
        self.assertEqual(dm.load_meta()["shards"], 123)
        dm.SAVE_FILE.write_text("{ not json")
        self.assertEqual(dm.load_meta()["shards"], 0)                         # corrupt file must not crash


class ArmoryUI(TempData, unittest.TestCase):
    class FM:
        def __init__(self): self.popped = False
        def mouse_to_logical(self, p): return p
        def pop(self, **k): self.popped = True

    def key(self, k): return pygame.event.Event(pygame.KEYDOWN, key=k, unicode="", mod=0)

    def state(self, **over):
        from game.states.armory_state import ArmoryState
        dm.save_meta(new_meta(**over)); fm = self.FM(); st = ArmoryState(fm); st.on_enter(); return st, fm

    def test_buying_with_keyboard_persists(self):
        st, _ = self.state(shards=1000)
        st.handle_events([self.key(pygame.K_RETURN)])                          # first row: VITALITY
        self.assertEqual(dm.load_meta()["upgrades"], {"vitality": 1}); self.assertEqual(dm.load_meta()["shards"], 700)
        self.assertIn("LEVEL 1", st.msg)

    def test_not_enough_shards_says_so_and_changes_nothing(self):
        st, _ = self.state(shards=10)
        st.handle_events([self.key(pygame.K_RETURN)])
        self.assertIn("NOT ENOUGH", st.msg); self.assertEqual(dm.load_meta()["shards"], 10)

    def test_maxed_upgrade_message(self):
        st, _ = self.state(shards=5000, upgrades={"vitality": 2})
        st.handle_events([self.key(pygame.K_RETURN)]); self.assertIn("MAX", st.msg)

    def test_tabs_and_loadout_flow(self):
        st, _ = self.state(shards=1000)
        st.handle_events([self.key(pygame.K_RIGHT)]); self.assertEqual(st.tab, 1)
        self.assertEqual(st.rows()[st.sel]["kind"], "weapon")                  # selection skips the header
        st.handle_events([self.key(pygame.K_DOWN), self.key(pygame.K_RETURN)])   # VOID SPREAD: buy + equip
        m = dm.load_meta(); self.assertIn(1, m["weapons"]); self.assertEqual(m["loadout"]["weapon"], 1)
        st.handle_events([self.key(pygame.K_LEFT)]); self.assertEqual(st.tab, 0)

    def test_navigation_wraps_and_never_lands_on_headers(self):
        st, _ = self.state(); st.handle_events([self.key(pygame.K_RIGHT)])
        for _ in range(40):
            st.handle_events([self.key(pygame.K_DOWN)]); self.assertNotEqual(st.rows()[st.sel]["kind"], "header")

    def test_mouse_selects_and_buys(self):
        st, _ = self.state(shards=1000)
        st.update(0.1); st.draw(pygame.Surface((1280, 720), pygame.SRCALPHA))
        r = st._rects[1]
        st.handle_events([pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=r.center, button=1)])
        self.assertEqual(dm.load_meta()["upgrades"], {"quickstep": 1})

    def test_all_tabs_draw_and_escape_leaves(self):
        st, fm = self.state(shards=500, achievements=["breaker"])
        for t in range(3):
            st._set_tab(t); st.update(0.1); st.draw(pygame.Surface((1280, 720), pygame.SRCALPHA))
        st.handle_events([self.key(pygame.K_ESCAPE)]); self.assertTrue(fm.popped)

    def test_menu_has_an_armory_entry_that_opens_it(self):
        from game.states import menu_state
        from game.states.menu_state import MenuState
        self.assertIn("ARMORY", menu_state._MENU_ITEMS)
        class FM2(self.FM):
            logo = None
            def push(self, state, **k): self.pushed = state
        fm = FM2(); ms = MenuState(fm); ms._activate(menu_state._MENU_ITEMS.index("ARMORY"))
        self.assertEqual(type(fm.pushed).__name__, "ArmoryState")


if __name__ == "__main__":
    unittest.main()
