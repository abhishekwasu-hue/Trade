"""Simple Core v2 (Abhi 2026-10-08): motive wave G1 / G8 / G9 (label + reference levels), K-10 निर्णय A–D, execution wave modes.

Waves: (1) wave 2 end ⇒ G1 + projections · (2) wave 3 मधला उथळ pullback ⇒ G8 · (3) wave 4 wave 1 च्या भागात ⇒ G9 नाही (gray) ·
(4) motive wave च्या आत pullback शिवाय ⇒ signal नाही · G9 (wave 4 end) projections.
A1 testing मध्ये जुन्या टोकापलीकडे close ⇒ break failed ⇒ trend परत · A2 testing ⇒ फक्त flip retest / range edge (TESTING_ONLY_FLIP_OR_EDGE).
B1 pause / commitment मालिकेतल्या कोणत्याही candle चा touch पुरेसा · B2 3 closes (buffer आत) ⇒ acceptance ⇒ BROKEN / flip ⇒ retest entry.
C execution settings (rr_filter on, min_rr 3, …) ⇒ K-10 मध्ये plan / sim · D 15M chart window ≤ 7 sessions.
"""
import pandas as pd
import pytest

from simple_core import engine as EN
from simple_core import execution as EX
from simple_core import waves as WV
from simple_core import settings as SS

MR = 10.0


def day(rows, d="2026-03-10"):
    ts = pd.date_range(f"{d} 09:15", periods=len(rows), freq="15min")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"])
    df.insert(0, "timestamp", ts)
    df["bar_end"] = ts + pd.Timedelta(minutes=15)
    return df


def buy_zone(lo, hi, zid="B1", bar=None):
    z = {"id": f"Z-{zid}", "zid": zid, "side": "buy", "role": "SUPPORT", "tool": "c", "type": "base", "kind": "solid", "low": lo, "high": hi,
         "state": "ACTIVE"}
    if bar is not None:
        z["bar"] = bar
    return z


UP = {"trend": 1, "side": 1, "protected": 1000.0, "impulse_end": 1100.0}
# ---------------------------------------------------------------------------------------------------------------- waves
IMP12 = [(1010, 1012, 1003, 1005), (1005, 1006, 1000, 1004), (1004, 1025, 1003, 1023), (1023, 1045, 1022, 1043), (1043, 1068, 1042, 1065),
         (1065, 1088, 1064, 1086), (1086, 1100, 1085, 1095)]                      # O 1000 (bar 1) ⇒ W1 1100 (bar 6)
G1_ROWS = IMP12 + [(1095, 1096, 1075, 1078), (1078, 1080, 1058, 1060), (1060, 1062, 1049, 1052),
                   (1052, 1055, 1047, 1051), (1051, 1054, 1046, 1050),            # pause (wave 2 end area)
                   (1050, 1068, 1049, 1066)]                                      # commitment
PV12 = [{"idx": 1, "price": 1000.0, "kind": "L"}, {"idx": 6, "price": 1100.0, "kind": "H"}]

W3 = [(1010, 1012, 1003, 1005), (1005, 1006, 1000, 1004), (1004, 1030, 1003, 1028), (1028, 1055, 1027, 1053), (1053, 1080, 1052, 1078),
      (1078, 1095, 1077, 1092), (1092, 1100, 1088, 1094), (1094, 1095, 1070, 1072), (1072, 1074, 1055, 1057), (1057, 1060, 1050, 1058),
      (1058, 1085, 1057, 1083), (1083, 1112, 1082, 1110), (1110, 1140, 1109, 1138), (1138, 1170, 1137, 1168), (1168, 1200, 1167, 1196)]
PV_W3 = [{"idx": 1, "price": 1000.0, "kind": "L"}, {"idx": 6, "price": 1100.0, "kind": "H"}, {"idx": 9, "price": 1050.0, "kind": "L"}]
G8_ROWS = W3 + [(1196, 1197, 1180, 1182), (1182, 1184, 1170, 1172), (1172, 1175, 1168, 1171), (1171, 1190, 1170, 1188)]
G9_ROWS = W3 + [(1196, 1198, 1185, 1187), (1187, 1190, 1172, 1175), (1175, 1180, 1160, 1163), (1163, 1168, 1148, 1150),
                (1150, 1155, 1138, 1141), (1141, 1144, 1131, 1137), (1137, 1140, 1130, 1135), (1135, 1155, 1133, 1153)]
