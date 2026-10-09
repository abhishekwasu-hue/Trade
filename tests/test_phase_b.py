"""टप्पा B (Abhi G-MAP1 निर्णय, 2026-10-09) — reading layer, decisions, no-lookahead."""
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from elliott import breaks as BR
from elliott import settings as ES


def _frame(closes, hl=0.5):
    ts = pd.date_range("2026-01-05 09:15", periods=len(closes), freq="15min")
    c = np.asarray(closes, float)
    return pd.DataFrame({"timestamp": ts, "bar_end": ts + pd.Timedelta(minutes=15), "open": c, "high": c + hl, "low": c - hl, "close": c})


def test_decision8_counts_rules_ignore_3close_structural_breaks_use_it():
    """निर्णय 8: रचनेचा break (breaks.py) 3 closes पलीकडे (buffer आत) ⇒ confirm; Elliott count rules (CountEngine cache) ला 3-close नाही."""
    from elliott.counts import CountEngine
    s = {**ES.DEFAULTS, "break_accept_closes": 3, "break_buffer_mr": 5.0}           # buffer मोठा ⇒ फक्त time acceptance ने break
    fr = _frame([100.0] * 25 + [99.8, 99.7, 99.6, 99.5])                             # level 100 खाली सलग 4 closes, buffer आत
    mr = np.full(len(fr), 1.0)
    assert BR.first_real_break(fr, 25, 100.0, "below", s, mr=mr) == 27                # रचना: तिसऱ्या close वर
    assert BR.first_real_break(fr, 25, 100.0, "below", {**s, "break_accept_closes": 0}, mr=mr) is None
    md = {0: {"tf": "15m", "frame": fr, "confirmed": [], "tentative": None}}
    eng = CountEngine(md, s)
    assert eng.cache[0].s["break_accept_closes"] == 0                                 # count rules: भावावरूनच, 3-close नाही
    assert s["break_accept_closes"] == 3                                              # caller चे settings बदलले नाहीत


# ------------------------------------------------------------------------------------------------- reading layer helpers
from simple_core import count_source as CSRC                                   # noqa: E402
from simple_core import engine as EN                                           # noqa: E402
from simple_core import execution as EX                                        # noqa: E402
from simple_core import reading as RD                                          # noqa: E402
from simple_core import settings as SS                                         # noqa: E402


def _bars(hl):
    """[(high, low)] ⇒ 15M frame (close = mid)."""
    ts = pd.date_range("2026-01-05 09:15", periods=len(hl), freq="15min")
    h = np.array([x[0] for x in hl], float)
    lo = np.array([x[1] for x in hl], float)
    c = (h + lo) / 2
    return pd.DataFrame({"timestamp": ts, "bar_end": ts + pd.Timedelta(minutes=15), "open": c, "high": h, "low": lo, "close": c})


def _pv(idx, price, kind, conf=None):
    return {"idx": idx, "price": price, "kind": kind, "conf": idx + 1 if conf is None else conf, "label": kind,
            "ts": pd.Timestamp("2026-01-05 09:15") + pd.Timedelta(minutes=15 * idx)}


def test_trade_impulse_is_the_one_before_the_traded_correction():
    """निर्णय 9: S = area च्या पलीकडचा सगळ्यात अलीकडचा start pivot; E = S नंतर pause आधीपर्यंतचं टोक (commitment चा नवा low नाही)."""
    hl = [(130, 128)] * 3 + [(120, 106)] * 2 + [(112, 100)] + [(114, 105)] * 2 + [(112, 104)] * 4 + [(118, 110)] * 3 + [(116, 97)]   # शेवटचा = commitment, नवा low
    fr = _bars(hl)
    piv = [_pv(1, 130.0, "H"), _pv(5, 100.0, "L"), _pv(13, 118.0, "H", conf=15)]   # 13 चा H अजून confirm नाही (k = 15)
    area = {"low": 114.0, "high": 118.0}
    imp, why = RD.trade_impulse(fr, piv, -1, 15, area, 0.5, lim=14)
    assert imp and imp["start"] == 130.0 and imp["end"] == 100.0                  # 97 (commitment) origin नाही
    imp2, why2 = RD.trade_impulse(fr, [_pv(1, 130.0, "H")], -1, 15, area, 0.5, lim=14)
    assert imp2 is None and "IMPULSE_NA" in why2                                  # origin confirmed pivot नाही


