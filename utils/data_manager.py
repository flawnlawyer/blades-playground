"""
data_manager.py — Persistent save/load for high scores and settings.
Uses a local JSON file. Auto-creates on first run.
"""

import json
from pathlib import Path

DATA_DIR  = Path(__file__).parent.parent / "data"
SAVE_FILE = DATA_DIR / "highscores.json"

DEFAULT_DATA: dict = {
    "scores": [],
    "settings": {
        "volume": 0.55,
        "muted": False,
    },
}


def _ensure() -> dict:
    DATA_DIR.mkdir(exist_ok=True)
    if not SAVE_FILE.exists():
        _write(DEFAULT_DATA)
    try:
        with open(SAVE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return dict(DEFAULT_DATA)


def _write(data: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with open(SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ── Scores ────────────────────────────────────────────────────────────────────

def load_scores() -> list:
    return _ensure().get("scores", [])


def save_score(name: str, score: int, wave: int, time: float) -> list:
    data = _ensure()
    entry = {
        "name":  name[:24].strip() or "???",
        "score": score,
        "wave":  wave,
        "time":  int(time),
    }
    scores = data.get("scores", [])
    scores.append(entry)
    scores.sort(key=lambda x: x["score"], reverse=True)
    data["scores"] = scores[:10]
    _write(data)
    return data["scores"]


def qualifies_for_leaderboard(score: int) -> bool:
    scores = load_scores()
    if len(scores) < 10:
        return True
    return score > scores[-1]["score"]


# ── Settings ──────────────────────────────────────────────────────────────────

def load_settings() -> dict:
    return _ensure().get("settings", dict(DEFAULT_DATA["settings"]))


def save_settings(settings: dict) -> None:
    data = _ensure()
    data["settings"] = settings
    _write(data)
