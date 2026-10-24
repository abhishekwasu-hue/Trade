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
    s = {"daily_min_sessions": 3, "daily_sigma_sessions": 3, "daily_parent_gate": False}   # Q53: origin_broken यंत्रणा (gate off)
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


def test_script_survives_malformed_accepted_legs_override(tmp_path, monkeypatch, caplog):
    """PR #304: a broken private override (DECISION3_ACCEPTED_LEGS) never kills the daily chart / Telegram run — warning, repo file."""
    from decision3 import accepted_legs as AL
    from scripts import v22_daily_swings_view as VS
    src = tmp_path / "d.csv"
    daily_from_path(FLAT + [66, 50])[["timestamp", "open", "high", "low", "close"]].to_csv(src, index=False)
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    monkeypatch.setenv(AL.ENV, str(bad))
    out = tmp_path / "run"
    with caplog.at_level("WARNING", logger=AL.__name__):
        assert VS.main(["--symbol", "BANKNIFTY", "--daily", str(src), "--out-dir", str(out), "--no-elliott", "--years", "1"]) == 0
    assert os.path.exists(out / "BANKNIFTY" / "daily_swings.png")
    assert any("falling back to the repo file" in r.getMessage() for r in caplog.records)


def test_no_dates_or_prices_hardcoded_in_module():
    src = open(DS.__file__, encoding="utf-8").read() + open(VS_PATH(), encoding="utf-8").read()
    assert not re.search(r"20\d\d-\d\d-\d\d", src)


def VS_PATH():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "v22_daily_swings_view.py")


def _sw(spec):
    from types import SimpleNamespace as N
    return [N(kind=k, price=float(px), bar=j * 3, confirm_bar=j * 3 + 2) for j, (k, px) in enumerate(spec)]


def _mirror(spec):
    return [("L" if k == "H" else "H", -px) for k, px in spec]


MIRROR_TAG = {"H": "L", "L": "H", "HH": "LL", "LL": "HH", "LH": "HL", "HL": "LH", "EQH": "EQL", "EQL": "EQH"}


def test_structure_tags_compare_with_the_same_degree_reference_not_an_inner_swing():
    """Abhi gallery review F1: a structural higher low is never "LL" because an inner low sat above it, and a pullback high inside a
    down leg is never "HH" while it stays below the leg's own high. Both mirrors."""
    up = [("L", 50), ("H", 70), ("L", 60), ("H", 65), ("L", 55), ("H", 75), ("L", 58), ("H", 72), ("L", 52)]
    tags = DS.tag_pivots(_sw(up))
    # 55 vs the reference low 50 (60 was an inner low) ⇒ HL; 75 > 70 ⇒ HH and the reference low moves to the low the break started
    # from (55); 58 ⇒ HL; 72 < 75 ⇒ LH; 52 < 55 ⇒ LL
    assert tags == ["L", "H", "HL", "LH", "HL", "HH", "HL", "LH", "LL"]
    dn = [("H", 100), ("L", 80), ("H", 95), ("L", 85), ("H", 97), ("L", 78), ("H", 96), ("L", 82), ("H", 98)]
    tags = DS.tag_pivots(_sw(dn))
    # 97 above the inner high 95 but below the reference high 100 ⇒ LH (the old label said HH); 78 < 80 ⇒ LL and the reference high
    # becomes the highest high between 80 and 78 (97); 96 < 97 ⇒ LH; 82 ⇒ HL; 98 > 97 ⇒ HH
    assert tags == ["H", "L", "LH", "HL", "LH", "LL", "LH", "HL", "HH"]
    for spec in (up, dn):
        assert DS.tag_pivots(_sw(_mirror(spec))) == [MIRROR_TAG[t] for t in DS.tag_pivots(_sw(spec))]


def test_structure_tags_equal_by_c13_area_only_with_opens_and_closes():
    """C-13 (L1-b): a later high that reaches the reference high candle's area (body top to high) without going beyond ⇒ EQH; one that
    stays short of the area ⇒ LH. Without opens / closes no EQ label. Mirror: EQL."""
    import numpy as np
    spec = [("H", 100), ("L", 80), ("H", 99), ("L", 85), ("H", 95)]
    piv = _sw(spec)
    n = piv[-1].bar + 3
    O, C = np.full(n, 90.0), np.full(n, 90.0)
    O[piv[0].bar], C[piv[0].bar] = 97.0, 92.0                              # the reference high's candle: area 97 – 100
    O[piv[1].bar], C[piv[1].bar] = 82.0, 82.0                              # the reference low's candle: area 80 – 82
    assert DS.tag_pivots(piv, O, C) == ["H", "L", "EQH", "HL", "LH"]
    assert DS.tag_pivots(piv) == ["H", "L", "LH", "HL", "LH"]
    mp = _sw(_mirror(spec))
    Om, Cm = -O, -C
    assert DS.tag_pivots(mp, Om, Cm) == ["L", "H", "EQL", "LH", "HL"]
