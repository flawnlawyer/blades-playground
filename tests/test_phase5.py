"""Phase 5 tests (part 1): input layer, evolutions, synergies, Sniper."""
import math, os, random, sys, unittest
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
pygame.init()
pygame.display.set_mode((1280, 720))

from game.constants import *
from game.entities import Enemy, Boss, Fragment, Projectile, Sniper
from game.game import Game, _ENEMY_COLORS
from game.perks import PERKS, SYNERGIES, active_synergies, completing_synergies, meets, roll_choices
from game.player import Player
from game.wave_manager import WaveManager
from utils.gamepad import Gamepad, menu_key_for_button
from utils.keybinds import KEYS, Keybinds, RESERVED

NO_KEYS = pygame.key.get_pressed()


class K(dict):
    def __missing__(self, k): return False


def fresh_game(**kw) -> Game:
    random.seed(0)
    g = Game(None, **kw)
    g.enemies.clear(); g.meh_blocks.clear(); g.fragments.clear()
    g.wave_mgr._break_timer = 9999
    return g


class Src:
    """Input source stub: lets a test drive Game.update without real hardware."""
    def __init__(self, keys=None, mouse=(900, 360), fire=False):
        self.keys, self.mouse, self.fire = K(keys or {}), mouse, fire
    def poll(self, game):
        return self.keys, self.mouse, (self.fire, False, False)


# ── Keybinds ──────────────────────────────────────────────────────────────────

class KeybindTests(unittest.TestCase):
    def tearDown(self): KEYS.reset()

    def test_defaults_and_secondary_slots(self):
        kb = Keybinds()
        for k in (pygame.K_w, pygame.K_UP):
            self.assertTrue(kb.pressed(K({k: True}), "up"))
        self.assertFalse(kb.pressed(K({pygame.K_w: True}), "down"))
        self.assertTrue(kb.pressed(K({pygame.K_RSHIFT: True}), "dash"))
        self.assertFalse(kb.pressed(K(), "hack"))             # None slot must never crash

    def test_rebind_steals_the_key_from_its_old_action(self):
        kb = Keybinds()
        taken = kb.rebind("hack", 0, pygame.K_m)               # M belonged to MUTE
        self.assertEqual(taken, "mute"); self.assertIsNone(kb.map["mute"][0])
        self.assertEqual(kb.actions_for(pygame.K_m), ["hack"])

    def test_reserved_keys_cannot_be_bound(self):
        kb = Keybinds()
        for k in (pygame.K_ESCAPE, pygame.K_BACKQUOTE, pygame.K_F3, pygame.K_F10, pygame.K_F11, pygame.K_RETURN):
            self.assertIn(k, RESERVED)
            with self.assertRaises(ValueError): kb.rebind("dash", 0, k)

    def test_reset_and_persistence_roundtrip(self):
        kb = Keybinds(); kb.rebind("dash", 0, pygame.K_q)
        kb2 = Keybinds(); kb2.load(kb.to_dict())
        self.assertEqual(kb2.map["dash"][0], pygame.K_q)
        kb2.reset(); self.assertEqual(kb2.map["dash"][0], pygame.K_LSHIFT)

    def test_malformed_saved_data_is_ignored(self):
        kb = Keybinds()
        kb.load({"up": "garbage", "down": [1], "left": [True, "x"], "right": [pygame.K_ESCAPE, 99999999]})
        self.assertEqual(kb.map["up"], [pygame.K_w, pygame.K_UP])          # untouched defaults
        self.assertIsNone(kb.map["left"][0]); self.assertIsNone(kb.map["right"][0])   # reserved/bool dropped
        kb.load(None); kb.load([1, 2, 3])                                   # wrong container types: no crash

    def test_player_follows_rebound_movement_and_weapon_keys(self):
        KEYS.rebind("right", 0, pygame.K_l); KEYS.rebind("weapon3", 0, pygame.K_t)
        p = Player(100, 360); x0 = p.pos.x
        for _ in range(10): p.update(K({pygame.K_l: True}), 1 / 60, (900, 360), (False,) * 3, [])
        self.assertGreater(p.pos.x, x0 + 20)
        p.update(K({pygame.K_t: True}), 1 / 60, (900, 360), (False,) * 3, [])
        self.assertEqual(p.weapon_index, 2)


