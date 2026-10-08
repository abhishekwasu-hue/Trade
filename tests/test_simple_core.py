"""Simple Core (Abhi 2026-10-08): trend + area + pause + commitment ⇒ ENTRY SIGNAL. SL / target / instrument फक्त execution settings मधून.

(a) trend + area + pause + commitment ⇒ signal · (b) commitment area पासून दूर ⇒ नाही · (c) pause नाही ⇒ नाही · (d) area वर उलट
acceptance ⇒ नाही · (e) uptrend / gap up मिरर · (f) signal मध्ये ref_levels; engine मध्ये SL / target / instrument चे hardcoded आकडे नाहीत ·
(g) execution settings बदलल्यावर तोच signal वेगळ्या SL / target ने simulate.
"""
import os
import re

import pandas as pd
import pytest

from simple_core import engine as EN
from simple_core import execution as EX

MR = 10.0
SELL = [{"id": "TL-R1", "zid": "S1", "side": "sell", "role": "RESISTANCE", "tool": "f", "type": "trendline", "kind": "solid",
         "low": 1048.0, "high": 1052.0, "state": "ACTIVE"},
        {"id": "SWH-1", "zid": "S2", "side": "sell", "role": "RESISTANCE", "tool": "e", "type": "liquidity", "kind": "solid",
         "low": 1043.0, "high": 1046.0, "state": "ACTIVE"}]
BUY_LOW = [{"id": "B1", "zid": "B1", "side": "buy", "role": "SUPPORT", "tool": "c", "type": "base", "kind": "solid", "low": 990.0,
            "high": 994.0, "state": "ACTIVE"}]
CTX = {"trend": -1, "protected": 1080.0, "impulse_end": 1000.0}


def day(rows, d="2026-03-10"):
    ts = pd.date_range(f"{d} 09:15", periods=len(rows), freq="15min")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"])
    df.insert(0, "timestamp", ts)
    df["bar_end"] = ts + pd.Timedelta(minutes=15)
    return df


# bear: relief वर seller area (1043–1052) ला, तिथे pause (लहान / अनिर्णयी), मग commitment (मजबूत bearish close)
A = [(1010, 1012, 1001, 1003),        # drive
     (1003, 1020, 1002, 1018),        # relief
     (1018, 1035, 1017, 1033),        # relief
     (1033, 1047, 1032, 1044),        # area ला लागला (मोठा bullish — pause नाही)
     (1044, 1049, 1041, 1045),        # pause (लहान, दोन्ही wicks)
     (1045, 1050, 1042, 1043),        # pause
     (1043, 1047, 1024, 1025)]        # commitment: touch (पाठचा pause) ⇒ मजबूत close तळाशी


def sig(rows, zones=SELL, ctx=CTX):
    return EN.detect(day(rows), zones, ctx, MR)


def test_a_trend_area_pause_commitment_gives_signal():
    r = sig(A)
    assert r["signal"] and r["signal"]["side"] == -1 and r["signal"]["pause_bars"] == 2
    s_ = r["signal"]
    assert s_["trigger_price"] == 1025 and s_["commitment"]["close"] == 1025 and s_["area"]["low"] <= 1043.0
    for k in range(len(A) - 1):
        assert not sig(A[: k + 1])["signal"], k                                            # आधीच्या bars वर signal नाही


def test_b_commitment_far_from_area_no_signal():
    far = A[:3] + [(1033, 1036, 1030, 1034), (1034, 1036, 1031, 1035), (1035, 1036, 1015, 1016)]
    r = sig(far)
    assert not r["signal"] and "area" in r["why"]


def test_c_no_pause_no_signal():
    direct = A[:3] + [(1033, 1049, 1032, 1047), (1047, 1049, 1026, 1027)]                 # area ला लागताच पडला — pause नाही
    r = sig(direct)
    assert not r["signal"] and "pause" in r["why"]


