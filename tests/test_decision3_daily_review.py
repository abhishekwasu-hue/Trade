"""Abhi daily-swings review (A1–A5, B1–B2): parent-degree gate, origin advancement, maturity, caption, Elliott log, RANGE check.

Synthetic fixture = the NIFTY shape from the review (no real dates / prices in code): a larger high, the (A) low, a (B) top, then a C
decline — (1)–(3) with minor bounces, a large (4) rally that breaks the engine's minor origin but not the C start, and (5) with three
small bounces into the (A) low zone.
"""
import numpy as np
import pandas as pd
import pytest

from decision3 import daily as DD
from decision3 import daily_swings as DS
from decision3 import settings as S3


def path(points):
    """[(price, bars to reach)] ⇒ Daily OHLC (linear closes; high / low = body ± 2 ⇒ turning bars carry the extremes)."""
    closes = [points[0][0]]
    for px, nb in points[1:]:
        closes += list(np.linspace(closes[-1], px, nb + 1)[1:])
    c = np.array(closes, float)
    o = np.r_[c[0], c[:-1]]
    ts = pd.bdate_range("2020-01-01", periods=len(c))
    return DS.prepare(pd.DataFrame({"timestamp": ts, "open": o, "high": np.maximum(o, c) + 2.0, "low": np.minimum(o, c) - 2.0,
                                    "close": c}))


HEAD = [(1000, 0), (1400, 20), (1000, 20), (1350, 20),                      # larger high, (A) low, (B) top
        (1250, 6), (1300, 4), (1150, 8),                                    # C: LH + close below the low between ⇒ DOWN
        (1170, 3), (1120, 4), (1160, 4), (1080, 6)]                         # (3) with two minor bounces (20, then 40)
WAVE4 = [(1250, 12)]                                                        # (4): breaks the minor origin, C start holds
WAVE5 = [(1215, 4), (1235, 3), (1190, 5),                                   # (5): LH + close below the low between
         (1200, 3), (1120, 6), (1135, 3), (1060, 6), (1075, 3), (996, 7), (1004, 2)]   # three small bounces ⇒ (A) low zone


def _fold(points, s=None):
    d = path(points)
    return d, DD.fold(d, s)


def _top_bar(d, a, b):
    return a + int(np.argmax(d["high"].to_numpy()[a:b]))


def test_c_wave_fixture_down_throughout_with_wave4_correction_and_wave5_origin():
    d, st = _fold(HEAD + WAVE4 + WAVE5)
    start = next(i for i, x in enumerate(st) if x.trend == "DOWN")
    assert all(x.trend == "DOWN" for x in st[start:]), "no UP state anywhere after the C decline starts"
    parent = st[start].parent.price                                        # ABC_FIX rule 1: the trend-degree impulse start = the (B)
    assert parent == 1352.0                                                 # top where C began (was the LH 1302 in #289 — Q50)
    n4 = sum(nb for _, nb in HEAD) + 1
    top4 = _top_bar(d, n4 - 12, n4 + 12)                                    # (4) top = the highest high of the rally
    broke = next(i for i in range(start, len(st)) if st[i].counter == "correction")
    assert broke < top4
    for x in st[broke:top4 + 1]:                                            # "correction (4) in progress" up to its top
        assert x.trend == "DOWN" and x.phase == "correction" and x.counter == "correction"
        assert x.protected.price == parent and x.parent.price == parent
    five = next(i for i in range(top4, len(st)) if st[i].phase == "impulse")
    for x in st[five:]:                                                     # (5): origin = (4) top for the whole decline
        assert x.protected.price == float(d["high"].iloc[top4]) and x.protected.bar == top4
    low3 = float(d["low"].iloc[60:110].min())                               # Q44: target = पहिल्या impulse leg चं टोक ((3) low,
    assert st[-1].mature and st[-1].targets == (low3,)                      # (4) A1 correction आधी); (5) तिथे पोचला ⇒ mature
    objs = DS.structure_objects(d, st)
    tags = [b["tag"] for b in objs["bounces"] if b["bar"] > top4]
    assert tags and all(t == "pullback" for t in tags)                     # bounces inside (5) are lower degree
    c4 = [c for c in objs["corrections"] if c["end_bar"] == top4]
    assert len(c4) == 1 and c4[0]["kind"] == "correction" and 0 < c4[0]["depth"] < 1   # depth vs the impulse from the parent


def test_parent_gate_off_flips_the_trend_on_the_wave4_rally():
    s = {**S3.DEFAULTS, "daily_parent_gate": False}
    _, st = _fold(HEAD + WAVE4 + WAVE5, s)
    start = next(i for i, x in enumerate(st) if x.trend == "DOWN")
    assert any(x.trend != "DOWN" or x.phase == "origin_broken" for x in st[start:])   # old behaviour: origin_broken / flip


