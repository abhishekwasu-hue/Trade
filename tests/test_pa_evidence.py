"""PA standard T3 (channels per timeframe) + T9 (evidence wiring) — docs/knowledge/pa_standard/t3_t9_coverage.md.

  • T9: every entry carries `pa_evidence` (each PA track's own evidence words); evidence is listed and NEVER blocks (CLAUDE.md) — the
    entries and the rows are byte-identical with the wiring replaced by an empty list (both mirrors);
  • no look-ahead: the PA rows at a bar = the rows on data cut at that bar;
  • T3: lines / channels on ANY timeframe by the same method §3 / K6.5 core (both mirrors); W / D read on their own candles and swings,
    1H / 15M = the existing degrees unchanged; the row gets the Daily / Weekly channels (`channels_htf`);
  • live display: the payload carries the first fact per track (dropped silently when the payload is too long), the card line is the
    first detail to go when the caption is full, and Vision's input stays as before.
Synthetic only (CI-safe); the real BANKNIFTY check skips without the private trade-data export."""
import json
from types import SimpleNamespace as NS

import numpy as np
import pandas as pd
import pytest

from decision3 import engine as E3
from decision3 import entry_models as EM
from decision3 import pa_evidence as PE
from decision3 import trendline as TL
from tests import oct12_fixture as F

MIRRORS = pytest.mark.parametrize("mirror", [False, True], ids=["bear_call", "bull_put"])
NEW_KEYS = {"pa_evidence", "channels_htf"}
S = {"level_death_side": "role", "entry_area_refine": "area"}


def _strip(x):
    if isinstance(x, dict):
        return {k: _strip(v) for k, v in x.items() if k not in NEW_KEYS}
    if isinstance(x, list):
        return [_strip(v) for v in x]
    return x


def _day(mirror):
    m15, fut, ltf = F.build(mirror=mirror)
    V = E3.V22(m15, s=S, ltf=ltf, futures=fut)
    ts = V.levels.ts
    last = ts.dt.normalize().iloc[-1]
    bars = [i for i in range(len(ts)) if ts.dt.normalize().iloc[i] == last][:3]
    return (m15, fut, ltf), V, bars


@pytest.fixture(scope="module", params=[False, True], ids=["bear_call", "bull_put"])
def day(request):
    inputs, V, bars = _day(request.param)
    return request.param, inputs, V, bars, {i: V.decide(i) for i in bars}


# ------------------------------------------------------------------------------------------------ T9: evidence never blocks
def test_entries_and_rows_identical_without_the_pa_evidence(day, monkeypatch):
    mirror, (m15, fut, ltf), _V, bars, rows = day
    assert any(r["entries"] for r in rows.values())                       # the fixture fires (E1 / E3 on the spike bar)
    monkeypatch.setattr(EM.PE, "for_entry", lambda *a, **k: [])
    V0 = E3.V22(m15, s=S, ltf=ltf, futures=fut)
    plain = {i: V0.decide(i) for i in bars}
    a = json.dumps(_strip(rows), default=str, sort_keys=True)
    b = json.dumps(_strip(plain), default=str, sort_keys=True)
    assert a == b                                                          # every decision field byte-identical
    for i in bars:
        assert [e.get("pa_evidence") for e in plain[i]["entries"]] == [[] for _ in plain[i]["entries"]]


def test_every_entry_lists_each_tracks_facts(day):
    mirror, _inputs, _V, bars, rows = day
    ents = [e for r in rows.values() for e in r["entries"]]
    for e in ents:
        rows_ = e["pa_evidence"]
        assert rows_ and all(set(x) == {"track", "concept", "tf", "text", "src"} and x["text"] for x in rows_)
        tracks = [x["track"] for x in rows_]
        assert tracks == sorted(tracks, key=PE.TRACK_ORDER.index)          # the standard's order
        assert {"T1", "T2", "T3", "T4", "T5", "T6"} <= set(tracks)
        assert not [x for x in rows_ if x["concept"] == "NA"]              # every track read on a real reader
        side = "bull" if mirror else "bear"
        assert any(f"hidden {side} divergence" in x["text"] for x in rows_ if x["track"] == "T6")
        assert any(x["track"] == "T2" and x["concept"] == "area base / departure" for x in rows_)   # the entry area's own base
        json.dumps(rows_)                                                  # JSON-safe (payload / store)
    e1 = next(e for e in ents if e["model"] == "E1")
    assert "required set" in e1["evidence"][0][0]                          # the evidence list keeps the required set first (DECISIONS 54)


