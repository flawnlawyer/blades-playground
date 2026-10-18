"""
Phase 3 tests: engine (spatial hash, dust field, LOD, stress, GPU path),
content (enemy bullets, The Prism, boss rotation), daily run (seed, codes, scores).
"""
import os, sys, math, random, subprocess, tempfile, unittest
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np
import pygame
pygame.init()
pygame.display.set_mode((1280, 720))

from game.constants import *
from game.dust import DustField
from game.entities import Enemy, Prism, Boss, EnemyBullet, Projectile
from game.game import Game
from game.wave_manager import boss_kind, BOSS_NAMES
from utils import daily, helpers
from utils.spatial import SpatialHash

PLAYER_AT = pygame.Vector2(640, 360)


def fresh_game(seed=None) -> Game:
    random.seed(0)
    g = Game(None, seed=seed)
    g.enemies.clear(); g.meh_blocks.clear(); g.fragments.clear()
    g.wave_mgr._break_timer = 9999
    return g


# ── Engine ────────────────────────────────────────────────────────────────────

class SpatialHashTests(unittest.TestCase):
    def test_nearby_never_misses_a_true_neighbour(self):
        rng = random.Random(5)
        es = [Enemy(rng.uniform(0, 1280), rng.uniform(0, 720)) for _ in range(400)]
        sh = SpatialHash(64); sh.rebuild(es)
        for _ in range(300):
            x, y, r = rng.uniform(0, 1280), rng.uniform(0, 720), rng.uniform(5, 60)
            truth  = {id(e) for e in es if math.hypot(e.pos.x - x, e.pos.y - y) <= r}
            found  = {id(e) for e in sh.nearby(x, y, r)}
            self.assertTrue(truth <= found)

    def test_len_counts_everything(self):
        es = [Enemy(i * 10.0, 10.0) for i in range(50)]
        sh = SpatialHash(); sh.rebuild(es)
        self.assertEqual(len(sh), 50)


class DustFieldTests(unittest.TestCase):
    def test_emit_respects_capacity(self):
        f = DustField(capacity=100)
        f.emit(10, 10, 80, (255, 0, 0)); f.emit(10, 10, 80, (255, 0, 0))
        self.assertEqual(len(f), 100)

    def test_particles_expire_and_compact(self):
        f = DustField(capacity=1000)
        f.emit(100, 100, 300, (255, 0, 0), life=(0.2, 0.2))
        f.emit(100, 100, 200, (0, 255, 0), life=(5.0, 5.0))
        f.update(0.3)
        self.assertEqual(len(f), 200)
        self.assertTrue((f.col[:200, 1] == 255).all(), "survivors must be the long-lived ones")

    def test_draw_writes_pixels_and_clips_offscreen(self):
        f = DustField(); f.emit(300, 300, 500, (255, 255, 255), speed=(100, 200), life=(5, 5))
        f.update(0.5)
        f.emit(-500, -500, 50, (255, 255, 255), speed=(0, 1), life=(5, 5))   # offscreen
        surf = pygame.Surface((1280, 720), pygame.SRCALPHA); surf.fill((0, 0, 0, 255))
        f.draw(surf)
        lit = int((pygame.surfarray.array3d(surf).sum(axis=2) > 0).sum())
        self.assertGreater(lit, 200)

    def test_game_kill_sprays_dust(self):
        g = fresh_game(); e = Enemy(300, 300); g.enemies.append(e)
        before = len(g.dust); g._on_enemy_killed(e)
        self.assertGreater(len(g.dust), before)