def test_correction_legs_gray2_cases():
    imp = {"dir": -1, "start": 130.0, "end": 100.0, "end_idx": 0, "start_idx": 0}
    fr = _bars([(101, 100)] + [(115, 110)] * 10)
    a_only = RD.correction_legs(fr, [], imp, 10)
    assert not a_only["complete"] and "फक्त A" in a_only["why"]
    abc = RD.correction_legs(fr, [_pv(3, 112.0, "H"), _pv(6, 105.0, "L")], imp, 10)          # C (115) ≥ A (112)
    assert abc["complete"]
    trunc = RD.correction_legs(_bars([(101, 100)] + [(110, 105)] * 10), [_pv(3, 112.0, "H"), _pv(6, 105.0, "L")], imp, 10)
    assert not trunc["complete"] and "truncated" in trunc["why"]
    five = RD.correction_legs(_bars([(101, 100)] + [(130, 120)] * 12),                    # वाढती टोकं, wave 4 (116) > wave 1 (112)
                              [_pv(2, 112.0, "H"), _pv(4, 108.0, "L"), _pv(6, 122.0, "H"), _pv(8, 116.0, "L")], imp, 12)
    assert not five["complete"] and "5 waves" in five["why"]
    tri = RD.correction_legs(_bars([(101, 100)] + [(111, 109)] * 12),
                             [_pv(2, 120.0, "H"), _pv(4, 104.0, "L"), _pv(6, 116.0, "H"), _pv(8, 107.0, "L")], imp, 12)
    assert tri["complete"] and "triangle" in tri["why"]
    flag = RD.correction_legs(fr, [], imp, 10, area_type="flag channel")
    assert flag["complete"]


def test_origin_beyond_real_break_is_s4_reclaim_is_s7_never_s3():
    imp = {"dir": -1, "start": 120.0, "end": 100.0, "end_idx": 2, "start_idx": 0}
    base = [(121, 119), (110, 104), (101, 100)] + [(110, 105)] * 25
    s4 = _bars(base + [(124, 122), (125, 123), (126, 124), (127, 125)])               # S पलीकडे सलग closes ⇒ real break
    assert RD.origin_state(s4, imp, len(s4) - 1) == "S4"
    s7 = _bars(base + [(121.5, 118.0), (119, 114)])                                 # wick पलीकडे, close आत
    assert RD.origin_state(s7, imp, len(s7) - 1) == "S7"
    assert RD.situation({"S4": True, "S3": True})[0] == "S4" and RD.situation({"S7": True})[0] == "S7"


def test_s3_trigger_1h_lh_real_break_and_no_pivot(monkeypatch):
    from market_state import core as MC
    h1 = _bars([(130, 128)] + [(129 - i, 125 - i) for i in range(10)] + [(118, 116)] * 3 + [(112, 100)] + [(108, 104)] * 3
               + [(119.6, 119.2)] * 6)                                              # शेवटी आतल्या LH (119) च्या वर सलग closes
    t0 = pd.Timestamp(h1["timestamp"].iloc[0])
    imp = {"dir": -1, "start": 130.0, "end": 100.0, "start_ts": t0, "end_ts": pd.Timestamp(h1["timestamp"].iloc[14])}
    monkeypatch.setattr(MC, "pivots", lambda f, m, tf="1h": [_pv(0, 130.0, "H"), _pv(8, 112.0, "L"), _pv(11, 119.0, "H"),
                                                              _pv(14, 100.0, "L")])
    r = RD.s3_trigger(h1.assign(timestamp=h1["timestamp"]), None, imp, h1["bar_end"].iloc[-1])
    assert r["s3"] and r["pivot"] == 119.0
    r2 = RD.s3_trigger(h1.iloc[:19], None, imp, h1["bar_end"].iloc[18])               # एक close (break अजून confirm नाही)
    assert not r2["s3"]
    monkeypatch.setattr(MC, "pivots", lambda f, m, tf="1h": [_pv(0, 130.0, "H"), _pv(14, 100.0, "L")])
    assert RD.s3_trigger(h1, None, imp, h1["bar_end"].iloc[-1])["code"] == "S3_NO_1H_PIVOT"


