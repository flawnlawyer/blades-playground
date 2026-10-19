"""Phase 4 tests: console + terminal control, cheats, cheated-run protection, graphics upgrades."""
import contextlib, io, os, random, subprocess, sys, tempfile, unittest
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np
import pygame
pygame.init()
pygame.display.set_mode((1280, 720))

from game import console as C
from game.console import Console
from game.constants import *
from game.entities import Enemy, Hunter, Berserker, Prism, Boss, Projectile
from game.game import Game, _ENEMY_COLORS
from game.perks import PERKS
from game.renderer import Renderer, THEMES

NO_KEYS = pygame.key.get_pressed()


class FakeMgr:
    def __init__(self, game=None):
        self.active_game, self.quit_called, self.replaced = game, False, []
    def quit(self): self.quit_called = True
    def replace_all(self, state, **kw): self.replaced.append(state)


def fresh_game(**kw) -> Game:
    random.seed(0)
    g = Game(None, **kw)
    g.enemies.clear(); g.meh_blocks.clear(); g.fragments.clear()
    g.wave_mgr._break_timer = 9999
    return g


def console_for(game=None):
    return Console(FakeMgr(game))


def run(con, line):
    """Execute and return the output lines produced (excluding the echoed input)."""
    n = len(con.lines)
    con.execute(line)
    return [(t, k) for t, k in con.lines[n:] if not t.startswith("> ")]


def last(con):
    return con.lines[-1]


class ConsoleBasics(unittest.TestCase):
    def test_help_lists_groups_and_details(self):
        con = console_for(); out = " ".join(t for t, _ in run(con, "help"))
        for name in ("god*", "spawn*", "perk*", "bloom", "music", "get", "set"):
            self.assertIn(name, out)
        detail = run(con, "help spawn")
        self.assertIn("[CHEAT]", detail[1][0])

    def test_unknown_and_malformed_commands_never_crash(self):
        con = console_for()
        self.assertEqual(run(con, "frobnicate")[0][1], "err")
        self.assertEqual(run(con, 'echo "unclosed')[0][1], "err")
        self.assertEqual(run(con, "")  , [])

    def test_game_commands_need_an_active_game_but_system_ones_do_not(self):
        con = console_for(None)
        self.assertIn("no active game", run(con, "god")[0][0])
        self.assertEqual(run(con, "echo hi")[0], ("hi", "info"))
        run(con, "quit"); self.assertTrue(con.manager.quit_called)

    def test_restart_keeps_daily_mode(self):
        con = console_for(fresh_game(seed=5)); run(con, "restart")
        self.assertTrue(con.manager.replaced[0].daily)

    def test_a_crashing_command_is_contained(self):
        @C.command("boom_test", needs_game=False)
        def _boom(ctx, args): raise RuntimeError("kaboom")
        try:
            out = run(console_for(), "boom_test")
            self.assertIn("RuntimeError: kaboom", out[0][0])
        finally:
            C.COMMANDS.pop("boom_test", None)