# ── Gamepad ───────────────────────────────────────────────────────────────────

class FakeCtrl:
    def __init__(self): self.axes, self.buttons, self.rumbled = {}, set(), []
    def get_axis(self, a): return int(self.axes.get(a, 0.0) * 32767)
    def get_button(self, b): return b in self.buttons
    def rumble(self, lo, hi, ms): self.rumbled.append((lo, hi, ms))


class GamepadTests(unittest.TestCase):
    def pad(self):
        g = Gamepad(); g.ctrl = FakeCtrl(); return g

    def test_no_controller_is_a_safe_noop(self):
        g = Gamepad(); g.ctrl = None
        self.assertFalse(g.connected); self.assertEqual(g.move_vector().length(), 0)
        self.assertFalse(g.fire()); self.assertFalse(g.button("CONTROLLER_BUTTON_A")); g.rumble()

    def test_deadzone_and_rescaling(self):
        g = self.pad()
        g.ctrl.axes[pygame.CONTROLLER_AXIS_LEFTX] = 0.1
        self.assertEqual(g.move_vector().length(), 0)                       # inside deadzone
        g.ctrl.axes[pygame.CONTROLLER_AXIS_LEFTX] = 1.0
        self.assertAlmostEqual(g.move_vector().length(), 1.0, places=2)
        g.ctrl.axes[pygame.CONTROLLER_AXIS_LEFTX] = 0.625                   # halfway past a 0.25 deadzone
        self.assertAlmostEqual(g.move_vector().length(), 0.5, delta=0.02)

    def test_right_stick_trigger_and_buttons(self):
        g = self.pad()
        g.ctrl.axes[pygame.CONTROLLER_AXIS_RIGHTY] = -1.0
        self.assertLess(g.aim_vector().y, -0.9)
        self.assertFalse(g.fire()); g.ctrl.axes[pygame.CONTROLLER_AXIS_TRIGGERRIGHT] = 0.8
        self.assertTrue(g.fire())
        g.ctrl.buttons.add(pygame.CONTROLLER_BUTTON_A); self.assertTrue(g.button("CONTROLLER_BUTTON_A"))

    def test_disabled_pad_reads_as_disconnected_and_rumble_works(self):
        g = self.pad(); g.enabled = False
        self.assertFalse(g.connected)
        g.enabled = True; g.rumble(0.5, 100); self.assertEqual(g.ctrl.rumbled, [(0.5, 0.5, 100)])

    def test_analog_movement_scales_speed_and_keys_win(self):
        def travel(analog, keys=None):
            p = Player(100, 360); p.analog = pygame.Vector2(*analog); x0 = p.pos.x
            for _ in range(30): p.update(K(keys or {}), 1 / 60, (900, 360), (False,) * 3, [])
            return p.pos.x - x0
        full, half = travel((1, 0)), travel((0.5, 0))
        self.assertAlmostEqual(half, full / 2, delta=full * 0.03)
        self.assertLess(travel((1, 0), {pygame.K_a: True}), 0)              # keys override the stick

    def test_dash_uses_stick_direction(self):
        p = Player(640, 360); p.analog = pygame.Vector2(0, -1)
        self.assertTrue(p.trigger_dash(NO_KEYS)); self.assertLess(p._dash_vel.y, -10)

    def test_menu_key_translation(self):
        self.assertEqual(menu_key_for_button(pygame.CONTROLLER_BUTTON_DPAD_DOWN, False), pygame.K_DOWN)
        self.assertEqual(menu_key_for_button(pygame.CONTROLLER_BUTTON_A, False), pygame.K_RETURN)
        self.assertEqual(menu_key_for_button(pygame.CONTROLLER_BUTTON_B, False), pygame.K_ESCAPE)
        self.assertIsNone(menu_key_for_button(pygame.CONTROLLER_BUTTON_A, True))     # A = dash in-game
        self.assertEqual(menu_key_for_button(pygame.CONTROLLER_BUTTON_START, True), pygame.K_ESCAPE)

    def test_state_manager_translates_buttons_and_mouse_retakes_aim(self):
        from game.state_manager import StateManager, BaseState
        m = StateManager(pygame.display.get_surface()); m.push(BaseState(m))
        down = pygame.event.Event(pygame.CONTROLLERBUTTONDOWN, button=pygame.CONTROLLER_BUTTON_DPAD_UP, instance_id=0)
        out = m._translate_pad([down])
        self.assertTrue(any(e.type == pygame.KEYDOWN and e.key == pygame.K_UP for e in out))
        m.gamepad.aiming = True
        m._translate_pad([pygame.event.Event(pygame.MOUSEMOTION, pos=(5, 5), rel=(1, 1), buttons=(0, 0, 0))])
        self.assertFalse(m.gamepad.aiming)

    def test_in_game_buttons_are_actions_not_menu_keys(self):
        from game.states.play_state import PlayState
        from game.state_manager import StateManager
        m = StateManager(pygame.display.get_surface()); ps = PlayState(m); m.push(ps)
        a = pygame.event.Event(pygame.CONTROLLERBUTTONDOWN, button=pygame.CONTROLLER_BUTTON_A, instance_id=0)
        self.assertFalse(any(e.type == pygame.KEYDOWN and e.key == pygame.K_RETURN for e in m._translate_pad([a])))

    def test_play_state_pad_actions(self):
        from game.states.play_state import PlayState
        from game.state_manager import StateManager
        m = StateManager(pygame.display.get_surface()); ps = PlayState(m); g = fresh_game()
        ps._pad_button(pygame.CONTROLLER_BUTTON_A, g); self.assertEqual(g.player.dash_charges, PLAYER_DASH_CHARGES - 1)
        e = Enemy(g.player.pos.x + 40, g.player.pos.y); g.enemies.append(e)
        ps._pad_button(pygame.CONTROLLER_BUTTON_X, g); self.assertTrue(e.stunned)
        ps._pad_button(pygame.CONTROLLER_BUTTON_RIGHTSHOULDER, g); self.assertEqual(g.player.weapon_index, 1)
        ps._pad_button(pygame.CONTROLLER_BUTTON_LEFTSHOULDER, g); ps._pad_button(pygame.CONTROLLER_BUTTON_LEFTSHOULDER, g)
        self.assertEqual(g.player.weapon_index, 4)                           # wraps around