def test_commit_vs_impulse_definition_and_na():
    fr = _bars([(110, 100), (108, 100), (106, 100), (104, 100)])                    # impulse bars ranges 10, 8, 6, 4 ⇒ median 7
    imp = {"start_idx": 0, "end_idx": 3}
    assert RD.commit_vs_impulse(fr, imp, {"high": 107.0, "low": 100.0}) == 1.0
    assert RD.commit_vs_impulse(fr, None, {"high": 1.0, "low": 0.0}) is None


def test_gray_policy_default_block():
    assert RD.get_gray_policy(pd.Timestamp("2026-10-09"))["policy"] == "block"


# ------------------------------------------------------------------------------------------------- apply_reading (decisions)
def _sig(setup=None, side=-1, bar="2026-01-05 11:00"):
    return {"side": side, "trigger_price": 105.0, "bar_start": bar, "area": {"id": "S1", "type": "flip", "low": 108.0, "high": 110.0},
            "commitment": {"high": 110.0, "low": 104.0, "bars": 1}, "setup": setup, "pause_from": None, "context_story": "",
            "ref_levels": {"structural_invalidation": 110.0, "next_opposite_area": None, "impulse_end": None}}


def _apply(monkeypatch, rd, cnt=None, pol=None, ctx_trend=-1, setup=None, s=None, bar="2026-01-05 11:00", side=-1):
    monkeypatch.setattr(RD, "read_signal", lambda *a, **k: dict(rd))
    monkeypatch.setattr(CSRC, "read", lambda *a, **k: dict(cnt or {"setup": None, "parent_dir": 0, "S11": False}))
    if pol is not None:
        monkeypatch.setattr(RD, "get_gray_policy", lambda d=None: pol)
    tr = EN.Tracker()
    sg = _sig(setup, side=side, bar=bar)
    tr.add(side, sg["area"], sg["bar_start"])
    r = EN.apply_reading({"signal": sg, "why": "ENTRY SIGNAL"}, _bars([(110, 100)] * 5), None, None, sg["bar_start"], 1.0,
                         SS.engine_settings(s), [], {"trend": ctx_trend}, {}, tracker=tr)
    return r, tr


IMP = {"start": 130.0, "end": 100.0, "end_ts": "2026-01-05 10:00", "start_ts": "2026-01-05 09:15"}


def test_gray2_block_default_and_reduce_marks_gray(monkeypatch):
    rd = {"impulse": IMP, "gray": "Gray-2", "gray_why": "Gray-2: फक्त A", "S": "S1", "legs": {"tops": [110.0]}}
    r, tr = _apply(monkeypatch, rd)
    assert r["signal"] is None and r["gray_candidate"] and "Gray-2" in r["why"] and not tr.used      # block ⇒ setup मोकळा
    r2, _ = _apply(monkeypatch, rd, pol={"policy": "reduce", "dir": None})
    assert r2["signal"]["gray"] == "Gray-2"


def test_gray1_reduce_needs_direction(monkeypatch):
    """12 Aug सारखा: Gray-1 + reduce, दिशा नाही ⇒ signal नाही; दिशेसह ⇒ त्याच दिशेने GRAY."""
    rd = {"impulse": IMP, "gray": "Gray-1", "gray_why": "S3", "S": "S3", "legs": {"tops": []}}
    r, _ = _apply(monkeypatch, rd, pol={"policy": "reduce", "dir": None})
    assert r["signal"] is None
    r2, _ = _apply(monkeypatch, rd, pol={"policy": "reduce", "dir": -1})
    assert r2["signal"]["gray"] == "Gray-1"
    r3, _ = _apply(monkeypatch, rd, pol={"policy": "reduce", "dir": 1})
    assert r3["signal"] is None


def test_parent_preferred_count_unknown_blocks_even_with_reduce(monkeypatch):
    rd = {"impulse": IMP, "gray": None, "gray_why": "", "S": "S1", "legs": {"tops": []}}
    r, _ = _apply(monkeypatch, rd, cnt={"setup": None, "parent_dir": 0}, pol={"policy": "reduce", "dir": -1},
                  s={"parent_source": "preferred_count"})
    assert r["signal"] is None and "PARENT_UNKNOWN" in r["why"] and r.get("blocked_candidate")
    ok, _ = _apply(monkeypatch, rd, cnt={"setup": None, "parent_dir": -1}, s={"parent_source": "preferred_count"})
    assert ok["signal"] is not None
    conflict, _ = _apply(monkeypatch, rd, cnt={"setup": None, "parent_dir": 1})               # market_state mode: फक्त नोंद
    assert conflict["signal"] is not None and conflict["reading"]["PARENT_CONFLICT"]