class CheatEffects(unittest.TestCase):
    def setUp(self):
        self.g = fresh_game(); self.con = console_for(self.g)

    def test_god_blocks_damage(self):
        run(self.con, "god on")
        self.g._hurt_player(pygame.Vector2(0, 0), 12, 18, 70)
        self.assertEqual(self.g.hp, 3)
        run(self.con, "god off")
        self.g._hurt_player(pygame.Vector2(0, 0), 12, 18, 70)
        self.assertEqual(self.g.hp, 2)

    def test_god_toggles_without_argument(self):
        run(self.con, "god"); self.assertTrue(self.g.god)
        run(self.con, "god"); self.assertFalse(self.g.god)

    def test_hp_heal_energy(self):
        run(self.con, "hp 9"); self.assertEqual(self.g.hp, 9)
        self.g.hp = 1; run(self.con, "heal"); self.assertEqual(self.g.hp, 3)
        run(self.con, "energy 40"); self.assertEqual(self.g.player.energy, 40)
        run(self.con, "energy full"); self.assertEqual(self.g.player.energy, self.g.player.max_energy)

    def test_chaos_on_and_off(self):
        run(self.con, "chaos 12")
        self.assertTrue(self.g.player.chaos_mode); self.assertEqual(self.g.player.chaos_timer, 12)
        run(self.con, "chaos off"); self.assertFalse(self.g.player.chaos_mode)

    def test_speed_multiplier_changes_distance_travelled(self):
        class K(dict):
            def __missing__(s, k): return False
        keys = K({pygame.K_d: True})
        def travel(mult):
            p = fresh_game().player; p.speed_mult = mult; x0 = p.pos.x
            for _ in range(30): p.update(keys, 1 / 60, (900, 360), (False,) * 3, [])
            return p.pos.x - x0
        self.assertAlmostEqual(travel(2.0), 2 * travel(1.0), delta=0.5)

    def test_dmg_multiplier_scales_projectiles(self):
        def dmg(cmd):
            g = fresh_game(); con = console_for(g)
            if cmd: run(con, cmd)
            g._logical_mouse = (900, 360)
            g.player._fire(g._logical_mouse, [], 1 / 60); g.update(1 / 60)
            return g.projectiles[0].damage
        self.assertAlmostEqual(dmg("dmg 7"), 7 * dmg(None))

    def test_firerate_shortens_cooldown(self):
        run(self.con, "firerate 4")
        self.g.player._fire((900, 360), [], 1 / 60)
        self.assertAlmostEqual(self.g.player._weapon_cds[0], PLASMA_CD / 4)

    def test_infinite_dash_and_dash_charges(self):
        run(self.con, "infdash on")
        for _ in range(5):
            self.g.player._dash_time_left = 0; self.g.player.is_dashing = False
            self.assertTrue(self.g.player.trigger_dash(NO_KEYS))
        self.assertEqual(self.g.player.dash_charges, self.g.player.max_dash_charges)
        run(self.con, "infdash off"); run(self.con, "dash 0")
        self.g.player._dash_time_left = 0; self.g.player.is_dashing = False
        self.assertFalse(self.g.player.trigger_dash(NO_KEYS))

    def test_tp_and_weapon(self):
        run(self.con, "tp 100 200"); self.assertEqual(tuple(self.g.player.pos), (100, 200))
        run(self.con, "weapon 4"); self.assertEqual(self.g.player.weapon_index, 3)

    def test_score_and_streak(self):
        run(self.con, "score 4242"); self.assertEqual(self.g.score, 4242)
        run(self.con, "streak 12"); self.assertEqual(self.g.streak, 12); self.assertEqual(self.g._streak_mult(), 2.0)

    def test_validation_errors_do_not_change_state_or_flag_the_run(self):
        for bad in ("hp 0", "hp abc", "hp", "speed 99", "tp 5000 5", "weapon 9", "dmg -1"):
            out = run(self.con, bad)
            self.assertEqual(out[0][1], "err", bad)
        self.assertEqual(self.g.hp, 3); self.assertFalse(self.g.cheated)


