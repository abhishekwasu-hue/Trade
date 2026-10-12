"""decision3.method.confirm / ltf_choch (Abhi, LEVEL_BOTS_CONFIRMATION a2 + c0 + c1) — V22 ⑥ आणि level bots चं एकच shared function.
प्रत्येक case आरशासह (किंमत p ↦ 2000 − p ⇒ तोच निर्णय, उलट दिशा)."""
import numpy as np
import pandas as pd
import pytest

from decision3 import method as M
from tests import test_level_reaction_c1 as C1
from tests.ltf_fixtures import ltf_rows, split_bars

T0 = C1.DAY0                                                              # सत्र सुरुवात 09:15
T_ARR = T0 + pd.Timedelta(minutes=25)                                     # area मध्ये arrival (09:40 चा 5M bar)
T_END = T0 + pd.Timedelta(minutes=40)                                     # commitment bar (09:50–09:55) चा close


def _ltf(tail, mirror=False, extra=None):
    df = ltf_rows(tail + (extra or []), T_ARR, 1)
    if mirror:
        df = df.assign(open=2000 - df["open"], high=2000 - df["low"], low=2000 - df["high"], close=2000 - df["close"])
    return M.ltf_frame(df, 1, "1M")


def _lvl(mirror):
    return {"lo": 1000.0, "hi": 1010.0} if mirror else {"lo": 990.0, "hi": 1000.0}


@pytest.mark.parametrize("mirror", [False, True])
def test_choch_by_close_after_higher_low(mirror):
    d = M.DOWN if mirror else M.UP
    ch = M.ltf_choch(_ltf(C1.CHOCH, mirror), d, T0, T_ARR, T_END, _lvl(mirror))
    assert ch["done"] and ch["at"] == str(T0 + pd.Timedelta(minutes=38))  # 09:52 ची 1M candle (09:53 ला बंद)
    assert ch["low"] == (1013.0 if mirror else 987.0) and ch["hl"] == (1012.0 if mirror else 988.0)   # LL नंतर CHoCH पर्यंतचा सर्वात खालचा low
    assert ch["lh"] == (997.5 if mirror else 1002.5)
    assert ch["line"] == ("1M CHoCH: lower high 1,012, close below HL 997.5 at 09:53" if mirror
                          else "1M CHoCH: higher low 988, close above LH 1,002.5 at 09:53")


@pytest.mark.parametrize("mirror", [False, True])
def test_wick_beyond_swing_is_not_choch(mirror):
    ch = M.ltf_choch(_ltf(C1.WICK, mirror), M.DOWN if mirror else M.UP, T0, T_ARR, T_END, _lvl(mirror))
    assert not ch["done"] and ch["code"] == M.C_LTF_PENDING and ch["line"].endswith("(wick only)")


@pytest.mark.parametrize("mirror", [False, True])
def test_lower_lows_continuing_is_trending_against(mirror):
    d = M.DOWN if mirror else M.UP
    ch = M.ltf_choch(_ltf(C1.FALL, mirror), d, T0, T_ARR, T_END, _lvl(mirror))
    assert not ch["done"] and ch["code"] == M.C_LTF_AGAINST and "LTF still trending against" in ch["line"]
    assert ("still making higher highs" if mirror else "still making lower lows") in ch["line"]
    at_low = M.ltf_choch(_ltf(C1.VREV, mirror), d, T0, T_ARR, T0 + pd.Timedelta(minutes=36), _lvl(mirror))
    assert at_low["code"] == M.C_LTF_AGAINST                               # 09:50 चा नवा LL हाच शेवटचा बंद bar ⇒ अजून against
    v = M.ltf_choch(_ltf(C1.VREV, mirror), d, T0, T_ARR, T_END, _lvl(mirror))
    assert v["done"] and v["hl"] == (1014.5 if mirror else 985.5)          # V: higher low = LL नंतर CHoCH पर्यंतचा सर्वात खालचा low


def _f5(rows, mirror=False):
    """review 🔴1 repro: 5M LTF bars 09:15 पासून."""
    df = ltf_rows(rows, T0, 5)
    if mirror:
        df = df.assign(open=2000 - df["open"], high=2000 - df["low"], low=2000 - df["high"], close=2000 - df["close"])
    return M.ltf_frame(df, 5, "5M")