@pytest.mark.xfail(strict=True, reason="Q50: #289 hybrid parent (previous same-degree correction top) superseded by ABC_FIX "
                                       "rule 1 (parent = trend-degree impulse start) — pending Abhi")
def test_parent_is_previous_same_degree_correction_when_one_is_large_enough():
    pts = [(1000, 0), (1400, 20), (1000, 20), (1350, 20), (1250, 6), (1300, 4), (1150, 8),
           (1170, 3), (1130, 4), (1220, 8), (1100, 8),                      # (2)-size correction (90) ⇒ origin → its top
           (1115, 3), (1085, 4), (1115, 4), (1060, 5),                      # minor correction (30) ⇒ origin → a minor top
           (1140, 8),                                                       # counter-move 80 < 90 ⇒ parent = (2) top, not the C start
           (1120, 4), (1130, 3), (1050, 6)]
    d, st = _fold(pts)
    corr = [x for x in st if x.counter == "correction"]
    assert corr, "the rally is a same-degree correction, not a flip"
    assert corr[0].parent.price == 1222.0 and corr[0].protected.price == 1222.0
    start = next(i for i, x in enumerate(st) if x.trend == "DOWN")
    assert st[start].protected.price == 1302.0                              # trend-start origin is further away
    assert all(x.trend == "DOWN" for x in st[start:])


def test_mature_impulse_lets_a_counter_impulse_break_the_origin_normally():
    _, st = _fold(HEAD + WAVE4 + WAVE5 + [(1270, 14)])                      # after mature (5): rally above the (5) origin
    assert st[-15].mature
    after = st[-14:]
    assert not any(x.counter == "correction" for x in after)               # no A1 hold after maturity
    assert any(x.phase == "origin_broken" or x.trend == "UP" for x in after)


def test_origin_risk_when_the_correction_reaches_the_parent_zone():
    d, st = _fold(HEAD + [(1349, 14), (1338, 2)])                          # (4) reaches the parent ((B) top) zone
    hit = [x for x in st if x.counter == "correction" and x.origin_risk]
    assert hit and all(x.trend == "DOWN" for x in hit)


def test_trend_line_wording_and_state_labels():
    d, st = _fold(HEAD + WAVE4 + WAVE5)
    v = DS.build(path(HEAD + WAVE4 + WAVE5), window=60, with_elliott=False)
    line = DS.trend_line(v["q15"])
    assert line.startswith("Trend DOWN") and "protected 1,252" in line and "larger reversal possible" in line   # (4) sharp-fall zone
    assert "correction completed at sharp-fall supply" in line and "target 1,078" in line                          # मध्ये संपली (rule 5)
    labels = {s for _, _, s in v["q15"]["states"]}
    assert labels <= {"UP · impulse", "UP · correction", "DOWN · impulse", "DOWN · correction", "RANGE", "NEUTRAL", "UNKNOWN"}
    cap = DS.caption(v, "TEST")                                             # §5.7: ओळ 1 अवस्था + protected + risk, ओळ 2 जवळचा पट्टा
    assert cap.splitlines()[0].startswith("TEST Daily: DOWN") and cap.splitlines()[1].startswith("Nearest ")
    assert cap.splitlines()[2].startswith("Trend DOWN") and "Dow minor swings (secondary)" in cap.splitlines()[3]
    q = {**v["q15"], "phase": "correction", "counter": "correction", "retrace": 0.62}
    assert "correction in progress (same degree; parent origin holds) (depth 62% of last impulse)" in DS.trend_line(q)
    assert "pullback in progress (lower degree)" in DS.trend_line({**v["q15"], "phase": "impulse", "counter": "pullback", "rule5": False})


def test_elliott_vs_dow_logs_agreement():
    v = {"q15": {"trend": "DOWN", "phase": "impulse", "counter": None, "protected_now": None, "mature": False},
         "elliott_degree": "D3", "elliott": {"degrees": {"D3": {"pattern": "wxy", "direction": -1, "current_wave": "Y", "gray": False}}}}
    ev = DS.elliott_vs_dow(v)
    assert ev["direction_agree"] is True and ev["structure_agree"] is False and ev["elliott"] == "D3 wxy wave Y"
    v["elliott"]["degrees"]["D3"].update(pattern="impulse", current_wave="4")
    ev = DS.elliott_vs_dow(v)
    assert ev["direction_agree"] is False
    assert DS.elliott_vs_dow({**v, "elliott_degree": None, "elliott": {"error": "disabled"}})["direction_agree"] is None


def test_range_check_reports_trend_degree_pairs():
    d, st = _fold(HEAD + WAVE4 + WAVE5)
    rc = DS.range_check(d, DS.structure_objects(d, st))
    assert len(rc["lows"]) == 2 and len(rc["highs"]) == 2 and rc["tol"] > 0 and rc["range"] is False