class CollisionTests(unittest.TestCase):
    def test_projectile_hits_nearest_of_overlapping_enemies(self):
        g = fresh_game()
        far, near = Enemy(318, 300), Enemy(300, 300)
        for e in (far, near): e.hp = 9; e.stunned = True; e.stun_timer = 9
        g.enemies += [far, near]                         # far listed first on purpose
        g.projectiles.append(Projectile(290, 300, 1, 0, 14, 1, 650, Projectile.TYPE_PLASMA))
        g.update(1 / 60)
        self.assertEqual((near.hp, far.hp), (8, 9))

    def test_dead_enemy_in_stale_index_is_not_hit(self):
        g = fresh_game()
        e = Enemy(300, 300); e.hp = 9; g.enemies.append(e)
        g._eh.rebuild(g.enemies); e._dead = True
        g.projectiles.append(Projectile(296, 300, 1, 0, 1, 1, 650, Projectile.TYPE_PLASMA))
        g.update(1 / 60)
        self.assertEqual(e.hp, 9)

    def test_lod_engages_for_crowds_and_resets(self):
        g = fresh_game()
        for i in range(150): g.enemies.append(Enemy(50 + (i * 8) % 1100, 100 + (i * 13) % 500))
        surf = pygame.Surface((1280, 720), pygame.SRCALPHA)
        g.draw(surf)
        self.assertFalse(helpers.LOD, "LOD must be switched back off after the enemy pass")

    def test_stress_mode_keeps_crowd_and_player_alive(self):
        g = fresh_game(); g.stress_target = 200
        for _ in range(30): g.update(1 / 60)
        self.assertGreaterEqual(len(g.enemies), 150)
        self.assertGreaterEqual(g.hp, 1); self.assertFalse(g.perk_pending)


class GpuPathTests(unittest.TestCase):
    def test_gpu_presenter_runs_through_state_manager(self):
        """Isolated subprocess (software SDL renderer): the whole GPU path must run
        and letterbox/mouse-map correctly.  Does NOT prove real-GPU speed."""
        code = (
            "import os,sys; os.environ['SDL_VIDEODRIVER']='dummy'; os.environ['SDL_AUDIODRIVER']='dummy'\n"
            f"sys.path.insert(0, {ROOT!r})\n"
            "import pygame; pygame.init()\n"
            "from game.constants import LOGICAL_W, LOGICAL_H\n"
            "from game.state_manager import StateManager, BaseState\n"
            "from utils.gpu import GpuPresenter\n"
            "class P(BaseState):\n"
            "    n=0\n"
            "    def update(self,dt):\n"
            "        P.n+=1\n"
            "        if P.n>=10: self.manager.quit()\n"
            "    def draw(self,s): s.fill((200,30,90,255))\n"
            "gp=GpuPresenter('t',(900,500),(LOGICAL_W,LOGICAL_H),vsync=False)\n"
            "m=StateManager(None,gp); m.push(P(m)); m.run()\n"
            "print('OK',P.n,m._scaled_size,m.mouse_to_logical((450,250)))\n")
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
        self.assertIn("OK 10 (888, 500) (639, 360)", out.stdout, out.stdout + out.stderr)


# ── Enemy bullets ─────────────────────────────────────────────────────────────

class BulletTests(unittest.TestCase):
    def _bullet_on_player(self, g):
        b = EnemyBullet(g.player.pos.x, g.player.pos.y, 0, 0)
        g.enemy_bullets.append(b); return b

    def test_bullet_hurts_player(self):
        g = fresh_game(); self._bullet_on_player(g)
        g._update_bullets(1 / 60)
        self.assertEqual(g.hp, 2); self.assertEqual(g.enemy_bullets, [])

    def test_dash_iframes_dodge_bullets_without_consuming_them(self):
        g = fresh_game(); g.player.trigger_dash(pygame.key.get_pressed())
        b = self._bullet_on_player(g)
        g._update_bullets(1 / 60)
        self.assertEqual(g.hp, 3); self.assertTrue(b.alive)

    def test_chaos_mode_erases_bullets(self):
        g = fresh_game(); g.player.chaos_mode = True
        self._bullet_on_player(g)
        g._update_bullets(1 / 60)
        self.assertEqual(g.hp, 3); self.assertEqual(g.enemy_bullets, [])

    def test_bullets_expire_offscreen(self):
        b = EnemyBullet(1270, 360, 400, 0)
        for _ in range(30): b.update(1 / 60)
        self.assertFalse(b.alive)

    def test_hack_clears_nearby_bullets_only(self):
        g = fresh_game()
        near = EnemyBullet(g.player.pos.x + 60, g.player.pos.y, 0, 0)
        far  = EnemyBullet(g.player.pos.x + 600, g.player.pos.y, 0, 0)
        g.enemy_bullets += [near, far]
        g._do_hack(); g._update_bullets(0.0)
        self.assertEqual(g.enemy_bullets, [far])

    def test_killing_the_boss_clears_all_bullets(self):
        g = fresh_game(); g.boss = Prism(640, 150)
        g.enemy_bullets += [EnemyBullet(100, 100, 1, 1) for _ in range(20)]
        g._on_boss_killed()
        self.assertEqual(g.enemy_bullets, [])


