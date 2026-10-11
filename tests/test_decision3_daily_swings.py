"""Daily swing review (Abhi): synthetic Daily fixture (तारखा / किंमती code मध्ये नाहीत) ⇒ view, chart, caption, JSON, manifest, holdout."""
import json
import os
import re

import pandas as pd

from decision3 import charts as CH
from decision3 import daily_swings as DS
from tests.test_decision3 import daily_from_path
from tests.test_decision3_daily_q15 import FLAT


def _view(window=40):
    d = daily_from_path(FLAT + [66, 50, 60, 55])
    return DS.build(d, s={"daily_min_sessions": 3, "daily_sigma_sessions": 3}, window=window, with_elliott=False), d


def test_build_layers_and_tags():
    v, d = _view()
    assert v["n"] == len(d) and v["i0"] == len(d) - 40
    tags = [p["tag"] for p in v["pivots"]]
    assert set(tags) <= {"H", "L", "HH", "LH", "HL", "LL"} and {"LH", "LL"} & set(tags)
    assert v["q15"]["trend"] == "DOWN" and v["minor"]["bands"][-1][1] == len(d) - 1
    assert any(p["protected_q15"] for p in v["pivots"]) and {s["ended"] for s in v["minor"]["protected"]} <= {"broken", "moved", "open"}


def test_q15_origin_break_marked_on_break_bar():
    """Q15: origin close ने तुटला (phase origin_broken, protected तसाच) ⇒ segment त्याच bar ला "broken" (X), flip bar ला नाही."""
    from decision3 import daily as DD
    d = daily_from_path(FLAT[:12] + [96, 92])
    s = {"daily_min_sessions": 3, "daily_sigma_sessions": 3}
    st = DD.fold(d, s)
    brk = next(i for i, x in enumerate(st) if x.phase == "origin_broken")
    v = DS.build(d, s=s, window=len(d), with_elliott=False)
    seg = [x for x in v["q15"]["protected"] if x["ended"] == "broken"]
    assert seg and seg[0]["to"] == brk and d["close"].iloc[brk] > seg[0]["price"]


def test_minor_break_marked_on_neutral_bar_not_when_moved():
    """Minor: protected close ने तुटला ⇒ trend NEUTRAL पण protected state मध्ये तसाच ⇒ X त्याच bar ला (नवा protected येईपर्यंत नाही)."""
    from types import SimpleNamespace as N
    L = N(kind="L", bar=1, price=100.0)
    H = N(kind="H", bar=6, price=120.0)
    st = [N(trend="NEUTRAL", protected=None)] + [N(trend="UP", protected=L)] * 3 + [N(trend="NEUTRAL", protected=L)] * 4 \
        + [N(trend="DOWN", protected=H)] * 2
    C = [110, 110, 105, 104, 99, 98, 101, 102, 103, 104]
    segs = DS.protected_segments(st, C)
    assert segs[0]["ended"] == "broken" and segs[0]["to"] == 4                                   # break bar, NEUTRAL stretch नाही
    assert len(segs) == 2 and segs[1]["kind"] == "H" and segs[1]["ended"] == "open"
    assert "(broken)" in DS._pv({"kind": "L", "price": 100.0}, True) and "(broken)" not in DS._pv({"kind": "L", "price": 100.0})


