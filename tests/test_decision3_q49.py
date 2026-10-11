"""Q49 (Abhi: TRADE_SESSION_Q44_Q49_Q55_CHART_FIX §2) — the 5-wave first leg of a deep counter-move is wave A by default (the
trend stays with the parent impulse). It becomes wave 1 only on (a) a close beyond the origin of the impulse it corrects (Abhi
via lead: the engine's impulse-leg origin — or the start of the complete 5-wave whose wave 5 that leg is), or (b) the
counter-move's own same-degree 5-wave structure ("1" in 5, a 3-wave "2", "3" beyond the end of "1" itself unfolding in 5). Chart
label "A", debug "alt: 1", no wave number on Telegram (Q46). No ratios / depth; every case in both directions."""
import numpy as np
import pytest

from tests import elliott_fixtures as F
from decision3 import daily as DD
from decision3 import daily_legs as DL
from decision3 import daily_swings as DS

MIRRORS = [pytest.param(False, id="down"), pytest.param(True, id="up")]


def _px(v, mirror, wick=0.0):
    """fixture किंमत ⇒ chart किंमत (DOWN: टोकाचा high = v + wick; UP आरसा: low = MIRROR − v − wick)."""
    return (F.MIRROR - v - wick) if mirror else (v + wick)


def _impulse_end(d, mirror):
    ext = d["high"].to_numpy() if mirror else d["low"].to_numpy()
    return int(np.argmin(np.abs(ext - _px(F.E, mirror, -F.WICK))))


@pytest.mark.parametrize("mirror", MIRRORS)
def test_deep_zigzag_with_5wave_a_stays_a_correction_labelled_A(mirror):
    """very_deep_holds_origin: A = 5-wave, B, C = 5-wave beyond A, parent holds ⇒ trend never flips; the A leg is labelled "A"
    (alt "1") while the A1 correction runs — depth alone never decides."""
    d, _ = F.correction_fixture("very_deep_holds_origin", mirror)
    st = DD.fold(d)
    eb = _impulse_end(d, mirror)
    want = "UP" if mirror else "DOWN"
    assert all(x.trend == want for x in st[eb:])
    lab = [x for x in st if x.wave_a is not None]
    assert lab and all(x.counter == "correction" and x.alt == "1" and x.trend == want for x in lab)
    a_end = _px(F.E + 0.55 * F.I, mirror, F.WICK)
    assert any(abs(x.wave_a.price - a_end) < 1e-9 for x in lab)
    assert any("Q49" in (x.why or "") and "wave A" in x.why for x in st)


@pytest.mark.parametrize("mirror", MIRRORS)
def test_negative_control_real_one_two_three_flips_under_b(mirror):
    """Same "1"-"2"-"3" as the deep zigzag, then "4" (holds the end of "1") and "5": the counter-move completes its own same-degree
    5-wave ⇒ wave 1 ⇒ flip — with no close beyond the parent origin (so (b), not (a)). Until then it is labelled "A"."""
    d, info = F.q49_complete_five(mirror)
    st = DD.fold(d)
    old, new = ("UP", "DOWN") if mirror else ("DOWN", "UP")
    eb = _impulse_end(d, mirror)
    fl = next(i for i in range(eb, len(st)) if st[i].trend == new)
    assert all(x.trend == old for x in st[eb:fl]) and st[-1].trend == new
    C = d["close"].to_numpy()[eb:fl + 1]
    par = _px(info["parent"], mirror)
    assert not ((C < par) if mirror else (C > par)).any()                  # (a) नाही
    assert any(x.wave_a is not None and x.alt == "1" for x in st[eb:fl])   # (b) होईपर्यंत wave A
    a_end = _px(info["a_end"], mirror, F.WICK)
    assert any(x.wave_a is not None and abs(x.wave_a.price - a_end) < 1e-9 for x in st[eb:fl])


@pytest.mark.parametrize("mirror", MIRRORS)
def test_abc_fix_shape_5wave_close_beyond_impulse_origin_flips_under_a(mirror):
    """Q49 (a) = ABC_FIX rule 1 (Abhi: BANKNIFTY Feb top ⇒ Mar low is a DOWN impulse): the 5-wave counter-move is "A" only until it
    closes beyond the origin of the impulse it corrects (here the (3) leg — the trend so far is no complete 5-wave); that close flips
    the trend while the trend start (A1 parent) still holds."""
    d, info = F.q49_beyond_impulse_origin(mirror)
    st = DD.fold(d)
    old, new = ("UP", "DOWN") if mirror else ("DOWN", "UP")
    eb = _impulse_end(d, mirror)
    fl = next(i for i in range(eb, len(st)) if st[i].trend == new)
    assert all(x.trend == old for x in st[eb:fl]) and st[-1].trend == new
    C = d["close"].to_numpy()
    org, par = _px(info["origin"], mirror, F.WICK), _px(info["parent"], mirror)
    assert ((C[fl] < org) if mirror else (C[fl] > org))                    # flip = impulse origin पलीकडे close
    assert not ((C[eb:fl + 1] < par) if mirror else (C[eb:fl + 1] > par)).any()   # trend सुरुवात (A1 parent) टिकलेली
    top = _px(info["top"], mirror, F.WICK)
    ext = d["high"].to_numpy() if not mirror else d["low"].to_numpy()
    assert ((ext[eb:fl + 1].max() <= top) if not mirror else (ext[eb:fl + 1].min() >= top))   # 5-wave counter-move च्या आतच
    assert any(x.wave_a is not None for x in st[eb:fl])                    # त्याआधी (origin पलीकडे close नाही) ⇒ "A"


