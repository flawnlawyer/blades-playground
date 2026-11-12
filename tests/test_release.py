"""Release-readiness tests: save paths, packaging spec, icon, workflows, versions, docs."""
import os, re, sys, tempfile, unittest, zipfile
from pathlib import Path
from unittest import mock
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pygame
pygame.init()
pygame.display.set_mode((1280, 720))

from utils import paths


def read(rel): return (ROOT / rel).read_text(encoding="utf-8")


class SavePaths(unittest.TestCase):
    """A one-file build unpacks to a temp dir that is deleted on exit; saves must NOT live there."""

    def test_source_runs_keep_using_the_project_data_folder(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BLADES_DATA_DIR", None)
            with mock.patch.object(sys, "frozen", False, create=True):
                self.assertEqual(paths.user_data_dir(), paths.PROJECT_ROOT / "data")

    def test_env_override_wins_everywhere(self):
        with mock.patch.dict(os.environ, {"BLADES_DATA_DIR": "/somewhere/else"}):
            self.assertEqual(paths.user_data_dir(), Path("/somewhere/else"))
            with mock.patch.object(sys, "frozen", True, create=True):
                self.assertEqual(paths.user_data_dir(), Path("/somewhere/else"))

    def _frozen_dir(self, platform, **env):
        clean = {k: v for k, v in os.environ.items() if k not in ("BLADES_DATA_DIR", "APPDATA", "XDG_DATA_HOME")}
        clean.update(env)
        with mock.patch.dict(os.environ, clean, clear=True), \
             mock.patch.object(sys, "frozen", True, create=True), \
             mock.patch.object(sys, "platform", platform), \
             mock.patch.object(Path, "home", return_value=Path("/home/tester")):
            return paths.user_data_dir()

    def test_packaged_windows_uses_appdata(self):
        d = str(self._frozen_dir("win32", APPDATA="C:/Users/tester/AppData/Roaming"))
        self.assertIn("AppData", d); self.assertTrue(d.endswith("BladesPlayground"))

    def test_packaged_windows_falls_back_without_appdata(self):
        d = self._frozen_dir("win32")
        self.assertEqual(d, Path("/home/tester/AppData/Roaming/BladesPlayground"))

    def test_packaged_macos(self):
        self.assertEqual(self._frozen_dir("darwin"), Path("/home/tester/Library/Application Support/BladesPlayground"))

    def test_packaged_linux_honours_xdg_then_defaults(self):
        self.assertEqual(self._frozen_dir("linux", XDG_DATA_HOME="/xdg"), Path("/xdg/BladesPlayground"))
        self.assertEqual(self._frozen_dir("linux"), Path("/home/tester/.local/share/BladesPlayground"))

    def test_packaged_saves_never_land_inside_the_code_tree(self):
        for plat in ("win32", "darwin", "linux"):
            self.assertNotIn(str(paths.PROJECT_ROOT), str(self._frozen_dir(plat)))

    def test_nuitka_style_marker_counts_as_frozen(self):
        with mock.patch.object(sys, "frozen", False, create=True), \
             mock.patch.dict(paths.__dict__, {"__compiled__": object()}):
            self.assertTrue(paths.is_frozen())

    def test_resource_path_uses_the_pyinstaller_unpack_dir_when_present(self):
        with mock.patch.object(sys, "_MEIPASS", "/tmp/_MEI123", create=True):
            self.assertEqual(paths.resource_path("assets/logo.png"), Path("/tmp/_MEI123/assets/logo.png"))
        self.assertTrue(paths.resource_path("assets/logo.png").exists())          # from source

    def test_saving_creates_missing_parent_folders(self):
        from utils import data_manager as dm
        old = dm.DATA_DIR, dm.SAVE_FILE
        with tempfile.TemporaryDirectory() as tmp:
            dm.DATA_DIR = Path(tmp) / "a" / "b" / "c"; dm.SAVE_FILE = dm.DATA_DIR / "hs.json"
            try:
                dm.save_score("TST", 10, 1, 5)                                     # first launch: nothing exists yet
                self.assertEqual(dm.load_scores()[0]["score"], 10)
            finally:
                dm.DATA_DIR, dm.SAVE_FILE = old


class PackagingFiles(unittest.TestCase):
    def test_spec_bundles_assets_not_the_developers_scores_and_loads_lazy_imports(self):
        spec = read("BladesPlayground.spec")
        self.assertIn("('assets', 'assets')", spec); self.assertNotIn("('data'", spec)
        for mod in ("pygame._sdl2.controller", "pygame._sdl2.video"):
            self.assertIn(mod, spec)
        self.assertIn("BP_CONSOLE", spec)

    def test_spec_icon_is_optional_and_the_icon_file_exists_and_is_valid(self):
        self.assertIn("ICON.exists()", read("BladesPlayground.spec"))             # old spec crashed on a missing icon
        ico = ROOT / "assets" / "logo.ico"; self.assertTrue(ico.exists())
        from PIL import Image
        with Image.open(ico) as im:
            self.assertIn((256, 256), im.info.get("sizes", {(256, 256)}))

    def test_gitignore_is_sane(self):
        lines = [l.strip() for l in read(".gitignore").splitlines() if l.strip() and not l.startswith("#")]
        self.assertFalse([l for l in lines if '"' in l or "'" in l], "stray quote characters (the old file had them)")
        for must in ("__pycache__/", "dist/", "build/", "data/highscores.json"):
            self.assertIn(must, lines)

    def test_requirements_are_minimal(self):
        req = read("requirements.txt").lower()
        self.assertIn("pygame", req); self.assertIn("numpy", req)


class Versioning(unittest.TestCase):
    def test_version_is_semver_and_used_by_the_menu(self):
        from game import __version__
        self.assertRegex(__version__, r"^\d+\.\d+\.\d+$")
        self.assertNotIn('"v1.0.0"', read("game/states/menu_state.py"))
        self.assertIn("__version__", read("game/states/menu_state.py"))

    def test_docs_mention_the_current_version(self):
        from game import __version__
        self.assertIn(f"Version-{__version__}", read("README.md"))
        self.assertIn(__version__, read("RELEASE_NOTES.md").splitlines()[0])
        self.assertIn(__version__, read("CHANGELOG.md"))


class Workflows(unittest.TestCase):
    @staticmethod
    def load(name):
        import yaml
        d = yaml.safe_load(read(f".github/workflows/{name}"))
        d["_on"] = d.get("on", d.get(True))                                        # YAML parses bare `on` as True
        return d

    def test_test_workflow_covers_three_oses_and_runs_headless(self):
        d = self.load("tests.yml"); job = d["jobs"]["test"]
        self.assertEqual(set(d["_on"]), {"push", "pull_request"})
        self.assertEqual(set(job["strategy"]["matrix"]["os"]), {"ubuntu-latest", "windows-latest", "macos-latest"})
        self.assertEqual(job["env"]["SDL_VIDEODRIVER"], "dummy"); self.assertEqual(job["env"]["SDL_AUDIODRIVER"], "dummy")
        self.assertTrue(any("unittest discover" in s.get("run", "") for s in job["steps"]))

    def test_release_workflow_gates_builds_and_publishes(self):
        d = self.load("release.yml")
        self.assertEqual(d["_on"]["push"]["tags"], ["v*"]); self.assertEqual(d["permissions"]["contents"], "write")
        steps = d["jobs"]["build"]["steps"]; runs = [s.get("run", "") for s in steps]
        i_tag  = next(i for i, r in enumerate(runs) if "__version__" in r and "GITHUB_REF_NAME" in r)
        i_test = next(i for i, r in enumerate(runs) if "unittest discover" in r)
        i_build = next(i for i, r in enumerate(runs) if "pyinstaller" in r and "BladesPlayground.spec" in r)
        self.assertTrue(i_tag < i_test < i_build, "tag check -> tests -> build, in that order")
        self.assertTrue(any("package_release.py" in r for r in runs))
        self.assertEqual(set(d["jobs"]["build"]["strategy"]["matrix"]["os"]), {"windows-latest", "macos-latest", "ubuntu-latest"})
        pub = d["jobs"]["publish"]; self.assertEqual(pub["needs"], "build")
        rel = next(s for s in pub["steps"] if "action-gh-release" in s.get("uses", ""))
        self.assertTrue((ROOT / rel["with"]["body_path"]).exists())

    def test_every_action_is_version_pinned(self):
        for name in ("tests.yml", "release.yml"):
            for m in re.finditer(r"uses:\s*(\S+)", read(f".github/workflows/{name}")):
                self.assertRegex(m.group(1), r"@v\d+", f"{name}: {m.group(1)} must be pinned")


class PackageScript(unittest.TestCase):
    def _fake_dist(self, tmp, name):
        d = Path(tmp) / "dist"; d.mkdir(); (d / name).write_bytes(b"\x7fELF fake binary"); return d

    def test_zip_contains_binary_with_exec_bit_and_docs(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import package_release as pr
        with tempfile.TemporaryDirectory() as tmp:
            d = self._fake_dist(tmp, "BladesPlayground")
            out = pr.build_zip(d)
            self.assertRegex(out.name, r"^BladesPlayground-\d+\.\d+\.\d+-(windows|macos|linux)\.zip$")
            with zipfile.ZipFile(out) as z:
                names = z.namelist()
                for need in ("BladesPlayground", "README.md", "LICENSE", "CONSOLE.md", "CHANGELOG.md"):
                    self.assertIn(need, names)
                self.assertEqual((z.getinfo("BladesPlayground").external_attr >> 16) & 0o777, 0o755)
                self.assertEqual(z.read("BladesPlayground"), b"\x7fELF fake binary")

    def test_windows_exe_name_is_found_and_missing_build_is_a_clear_error(self):
        import package_release as pr
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIn("BladesPlayground.exe", zipfile.ZipFile(pr.build_zip(self._fake_dist(tmp, "BladesPlayground.exe"))).namelist())
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "dist").mkdir()
            with self.assertRaises(SystemExit): pr.build_zip(Path(tmp) / "dist")


class DocsStayInSync(unittest.TestCase):
    def test_console_md_matches_the_command_registry(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import gen_docs
        self.assertEqual(read("CONSOLE.md"), gen_docs.render(), "run: python tools/gen_docs.py")

    def test_about_command_reports_version_paths_and_writable_saves(self):
        from game import __version__
        from game.console import Console
        class M:
            active_game = None
            def quit(self): pass
        c = Console(M()); c.execute("about")
        text = " ".join(t for t, _ in c.lines)
        self.assertIn(__version__, text); self.assertIn("running from source", text)
        self.assertIn("found", text); self.assertIn("writable", text); self.assertNotIn("MISSING", text)


if __name__ == "__main__":
    unittest.main()
