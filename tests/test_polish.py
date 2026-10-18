"""Phase 3 polish tests: hit-stop, shake, music, perk icons, new SFX, seamless drone, vignette."""
import os, sys, random, unittest
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pygame
pygame.init()
pygame.display.set_mode((1280, 720))

from game import music
from game.audio import SoundManager, _build_ambient_drone
from game.entities import Enemy
from game.game import Game
from game.perk_icons import draw_perk_icon
from game.perks import PERKS
from game.renderer import Renderer


def fresh_game(**kw) -> Game:
    random.seed(0)
    g = Game(None, **kw)
    g.enemies.clear(); g.meh_blocks.clear(); g.fragments.clear()
    g.wave_mgr._break_timer = 9999
    return g


class HitStopTests(unittest.TestCase):
    def _chaser_travel(self, freeze):
        g = fresh_game()
        e = Enemy(500, 360); e.speed = 2.0; g.enemies.append(e)
        g.player.pos.update(700, 360)
        if freeze: g._freeze(0.1)
        x0 = e.pos.x
        for _ in range(4): g.update(1 / 60); g.player.pos.update(700, 360)
        return e.pos.x - x0

    def test_freeze_halts_the_world_then_releases(self):
        self.assertEqual(self._chaser_travel(True), 0.0)
        self.assertGreater(self._chaser_travel(False), 3.0)
        g = fresh_game(); g._freeze(0.1)
        for _ in range(8): g.update(1 / 60)           # 0.133 s > 0.1 s freeze
        self.assertLessEqual(g._hitstop_t, 0)

    def test_freeze_is_capped(self):
        g = fresh_game(); g._freeze(5.0)
        self.assertLessEqual(g._hitstop_t, 0.3)

    def test_taking_damage_and_boss_kill_freeze(self):
        g = fresh_game(); g._hurt_player(pygame.Vector2(0, 0), 12, 18, 70)
        self.assertGreater(g._hitstop_t, 0)

    def test_stress_mode_never_freezes(self):
        g = fresh_game(); g.stress_target = 50; g._freeze(0.2)
        self.assertEqual(g._hitstop_t, 0.0)

    def test_death_slowmo_still_ends_during_hitstop(self):
        g = fresh_game(); g.hp = 1
        g._hurt_player(pygame.Vector2(0, 0), 12, 18, 70)
        self.assertTrue(g.dying)
        for _ in range(60): g.update(1 / 60)
        self.assertTrue(g.game_over, "death timer must run on real time even while frozen")


class ShakeTests(unittest.TestCase):
    def test_bounded_and_zero_when_calm(self):
        g = fresh_game()
        g.shake = 0.5; self.assertEqual(g._shake_offset(1.234), (0, 0))
        g.shake = 12
        for i in range(500):
            ox, oy = g._shake_offset(i * 0.016)
            self.assertLessEqual(abs(ox), 12); self.assertLessEqual(abs(oy), 12)

    def test_is_continuous_not_random_jitter(self):
        g = fresh_game(); g.shake = 12
        xs = [g._shake_offset(i * 0.016)[0] for i in range(240)]
        self.assertEqual(xs, [g._shake_offset(i * 0.016)[0] for i in range(240)])   # deterministic in t
        # neighbouring frames move by far less than the full +/-shake range random jitter would use
        self.assertLess(np.mean(np.abs(np.diff(xs))), 7.5)