def test_d_acceptance_beyond_area_no_signal():
    acc = A[:5] + [(1045, 1060, 1044, 1058), (1058, 1066, 1055, 1064), (1064, 1065, 1042, 1043)]
    r = sig(acc)
    assert not r["signal"] and "acceptance" in r["why"]


def mirror(rows, c=1000.0):
    return [(2 * c - o, 2 * c - lo, 2 * c - h, 2 * c - cl) for o, h, lo, cl in rows]


def test_e_uptrend_mirror():
    buy = [{**z, "side": "buy", "role": "SUPPORT", "low": 2000 - z["high"], "high": 2000 - z["low"]} for z in SELL]
    r = EN.detect(day(mirror(A)), buy, {"trend": 1, "protected": 920.0, "impulse_end": 1000.0}, MR)
    assert r["signal"] and r["signal"]["side"] == 1 and r["signal"]["trigger_price"] == 975


def test_f_signal_has_ref_levels_and_engine_has_no_execution_numbers():
    s_ = EN.detect(day(A), SELL + BUY_LOW, CTX, MR)["signal"]
    ref = s_["ref_levels"]
    assert set(ref) == {"structural_invalidation", "commitment_extreme", "next_opposite_area", "impulse_end", "wave3_projection",
                        "wave5_projection", "wave1_origin", "wave1_extreme", "subwave_origin"}
    assert ref["wave3_projection"] is None and "लागू नाही" in s_["ref_notes"]["wave3_projection"]        # pivots नाहीत ⇒ count gray
    assert ref["commitment_extreme"] == 1047 and ref["next_opposite_area"] == 994.0 and ref["impulse_end"] == 1000.0
    assert ref["structural_invalidation"] >= 1052.0
    assert {"side", "trigger_time", "trigger_price", "area", "pause_bars", "commitment", "ref_levels", "context_story"} <= set(s_)
    src = open(os.path.join(os.path.dirname(EN.__file__), "engine.py"), encoding="utf-8").read()
    for word in ("stop_loss", "sl_mode", "target_mode", "min_rr", "lots", "strike", "credit_spread", "premium"):
        assert word not in src, word                                                      # execution engine मध्ये नाही


def test_g_same_signal_different_execution_settings():
    s_ = EN.detect(day(A), SELL + BUY_LOW, CTX, MR)["signal"]
    base = {"sl_mode": "structural_invalidation", "sl_buffer": 2.0, "sl_buffer_unit": "points", "target_mode": "next_opposite_area",
            "target_value": None, "rr_filter": False, "min_rr": None, "instrument": "futures", "lots": 1}
    p1 = EX.plan(s_, base)
    p2 = EX.plan(s_, {**base, "sl_mode": "commitment_extreme", "target_mode": "r_multiple", "target_value": 2.0})
    assert p1["ok"] and p2["ok"] and p1["sl"] != p2["sl"] and p1["target"] != p2["target"]
    after = day([(1025, 1030, 1000, 1002), (1002, 1004, 990, 992)], d="2026-03-10")
    after["timestamp"] += pd.Timedelta(hours=2)
    r1, r2 = EX.simulate(p1, after), EX.simulate(p2, after)
    assert r1["result"] in ("TARGET", "SL", "TIME") and r2["result"] in ("TARGET", "SL", "TIME")
    assert p1["settings_hash"] != p2["settings_hash"]


def test_missing_execution_settings_means_no_trade_with_clear_message():
    s_ = EN.detect(day(A), SELL, CTX, MR)["signal"]
    p = EX.plan(s_, {})
    assert not p["ok"] and "SL mode निवडलेला नाही" in p["reason"]
    p = EX.plan(s_, {"sl_mode": "commitment_extreme", "sl_buffer": 0, "sl_buffer_unit": "points"})
    assert not p["ok"] and "target mode" in p["reason"].lower()
    p = EX.plan(s_, {"sl_mode": "commitment_extreme", "sl_buffer": 0, "sl_buffer_unit": "points", "target_mode": "none",
                     "rr_filter": False, "instrument": "credit_spread", "lots": 1})
    assert not p["ok"] and "strike" in p["reason"]