class InputSourceTests(unittest.TestCase):
    def test_input_source_drives_movement_and_firing(self):
        g = fresh_game(); g.input_source = Src({pygame.K_d: True}, mouse=(900, 360), fire=True)
        x0 = g.player.pos.x
        for _ in range(20): g.update(1 / 60)
        self.assertGreater(g.player.pos.x, x0 + 20); self.assertGreater(len(g.projectiles) + g.score, 0)

    def test_pad_fire_shoots_without_the_mouse(self):
        g = fresh_game(); g.pad_fire = True; g._logical_mouse = (900, 360)
        for _ in range(5): g.update(1 / 60)
        self.assertGreater(len(g.projectiles), 0)

    def test_no_input_source_means_no_firing(self):
        g = fresh_game()
        for _ in range(5): g.update(1 / 60)
        self.assertEqual(len(g.projectiles), 0)


# ── Perk data: evolutions & synergies ─────────────────────────────────────────

class PerkDataTests(unittest.TestCase):
    EVOS = ("homing", "void_bloom", "tesla", "null_lance", "cluster")

    def test_evolutions_are_flagged_single_stack_and_have_prerequisites(self):
        for k in self.EVOS:
            p = PERKS[k]; self.assertTrue(p.evolution); self.assertEqual(p.max_stacks, 1); self.assertTrue(p.requires)
            for req, n in p.requires: self.assertIn(req, PERKS)

    def test_evolutions_never_offered_without_prerequisites(self):
        rng = random.Random(1)
        for _ in range(200):
            self.assertFalse(any(p.evolution for p in roll_choices({}, rng=rng)))

    def test_evolution_appears_sometimes_when_unlocked_and_never_twice(self):
        rng = random.Random(2); owned = {"overclock": 2, "pierce": 1}
        hits = sum(any(p.key == "homing" for p in roll_choices(owned, rng=rng)) for _ in range(300))
        self.assertTrue(60 < hits < 240, hits)                               # offered often, not always
        owned["homing"] = 1
        for _ in range(100): self.assertNotIn("homing", [p.key for p in roll_choices(owned, rng=rng)])

    def test_choices_are_always_distinct_and_at_most_three(self):
        rng = random.Random(3); owned = {k: 1 for k in ("overclock", "pierce", "arc_lattice", "surge", "salvage", "volatile")}
        for _ in range(200):
            c = roll_choices(owned, rng=rng); self.assertLessEqual(len(c), 3)
            self.assertEqual(len({p.key for p in c}), len(c))

    def test_synergy_queries(self):
        self.assertEqual(active_synergies({}), [])
        self.assertEqual([s.key for s in active_synergies({"pierce": 1, "volatile": 1})], ["detonating_trails"])
        self.assertEqual([s.key for s in completing_synergies({"pierce": 1}, "volatile")], ["detonating_trails"])
        self.assertEqual(completing_synergies({"pierce": 1, "volatile": 1}, "volatile"), [])   # already on
        self.assertTrue(meets((("a", 2),), {"a": 2})); self.assertFalse(meets((("a", 2),), {"a": 1}))

    def test_daily_seeded_rolls_are_reproducible(self):
        owned = {"overclock": 2, "pierce": 1}
        a = [p.key for p in roll_choices(owned, rng=random.Random("x"))]
        b = [p.key for p in roll_choices(owned, rng=random.Random("x"))]
        self.assertEqual(a, b)