STAIR = [(1012, 1013, 1006, 1008), (1008, 1014, 1007, 1009), (1009, 1010, 1000, 1001), (1001, 1002, 995, 997),   # 09:30 LL 995
         (997, 1008, 996, 1007), (1007, 1016, 1006, 1015), (1015, 1026, 1014, 1025), (1025, 1035, 1024, 1034)]   # सगळे lows वर


@pytest.mark.parametrize("mirror", [False, True])
def test_stair_step_v_reversal_is_choch(mirror):
    """review 🔴1: lowest low 995 (09:30) area 990–1000 मध्ये, मग चार वाढते lows, closes 1007 → 1034, lower high 1014 वर ⇒ CHoCH (09:40 चा bar, 09:45 ला बंद)."""
    d = M.DOWN if mirror else M.UP
    L = _f5(STAIR, mirror)
    arr = T0 + pd.Timedelta(minutes=10)
    for cut, done in ((20, False), (25, False), (30, True), (35, True), (40, True), (80, True)):   # cut = setup close (T0 + मिनिटं)
        ch = M.ltf_choch(L, d, T0, arr, T0 + pd.Timedelta(minutes=cut), _lvl(mirror))
        assert ch["done"] is done, (cut, ch)
        if cut == 20:
            assert ch["code"] == M.C_LTF_AGAINST                           # 09:30 चा LL हाच शेवटचा बंद bar
        if cut == 25:
            assert ch["code"] == M.C_LTF_PENDING                           # low थांबला, close 1007 < 1014
        if done:
            assert ch["at"] == str(T0 + pd.Timedelta(minutes=30)) and ch["lh"] == (986.0 if mirror else 1014.0)
            assert ch["hl"] == (1004.0 if mirror else 996.0)


@pytest.mark.parametrize("mirror", [False, True])
def test_gap_down_first_bar_is_the_low(mirror):
    """review 🔴1: gap-down — window चा पहिलाच bar सर्वात खालचा; मग वाढते lows आणि आधीच्या candle च्या high वर close ⇒ CHoCH."""
    rows = [(1030, 1031, 1022, 1024), (1024, 1026, 1018, 1019),            # संदर्भ (pullback)
            (1004, 1006, 996, 999), (999, 1012, 998, 1011), (1011, 1028, 1010, 1027)]   # 09:25 gap-down LL 996
    d = M.DOWN if mirror else M.UP
    ch = M.ltf_choch(_f5(rows, mirror), d, T0, T0 + pd.Timedelta(minutes=10), T0 + pd.Timedelta(minutes=40), _lvl(mirror))
    assert ch["done"] and ch["lh"] == (2000 - 1026 if mirror else 1026) and ch["at"] == str(T0 + pd.Timedelta(minutes=25))


@pytest.mark.parametrize("mirror", [False, True])
def test_equal_low_is_double_bottom_not_against(mirror):
    """review ⚪: LL नंतर समान low (double bottom) ⇒ trending against नाही; मग LH वर close ⇒ CHoCH."""
    rows = [(1012, 1014, 1006, 1008), (1008, 1009, 995, 996), (996, 1003, 995.5, 1002), (1002, 1003, 995, 997),
            (997, 1016, 996.5, 1015)]
    d = M.DOWN if mirror else M.UP
    L = _f5(rows, mirror)
    pend = M.ltf_choch(L, d, T0, T0 + pd.Timedelta(minutes=5), T0 + pd.Timedelta(minutes=20), _lvl(mirror))
    assert pend["code"] == M.C_LTF_PENDING                                 # समान low शेवटचा bar असला तरी against नाही
    ch = M.ltf_choch(L, d, T0, T0 + pd.Timedelta(minutes=5), T0 + pd.Timedelta(minutes=25), _lvl(mirror))
    assert ch["done"] and ("double top" if mirror else "double bottom") in ch["line"]