class WorldCommands(unittest.TestCase):
    def setUp(self):
        self.g = fresh_game(); self.con = console_for(self.g)

    def test_spawn_variants(self):
        run(self.con, "spawn berserker 3 100 120")
        zerks = [e for e in self.g.enemies if isinstance(e, Berserker)]
        self.assertEqual(len(zerks), 3); self.assertEqual(tuple(zerks[0].pos), (100, 120))
        run(self.con, "spawn drone 2"); self.assertEqual(len(self.g.enemies), 5)
        self.assertEqual(run(self.con, "spawn nonsense")[0][1], "err")
        self.assertEqual(run(self.con, "spawn hunter 9999")[0][1], "err")

    def test_kill_by_type_and_all_including_boss(self):
        run(self.con, "spawn hunter 3"); run(self.con, "spawn standard 2")
        run(self.con, "kill hunter")
        self.assertTrue(all(not isinstance(e, Hunter) for e in self.g.enemies))
        self.assertEqual(len(self.g.enemies), 2)
        run(self.con, "boss prism"); run(self.con, "kill all")
        self.assertEqual(self.g.enemies, []); self.assertIsNone(self.g.boss)

    def test_boss_command(self):
        run(self.con, "boss prism 2")
        self.assertIsInstance(self.g.boss, Prism); self.assertEqual(self.g.boss.max_hp, PRISM_HP + 20)
        run(self.con, "boss"); self.assertIsInstance(self.g.boss, Boss)
        self.assertEqual(run(self.con, "boss dragon")[0][1], "err")

    def test_wave_jump_clears_arena_then_starts_that_wave(self):
        run(self.con, "spawn standard 5")
        self.g.wave_mgr._break_timer = 0     # (setUp froze the timer; set_wave must override it)
        run(self.con, "wave 7")
        self.assertEqual(self.g.enemies, [])
        self.g.stress_target = 0
        for _ in range(60): self.g.update(1 / 60)
        self.assertEqual(self.g.wave_mgr.wave, 7)
        self.assertGreater(len(self.g.enemies), 0)

    def test_nextwave(self):
        self.g.wave_mgr.wave = 3
        run(self.con, "nextwave")
        for _ in range(60): self.g.update(1 / 60)
        self.assertEqual(self.g.wave_mgr.wave, 4)

    def test_freeze_stops_enemies_and_bullets(self):
        e = Enemy(500, 360); self.g.enemies.append(e); self.g.player.pos.update(700, 360)
        run(self.con, "freeze on")
        x0 = e.pos.x
        for _ in range(20): self.g.update(1 / 60); self.g.player.pos.update(700, 360)
        self.assertEqual(e.pos.x, x0)
        run(self.con, "freeze off")
        for _ in range(20): self.g.update(1 / 60); self.g.player.pos.update(700, 360)
        self.assertNotEqual(e.pos.x, x0)

    def test_timescale_is_clamped_and_stored(self):
        run(self.con, "timescale 0.5"); self.assertEqual(self.g.time_scale, 0.5)
        self.assertEqual(run(self.con, "timescale 50")[0][1], "err")

    def test_perk_commands(self):
        run(self.con, "perk overclock 2"); self.assertEqual(self.g.perks["overclock"], 2)
        run(self.con, "perk pierce"); self.assertEqual(self.g.perks["pierce"], 1)
        run(self.con, "perk all")
        self.assertTrue(all(self.g.perks[k] == p.max_stacks for k, p in PERKS.items()))
        run(self.con, "unperk phase_drive")
        self.assertNotIn("phase_drive", self.g.perks)
        self.assertLessEqual(self.g.player.dash_charges, self.g.player.max_dash_charges)
        run(self.con, "clearperks"); self.assertEqual(self.g.perks, {})
        self.assertEqual(run(self.con, "perk banana")[0][1], "err")
        self.assertIn("overclock", " ".join(t for t, _ in run(self.con, "perks")))


class CheatTracking(unittest.TestCase):
    def test_first_cheat_flags_the_run_and_announces_it_once(self):
        g = fresh_game(); con = console_for(g)
        out = run(con, "god"); self.assertTrue(g.cheated)
        self.assertEqual(sum(1 for t, k in out if k == "cheat"), 1)
        self.assertEqual(sum(1 for t, k in run(con, "hp 5") if k == "cheat"), 0)

    def test_visual_audio_and_info_commands_do_not_flag(self):
        g = fresh_game(); con = console_for(g)
        for cmd in ("bloom off", "bloom 1.2", "theme 2", "theme auto", "vignette 0.3", "shake 5",
                    "music off", "volume 0.4", "debug", "seed", "perks", "help", "get player", "echo x"):
            self.assertNotIn("err", [k for _, k in run(con, cmd)], cmd)       # (some commands are silent)
        self.assertFalse(g.cheated)

    def test_cheated_run_is_not_saved_to_scores_or_daily_board(self):
        from game.states.gameover_state import GameOverState
        from utils import data_manager as dm
        old = dm.DATA_DIR, dm.SAVE_FILE
        with tempfile.TemporaryDirectory() as tmp:
            dm.DATA_DIR = type(old[0])(tmp); dm.SAVE_FILE = dm.DATA_DIR / "hs.json"
            try:
                g = fresh_game(seed=9); g.daily_date = "20261016"; g.cheated = True
                go = GameOverState(FakeMgr(), score=99999, wave=9, time=100, game=g); go.on_enter()
                self.assertFalse(go._entering); self.assertFalse(go._qualifies)
                self.assertIn("NOT SAVED", go._daily_info[0])
                self.assertIsNone(dm.load_daily("20261016"))
                clean = fresh_game(seed=9); clean.daily_date = "20261016"
                go2 = GameOverState(FakeMgr(), score=99999, wave=9, time=100, game=clean); go2.on_enter()
                self.assertTrue(go2._entering)
                self.assertEqual(dm.load_daily("20261016")["score"], 99999)
            finally:
                dm.DATA_DIR, dm.SAVE_FILE = old


