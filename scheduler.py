"""Decides when Iroas should reach out on its own.

Once a day, at or after the evening `ping_time`, Iroas runs one "check-in":
  - daily_review: "how did training go?" — skipped if today is already logged
  - body_comp:    the weekly weigh-in ask, on `body_comp_day` (or caught up
                  later if the PC was off that day)
  - nudges:       Iroas scans the log for patterns worth flagging; stays silent
                  when nothing is notable

If the PC was off at ping time, the check-in fires as soon as the bot starts
(same day). A missed day is never "made up" twice — the next evening's check-in
catches up from the log instead.

Everything here is pure (dates/strings in, decisions out) so it's unit-tested.
"""
import datetime as dt
import json
import logging
import re
from pathlib import Path

import config

logger = logging.getLogger(__name__)

_ENTRY_DATE_RE = re.compile(r"\*\*(\d{4}-\d{2}-\d{2})\*\*")


# --- state.json --------------------------------------------------------------

def load_state(path: Path | None = None) -> dict:
    path = path or config.STATE_PATH
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(state: dict, path: Path | None = None) -> None:
    path = path or config.STATE_PATH
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


# --- parsing -----------------------------------------------------------------

def entry_dates(text: str) -> list[dt.date]:
    """All `**YYYY-MM-DD**` dates in a log/measurements file."""
    out = []
    for m in _ENTRY_DATE_RE.finditer(text or ""):
        try:
            out.append(dt.date.fromisoformat(m.group(1)))
        except ValueError:
            pass
    return out


def newest_entry(text: str) -> dt.date | None:
    dates = entry_dates(text)
    return max(dates) if dates else None


def _parse_hhmm(value: str) -> dt.time:
    try:
        h, m = value.split(":")
        return dt.time(int(h), int(m))
    except (ValueError, AttributeError):
        return dt.time(19, 0)


def _days_since(iso: str | None, today: dt.date) -> int | None:
    if not iso:
        return None
    try:
        return (today - dt.date.fromisoformat(iso)).days
    except ValueError:
        return None


# --- the decision ------------------------------------------------------------

def due_checkin(now: dt.datetime, settings: dict, state: dict,
                log_text: str, measurements_text: str) -> dict | None:
    """What (if anything) tonight's check-in should cover.

    Returns None when nothing is due yet, else a dict of booleans
    {daily, body_comp, nudges}. The caller records `last_checkin_date` either
    way once it has acted, so this fires at most once per day."""
    if not settings.get("owner_telegram_id") or not settings.get("onboarded"):
        return None
    today = now.date()
    if state.get("last_checkin_date") == today.isoformat():
        return None
    if now.time() < _parse_hhmm(settings.get("ping_time", "19:00")):
        return None

    features = settings.get("features") or {}

    daily = bool(features.get("daily_review")) and today not in entry_dates(log_text)

    body_comp = False
    if features.get("body_comp"):
        newest = newest_entry(measurements_text)
        stale = newest is None or (today - newest).days >= 7
        since_ask = _days_since(state.get("last_body_comp_ask_date"), today)
        asked_recently = since_ask is not None and since_ask < 7
        is_the_day = now.strftime("%A").lower() == settings.get("body_comp_day", "sunday")
        overdue = since_ask is not None and since_ask >= 8  # PC was off on the day
        body_comp = stale and not asked_recently and (is_the_day or overdue)

    nudges = bool(features.get("nudges"))

    if not (daily or body_comp or nudges):
        return None
    return {"daily": daily, "body_comp": body_comp, "nudges": nudges}


def checkin_prompt(due: dict, now: dt.datetime) -> str:
    """The instruction Iroas gets when the scheduler wakes it up."""
    parts = [f"[Scheduled evening check-in — {now:%A %Y-%m-%d %H:%M}. "
             "This is an automatic trigger, not a message from them. "
             "Write ONE short Telegram message to send them now.]"]
    if due["daily"]:
        parts.append("- Ask how today's training went (or whether it was a rest day). "
                     "If earlier days since the last log.md entry are missing, "
                     "mention you'll catch those up too. Don't pull Hevy yet — wait for their answer.")
    if due["body_comp"]:
        parts.append("- It's weigh-in week: ask for their latest scale numbers "
                     "(weight, body fat %, muscle %). Just ask; log them when they reply.")
    if due["nudges"]:
        parts.append("- Scan log.md (and Hevy if useful) for a pattern worth flagging "
                     "(3+ rest days in 7, a lift stalled 3 sessions, a skipped muscle group). "
                     "Include at most one nudge, and only if it's genuinely notable.")
    if not (due["daily"] or due["body_comp"]):
        parts.append(f"If there is nothing notable to nudge about, reply with exactly {SILENT} "
                     "and nothing else — no message will be sent.")
    return "\n".join(parts)


SILENT = "[[SILENT]]"