@pytest.mark.parametrize("mirror", MIRRORS)
def test_complete_five_does_not_flip_at_the_end_of_3(mirror):
    """Review 🟡3: "1"-"2"-"3" alone (= the deep zigzag's A-B-C) is no flip — the trend holds through the end of "3" and the whole
    "4"; the flip comes only while the counter-move's own "5" runs beyond the end of "3"."""
    d, info = F.q49_complete_five(mirror)
    st = DD.fold(d)
    old, new = ("UP", "DOWN") if mirror else ("DOWN", "UP")
    eb = _impulse_end(d, mirror)
    H, L = d["high"].to_numpy(), d["low"].to_numpy()
    top, bot = (L, H) if mirror else (H, L)
    b3 = eb + int(np.argmin(np.abs(top[eb:] - _px(info["end3"], mirror, F.WICK))))   # "3" चा शेवट
    b4 = b3 + int(np.argmin(np.abs(bot[b3:] - _px(info["end4"], mirror, -F.WICK))))  # "4" चा शेवट
    fl = next(i for i in range(eb, len(st)) if st[i].trend == new)
    assert st[b3].trend == old and st[b3].wave_a is not None and st[b3].alt == "1"
    assert all(x.trend == old for x in st[b3:b4 + 1]) and fl > b4
    end3 = _px(info["end3"], mirror, F.WICK)
    assert ((top[b4:fl + 1].min() < end3) if mirror else (top[b4:fl + 1].max() > end3))   # "5" "3" पलीकडे


def _q49_fixtures():
    out = [F.correction_fixture(k, m)[0] for k in F.CORRECTIONS for m in (False, True)]
    out += [fx(m)[0] for fx in (F.q49_complete_five, F.q49_beyond_impulse_origin, F.q49_lower_degree_a) for m in (False, True)]
    return out


def test_q49_why_never_claims_a_held_origin_the_close_broke():
    """Review 🟡4: the Q49 text depends on the path — on the Q22 lower-degree path the impulse origin may already be broken, so the
    text names only the parent; any "origin X close ने टिकला" claim must be true on that bar's close. The lower-degree fixture
    (close beyond the triangle-e origin) must take the Q22 wording."""
    import re
    seen_q22 = 0
    for d in _q49_fixtures():
        C = d["close"].to_numpy()
        for i, x in enumerate(DD.fold(d)):
            w = x.why or ""
            if "Q49" not in w:
                continue
            m = re.search(r"origin ([\d,\.]+) close ने टिकला", w)
            if m:
                px = float(m.group(1).replace(",", ""))
                assert not ((C[i] > px) if x.trend == "DOWN" else (C[i] < px)), (i, w)   # टिकला ⇒ close पलीकडे नाही
            if "(Q22)" in w:
                seen_q22 += 1
                assert "टिकला" not in w.split("(alt: 1)")[0]
    assert seen_q22 > 0
    for mirror in (False, True):                                           # lower-degree A: close already beyond the e origin
        d, info = F.q49_lower_degree_a(mirror)
        C = d["close"].to_numpy()
        e = _px(info["e"], mirror, F.WICK)
        hits = [(i, x.why) for i, x in enumerate(DD.fold(d)) if "Q49" in (x.why or "")]
        assert hits and all("(Q22)" in w for _, w in hits)
        assert any(((C[i] < e) if mirror else (C[i] > e)) for i, _ in hits)


def _subdivided_impulse():
    return F.build(0.0, [(30.0, "m5"), (18.0, "c3"), (75.0, "m5"), (60.0, "c3"), (100.0, "m5")])