class GetSet(unittest.TestCase):
    def setUp(self):
        self.g = fresh_game(); self.con = console_for(self.g)

    def test_get_reads_values_and_lists_objects(self):
        self.assertIn("speed_mult = 1.0", run(self.con, "get player.speed_mult")[0][0])
        self.assertIn("god = False", " ".join(t for t, _ in run(self.con, "get game")))
        self.assertIn("roots", run(self.con, "get")[0][0])

    def test_set_changes_values_and_flags_gameplay_roots_only(self):
        run(self.con, "set renderer.bloom_strength 0.9")
        self.assertEqual(self.g.renderer.bloom_strength, 0.9); self.assertFalse(self.g.cheated)
        run(self.con, "set player.speed_mult 2"); self.assertEqual(self.g.player.speed_mult, 2)
        self.assertTrue(self.g.cheated)

    def test_set_is_type_checked_and_cannot_execute_code(self):
        for bad in ("set player.speed_mult banana", "set player.speed_mult __import__('os').system('x')",
                    "set wave.wave 2.5", "set game.god maybe", "set player.pos 5",
                    "set game._hitstop_t 1", "set nope.x 1", "set player.ghost 1", "set player"):
            self.assertEqual(run(self.con, bad)[0][1], "err", bad)

    def test_bool_and_int_attributes(self):
        run(self.con, "set game.god on"); self.assertTrue(self.g.god)
        run(self.con, "set wave.wave 4"); self.assertEqual(self.g.wave_mgr.wave, 4)


class Editing(unittest.TestCase):
    def key(self, k, uni="", mod=0):
        return pygame.event.Event(pygame.KEYDOWN, key=k, unicode=uni, mod=mod)

    def typed(self, con, text):
        con.handle_events([self.key(ord(c), c) for c in text])

    def test_typing_enter_backspace_history(self):
        con = console_for(fresh_game())
        self.typed(con, "echox"); con.handle_events([self.key(pygame.K_BACKSPACE)])
        self.typed(con, " hello"); con.handle_events([self.key(pygame.K_RETURN)])
        self.assertIn(("hello", "info"), con.lines); self.assertEqual(con.input, "")
        con.handle_events([self.key(pygame.K_UP)]); self.assertEqual(con.input, "echo hello")
        con.handle_events([self.key(pygame.K_DOWN)]); self.assertEqual(con.input, "")

    def test_tab_completion(self):
        con = console_for(fresh_game())
        con.input = "spa"; con.complete(); self.assertEqual(con.input, "spawn ")
        con.input = "perk ov"; con.complete(); self.assertEqual(con.input, "perk overclock ")
        con.input = "boss pr"; con.complete(); self.assertEqual(con.input, "boss prism ")
        con.input = "s"; con.complete()                       # ambiguous: common prefix, lists options
        self.assertTrue(con.input.startswith("s")); self.assertIn("spawn", " ".join(t for t, _ in con.lines[-2:]))

    def test_escape_closes_and_toggle_reopens(self):
        con = console_for(); con.toggle(); self.assertTrue(con.open)
        con.handle_events([self.key(pygame.K_ESCAPE)]); self.assertFalse(con.open)

    def test_scrollback_and_clear(self):
        con = console_for()
        for i in range(60): con.print(f"line {i}")
        con.handle_events([self.key(pygame.K_PAGEUP)]); self.assertGreater(con.scroll, 0)
        con.handle_events([self.key(pygame.K_PAGEDOWN)]); self.assertEqual(con.scroll, 0)
        run(con, "clear"); self.assertEqual(con.lines, [])

    def test_log_is_capped(self):
        con = console_for()
        for i in range(Console.MAX_LINES + 100): con.print(str(i))
        self.assertLessEqual(len(con.lines), Console.MAX_LINES)

    def test_overlay_draws_open_closed_and_scrolled(self):
        g = fresh_game(); g.cheated = True; con = console_for(g)
        surf = pygame.Surface((1280, 720), pygame.SRCALPHA)
        con.draw(surf); con.toggle()
        for i in range(60): con.print(f"line {i}")
        con.scroll = 5; con.input = "spawn"; con.draw(surf)
        self.assertGreater(int(pygame.surfarray.array3d(surf).sum()), 0)


