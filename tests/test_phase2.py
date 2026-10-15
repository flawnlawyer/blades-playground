"""
Phase 2 tests: new enemies, kill streaks, death slow-mo, perks.
Run headless:   python -m unittest discover -s tests -v
"""
import os, sys, unittest, random
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
pygame.init()
pygame.display.set_mode((1280, 720))

from game.constants import *
from game.entities import (Enemy, SwarmNode, Berserker, Teleporter, ShieldDrone,
                           Splitter, Projectile, Fragment)
from game.game import Game
from game.perks import PERKS, roll_choices
from game.player import Player
from game.wave_manager import WaveManager, WAVE_DEFS

PLAYER_AT = pygame.Vector2(640, 360)
FAR       = pygame.Vector2(1200, 100)


def fresh_game() -> Game:
    random.seed(0)
    g = Game(None)
    g.enemies.clear(); g.meh_blocks.clear(); g.fragments.clear()
    g.wave_mgr._break_timer = 9999          # keep the wave system quiet
    return g


def kill_new_enemy(g, hp=1):
    e = Enemy(100, 100); e.hp = hp
    g.enemies.append(e)
    g._on_enemy_killed(e)
    return e


class NewEnemyTests(unittest.TestCase):
    def test_all_new_types_spawn(self):
        g = fresh_game()
        for t, cls in [("berserker", Berserker), ("teleporter", Teleporter),
                       ("shield_drone", ShieldDrone), ("splitter", Splitter)]:
            n = len(g.enemies)
            g._spawn_entity(t, 200.0, 200.0)
            self.assertEqual(len(g.enemies), n + 1, t)
            self.assertIsInstance(g.enemies[-1], cls)

    def test_berserker_enrages_below_half_hp_and_speeds_up(self):
        calm, mad = Berserker(300, 300), Berserker(300, 300)
        self.assertFalse(mad.enraged)
        mad.take_damage(1); self.assertFalse(mad.enraged)       # 4/5 HP
        mad.take_damage(2); self.assertTrue(mad.enraged)         # 2/5 HP
        for _ in range(30):
            calm.update(1 / 60, FAR); mad.update(1 / 60, FAR)
        self.assertGreater((mad.pos - pygame.Vector2(300, 300)).length(),
                           2 * (calm.pos - pygame.Vector2(300, 300)).length())

    def test_teleporter_invulnerable_until_it_blinks(self):
        t = Teleporter(100, 100)
        self.assertFalse(t.take_damage(1)); self.assertEqual(t.hp, TELEPORTER_HP)
        t._blink_cd = 0.0
        t.update(1 / 60, PLAYER_AT)
        self.assertTrue(t.blink_event)
        self.assertTrue(t.vulnerable)
        d = t.pos.distance_to(PLAYER_AT)
        self.assertTrue(TELEPORTER_BLINK_RANGE * 0.5 < d < TELEPORTER_BLINK_RANGE + 40, d)
        t.take_damage(1); self.assertEqual(t.hp, TELEPORTER_HP - 1)

    def test_hack_stun_makes_teleporter_vulnerable(self):
        t = Teleporter(100, 100)
        t.stun()
        self.assertTrue(t.vulnerable)
        t.take_damage(1); self.assertEqual(t.hp, TELEPORTER_HP - 1)

    def test_shield_drone_protects_host_until_killed(self):
        g = fresh_game()
        host, drone = Enemy(300, 300), ShieldDrone(320, 300)
        g.enemies += [host, drone]
        g._update_shields()
        self.assertEqual(host.shield, 1)
        self.assertFalse(host.take_damage(5)); self.assertEqual(host.hp, 2)
        g._on_enemy_killed(drone); g._update_shields()
        self.assertEqual(host.shield, 0)
        self.assertTrue(host.take_damage(5))

    def test_stunned_drone_drops_the_shield(self):
        g = fresh_game()
        host, drone = Enemy(300, 300), ShieldDrone(320, 300)
        g.enemies += [host, drone]
        drone.stun(); g._update_shields()
        self.assertEqual(host.shield, 0)

    def test_splitter_bursts_into_two_swarm_nodes(self):
        g = fresh_game()
        s = Splitter(400, 400); g.enemies.append(s)
        g._on_enemy_killed(s)
        self.assertEqual([type(e) for e in g.enemies], [SwarmNode, SwarmNode])

    def test_double_kill_does_not_double_score(self):
        g = fresh_game()
        e = Enemy(100, 100); g.enemies.append(e)
        g._on_enemy_killed(e); first = g.score
        g._on_enemy_killed(e)                       # e.g. beam + chain on the same frame
        self.assertEqual(g.score, first)

    def test_wave_schedule_introduces_new_enemies(self):
        self.assertIn("splitter",  [t for t, _ in WAVE_DEFS[2]])
        self.assertIn("berserker", [t for t, _ in WAVE_DEFS[3]])
        wm = WaveManager(); wm.wave = 12
        types = {s[0] for s in wm._build_spawn_list()}
        self.assertTrue({"splitter", "berserker", "teleporter", "shield_drone"} <= types, types)


