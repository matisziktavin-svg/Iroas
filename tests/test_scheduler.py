import datetime as dt

import scheduler

# 2026-10-04 is a Sunday
SUN_EVENING = dt.datetime(2026, 10, 4, 19, 30)
SUN_AFTERNOON = dt.datetime(2026, 10, 4, 15, 0)
MON_EVENING = dt.datetime(2026, 10, 5, 19, 30)


def base_settings(**over):
    s = {"owner_telegram_id": 42, "onboarded": True, "ping_time": "19:00",
         "body_comp_day": "sunday",
         "features": {"daily_review": True, "hevy_progression": True,
                      "body_comp": True, "nudges": True}}
    s.update(over)
    return s


def test_not_before_ping_time():
    assert scheduler.due_checkin(SUN_AFTERNOON, base_settings(), {}, "", "") is None


def test_fires_after_ping_time_incl_catchup_on_late_start():
    due = scheduler.due_checkin(dt.datetime(2026, 10, 4, 23, 50), base_settings(), {}, "", "")
    assert due and due["daily"]


def test_only_once_per_day():
    state = {"last_checkin_date": "2026-10-04"}
    assert scheduler.due_checkin(SUN_EVENING, base_settings(), state, "", "") is None


def test_not_before_onboarding_or_pairing():
    assert scheduler.due_checkin(SUN_EVENING, base_settings(onboarded=False), {}, "", "") is None
    assert scheduler.due_checkin(SUN_EVENING, base_settings(owner_telegram_id=None), {}, "", "") is None


def test_daily_skipped_when_today_already_logged():
    log = "- **2026-10-04** — Legs — done\n- **2026-10-03** — Rest"
    s = base_settings(features={"daily_review": True, "body_comp": False, "nudges": False})
    assert scheduler.due_checkin(SUN_EVENING, s, {}, log, "") is None


def test_body_comp_on_its_day_when_stale():
    meas = "- **2026-09-20** — weight 200"
    due = scheduler.due_checkin(SUN_EVENING, base_settings(), {}, "", meas)
    assert due["body_comp"]


def test_body_comp_not_on_other_days():
    due = scheduler.due_checkin(MON_EVENING, base_settings(), {}, "", "")
    assert not due["body_comp"]


def test_body_comp_not_when_recent_reading():
    meas = "- **2026-10-01** — weight 200"
    assert not scheduler.due_checkin(SUN_EVENING, base_settings(), {}, "", meas)["body_comp"]


def test_body_comp_not_when_asked_recently():
    state = {"last_body_comp_ask_date": "2026-09-30"}
    assert not scheduler.due_checkin(SUN_EVENING, base_settings(), state, "", "")["body_comp"]


def test_body_comp_catches_up_after_missed_day():
    # asked 9 days ago, PC was off last Sunday-ish -> ask on a Monday
    state = {"last_body_comp_ask_date": "2026-09-26"}
    assert scheduler.due_checkin(MON_EVENING, base_settings(), state, "", "")["body_comp"]


def test_all_features_off_means_nothing():
    s = base_settings(features={k: False for k in ("daily_review", "hevy_progression", "body_comp", "nudges")})
    assert scheduler.due_checkin(SUN_EVENING, s, {}, "", "") is None


def test_nudges_only_prompt_allows_silence():
    prompt = scheduler.checkin_prompt({"daily": False, "body_comp": False, "nudges": True}, SUN_EVENING)
    assert scheduler.SILENT in prompt


def test_daily_prompt_has_no_silence_option():
    prompt = scheduler.checkin_prompt({"daily": True, "body_comp": False, "nudges": True}, SUN_EVENING)
    assert scheduler.SILENT not in prompt


def test_entry_dates_ignores_format_placeholder():
    text = "*Format:* `- **YYYY-MM-DD** — Type`\n- **2026-10-01** — Upper"
    assert scheduler.entry_dates(text) == [dt.date(2026, 10, 1)]


def test_bad_ping_time_falls_back():
    s = base_settings(ping_time="garbage")
    assert scheduler.due_checkin(dt.datetime(2026, 10, 4, 18, 0), s, {}, "", "") is None
    assert scheduler.due_checkin(SUN_EVENING, s, {}, "", "") is not None


def test_state_roundtrip(sandbox):
    assert scheduler.load_state() == {}
    scheduler.save_state({"a": 1})
    assert scheduler.load_state() == {"a": 1}
