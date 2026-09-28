"""Thin client for the official Hevy API — Iroas's view of your real workouts.

API: base https://api.hevyapp.com/v1, auth via the `api-key` header. The key
comes from https://hevy.com/settings?developer and needs **Hevy Pro**.
Docs: https://api.hevyapp.com/docs/

stdlib-only (urllib). Iroas runs it through the CLI at the bottom:

    python hevy.py check                       # is the key valid? whose account?
    python hevy.py recent [--limit N] [--detail]
    python hevy.py routines
    python hevy.py get <routine_id>
    python hevy.py templates "<search>"
    python hevy.py push SPEC.json --title "Day A" [--dry-run]   # replace a routine
    python hevy.py create SPEC.json [--dry-run]                 # make a new routine

Response shapes:
    GET /v1/workouts?page=1&pageSize=10 -> {page, page_count, workouts: [Workout]}
    Workout : id, title, start_time, end_time, exercises: [Exercise]
    Exercise: index, title, notes, exercise_template_id, sets: [Set]
    Set     : index, type, weight_kg, reps, distance_meters, duration_seconds,
              rpe, custom_metric
"""
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

BASE_URL = "https://api.hevyapp.com/v1"
_USER_AGENT = "Iroas/1.0 (personal trainer bot)"
_TIMEOUT_S = 20
_RETRIES = 3
KG_PER_LB = 0.45359237


class HevyError(Exception):
    """Any Hevy API failure (HTTP error, bad JSON, transport)."""


class HevyNotConfigured(HevyError):
    """No API key available."""


def is_configured() -> bool:
    return bool(os.environ.get("HEVY_API_KEY"))


class HevyClient:
    """Minimal client over the Hevy public API. `_request` is the one network
    seam; tests mock it or patch `urllib.request.urlopen`."""

    def __init__(self, api_key: str | None = None, *, timeout: int = _TIMEOUT_S):
        self.api_key = api_key if api_key is not None else os.environ.get("HEVY_API_KEY")
        if not self.api_key:
            raise HevyNotConfigured(
                "No Hevy API key. Put HEVY_API_KEY in the .env file "
                "(get it at hevy.com/settings?developer — Hevy Pro required)."
            )
        self.timeout = timeout
        self._tmpl_index: dict[str, str] | None = None

    def _request(self, path: str, params: dict | None = None, *,
                 method: str = "GET", json_body: dict | None = None) -> dict:
        """{method} BASE_URL+path with the api-key header; returns parsed JSON.
        Transport errors on GET/PUT retry with backoff (both idempotent); POST
        is never retried so a create can't happen twice. HTTP errors raise
        HevyError immediately."""
        url = f"{BASE_URL}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        headers = {"api-key": self.api_key, "Accept": "application/json",
                   "User-Agent": _USER_AGENT}
        data = None
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        retriable = method in ("GET", "PUT")
        last: Exception | None = None
        for attempt in range(_RETRIES if retriable else 1):
            try:
                req = urllib.request.Request(url, data=data, headers=headers, method=method)
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read().decode("utf-8").strip()
                    return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as e:
                detail = ""
                try:
                    detail = e.read().decode("utf-8")[:300]
                except Exception:
                    pass
                if e.code == 401:
                    detail += " (the HEVY_API_KEY is wrong, or Hevy Pro has lapsed)"
                raise HevyError(f"Hevy API {e.code} for {method} {path}: {detail}") from e
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
                last = e
                time.sleep(0.5 * (attempt + 1))
        raise HevyError(f"Hevy API request failed for {method} {path}: {last}") from last

    # --- account / workouts ---------------------------------------------

    def user_info(self) -> dict:
        data = self._request("/user/info")
        return data.get("data", data) if isinstance(data, dict) else {}

    def workout_count(self) -> int:
        return int(self._request("/workouts/count").get("workout_count", 0))

    def recent_workouts(self, limit: int = 5) -> list[dict]:
        """The newest `limit` workouts. Hevy caps pageSize at 10, so page."""
        out: list[dict] = []
        page = 1
        while len(out) < limit:
            data = self._request("/workouts", {"page": page, "pageSize": 10})
            batch = data.get("workouts") or []
            out.extend(batch)
            if not batch or page >= int(data.get("page_count") or 1):
                break
            page += 1
        return out[:limit]

    # --- routines -------------------------------------------------------

    def all_routines(self, max_pages: int = 10) -> list[dict]:
        out: list[dict] = []
        for page in range(1, max_pages + 1):
            data = self._request("/routines", {"page": page, "pageSize": 10})
            batch = data.get("routines") or []
            out.extend(batch)
            if not batch or page >= int(data.get("page_count") or 1):
                break
        return out

    def get_routine(self, routine_id: str) -> dict:
        """GET /routines/{id} wraps the routine under `routine`; unwrap it."""
        data = self._request(f"/routines/{routine_id}")
        return data.get("routine", data) if isinstance(data, dict) else data

    def find_routine_by_title(self, title: str) -> dict | None:
        want = title.strip().lower()
        for r in self.all_routines():
            if (r.get("title") or "").strip().lower() == want:
                return r
        return None

    def update_routine(self, routine_id: str, routine: dict) -> dict:
        return self._request(f"/routines/{routine_id}", method="PUT",
                             json_body={"routine": routine})

    def create_routine(self, routine: dict) -> dict:
        return self._request("/routines", method="POST", json_body={"routine": routine})

    # --- exercise templates ---------------------------------------------

    def all_exercise_templates(self, max_pages: int = 30) -> list[dict]:
        out: list[dict] = []
        for page in range(1, max_pages + 1):
            data = self._request("/exercise_templates", {"page": page, "pageSize": 100})
            batch = data.get("exercise_templates") or []
            out.extend(batch)
            if not batch or page >= int(data.get("page_count") or 1):
                break
        return out

    def template_index(self) -> dict[str, str]:
        """Cached {title.lower(): id}."""
        if self._tmpl_index is None:
            self._tmpl_index = {
                (t.get("title") or "").strip().lower(): t["id"]
                for t in self.all_exercise_templates()
                if t.get("title") and t.get("id")
            }
        return self._tmpl_index

    def resolve_template(self, name: str) -> str:
        """Exact (case-insensitive) title -> template id. Never guesses: an
        unknown name raises HevyError listing close candidates."""
        idx = self.template_index()
        key = name.strip().lower()
        if key in idx:
            return idx[key]
        cands = [t for t in idx if key in t or t in key]
        hint = f" Did you mean: {', '.join(sorted(cands)[:8])}?" if cands else ""
        raise HevyError(f"No exercise template titled {name!r}.{hint}")