@pytest.mark.parametrize("sign", [pytest.param(1, id="up"), pytest.param(-1, id="down")])
def test_unfolded_123_reader(sign):
    """(b) reader on raw waypoints: a 5-wave whose "3" is a single straight leg is not (b) (stays A); a fully subdivided 5-3-5-3-5
    is; a 5-3-5 zigzag (A-B-C) is not — the counter-move must itself read as the 5-wave."""
    f = lambda xs: [sign * x for x in [0.0] + list(xs)]                  # noqa: E731
    simple = f([30.0, 18.0, 75.0, 60.0, 100.0])
    assert DL.read_counter(simple)["family"] == "impulse" and not DL.unfolded_123(simple)
    full = f(_subdivided_impulse())
    assert DL.read_counter(full)["family"] == "impulse" and DL.unfolded_123(full)
    zz = f(F.build(0.0, F.zz(55.0, 30.0, 88.0)))
    assert DL.read_counter(zz)["family"] == "zigzag" and not DL.unfolded_123(zz)


def _a_bar(st):
    return next(i for i, x in enumerate(st) if x.wave_a is not None)


@pytest.mark.parametrize("mirror", MIRRORS)
def test_chart_label_A_debug_alt_1_and_no_wave_number_on_telegram(mirror):
    """While wave A is open: chart spec carries "A", debug JSON carries alt "1"; trader text (trend line, caption, ① Telegram
    reading) carries no wave number (Q46)."""
    from tests.test_decision3_daily_q15 import _V_with
    d, _ = F.correction_fixture("very_deep_holds_origin", mirror)
    st = DD.fold(d)
    k = _a_bar(st) + 3
    dk = d.iloc[:k + 1].reset_index(drop=True)
    v = DS.build(dk, window=len(dk), with_elliott=False)
    q = v["q15"]
    assert q["wave_a"]["label"] == "A" and q["alt"] == "1" and q["counter"] == "correction"
    assert [w["label"] for w in DS.view_spec(v)["waves"]] == ["A"]
    js = DS.to_json(v, "TEST")
    assert js["wave_a"]["label"] == "A" and js["wave_a"]["alt"] == "1"
    text = DS.trend_line(q) + "\n" + DS.caption(v, "TEST")
    V = _V_with(DD.fold(dk), [DD.DState(0, st[0].day, st[0].known_at, "UNKNOWN")])
    ok, why, s1, ctx = V.step1(0)
    for t in (text, why):
        assert "alt" not in t and "wave A" not in t and "(1)" not in t and " A " not in t, t


@pytest.mark.parametrize("mirror", MIRRORS)
def test_wave_a_and_flip_have_no_lookahead(mirror):
    """Truncation invariance: wave A / alt / trend at bar k are the same with or without later bars (conditions use pivots
    confirmed ≤ k)."""
    d, _ = F.q49_complete_five(mirror)
    full = DD.fold(d)
    key = lambda x: (x.trend, x.phase, x.counter, getattr(x.wave_a, "price", None), x.alt,   # noqa: E731
                     getattr(x.protected, "price", None))
    for k in range(130, len(d), 6):
        part = DD.fold(d.iloc[:k].reset_index(drop=True))
        assert [key(x) for x in part] == [key(x) for x in full[:k]], k


@pytest.mark.parametrize("mirror", MIRRORS)
def test_complete_impulse_start_matches_rule4_origin_by_bar(mirror):
    """Review 🟡2: after a Rule-4 continuation the leg origin is the correction's END (a lower-degree pivot below its extreme, not in
    the trend-degree seq). The (a) extension still finds the complete 5-wave start: wave 5 is matched by bar inside the correction
    window, not by price (a price match on the extreme would miss it)."""
    import pandas as pd

    def pv(kind, px, bar):
        if mirror:
            kind, px = ("L" if kind == "H" else "H"), F.MIRROR - px
        return DD.DPivot(kind, float(px), bar, pd.Timestamp("2030-01-01"), bar + 2, pd.Timestamp("2030-01-01"))
    P = pv("H", 1282.0, 0)
    seq = [P, pv("L", 1210.0, 10), pv("H", 1240.0, 20), pv("L", 1090.0, 40), pv("H", 1170.0, 50)]   # (4) extreme = 1170
    low = seq + [pv("L", 1120.0, 55), pv("H", 1150.0, 60)]                 # Rule-4 origin = (4) चा शेवट 1150 (bar 60, फक्त low मध्ये)
    low.sort(key=lambda p: p.bar)
    end = pv("L", 998.0, 80)
    origin = low[-1]
    assert DD.complete_impulse_start([P], seq, low, end, 40, origin.bar, 100) is P
    assert DD.complete_impulse_start([P], seq, low, end, 51, origin.bar, 100) is None   # wave 5 (4) च्या आधी सुरू ⇒ नाही
    pr, _ = DL.leg_points(seq, P.bar, P.price, end.bar, end.price, 100)
    assert DL._motive_segs(pr)[4][0] != origin.price                       # जुनी किंमत-जुळवणी इथे चुकली असती