def test_single_count_source_sets_g9_and_target_degree(monkeypatch):
    rd = {"impulse": IMP, "gray": None, "gray_why": "", "S": "S1", "legs": {"tops": [112.0]}}
    pref = {"pattern": "impulse", "wave": "4", "points": [("t0", 140.0), ("t1", 120.0), ("t2", 128.0), ("t3", 100.0)]}
    r, _ = _apply(monkeypatch, rd, cnt={"setup": "G9", "parent_dir": -1, "preferred": pref})
    sg = r["signal"]
    assert sg["setup"] == "G9" and sg["ref_levels"]["impulse_end"] == 100.0
    assert sg["ref_levels"]["wave1_origin"] == 140.0 and sg["ref_levels"]["wave5_projection"] == 112.0 - 20.0
    r2, _ = _apply(monkeypatch, rd, cnt={"setup": None, "parent_dir": -1})
    assert r2["signal"]["setup"] is None and r2["signal"]["ref_levels"]["wave1_origin"] is None   # waves.py चा G9 नाही


def test_exceptions_not_killed_by_parent_or_gray(monkeypatch):
    rd = {"impulse": IMP, "gray": "Gray-1", "gray_why": "S3", "S": "S3", "legs": {"tops": []}}
    for st in ("G4", "G10"):
        r, _ = _apply(monkeypatch, rd, setup=st, ctx_trend=1)                                   # पालक विरुद्ध + Gray-1
        assert r["signal"] is not None and r["signal"]["setup"] == st


def test_s11_and_s4_block(monkeypatch):
    rd = {"impulse": IMP, "gray": None, "gray_why": "", "S": "S1", "legs": {"tops": []}}
    r, _ = _apply(monkeypatch, rd, cnt={"setup": None, "parent_dir": -1, "S11": True})
    assert r["signal"] is None and "S11" in r["why"]
    r2, _ = _apply(monkeypatch, {**rd, "gray": "S4", "gray_why": "S4: फक्त flip retest"}, pol={"policy": "reduce", "dir": -1})
    assert r2["signal"] is None and "S4" in r2["why"]


def test_eod_signal_recheck_no_auto_entry_and_area_released(monkeypatch):
    rd = {"impulse": IMP, "gray": None, "gray_why": "", "S": "S12", "legs": {"tops": []}}
    r, tr = _apply(monkeypatch, rd, bar="2026-01-05 15:15")
    sg = r["signal"]
    assert sg["eod_carry"] == "recheck" and not tr.used                                    # पुढच्या दिवशी नवी commitment शक्य
    p = EX.plan({**sg, "ref_levels": {**sg["ref_levels"], "structural_invalidation": 110.0, "next_opposite_area": 90.0}},
                {"sl_mode": "structural_invalidation", "sl_buffer": 0, "sl_buffer_unit": "points", "target_mode": "next_opposite_area",
                 "rr_filter": False}, 1.0, spot_only=True)
    assert not p["ok"] and "recheck" in p["reason"] and p["sl"] == 110.0                     # SL / target मोजलेले, entry नाही


def test_gray_size_half_floor_and_g10_shadow():
    ex = {"sl_mode": "structural_invalidation", "sl_buffer": 0, "sl_buffer_unit": "points", "target_mode": "next_opposite_area",
          "rr_filter": False, "instrument": "futures", "lots": 3, "gray_size": "half"}
    sg = {**_sig(), "gray": "Gray-2", "ref_levels": {"structural_invalidation": 110.0, "next_opposite_area": 90.0}}
    assert EX.plan(sg, ex, 1.0)["lots"] == 1                                                # 3 ⇒ 1
    p = EX.plan(sg, {**ex, "lots": 1}, 1.0)
    assert not p["ok"] and "< 1" in p["reason"]                                            # 1 ⇒ 0 ⇒ trade नाही
    g10 = {**_sig("G10"), "g10": {"mode": "shadow"}, "ref_levels": {"structural_invalidation": 110.0, "next_opposite_area": 90.0}}
    p10 = EX.plan(g10, ex, 1.0)
    assert not p10["ok"] and p10.get("shadow") == "G10" and p10["rr"] is not None
    assert EX.plan({**g10, "g10": {"mode": "paper"}}, ex, 1.0)["ok"]
    assert EX.telegram_action(p10) == "info" and EX.telegram_action(EX.plan(sg, ex, 1.0)) == "approve"
    assert EX.telegram_action(p) is None


