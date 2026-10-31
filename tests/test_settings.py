"""Settings + Controls screens, settings application, and the saved-volume bug fix."""
import os, random, sys, tempfile, unittest
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
pygame.init()
pygame.display.set_mode((1280, 720))

from game.game import Game
from utils import data_manager as dm, settings as S
from utils.keybinds import KEYS, ACTIONS


class TempData:
    def setUp(self):
        self._old = dm.DATA_DIR, dm.SAVE_FILE
        self._tmp = tempfile.TemporaryDirectory()
        dm.DATA_DIR = type(self._old[0])(self._tmp.name); dm.SAVE_FILE = dm.DATA_DIR / "hs.json"
    def tearDown(self):
        KEYS.reset(); dm.DATA_DIR, dm.SAVE_FILE = self._old; self._tmp.cleanup()


class FM:
    def __init__(self):
        self.popped, self.pushed, self._fullscreen = False, None, False
        self.gamepad = type("P", (), {"enabled": True, "deadzone": 0.25})()
        self.fs_toggled = 0
    def mouse_to_logical(self, p): return p
    def pop(self, **k): self.popped = True
    def push(self, st, **k): self.pushed = st
    def toggle_fullscreen(self): self.fs_toggled += 1


def key(k, uni=""): return pygame.event.Event(pygame.KEYDOWN, key=k, unicode=uni, mod=0)


class SettingsData(TempData, unittest.TestCase):
    def test_defaults_when_nothing_saved_or_garbage(self):
        self.assertEqual(S.load()["bloom"], "MEDIUM")
        for junk in (None, 7, "x", [], {"volume": "loud", "bloom": "ULTRA", "shake": -5, "deadzone": 99, "music": "yes"}):
            s = S.normalise(junk)
            self.assertEqual(s["bloom"], "MEDIUM"); self.assertTrue(0 <= s["shake"] <= 1)
            self.assertTrue(0.05 <= s["deadzone"] <= 0.6); self.assertIs(s["music"], True)

    def test_values_are_clamped(self):
        s = S.normalise({"volume": 5, "vignette": -1, "deadzone": 0.0})
        self.assertEqual((s["volume"], s["vignette"], s["deadzone"]), (1.0, 0.0, 0.05))

    def test_roundtrip_through_the_save_file(self):
        s = S.normalise({"volume": 0.3, "bloom": "HIGH", "hitstop": False}); S.save(s)
        back = S.load(); self.assertEqual((back["volume"], back["bloom"], back["hitstop"]), (0.3, "HIGH", False))

    def test_settings_do_not_clobber_scores_or_progression(self):
        dm.save_score("ABC", 123, 4, 50); S.save(S.normalise({"volume": 0.1}))
        self.assertEqual(dm.load_scores()[0]["score"], 123)


class ApplySettings(TempData, unittest.TestCase):
    def game(self):
        random.seed(0); g = Game(None); g.meh_blocks.clear(); return g

    def test_saved_volume_actually_reaches_the_game(self):
        """The original game never applied the saved volume (each run built its own
        SoundManager at the default).  Regression test for that bug."""
        g = self.game(); S.apply_to_game(g, S.normalise({"volume": 0.2}))
        self.assertAlmostEqual(g.audio.volume, 0.2)

    def test_mute_music_bloom_shake_hitstop_vignette(self):
        g = self.game()
        S.apply_to_game(g, S.normalise({"muted": True, "music": False, "bloom": "OFF", "shake": 0.0,
                                        "hitstop": False, "vignette": 0.2}))
        self.assertTrue(g.audio.muted); self.assertTrue(g.music.disabled)
        self.assertFalse(g.renderer.bloom_enabled); self.assertAlmostEqual(g.renderer.vignette, 0.2)
        g.shake = 20; self.assertEqual(g._shake_offset(1.234), (0, 0))      # shake scaled to nothing
        g._freeze(0.2); self.assertEqual(g._hitstop_t, 0.0)                 # hit-stop disabled
        g.music.start(); self.assertFalse(g.music._playing)                 # music stays off

    def test_bloom_levels_map_to_strengths(self):
        for name, strength in S.BLOOM_LEVELS:
            g = self.game(); S.apply_to_game(g, S.normalise({"bloom": name}))
            self.assertEqual(g.renderer.bloom_strength, strength); self.assertEqual(g.renderer.bloom_enabled, strength > 0)

    def test_shake_scale_halves_the_shake(self):
        g = self.game(); g.shake = 20; full = max(abs(g._shake_offset(t / 7)[0]) for t in range(100))
        S.apply_to_game(g, S.normalise({"shake": 0.5})); half = max(abs(g._shake_offset(t / 7)[0]) for t in range(100))
        self.assertAlmostEqual(half, full / 2, delta=1.5)

    def test_apply_global_loads_keybinds_and_pad_options(self):
        fm = FM()
        S.apply_global(fm, S.normalise({"gamepad": False, "deadzone": 0.4, "keybinds": {"dash": [pygame.K_q, None]}}))
        self.assertFalse(fm.gamepad.enabled); self.assertEqual(fm.gamepad.deadzone, 0.4)
        self.assertEqual(KEYS.map["dash"][0], pygame.K_q)

    def test_play_state_applies_saved_settings_on_entry(self):
        from game.states.play_state import PlayState
        from game.state_manager import StateManager
        S.save(S.normalise({"volume": 0.25, "bloom": "LOW"}))
        ps = PlayState(StateManager(pygame.display.get_surface())); ps.on_enter()
        self.assertAlmostEqual(ps._game.audio.volume, 0.25); self.assertEqual(ps._game.renderer.bloom_strength, 0.30)