def test_rr_filter_only_when_enabled():
    s_ = EN.detect(day(A), SELL + BUY_LOW, CTX, MR)["signal"]
    ex = {"sl_mode": "structural_invalidation", "sl_buffer": 0, "sl_buffer_unit": "points", "target_mode": "next_opposite_area",
          "target_value": None, "rr_filter": True, "min_rr": 50.0, "instrument": "futures", "lots": 1}
    assert not EX.plan(s_, ex)["ok"]
    assert EX.plan(s_, {**ex, "rr_filter": False})["ok"]


def test_dup_setup_one_entry_per_area():
    tr = EN.Tracker()
    rows = A + [(1025, 1046, 1024, 1044), (1044, 1048, 1042, 1045), (1045, 1047, 1026, 1027)]
    hits = []
    for k in range(len(rows)):
        r = EN.detect(day(rows[: k + 1]), SELL, CTX, MR, tracker=tr)
        hits.append(bool(r["signal"]))
    assert hits.count(True) == 1 and hits[len(A) - 1]


def test_exec_settings_store_round_trip_and_no_defaults(tmp_path):
    from simple_core import settings as SS
    p = str(tmp_path / "x.json")
    assert SS.load_profile("paper", p) == {}                                               # default भरत नाही
    h = SS.save_profile("paper", {"sl_mode": "commitment_extreme", "sl_buffer": 5.0, "sl_buffer_unit": "points"}, p)
    assert SS.load_profile("paper", p)["sl_mode"] == "commitment_extreme" and len(h) == 10
    with pytest.raises(ValueError):
        SS.save_profile("paper", {"sl_mode": "magic"}, p)
    with pytest.raises(ValueError):
        SS.save_profile("paper", {"unknown_key": 1}, p)


def test_page_exec_form_values_skip_unselected():
    import page_backtest_review as P
    vals = P.exec_form_values({}, lambda k, kind, cur: "futures" if k == "instrument" else None)
    assert vals == {"instrument": "futures"}


# ------------------------------------------------------------------ स्वतंत्र review (2026-10-08) नंतरचे tests
def test_review_testing_blocks_signal_confirmed_trend_drives_side():
    ctx = EN.context_from({"trend": {"dir": -1, "state": "testing"}, "side": "unclear"})
    assert not EN.detect(day(A), SELL, {**ctx, "impulse_end": 1000.0}, MR)["signal"]
    ctx2 = EN.context_from({"trend": {"dir": -1, "state": "trend"}, "side": "bear_call"})
    assert EN.detect(day(A), SELL, ctx2, MR)["signal"]
    # K-10 (16 Feb 2018): HTF trend down confirmed, F4 "unclear" फक्त आधीचा up-impulse फसल्यामुळे ⇒ core HTF trend नुसार bear
    ctx3 = EN.context_from({"trend": {"dir": -1, "state": "trend"}, "side": "unclear"})
    assert ctx3["side"] == -1 and EN.detect(day(A), SELL, ctx3, MR)["signal"]
    assert EN.context_from({"trend": {"dir": 0, "state": "range"}, "side": "unclear"})["side"] == 0
    assert EN.context_from({"trend": {"dir": 0, "state": "range"}, "side": "bull_put"})["side"] == 1


def test_review_flip_retest_not_cancelled_by_old_closes_beyond():
    flip = [{"id": "FLIP", "zid": "S1", "side": "sell", "role": "RESISTANCE", "tool": "b", "type": "flip", "kind": "solid",
             "low": 1040.0, "high": 1046.0, "state": "FLIPPED"}]
    rows = [(1050, 1056, 1049, 1055), (1055, 1056, 1048, 1050),        # break आधी area वर
            (1050, 1051, 1030, 1032), (1032, 1033, 1020, 1022),        # break खाली, area पासून दूर
            (1022, 1036, 1021, 1035), (1035, 1044, 1034, 1041),        # retest
            (1041, 1045, 1038, 1040), (1040, 1044, 1020, 1021)]        # pause, commitment
    r = EN.detect(day(rows), flip, CTX, MR)
    assert r["signal"], r["why"]