OVERLAP_ROWS = W3 + [(1196, 1198, 1180, 1182), (1182, 1185, 1165, 1167), (1167, 1170, 1150, 1152), (1152, 1155, 1135, 1137),
                     (1137, 1140, 1118, 1120), (1120, 1123, 1103, 1105), (1105, 1107, 1094, 1101), (1101, 1104, 1095, 1099),
                     (1099, 1118, 1097, 1116)]


def wsig(rows, zones, pv):
    return EN.detect(day(rows), zones, {**UP, "pivots": pv}, MR)


def test_wave2_end_gives_g1_with_projections():
    r = wsig(G1_ROWS, [buy_zone(1045.0, 1052.0)], PV12)
    s = r["signal"]
    assert s and s["side"] == 1 and s["setup"] == "G1"
    ref = s["ref_levels"]
    assert ref["wave1_origin"] == 1000.0 and ref["wave1_extreme"] == 1100.0
    assert ref["wave3_projection"] == pytest.approx(1046.0 + 1.618 * 100.0)          # wave 2 end (pullback low) + 1.618 × wave 1
    assert s["wave"]["alts"]["wave3_projection"]["1.0"] == pytest.approx(1146.0)
    assert ref["wave5_projection"] is None and "लागू नाही" in s["ref_notes"]["wave5_projection"]
    assert "G1" in s["context_story"]


def test_shallow_pullback_inside_wave3_is_g8():
    r = wsig(G8_ROWS, [buy_zone(1165.0, 1172.0, bar=13)], PV_W3)
    s = r["signal"]
    assert s and s["setup"] == "G8"
    assert s["ref_levels"]["subwave_origin"] == 1050.0 and s["ref_levels"]["wave1_extreme"] == 1100.0
    assert s["ref_levels"]["wave3_projection"] == pytest.approx(1050.0 + 161.8)


def test_wave4_end_gives_g9_with_wave5_projection():
    r = wsig(G9_ROWS, [buy_zone(1128.0, 1136.0, bar=12)], PV_W3)
    s = r["signal"]
    assert s and s["setup"] == "G9"
    assert s["ref_levels"]["wave5_projection"] == pytest.approx(1130.0 + 100.0)
    assert s["wave"]["alts"]["wave5_projection"]["w13"] == pytest.approx(1130.0 + 0.618 * 200.0)
    assert s["ref_levels"]["wave3_projection"] is None and s["ref_levels"]["wave1_extreme"] == 1100.0


def test_wave4_overlapping_wave1_is_not_g9():
    r = wsig(OVERLAP_ROWS, [buy_zone(1092.0, 1100.0, bar=3)], PV_W3)
    s = r["signal"]
    assert s, r["why"]                                                               # core चे 4 टप्पे तसेच (label फक्त context)
    assert s["setup"] is None and "R3" in s["wave"]["gray"]
    assert all(s["ref_levels"][k] is None for k in WV.REF_KEYS)
    assert all("लागू नाही" in s["ref_notes"][k] for k in WV.REF_KEYS)


def test_inside_motive_wave_without_pullback_no_signal():
    r = wsig(W3[:13] + [(1138, 1170, 1137, 1168), (1168, 1188, 1167, 1186)], [buy_zone(1165.0, 1172.0, bar=12)], PV_W3)
    assert not r["signal"] and ("pause" in r["why"] or "acceptance" in r["why"]), r["why"]   # खालून चढताना: pullback / pause नाही


def test_wave1_extreme_is_a_flip_area_after_wave3_passes_it():
    z = WV.wave1_zone(day(G8_ROWS), PV_W3, 1, MR)
    assert z and z["side"] == "buy" and z["low"] < 1100.0 < z["high"] and z["bar"] == 11


# ---------------------------------------------------------------------------------------------------------------- execution
BASE_EX = {"sl_buffer": 2.0, "sl_buffer_unit": "points", "rr_filter": False, "instrument": "futures", "lots": 1}


def test_execution_wave_target_and_sl_modes():
    s = wsig(G1_ROWS, [buy_zone(1045.0, 1052.0)], PV12)["signal"]
    p = EX.plan(s, {**BASE_EX, "sl_mode": "wave1_origin", "target_mode": "wave3_projection"}, MR)
    assert p["ok"] and p["sl"] == 998.0 and p["target"] == pytest.approx(1207.8, abs=0.01)
    p = EX.plan(s, {**BASE_EX, "sl_mode": "wave1_origin", "target_mode": "wave5_projection"}, MR)
    assert not p["ok"] and "wave5_projection" in p["reason"] and "लागू नाही" in p["reason"]
    p = EX.plan(s, {**BASE_EX, "sl_mode": "subwave_origin", "target_mode": "wave3_projection"}, MR)
    assert not p["ok"] and "subwave_origin" in p["reason"]


