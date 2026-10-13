"""scripts/golden_vision_check.py (R0): dry-run मार्ग fakes सह (API / Upstox / खरा data नाही), anonymise, policy guard, compare."""
import importlib
import json

import numpy as np
import pandas as pd
import pytest

G = importlib.import_module("scripts.golden_vision_check")
from vision import checklist as CK      # noqa: E402
from vision import method_pack as MP    # noqa: E402

DEC = "2026-10-12 09:30"                                                   # fixture तारीख (test data, code logic नाही)


def _frames(decision):
    d = pd.Timestamp(decision)
    out = {}
    for tf, step, n in (("W", "7D", 10), ("D", "1D", 20), ("1H", "1h", 30), ("15M", "15min", 40), ("5M", "5min", 50)):
        ts = pd.date_range(end=d, periods=n, freq=step)
        base = 22600 + np.arange(n) * 1.37
        out[tf] = pd.DataFrame({"timestamp": ts, "bar_end": ts + pd.Timedelta(step), "open": base, "high": base + 9.4,
                                "low": base - 7.65, "close": base + 2.2})
    return out, d + pd.Timedelta(minutes=15)


def _deps(calls):
    def no_client():
        calls.append("client")
        raise AssertionError("dry-run must not create an API client")
    return {"load": lambda paths: calls.append(("load", tuple(paths))) or pd.DataFrame(),
            "frames": lambda m1, dec: _frames(dec),
            "render": lambda fr, asof: [b"PNG-" + tf.encode() for tf in G.TFS if tf in fr],
            "client": no_client, "on_usage": lambda ver: (lambda u, c: calls.append("usage"))}


def _cases(tmp_path, cases):
    p = tmp_path / "cases.json"
    p.write_text(json.dumps({"cases": cases}), encoding="utf-8")
    return str(p)


CASE = {"id": "c1", "symbol": "NIFTY", "decision": DEC, "direction": "BEARISH", "area": [22640.0, 22667.35], "data": ["x.csv"],
        "expected": {"1": "pass", "2": "TODO", "verdict": "TODO"}}


def test_dry_run_builds_everything_prints_estimate_and_never_calls_api(tmp_path):
    calls, lines = [], []
    out_dir = tmp_path / "out"
    rc = G.main(["--dry-run", "--cases", _cases(tmp_path, [CASE]), "--out-dir", str(out_dir)], deps=_deps(calls), out=lines.append)
    text = "\n".join(lines)
    assert rc == 0 and "client" not in calls and "usage" not in calls
    assert "DRY_RUN" in text and "tokens: system ≈" in text and "cost est.: uncached $" in text
    summ = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    r = summ[0]
    assert r["status"] == "DRY_RUN" and r["n_images"] == 5 and r["pack_version"] == MP.load()[1]
    assert r["estimate"]["system_tokens"] > 6000 and r["estimate"]["usd_cached"] < r["estimate"]["usd_uncached"]
    facts = (out_dir / "c1" / "facts.txt").read_text(encoding="utf-8")
    assert "NIFTY" not in facts and "2026" not in facts and "22,640" not in facts      # symbol / तारीख / किंमत लपवले
    assert "hidden" in facts and "BEARISH" in facts and (out_dir / "c1" / "input_15M.png").read_bytes() == b"PNG-15M"


def test_todo_cases_are_skipped_and_holdout_refused(tmp_path):
    calls, lines = [], []
    todo = dict(CASE, id="t", decision="TODO(Abhi): later")
    nodata = dict(CASE, id="n", data="TODO(Abhi): file")
    hold = dict(CASE, id="h", decision="2025-03-03 10:15")                  # sealed holdout ⇒ कधीच load नाही
    G.main(["--dry-run", "--cases", _cases(tmp_path, [todo, nodata, hold])], deps=_deps(calls), out=lines.append)
    text = "\n".join(lines)
    assert "t · SKIPPED_TODO" in text and "n · SKIPPED_TODO" in text and "h · REFUSED_POLICY" in text
    assert not any(isinstance(c, tuple) and c[0] == "load" for c in calls)