def test_review_invalid_trendline_is_not_an_area():
    bad = [{**SELL[0], "valid": False}]
    assert EN.areas(bad, -1) == []


def test_review_structural_invalidation_includes_every_pause_bar():
    rows = A[:4] + [(1044, 1049.5, 1041, 1045), (1045, 1048, 1042, 1043)] + A[6:]
    s_ = EN.detect(day(rows), [SELL[1]], CTX, MR)["signal"]
    assert s_ and s_["pause_bars"] == 2 and s_["ref_levels"]["structural_invalidation"] == 1049.5   # पहिल्या pause bar चं टोक


def test_review_target_or_sl_on_wrong_side_is_rejected():
    s_ = EN.detect(day(A), SELL, CTX, MR)["signal"]
    bad_t = {**s_, "ref_levels": {**s_["ref_levels"], "impulse_end": 1100.0}}
    ex = {"sl_mode": "structural_invalidation", "sl_buffer": 0, "sl_buffer_unit": "points", "target_mode": "impulse_end",
          "rr_filter": False, "instrument": "futures", "lots": 1}
    p = EX.plan(bad_t, ex)
    assert not p["ok"] and "target" in p["reason"].lower()


def test_review_mr_buffer_without_mr_is_not_silently_zero():
    s_ = EN.detect(day(A), SELL, CTX, MR)["signal"]
    ex = {"sl_mode": "structural_invalidation", "sl_buffer": 0.25, "sl_buffer_unit": "mr", "target_mode": "none",
          "rr_filter": False, "instrument": "futures", "lots": 1}
    assert not EX.plan(s_, ex, mr=None)["ok"]
    assert EX.plan(s_, ex, mr=10.0)["sl"] == round(s_["ref_levels"]["structural_invalidation"] + 2.5, 2)


def test_review_sigma_strike_and_step_from_settings():
    s_ = EN.detect(day(A), SELL, CTX, MR)["signal"]
    ex = {"sl_mode": "commitment_extreme", "sl_buffer": 0, "sl_buffer_unit": "points", "target_mode": "none", "rr_filter": False,
          "instrument": "naked_sell", "lots": 1, "strike_mode": "sigma", "strike_value": 2.0, "strike_step": 50}
    assert EX.plan(s_, ex, sigma_px=20.0)["strike"] == 1100                                # 1025 + 2×20 = 1065 ⇒ वरचा 50 = 1100
    assert not EX.plan(s_, {**ex, "strike_step": None}, sigma_px=20.0)["ok"]


def test_review_tracker_sloping_area_and_release():
    tr = EN.Tracker()
    a1 = {"low": 1048.0, "high": 1052.0, "source_ids": ["TL-R1"]}
    tr.add(-1, a1, "2026-03-10 11:00:00", invalidation=1060.0)
    moved = {"low": 1038.0, "high": 1042.0, "source_ids": ["TL-R1"]}                       # रेषा उतरली, पट्टा overlap नाही
    assert tr.seen(-1, moved)
    tr.on_bar(close=1061.0)                                                                # invalidation पलीकडे close ⇒ मोकळी
    assert not tr.seen(-1, a1)



def test_area_born_inside_the_pause_is_not_an_area():
    """K-10 (7 Oct 14:45): याच rally चा swing high (pause मध्ये जन्मलेला) ⇒ "आपला" area नाही ⇒ signal नाही."""
    late = [{**SELL[1], "id": "SWH-late", "bar": 4}]                                       # bar 4 = पहिला pause bar
    assert not EN.detect(day(A), late, CTX, MR)["signal"]
    early = [{**SELL[1], "id": "SWH-old", "bar": 1}]
    assert EN.detect(day(A), early, CTX, MR)["signal"]