def test_g9_needs_tier_setting_and_skip_means_no_trade():
    s = wsig(G9_ROWS, [buy_zone(1128.0, 1136.0, bar=12)], PV_W3)["signal"]
    ex = {**BASE_EX, "sl_mode": "wave1_extreme", "target_mode": "wave5_projection"}
    p = EX.plan(s, ex, MR)
    assert not p["ok"] and "G9" in p["reason"]
    assert not EX.plan(s, {**ex, "g9_tier": "skip"}, MR)["ok"]
    p = EX.plan(s, {**ex, "g9_tier": "C", "g9_lots": 1}, MR)
    assert p["ok"] and p["lots"] == 1 and p["tier"] == "C" and p["sl"] == 1098.0 and p["target"] == pytest.approx(1230.0)
    assert not EX.plan(s, {**ex, "g9_tier": "C"}, MR)["ok"]                         # g9_lots नाही ⇒ trade नाही


# ---------------------------------------------------------------------------------------------------------------- A testing
def test_a1_close_beyond_old_extreme_fails_the_break():
    from tests.test_market_state import DOWN_THEN_DEEP_RALLY, _path
    import market_state as MS
    up = DOWN_THEN_DEEP_RALLY[:-2] + [(300, 1230), (250, 1190), (500, 1290), (200, 1250), (300, 1360), (200, 1320), (300, 1420), (400, 1270)]
    df = _path(up + [(300, 1445)])                                                   # testing मध्ये जुन्या HH 1420 पलीकडे closes
    t = df["timestamp"].iloc[-1] + pd.Timedelta(minutes=1)
    tr = MS.read(df, t, run_elliott=False)["trend"]
    assert tr["dir"] == 1 and tr["state"] == "trend"
    assert any(e["event"] == "BREAK_FAILED" for e in tr["events"])


SELL_A = [(1010, 1012, 1001, 1003), (1003, 1020, 1002, 1018), (1018, 1035, 1017, 1033), (1033, 1047, 1032, 1044), (1044, 1049, 1041, 1045),
          (1045, 1050, 1042, 1043), (1043, 1047, 1024, 1025)]


def test_a2_testing_allows_only_flip_retest_or_range_edge():
    plain = [{"id": "S-x", "zid": "S1", "side": "sell", "role": "RESISTANCE", "tool": "c", "type": "base", "kind": "solid", "low": 1043.0,
              "high": 1050.0, "state": "ACTIVE"}]
    def ctx(prot):
        return EN.context_from({"trend": {"dir": 1, "state": "testing", "protected": {"price": prot}, "extreme": 1200.0}, "side": "unclear"})
    assert ctx(980.0)["side"] == 0 and ctx(980.0)["testing"]["dir"] == 1
    r = EN.detect(day(SELL_A), plain, {**ctx(980.0), "range": (900.0, 1200.0)}, MR)
    assert not r["signal"] and "TESTING_ONLY_FLIP_OR_EDGE" in r["why"]
    # (a) तुटलेला protected L 1046 चा flip retest, break दिशेने (bear) ⇒ G4
    r = EN.detect(day(SELL_A), [], {**ctx(1046.0), "range": (900.0, 1200.0)}, MR)
    assert r["signal"] and r["signal"]["side"] == -1 and r["signal"]["setup"] == "G4"
    # (b) range ची वरची कड ⇒ bear (zone नियमासह)
    r = EN.detect(day(SELL_A), plain, {**ctx(980.0), "range": (900.0, 1048.0)}, MR)
    assert r["signal"] and r["signal"]["side"] == -1 and r["signal"]["setup"] == "range_edge"