def test_data_arg_overrides_case_data(tmp_path):
    calls = []
    nodata = dict(CASE, data="TODO")
    G.main(["--dry-run", "--cases", _cases(tmp_path, [nodata]), "--data", "NIFTY=/a.csv,/b.csv"], deps=_deps(calls), out=lambda s: None)
    assert ("load", ("/a.csv", "/b.csv")) in calls


def test_repo_fixture_has_three_golden_cases_with_todo_expectations():
    cases = json.load(open(G.CASES_DEFAULT, encoding="utf-8"))["cases"]
    assert [c["symbol"] for c in cases] == ["NIFTY", "NIFTY", "BANKNIFTY"]
    for c in cases:
        assert set(c["expected"]) == {str(n) for n in range(1, 8)} | {"verdict"}
    lines = []
    G.main(["--dry-run"], deps=_deps([]), out=lines.append)                 # TODO ⇒ skip, crash नाही
    assert sum("SKIPPED_TODO" in x for x in lines) >= 2


def test_anonymise_shifts_whole_weeks_and_rescales_to_tick():
    fr, asof = _frames(DEC)
    afr, aasof = G.anonymise(fr, asof, shift_weeks=10, scale=0.5, tick=0.05)
    assert (pd.Timestamp(asof) - aasof).days == 70 and aasof.weekday() == pd.Timestamp(asof).weekday()
    assert aasof.strftime("%H:%M") == pd.Timestamp(asof).strftime("%H:%M")
    v = afr["15M"]["high"].to_numpy()
    assert np.allclose(np.round(v / 0.05) * 0.05, v)
    assert np.allclose(v, np.round(fr["15M"]["high"].to_numpy() * 0.5 / 0.05) * 0.05)
    assert not set(fr["15M"]["close"]) & set(afr["15M"]["close"])


def test_compare_marks_match_mismatch_todo():
    data = {"verdict": "partly", "items": [{"n": n, "status": "pass" if n != 6 else "fail", "evidence": f"e{n}"} for n in range(1, 8)]}
    rows, vr = G.compare(data, {"1": "pass", "6": "pass", "verdict": "partly"})
    marks = {r[0]: r[-1] for r in rows}
    assert marks[1] == "✔" and marks[6] == "✘" and marks[2] == "TODO" and vr[-1] == "✔"


def test_real_run_path_with_fake_client_validates_and_logs_usage(tmp_path):
    import types
    _, ver = MP.load()
    calls = []

    class FC:
        def __init__(self):
            self.messages = self

        def create(self, **kw):
            calls.append(kw)
            txt = kw["messages"][0]["content"][-1]["text"]
            price = CK.numbers(txt.split("Proposed area: ")[1])[0][2]          # anonymised किंमत (facts मधून)
            items = [{"n": n, "status": "pass", "evidence": f"band {price}" if n == 2 else "ok"} for n in range(1, 8)]
            u = types.SimpleNamespace(input_tokens=100, output_tokens=50, cache_read_input_tokens=0, cache_creation_input_tokens=0)
            return types.SimpleNamespace(stop_reason="end_turn", usage=u, content=[types.SimpleNamespace(
                type="text", text=json.dumps({"pack_version": ver, "items": items, "verdict": "agree"}))])
    a = types.SimpleNamespace(data={}, model="m", max_tokens=8000, shift_weeks=G.SHIFT_WEEKS, scale=G.SCALE, tick=G.TICK, out_dir=None,
                              dry_run=False)
    deps = {**G.default_deps(a), **_deps([]), "client": FC}
    deps["on_usage"] = lambda v: (lambda u, c: calls.append(("usage", v)))
    rec = G.run_case(dict(CASE, expected={"1": "pass", "verdict": "agree"}), a, deps, {"spent": 0.0, "cap": 2.0})
    assert rec["status"] == "DONE", rec
    assert ("usage", ver) in calls and rec["verdict_row"][-1] == "✔"
    rec = G.run_case(CASE, a, deps, {"spent": 1.99, "cap": 2.0})            # $2 / दिवस budget ओलांडत नाही
    assert rec["status"] == "NOT_RUN_BUDGET"


def test_guard_uses_data_policy():
    from elliott import data_policy as DP
    G.guard(pd.Timestamp(DEC))
    G.guard(pd.Timestamp("2026-09-29 12:15"))
    with pytest.raises(DP.HoldoutError):
        G.guard(pd.Timestamp("2024-06-03 10:00"))