def test_g10_settings_defaults_shadow():
    ss = SS.engine_settings({"g10_enabled": False})
    assert ss["g10_enabled"] is False and SS.engine_settings()["g10_enabled"] is True and ss["g10_mode"] == "shadow"
    assert SS.PAPER_SEED["g10_mode"] == "shadow" and SS.PAPER_SEED["parent_source"] == "market_state"
    SS.validate(SS.PAPER_SEED)


def test_g10_edges_range_only_and_parent_trend_side(monkeypatch):
    """S9: RANGE नाही ⇒ G10 नाही; पालक trend नाही ⇒ दोन्ही कडा; bear पालक ⇒ फक्त वरची कड; target = विरुद्ध कड."""
    from opportunity_engine import structure as STR

    class FakeST:
        state = "RANGE"

        def __init__(self, tf):
            pass

        def on_bar(self, *a):
            pass

        def snapshot(self):
            return {"trend_state": FakeST.state, "range_high": 120.0, "range_low": 100.0}

    monkeypatch.setattr(STR, "StructureTracker", FakeST)
    seen = []

    def fake_episode(trig, zs, ctx, mr, s, tracker):
        seen.append((ctx["side"], zs[0]["low"]))
        if ctx["side"] < 0:
            return {"signal": {**_sig(), "pause_bars": 1, "commitment": {"high": 119.0, "low": 115.0, "bars": 1}}, "why": "ENTRY SIGNAL"}
        return {"signal": None, "why": "pause नाही"}

    monkeypatch.setattr(EN, "_detect_episode", fake_episode)
    fr = _bars([(118, 112)] * 10)
    ss = SS.engine_settings()
    r = EN.g10(fr, [], {"trend": 0}, 1.0, None, None, ss)
    assert [x[0] for x in seen] == [-1] and r["signal"]["setup"] == "G10"            # वरची कड आधी, मिळाली
    assert r["signal"]["ref_levels"]["next_opposite_area"] == 100.0 and r["signal"]["g10"]["mode"] == "shadow"
    seen.clear()
    EN.g10(fr, [], {"trend": 1}, 1.0, None, None, ss)
    assert seen == [(1, 100.0)]                                                        # bull पालक ⇒ फक्त खालची कड
    FakeST.state = "TREND"
    seen.clear()
    assert EN.g10(fr, [], {"trend": 0}, 1.0, None, None, ss)["signal"] is None and not seen


def test_g8_flag_is_2_to_6_candles():
    s = SS.engine_settings()
    assert s["flag_min_bars"] == 2 and s["g8_max_bars"] == 6


def test_wave_refs_from_preferred_count_only_for_g1_g9():
    s = SS.engine_settings()
    pref = {"points": [("a", 100.0), ("b", 120.0)]}
    g1 = CSRC.wave_refs(pref, "G1", s, ext=110.0)
    assert g1["wave1_origin"] == 100.0 and g1["wave3_projection"] == 110.0 + 1.618 * 20.0
    assert CSRC.wave_refs(pref, None, s, ext=110.0)["wave1_origin"] is None


# ------------------------------------------------------------------------------------------------- no-lookahead (B6, Phase B §5)
def _lk_path():
    from tests.test_market_state import DOWN_THEN_DEEP_RALLY, _path
    return _path(DOWN_THEN_DEEP_RALLY)


def _lk_read(df1m, asof):
    from chart_reader import evaluate as EV
    trig = EV.frame(df1m, "15m", asof)
    h1 = EV.frame(df1m, "1h", asof)
    last = trig.iloc[-1]
    sig = {"side": -1, "bar_start": str(last["timestamp"]), "pause_from": str(trig["timestamp"].iloc[-3]),
           "area": {"type": "flip", "low": float(last["high"]) - 2, "high": float(last["high"]) + 2},
           "commitment": {"high": float(last["high"]), "low": float(last["low"]), "bars": 1}}
    return RD.read_signal(trig, h1, sig, sig["area"], 5.0, SS.engine_settings(), asof)