# ── Evolution & synergy effects ───────────────────────────────────────────────

class EvolutionEffects(unittest.TestCase):
    def test_homing_bolts_curve_into_an_off_axis_enemy(self):
        def hit(homing):
            g = fresh_game(); e = Enemy(560, 250); e.hp = 9; e.stunned = True; e.stun_timer = 99; g.enemies.append(e)
            g.player.pos.update(300, 360)
            pr = Projectile(300, 360, 1, 0, 14, 1, 650, Projectile.TYPE_PLASMA); pr.homing = homing
            g.projectiles.append(pr)
            for _ in range(60): g.update(1 / 60); g.player.pos.update(300, 360)
            return e.hp < 9
        self.assertFalse(hit(False)); self.assertTrue(hit(True))

    def test_void_bloom_fires_nine_pellets(self):
        def pellets(perk):
            p = Player(640, 360); p.weapon_index = 1
            if perk: p.perks["void_bloom"] = 1
            p._fire((900, 360), [], 1 / 60); return len(p.new_projectiles)
        self.assertEqual((pellets(False), pellets(True)), (SPREAD_COUNT, SPREAD_COUNT + 4))

    def test_tesla_coil_chains_into_the_boss_for_extra_damage(self):
        def boss_loss(tesla):
            g = fresh_game(); g.boss = Boss(760, 360); g.boss.stunned = True; g.boss.stun_timer = 99
            hp0 = g.boss.hp; g.player.pos.update(640, 360); g.player.weapon_index = 2
            if tesla: g.perks["tesla"] = 1
            g.input_source = Src(fire=True)
            g.update(1 / 60); return hp0 - g.boss.hp
        self.assertEqual(boss_loss(False), 0)
        self.assertEqual(boss_loss(True), CHAIN_DAMAGE + 1)

    def test_null_lance_is_wider_and_hits_harder(self):
        g = fresh_game(); g.player.pos.update(400, 360); g.player._angle = 0.0
        e = Enemy(600, 360 + ENEMY_RADIUS + 10)                                # 10px beyond the normal hit width
        self.assertFalse(g._beam_hits(e, 1.0, 0.0)); g.perks["null_lance"] = 1
        self.assertTrue(g._beam_hits(e, 1.0, 0.0))
        def dmg(lance):
            g2 = fresh_game(); g2.player.pos.update(400, 360); g2.player._angle = 0.0
            if lance: g2.perks["null_lance"] = 1
            t = Enemy(600, 360); t.hp = 100; g2.enemies.append(t)
            for _ in range(30): g2._apply_beam(1 / 60)
            return 100 - t.hp
        self.assertAlmostEqual(dmg(True), dmg(False) * 1.5, delta=0.01)

    def test_cluster_bombs_reach_beyond_the_normal_blast(self):
        def survives(cluster):
            g = fresh_game(); a = 0.6
            e = Enemy(640 + math.cos(a) * 140, 360 + math.sin(a) * 140); e.hp = 2; g.enemies.append(e)
            if cluster: g.perks["cluster"] = 1
            pr = Projectile(640, 360, 1, 0, 6, BOMB_DAMAGE, 9999, Projectile.TYPE_BOMB)
            g._handle_bomb_explosion(pr); return e in g.enemies
        self.assertTrue(survives(False)); self.assertFalse(survives(True))