def test_volume_rows_say_fut_volume_missing_never_spot():
    m15, _fut, ltf = F.build()
    V = E3.V22(m15, s=S, ltf=ltf)                                          # no FUT bars
    t = len(m15) - 20
    area = {"id": None, "lo": float(m15["low"].iloc[t]), "hi": float(m15["high"].iloc[t]), "object": "line"}
    rows = PE.for_entry(V, t, -1, area)
    vol = [x for x in rows if x["track"] == "T5" and x["concept"] == "volume"]
    assert [x["text"] for x in vol] == ["FUT volume missing (never spot volume)"]


def test_one_track_failing_gives_one_na_row_and_never_stops_the_rest(monkeypatch):
    m15, fut, ltf = F.build()
    V = E3.V22(m15, s=S, ltf=ltf, futures=fut)
    t = len(m15) - 20
    boom = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x"))       # noqa: E731
    monkeypatch.setattr(PE, "TRACKS", tuple((k, boom if k == "T4" else f) for k, f in PE.TRACKS))
    rows = PE.for_entry(V, t, -1, {"id": None, "lo": 1.0, "hi": 1.0, "object": "line"})
    na = [x for x in rows if x["concept"] == "NA"]
    assert [x["track"] for x in na] == ["T4"] and "not read (RuntimeError)" in na[0]["text"]
    assert {"T1", "T3", "T5"} <= {x["track"] for x in rows}


@pytest.mark.parametrize("back", [0, 10], ids=["session_close", "mid_session"])
def test_no_look_ahead_rows_at_a_bar_equal_the_rows_on_data_cut_there(back):
    m15, fut, ltf = F.build()
    V = E3.V22(m15, s=S, ltf=ltf, futures=fut)
    ts = V.levels.ts
    day_end = [i for i in range(len(ts) - 1) if ts.iloc[i + 1].normalize() != ts.iloc[i].normalize()]
    t = day_end[-3] - back                                                 # a session's last bar (or inside it), two sessions back
    snap = [a for a in V.levels.snapshot(t) if a["state"] != "DEAD"]
    a = min(snap, key=lambda x: x["dist"])
    d = -1 if a["role"] == "resistance" else 1
    area = {k: a.get(k) for k in ("id", "tf", "role", "lo", "hi")} | {"object": "area"}
    full = PE.for_entry(V, t, d, area, lvl=a)
    end = pd.Timestamp(m15["bar_end"].iloc[t])
    five = pd.Timedelta(minutes=5)                                         # the fixture's 5M bars carry their start only
    V2 = E3.V22(m15.iloc[:t + 1].reset_index(drop=True), s=S, ltf=ltf[ltf["timestamp"] + five <= end].reset_index(drop=True),
                futures=fut[fut["timestamp"] + five <= end].reset_index(drop=True))
    a2 = next(x for x in V2.levels.snapshot(t) if x["id"] == a["id"])
    cut = PE.for_entry(V2, t, d, area, lvl=a2)
    assert [x["text"] for x in full] == [x["text"] for x in cut]
    assert TL.channels_by_tf(V, t)["D"]["channels"] == TL.channels_by_tf(V2, t)["D"]["channels"]


# ------------------------------------------------------------------------------------------------ T3: channels per timeframe
MID = 100.0
# A rising channel on any timeframe's own bars: lows 90 (bar 2) → 94 (bar 8), the highs between at 100 (bar 5); price inside at the end.
CLOSES = [93, 91.5, 90.5, 94, 97, 99, 96, 95, 94.5, 97.5, 100.5, 101, 100]
LOWS = [92, 91, 90, 93, 96, 98, 95, 94.6, 94, 96.5, 99.5, 100.5, 99.5]
HIGHS = [94, 93, 91.5, 95, 98, 100, 97.5, 96, 95.5, 98, 101.5, 102.8, 101.5]
PIVOTS = [("L", 90.0, 2), ("H", 100.0, 5), ("L", 94.0, 8), ("H", 102.8, 11)]