def test_reading_no_lookahead_truncation_invariance():
    """impulse / impulse_end / legs / S3 pivot / commit_vs_impulse — asof नंतरचा data जोडल्याने काहीच बदलत नाही."""
    df = _lk_path()
    for frac in (0.55, 0.7, 0.85):
        asof = pd.Timestamp(df["timestamp"].iloc[int(len(df) * frac)]).floor("15min")
        cut = df[pd.to_datetime(df["timestamp"]) + pd.Timedelta(minutes=1) <= asof]
        assert _lk_read(df, asof) == _lk_read(cut, asof)


def test_count_source_no_lookahead_degree_and_parent():
    df = _lk_path()
    asof = pd.Timestamp(df["timestamp"].iloc[int(len(df) * 0.7)]).floor("15min")
    cut = df[pd.to_datetime(df["timestamp"]) + pd.Timedelta(minutes=1) <= asof]
    r = _lk_read(df, asof)
    e_ts = (r["impulse"] or {}).get("end_ts")
    a, b = CSRC.read(df, asof, e_ts, -1), CSRC.read(cut, asof, e_ts, -1)
    assert a == b


# ------------------------------------------------------------------------------------------------- provisional (real data, Abhi ✔ बाकी)
RECENT = Path(os.environ.get("TRADE_DATA_DIR", "/home/user/trade-data")) / "upstox" / "NIFTY_1m_2026-07-01_2026-10-08.csv.gz"
needs_recent = pytest.mark.skipif(not RECENT.exists(), reason="Jul–Oct 2026 1m data (private trade-data) नाही — CI मध्ये skip")


def _replay_until(day, hhmm):
    """दिवसाचा 15M replay (memory + tracker सह, k10 सारखा) hhmm bar पर्यंत ⇒ त्या bar चा candidate (signal / gray / blocked) किंवा None."""
    from chart_reader import setups as SU
    raw = pd.read_csv(RECENT, parse_dates=["timestamp"])
    ts = pd.to_datetime(raw["timestamp"])
    raw["timestamp"] = ts.dt.tz_localize(None) if ts.dt.tz is not None else ts
    d = pd.Timestamp(day)
    m1 = raw[(raw.timestamp >= d - pd.Timedelta(days=130)) & (raw.timestamp < d + pd.Timedelta(days=1))]
    mem, tr = SU.LineMemory(), EN.Tracker()
    end = pd.Timestamp(f"{day} {hhmm}")
    for t in pd.date_range(d + pd.Timedelta(hours=9, minutes=15), end, freq="15min"):
        r = EN.signal_at(m1, t + pd.Timedelta(minutes=15), memory=mem, tracker=tr)
    return r.get("signal") or r.get("gray_candidate") or r.get("blocked_candidate")


@needs_recent
def test_provisional_7oct_1215_target_is_impulse_end_not_inside_correction():
    """PROVISIONAL (Abhi चा 7 Oct count बाकी): impulse 22,809.35 → 22,217.3; target = impulse_end; next_opposite_area correction च्या
    आतला (जुना 22,626.6) नाही. Label (S11 वि. Abhi चा C-end) Abhi च्या count नंतर ठरेल — इथे तपासत नाही."""
    c = _replay_until("2026-10-07", "12:15")
    imp = c["reading"]["impulse"]
    assert (imp["start"], imp["end"]) == (22809.35, 22217.3)
    assert c["ref_levels"]["impulse_end"] == 22217.3
    assert c["ref_levels"]["next_opposite_area"] is None or c["ref_levels"]["next_opposite_area"] < 22300.0


@needs_recent
@pytest.mark.parametrize("day,hhmm,small", [("2026-09-25", "10:30", 23030.0), ("2026-09-28", "14:15", 22785.5)])
def test_provisional_sep_targets_not_tiny_recent_impulse(day, hhmm, small):
    """PROVISIONAL (A6): टप्पा A मध्ये ref impulse अगदी अलीकडचा लहान impulse होता (R:R 0.48 / 0.13). आता तो target नाही
    (एकतर योग्य degree चा impulse, किंवा origin confirm नाही ⇒ Gray-2 / signal नाही)."""
    c = _replay_until(day, hhmm)
    assert c is None or c["ref_levels"].get("impulse_end") != small