class SettingsScreen(TempData, unittest.TestCase):
    def state(self):
        from game.states.settings_state import SettingsState
        fm = FM(); st = SettingsState(fm); st.on_enter(); return st, fm

    def test_slider_toggle_and_choice_edit_and_persist_instantly(self):
        st, _ = self.state()
        st.handle_events([key(pygame.K_LEFT)] * 3)                               # VOLUME 0.55 -> 0.40
        self.assertAlmostEqual(S.load()["volume"], 0.40, places=2)
        st.handle_events([key(pygame.K_DOWN), key(pygame.K_RETURN)])             # MUSIC off
        self.assertFalse(S.load()["music"])
        st.handle_events([key(pygame.K_DOWN)] * 3 + [key(pygame.K_RIGHT)])       # BLOOM MEDIUM -> HIGH
        self.assertEqual(S.load()["bloom"], "HIGH")

    def test_sliders_clamp_at_the_ends(self):
        st, _ = self.state()
        st.handle_events([key(pygame.K_RIGHT)] * 40); self.assertEqual(S.load()["volume"], 1.0)
        st.handle_events([key(pygame.K_LEFT)] * 60);  self.assertEqual(S.load()["volume"], 0.0)

    def test_gamepad_toggle_reaches_the_live_pad(self):
        st, fm = self.state()
        st._sel = next(i for i, r in enumerate(st._rows) if r["key"] == "gamepad")
        st.handle_events([key(pygame.K_RETURN)]); self.assertFalse(fm.gamepad.enabled)

    def test_fullscreen_controls_and_back_rows(self):
        st, fm = self.state()
        st._sel = next(i for i, r in enumerate(st._rows) if r["key"] == "fullscreen")
        st.handle_events([key(pygame.K_RETURN)]); self.assertEqual(fm.fs_toggled, 1)
        st._sel = next(i for i, r in enumerate(st._rows) if r["key"] == "controls")
        st.handle_events([key(pygame.K_RETURN)]); self.assertEqual(type(fm.pushed).__name__, "ControlsState")
        st._sel = len(st._rows) - 1; st.handle_events([key(pygame.K_RETURN)]); self.assertTrue(fm.popped)

    def test_mouse_drag_sets_a_slider_and_click_toggles(self):
        st, _ = self.state(); st.update(0.1); st.draw(pygame.Surface((1280, 720), pygame.SRCALPHA))
        r = st._rects[0]; bx = r.right - 250
        st.handle_events([pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(bx + 190, r.centery), button=1)])
        self.assertEqual(S.load()["volume"], 1.0)
        st.handle_events([pygame.event.Event(pygame.MOUSEMOTION, pos=(bx + 95, r.centery), rel=(0, 0), buttons=(1, 0, 0))])
        self.assertAlmostEqual(S.load()["volume"], 0.5, delta=0.06)
        st.handle_events([pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(0, 0), button=1)])
        r2 = st._rects[1]; st.handle_events([pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=r2.center, button=1)])
        self.assertFalse(S.load()["music"])

    def test_draws_and_escape_leaves(self):
        st, fm = self.state()
        for i in range(len(st._rows)):
            st._sel = i; st.update(0.1); st.draw(pygame.Surface((1280, 720), pygame.SRCALPHA))
        st.handle_events([key(pygame.K_ESCAPE)]); self.assertTrue(fm.popped)