def _frame(mirror):
    m = (lambda x: 2 * MID - x) if mirror else (lambda x: x)
    C = np.array([m(x) for x in CLOSES], float)
    H = np.array([m(x) for x in (LOWS if mirror else HIGHS)], float)
    L = np.array([m(x) for x in (HIGHS if mirror else LOWS)], float)
    A = {"open": np.r_[C[0], C[:-1]], "high": H, "low": L, "close": C}
    flip = {"H": "L", "L": "H"}
    known = [NS(kind=flip[k] if mirror else k, price=m(p), bar=b, confirm_bar=b + 1) for k, p, b in PIVOTS]
    return A, known


@MIRRORS
def test_lines_and_channels_on_any_timeframe_by_the_same_core(mirror):
    A, known = _frame(mirror)
    t = len(A["close"]) - 1
    lines = TL.lines_on(A, known, t, None, "D", "D")
    fam = "falling line of highs" if mirror else "rising line of lows"
    ln = next(x for x in lines if x["family"] == fam)
    assert ln["id"] == f"D:{'H-' if mirror else 'L+'}:2-8" and ln["tf"] == "D" and ln["state"] == "ACTIVE" and ln["touches"] >= 2
    ch = next(c for c in TL.channels_on(A, known, lines, t, None) if c["base"] == ln["id"])
    assert ch["state"] == "inside" and ch["tf"] == "D" and ch["slope_dir"] == ("falling" if mirror else "rising")
    par = 2 * MID - 100.0 if mirror else 100.0                             # the parallel through the opposite extreme between the anchors
    assert ch["parallel"]["p1"] == [5, par]
    up, lo = (2 * MID - ch["lower_t"], 2 * MID - ch["upper_t"]) if mirror else (ch["upper_t"], ch["lower_t"])
    assert lo < float(CLOSES[-1]) < up


def test_channels_by_tf_reads_each_timeframe_on_its_own_swings(day):
    _mirror, _inputs, V, bars, rows = day
    t = bars[0]
    by = TL.channels_by_tf(V, t)
    assert tuple(by) == TL.CHANNEL_TFS == ("W", "D", "1H", "15M")
    for tf, g in (("1H", 2), ("15M", 1)):                                  # the existing degrees of the 15M chart, unchanged
        assert by[tf]["channels"] == TL.channels(V, t, g) and by[tf]["lines"] == TL.channel_lines(V, t, g)
    from decision3 import mtf_state as MS
    n = MS.frame(V, t, "D")["n"]
    assert by["D"]["structure"].startswith("Daily") and by["D"]["lines"]
    for x in by["D"]["lines"]:                                             # Daily candles closed by t only
        assert x["id"].startswith("D:") and x["p2"][0] < n and x["tf"] == "D"
    r = rows[t]
    assert set(r["channels_htf"]) == {"D", "W"}
    assert r["channels_htf"]["D"]["channels"] == TL.compact_channels(by["D"]["channels"])
    assert [c["id"] for c in r["channels"]] == [c["id"] for g in TL.line_degrees(V) for c in TL.channels(V, t, g)]   # row unchanged


def test_e4b_objects_stay_the_trend_degrees_lines(day):
    """Daily / Weekly broken channel lines are evidence only — never an E4 (b) retest object (that would be a new entry location)."""
    _mirror, _inputs, V, bars, _rows = day
    t = bars[-1]
    for d in (-1, 1):
        ids = [obj["id"] for kind, obj, *_ in EM.Reader(V).broken_objects(t, d) if kind == "line"]
        assert all(i.startswith(f"D{V.s['level_degree']}:") for i in ids), ids