# ------------------------------------------------------------------------------------------------- §2.6 Daily / Weekly (own OHLC)
def _daily(n=400, seed=3):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2016-01-04", periods=n)
    c = 8000 + np.cumsum(rng.normal(0, 60, n)) + 900 * np.sin(np.arange(n) / 35.0)
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + np.abs(rng.normal(0, 30, n))
    lo = np.minimum(o, c) - np.abs(rng.normal(0, 30, n))
    return pd.DataFrame({"timestamp": days, "bar_end": days + pd.Timedelta(hours=15, minutes=30), "open": o, "high": h, "low": lo, "close": c})


def test_own_tf_daily_weekly_no_lookahead():
    """§2.6: decision दिवसाच्या close नंतरचा data नाही — पूर्ण frame वि. कापलेला frame ⇒ तेच pivots / counts. चालू (अर्धवट) आठवडा नाही."""
    from elliott import own_tf as OT
    d = _daily()
    now = pd.Timestamp(d["bar_end"].iloc[300])                                   # बुधवार/कोणताही दिवस 15:30
    cut = d[d["bar_end"] <= now]
    a, b = OT.snapshot(d, now, "1d"), OT.snapshot(cut, now, "1d")
    assert a[0] is not None and OT.brief(*a) == OT.brief(*b)
    assert any(v["n_pivots"] for v in OT.brief(*a).values())
    wk_full, wk_cut = OT.weekly_frame(d), OT.weekly_frame(cut)
    wa, wb = OT.snapshot(wk_full, now, "1w"), OT.snapshot(wk_cut, now, "1w")
    assert OT.brief(*wa) == OT.brief(*wb)
    known = wk_full[wk_full["bar_end"] <= now]
    assert known["bar_end"].max() <= now and (pd.Timestamp(known["bar_end"].iloc[-1]).dayofweek == 4)


# ------------------------------------------------------------------------------------------------- नकाशा I7 (B6) — जुळणारे केस
IS_PARQUET = Path(__file__).resolve().parents[1] / "data" / "nifty50_1min.parquet"


def _i7(day, until):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research"))
    import map_b_i7 as I7
    if pd.Timestamp(day) < pd.Timestamp("2026-07-01"):
        raw = I7.read(IS_PARQUET, "research")
    else:
        raw = I7.read(RECENT, "golden")
    bars = [I7.brief(t, r) for t, r in I7.replay(raw, day, until)]
    return bars


@pytest.mark.parametrize("day,until,expect", [
    pytest.param("2026-08-12", "10:15", "none", marks=needs_recent),
    pytest.param("2026-08-25", "10:45", "none", marks=needs_recent),
    pytest.param("2026-08-26", None, "bear", marks=needs_recent),
    pytest.param("2026-08-31", None, "none", marks=needs_recent),
    pytest.param("2026-10-07", "09:30", "none", marks=needs_recent),
    pytest.param("2026-10-07", "12:15", "bear", marks=needs_recent),                  # Abhi ✔ 2026-10-09: C-end
    pytest.param("2018-02-16", "13:30", "none", marks=pytest.mark.skipif(not IS_PARQUET.exists(), reason="IS parquet नाही")),
])
def test_i7_map_answers(day, until, expect):
    """KB I7 (decision-bar labels). 22 Sep / 28 Sep = I6 अहवाल (docs/reports/situation_map/B_I7_cases.md: थर निर्णय /
    वाचन-area / वाचन-count, Abhi ✔ बाकी) — constants बदलून pass नाही. 16 Feb 09:30 आणि 15 Nov 13:00 = Abhi च्या निर्णयानुसार."""
    bars = _i7(day, until)
    sigs = [b for b in bars if b["signal"]] if until is None else [b for b in bars[-1:] if b["signal"]]
    if expect == "none":
        assert not sigs
    else:
        assert any((b["side"] or 0) < 0 for b in sigs)


def test_b4_log_has_map_fields(monkeypatch):
    """B4 (P7): S#, दोन counts (प्रत्येक degree), पालक + PARENT_CONFLICT, gray प्रकार, दिवसाचं धोरण, area source, invalidation."""
    rd = {"impulse": IMP, "gray": None, "gray_why": "", "S": "S1", "legs": {"tops": []}}
    cnt = {"setup": None, "parent_dir": 1, "degrees": {"D3": {"preferred": "flat/B/-1", "alternate": "impulse/2/-1", "gray": False}}}
    r, _ = _apply(monkeypatch, rd, cnt=cnt)
    x = r["reading"]
    assert x["S"] == "S1" and x["count"]["degrees"]["D3"]["alternate"] == "impulse/2/-1"
    assert x["parent"] == -1 and x["parent_count"] == 1 and x["PARENT_CONFLICT"] is True
    assert x["policy"]["policy"] == "block" and x["area_source"] == "S1 (flip)" and x["invalidation"] == 110.0
    import research.k10_days as K
    b = K._reading_brief(x)
    assert b["counts_by_degree"]["D3"]["preferred"] == "flat/B/-1" and b["area_source"] and b["invalidation"] == 110.0