class SynergyEffects(unittest.TestCase):
    def test_detonating_trails_blast_a_neighbour_the_bolt_never_touches(self):
        def neighbour_hp(syn):
            g = fresh_game(); g.perks["pierce"] = 1
            if syn: g.perks["volatile"] = 1
            e1, e2 = Enemy(300, 300), Enemy(300, 340)                          # e2 is 40px off the bolt's path
            for e in (e1, e2): e.hp = 9; e.stunned = True; e.stun_timer = 99
            g.enemies += [e1, e2]
            pr = Projectile(280, 300, 1, 0, 14, 1, 650, Projectile.TYPE_PLASMA); pr.pierce = 1; g.projectiles.append(pr)
            for _ in range(2): g.update(1 / 60)
            return e2.hp
        self.assertEqual(neighbour_hp(False), 9); self.assertLess(neighbour_hp(True), 9)

    def test_slipstream_pulls_fragments_while_dashing_only(self):
        def collected(syn, dashing):
            g = fresh_game(); g.player.pos.update(640, 360)
            if syn: g.perks.update({"phase_drive": 1, "salvage": 1})
            g.fragments.append(Fragment(640 + 95, 360, "x")); g.player.is_dashing = dashing
            g._handle_collisions(); return not g.fragments
        self.assertTrue(collected(True, True))
        self.assertFalse(collected(True, False)); self.assertFalse(collected(False, True))

    def test_overcharged_arc_shortens_chain_cooldown_only_with_both_perks(self):
        def cd(perks):
            p = Player(100, 360); p.perks.update(perks); p.weapon_index = 2
            p._fire((900, 360), [Enemy(150, 360)], 1 / 60); return p._weapon_cds[2]
        self.assertEqual(cd({"overclock": 2}), CHAIN_CD)                         # overclock alone: unchanged
        self.assertAlmostEqual(cd({"overclock": 2, "arc_lattice": 1}), CHAIN_CD * 0.75 ** 2)

    def test_last_stand_second_wind_also_starts_chaos(self):
        g = fresh_game(); g.perks.update({"second_wind": 1, "surge": 1}); g.hp = 1
        g._hurt_player(pygame.Vector2(0, 0), 12, 18, 70)
        self.assertFalse(g.dying); self.assertTrue(g.player.chaos_mode)

    def test_regen_matrix_heals_on_every_sixth_fragment(self):
        g = fresh_game(); g.perks.update({"repair": 1, "salvage": 1})
        for i in range(12):
            g.fragments.append(Fragment(g.player.pos.x, g.player.pos.y, f"f{i}")); g._handle_collisions()
        self.assertEqual(g.hp, 3 + 2)

    def test_granting_the_completing_perk_announces_the_synergy(self):
        g = fresh_game(); g.grant_perk("pierce")
        n = len(g.particles); g.grant_perk("volatile")
        self.assertTrue(any("SYNERGY" in getattr(p, "text", "") for p in g.particles[n - 1:]))

    def test_perk_cards_show_synergy_and_evolution_hints_without_error(self):
        from game.states.perk_state import PerkState
        class M:
            def mouse_to_logical(s, p): return p
            def pop(s, **k): pass
        g = fresh_game(); g.perks.update({"pierce": 1, "overclock": 1})
        g.perk_choices = [PERKS["volatile"], PERKS["homing"], PERKS["surge"]]
        st = PerkState(M(), g); st.on_enter(); st.update(0.6)
        st.draw(pygame.Surface((1280, 720), pygame.SRCALPHA))