# ------------------------------------------------------------------------------------------------ live display
def test_payload_carries_the_first_fact_per_track_and_drops_it_silently_when_too_long():
    import engine3_live as L
    rows = [{"track": "T1", "concept": "market state", "tf": "W", "text": "W trending up", "src": "x"},
            {"track": "T1", "concept": "market state", "tf": "D", "text": "D range", "src": "x"},
            {"track": "T3", "concept": "channel", "tf": "D", "text": "D rising channel: price inside", "src": "x"}]
    e = {"model": "E1", "direction": -1, "area": {"id": 1, "lo": 1.0, "hi": 2.0}, "invalidation": 2.0, "pa_evidence": rows}
    c = L.compact_entries([e])[0]
    assert c["pa_evidence"] == [{"track": "T1", "tf": "W", "text": "W trending up"},
                                {"track": "T3", "tf": "D", "text": "D rising channel: price inside"}]
    assert "pa_evidence" not in L.compact_entries([{k: v for k, v in e.items() if k != "pa_evidence"}])[0]   # older rows: as before
    big = {"engine": "decision3", "entries": [c], "pad": "x" * 50}
    out = json.loads(L.fit_payload(big, limit=len(json.dumps(big)) - 10))
    assert "pa_evidence" not in out["entries"][0] and "dropped" not in out and out["pad"] == big["pad"]


def test_card_pa_line_and_vision_input_unchanged():
    from vision import card_summary as CS
    from vision import signal_audit as SA
    from vision import worker as W
    tags = {"entry_model": "E1", "entry_name": "Aggressive", "entry_pa_evidence": [
        {"track": "T1", "tf": "W", "text": "W trending up (protected 1,000.00)"},
        {"track": "T5", "tf": "15M", "text": "FUT volume missing (never spot volume)"}]}
    line = CS.pa_lines(tags)
    assert len(line) == 1 and "PA evidence (listed, never blocks)" in line[0]
    assert "W trending up · FUT volume missing" in line[0] and "protected" not in line[0]
    assert CS.pa_lines({"entry_pa_evidence": tags["entry_pa_evidence"]}) == []   # not an entry-model signal ⇒ today's card
    assert CS.pa_brief("x" * 3) == "" and len(CS.pa_brief([{"track": "T1", "text": "y" * 999}])) == CS.PA_MAX
    base = {"symbol": "NIFTY", "direction": "BEARISH", "tags": {"entry_model": "E1"}}
    assert SA.signal_text({**base, "tags": {**base["tags"], "entry_pa_evidence": tags["entry_pa_evidence"]}}) == SA.signal_text(base)
    lines = ["head", "dec", "detail 1", "detail 2", line[0], "tail"]       # the caption order: PA line just before the tail
    fit = W._fit(lines, limit=len("\n".join(lines)) - 5, keep=2)
    assert line[0] not in fit and "detail 2" in fit and fit.endswith("tail")   # the PA line goes first; today's lines stay


# ------------------------------------------------------------------------------------------------ real data (private export)
def test_real_banknifty_entries_identical_and_every_entry_has_pa_evidence(monkeypatch):
    R = pytest.importorskip("tests.test_entry_models_real_bn_oct07")
    monkeypatch.setattr(R, "DAY", "2026-10-09")
    _V, _ts, rows = R._build()                                             # skips cleanly without the private trade-data export
    ents = [e for r in rows.values() for e in r["entries"]]
    assert ents and all(e["pa_evidence"] and not [x for x in e["pa_evidence"] if x["concept"] == "NA"] for e in ents)
    assert all(set(r["channels_htf"]) == {"D", "W"} for r in rows.values())
    monkeypatch.setattr(EM.PE, "for_entry", lambda *a, **k: [])
    _V0, _ts0, plain = R._build()
    assert json.dumps(_strip(rows), default=str, sort_keys=True) == json.dumps(_strip(plain), default=str, sort_keys=True)


def test_fit_payload_drops_pa_evidence_before_the_reader_facts():
    """Review of #375: the new display evidence never pushes out today's card facts (`reader`)."""
    import json
    import engine3_live as EL
    payload = {"engine": "v22", "reader": {"summary": "x" * 200},
               "entries": [{"model": "E3", "pa_evidence": [{"text": "y" * 400}]}], "armed": []}
    full = json.dumps(payload, ensure_ascii=False)
    lim = len(full) - 100                                                   # only the PA evidence has to go
    out = json.loads(EL.fit_payload(payload, lim))
    assert "reader" in out and "pa_evidence" not in out["entries"][0]
