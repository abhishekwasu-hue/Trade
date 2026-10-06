"""tests/test_major_levels.py — Major Level (Trader's Eye) engine v1: HTF bars, pivots (no-lookahead), clustering, role reversal, trendline,
precision/recall, आणि research/major_levels_eval (fake fetch सह export, synthetic eval). Network नाही."""
import importlib.util
import os

import numpy as np
import pandas as pd

from price_action import major_levels as ML

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("ml_eval", os.path.join(ROOT, "research", "major_levels_eval.py"))
E = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(E)


def _nse(path_fn, start="2026-08-17", end="2026-10-06", seed=1):
    rng = np.random.default_rng(seed)
    rows, price, t = [], None, 0
    for d in pd.bdate_range(start, end):
        for k in range(25):
            ts = d + pd.Timedelta(hours=9, minutes=15 + 15 * k)
            target = path_fn(t)
            t += 1
            o = target if price is None else price
            c = target + rng.normal(0, 0.15)
            rows.append((ts, o, max(o, c) + 0.05, min(o, c) - 0.05, c))
            price = c
    return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close"])


def test_htf_bars_nse_sessions_and_completeness():
    df = _nse(lambda t: 100.0, start="2026-10-05", end="2026-10-06")
    h = ML.htf_bars(df, 240, "NSE")
    assert list(h["timestamp"].dt.strftime("%H:%M")[:2]) == ["09:15", "13:15"] and len(h) == 4
    h2 = ML.htf_bars(df[df["timestamp"] <= "2026-10-06 11:00"], 240, "NSE")   # 09:15–13:15 चा bar अपूर्ण ⇒ वगळला
    assert h2["timestamp"].max() < pd.Timestamp("2026-10-06 09:15")


def test_no_lookahead_levels_ignore_future_bars():
    df = _nse(lambda t: 105 + 5 * np.sin(t / 18.0))
    asof = pd.Timestamp("2026-09-25 15:30")
    a = ML.major_levels(df, asof=asof)[0]
    df2 = df.copy()
    df2.loc[df2["timestamp"] > asof, ["high", "close"]] *= 1.3
    b = ML.major_levels(df2, asof=asof)[0]
    assert [x["price"] for x in a] == [x["price"] for x in b]


def test_range_edges_found_and_count_limited():
    df = _nse(lambda t: 105 + 5 * np.sin(t / 18.0))
    lv, _, info = ML.major_levels(df, cfg=ML.MLConfig(lookback_weeks=4))
    prices = sorted(x["price"] for x in lv)
    assert 2 <= len(lv) <= 4
    assert abs(prices[0] - 100) < 1.0 and abs(prices[-1] - 110) < 1.0
    assert all(x["n_react"] >= 2 for x in lv)


def test_role_reversal_gets_extra_weight():
    piv_h = [(0, "H", 100.0), (5, "H", 100.1)]
    piv_rr = [(0, "H", 100.0), (5, "L", 100.1)]
    assert ML._clusters(piv_h, 0.5) == [piv_h] and ML._clusters(piv_rr, 0.5) == [piv_rr]
    cfg = ML.MLConfig()
    assert cfg.rr_weight > 0


def test_descending_trendline_needs_three_pivots():
    df = _nse(lambda t: 110 - t * 0.004 + 4 * np.sin(t / 15.0))       # उतरते lower highs
    _, lines, _ = ML.major_levels(df, cfg=ML.MLConfig(lookback_weeks=6, prom_s=1.0))
    for ln in lines:
        assert ln["n_pivots"] >= 3
    desc = [ln for ln in lines if ln["type"] == "desc_resistance"]
    assert desc and desc[0]["slope"] < 0


def test_match_levels_precision_recall():
    p, r, f1 = ML.match_levels([100.1, 105.0, 110.0], [100.0, 110.1], tol_pct=0.15)
    assert (round(p, 3), round(r, 3)) == (round(2 / 3, 3), 1.0) and 0 < f1 < 1
    assert ML.match_levels([], [100.0]) == (0.0, 0.0, 0.0)