@pytest.mark.parametrize("mirror", [False, True])
def test_sweep_of_low_closing_back_inside_then_close_above_lh(mirror):
    """higher low नाही, पण lower-low candle ने area ची far edge (990) sweep करून close परत आत ⇒ मग LH वर close = CHoCH."""
    tail = C1.BASE[:6] + [(994.5, 995, 986, 991.5),                            # sweep: low 986 < 990, close 991.5 परत आत
                          (991.5, 997, 991, 996.5), (996.5, 1003.5, 996, 1003)]
    ch = M.ltf_choch(_ltf(tail, mirror), M.DOWN if mirror else M.UP, T0, T_ARR, T_ARR + pd.Timedelta(minutes=9), _lvl(mirror))
    assert ch["done"] and ch["sweep"] and "closed back inside" in ch["line"]
    no_edge = M.ltf_choch(_ltf(tail, mirror), M.DOWN if mirror else M.UP, T0, T_ARR, T_ARR + pd.Timedelta(minutes=9), None)
    assert no_edge["done"] and not no_edge["sweep"]                        # area नसताना sweep नाही (lower lows थांबले ⇒ तरीही CHoCH)


@pytest.mark.parametrize("mirror", [False, True])
def test_no_lookahead_bars_after_setup_close_ignored(mirror):
    d = M.DOWN if mirror else M.UP
    later = [(1008, 1008.5, 960, 961)] * 3                                 # setup close नंतर नवा lower low
    a = M.ltf_choch(_ltf(C1.CHOCH, mirror), d, T0, T_ARR, T_END, _lvl(mirror))
    b = M.ltf_choch(_ltf(C1.CHOCH, mirror, later), d, T0, T_ARR, T_END, _lvl(mirror))
    assert a == b and a["done"]
    early = M.ltf_choch(_ltf(C1.CHOCH, mirror, later), d, T0, T_ARR, T0 + pd.Timedelta(minutes=37), _lvl(mirror))
    assert not early["done"]                                               # 09:52 ची CHoCH candle अजून बंद नाही ⇒ नाही


def test_missing_ltf_is_reported_never_skipped():
    assert M.ltf_choch(None, M.UP, T0, T_ARR, T_END)["code"] == M.C_LTF_MISSING
    assert M.ltf_choch(_ltf(C1.CHOCH), M.UP, T0, T_END, T_END)["code"] == M.C_LTF_MISSING   # window मध्ये बंद LTF bar नाही


def _A(tail, vol_commit=200.0, vol=True, mirror=False):
    bars, k, m1, area, ctx, others = C1._case(tail, vol_commit, mirror, vol)
    A = {c: bars[c].to_numpy(float) for c in ("open", "high", "low", "close")}
    A["volume"] = bars["volume"].to_numpy(float) if vol else None
    lvl = {"lo": area[0], "hi": area[1]}
    return A, len(bars) - 3, len(bars) - 1, lvl, M.ltf_frame(m1, 1, "1M")


@pytest.mark.parametrize("mirror", [False, True])
def test_confirm_requires_all_three_and_reports_each_missing_piece(mirror):
    d = M.DOWN if mirror else M.UP
    s = M.S3.DEFAULTS
    A, arm, t, lvl, L = _A(C1.CHOCH, mirror=mirror)
    times = (T0, T_ARR, T_END)
    ok = M.confirm(A, arm, t, d, lvl, s, ltf=L, ltf_times=times)
    assert ok["ok"] and ok["c0"] and ok["c1"] and ok["wait"] is None
    assert ok["lines"][0].startswith("inside supply:" if mirror else "inside demand:")
    assert "body 4.2× window avg · volume 2.0× window avg" in ok["lines"][1] and ok["lines"][2].startswith("1M CHoCH:")
    miss = M.confirm(A, arm, t, d, lvl, s, ltf=None, ltf_times=times)
    assert not miss["ok"] and miss["wait"] == M.C_LTF_MISSING and miss["c0"]
    assert M.confirm(A, arm, t, d, lvl, s, ltf=_ltf(C1.FALL, mirror), ltf_times=times)["wait"] == M.C_LTF_AGAINST
    A2, arm, t, lvl, L2 = _A(C1.VREV, mirror=mirror)
    assert M.confirm(A2, arm, t, d, lvl, s, ltf=L2, ltf_times=times)["ok"]   # V-reversal ⇒ CHoCH (review 🔴1)
    calls = []
    lazy = M.confirm(A, arm - 1, arm, d, lvl, s, ltf=lambda: calls.append(1) or L, ltf_times=times)
    assert not lazy["c0"] and not calls                                    # commitment नाही ⇒ LTF बोलावत नाही
    A3, arm, t, lvl, L3 = _A(C1.CHOCH, vol_commit=80.0, mirror=mirror)
    lowv = M.confirm(A3, arm, t, d, lvl, s, ltf=L3, ltf_times=times)
    assert not lowv["ok"] and lowv["wait"] == "low_volume" and lowv["c1"]  # CHoCH आहे, पण कमी volume ⇒ या candle वर नाही
    A4, arm, t, lvl, L4 = _A(C1.CHOCH, vol=False, mirror=mirror)
    na = M.confirm(A4, arm, t, d, lvl, s, ltf=L4, ltf_times=times)
    assert na["ok"] and na["commit"]["grade"] == "B" and "volume: NA (grade cap B)" in na["lines"][1]