class TerminalBridge(unittest.TestCase):
    def test_queued_terminal_commands_run_and_echo_to_stdout(self):
        con = console_for(fresh_game()); con._q.put("echo from-terminal"); con._q.put("hp 7")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            con.update(0.016)
        self.assertIn("from-terminal", buf.getvalue()); self.assertEqual(con.manager.active_game.hp, 7)

    def test_real_stdin_thread_end_to_end(self):
        """Pipe commands into a real process: the stdin thread must feed the console."""
        code = (
            "import os,sys,time; os.environ['SDL_VIDEODRIVER']='dummy'; os.environ['SDL_AUDIODRIVER']='dummy'\n"
            f"sys.path.insert(0,{ROOT!r})\n"
            "from game.console import Console\n"
            "class M:\n"
            "    active_game=None\n"
            "    def quit(self): print('QUIT-CALLED', flush=True)\n"
            "c=Console(M()); c.start_terminal()\n"
            "t0=time.time()\n"
            "while time.time()-t0<3:\n"
            "    c.update(0.01); time.sleep(0.01)\n")
        out = subprocess.run([sys.executable, "-c", code], input="echo piped-hello\nquit\n",
                             capture_output=True, text=True, timeout=30)
        self.assertIn("piped-hello", out.stdout, out.stdout + out.stderr)
        self.assertIn("QUIT-CALLED", out.stdout)


# ── Graphics ──────────────────────────────────────────────────────────────────

class SpawnAndDeathFx(unittest.TestCase):
    def test_spawn_in_grace_protects_then_releases(self):
        g = fresh_game(); g._spawn_entity("standard", 640.0, 360.0)
        e = g.enemies[0]
        self.assertGreater(e.spawn_grace, 0)
        self.assertTrue(any(type(p).__name__ == "Ring" for p in g.particles), "converging ring expected")
        g.player.pos.update(640, 360); g.player.inv_timer = 0
        g._handle_collisions(); self.assertEqual(g.hp, 3, "no contact damage while spawning in")
        e.spawn_grace = 0; e.stunned = False
        g._handle_collisions(); self.assertEqual(g.hp, 2)

    def test_no_spawn_telegraph_in_stress_mode(self):
        g = fresh_game(); g.stress_target = 10; g._spawn_entity("standard")
        self.assertEqual(g.enemies[0].spawn_grace, 0)

    def test_every_enemy_type_has_a_death_colour(self):
        from game.entities import Enemy, Hunter, SwarmNode, Phantom, Berserker, Teleporter, ShieldDrone, Splitter
        for cls in (Enemy, Hunter, SwarmNode, Phantom, Berserker, Teleporter, ShieldDrone, Splitter):
            self.assertIn(cls, _ENEMY_COLORS)

    def test_kill_emits_ring_flash_and_dust_in_enemy_colour(self):
        g = fresh_game(); e = Berserker(300, 300); g.enemies.append(e)
        n = len(g.particles); d = len(g.dust)
        g._on_enemy_killed(e)
        kinds = [type(p).__name__ for p in g.particles[n:]]
        self.assertIn("Ring", kinds); self.assertIn("DashTrail", kinds)
        self.assertGreater(len(g.dust), d)

    def test_muzzle_flash_on_fire(self):
        g = fresh_game(); d = len(g.dust)
        g._logical_mouse = (900, 360); g.player._fire(g._logical_mouse, [], 1 / 60); g.update(1 / 60)
        self.assertGreater(len(g.dust), d)
        self.assertTrue(any(type(p).__name__ == "Ring" for p in g.particles))

    def test_dash_sprays_dust(self):
        g = fresh_game(); g.player.trigger_dash(NO_KEYS)
        d = len(g.dust); g.update(1 / 60)
        self.assertGreater(len(g.dust), d)