# ── The Prism ─────────────────────────────────────────────────────────────────

def run_prism_until(prism, attack, player, limit=600):
    """Advance until the Prism is in the 'fire' state of the given attack."""
    for _ in range(limit):
        prism.update(1 / 60, player)
        if prism._state == "fire" and prism._attack == attack:
            return True
    return False


class PrismTests(unittest.TestCase):
    def test_boss_rotation(self):
        self.assertEqual([boss_kind(w) for w in (5, 10, 15, 20, 25)],
                         ["architect", "prism", "architect", "prism", "architect"])

    def test_prism_spawns_on_wave_10_with_name_and_scaled_hp(self):
        g = fresh_game()
        g.wave_mgr.wave = 10; g._spawn_entity("boss")
        self.assertIsInstance(g.boss, Prism); self.assertEqual(g.boss.name, "THE PRISM")
        g.wave_mgr.wave = 20; g._spawn_entity("boss")
        self.assertGreater(g.boss.max_hp, PRISM_HP + 10)
        g.wave_mgr.wave = 5; g._spawn_entity("boss")
        self.assertIsInstance(g.boss, Boss); self.assertEqual(g.boss.name, "THE ARCHITECT")

    def test_attacks_are_telegraphed_before_firing(self):
        p = Prism(640, 150)
        for _ in range(600):
            p.update(1 / 60, PLAYER_AT)
            if p._state == "warn":
                self.assertEqual(p.bullet_queue, [], "no bullets while warning")
                break
        else:
            self.fail("never entered warn state")

    def test_each_attack_fires_bullets(self):
        for attack in ("spiral", "ring", "aimed"):
            p = Prism(640, 150)
            self.assertTrue(run_prism_until(p, attack, PLAYER_AT), attack)
            for _ in range(30): p.update(1 / 60, PLAYER_AT)
            self.assertGreater(len(p.bullet_queue), 0, attack)

    def test_ring_always_leaves_a_gap(self):
        p = Prism(640, 150); p.pos.update(640, 150)
        p._attack_i = 1                      # start the cycle at RING (queue then holds only ring bullets)
        self.assertTrue(run_prism_until(p, "ring", PLAYER_AT))
        p.update(1 / 60, PLAYER_AT)
        angles = sorted(math.atan2(vy, vx) % math.tau for (_, _, vx, vy) in p.bullet_queue)
        self.assertLess(len(angles), 26)                      # some bullets omitted
        gaps = [(b - a) for a, b in zip(angles, angles[1:] + [angles[0] + math.tau])]
        self.assertGreater(max(gaps), 0.6, "a passable gap must exist")

    def test_phase_two_triggers_once_and_calls_reinforcements(self):
        p = Prism(640, 150); p.hp = p._p2_hp
        p.update(1 / 60, PLAYER_AT)
        self.assertEqual(p.phase, 2); self.assertTrue(p.just_phase2)
        self.assertEqual([t for t, *_ in p.spawn_queue], ["swarm"] * 3)
        p.just_phase2 = False; p.spawn_queue.clear()
        p.update(1 / 60, PLAYER_AT)
        self.assertFalse(p.just_phase2); self.assertEqual(p.spawn_queue, [])

    def test_stunned_prism_does_not_fire(self):
        p = Prism(640, 150)
        self.assertTrue(run_prism_until(p, "spiral", PLAYER_AT))
        p.bullet_queue.clear(); p.stun()
        for _ in range(30): p.update(1 / 60, PLAYER_AT)
        self.assertEqual(p.bullet_queue, [])

    def test_prism_fight_soak_via_game(self):
        g = fresh_game(); g.wave_mgr.wave = 10; g._spawn_entity("boss")
        surf = pygame.Surface((1280, 720), pygame.SRCALPHA)
        for i in range(60 * 40):
            g.player.pos.update(640 + 200 * math.sin(i / 50), 600)
            g.hp = 3; g.update(1 / 60)
            if i % 5 == 0: g.draw(surf)
        self.assertLessEqual(len(g.enemy_bullets), MAX_ENEMY_BULLETS)