def test_view_script_logs_elliott_vs_dow(tmp_path):
    import importlib.util
    import os
    spec = importlib.util.spec_from_file_location("vds", os.path.join(os.path.dirname(__file__), "..", "scripts",
                                                                       "v22_daily_swings_view.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    ev = {"dow": "Trend DOWN (impulse)", "elliott": "D3 wxy wave Y", "direction_agree": True, "structure_agree": False}
    m.log_elliott(str(tmp_path), "NIFTY", "2030-01-02", ev)
    m.log_elliott(str(tmp_path), "NIFTY", "2030-01-02", {**ev, "structure_agree": True})   # same day re-run ⇒ row replaced
    rows = [x for x in (tmp_path / "ELLIOTT_VS_DOW.md").read_text().splitlines() if x.startswith("| 20")]
    assert rows == ["| 2030-01-02 | NIFTY | Trend DOWN (impulse) | D3 wxy wave Y | yes | yes |"]


def test_default_chart_spec_trend_degree_only_and_renders():
    """C1: default chart वर फक्त degree labels; ≤ 6 पट्टे; प्रत्येक trend-degree correction ला box (§5.1: लहान window ⇒ जुने फिके,
    text फक्त चालू + आधीच्या correction ला; "pullback" एकदाच); debug PNG वेगळा."""
    from decision3 import charts as CH
    v = DS.build(path(HEAD + WAVE4 + WAVE5), window=60, with_elliott=False)
    sp = DS.view_spec(v)
    allowed = ("correction", "pullback")
    assert sp["tags"] and all(t.startswith(allowed) for t in sp["tags"])
    assert not any(k in " ".join(sp["tags"]) for k in ("HH", "HL", "LH", "LL"))
    assert len(sp["tags"]) <= 2 and sum(t == "pullback" for t in sp["tags"]) <= 1   # §5.1 / §5.2
    full = DS.view_spec(v, full=True)                                      # full (debug): सगळे corrections + चालू leg चे bounces
    ob = v["q15"]["objects"]
    cur = ob["legs"][-1]
    want = len([c for c in ob["corrections"] if c["end_bar"] >= v["i0"]]) + len(
        [b for b in ob["bounces"] if b["bar"] > cur["from"] and b["bar"] >= v["i0"] and b["tag"] in ("pullback", "candidate")])
    assert len(full["tags"]) == want
    assert 0 < len(sp["bands"]) <= DS.MAX_BANDS
    assert {b["state"] for b in sp["bands"]} <= {"fresh", "tested", "broken", "target"}
    corr = [c for c in v["q15"]["objects"]["corrections"] if c["end_bar"] >= v["i0"]]
    assert corr and len(sp["boxes"]) == len(corr)                         # प्रत्येक correction ला box
    assert any(b["label"] == "protected origin" for b in sp["bands"]) and sp["protected"]["price"] == 1252.0
    assert v["q15"]["parent"]["price"] == 1252.0                            # after the A1 completion the trend-degree impulse
    assert not any(b["label"] == "larger-degree origin" for b in sp["bands"])   # starts at the (4) top = protected (one band)
    strip = {s for _, _, s in sp["strip"]["degree-aware"]}
    assert not any(x in " ".join(strip) for x in ("corr ", "broken", "imp "))
    a, b = CH.daily_swings_png(v, "TEST"), CH.daily_swings_debug_png(v, "TEST")
    assert a[:4] == b[:4] == b"\x89PNG" and a != b
    js = DS.to_json(v, "TEST")
    assert js["bands"] and js["objects"]["corrections"] and js["trend_line"].startswith("Trend DOWN")


def test_default_chart_spec_snapshot_on_fixture():
    """C1 snapshot (structure, PNG pixels नाहीत): fixture वर default chart काय काढतो ते स्थिर."""
    v = DS.build(path(HEAD + WAVE4 + WAVE5), window=60, with_elliott=False)
    sp = DS.view_spec(v)
    snap = {"tags": sp["tags"], "bands": [(b["label"], b["price"], b["state"], b["off_window"]) for b in sp["bands"]],
            "names": [b["name"] for b in sp["bands"]], "protected": sp["protected"]["price"], "legs": len(sp["legs"])}
    assert snap == {
        "tags": ["correction · 64% of impulse", "pullback"],              # depth vs the (B) top (Q50); §5.2 pullback एकदाच
        "bands": [("protected origin", 1252.0, "tested", None), ("sharp-fall supply", 1265.67, "broken", None),   # Q55: (2) चा
                  ("window low", 994.0, "tested", None), ("target", 1078.0, "target", None)],   # तुटलेला swing low; Q44: (3) low
        "names": ["protected 1,252 (tested)", "sharp-fall supply 1,266 (broken)", "demand 994 (tested)", "target 1,078"],   # §5.4
        "protected": 1252.0, "legs": 2}
