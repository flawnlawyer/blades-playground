# Releasing

## One-time setup
1. Untrack local saves so your personal scores never ship: `git rm --cached data/highscores.json` (it is already in `.gitignore`).
2. Push this repo to GitHub with the `.github/workflows/` folder. Check the **Actions** tab shows `tests` running green on Windows, macOS and Linux.

## Each release
1. Bump `__version__` in `game/__init__.py` and the badge in `README.md`; add a section to `CHANGELOG.md`; update the first line of `RELEASE_NOTES.md`.
2. `git push origin main --tags` (the `Versioning` tests fail if the docs and version disagree).
3. Commit, then tag and push:
   ```bash
   git tag v3.0.0
   git push origin main --tags
   ```
4. The **release** workflow checks the tag matches `__version__`, runs the tests, builds binaries on Windows / macOS / Linux with PyInstaller, and publishes a GitHub Release with the zips and `RELEASE_NOTES.md`.

## Building locally
```bash
pip install pyinstaller
pyinstaller --noconfirm BladesPlayground.spec        # -> dist/BladesPlayground[.exe]
python tools/package_release.py                      # -> dist/BladesPlayground-<version>-<os>.zip
BP_CONSOLE=1 pyinstaller --noconfirm BladesPlayground.spec   # console build: smoke-test with piped stdin
printf 'about\nquit\n' | ./dist/BladesPlayground --terminal
```

## What has and hasn't been verified
* The Linux build was built and run headless (version, bundled logo, per-user save folder, clean exit).
* The Windows and macOS builds and the GitHub workflows themselves can only be proven by running them on GitHub — check the first run.
* Builds are unsigned. Code-signing needs your own certificates (Windows) / Apple Developer account (macOS).
