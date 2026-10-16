"""
daily.py — Daily-run seeding and share codes.

The seed is derived from the UTC date, so everyone on the same day gets the same
arena layout, wave spawn positions and perk offers.  (Enemy AI jitter is not
seeded, so runs are comparable but not frame-identical.)

There is no server: a "share code" is a self-describing, checksummed string you
can paste to a friend, e.g.   BP-20261014-5200-7-3FA9   (date-score-wave-check).
The checksum catches typos and casual edits; because the secret ships with the
game it is NOT cheat-proof — real anti-cheat needs a server.
"""
from __future__ import annotations
import datetime
import hashlib

_SALT = "blades-playground-daily-v1"


def today() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d")


def seed_for(date: str) -> int:
    return int(hashlib.sha256(f"{_SALT}:{date}".encode()).hexdigest()[:8], 16)


def _check(body: str) -> str:
    return hashlib.sha256(f"{_SALT}|{body}".encode()).hexdigest()[:4].upper()


def share_code(date: str, score: int, wave: int) -> str:
    body = f"{date}-{int(score)}-{int(wave)}"
    return f"BP-{body}-{_check(body)}"


def parse_code(code: str) -> dict | None:
    """Return {date, score, wave} if *code* is well-formed with a valid checksum."""
    try:
        tag, date, score, wave, chk = code.strip().upper().split("-")
        if tag != "BP" or len(date) != 8 or not date.isdigit():
            return None
        body = f"{date}-{int(score)}-{int(wave)}"
        if chk != _check(body):
            return None
        return {"date": date, "score": int(score), "wave": int(wave)}
    except (ValueError, AttributeError):
        return None