class BossIntro(unittest.TestCase):
    def test_intro_slows_world_and_holds_the_boss_back(self):
        g = fresh_game(); g.spawn_boss("prism")
        self.assertGreater(g._boss_intro, 1.0); self.assertTrue(g.boss.stunned)
        e = Enemy(500, 360); g.enemies.append(e); g.player.pos.update(700, 360)
        x0 = e.pos.x
        for _ in range(10): g.update(1 / 60); g.player.pos.update(700, 360)
        slow = e.pos.x - x0
        g2 = fresh_game(); e2 = Enemy(500, 360); g2.enemies.append(e2); g2.player.pos.update(700, 360)
        x1 = e2.pos.x
        for _ in range(10): g2.update(1 / 60); g2.player.pos.update(700, 360)
        self.assertLess(slow, (e2.pos.x - x1) * 0.6)
        self.assertEqual(g.enemy_bullets, [])

    def test_boss_attacks_after_intro_ends(self):
        g = fresh_game(); g.spawn_boss("prism")
        for _ in range(int(60 * 9)):
            g.player.pos.update(640, 650); g.hp = 3; g.update(1 / 60)
        self.assertLessEqual(g._boss_intro, 0); self.assertFalse(g.boss.stunned)
        self.assertGreater(g.boss._attack_i, 0, "boss must have started its attack cycle")

    def test_intro_draws_letterbox_bars(self):
        g = fresh_game(); g.spawn_boss("architect"); g._boss_intro = g._boss_intro_total * 0.5
        surf = pygame.Surface((1280, 720), pygame.SRCALPHA); g.draw(surf)
        self.assertEqual(tuple(surf.get_at((5, 3)))[:3], (0, 0, 0)); self.assertEqual(tuple(surf.get_at((5, 716)))[:3], (0, 0, 0))

    def test_stress_mode_skips_the_intro(self):
        g = fresh_game(); g.stress_target = 5; g.spawn_boss("prism")
        self.assertEqual(g._boss_intro, 0)


class Themes(unittest.TestCase):
    def test_each_theme_is_visually_distinct(self):
        r = Renderer(); imgs = []
        for i in range(len(THEMES)):
            r.set_theme(i); r._fade = 0
            s = pygame.Surface((1280, 720)); r.draw_background(s, False)
            imgs.append(pygame.surfarray.array3d(s).mean(axis=(0, 1)))
        for i in range(len(imgs)):
            for j in range(i + 1, len(imgs)):
                self.assertGreater(float(np.abs(imgs[i] - imgs[j]).sum()), 1.0)

    def test_crossfade_runs_for_about_a_second_and_draws(self):
        r = Renderer(); r.set_theme(2); self.assertEqual(r._fade, 1.0)
        s = pygame.Surface((1280, 720)); r.draw_background(s, False)
        for _ in range(70): r.update(1 / 60, False)
        self.assertEqual(r._fade, 0.0)

    def test_auto_theme_follows_wave_and_manual_overrides(self):
        g = fresh_game(); g.wave_mgr._state = "break"; g.wave_mgr.wave = 4; g.wave_mgr._break_timer = 0.0
        g.update(1 / 60); self.assertEqual(g.wave_mgr.wave, 5); self.assertEqual(g.renderer._theme, 1)
        con = console_for(g); run(con, "theme 3"); self.assertFalse(g.renderer.theme_auto)
        self.assertEqual(g.renderer._theme, 3)
        run(con, "theme auto"); self.assertTrue(g.renderer.theme_auto); self.assertEqual(g.renderer._theme, 1)

    def test_vignette_command_rebakes(self):
        r = Renderer(); before = pygame.surfarray.array3d(r._overlay)[5, 5, 0]
        r.set_vignette(0.0)
        self.assertGreater(int(pygame.surfarray.array3d(r._overlay)[5, 5, 0]), int(before))