# ------------------------------------------------------------------------------------------------ V22 (⑥ = confirm)
def _v22_setup_bar():
    from decision3 import engine as E3
    from tests.test_decision3_method import _abc_m15
    m15 = _abc_m15()
    s = {"maturity_sigma_d": -1e6, "commit_dom_mult": 0.0}                 # fixture ला dominant candle नाही ⇒ c0 बंद; c1 default (चालू)
    return m15, s, E3


def test_v22_without_ltf_fails_closed_with_reason():
    m15, s, E3 = _v22_setup_bar()
    V = E3.V22(m15, s=s)
    assert V.ltf is None
    rows = V.run()
    assert not [r for r in rows if r["decision"] == "setup"]
    hit = [r for r in rows if "LTF data missing" in str(r["checklist"]["⑥"][1])]
    assert hit and all(r["checklist"]["⑥"][0] is False for r in hit)
    off = [r for r in E3.V22(m15, s={**s, "ltf_choch": False}).run() if r["decision"] == "setup"]
    assert {r["bar"] for r in off} <= {r["bar"] for r in hit}              # c1 बंद (what-if) चे setups = इथे फक्त LTF ने अडलेले


def test_v22_ltf_from_same_1m_source_and_no_lookahead():
    m15, s, E3 = _v22_setup_bar()
    from swings2 import engine as SE
    res = SE.build(m15)
    m1 = split_bars(m15, 15, 15)
    V = E3.V22(m15, df1m=m1, s=s, res=res)                                 # 1m ⇒ 5M (market_state.core.frame)
    assert V.ltf is not None and V.ltf["minutes"] == 5 and V.ltf["label"] == "5M"
    rows = V.run()
    tested = [r for r in rows if r["checklist"]["⑥"][1] and "5M" in str(r["checklist"]["⑥"][1])]
    assert tested                                                          # test vacuous नाही: c1 खरंच वाचला
    for r in tested[:6]:
        t = r["bar"]
        cut = m1[pd.to_datetime(m1["timestamp"]) + pd.Timedelta(minutes=1) <= pd.Timestamp(V.bar_end[t])]
        Vt = E3.V22(m15, df1m=cut, s=s, res=res)                           # setup bar च्या close नंतरचा 1m नाही ⇒ तोच ⑥
        assert Vt.decide(t)["checklist"]["⑥"] == r["checklist"]["⑥"]


def test_v22_futures_volume_feeds_c0_and_power_shift_e():
    m15, s, E3 = _v22_setup_bar()
    from swings2 import engine as SE
    res = SE.build(m15)
    ts5 = pd.date_range(m15["timestamp"].min(), m15["bar_end"].max(), freq="5min")
    fut = pd.DataFrame({"timestamp": ts5, "volume": np.arange(len(ts5)) % 7 * 10.0 + 100.0, "contract": "FUT",
                        "expiry": pd.Timestamp(m15["timestamp"].max()).normalize() + pd.Timedelta(days=30)})
    V = E3.V22(m15, s={**s, "ltf_choch": False}, res=res, futures=fut)
    assert np.isfinite(V.levels.A["volume"]).sum() > 0
    rows = V.run()
    assert any((r.get("commit") or {}).get("vol_mult") is not None for r in rows)            # c0 volume वाचला
    V0 = E3.V22(m15, s={**s, "ltf_choch": False}, res=res)
    assert all((r.get("commit") or {}).get("vol_mult") is None for r in V0.run())           # volume नाही ⇒ NA
    ok, n, items = M.power_shift(V.levels.A, rows[-1]["bar"], M.UP, None, V.s)
    assert items["e_handover_volume"] is not None                         # ④ (e): volume असेल तर handover-volume वाचन (NA नाही)