class StreakTests(unittest.TestCase):
    def test_multiplier_tiers(self):
        g = fresh_game()
        for n, expect in [(0, 1.0), (4, 1.0), (5, 1.5), (9, 1.5), (10, 2.0), (19, 2.0), (20, 3.0)]:
            g.streak = n
            self.assertEqual(g._streak_mult(), expect, n)

    def test_kills_build_streak_and_score_multiplier(self):
        g = fresh_game()
        for _ in range(4): kill_new_enemy(g)
        base = g.score; self.assertEqual(base, 4 * 35)
        kill_new_enemy(g)                                   # 5th kill -> x1.5
        self.assertEqual(g.streak, 5)
        self.assertGreater(g.score - base, 35)

    def test_streak_expires(self):
        g = fresh_game()
        g.streak, g.streak_timer = 7, STREAK_RESET_TIME
        for _ in range(int((STREAK_RESET_TIME + 0.3) * 60)):
            g.update(1 / 60)
        self.assertEqual(g.streak, 0)

    def test_getting_hit_breaks_streak(self):
        g = fresh_game(); g.streak = 12
        g._hurt_player(PLAYER_AT + pygame.Vector2(30, 0), 12, 18, 70)
        self.assertEqual(g.streak, 0)


class DeathSlowMoTests(unittest.TestCase):
    def test_lethal_hit_starts_slowmo_then_game_over(self):
        g = fresh_game(); g.hp = 1
        g._hurt_player(PLAYER_AT + pygame.Vector2(30, 0), 12, 18, 70)
        self.assertTrue(g.dying); self.assertFalse(g.game_over)
        for _ in range(int((DEATH_SLOW_DURATION + 0.2) * 60)):
            g.update(1 / 60)
        self.assertTrue(g.game_over)

    def test_world_runs_slowly_while_dying(self):
        g = fresh_game(); g.hp = 1
        h = Enemy(100, 360); h.speed = 2.0; g.enemies.append(h)
        g.player.pos.update(1200, 360)
        g._hurt_player(PLAYER_AT + pygame.Vector2(30, 0), 12, 18, 70)   # -> dying
        x0 = h.pos.x
        g.player.pos.update(1200, 360)
        for _ in range(10): g.update(1 / 60)
        slow = h.pos.x - x0
        g2 = fresh_game(); h2 = Enemy(100, 360); h2.speed = 2.0; g2.enemies.append(h2)
        g2.player.pos.update(1200, 360); x1 = h2.pos.x
        for _ in range(10): g2.update(1 / 60)
        self.assertLess(slow, (h2.pos.x - x1) * 0.4)

    def test_no_extra_damage_while_dying(self):
        g = fresh_game(); g.hp = 1
        g._hurt_player(PLAYER_AT + pygame.Vector2(30, 0), 12, 18, 70)
        hp = g.hp
        g._hurt_player(PLAYER_AT + pygame.Vector2(30, 0), 12, 18, 70)
        self.assertEqual(g.hp, hp)