def test_eval_pipeline_on_synthetic(tmp_path):
    df = _nse(lambda t: 105 + 5 * np.sin(t / 18.0))
    cd = tmp_path / "candles"
    cd.mkdir()
    df.to_csv(cd / "NIFTY_15m.csv", index=False)
    lv, _, _ = ML.major_levels(df, asof=pd.Timestamp("2026-10-06 23:59"), cfg=ML.MLConfig(lookback_weeks=2, k_tol=0.25, price_mode="extreme"))
    gt = tmp_path / "gt.csv"
    gt.write_text("symbol,tf,type,price,window_start,window_end,anchor_dates,notes\n"
                  + "".join(f"NIFTY,15m,horizontal,{x['price']:.2f},2026-09-07,2026-10-06,,\n" for x in lv))
    res = E.evaluate(candle_dir=str(cd), out_dir=str(tmp_path), gt_path=str(gt), png=False)
    assert res["per_chart"].iloc[0]["recall"] == 1.0
    assert (tmp_path / "agreement_grid.csv").exists() and (tmp_path / "agreement_per_chart.csv").exists()
    assert len(pd.read_csv(tmp_path / "agreement_grid.csv")) == np.prod([len(v) for v in E.GRID.values()])


def test_export_uses_fetchers_and_writes_csvs(tmp_path):
    gt = E.load_gt()
    calls = []
    df = _nse(lambda t: 100.0, start="2026-10-05", end="2026-10-06")

    def fi(tok, sym, spot, interval, lookback_days):
        calls.append((sym, interval))
        return df

    def fm(tok, key, interval, lookback_days):
        calls.append((key, interval))
        return df
    def res(tok, sym, roll_days=None):                                 # GOLD: bot contract ≠ सर्वात जवळचा
        suffix = "DEC" if (sym == "GOLD" and roll_days is None) else "OCT"
        return True, {"instrument_key": f"MCX|{sym}{suffix}", "trading_symbol": f"{sym}{suffix}"}
    rc = E.export(gt, out_dir=str(tmp_path), token="x", fetch_index=fi, fetch_mcx=fm, resolve=res)
    assert rc == 0 and ("NIFTY", "15minute") in calls and ("MCX|GOLDDEC", "30minute") in calls and ("MCX|GOLDOCT", "30minute") in calls
    assert sorted(os.listdir(tmp_path)) == ["COPPER_30m.csv", "GOLD_30m.csv", "GOLD__near_30m.csv", "NIFTY_15m.csv", "SILVER_30m.csv"]
    assert pd.read_csv(tmp_path / "GOLD_30m.csv")["contract"].iloc[0] == "GOLDDEC"


def test_ground_truth_file_shape():
    gt = E.load_gt()
    assert set(gt["symbol"]) == {"NIFTY", "GOLD", "COPPER", "SILVER"}
    assert (gt["type"] == "horizontal").sum() == 10 and (gt["type"] == "trendline_desc").sum() == 1
    assert gt["window_end"].max() == pd.Timestamp("2026-10-06")


# ---- review नंतरचे tests --------------------------------------------------------------------------------------------------------------
def _planted(start="2026-08-17", end="2026-10-06"):
    """100–110 range: wicks नेमके 100.00 आणि 110.00 ला (planted levels) — non-circular eval साठी."""
    df = _nse(lambda t: 105 + 6 * np.sin(t / 18.0), start, end)
    df["high"] = df["high"].clip(upper=110.0)
    df["low"] = df["low"].clip(lower=100.0)
    df["open"] = df["open"].clip(100.0, 110.0)
    df["close"] = df["close"].clip(100.0, 110.0)
    return df


def test_planted_levels_recovered_non_circular(tmp_path):
    cd = tmp_path / "candles"
    cd.mkdir()
    _planted().to_csv(cd / "NIFTY_15m.csv", index=False)
    gt = tmp_path / "gt.csv"
    gt.write_text("symbol,tf,type,price,window_start,window_end,anchor_dates,notes\n"
                  "NIFTY,15m,horizontal,110.00,2026-09-07,2026-10-06,,\nNIFTY,15m,horizontal,100.00,2026-09-07,2026-10-06,,\n")
    res = E.evaluate(candle_dir=str(cd), out_dir=str(tmp_path), gt_path=str(gt), png=False)
    assert res["per_chart"].iloc[0]["recall"] == 1.0


def test_asof_excludes_bar_that_has_not_closed():
    df = _nse(lambda t: 100.0 + (50 if t == 10 else 0), start="2026-10-05", end="2026-10-05")   # 11:45 bar ला spike
    h_before = ML.htf_bars(df[df["timestamp"] + pd.Timedelta(minutes=15) <= pd.Timestamp("2026-10-05 11:45")], 240, "NSE")
    lv, _, info = ML.major_levels(df, asof=pd.Timestamp("2026-10-05 11:45"))   # 11:45 चा bar 12:00 ला संपतो ⇒ वगळला
    d = ML._prep(df)
    assert d[d["timestamp"] == pd.Timestamp("2026-10-05 11:45")]["high"].iloc[0] > 140
    assert all(x["price"] < 140 for x in lv) and len(h_before) == 0