# --- formatting (pure) -------------------------------------------------------


def summarize_workout(workout: dict) -> str:
    """`DATE — Title — N exercises, M sets`."""
    start = (workout.get("start_time") or "").strip()
    date = start[:10] if len(start) >= 10 else (start or "?")
    title = (workout.get("title") or "Workout").strip()
    exercises = workout.get("exercises") or []
    n_ex = len(exercises)
    n_sets = sum(len(ex.get("sets") or []) for ex in exercises)
    return (f"{date} — {title} — {n_ex} exercise{'s' if n_ex != 1 else ''}, "
            f"{n_sets} set{'s' if n_sets != 1 else ''}")


def format_weight(kg) -> str:
    """Hevy stores kg; show both so neither unit needs mental math."""
    lb = kg / KG_PER_LB
    return f"{round(kg, 1):g}kg/{round(lb, 1):g}lb"


def format_set(s: dict) -> str:
    parts: list[str] = []
    w = s.get("weight_kg")
    w_str = format_weight(w) if isinstance(w, (int, float)) else None
    reps = s.get("reps")
    if w_str is not None and reps is not None:
        parts.append(f"{w_str} × {reps}")
    elif reps is not None:
        parts.append(f"{reps} reps")
    elif w_str is not None:
        parts.append(w_str)
    if s.get("distance_meters") is not None:
        parts.append(f"{s['distance_meters']}m")
    if s.get("duration_seconds") is not None:
        parts.append(f"{s['duration_seconds']}s")
    if not parts:
        parts.append("—")
    line = " ".join(parts)
    if s.get("type") and s["type"] != "normal":
        line += f" ({s['type']})"
    if s.get("rpe") is not None:
        line += f" @RPE{s['rpe']}"
    return line


def format_workout_detail(workout: dict) -> str:
    lines = [summarize_workout(workout)]
    for ex in workout.get("exercises") or []:
        title = (ex.get("title") or "Exercise").strip()
        sets = ex.get("sets") or []
        joined = ", ".join(format_set(s) for s in sets) if sets else "(no sets)"
        lines.append(f"  {title}: {joined}")
    return "\n".join(lines)


def recent_workouts_block(limit: int = 5, api_key: str | None = None) -> str:
    """Prompt block of recent workouts, or "" if Hevy is unreachable. Never
    raises — a Hevy outage must not stop Iroas from answering."""
    if api_key is None and not is_configured():
        return ""
    try:
        workouts = HevyClient(api_key=api_key).recent_workouts(limit=limit)
    except Exception as e:
        logger.warning("hevy: recent_workouts_block skipped (%s)", e)
        return "(Hevy could not be reached just now — run `hevy.py recent` to retry.)"
    if not workouts:
        return "(No workouts logged in Hevy yet.)"
    return "\n".join(f"- {summarize_workout(w)}" for w in workouts)


# --- routine authoring -------------------------------------------------------

_SET_FIELDS = ("weight_kg", "reps", "distance_meters", "duration_seconds",
               "custom_metric", "rep_range")