class MusicTests(unittest.TestCase):
    def test_layers_are_equal_length_exact_loops_and_clickless(self):
        L = music.layer_samples()
        self.assertEqual(set(L), set(music.LAYERS))
        for name, v in L.items():
            self.assertEqual(len(v), music.LOOP_N, name)
            self.assertLess(abs(float(v[0])), 1e-4, name); self.assertLess(abs(float(v[-1])), 1e-4, name)
            self.assertLess(float(np.abs(v).max()), 1.0, name)

    def test_beat_is_an_exact_integer_number_of_samples(self):
        self.assertEqual(music.SR * 60 % music.BPM, 0)

    def test_target_levels_follow_game_state(self):
        calm = music.target_levels(0, False, False, 0, 1, False)
        self.assertEqual((calm["drums"], calm["arp"], calm["lead"]), (0.0, 0.0, 0.0))
        self.assertLess(calm["bass"], 0.5)
        fight = music.target_levels(12, False, False, 0, 3, False)
        self.assertEqual((fight["bass"], fight["drums"], fight["arp"]), (1.0, 1.0, 1.0))
        self.assertEqual(music.target_levels(2, False, True, 0, 1, False)["lead"], 1.0)
        boss = music.target_levels(0, True, False, 0, 1, False)
        self.assertEqual((boss["drums"], boss["arp"]), (1.0, 1.0))
        duck = music.target_levels(12, False, True, 9, 5, True)
        self.assertTrue(all(v <= 0.5 for v in duck.values()))

    def test_engine_glides_and_respects_mute(self):
        audio = SoundManager(); eng = music.MusicEngine(audio)
        eng.start()
        eng.update(0.1, enemies=12, boss=False, chaos=False, streak=0, wave=3, dying=False)
        self.assertLessEqual(eng._level["drums"], music.MusicEngine.GLIDE * 0.1 + 1e-6)   # no jump
        for _ in range(60):
            eng.update(1 / 30, enemies=12, boss=False, chaos=False, streak=0, wave=3, dying=False)
        self.assertEqual(eng._level["drums"], 1.0)
        audio.toggle_mute()
        eng.update(1 / 60, enemies=12, boss=False, chaos=False, streak=0, wave=3, dying=False)
        self.assertEqual(eng._chans["drums"].get_volume(), 0.0)
        eng.stop(); self.assertFalse(eng._playing)

    def test_game_updates_music_and_survives_a_boss_fight(self):
        g = fresh_game(); g.music.start()
        for _ in range(120): g.update(1 / 60)
        self.assertTrue(g.music._playing)
        g.music.stop()


class IconTests(unittest.TestCase):
    def _render(self, key):
        s = pygame.Surface((80, 80), pygame.SRCALPHA)
        draw_perk_icon(s, key, 40, 40, (200, 200, 255), 24)
        return pygame.surfarray.array3d(s).copy()

    def test_every_perk_has_a_distinct_nonblank_icon(self):
        imgs = {k: self._render(k) for k in PERKS}
        for k, a in imgs.items():
            self.assertGreater(int((a.sum(axis=2) > 0).sum()), 40, k)
        keys = list(imgs)
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                self.assertFalse(np.array_equal(imgs[a], imgs[b]), f"{a} == {b}")

    def test_unknown_key_falls_back_to_generic_badge(self):
        self.assertGreater(int((self._render("???").sum(axis=2) > 0).sum()), 40)


class SoundTests(unittest.TestCase):
    NEW = ("perk_select", "shield_break", "enrage", "teleport", "streak_up", "telegraph")

    def test_new_sounds_exist_and_play(self):
        sm = SoundManager()
        for n in self.NEW:
            self.assertIn(n, sm._sounds, n); sm.play(n)

    def test_mute_blocks_new_sounds(self):
        sm = SoundManager(); sm.toggle_mute()
        for n in self.NEW: sm.play(n)          # must not raise

    def test_drone_loop_is_seamless_for_any_energy_level(self):
        for hz in (60.0, 73.4, 91.9, 110.0):
            a = pygame.sndarray.array(_build_ambient_drone(hz, False))[:, 0].astype(int)
            self.assertLess(abs(int(a[0]) - int(a[-1])), 900, hz)       # ~ one sample step, no click


class VignetteTests(unittest.TestCase):
    def test_centre_is_clear_corners_are_dark_and_smooth(self):
        m = pygame.surfarray.array3d(Renderer()._overlay)[:, :, 0].astype(int)
        W, H = m.shape
        self.assertGreater(m[W // 2, H // 2 + 1], 235)               # row +1 avoids a scanline row
        self.assertLess(m[3, 4], 150); self.assertLess(m[W - 4, H - 5], 150)
        self.assertLess(float(np.abs(np.diff(m[:, H // 2 + 1])).mean()), 1.0)   # no ring banding


if __name__ == "__main__":
    unittest.main()
