import json

import pytest

import hevy


class FakeClient(hevy.HevyClient):
    """HevyClient with the network seam replaced by canned responses."""

    def __init__(self, responses):
        super().__init__(api_key="test-key")
        self.responses = responses
        self.calls = []

    def _request(self, path, params=None, *, method="GET", json_body=None):
        self.calls.append((method, path, params, json_body))
        r = self.responses.get((method, path))
        if callable(r):
            return r(params)
        if r is None:
            raise hevy.HevyError(f"unexpected {method} {path}")
        return r


WORKOUT = {
    "title": "Upper A", "start_time": "2026-10-01T18:00:00Z",
    "exercises": [
        {"title": "Bench Press (Barbell)", "sets": [
            {"type": "warmup", "weight_kg": 40, "reps": 10},
            {"type": "normal", "weight_kg": 61.23497, "reps": 8, "rpe": 8},
        ]},
        {"title": "Treadmill", "sets": [{"duration_seconds": 600, "distance_meters": 1500}]},
    ],
}


def test_requires_key(monkeypatch):
    monkeypatch.delenv("HEVY_API_KEY", raising=False)
    with pytest.raises(hevy.HevyNotConfigured):
        hevy.HevyClient()


def test_summary_and_detail():
    assert hevy.summarize_workout(WORKOUT) == "2026-10-01 — Upper A — 2 exercises, 3 sets"
    d = hevy.format_workout_detail(WORKOUT)
    assert "61.2kg/135lb × 8 @RPE8" in d
    assert "(warmup)" in d
    assert "1500m 600s" in d


def test_recent_workouts_pages_past_ten():
    pages = {1: {"page_count": 2, "workouts": [{"id": i} for i in range(10)]},
             2: {"page_count": 2, "workouts": [{"id": i} for i in range(10, 20)]}}
    c = FakeClient({("GET", "/workouts"): lambda p: pages[p["page"]]})
    got = c.recent_workouts(limit=13)
    assert [w["id"] for w in got] == list(range(13))
    assert all(call[2]["pageSize"] == 10 for call in c.calls)


def test_resolve_template_exact_or_raises_with_hint():
    c = FakeClient({("GET", "/exercise_templates"): {"page_count": 1, "exercise_templates": [
        {"id": "AAA", "title": "Bench Press (Barbell)"},
        {"id": "BBB", "title": "Bench Press (Dumbbell)"}]}})
    assert c.resolve_template("bench press (barbell)") == "AAA"
    with pytest.raises(hevy.HevyError, match="Did you mean"):
        c.resolve_template("Bench Press")


def test_build_routine_body_keeps_only_known_fields():
    c = FakeClient({("GET", "/exercise_templates"): {"page_count": 1, "exercise_templates": [
        {"id": "AAA", "title": "Squat (Barbell)"}]}})
    body = hevy.build_routine_body(c, {"notes": "n", "exercises": [
        {"name": "Squat (Barbell)", "rest_seconds": 120, "sets": [
            {"weight_kg": 80, "reps": 8, "rep_range": {"start": 6, "end": 10}, "junk": 1}]}]},
        title="Legs")
    assert body == {"title": "Legs", "notes": "n", "exercises": [
        {"exercise_template_id": "AAA", "rest_seconds": 120, "sets": [
            {"type": "normal", "weight_kg": 80, "reps": 8, "rep_range": {"start": 6, "end": 10}}]}]}


def test_get_routine_unwraps():
    c = FakeClient({("GET", "/routines/r1"): {"routine": {"id": "r1", "title": "Legs"}}})
    assert c.get_routine("r1")["title"] == "Legs"


def test_block_never_raises(monkeypatch):
    monkeypatch.setenv("HEVY_API_KEY", "x")

    def boom(self, *a, **k):
        raise hevy.HevyError("down")
    monkeypatch.setattr(hevy.HevyClient, "_request", boom)
    assert "could not be reached" in hevy.recent_workouts_block()


def test_block_empty_without_key(monkeypatch):
    monkeypatch.delenv("HEVY_API_KEY", raising=False)
    assert hevy.recent_workouts_block() == ""


def test_http_401_explains(monkeypatch):
    import io
    import urllib.error

    def fake_urlopen(req, timeout=None):
        assert req.headers["Api-key"] == "k"
        raise urllib.error.HTTPError(req.full_url, 401, "no", {}, io.BytesIO(b"bad key"))
    monkeypatch.setattr(hevy.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(hevy.HevyError, match="Hevy Pro"):
        hevy.HevyClient(api_key="k").workout_count()


def _cli_client(monkeypatch, responses):
    monkeypatch.setenv("HEVY_API_KEY", "x")
    fake = FakeClient(responses)
    monkeypatch.setattr(hevy, "HevyClient", lambda *a, **k: fake)
    return fake


TEMPLATES = {("GET", "/exercise_templates"): {"page_count": 1, "exercise_templates": [
    {"id": "AAA", "title": "Squat (Barbell)"}]}}


def _spec(tmp_path, data):
    p = tmp_path / "s.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_cli_create_dry_run_does_not_post(monkeypatch, tmp_path, capsys):
    fake = _cli_client(monkeypatch, dict(TEMPLATES))
    spec = _spec(tmp_path, {"title": "Legs", "exercises": [{"name": "Squat (Barbell)", "sets": [{"reps": 5}]}]})
    assert hevy._main(["create", str(spec), "--dry-run"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["routine"]["folder_id"] is None and out["routine"]["title"] == "Legs"
    assert not any(c[0] == "POST" for c in fake.calls)
    assert spec.exists()


def test_cli_create_posts_and_cleans_spec(monkeypatch, tmp_path):
    fake = _cli_client(monkeypatch, {**TEMPLATES, ("POST", "/routines"): {"routine": [{"id": "new"}]}})
    spec = _spec(tmp_path, {"title": "Legs", "exercises": [{"name": "Squat (Barbell)", "sets": [{"reps": 5}]}]})
    assert hevy._main(["create", str(spec)]) == 0
    post = [c for c in fake.calls if c[0] == "POST"][0]
    assert post[3]["routine"]["exercises"][0]["exercise_template_id"] == "AAA"
    assert not spec.exists()


def test_cli_create_needs_title(monkeypatch, tmp_path):
    _cli_client(monkeypatch, dict(TEMPLATES))
    assert hevy._main(["create", str(_spec(tmp_path, {"exercises": []}))]) == 1


def test_cli_push_by_title_keeps_title(monkeypatch, tmp_path):
    fake = _cli_client(monkeypatch, {
        **TEMPLATES,
        ("GET", "/routines"): {"page_count": 1, "routines": [{"id": "r9", "title": "Legs Day"}]},
        ("PUT", "/routines/r9"): {},
    })
    spec = _spec(tmp_path, {"exercises": [{"name": "Squat (Barbell)", "sets": [{"reps": 6}]}]})
    assert hevy._main(["push", str(spec), "--title", "legs day"]) == 0
    put = [c for c in fake.calls if c[0] == "PUT"][0]
    assert put[3]["routine"]["title"] == "Legs Day"


def test_cli_push_unknown_title(monkeypatch, tmp_path):
    _cli_client(monkeypatch, {("GET", "/routines"): {"page_count": 1, "routines": []}})
    assert hevy._main(["push", str(_spec(tmp_path, {})), "--title", "Nope"]) == 1