class PerkTests(unittest.TestCase):
    def test_roll_choices_distinct_and_respect_caps(self):
        owned = {k: p.max_stacks for k, p in PERKS.items()}
        self.assertEqual(roll_choices(owned), [])
        del owned["surge"]; del owned["salvage"]
        out = roll_choices(owned)
        self.assertEqual({p.key for p in out}, {"surge", "salvage"})
        picks = roll_choices({})
        self.assertEqual(len(picks), 3); self.assertEqual(len({p.key for p in picks}), 3)

    def test_stack_cap_enforced(self):
        g = fresh_game()
        g.grant_perk("second_wind"); g.grant_perk("second_wind")
        self.assertEqual(g.perks["second_wind"], 1)

    def test_overclock_shortens_cooldown(self):
        p = Player(640, 360); p.perks["overclock"] = 2
        p._fire((900, 360), [], 1 / 60)
        self.assertAlmostEqual(p._weapon_cds[0], PLASMA_CD * 0.75 ** 2)

    def test_arc_lattice_adds_chain_links(self):
        def links(n):
            p = Player(100, 360); p.perks["arc_lattice"] = n; p.weapon_index = 2
            es = [Enemy(130 + i * 30, 360) for i in range(8)]
            p._fire((900, 360), es, 1 / 60)
            return len(p.chain_targets)
        self.assertEqual(links(0), CHAIN_LINKS); self.assertEqual(links(1), CHAIN_LINKS + 2)

    def test_surge_extends_chaos(self):
        p = Player(640, 360); p.perks["surge"] = 2
        p.add_energy(p.max_energy)
        self.assertEqual(p.chaos_timer, CHAOS_DURATION + 6.0)

    def test_salvage_boosts_fragment_energy(self):
        g = fresh_game(); g.perks["salvage"] = 1
        g.fragments.append(Fragment(g.player.pos.x, g.player.pos.y, "x"))
        g._handle_collisions()
        self.assertAlmostEqual(g.player.energy, FRAG_ENERGY_REWARD * 1.4)

    def test_repair_and_phase_drive_apply_immediately(self):
        g = fresh_game()
        g.grant_perk("repair");      self.assertEqual(g.hp, 4)
        g.grant_perk("phase_drive")
        self.assertEqual(g.player.dash_charges, PLAYER_DASH_CHARGES + 1)
        self.assertEqual(g.player.max_dash_charges, PLAYER_DASH_CHARGES + 1)

    def test_second_wind_saves_you_exactly_once(self):
        g = fresh_game(); g.grant_perk("second_wind"); g.hp = 1
        far = Enemy(900, 500); g.enemies.append(far)
        g._hurt_player(PLAYER_AT + pygame.Vector2(30, 0), 12, 18, 70)
        self.assertFalse(g.dying); self.assertEqual(g.hp, 1)
        self.assertTrue(far.stunned); self.assertGreaterEqual(g.player.inv_timer, 1.9)
        g._hurt_player(PLAYER_AT + pygame.Vector2(30, 0), 12, 18, 70)
        self.assertTrue(g.dying)

    def test_volatile_core_chains_to_neighbours_only(self):
        g = fresh_game(); g.perks["volatile"] = 1
        a, b, far = Enemy(300, 300), Enemy(340, 300), Enemy(900, 600)
        g.enemies += [a, b, far]
        g._on_enemy_killed(a)
        self.assertNotIn(b, g.enemies, "neighbour inside 80px should die (2 dmg vs 2 hp)")
        self.assertIn(far, g.enemies)

    def _pierce_hits(self, pierce):
        g = fresh_game()
        e1, e2 = Enemy(300, 300), Enemy(330, 300)
        for e in (e1, e2): e.hp = 9; e.stunned = True; e.stun_timer = 9
        g.enemies += [e1, e2]
        pr = Projectile(280, 300, 1, 0, 14, 1, 650, Projectile.TYPE_PLASMA)
        pr.pierce = pierce; g.projectiles.append(pr)
        for _ in range(6): g.update(1 / 60)
        return e1.hp < 9, e2.hp < 9

    def test_pierce_passes_through_enemies(self):
        self.assertEqual(self._pierce_hits(0), (True, False))
        self.assertEqual(self._pierce_hits(1), (True, True))

    def test_shield_deflects_and_consumes_a_piercing_bolt(self):
        """A bolt that hits a shielded enemy does no damage and is NOT allowed to
        pierce onward — otherwise PIERCE would trivialise Shield Drones."""
        g = fresh_game()
        e1, e2 = Enemy(300, 300), Enemy(330, 300)
        for e in (e1, e2): e.hp = 9; e.stunned = True; e.stun_timer = 9
        g.enemies += [e1, e2]; e1.shield = 1      # collision runs before shields refresh
        pr = Projectile(280, 300, 1, 0, 14, 1, 650, Projectile.TYPE_PLASMA); pr.pierce = 3
        g.projectiles.append(pr)
        g.update(1 / 60)
        self.assertEqual((e1.hp, e2.hp), (9, 9))
        self.assertNotIn(pr, g.projectiles)

    def test_clearing_a_wave_offers_perks(self):
        g = fresh_game()
        g.wave_mgr._state = "active"; g.wave_mgr.wave = 1; g.wave_mgr._break_timer = 0
        g.wave_mgr._all_dead_timer = 1.19; g.wave_mgr._pending_spawns = []
        g.update(0.05)
        self.assertTrue(g.perk_pending); self.assertEqual(len(g.perk_choices), 3)


