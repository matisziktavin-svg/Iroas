import datetime as dt
import os

import agent
import config
import settings


def test_ensure_data_files_copies_templates_without_overwriting(sandbox, monkeypatch):
    monkeypatch.setattr(config, "ROOT", sandbox)
    agent.ensure_data_files()
    for name in config.DATA_FILES:
        assert (sandbox / "data" / name).exists()
    (sandbox / "data" / "log.md").write_text("mine", encoding="utf-8")
    agent.ensure_data_files()
    assert (sandbox / "data" / "log.md").read_text(encoding="utf-8") == "mine"


def test_system_prompt_contents(sandbox, monkeypatch):
    monkeypatch.setattr(config, "ROOT", sandbox)
    agent.ensure_data_files()
    (sandbox / "data" / "profile.md").write_text("Goal: deadlift 400", encoding="utf-8")
    p = agent.build_system_prompt(dt.datetime(2026, 10, 4, 19, 0), include_hevy=False)
    assert "You are Iroas" in p
    assert "Goal: deadlift 400" in p
    assert "NOT DONE" in p
    assert "{PYTHON}" not in p and "{ROOT}" not in p
    assert "Sunday, October 04, 2026" in p
    settings.set_value("onboarded", "true")
    assert "COMPLETE" in agent.build_system_prompt(include_hevy=False)


def test_long_log_is_trimmed(sandbox, monkeypatch):
    monkeypatch.setattr(config, "ROOT", sandbox)
    agent.ensure_data_files()
    lines = [f"- **2026-01-{(i % 28) + 1:02d}** — Day {i}" for i in range(500)]
    (sandbox / "data" / "log.md").write_text("\n".join(lines), encoding="utf-8")
    p = agent.build_system_prompt(include_hevy=False)
    assert "Day 0\n" in p and "Day 499" not in p and "older entries omitted" in p


def test_session_only_resumed_same_day():
    state = {"session_id": "abc", "session_date": "2026-10-04"}
    assert agent._session_for_today(state, "2026-10-04") == "abc"
    assert agent._session_for_today(state, "2026-10-05") is None


def test_auth_error_detection():
    assert agent._looks_like_auth_error("Failed to authenticate. API Error: 401 authentication_error")
    assert agent._looks_like_auth_error("Invalid API key - Please run /login")
    assert not agent._looks_like_auth_error("Hevy API 401 for GET /workouts")


def test_no_api_key_in_env():
    assert "ANTHROPIC_API_KEY" not in os.environ


def test_api_errors_map_to_friendly_messages():
    e = agent._unavailable("authentication_failed", "401 OAuth access token is invalid.")
    assert isinstance(e, agent.AuthError) and "refresh_claude_login.bat" in e.user_message
    assert "usage limit" in agent._unavailable("rate_limit", "").user_message
    assert "billing" in agent._unavailable("billing_error", "").user_message
    other = agent._unavailable("server_error", "boom")
    assert not isinstance(other, agent.AuthError) and "few minutes" in other.user_message