class ControlsScreen(TempData, unittest.TestCase):
    def state(self):
        from game.states.controls_state import ControlsState
        fm = FM(); st = ControlsState(fm); st.on_enter(); return st, fm

    def test_rebind_flow_persists_and_takes_effect(self):
        st, _ = self.state()
        st.sel = ACTIONS.index("dash")
        st.handle_events([key(pygame.K_RETURN)]); self.assertTrue(st.wait)
        st.handle_events([key(pygame.K_q)])
        self.assertFalse(st.wait); self.assertEqual(KEYS.map["dash"][0], pygame.K_q)
        self.assertEqual(S.load()["keybinds"]["dash"][0], pygame.K_q)           # saved immediately
        self.assertIn("Q", st.msg)

    def test_secondary_slot_and_conflict_message(self):
        st, _ = self.state()
        st.sel = ACTIONS.index("hack"); st.handle_events([key(pygame.K_RIGHT)]); self.assertEqual(st.slot, 1)
        st.handle_events([key(pygame.K_RETURN), key(pygame.K_m)])                # M was MUTE's
        self.assertEqual(KEYS.map["hack"][1], pygame.K_m); self.assertIsNone(KEYS.map["mute"][0])
        self.assertIn("taken from MUTE", st.msg)

    def test_reserved_key_is_refused_and_capture_continues(self):
        st, _ = self.state(); st.sel = ACTIONS.index("dash")
        st.handle_events([key(pygame.K_RETURN), key(pygame.K_F3)])
        self.assertIn("reserved", st.msg); self.assertEqual(KEYS.map["dash"][0], pygame.K_LSHIFT)
        self.assertTrue(st.wait)

    def test_escape_cancels_capture_without_leaving_and_backspace_clears(self):
        st, fm = self.state(); st.sel = ACTIONS.index("up")
        st.handle_events([key(pygame.K_RETURN), key(pygame.K_ESCAPE)])
        self.assertFalse(st.wait); self.assertFalse(fm.popped); self.assertEqual(KEYS.map["up"][0], pygame.K_w)
        st.handle_events([key(pygame.K_RETURN), key(pygame.K_BACKSPACE)]); self.assertIsNone(KEYS.map["up"][0])

    def test_reset_row_restores_defaults(self):
        st, _ = self.state(); KEYS.rebind("dash", 0, pygame.K_q)
        st.sel = st.ROW_RESET; st.handle_events([key(pygame.K_RETURN)])
        self.assertEqual(KEYS.map["dash"][0], pygame.K_LSHIFT)
        self.assertEqual(S.load()["keybinds"]["dash"][0], pygame.K_LSHIFT)

    def test_navigation_wraps_and_back_row_leaves(self):
        st, fm = self.state()
        st.handle_events([key(pygame.K_UP)]); self.assertEqual(st.sel, st.ROW_BACK)
        st.handle_events([key(pygame.K_RETURN)]); self.assertTrue(fm.popped)

    def test_mouse_click_on_a_slot_starts_capture_and_screen_draws(self):
        st, _ = self.state(); st.update(0.1); st.draw(pygame.Surface((1280, 720), pygame.SRCALPHA))
        row, slots = st._rects[ACTIONS.index("hack")]
        st.handle_events([pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=slots[1].center, button=1)])
        self.assertTrue(st.wait); self.assertEqual((st.sel, st.slot), (ACTIONS.index("hack"), 1))
        st.draw(pygame.Surface((1280, 720), pygame.SRCALPHA))

    def test_saved_bindings_survive_a_restart(self):
        st, _ = self.state(); st.sel = ACTIONS.index("dash")
        st.handle_events([key(pygame.K_RETURN), key(pygame.K_q)])
        KEYS.reset()                                                            # simulate a fresh launch
        S.apply_global(FM(), S.load()); self.assertEqual(KEYS.map["dash"][0], pygame.K_q)


if __name__ == "__main__":
    unittest.main()
