"""
Regression tests for bugs found in the v2.0 code review.
Run headless:   python -m unittest discover -s tests -v
"""
import os, sys, unittest, random
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
pygame.init()
pygame.display.set_mode((1280, 720))

from game.constants import BOSS_HP, PLAYER_DASH_CHARGES, PLAYER_DASH_CHARGE_CD
from game.entities import Enemy, Hunter, Boss
from game.game import Game
from game.player import Player
from game.wave_manager import WaveManager

NO_KEYS = pygame.key.get_pressed()


def fresh_game() -> Game:
    random.seed(0)
    g = Game(None)
    g.enemies.clear()
    g.meh_blocks.clear()
    return g


class BeamTests(unittest.TestCase):
    def test_beam_kills_and_removes_enemy(self):
        g = fresh_game()
        g.player.pos.update(400, 360)
        g.player._angle = 0.0                       # aim right
        e = Enemy(500, 360); e.hp = 2
        g.enemies.append(e)
        g.player.beam_active = True
        for _ in range(60):                         # 1 second of beam
            g._apply_beam(1 / 60)
        self.assertNotIn(e, g.enemies, "beam must remove enemies it kills")
        self.assertGreater(g.score, 0, "beam kills must award score")

    def test_beam_damages_boss(self):
        g = fresh_game()
        g.player.pos.update(640, 600)
        g.player._angle = -1.5707963                # aim straight up
        g.boss = Boss(640, 200)
        start = g.boss.hp
        for _ in range(60):
            g._apply_beam(1 / 60)
        self.assertLess(g.boss.hp, start - 3, "1s of beam should deal ~5 damage")

    def test_beam_misses_off_axis_enemy(self):
        g = fresh_game()
        g.player.pos.update(400, 360)
        g.player._angle = 0.0
        e = Enemy(500, 460); g.enemies.append(e)    # 100px off the ray
        for _ in range(60):
            g._apply_beam(1 / 60)
        self.assertEqual(e.hp, 2)


class WaveTests(unittest.TestCase):
    def test_later_boss_waves_spawn_a_boss(self):
        for wave in (5, 10, 15, 20):
            wm = WaveManager(); wm.wave = wave
            types = {s[0] for s in wm._build_spawn_list()}
            self.assertIn("boss", types, f"wave {wave} is a boss wave")

    def test_regular_waves_have_no_boss(self):
        for wave in (1, 2, 3, 4, 6, 7, 8, 9, 11):
            wm = WaveManager(); wm.wave = wave
            self.assertNotIn("boss", {s[0] for s in wm._build_spawn_list()})

    def test_boss_hp_scales_with_tier(self):
        g = fresh_game()
        g.wave_mgr.wave = 5;  g._spawn_entity("boss"); hp5 = g.boss.max_hp
        g.wave_mgr.wave = 10; g._spawn_entity("boss"); hp10 = g.boss.max_hp
        self.assertEqual(hp5, BOSS_HP)
        self.assertGreater(hp10, hp5)

    def test_phase2_threshold_is_proportional(self):
        self.assertEqual(Boss(0, 0)._p2_hp, 7)       # unchanged for the wave-5 boss
        self.assertEqual(Boss(0, 0, hp=31)._p2_hp, 15)


class DashTests(unittest.TestCase):
    def test_two_charges_then_empty(self):
        p = Player(640, 360)
        self.assertEqual(p.dash_charges, PLAYER_DASH_CHARGES)
        p.update(NO_KEYS, 1 / 60, (900, 360), (False,) * 3, [])
        self.assertTrue(p.trigger_dash(NO_KEYS))
        for _ in range(20): p.update(NO_KEYS, 1 / 60, (900, 360), (False,) * 3, [])
        self.assertTrue(p.trigger_dash(NO_KEYS))
        for _ in range(20): p.update(NO_KEYS, 1 / 60, (900, 360), (False,) * 3, [])
        self.assertFalse(p.trigger_dash(NO_KEYS), "third dash needs a recharge")

    def test_charge_recharges(self):
        p = Player(640, 360)
        p.trigger_dash(NO_KEYS)
        for _ in range(int((PLAYER_DASH_CHARGE_CD + 0.5) * 60)):
            p.update(NO_KEYS, 1 / 60, (900, 360), (False,) * 3, [])
        self.assertEqual(p.dash_charges, PLAYER_DASH_CHARGES)

    def test_dash_grants_iframes(self):
        g = fresh_game()
        g.player.pos.update(640, 360)
        g.player.trigger_dash(NO_KEYS)
        g.enemies.append(Enemy(640, 360))            # standing on the player
        g._handle_collisions()
        self.assertEqual(g.hp, 3, "no damage while dashing")
        g.player.is_dashing = False; g.player._dash_time_left = 0
        g._handle_collisions()
        self.assertEqual(g.hp, 2, "damage once the dash ends")


class FrameRateIndependenceTests(unittest.TestCase):
    """Same simulated second must move things the same distance at 30 and 60 FPS."""

    def _hunter_travel(self, fps):
        h = Hunter(100, 360); start = pygame.Vector2(h.pos); h.speed = 3.0
        target = pygame.Vector2(1200, 360)
        for _ in range(fps // 2):                    # half a second
            h.update(1 / fps, target)
        return (h.pos - start).length()

    def test_enemy_speed_independent_of_fps(self):
        a, b = self._hunter_travel(60), self._hunter_travel(30)
        self.assertAlmostEqual(a, b, delta=a * 0.02)

    def _player_travel(self, fps):
        p = Player(100, 360)
        class K(dict):
            def __missing__(self, k): return False
        keys = K({pygame.K_d: True})
        for _ in range(fps // 2):
            p.update(keys, 1 / fps, (900, 360), (False,) * 3, [])
        return p.pos.x - 100

    def test_player_speed_independent_of_fps(self):
        a, b = self._player_travel(60), self._player_travel(30)
        self.assertAlmostEqual(a, b, delta=a * 0.02)


class RobustnessTests(unittest.TestCase):
    def test_enemy_exactly_on_player_does_not_crash(self):
        e = Enemy(300, 300)
        e.update(1 / 60, pygame.Vector2(300, 300))   # used to raise ValueError (normalize 0)


if __name__ == "__main__":
    unittest.main()