def build_exercises(client: HevyClient, spec_exercises: list[dict]) -> list[dict]:
    """Friendly spec -> Hevy routine exercise array. Each exercise has `name`
    (exact Hevy title) or `exercise_template_id`, optional rest_seconds /
    notes / superset_id, and sets of {type?, weight_kg?, reps?, rep_range?...}."""
    out: list[dict] = []
    for ex in spec_exercises:
        tid = ex.get("exercise_template_id") or client.resolve_template(ex["name"])
        sets = []
        for s in ex.get("sets") or []:
            st = {"type": s.get("type", "normal")}
            for f in _SET_FIELDS:
                if s.get(f) is not None:
                    st[f] = s[f]
            sets.append(st)
        e = {"exercise_template_id": tid, "sets": sets}
        for f in ("rest_seconds", "superset_id"):
            if ex.get(f) is not None:
                e[f] = ex[f]
        if ex.get("notes"):
            e["notes"] = ex["notes"]
        out.append(e)
    return out


def build_routine_body(client: HevyClient, spec: dict, *, title: str | None) -> dict:
    routine = {"title": title, "exercises": build_exercises(client, spec.get("exercises") or [])}
    if spec.get("notes") is not None:
        routine["notes"] = spec["notes"]
    return routine


# --- CLI ---------------------------------------------------------------------


def _main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    try:  # load .env when run as a script
        import config  # noqa: F401  (config loads .env on import)
    except Exception:
        pass
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252

    ap = argparse.ArgumentParser(prog="hevy.py", description="Hevy tools for Iroas.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="verify the API key and show the account name")
    rc = sub.add_parser("recent", help="recent LOGGED workouts, newest first")
    rc.add_argument("--limit", type=int, default=5)
    rc.add_argument("--detail", action="store_true", help="per-set weight × reps")
    sub.add_parser("routines", help="list routines (id + title)")
    g = sub.add_parser("get", help="dump one routine as JSON")
    g.add_argument("routine_id")
    t = sub.add_parser("templates", help="search exercise titles")
    t.add_argument("query")
    p = sub.add_parser("push", help="REPLACE an existing routine with a JSON spec")
    p.add_argument("spec")
    who = p.add_mutually_exclusive_group(required=True)
    who.add_argument("--id", dest="routine_id")
    who.add_argument("--title", dest="routine_title")
    p.add_argument("--dry-run", action="store_true")
    c = sub.add_parser("create", help="CREATE a new routine from a JSON spec (needs a title)")
    c.add_argument("spec")
    c.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if not is_configured():
        print("HEVY_API_KEY is not set in .env — cannot reach Hevy.")
        return 2
    client = HevyClient()

    try:
        if args.cmd == "check":
            info = client.user_info()
            print(f"OK — connected to Hevy account {info.get('name') or info.get('id') or '?'}"
                  f" ({client.workout_count()} workouts logged).")
        elif args.cmd == "recent":
            workouts = client.recent_workouts(limit=args.limit)
            if not workouts:
                print("No logged workouts found.")
            for w in workouts:
                print(format_workout_detail(w) if args.detail else summarize_workout(w))
        elif args.cmd == "routines":
            routines = client.all_routines()
            if not routines:
                print("No routines yet.")
            for r in routines:
                print(f"{r.get('id')}  {r.get('title')!r}  ({len(r.get('exercises') or [])} exercises)")
        elif args.cmd == "get":
            print(json.dumps(client.get_routine(args.routine_id), indent=2))
        elif args.cmd == "templates":
            q = args.query.strip().lower()
            hits = sorted((ti, i) for ti, i in client.template_index().items() if q in ti)
            for title, tid in hits[:40]:
                print(f"{tid}  {title}")
            print(f"({len(hits)} match{'es' if len(hits) != 1 else ''})")
        elif args.cmd in ("push", "create"):
            with open(args.spec, encoding="utf-8") as fh:
                spec = json.load(fh)
            if args.cmd == "create":
                if not spec.get("title"):
                    print("ERROR: a new routine needs a \"title\" in the spec.")
                    return 1
                body = build_routine_body(client, spec, title=spec["title"])
                body["folder_id"] = None
                if args.dry_run:
                    print(json.dumps({"routine": body}, indent=2))
                    return 0
                client.create_routine(body)
                print(f"OK — created routine {spec['title']!r} with {len(body['exercises'])} exercises.")
            else:
                routine_id = args.routine_id
                current_title = None
                if not routine_id:
                    match = client.find_routine_by_title(args.routine_title)
                    if not match:
                        print(f"No routine titled {args.routine_title!r}. Use `routines` to list them.")
                        return 1
                    routine_id, current_title = match["id"], match.get("title")
                # Hevy requires a title on every PUT — keep the current one by default.
                title = spec.get("title") or current_title or client.get_routine(routine_id).get("title")
                body = build_routine_body(client, spec, title=title)
                if args.dry_run:
                    print(json.dumps({"routine": body}, indent=2))
                    return 0
                client.update_routine(routine_id, body)
                print(f"OK — pushed {len(body['exercises'])} exercises to routine {title!r}.")
            if not getattr(args, "dry_run", False):
                try:  # specs are throwaway; don't let them pile up
                    os.remove(args.spec)
                except OSError:
                    pass
    except HevyError as e:
        print(f"ERROR: {e}")
        return 1
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(_main(sys.argv[1:]))