# ---------------------------------------------------------------------------------------------------------------- B touch / flip
def test_b1_pause_touch_is_enough_commitment_slightly_away():
    zones = [{"id": "S-1", "zid": "S1", "side": "sell", "role": "RESISTANCE", "tool": "e", "type": "liquidity", "kind": "solid",
              "low": 1050.0, "high": 1053.0, "state": "ACTIVE"}]
    rows = [(1010, 1012, 1001, 1003), (1003, 1020, 1002, 1018), (1018, 1035, 1017, 1033), (1033, 1052, 1032, 1045),
            (1045, 1048, 1041, 1044), (1044, 1047, 1040, 1043),                       # pause (1052 ला touch आधीच्या bar ने)
            (1042, 1044, 1023, 1024)]                                                # commitment: high 1044 (area पासून 6 > 0.3 MR)
    r = EN.detect(day(rows), zones, {"trend": -1, "side": -1, "protected": 1100.0, "impulse_end": 1000.0}, MR)
    assert r["signal"], r["why"]


def test_b2_three_closes_inside_buffer_break_and_flip_then_retest_entry():
    from elliott import breaks as BR
    from price_action import levels_v2 as LV
    flat = (1010.0, 1012.0, 1008.0, 1010.0)
    rows = [flat] * 25 + [(1006, 1007, 1003, 1004), (1004, 1005, 998, 999.5), (999.5, 1000, 998.5, 999), (999, 999.8, 998.6, 999.2),
                          (999.2, 1000.6, 995, 996), (996, 1001.4, 995.5, 997)]        # 3 closes PDL 1000 खाली (buffer 1 आत) ⇒ BROKEN
    f = day(rows)
    lc = LV.lifecycle(f, (1000.0, 1001.0), "SUPPORT", 25, 4.0, dict(LV.DEFAULTS))
    assert lc["state"] in ("BROKEN", "FLIPPED") and lc["role"] == "RESISTANCE" and lc["broken_at"] == 28
    es = {"median_range_n": 5, "break_buffer_mr": 0.25, "break_displacement_confirm": True, "strength_min": 1.2, "break_close_loc": 0.3,
          "break_no_reclaim_bars": 2, "break_accept_closes": 3}
    assert BR.first_real_break(f, 25, 1000.0, "below", es) == 28
    assert BR.first_real_break(f, 25, 1000.0, "below", {**es, "break_accept_closes": 0}) == 29     # buffer + displacement ⇒ उशिरा
    # retest entry: तुटलेला PDL (आता seller area) वर pause + commitment ⇒ bear signal
    zone = {"id": "PDL", "zid": "S1", "side": "sell", "role": "RESISTANCE", "tool": "b", "type": "flip (PDL)", "kind": "solid",
            "low": 1000.0, "high": 1001.0, "state": lc["state"], "bar": 28, "role_since": lc["broken_at"]}
    retest = rows[:31] + [(997, 1000.5, 996.5, 999.6), (999.6, 1000.8, 998.8, 999.8), (999.8, 1000.2, 986, 987)]
    r = EN.detect(day(retest), [zone], {"trend": -1, "side": -1, "protected": 1012.0, "impulse_end": 990.0}, 7.0)
    assert r["signal"] and r["signal"]["side"] == -1, r["why"]


# ---------------------------------------------------------------------------------------------------------------- C / D
def test_c_k10_exec_json_profile_and_manifest_reading():
    from research import k10_days as K
    ex = K.exec_from_args(None, '{"rr_filter": true, "min_rr": 3, "sl_mode": "structural_invalidation", '
                                '"target_mode": "next_opposite_area"}')
    assert ex == {"rr_filter": True, "min_rr": 3, "sl_mode": "structural_invalidation", "target_mode": "next_opposite_area"}
    with pytest.raises(ValueError):
        K.exec_from_args(None, '{"sl_mode": "magic"}')
    rec = {"date": "2026-08-31", "trend": "down", "signals": [{"time": "13:45", "side": -1, "trigger_price": 24047.05, "setup": None,
                                                              "area": {"id": "S1", "type": "flip (PDL)", "low": 24070.5, "high": 24083.2},
                                                              "pause_bars": 7, "plan": {"ok": False, "reason": "R:R 1.1 < 3 (rr_filter)"},
                                                              "sim": {"result": "NO_TRADE"}}],
           "why_by_bar": [["13:30", "area वर commitment candle नाही"]]}
    line = K.reading(rec)
    assert "down" in line and "S1" in line and "pause 7" in line and "13:45" in line and "R:R 1.1" in line
    rec2 = {"date": "2026-08-25", "trend": "testing", "signals": [], "why_by_bar": [["10:00", "x"], ["10:15", "x"], ["11:00", "y"]]}
    assert "Signal नाही" in K.reading(rec2) and "x" in K.reading(rec2)