class Bloom(unittest.TestCase):
    def _scene(self):
        s = pygame.Surface((1280, 720), pygame.SRCALPHA); s.fill((0, 0, 0, 255))
        pygame.draw.circle(s, (255, 255, 255), (640, 360), 14); return s

    def test_bright_things_glow_and_dark_areas_stay_dark(self):
        r = Renderer(); s = self._scene()
        near_before = int(s.get_at((662, 360))[0]); far_before = int(s.get_at((100, 100))[0])
        r.draw_bloom(s)
        self.assertGreater(int(s.get_at((662, 360))[0]), near_before + 20)    # halo 8px outside the disc
        self.assertGreater(int(s.get_at((678, 360))[0]), 5)                   # ...still faintly lit further out
        self.assertEqual(int(s.get_at((100, 100))[0]), far_before)            # empty corner untouched

    def test_dim_surfaces_do_not_bloom(self):
        r = Renderer(); s = pygame.Surface((1280, 720), pygame.SRCALPHA); s.fill((100, 100, 120, 255))
        before = pygame.surfarray.array3d(s).copy(); r.draw_bloom(s)
        self.assertTrue(np.array_equal(before, pygame.surfarray.array3d(s)), "gray blocks must not glow")

    def test_zero_strength_is_a_noop_and_toggle_command_works(self):
        r = Renderer(); r.bloom_strength = 0; s = self._scene(); before = pygame.surfarray.array3d(s).copy()
        r.draw_bloom(s); self.assertTrue(np.array_equal(before, pygame.surfarray.array3d(s)))
        g = fresh_game(); con = console_for(g)
        run(con, "bloom off"); self.assertFalse(g.renderer.bloom_enabled)
        run(con, "bloom 1.5"); self.assertTrue(g.renderer.bloom_enabled); self.assertEqual(g.renderer.bloom_strength, 1.5)

    def test_game_skips_bloom_for_huge_crowds(self):
        g = fresh_game(); calls = []
        g.renderer.draw_bloom = lambda surf: calls.append(1)
        surf = pygame.Surface((1280, 720), pygame.SRCALPHA)
        g.draw(surf); self.assertEqual(len(calls), 1)
        for i in range(130): g.enemies.append(Enemy(50 + i * 8 % 1100, 100 + i * 5 % 500))
        g.draw(surf); self.assertEqual(len(calls), 1)


class CheatHud(unittest.TestCase):
    def test_cheat_tag_draws_without_error_in_all_modes(self):
        g = fresh_game(seed=4); g.cheated = True; g.daily_date = "20261016"
        g.draw(pygame.Surface((1280, 720), pygame.SRCALPHA))


if __name__ == "__main__":
    unittest.main()


class HudBannerLayout(unittest.TestCase):
    def _lit_row_runs(self, g):
        surf = pygame.Surface((1280, 720), pygame.SRCALPHA); surf.fill((0, 0, 0, 255)); g.draw(surf)
        strip = pygame.surfarray.array3d(surf).astype(int)[440:840, :120, :]
        rowmax = strip.max(axis=(0, 2)); runs = []
        for y in range(120):
            if rowmax[y] > 70:                       # text is >=110 even at the dimmest pulse; background ~47
                if runs and y - runs[-1][1] <= 2: runs[-1][1] = y
                else: runs.append([y, y])
        return runs

    def test_chaos_banner_and_wave_countdown_are_separate_rows(self):
        g = fresh_game(); g.wave_mgr.wave = 3                         # countdown only shows from wave 1 on
        g.wave_mgr._state = "break"; g.wave_mgr._break_timer = 3.0
        g.player.chaos_mode = True; g.player.chaos_timer = 5
        runs = self._lit_row_runs(g)
        self.assertEqual(len(runs), 2, runs)                          # two distinct text bands...
        self.assertGreater(runs[1][0] - runs[0][1], 4, runs)          # ...with clear space between

    def test_countdown_alone_sits_at_the_top_row(self):
        g = fresh_game(); g.wave_mgr.wave = 3
        g.wave_mgr._state = "break"; g.wave_mgr._break_timer = 3.0
        runs = self._lit_row_runs(g)
        self.assertEqual(len(runs), 1); self.assertLess(runs[0][0], 45)
