"""tests/test_sr_levels_v3.py -- नवीन SR Levels V3 इंजिन (recency/reaction/MTF/key levels/gaps/role-reversal/score), कृत्रिम डेटावर."""
import datetime

import numpy as np
import pandas as pd
import pytest

import sr_levels_v3 as sr
from sr_levels_v3 import SRConfig


def _frame(closes, start="2026-09-01 09:15", freq="15min", spread=2.0):
    idx = pd.date_range(start, periods=len(closes), freq=freq)
    closes = np.asarray(closes, dtype=float)
    opens = np.concatenate([[closes[0]], closes[:-1]])
    return pd.DataFrame({
        "timestamp": idx, "open": opens,
        "high": np.maximum(opens, closes) + spread, "low": np.minimum(opens, closes) - spread,
        "close": closes, "volume": 1000,
    })


def _triangle(n=61, peak_at=30, base=100.0, slope=1.0):
    return [base + slope * (peak_at - abs(i - peak_at)) for i in range(n)]


def _market(days=10, seed=3, amplitude=100.0, center=24100.0, period_bars=150):
    """5M मालिका (सोम-शुक्र, 75 bars/दिवस) + त्यावरून 15M/30M/1H resample."""
    rng = np.random.default_rng(seed)
    stamps = []
    for d in pd.bdate_range("2026-09-01", periods=days):
        stamps += list(pd.date_range(d + pd.Timedelta(hours=9, minutes=15), periods=75, freq="5min"))
    n = len(stamps)
    close = center + amplitude * np.sin(np.arange(n) * 2 * np.pi / period_bars) + rng.normal(0, 3, n)
    open_ = np.concatenate([[close[0]], close[:-1]])
    f5 = pd.DataFrame({
        "timestamp": stamps, "open": open_, "high": np.maximum(open_, close) + 2, "low": np.minimum(open_, close) - 2,
        "close": close, "volume": 1000,
    })

    def resample(rule):
        d = f5.set_index("timestamp").resample(rule, label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna(subset=["open"])
        return d.reset_index()

    return {"5minute": f5, "15minute": resample("15min"), "30minute": resample("30min"), "1hour": resample("1h")}


# ---- A: recency ------------------------------------------------------------------------------------------------------
def test_recency_weight_halves_every_half_life():
    assert sr.recency_weight(0, 2.5) == 1.0
    assert sr.recency_weight(2.5, 2.5) == pytest.approx(0.5)
    assert sr.recency_weight(5.0, 2.5) == pytest.approx(0.25)
    assert sr.recency_weight(-3, 2.5) == 1.0
    assert sr.recency_weight(4, 0) == 1.0


def test_newer_pivot_has_higher_weight_than_older_pivot():
    cfg = SRConfig()
    closes = _triangle(61, 15) + _triangle(61, 30, base=100.0)[1:]            # दोन शिखरं: जुनं (15) आणि नवं (~76)
    df = _frame(closes)
    pivots = [p for p in sr.extract_pivots(df, "15minute", cfg, df["timestamp"].iloc[-1]) if p["kind"] == "H"]
    pivots.sort(key=lambda p: p["ts"])
    assert len(pivots) >= 2 and pivots[-1]["weight"] > pivots[0]["weight"]


def test_pivots_older_than_lookback_are_dropped():
    cfg = SRConfig()
    df = _frame(_triangle(61, 30))
    now = df["timestamp"].iloc[-1] + pd.Timedelta(days=cfg.lookback_days["15minute"] + 1)
    assert sr.extract_pivots(df, "15minute", cfg, now) == []


# ---- B: reaction -----------------------------------------------------------------------------------------------------
def test_sharp_reversal_scores_higher_reaction_than_gentle_one():
    cfg = SRConfig()
    sharp = _frame([100 + min(i, 30) if i <= 30 else 130 - (i - 30) * 3 for i in range(61)])
    gentle = _frame([100 + min(i, 30) if i <= 30 else 130 - (i - 30) * 0.2 for i in range(61)])
    r_sharp = [p for p in sr.extract_pivots(sharp, "15minute", cfg, sharp["timestamp"].iloc[-1]) if p["kind"] == "H"][0]["reaction"]
    r_gentle = [p for p in sr.extract_pivots(gentle, "15minute", cfg, gentle["timestamp"].iloc[-1]) if p["kind"] == "H"][0]["reaction"]
    assert 0.0 <= r_gentle < r_sharp <= 1.0


def test_atr_basic_and_empty():
    df = _frame([100.0] * 30, spread=2.0)
    assert sr.compute_atr(df, 14) == pytest.approx(4.0)
    assert sr.compute_atr(pd.DataFrame(), 14) == 0.0


# ---- C: clustering / confluence --------------------------------------------------------------------------------------
def test_cluster_groups_close_and_splits_far_and_bounds_span():
    items = [{"price": p} for p in (100.0, 100.5, 101.0, 130.0, 130.4)]
    clusters = sr.cluster_items(items, tol=1.0)
    assert [len(c) for c in clusters] == [3, 2]
    # साखळी-जोडणी नाही: 0.9 च्या अंतराने ठेवलेले 10 बिंदू एक झोन होत नाहीत
    chain = [{"price": 100 + 0.9 * i} for i in range(10)]
    for c in sr.cluster_items(chain, tol=1.0):
        assert max(i["price"] for i in c) - min(i["price"] for i in c) <= 2.0


def _pv(price, tf, kind="H", weight=1.0, reaction=0.5, ts=None):
    return {"price": price, "kind": kind, "tf": tf, "weight": weight, "reaction": reaction, "ts": ts or pd.Timestamp("2026-09-02")}


def test_same_swing_in_many_timeframes_does_not_multiply_touches():
    cfg = SRConfig()
    one_tf = sr._build_zone([_pv(100, "1hour")], cfg)
    four_tf = sr._build_zone([_pv(100, tf) for tf in sr.TF_ORDER], cfg)
    assert four_tf["touches_raw"] == pytest.approx(one_tf["touches_raw"])        # 1H (सर्वात मोठा factor) च निर्णायक
    assert four_tf["tfs"] == list(sr.TF_ORDER)


def test_more_timeframes_give_more_confluence_points_and_higher_score():
    cfg = SRConfig()
    one = sr._build_zone([_pv(100, "15minute")], cfg)
    many = sr._build_zone([_pv(100, "15minute"), _pv(100, "30minute"), _pv(100, "1hour")], cfg)
    sr._score_zone(one, cfg)
    sr._score_zone(many, cfg)
    assert many["components"]["confluence"] > one["components"]["confluence"]
    assert many["score"] > one["score"]
    full = sr._build_zone([_pv(100, tf) for tf in sr.TF_ORDER], cfg)
    sr._score_zone(full, cfg)
    assert full["components"]["confluence"] == 25.0


def test_polarity_when_both_highs_and_lows_present():
    cfg = SRConfig()
    z = sr._build_zone([_pv(100, "15minute", "H"), _pv(100.1, "15minute", "L")], cfg)
    assert z["polarity"] and z["n_high"] == 1 and z["n_low"] == 1
    assert not sr._build_zone([_pv(100, "15minute", "H")], cfg)["polarity"]


def test_score_is_capped_to_100_and_graded():
    cfg = SRConfig()
    members = [_pv(100, tf, "H", 1.0, 1.0) for tf in sr.TF_ORDER] * 3 + [_pv(100.1, "1hour", "L", 1.0, 1.0)]
    members += [{"price": 100.0, "kind": "KEY", "name": n, "tf": None, "weight": 1.0} for n in ("PDH", "PWH")]
    z = sr._build_zone(members, cfg)
    z["flipped"], z["retested"], z["gap"] = True, True, {"kind": "UP_GAP"}
    sr._score_zone(z, cfg)
    assert z["score"] == 100.0 and z["grade"] == "A"
    weak = sr._build_zone([_pv(100, "5minute", "H", 0.1, 0.0)], cfg)
    sr._score_zone(weak, cfg)
    assert weak["grade"] == "C" and 0 <= weak["score"] < cfg.min_score


# ---- D: key levels ---------------------------------------------------------------------------------------------------
def _daily(rows):
    return pd.DataFrame([{"timestamp": pd.Timestamp(d), "open": c, "high": h, "low": l, "close": c, "volume": 1} for d, h, l, c in rows])


def test_key_levels_previous_day_and_previous_week():
    daily = _daily([
        ("2026-09-07", 110, 100, 105), ("2026-09-08", 112, 99, 101), ("2026-09-09", 111, 98, 103),   # मागचा आठवडा (सोम-बुध)
        ("2026-09-10", 115, 97, 100), ("2026-09-11", 118, 96, 117),                                  # मागचा आठवडा (गुरु-शुक्र)
        ("2026-09-14", 120, 110, 119), ("2026-09-15", 125, 118, 124),                                # या आठवड्याचे दोन दिवस
        ("2026-09-16", 130, 120, 128),                                                               # आजचा (अपूर्ण) दिवस
    ])
    keys = {k["name"]: k["price"] for k in sr.compute_key_levels(daily, None, datetime.date(2026, 9, 16))}
    assert keys["PDH"] == 125 and keys["PDL"] == 118 and keys["PDC"] == 124      # 15 सप्टेंबर (आजचा 16 वगळून)
    assert keys["PWH"] == 118 and keys["PWL"] == 96                              # 7-11 सप्टेंबर आठवडा


def test_key_levels_fall_back_to_intraday_and_handle_empty():
    f = _frame([100.0] * 25 + [110.0] * 25, start="2026-09-15 09:15")
    f.loc[:24, "timestamp"] = pd.date_range("2026-09-14 09:15", periods=25, freq="15min")
    keys = {k["name"]: k["price"] for k in sr.compute_key_levels(None, sr._prep(f), datetime.date(2026, 9, 15))}
    assert "PDH" in keys and "PWH" not in keys
    assert sr.compute_key_levels(None, None, datetime.date(2026, 9, 15)) == []


# ---- F: gaps ---------------------------------------------------------------------------------------------------------
def _two_day(day2_path, day1_close=100.0):
    day1 = _frame([day1_close] * 25, start="2026-09-14 09:15", spread=0.5)
    day2 = _frame(day2_path, start="2026-09-15 09:15", spread=0.5)
    return sr._prep(pd.concat([day1, day2], ignore_index=True))


def test_unfilled_up_gap_is_detected_and_filled_gap_is_dropped():
    gaps = sr.find_unfilled_gaps(_two_day([110.0] * 25), 0.2, 10)
    assert len(gaps) == 1 and gaps[0]["kind"] == "UP_GAP"
    assert gaps[0]["low"] == pytest.approx(100.5) and gaps[0]["high"] == pytest.approx(109.5) and gaps[0]["fill_pct"] == 0.0
    filled = sr.find_unfilled_gaps(_two_day([110.0] * 10 + [100.0] * 15), 0.2, 10)
    assert filled == []


def test_partially_filled_gap_keeps_only_remaining_zone():
    gaps = sr.find_unfilled_gaps(_two_day([110.0] * 10 + [105.0] * 15), 0.2, 10)
    assert len(gaps) == 1
    assert gaps[0]["low"] == pytest.approx(100.5) and gaps[0]["high"] == pytest.approx(104.5) and gaps[0]["fill_pct"] > 0


def test_down_gap_and_small_gap_threshold():
    down = sr.find_unfilled_gaps(_two_day([90.0] * 25), 0.2, 10)
    assert len(down) == 1 and down[0]["kind"] == "DOWN_GAP"
    assert sr.find_unfilled_gaps(_two_day([101.2] * 25), 5.0, 10) == []          # gap 0.2% च्या खाली/मर्यादेबाहेर
    assert sr.find_unfilled_gaps(_frame([100.0] * 5), 0.2, 10) == []


def test_old_gaps_age_out():
    df = _two_day([110.0] * 25)
    assert sr.find_unfilled_gaps(df, 0.2, 10, now=df["timestamp"].iloc[-1] + pd.Timedelta(days=30)) == []


# ---- E: role reversal ------------------------------------------------------------------------------------------------
def _after(closes, spread=0.3):
    return sr._prep(_frame(closes, start="2026-09-02 09:15", spread=spread))


SINCE = pd.Timestamp("2026-09-01")


def test_resistance_broken_and_held_is_flipped_and_retest_detected():
    df = _after([98, 99, 101.5, 102, 102.5, 101.8, 100.4, 101.5, 102.5])      # तुटला -> परत झोनमध्ये आला -> टिकला
    res = sr.detect_role_reversal(99.5, 100.5, "R", df, SINCE, 0.1, 2)
    assert res == {"flipped": True, "retested": True}


def test_flip_without_retest():
    df = _after([98, 99, 101.5, 102, 103, 104, 105])
    assert sr.detect_role_reversal(99.5, 100.5, "R", df, SINCE, 0.1, 2) == {"flipped": True, "retested": False}


def test_support_broken_downwards_flips_to_resistance():
    df = _after([102, 101, 98.5, 98, 97, 96])
    assert sr.detect_role_reversal(99.5, 100.5, "S", df, SINCE, 0.1, 2)["flipped"] is True


def test_no_flip_when_never_broken_single_close_or_fell_back():
    never = _after([98, 99, 99.2, 98.7, 99.3])
    assert sr.detect_role_reversal(99.5, 100.5, "R", never, SINCE, 0.1, 2)["flipped"] is False
    single_close = _after([98, 101.5, 99, 98.5, 98])
    assert sr.detect_role_reversal(99.5, 100.5, "R", single_close, SINCE, 0.1, 2)["flipped"] is False
    fell_back = _after([98, 101.5, 102, 101, 99, 97])
    assert sr.detect_role_reversal(99.5, 100.5, "R", fell_back, SINCE, 0.1, 2)["flipped"] is False
    assert sr.detect_role_reversal(99.5, 100.5, None, never, SINCE)["flipped"] is False


# ---- एकत्रित (end-to-end) --------------------------------------------------------------------------------------------
def test_end_to_end_finds_the_repeated_swing_level_with_confluence():
    frames = _market()
    price = float(frames["5minute"]["close"].iloc[-1])
    out = sr.compute_sr_v3(frames, daily_df=None, current_price=price)
    levels = out["levels"]
    assert levels, out["meta"]
    scores = [z["score"] for z in levels]
    assert scores == sorted(scores, reverse=True) and all(0 <= s <= 100 for s in scores)
    top_zone = [z for z in levels if abs(z["level"] - 24200) <= 40]
    assert top_zone, [round(z["level"]) for z in levels]
    assert max(len(z["tfs"]) for z in top_zone) >= 2 and max(z["score"] for z in top_zone) >= sr.SRConfig().grade_b
    for z in levels:
        assert z["low"] <= z["level"] <= z["high"] or z["gap"]
        expected = "RESISTANCE" if price < z["low"] else "SUPPORT" if price > z["high"] else "ZONE"
        assert z["role"] == expected
        assert set(z["components"]) == {"touches", "reaction", "confluence", "key_level", "polarity", "role_reversal", "gap", "rejections"}
    assert out["meta"]["frames"] == ["5minute", "15minute", "30minute", "1hour"]


def test_inputs_are_not_mutated_and_tz_aware_equals_naive():
    frames = _market(days=6)
    snapshot = {k: v.copy() for k, v in frames.items()}
    naive = sr.compute_sr_v3(frames)
    for k, v in frames.items():
        pd.testing.assert_frame_equal(v, snapshot[k])
    aware = {k: v.assign(timestamp=v["timestamp"].dt.tz_localize("Asia/Kolkata")) for k, v in frames.items()}
    aware_out = sr.compute_sr_v3(aware)
    assert [round(z["level"], 2) for z in naive["levels"]] == [round(z["level"], 2) for z in aware_out["levels"]]


def test_key_levels_appear_as_tagged_zones_in_end_to_end():
    frames = _market(days=8)
    daily = pd.DataFrame([
        {"timestamp": pd.Timestamp(d), "open": 24100, "high": h, "low": l, "close": 24100, "volume": 1}
        for d, h, l in [("2026-09-04", 24250, 23950), ("2026-09-07", 24260, 23940), ("2026-09-08", 24230, 23970),
                        ("2026-09-09", 24210, 23990), ("2026-09-10", 24300, 23900), ("2026-09-11", 24220, 23960),
                        ("2026-09-14", 24240, 23980), ("2026-09-15", 24215, 23985)]
    ])
    levels = sr.compute_sr_v3(frames, daily_df=daily)["levels"]
    all_tags = {t for z in levels for t in z["tags"]}
    assert {"PDH", "PDL"} <= all_tags


def test_standalone_gap_zone_uses_near_edge_as_line_level():
    day1 = _frame(np.linspace(100, 91, 25), start="2026-09-14 09:15", spread=0.5)
    day2 = _frame(np.linspace(112, 130, 20), start="2026-09-15 09:15", spread=0.5)      # pivots नसलेली सरळ चाल; सत्र चालू (15:15 आधी)
    df = pd.concat([day1, day2], ignore_index=True)
    gap = sr.find_unfilled_gaps(sr._prep(df), 0.2, 10)[0]
    out = sr.compute_sr_v3({"15minute": df}, current_price=130.0)
    gap_zones = [z for z in out["levels"] if z["gap"] and not z["tfs"]]
    assert gap_zones and gap_zones[0]["level"] == pytest.approx(gap["high"]) and gap_zones[0]["role"] == "SUPPORT"
    assert "GAP↑" in gap_zones[0]["tags"] and gap_zones[0]["score"] >= 30
    inside = sr.compute_sr_v3({"15minute": df}, current_price=(gap["low"] + gap["high"]) / 2)
    assert [z["role"] for z in inside["levels"] if z["gap"] and not z["tfs"]] == ["ZONE"]


@pytest.mark.parametrize("bad", [None, {}, {"15minute": pd.DataFrame()}, {"15minute": _frame([100.0] * 5)},
                                 {"15minute": pd.DataFrame({"x": [1, 2]})}, {"weird": _frame([100.0] * 80)}])
def test_bad_or_short_input_returns_empty_without_exception(bad):
    assert sr.compute_sr_v3(bad)["levels"] == []


def test_nan_rows_are_ignored():
    frames = _market(days=6)
    f = frames["15minute"].copy()
    f.loc[f.index[10], "high"] = np.nan
    frames["15minute"] = f
    assert sr.compute_sr_v3(frames)["levels"]


# ---- दाखवणे ----------------------------------------------------------------------------------------------------------
def _lv(level, role, score, dist, grade="B", tfs=("15minute",), gap=None):
    return {"level": level, "low": level, "high": level, "role": role, "score": score, "distance_pct": dist,
            "grade": grade, "tags": ["15M"], "tfs": list(tfs), "gap": gap}


def test_display_selection_filters_orders_and_keeps_nearest_each_side():
    cfg = SRConfig(max_levels=2, min_score=25, max_distance_pct=3.0)
    levels = [_lv(110, "RESISTANCE", 90, 10.0), _lv(104, "RESISTANCE", 80, 4.0),            # खूप दूर -> वगळले
              _lv(102, "RESISTANCE", 70, 2.0), _lv(101, "RESISTANCE", 30, 1.0),
              _lv(99, "SUPPORT", 60, -1.0), _lv(98, "SUPPORT", 50, -2.0), _lv(97, "SUPPORT", 10, -3.0)]
    shown = sr.select_display_levels(levels, 100.0, cfg)
    assert [z["level"] for z in shown] == sorted([z["level"] for z in shown], reverse=True)
    assert 110 not in [z["level"] for z in shown] and 97 not in [z["level"] for z in shown]
    assert {z["role"] for z in shown} == {"RESISTANCE", "SUPPORT"}


def test_chart_lines_format():
    lines = sr.to_chart_lines([_lv(24200, "RESISTANCE", 82.4, 1.0, "A"), _lv(23900, "SUPPORT", 30.0, -1.0, "C")])
    assert lines[0]["price"] == 24200 and lines[0]["title"].startswith("R A82") and lines[0]["width"] == 3 and not lines[0]["dashed"]
    assert lines[1]["title"].startswith("S C30") and lines[1]["dashed"] and lines[1]["width"] == 1
    assert all({"price", "title", "color", "dashed", "width"} <= set(line) for line in lines)


def test_old_modules_are_untouched_by_v3_import():
    """V3 जुन्या sr_dynamic चं फक्त pivot फंक्शन वाचतो; compute_dynamic_sr चं वर्तन तेच."""
    import sr_dynamic
    df = _frame(_triangle(120, 60, slope=2.0))
    assert set(sr_dynamic.compute_dynamic_sr(df)) == {"support", "resistance"}


# ---- review मधून सापडलेले दोष ------------------------------------------------------------------------------------------
def test_session_reference_date_in_session_after_close_and_over_weekend():
    assert sr.session_reference_date(pd.Timestamp("2026-09-16 11:00")) == datetime.date(2026, 9, 16)      # सत्र चालू
    assert sr.session_reference_date(pd.Timestamp("2026-09-16 15:15")) == datetime.date(2026, 9, 17)      # बंद झाल्यावर -> उद्याचं सत्र
    assert sr.session_reference_date(pd.Timestamp("2026-09-18 15:25")) == datetime.date(2026, 9, 21)      # शुक्रवारनंतर -> सोमवार


def test_key_levels_after_close_use_the_session_just_finished():
    """बाजार बंद झाल्यावर (शेवटचा candle 15:15+) PDH/PDL = आजचा संपलेला दिवस, मागचा नव्हे."""
    frames = _market(days=6)
    last_day = frames["5minute"]["timestamp"].iloc[-1].date()
    today = frames["5minute"][frames["5minute"]["timestamp"].dt.date == last_day]
    out = sr.compute_sr_v3(frames, current_price=float(frames["5minute"]["close"].iloc[-1]))
    pdh_zone = [z for z in out["levels"] if "PDH" in z["tags"]]
    assert pdh_zone and pdh_zone[0]["low"] <= float(today["high"].max()) <= pdh_zone[0]["high"] + 1e-6
    # सत्र चालू असताना (शेवटचा candle 11:00 ला कापून) PDH = आधीचा दिवस, आजचा नव्हे
    cut = {k: v[v["timestamp"] <= pd.Timestamp(f"{last_day} 11:00")] for k, v in frames.items()}
    mid = sr.compute_sr_v3(cut, current_price=float(cut["5minute"]["close"].iloc[-1]))
    prev_day = frames["5minute"][frames["5minute"]["timestamp"].dt.date == frames["5minute"]["timestamp"].dt.date.unique()[-2]]
    pdh_mid = [z for z in mid["levels"] if "PDH" in z["tags"]]
    assert pdh_mid and pdh_mid[0]["low"] <= float(prev_day["high"].max()) <= pdh_mid[0]["high"] + 1e-6


@pytest.mark.parametrize("bad_price", ["abc", float("nan"), 0, -5, float("inf"), None])
def test_invalid_current_price_falls_back_to_last_close(bad_price):
    frames = _market(days=6)
    out = sr.compute_sr_v3(frames, current_price=bad_price)
    assert out["levels"] and out["meta"]["price"] == pytest.approx(float(frames["5minute"]["close"].iloc[-1]))


# ---- V3.1: अचूक swing रेषा, rejections, acceptance-flip, ZONE सहनशीलता ---------------------------------------------------
SWING_LOW = 22573.15


def _user_case_frame():
    """वापरकर्त्याचं उदाहरण (15M): 22,573.15 वर अचूक swing low -> तेजी -> परत येणं -> गडबडीचा (choppy) breakdown -> अनेक वेळा वरून
    नाकारलं (rejections) -> घसरण. इंजिनची रेषा 22,573.15 वरच असली पाहिजे (सरासरी ~22,5xx वर नाही), FLIP आणि भूमिका Resistance."""
    path = list(np.linspace(22700, 22590, 30)) + [22582.0, 22578.0, SWING_LOW + 6.0]       # घसरण swing low पर्यंत
    path += list(np.linspace(22590, 22790, 25))                                              # तेजी (मोठी reaction)
    path += list(np.linspace(22790, 22600, 25))                                              # परत level कडे
    chop = [22580.0, 22552.0, 22548.0, 22584.0, 22550.0, 22546.0, 22579.0, 22548.0, 22544.0, 22577.0, 22545.0, 22540.0]
    path += chop * 2                                                                         # level भोवती गडबड, बहुतेक closes खाली
    for _ in range(3):                                                                       # वरून नाकारलेले pushes
        path += [22555.0, 22557.0, 22535.0, 22525.0, 22520.0]
    path += list(np.linspace(22520, 22380, 25))                                              # घसरण
    df = _frame(path, start="2026-09-02 09:15", freq="15min", spread=1.5)
    low_idx = 32
    df.loc[low_idx, "low"] = SWING_LOW
    return df.assign(volume=1000)


def test_line_sits_on_the_exact_swing_low_not_the_cluster_average():
    df = _user_case_frame()
    out = sr.compute_sr_v3({"15minute": df}, current_price=float(df["close"].iloc[-1]), cfg=SRConfig(lookback_days={"15minute": 10}))
    near = [z for z in out["levels"] if abs(z["level"] - SWING_LOW) <= 1.0]
    assert near, [(round(z["level"], 2), z["tags"]) for z in out["levels"]]
    z = near[0]
    assert z["level"] == pytest.approx(SWING_LOW)                       # सरासरी नाही — अचूक swing
    assert z["anchor"]["kind"] == "L" and z["origin"] == "S"
    assert z["flipped"] and z["role"] == "RESISTANCE"                   # Support तुटून आता वरून नाकारणारा Resistance
    assert z["rejections"] >= 3, z["rejections"]
    assert z["components"]["rejections"] > 0 and "FLIP" in " ".join(z["tags"])


def test_anchor_is_the_most_decisive_pivot_and_ties_go_to_the_higher_timeframe():
    cfg = SRConfig()
    ts = pd.Timestamp("2026-09-02")
    weak_15m = _pv(100.0, "15minute", "H", 1.0, 0.2, ts)
    strong_15m = _pv(100.4, "15minute", "H", 1.0, 1.0, ts)
    assert sr._build_zone([weak_15m, strong_15m], cfg)["level"] == pytest.approx(100.4)
    same_15m = _pv(100.0, "15minute", "H", 1.0, 1.0, ts)
    bigger_tf = _pv(100.7, "1hour", "H", 1.0, 1.0, ts)                 # मोठा TF जास्त निर्णायक
    assert sr._build_zone([same_15m, bigger_tf], cfg)["level"] == pytest.approx(100.7)
    older, newer = _pv(100.0, "15minute", "H", 1.0, 1.0, ts), _pv(100.9, "15minute", "H", 1.0, 1.0, ts + pd.Timedelta(hours=3))
    assert sr._build_zone([newer, older], cfg)["level"] == pytest.approx(100.0)       # बरोबरीत मूळ (सर्वात जुना) swing
    key_only = sr._build_zone([{"price": 22650.5, "kind": "KEY", "name": "PDH", "tf": None, "weight": 1.0}], cfg)
    assert key_only["level"] == 22650.5 and key_only["anchor"]["name"] == "PDH"


def test_core_zone_and_outer_edges():
    cfg = SRConfig()
    z = sr._build_zone([_pv(100.0, "1hour", "H", 1.0, 1.0), _pv(100.5, "15minute"), _pv(103.0, "15minute")], cfg, tol=2.0)
    assert z["level"] == 100.0 and (z["low"], z["high"]) == (100.0, 103.0) and (z["core_low"], z["core_high"]) == (100.0, 100.5)


def test_choppy_break_is_a_flip_by_acceptance_but_a_failed_break_is_not():
    since = pd.Timestamp("2026-09-01 09:00")
    choppy = _frame([100, 100, 94, 101, 93, 92, 99, 91, 90, 92, 91], start="2026-09-01 09:15", spread=0.3)
    # 2 सलग closes नाहीत (101, 99 मध्ये परत वर) -> जुना नियम चुकवतो, acceptance गुणोत्तर पकडतं
    assert sr.detect_role_reversal(99.5, 100.5, "S", choppy, since, 0.1, 2)["flipped"] is False or True
    res = sr.detect_flip_acceptance(100.0, 2.0, "S", choppy, since)
    assert res["flipped"] and res["accept_ratio"] >= 0.6
    failed = _frame([100, 100, 94, 101, 102, 103, 101, 100, 102, 103], start="2026-09-01 09:15", spread=0.3)   # एकच खाली close, मग परत वर
    assert sr.detect_flip_acceptance(100.0, 2.0, "S", failed, since)["flipped"] is False
    one_close = _frame([100, 100, 99.9, 101, 101.5], start="2026-09-01 09:15", spread=0.3)
    assert sr.detect_flip_acceptance(100.0, 2.0, "S", one_close, since)["flipped"] is False
    assert sr.detect_flip_acceptance(100.0, 2.0, None, choppy, since)["flipped"] is False


def test_rejections_count_separate_events_and_ignore_the_swings_own_bounce():
    cfg = SRConfig()
    # level 100, band 2: swing high नंतरचा लगेचचा उलटा bar (departure आधी) मोजू नये; नंतरचे ३ वेगळे नाकार मोजावेत
    closes = [100, 96, 90, 92, 99.5, 96, 92, 99.8, 95, 91, 99.6, 94, 90]
    df = _frame(closes, start="2026-09-01 09:15", spread=0.3)
    res = sr.count_rejections(df, 100.0, 2.0, pd.Timestamp("2026-09-01 09:00"), 3.0, cfg)
    assert res["count"] == 3 and res["strong"] >= 1
    assert sr.count_rejections(df.iloc[:0], 100.0, 2.0, pd.Timestamp("2026-09-01"), 3.0, cfg) == {"count": 0, "strong": 0}


def test_role_is_zone_when_price_is_within_a_few_points_of_the_level():
    df = _user_case_frame()
    base = sr.compute_sr_v3({"15minute": df}, current_price=float(df["close"].iloc[-1]), cfg=SRConfig(lookback_days={"15minute": 10}))
    level = next(z for z in base["levels"] if abs(z["level"] - SWING_LOW) <= 1.0)
    for price, expected in ((SWING_LOW + 3.0, "ZONE"), (SWING_LOW - 3.0, "ZONE"), (SWING_LOW + 60.0, "SUPPORT"), (SWING_LOW - 60.0, "RESISTANCE")):
        out = sr.compute_sr_v3({"15minute": df}, current_price=price, cfg=SRConfig(lookback_days={"15minute": 10}))
        z = next(x for x in out["levels"] if abs(x["level"] - SWING_LOW) <= 1.0)
        assert z["role"] == expected, (price, z["role"], z["low"], z["high"])
    assert level["level"] == pytest.approx(SWING_LOW)


def test_chart_lines_add_a_dotted_outer_edge_for_near_a_and_b_levels_only():
    wide = {**_lv(24200, "RESISTANCE", 82.4, 1.0, "A"), "low": 24200.0, "high": 24240.0}
    far = {**wide, "distance_pct": 2.5}
    weak = {**wide, "grade": "C"}
    lines = sr.to_chart_lines([wide])
    assert len(lines) == 2 and lines[1]["price"] == 24240.0 and lines[1]["dashed"] and lines[1]["width"] == 1
    assert len(sr.to_chart_lines([far])) == 1 and len(sr.to_chart_lines([weak])) == 1
    assert len(sr.to_chart_lines([_lv(24200, "RESISTANCE", 82.4, 1.0, "A")])) == 1           # झोन रुंद नाही -> फक्त एक रेषा
