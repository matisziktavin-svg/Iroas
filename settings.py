"""settings.json — the user-editable switches for Iroas.

Edit the file by hand, ask Iroas in chat ("turn off the weekly weigh-in"), or
use the CLI (this is what Iroas itself runs):

    python settings.py show
    python settings.py set features.body_comp false
    python settings.py set ping_time 18:30

The scheduler re-reads this file every minute, so changes apply without a
restart.
"""
import copy
import json
import logging
import re
import sys
from pathlib import Path

import config

logger = logging.getLogger(__name__)

FEATURES = {
    "daily_review": "Evening message asking how training went; reviews it and logs the day.",
    "hevy_progression": "Pushes new rep/weight targets into your Hevy routines when you earn them.",
    "body_comp": "Weekly ask for your scale numbers (weight, body fat %, muscle %) to track the trend.",
    "nudges": "Heads-up when a pattern looks off (e.g. lots of rest days, a lift stalling).",
}

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

DEFAULTS = {
    "owner_telegram_id": None,   # set when the owner sends /start <pairing code>
    "owner_name": "",
    "onboarded": False,
    "features": {name: True for name in FEATURES},
    "ping_time": "19:00",        # 24h local time for the evening check-in
    "body_comp_day": "sunday",   # weekday the weekly weigh-in ask rides along
    "units": "lb",               # "lb" or "kg" — how Iroas talks about weight
}

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def _merge(defaults: dict, loaded: dict) -> dict:
    out = copy.deepcopy(defaults)
    for key, val in loaded.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = {**out[key], **val}
        else:
            out[key] = val
    return out


def load(path: Path | None = None) -> dict:
    """Current settings merged over DEFAULTS. A missing or broken file never
    crashes the bot: a broken one is backed up and defaults are used."""
    path = path or config.SETTINGS_PATH
    if not path.exists():
        return copy.deepcopy(DEFAULTS)
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("settings.json must hold a JSON object")
    except (ValueError, OSError) as e:
        backup = path.with_suffix(".broken.json")
        logger.error("settings.json unreadable (%s); backed up to %s, using defaults", e, backup.name)
        try:
            backup.write_text(path.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
        except OSError:
            pass
        return copy.deepcopy(DEFAULTS)
    return _merge(DEFAULTS, loaded)


def save(settings: dict, path: Path | None = None) -> None:
    path = path or config.SETTINGS_PATH
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _parse_value(key: str, raw: str):
    """Validate + coerce a CLI value for `key`. Raises ValueError on bad input."""
    low = raw.strip().lower()
    if key.startswith("features.") or key == "onboarded":
        if low in ("true", "on", "yes", "1"):
            return True
        if low in ("false", "off", "no", "0"):
            return False
        raise ValueError(f"{key} must be true/false")
    if key == "ping_time":
        m = _TIME_RE.match(low)
        if not m:
            raise ValueError("ping_time must be HH:MM in 24h time, e.g. 19:00")
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    if key == "body_comp_day":
        if low not in WEEKDAYS:
            raise ValueError(f"body_comp_day must be one of {', '.join(WEEKDAYS)}")
        return low
    if key == "units":
        if low not in ("lb", "kg"):
            raise ValueError("units must be lb or kg")
        return low
    if key == "owner_name":
        return raw.strip()
    raise ValueError(f"unknown or read-only setting {key!r}")


def set_value(key: str, raw: str, path: Path | None = None) -> dict:
    """Set one setting (dotted key for features) and save. Returns new settings."""
    if key.startswith("features.") and key.split(".", 1)[1] not in FEATURES:
        raise ValueError(f"unknown feature {key.split('.', 1)[1]!r}; known: {', '.join(FEATURES)}")
    value = _parse_value(key, raw)
    s = load(path)
    if key.startswith("features."):
        s["features"][key.split(".", 1)[1]] = value
    else:
        s[key] = value
    save(s, path)
    return s


def describe(s: dict) -> str:
    """Human-readable settings summary (used by /settings and the agent prompt)."""
    lines = [f"Evening check-in time: {s['ping_time']}",
             f"Weekly weigh-in day: {s['body_comp_day'].title()}",
             f"Units: {s['units']}",
             "Features:"]
    for name, blurb in FEATURES.items():
        state = "ON " if s["features"].get(name) else "OFF"
        lines.append(f"  [{state}] {name} — {blurb}")
    return "\n".join(lines)


def _main(argv: list[str]) -> int:
    if not argv or argv[0] == "show":
        print(describe(load()))
        return 0
    if argv[0] == "set" and len(argv) == 3:
        try:
            s = set_value(argv[1], argv[2])
        except ValueError as e:
            print(f"ERROR: {e}")
            return 1
        print("Saved.\n" + describe(s))
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