def test_d_15m_window_at_most_7_sessions():
    from backtest_review import charts as BC
    ts = pd.date_range("2026-08-01", periods=20, freq="B")
    rows = []
    for d in ts:
        for t in pd.date_range(d + pd.Timedelta(hours=9, minutes=15), periods=25, freq="15min"):
            rows.append({"timestamp": t, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0})
    m15 = pd.DataFrame(rows)
    m15["bar_end"] = m15["timestamp"] + pd.Timedelta(minutes=15)
    end = m15["bar_end"].iloc[-1]
    c = {"impulse": {"from_ts": ts[2] + pd.Timedelta(hours=10), "start_ts": ts[2] + pd.Timedelta(hours=10)}}
    d = BC.adaptive_window(m15, end, c, max_s=BC.CHART["m15_max_sessions"])
    assert BC.CHART["m15_max_sessions"] == 7
    assert pd.to_datetime(d["timestamp"]).dt.normalize().nunique() <= 7


def test_gallery_g8_g9_g7_detectors(monkeypatch):
    from backtest_review import gallery as GL
    monkeypatch.setattr(GL, "_rejection", lambda bar, side: True)
    trig = day(G8_ROWS)
    piv = [{"ts": trig["timestamp"].iloc[p["idx"]], "price": p["price"], "kind": p["kind"]} for p in PV_W3]
    ms = {"trend": {"dir": 1, "state": "trend"}, "swings": piv}
    assert [h["setup"] for h in GL.detect_waves(ms, trig, len(trig) - 1, MR)] == ["G8"]
    trig9 = day(G9_ROWS)
    piv9 = [{"ts": trig9["timestamp"].iloc[p["idx"]], "price": p["price"], "kind": p["kind"]} for p in PV_W3]
    assert [h["setup"] for h in GL.detect_waves({**ms, "swings": piv9}, trig9, len(trig9) - 1, MR)] == ["G9"]
    # G7: आदल्या दिवशी 1000, आज trend दिशेने gap up 1040 (4 MR), टोक, open खाली close, मग pullback reversal (bear)
    prev = day([(1000, 1002, 998, 1000)] * 4, d="2026-03-09")
    today = day([(1040, 1052, 1039, 1050), (1050, 1055, 1044, 1046), (1046, 1047, 1030, 1032), (1032, 1041, 1031, 1039),
                 (1039, 1040, 1026, 1028)], d="2026-03-10")
    t7 = pd.concat([prev, today], ignore_index=True)
    hits = GL.detect_g7({"trend": {"dir": 1, "state": "trend"}}, t7, len(t7) - 1, MR)
    assert hits and hits[0]["setup"] == "G7" and hits[0]["side"] == -1
    assert not GL.detect_g7({"trend": {"dir": -1, "state": "trend"}}, t7, len(t7) - 1, MR)       # gap trend विरुद्ध ⇒ G7 नाही


def test_commitment_must_beat_pause_average():
    zones = [{"id": "S", "zid": "S1", "side": "sell", "role": "RESISTANCE", "tool": "c", "type": "base", "kind": "solid", "low": 1043.0,
              "high": 1050.0, "state": "ACTIVE"}]
    base = SELL_A[:3] + [(1033, 1047, 1032, 1044), (1044, 1049, 1040, 1045), (1045, 1050, 1041, 1043)]   # pause bars range 9
    small = base + [(1043, 1046, 1033, 1034)]                                       # commitment 13 ≥ 1.2 MR पण < 1.5 × 9
    r = EN.detect(day(small), zones, {"trend": -1, "side": -1, "protected": 1100.0}, MR)
    assert not r["signal"] and "pause सरासरी" in r["why"], r["why"]
    big = base + [(1043, 1047, 1027, 1028)]                                         # 20 ≥ 13.5 ⇒ signal
    assert EN.detect(day(big), zones, {"trend": -1, "side": -1, "protected": 1100.0}, MR)["signal"]


def test_b2_engine_time_acceptance_inside_buffer_cancels_setup():
    zones = [{"id": "S", "zid": "S1", "side": "sell", "role": "RESISTANCE", "tool": "c", "type": "base", "kind": "solid", "low": 1043.0,
              "high": 1050.0, "state": "ACTIVE"}]
    rows = SELL_A[:3] + [(1033, 1052, 1032, 1051), (1051, 1053, 1049, 1052), (1052, 1053, 1050, 1051.5), (1051, 1052, 1033, 1035)]
    r = EN.detect(day(rows), zones, {"trend": -1, "side": -1, "protected": 1100.0}, MR)   # 3 closes 1050 वर (buffer 2.5 आत)
    assert not r["signal"] and "acceptance" in r["why"], r["why"]