def test_nifty_aliases_get_holdout_filter():
    import importlib.util
    spec = importlib.util.spec_from_file_location("v22dsv", os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                                                         "scripts", "v22_daily_swings_view.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert all(m.is_nifty(x) for x in ("NIFTY", "nifty", "NIFTY50", "NIFTY 50", "Nifty_50", "NSE:NIFTY"))
    assert not any(m.is_nifty(x) for x in ("BANKNIFTY", "FINNIFTY", "SENSEX"))


def test_legs_use_phase_not_only_trend():
    v, _ = _view()
    q = DS.DD.fold(_view()[1], {"daily_min_sessions": 3, "daily_sigma_sessions": 3})
    for lg in v["legs"]:
        st = q[lg["to"]]
        if lg["class"] == "impulse":
            assert st.phase == "impulse"


def test_chart_png_and_caption_limits():
    v, _ = _view()
    png = CH.daily_swings_png(v, "TEST")
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 10000
    cap = DS.caption(v, "TEST", audit_line="Vision audit: pass")
    lines = cap.splitlines()
    assert len(lines) <= 7 and lines[-1] == "Visual review only — no trade, no order" and "Vision audit: pass" in lines


def test_json_matches_view():
    v, _ = _view()
    js = DS.to_json(v, "TEST")
    shown = [p for p in v["pivots"] if p["in_window"]]
    assert [(p["bar"], p["kind"], p["tag"]) for p in js["pivots"]] == [(p["bar"], p["kind"], p["tag"]) for p in shown]
    assert js["q15"]["trend"] == v["q15"]["trend"] and json.dumps(js, default=str)


def test_elliott_advisory_runs_on_daily_frames():
    d = DS.prepare(daily_from_path([100, 60, 98, 85, 93, 82, 84.5, 74, 76, 62, 80, 70, 72, 58, 75, 64, 70] * 2, legs=6))
    ev = DS.elliott_view(d)
    assert "degrees" in ev and set(ev["degrees"]) >= {"D0", "D1"}                # Daily frames वर engine चालतो (fake 1m ⇒ "1d")
    bad = DS.elliott_view(d.drop(columns=["close"]))
    assert "error" in bad and "degrees" not in bad                                  # अपयश ⇒ कारण, chart तरी बनतो


def _no_holdout_dates(folder, manifest=None):
    """Q33 (Abhi): NIFTY साठी कोणत्याही output (JSON, caption, manifest) मध्ये holdout तारीख नाही."""
    from elliott import data_policy as DP
    texts = [open(folder / f, encoding="utf-8").read() for f in ("daily_swings.json", "caption.txt")]
    texts.append(json.dumps(manifest or {}))
    days = {x for t in texts for x in re.findall(r"\d{4}-\d{2}-\d{2}", t)}
    assert days and not [x for x in days if DP.period(x) == "HOLDOUT"], sorted(days)


def test_nifty_full_history_warmup_never_emits_holdout_dates(tmp_path):
    """Q33: holdout काळात swings / trend असले तरी (elliott labels सह) output मध्ये ती तारीख नाही; engine त्या candles वर warm-up होतो."""
    from elliott import data_policy as DP
    from scripts import v22_daily_swings_view as VS
    pre = daily_from_path([100, 60, 98, 85, 93, 82, 84.5, 74, 76, 62, 80, 70, 72, 58, 75, 64, 70] * 2, legs=6,
                          start=str((DP.HOLDOUT_START - pd.offsets.BDay(100)).date()))
    post = daily_from_path(FLAT + [66, 50], start=str(DP.CONTAMINATED_START.date()))
    a, b = tmp_path / "a.csv", tmp_path / "b.parquet"
    pre[["timestamp", "open", "high", "low", "close"]].to_csv(a, index=False)
    post[["timestamp", "open", "high", "low", "close"]].to_parquet(b)
    out = tmp_path / "run"
    assert VS.main(["--symbol", "NIFTY 50", "--daily", str(a), str(b), "--out-dir", str(out), "--years", "2"]) == 0
    assert any(DP.period(t) == "HOLDOUT" for t in pre["timestamp"])                  # fixture खरंच holdout मधून जातो
    m = json.load(open(out / "manifest.json"))
    _no_holdout_dates(out / "NIFTY 50", m)
    js = json.load(open(out / "NIFTY 50" / "daily_swings.json"))
    assert js["history"]["bars"] == len(pre) + len(post)


def test_script_writes_manifest_nifty_first_and_drops_holdout(tmp_path):
    from elliott import data_policy as DP
    from scripts import v22_daily_swings_view as VS
    d = daily_from_path(FLAT + [66, 50], start=str(DP.CONTAMINATED_START.date()))
    h = daily_from_path([100, 101], start=str(DP.HOLDOUT_START.date()))
    src = tmp_path / "d.csv"
    pd.concat([h, d])[["timestamp", "open", "high", "low", "close"]].to_csv(src, index=False)
    out = tmp_path / "run"
    for sym in ("BANKNIFTY", "NIFTY"):
        assert VS.main(["--symbol", sym, "--daily", str(src), "--out-dir", str(out), "--no-elliott", "--years", "1"]) == 0
    m = json.load(open(out / "manifest.json"))
    assert [x["symbol"] for x in m["items"]] == ["NIFTY", "BANKNIFTY"] and [x["n"] for x in m["items"]] == [1, 2]
    assert all(os.path.exists(out / f) for x in m["items"] for f in x["files"])
    nj = json.load(open(out / "NIFTY" / "daily_swings.json"))
    assert nj["history"]["bars"] == len(h) + len(d)                                  # Q33: holdout candles फक्त engine warm-up
    assert pd.Timestamp(nj["window"]["from"]) >= DP.CONTAMINATED_START               # Q31: NIFTY chart holdout नंतरचाच
    _no_holdout_dates(out / "NIFTY", m)
    bj = json.load(open(out / "BANKNIFTY" / "daily_swings.json"))
    assert pd.Timestamp(bj["history"]["from"]) < DP.CONTAMINATED_START
    from backtest_review import telegram as RT
    assert len(RT.load_manifest(str(out))["items"]) == 2


def test_no_dates_or_prices_hardcoded_in_module():
    src = open(DS.__file__, encoding="utf-8").read() + open(VS_PATH(), encoding="utf-8").read()
    assert not re.search(r"20\d\d-\d\d-\d\d", src)


def VS_PATH():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "v22_daily_swings_view.py")