# ── Sniper ────────────────────────────────────────────────────────────────────

class SniperTests(unittest.TestCase):
    def test_telegraphs_then_fires_one_aimed_fast_bullet(self):
        s = Sniper(300, 360); s._cd = 0.01; player = pygame.Vector2(640, 360)
        t = 0.0; fired = None
        while t < 3.0 and fired is None:
            s.update(1 / 60, player); t += 1 / 60
            if s.aiming: self.assertEqual(s.bullet_queue, [], "no bullet while telegraphing")
            if s.bullet_queue: fired = s.bullet_queue[0]
        self.assertIsNotNone(fired)
        speed = math.hypot(fired[2], fired[3]); self.assertAlmostEqual(speed, SNIPER_BULLET_SPEED, delta=1)
        self.assertGreater(fired[2], 0)                                         # towards the player

    def test_aim_locks_for_the_final_quarter_second(self):
        s = Sniper(300, 360); s._cd = 0.01
        player = pygame.Vector2(640, 360)
        while not s.aiming or s._aim_t > 0.2: s.update(1 / 60, player)
        locked = pygame.Vector2(s.aim)
        s.update(1 / 60, pygame.Vector2(640, 100))                              # player dodges after the lock
        self.assertEqual(tuple(s.aim), tuple(locked))

    def test_hack_stun_cancels_the_shot(self):
        s = Sniper(300, 360); s._cd = 0.01
        while not s.aiming: s.update(1 / 60, pygame.Vector2(640, 360))
        s.stun(); self.assertFalse(s.aiming)
        for _ in range(60): s.update(1 / 60, pygame.Vector2(640, 360))
        self.assertEqual(s.bullet_queue, [])

    def test_keeps_its_distance(self):
        s = Sniper(560, 360); s._cd = 99; player = pygame.Vector2(640, 360)
        d0 = s.pos.distance_to(player)
        for _ in range(60): s.update(1 / 60, player)
        self.assertGreater(s.pos.distance_to(player), d0 + 30)

    def test_game_turns_sniper_shots_into_dodgeable_bullets(self):
        g = fresh_game(); g._spawn_entity("sniper", 200.0, 360.0)
        sn = g.enemies[0]; sn._cd = 0.05; sn.spawn_grace = 0
        g.player.pos.update(900, 360)
        got = False
        for _ in range(60 * 3):
            g.hp = 3; g.update(1 / 60); g.player.pos.update(900, 360)
            if g.enemy_bullets: got = True; break
        self.assertTrue(got)
        b = g.enemy_bullets[0]; self.assertEqual(b.color, SNIPER_COL); self.assertEqual(b.radius, 5)

    def test_wave_schedule_colour_and_console_support(self):
        def types(w):
            wm = WaveManager(); wm.wave = w; return {s[0] for s in wm._build_spawn_list()}
        self.assertNotIn("sniper", types(6)); self.assertIn("sniper", types(7)); self.assertIn("sniper", types(16))   # (wave 15 is a boss wave)
        self.assertIn(Sniper, _ENEMY_COLORS)
        from game.console import Console
        class M:
            active_game = None
            def quit(self): pass
        g = fresh_game(); M.active_game = g; c = Console(M()); c.execute("spawn sniper 2 400 300")
        self.assertEqual(sum(isinstance(e, Sniper) for e in g.enemies), 2)


if __name__ == "__main__":
    unittest.main()
