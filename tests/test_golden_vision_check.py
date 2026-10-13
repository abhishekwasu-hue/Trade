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
            "client": no_client, "on_usage": lambda ver: (lambda u, c: calls.append("usage")),
            "load_fut": lambda paths: calls.append(("fut", tuple(paths))) or None}


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
    a = types.SimpleNamespace(data={}, futures={}, model="m", max_tokens=8000, shift_weeks=G.SHIFT_WEEKS, scale=G.SCALE, tick=G.TICK, out_dir=None,
                              dry_run=False)
    deps = {**G.default_deps(a), **_deps([]), "client": FC}
    deps["on_usage"] = lambda v: (lambda u, c: calls.append(("usage", v)))
    g = {"vision_daily_budget_usd": 2.0, "vision_monthly_budget_usd": 60.0, "signals_daily_reserve_usd": 0.20}
    today = pd.Timestamp("2026-10-13 18:00")
    st = {"by_task": {}, "g": g, "today": today}
    rec = G.run_case(dict(CASE, expected={"1": "pass", "verdict": "agree"}), a, deps, st)
    assert rec["status"] == "DONE", rec
    assert ("usage", ver) in calls and rec["verdict_row"][-1] == "✔"
    assert st["by_task"][G.TASK][2] == 1
    assert "item 1 unreliable" in rec["warnings"][0]                        # fake W / D लहान ⇒ इशारा
    rec = G.run_case(CASE, a, deps, {"by_task": {"signal": (1.79, 5.0, 9)}, "g": g, "today": today})
    assert rec["status"] == "NOT_RUN_BUDGET" and "reserve" in rec["why"]   # $2 − signals राखीव ओलांडत नाही
    rec = G.run_case(CASE, a, deps, {"by_task": {"signal": (0.0, 59.99, 9)}, "g": g, "today": today})
    assert rec["status"] == "NOT_RUN_BUDGET" and "monthly" in rec["why"]


def test_guard_uses_data_policy():
    from elliott import data_policy as DP
    G.guard(pd.Timestamp(DEC))
    G.guard(pd.Timestamp("2026-09-29 12:15"))
    with pytest.raises(DP.HoldoutError):
        G.guard(pd.Timestamp("2024-06-03 10:00"))


def test_holdout_gap_in_weekly_daily_is_refused(tmp_path):
    fr, asof = _frames(DEC)
    fr["D"] = pd.concat([fr["D"].iloc[:1].assign(timestamp=pd.Timestamp("2024-03-28")), fr["D"]], ignore_index=True)
    assert G.holdout_gap(fr)
    deps = {**_deps([]), "frames": lambda m1, dec: (fr, asof)}
    lines = []
    G.main(["--dry-run", "--cases", _cases(tmp_path, [CASE])], deps=deps, out=lines.append)
    assert any("REFUSED_HOLDOUT_GAP" in x for x in lines)


def test_load_data_refuses_holdout_parquet_and_filters_rows(tmp_path):
    from elliott import data_policy as DP
    df = pd.DataFrame({"timestamp": pd.to_datetime(["2025-01-02 09:15", "2026-09-29 09:15"]), "open": [1.0, 2.0], "high": [1.0, 2.0],
                       "low": [1.0, 2.0], "close": [1.0, 2.0]})
    bad = tmp_path / "nifty50_daily_extension.parquet"
    df.to_parquet(bad)
    with pytest.raises(DP.HoldoutError):
        G.load_data([str(bad)])
    ok = tmp_path / "x.csv"
    df.to_csv(ok, index=False)
    got = G.load_data([str(ok)])
    assert list(got["timestamp"].dt.year) == [2026]                          # holdout row कधीच परत नाही


def test_load_data_converts_tz_aware_parquet_to_ist_before_policy(tmp_path):
    ts = pd.to_datetime(["2025-01-02 09:15", "2026-09-29 09:15", "2026-09-29 09:16"]).tz_localize("Asia/Kolkata")
    df = pd.DataFrame({"timestamp": ts, "open": [1.0, 2.0, 3.0], "high": [1.0, 2.0, 3.0], "low": [1.0, 2.0, 3.0], "close": [1.0, 2.0, 3.0]})
    f = tmp_path / "nifty_tz.parquet"
    df.to_parquet(f)
    got = G.load_data([str(f)])
    assert got["timestamp"].dt.tz is None
    assert [str(x) for x in got["timestamp"]] == ["2026-09-29 09:15:00", "2026-09-29 09:16:00"]