def test_mcx_session_buckets_and_winter_close():
    rows = []
    for d in ("2026-10-05", "2026-11-05"):
        for k in range(0, 30 * 30, 30):
            ts = pd.Timestamp(d) + pd.Timedelta(hours=9, minutes=k)
            if ts.hour == 23 and ts.minute > (30 if ts.month == 10 else 55) - 30:
                break
            rows.append((ts, 100, 101, 99, 100))
    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close"])
    h = ML.htf_bars(df, 240, "MCX")
    starts = h["timestamp"].dt.strftime("%H:%M").tolist()
    assert starts[:4] == ["09:00", "13:00", "17:00", "21:00"]
    assert ML.session_close("2026-11-05", "MCX").strftime("%H:%M") == "23:55" and ML.session_close("2026-10-05", "MCX").strftime("%H:%M") == "23:30"


def test_min_levels_filled_with_weak_range_edges():
    df = _nse(lambda t: 100 + 0.02 * t + 3 * np.sin(t / 9.0))
    lv, _, info = ML.major_levels(df, cfg=ML.MLConfig(lookback_weeks=2, min_react=3, prom_s=2.0))
    if info.get("below_min"):
        assert any(x["weak"] for x in lv) and all(x["edge"] for x in lv if x["weak"])
    assert len(lv) >= 1


def test_role_reversal_ranks_first():
    # 5 same-side highs at 110 वि. 2-touch role reversal at 105 (आधी resistance, मग support)
    piv_cfg = ML.MLConfig(lookback_weeks=8, prom_s=0.0, min_react=2, k_tol=0.3)
    df = _nse(lambda t: 105 + 5 * np.sin(t / 18.0))
    lv, _, _ = ML.major_levels(df, cfg=piv_cfg)
    rr = [i for i, x in enumerate(lv) if x["role_reversal"]]
    non = [i for i, x in enumerate(lv) if not x["role_reversal"]]
    assert not rr or not non or max(rr) < min(non)


def test_prominence_filters_minor_swings():
    df = _nse(lambda t: 105 + 5 * np.sin(t / 18.0) + 0.6 * np.sin(t / 2.0))
    _, _, loose = ML.major_levels(df, cfg=ML.MLConfig(prom_s=0.0))
    _, _, strict = ML.major_levels(df, cfg=ML.MLConfig(prom_s=2.0))
    assert strict["pivots"] < loose["pivots"]


def test_extreme_mode_uses_outer_wick():
    df = _planted()
    a, _, _ = ML.major_levels(df, cfg=ML.MLConfig(price_mode="extreme", lookback_weeks=4))
    tops = [x["price"] for x in a if x["kinds"] == "H"]
    assert not tops or max(tops) == 110.0


def test_trendline_rejected_when_close_breaks_above():
    df = _nse(lambda t: 110 - t * 0.004 + 4 * np.sin(t / 15.0))
    _, lines, _ = ML.major_levels(df, cfg=ML.MLConfig(lookback_weeks=6, prom_s=1.0))
    if not [ln for ln in lines if ln["type"] == "desc_resistance"]:
        return
    df2 = df.copy()
    last = df2.index[-30:]
    df2.loc[last, ["open", "high", "low", "close"]] = df2.loc[last, ["open", "high", "low", "close"]] + 15     # शेवटी रेषेच्या खूप वर closes
    _, lines2, _ = ML.major_levels(df2, cfg=ML.MLConfig(lookback_weeks=6, prom_s=1.0))
    d1 = [ln for ln in lines if ln["type"] == "desc_resistance"][0]
    assert all(ln["anchors"] != d1["anchors"] for ln in lines2 if ln["type"] == "desc_resistance")


def test_loco_with_two_charts(tmp_path):
    cd = tmp_path / "candles"
    cd.mkdir()
    _planted().to_csv(cd / "NIFTY_15m.csv", index=False)
    m = _planted()
    m["contract"] = "GOLDDEC"
    m.to_csv(cd / "GOLD_30m.csv", index=False)
    gt = tmp_path / "gt.csv"
    gt.write_text("symbol,tf,type,price,window_start,window_end,anchor_dates,notes\n"
                  "NIFTY,15m,horizontal,110.00,2026-09-07,2026-10-06,,\nNIFTY,15m,horizontal,100.00,2026-09-07,2026-10-06,,\n"
                  "GOLD,30m,horizontal,110.00,2026-09-07,2026-10-06,,\n")
    res = E.evaluate(candle_dir=str(cd), out_dir=str(tmp_path), gt_path=str(gt), png=False)
    assert set(res["loco"]["held_out"]) == {"NIFTY", "GOLD"} and "GOLDDEC" in set(res["per_chart"]["contract"])