# ── Daily run ─────────────────────────────────────────────────────────────────

class DailyTests(unittest.TestCase):
    def test_seed_is_stable_per_date_and_differs_across_dates(self):
        self.assertEqual(daily.seed_for("20261014"), daily.seed_for("20261014"))
        self.assertNotEqual(daily.seed_for("20261014"), daily.seed_for("20261015"))

    def test_share_code_roundtrip_and_tamper_detection(self):
        code = daily.share_code("20261014", 5200, 7)
        self.assertEqual(daily.parse_code(code), {"date": "20261014", "score": 5200, "wave": 7})
        self.assertIsNone(daily.parse_code(code.replace("5200", "9999")))
        self.assertIsNone(daily.parse_code("nonsense")); self.assertIsNone(daily.parse_code(""))

    def test_same_seed_same_arena_different_seed_differs(self):
        pos = lambda g: [(b.rect.x, b.rect.y) for b in g.meh_blocks]
        a, b, c = Game(None, seed=42), Game(None, seed=42), Game(None, seed=43)
        self.assertEqual(pos(a), pos(b)); self.assertNotEqual(pos(a), pos(c))
        self.assertEqual([f.text for f in a.fragments], [f.text for f in b.fragments])

    def test_same_seed_same_wave_spawn_positions(self):
        def spawn_positions(seed):
            g = Game(None, seed=seed); g.meh_blocks.clear()
            g.player.pos.update(640, 360)
            g.wave_mgr._break_timer = 0.01
            seen, out = set(), []
            for _ in range(60 * 9):
                g.hp = 3; g.update(1 / 60)
                for e in g.enemies:
                    if id(e) not in seen:
                        seen.add(id(e)); out.append((round(e.pos.x), round(e.pos.y)))
            return out
        a, b = spawn_positions(7), spawn_positions(7)
        self.assertGreater(len(a), 3)
        self.assertEqual(a, b)

    def test_same_seed_same_perk_offers(self):
        def offers(seed):
            g = Game(None, seed=seed); g.enemies.clear()
            g.wave_mgr._state = "active"; g.wave_mgr.wave = 3; g.wave_mgr._break_timer = 0
            g.wave_mgr._all_dead_timer = 1.19; g.wave_mgr._pending_spawns = []
            g.update(0.05)
            return [p.key for p in g.perk_choices]
        self.assertEqual(offers(9), offers(9)); self.assertEqual(len(offers(9)), 3)

    def test_daily_flag_and_unseeded_game(self):
        self.assertTrue(Game(None, seed=1).daily); self.assertFalse(Game(None).daily)

    def test_record_daily_keeps_best_per_date(self):
        from utils import data_manager as dm
        old_dir, old_file = dm.DATA_DIR, dm.SAVE_FILE
        with tempfile.TemporaryDirectory() as tmp:
            dm.DATA_DIR = type(old_dir)(tmp); dm.SAVE_FILE = dm.DATA_DIR / "hs.json"
            try:
                dm.record_daily("20261014", 500, 3)
                best = dm.record_daily("20261014", 300, 9)          # worse: ignored
                self.assertEqual(best, {"score": 500, "wave": 3})
                self.assertEqual(dm.record_daily("20261014", 900, 4)["score"], 900)
                self.assertEqual(dm.load_daily("20261014")["score"], 900)
                self.assertIsNone(dm.load_daily("20990101"))
            finally:
                dm.DATA_DIR, dm.SAVE_FILE = old_dir, old_file


if __name__ == "__main__":
    unittest.main()