class _FakeManager:
    def __init__(self): self.popped = False
    def mouse_to_logical(self, pos): return pos
    def pop(self, **kw): self.popped = True


class PerkScreenTests(unittest.TestCase):
    def _state(self):
        from game.states.perk_state import PerkState
        g = fresh_game(); g.perk_choices = roll_choices({}); g.perk_pending = True
        m = _FakeManager(); st = PerkState(m, g); st.on_enter()
        return g, m, st

    def test_input_is_locked_on_entry(self):
        g, m, st = self._state()
        ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_1)
        st.handle_events([ev])
        self.assertFalse(m.popped); self.assertEqual(g.perks, {})

    def test_pick_after_lock_grants_perk_and_closes(self):
        g, m, st = self._state()
        chosen = g.perk_choices[1].key
        st.update(0.5)
        st.handle_events([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_2)])
        self.assertTrue(m.popped); self.assertEqual(g.perks, {chosen: 1})

    def test_renders_without_error(self):
        g, m, st = self._state(); st.update(0.5)
        surf = pygame.Surface((1280, 720), pygame.SRCALPHA)
        st.draw(surf)


class SoakTest(unittest.TestCase):
    def test_two_minutes_of_chaos_does_not_crash(self):
        random.seed(3)
        g = Game(None)
        surf = pygame.Surface((1280, 720), pygame.SRCALPHA)
        for k in PERKS: g.perks[k] = 1
        g.hp = 99
        for i in range(120 * 60):
            if i % 50 == 0:
                for t in ("standard", "hunter", "swarm", "phantom", "berserker",
                          "teleporter", "shield_drone", "splitter"):
                    g._spawn_entity(t)
            if i % 600 == 0: g._spawn_entity("boss")
            g.player.weapon_index = (i // 90) % 5
            g._logical_mouse = (random.randint(0, 1280), random.randint(0, 720))
            if i % 40 == 0: g.player.trigger_dash(pygame.key.get_pressed())
            if i % 55 == 0: g._do_hack()
            g.player._fire(g._logical_mouse, g.enemies, 1 / 60)
            g.update(1 / 60)
            if i % 4 == 0: g.draw(surf)
            g.hp = 99
            if len(g.enemies) > 150: g.enemies = g.enemies[-60:]
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