def test_holdout_gap_checked_on_every_frame():
    fr, _ = _frames(DEC)
    assert not G.holdout_gap(fr)
    fr["15M"] = pd.concat([fr["15M"].iloc[:1].assign(timestamp=pd.Timestamp("2024-03-28 10:00")), fr["15M"]], ignore_index=True)
    assert G.holdout_gap(fr)



def _fut(decision, mult_last=3.0):
    """Fake near-month FUT 5M rows aligned to the fake 15M bars (3 × 5M per 15M); last 15M bar volume × mult_last."""
    fr, _ = _frames(decision)
    rows = []
    for i, t in enumerate(fr["15M"]["timestamp"]):
        for k in range(3):
            v = 1000.0 * (mult_last if i == len(fr["15M"]) - 1 else 1.0)
            rows.append((pd.Timestamp(t) + pd.Timedelta(minutes=5 * k), v))
    f = pd.DataFrame(rows, columns=["timestamp", "volume"])
    f["expiry"] = pd.Timestamp("2026-10-27")
    return f


def test_futures_volume_in_facts_and_measured(tmp_path):
    calls, lines = [], []
    deps = {**_deps(calls), "load_fut": lambda paths: calls.append(("fut", tuple(paths))) or _fut(DEC)}
    out_dir = tmp_path / "o"
    G.main(["--dry-run", "--cases", _cases(tmp_path, [CASE]), "--out-dir", str(out_dir), "--futures", "NIFTY=/f.parquet"], deps=deps,
           out=lines.append)
    assert ("fut", ("/f.parquet",)) in calls
    r = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))[0]
    assert r["volume"] == "FUT" and r["measured"]["fut_volume"].startswith("3.00x")
    facts = (out_dir / "c1" / "facts.txt").read_text(encoding="utf-8")
    assert "fut_volume" in facts and "Futures volume: NA" not in facts


def test_missing_futures_is_explicit_na_and_default_paths_used(tmp_path):
    calls, lines = [], []
    out_dir = tmp_path / "o"
    G.main(["--dry-run", "--cases", _cases(tmp_path, [CASE]), "--out-dir", str(out_dir)], deps=_deps(calls), out=lines.append)
    fut_call = [c for c in calls if isinstance(c, tuple) and c[0] == "fut"][0]
    assert any(p.endswith("oe_futures_5min_NIFTY.parquet") for p in fut_call[1])         # collector default
    r = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))[0]
    assert r["volume"] == "NA" and any("volume NA" in w for w in r["warnings"])
    facts = (out_dir / "c1" / "facts.txt").read_text(encoding="utf-8")
    assert "Futures volume: NA" in facts and "never pass an item on volume" in facts
    assert "volume" in "\n".join(lines)


def test_draft_expectations_print_provisional(tmp_path):
    lines = []
    draft = dict(CASE, status="draft — pending Abhi ✅")
    G.main(["--dry-run", "--cases", _cases(tmp_path, [draft])], deps=_deps([]), out=lines.append)
    text = "\n".join(lines)
    assert "PROVISIONAL" in text and "(provisional)" in text and "results PROVISIONAL" in text
    lines.clear()
    G.main(["--dry-run", "--cases", _cases(tmp_path, [dict(CASE, status="confirmed by Abhi ✅")])], deps=_deps([]), out=lines.append)
    assert "PROVISIONAL" not in "\n".join(lines) and "(provisional)" not in "\n".join(lines)


def test_decision3_map_in_every_record(tmp_path):
    out_dir = tmp_path / "o"
    G.main(["--dry-run", "--cases", _cases(tmp_path, [CASE]), "--out-dir", str(out_dir)], deps=_deps([]), out=lambda s: None)
    r = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))[0]
    assert r["decision3_map"] == {str(k): v for k, v in CK.DECISION3_MAP.items()}
