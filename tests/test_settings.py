import json

import pytest

import settings


def test_defaults_when_missing(sandbox):
    s = settings.load()
    assert s["onboarded"] is False
    assert all(s["features"].values())
    assert s["ping_time"] == "19:00"


def test_set_feature_roundtrip(sandbox):
    settings.set_value("features.body_comp", "off")
    s = settings.load()
    assert s["features"]["body_comp"] is False
    assert s["features"]["daily_review"] is True  # others untouched


def test_set_time_normalizes(sandbox):
    settings.set_value("ping_time", "7:05")
    assert settings.load()["ping_time"] == "07:05"


@pytest.mark.parametrize("key,val", [
    ("ping_time", "25:00"), ("ping_time", "7pm"), ("units", "stone"),
    ("body_comp_day", "funday"), ("features.flying", "true"),
    ("features.nudges", "maybe"), ("owner_telegram_id", "123"),
])
def test_rejects_bad_values(sandbox, key, val):
    with pytest.raises(ValueError):
        settings.set_value(key, val)


def test_broken_file_falls_back_and_backs_up(sandbox):
    (sandbox / "settings.json").write_text("{not json", encoding="utf-8")
    s = settings.load()
    assert s["onboarded"] is False
    assert (sandbox / "settings.broken.json").exists()


def test_partial_file_merges_with_defaults(sandbox):
    (sandbox / "settings.json").write_text(json.dumps({"features": {"nudges": False}}), encoding="utf-8")
    s = settings.load()
    assert s["features"]["nudges"] is False and s["features"]["daily_review"] is True
    assert s["units"] == "lb"


def test_cli(sandbox, capsys):
    assert settings._main(["set", "units", "kg"]) == 0
    assert settings.load()["units"] == "kg"
    assert settings._main(["set", "units", "bogus"]) == 1
    assert "ERROR" in capsys.readouterr().out