def test_b2_zone_annotate_path_breaks_on_three_closes():
    from chart_reader import settings as CS
    from chart_reader import zones as ZN
    flat = (1010.0, 1012.0, 1008.0, 1010.0)
    rows = [flat] * 30 + [(1006, 1007, 1003, 1004), (1004, 1005, 998, 999.5), (999.5, 1000, 998.5, 999), (999, 999.8, 998.6, 999.2)]
    z = {"id": "SWL-1", "tool": "e", "pool": "swing_low", "kind": "solid", "low": 1000.0, "high": 1001.0, "bar": 5}
    out = ZN.annotate([z], day(rows), CS.load(), 4.0)
    assert out and out[0]["state"] in ("BROKEN", "FLIPPED") and out[0]["role"] == "RESISTANCE" and out[0].get("role_since") == 33


def test_possible_reversal_blocks_old_trend_side_allows_new():
    rev = {"dir": 1, "state": "active", "reason": "POSSIBLE_REVERSAL (active): counter-move 58%, impulsive 4/5"}
    ctx = EN.context_from({"trend": {"dir": -1, "state": "trend"}, "side": "unclear", "possible_reversal": rev})
    assert ctx["side"] == 1 and ctx["reversal"] == "active"                          # नव्या दिशेने (wave (2) end) चालतं
    r = EN.detect(day(SELL_A), [{"id": "S", "zid": "S1", "side": "sell", "role": "RESISTANCE", "tool": "c", "type": "base",
                                 "kind": "solid", "low": 1043.0, "high": 1050.0, "state": "ACTIVE"}], ctx, MR)
    assert not r["signal"]                                                           # जुन्या (bear) दिशेने नाही
    gone = EN.context_from({"trend": {"dir": -1, "state": "trend"}, "side": "bear_call", "possible_reversal": {**rev, "state": "cancelled"}})
    assert gone["side"] == -1


RV_BASE = [(0, 1300), (600, 1200), (300, 1260), (600, 1100), (300, 1180), (150, 1060), (150, 1120), (150, 990)]


def _rev(tail):
    from tests.test_market_state import _path
    import market_state as MS
    df = _path(RV_BASE + tail, noise=0.3)
    return MS.read(df, df["timestamp"].iloc[-1] + pd.Timedelta(minutes=1), run_elliott=False)


def test_reversal_v2_impulsive_58pct_is_flag_corrective_is_not():
    ms = _rev([(45, 1101)])                                                         # सरळ, जलद 58% rally (11 Aug सारखी)
    pr = ms["possible_reversal"]
    assert pr and pr["state"] == "active" and pr["dir"] == 1 and pr["score"] >= 3 and 0.5 < pr["retrace"] < 0.65
    assert ms["side"] == "unclear"
    assert _rev([(150, 1060), (150, 1020), (200, 1100)])["possible_reversal"] is None   # 3 legs, overlap, संथ ⇒ corrective


def test_reversal_v2_ends_only_by_structure():
    b = _rev([(60, 1070), (60, 1045), (45, 1110), (30, 1030)])["possible_reversal"]   # (b) शेवटचा आतला HL impulsive leg ने तुटला
    assert b["state"] == "cancelled" and "(b)" in b["reason"]
    c = _rev([(45, 1110), (150, 1050), (60, 1095)])["possible_reversal"]            # (c) HL confirm ⇒ नवीन trend
    assert c["state"] == "new_trend" and "(c)" in c["reason"]
    w2 = _rev([(45, 1110), (100, 1045), (60, 1100)])["possible_reversal"]           # 75% परत (wave (2)) — तरी flag चालू (61.8% नियम नाही)
    assert w2["state"] in ("active", "new_trend")
    assert _rev([(45, 1101), (120, 985)])["possible_reversal"] is None             # (a) सुरुवात (impulse टोक) परत ⇒ flag नाही


def test_reversal_v2_protected_break_is_not_possible_reversal():
    ms = _rev([(60, 1215)])                                                         # HTF protected (LH) च्या पलीकडे ⇒ trend / testing प्रश्न
    assert ms["possible_reversal"] is None