def test_break_from_is_first_real_break_window():
    """निर्णय 8: engine area acceptance = breaks.py ची real break (displacement ⇒ लगेच; कमकुवत close ⇒ पुढचा bar reclaim नाही; पुढचा bar
    नाही ⇒ अपुष्ट −1)."""
    from elliott import breaks as BR
    from elliott import settings as ES
    s = {**ES.DEFAULTS, "break_buffer_mr": 0.25}
    f = _bars([(101, 99)] * 25 + [(106, 99.5)])                                        # displacement वर (range 6.5, close टोकाजवळ नाही) …
    f.loc[25, "close"] = 105.8
    mr = np.full(len(f), 2.0)
    assert BR.break_from(f, 25, 101.0, "above", s, mr=mr) == 25
    g = _bars([(101, 99)] * 25 + [(102.2, 101.4)])                                     # कमकुवत close buffer पलीकडे, पुढचा bar नाही
    g.loc[25, "close"] = 101.8
    assert BR.break_from(g, 25, 101.0, "above", s, mr=np.full(len(g), 2.0)) == -1
    h = pd.concat([g, _bars([(101.5, 100.0)]).assign(timestamp=g["timestamp"].iloc[-1] + pd.Timedelta(minutes=15))], ignore_index=True)
    h.loc[26, "close"] = 100.5                                                         # पुढचा bar परत आत ⇒ खरा break नाही
    assert BR.break_from(h, 25, 101.0, "above", s, mr=np.full(len(h), 2.0)) is None


class _N:
    def __init__(self, pattern, wave, direction, score, pts):
        self.pattern, self.current_wave, self.direction, self.current_dir, self.next_motive_dir = pattern, wave, direction, -direction, direction
        self.joint_score, self.invs = score, []
        self.points = [type("P", (), {"ts": pd.Timestamp(t), "price": p})() for t, p in pts]


def test_count_tie_is_not_a_preference(monkeypatch):
    """I6 (7 Oct, Abhi ✔ C-end): beam मध्ये score बरोबरी ⇒ नावाच्या क्रमाचा 'preferred' (flat/B) पसंती नाही ⇒ S11 / G9 नाहीत; एकटा
    सर्वोच्च ⇒ नेहमीसारखा."""
    pts = [("2026-10-01 09:00", 22809.3), ("2026-10-01 14:05", 22217.3)]
    piv = type("Pv", (), {"kind": "L", "ts": pd.Timestamp("2026-10-01 14:05"), "confirmed_at": pd.Timestamp("2026-10-01 15:00")})()
    md = {3: {"tf": "5m", "confirmed": [piv]}}

    def snap(nodes):
        v = type("V", (), {"nodes": nodes, "preferred": nodes[0], "gray": False})()
        return type("S", (), {"degrees": {3: v}})()

    tie = [_N("flat", "B", -1, 0.5, pts), _N("impulse", "2", -1, 0.5, pts)]
    r = CSRC.read(None, "2026-10-07 12:30", "2026-10-01 14:05", -1, md_snap=(md, snap(tie)))
    assert not r["S11"] and r["setup"] is None and r["count_tie"] == ["flat/B", "impulse/2"] and r["S11_alpha"]
    one = [_N("flat", "B", -1, 0.6, pts), _N("impulse", "2", -1, 0.5, pts)]
    r1 = CSRC.read(None, "2026-10-07 12:30", "2026-10-01 14:05", -1, md_snap=(md, snap(one)))
    assert r1["S11"] and "count_tie" not in r1
    g9 = [_N("impulse", "4", -1, 0.7, pts), _N("zigzag", "B", -1, 0.5, pts)]
    assert CSRC.read(None, "2026-10-07 12:30", "2026-10-01 14:05", -1, md_snap=(md, snap(g9)))["setup"] == "G9"