def test_k10_sensitivity_report_side_by_side():
    from research import k10_days as K
    rec = {"date": "2026-08-31", "signals": [{"time": "13:45", "side": -1, "trigger_price": 24047.0, "setup": None, "pause_bars": 7,
                                              "area": {"id": "S1", "type": "flip", "low": 24070.5, "high": 24083.2},
                                              "plan": {"ok": False, "reason": "R:R 1.1 < 3 (rr_filter)"}, "sim": {"result": "NO_TRADE"},
                                              "alts": {"buffer0": {"plan": {"ok": True, "sl": 24083.2, "target": 23900.0, "rr": 4.1},
                                                                   "sim": {"result": "SL"}}}}]}
    md, st = K.sensitivity_md([rec], "buffer0.25mr", ["buffer0"])
    assert "trade नाही: R:R 1.1 < 3" in md and "R:R 4.1 ⇒ SL" in md
    assert st["buffer0.25mr"]["rr_reject"] == 1 and st["buffer0"]["trades"] == 1 and st["buffer0"]["sl"] == 1
    assert "[buffer0: R:R 4.1 ⇒ SL]" in K.reading({**rec, "trend": "down"})


IMP_DN = [(1100, 1101, 1080, 1082), (1082, 1083, 1060, 1062), (1062, 1063, 1040, 1042), (1042, 1043, 1020, 1022),
          (1022, 1023, 1003, 1004), (1004, 1006, 1000, 1002)]
FLAG_UP = [(1002, 1012, 1000, 1010), (1010, 1015, 1005, 1008), (1008, 1018, 1006, 1016), (1016, 1021, 1011, 1014),
           (1014, 1024, 1012, 1022), (1022, 1027, 1017, 1020)]
IMP_CTX = {"trend": -1, "side": -1, "protected": 1150.0}


def _imp(df):
    return {"dir": -1, "from": 1100.0, "to": 1000.0, "to_ts": df["timestamp"].iloc[5]}


def test_g8_flag_channel_is_area_and_breakout_signal():
    rows = IMP_DN + FLAG_UP + [(1020, 1022, 1001, 1003)]                            # flag च्या खालच्या रेषेखाली commitment
    df = day(rows)
    r = EN.detect(df, [], {**IMP_CTX, "impulse": _imp(df)}, MR)
    assert r["signal"] and r["signal"]["setup"] == "G8" and "flag channel" in r["signal"]["area"]["type"], r["why"]
    assert not EN.detect(df, [], IMP_CTX, MR)["signal"]                             # impulse माहिती नाही ⇒ flag area नाही


def test_g8_flag_needs_breakout_shallow_and_overlap():
    inside = IMP_DN + FLAG_UP + [(1020, 1025, 1019, 1024)]                          # रेषेबाहेर close नाही
    df = day(inside)
    assert not EN.detect(df, [], {**IMP_CTX, "impulse": _imp(df)}, MR)["signal"]
    deep = IMP_DN + [(1002, 1030, 1000, 1028), (1028, 1056, 1026, 1054), (1054, 1070, 1050, 1066), (1066, 1072, 1058, 1060),
                     (1060, 1066, 1054, 1058), (1058, 1064, 1052, 1056)]                # 70% retrace ⇒ flag नाही
    from simple_core import flags as FL
    dd = day(deep + [(1056, 1058, 1035, 1036)])
    assert FL.flag_zone(dd, _imp(dd), -1, MR) is None


def test_g8_breakout_bar_that_makes_new_low_still_uses_flag():
    rows = IMP_DN + FLAG_UP + [(1020, 1021, 997, 999)]                              # breakout bar नेच नवा low (impulse टोक पुढे सरकलं)
    df = day(rows)
    imp = {"dir": -1, "from": 1100.0, "to": 997.0, "from_ts": df["timestamp"].iloc[0], "to_ts": df["timestamp"].iloc[-1]}
    r = EN.detect(df, [], {**IMP_CTX, "impulse": imp}, MR)
    assert r["signal"] and r["signal"]["setup"] == "G8", r["why"]


def test_review_all_pause_flag_still_gives_g8():
    flag = [(1002, 1008, 1000, 1004), (1004, 1010, 1002, 1005), (1005, 1012, 1004, 1008), (1008, 1013, 1005, 1007),
            (1007, 1015, 1006, 1010), (1010, 1016, 1008, 1011)]                       # सगळे लहान indecision bars (सामान्य flag)
    df = day(IMP_DN + flag + [(1011, 1012, 995, 996)])
    r = EN.detect(df, [], {**IMP_CTX, "impulse": _imp(df)}, MR)
    assert r["signal"] and r["signal"]["setup"] == "G8", r["why"]


def test_review_g9_spot_only_without_lots_and_wave_g9_under_flag_label():
    s = wsig(G9_ROWS, [buy_zone(1128.0, 1136.0, bar=12)], PV_W3)["signal"]
    ex = {"sl_mode": "wave1_extreme", "sl_buffer": 2.0, "sl_buffer_unit": "points", "target_mode": "wave5_projection", "rr_filter": False,
          "g9_tier": "C"}
    p = EX.plan(s, ex, MR, spot_only=True)                                         # K-10: lots नाहीत ⇒ crash नाही
    assert p["ok"] and p["tier"] == "C"
    flagged = {**s, "setup": "G8", "wave": {**s["wave"], "setup": "G9"}}
    assert "G9" in EX.plan(flagged, {k: v for k, v in ex.items() if k != "g9_tier"}, MR, spot_only=True)["reason"]
    assert not EX.plan(s, {**ex, "rr_filter": "false", "sl_mode": "magic"}, MR, spot_only=True)["ok"]


def test_review_latest_counter_leg_is_found():
    ms = _rev([(60, 1070), (60, 1045), (45, 1110), (30, 1030), (45, 1105)])         # पूर्ण leg (b) ने रद्द, मग 1030 पासून ताजा impulsive leg
    pr = ms["possible_reversal"]
    assert pr and pr["leg"] == "latest" and pr["state"] == "active" and abs(pr["start"] - 1030) < 15, pr


def test_review_k10_reading_with_no_sl_target():
    from research import k10_days as K
    rec = {"date": "2026-08-31", "trend": "down", "signals": [{"time": "13:45", "side": -1, "trigger_price": 24047.0, "setup": None,
           "pause_bars": 2, "area": {"id": "S1", "type": "flip", "low": 24070.5, "high": 24083.2},
           "plan": {"ok": True, "sl": None, "target": None, "rr": None}, "sim": {"result": "TIME"}}]}
    assert "SL — T —" in K.reading(rec)
    assert "SL — · T —" in K.sensitivity_md([rec], "m", [])[0]


def test_g9_tier_full_and_half_use_profile_lots():
    """Abhi 2026-10-08 23:48: g9_tier = full (PAPER). full ⇒ lots; half ⇒ lots ÷ 2 (खाली); < 1 ⇒ trade नाही."""
    s = wsig(G9_ROWS, [buy_zone(1128.0, 1136.0, bar=12)], PV_W3)["signal"]
    ex = {**BASE_EX, "sl_mode": "wave1_extreme", "target_mode": "wave5_projection", "lots": 4}
    p = EX.plan(s, {**ex, "g9_tier": "full"}, MR)
    assert p["ok"] and p["lots"] == 4 and p["tier"] == "full"
    p = EX.plan(s, {**ex, "g9_tier": "half"}, MR)
    assert p["ok"] and p["lots"] == 2 and p["tier"] == "half"
    p = EX.plan(s, {**ex, "g9_tier": "half", "lots": 1}, MR)
    assert not p["ok"] and "half" in p["reason"]
    assert EX.plan(s, {**ex, "g9_tier": "half", "lots": 1}, MR, spot_only=True)["ok"]   # review (order नाही) ⇒ lots तपासत नाही


def test_paper_profile_seed_only_for_paper(tmp_path):
    """PAPER profile store मध्ये नसेल ⇒ Abhi चे मूल्य; इतर profile (LIVE सह) ⇒ {} (default नाही); saved profile ⇒ तेच."""
    path = str(tmp_path / "exec.json")
    p = SS.load_profile(SS.PAPER_PROFILE, path)
    assert p["target_mode"] == "impulse_end" and p["g9_tier"] == "full" and p["sl_buffer"] == 0.25 and p["min_rr"] == 3.0
    assert "instrument" not in p and "lots" not in p                                     # order साठी dashboard वर निवडायलाच हवे
    assert SS.load_profile("live_core", path) == {}
    SS.save_profile(SS.PAPER_PROFILE, {"target_mode": "next_opposite_area"}, path)
    assert SS.load_profile(SS.PAPER_PROFILE, path) == {"target_mode": "next_opposite_area"}
    SS.validate(SS.PAPER_SEED)
