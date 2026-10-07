"""tests/test_elliott_e4.py — Elliott E4: backtest (fill पुढच्या bar च्या open वर, P&L / R / खर्च, shadow sizing, re-entry,
truncation invariance), model premium (causal IV), golden-file matcher (must / must_not / rejections) आणि golden data वर
regression (data असेल तरच)."""
import os
from types import SimpleNamespace as NS

import numpy as np
import pandas as pd
import pytest

from elliott import backtest as BT
from elliott import golden as GD
from elliott import settings as S
from elliott.trigger import Scanner

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _cfg(**k):
    c, e = S.validate(k)
    assert not e, e
    return c


S0 = _cfg()
SB = _cfg(c_min_by_dte=[0.0] * 5, min_credit_pts=0.0)


@pytest.fixture(scope="module")
def run2019():
    d = pd.read_parquet(os.path.join(ROOT, "data", "nifty50_1min.parquet"))
    d = d[(d["timestamp"] >= "2019-03-01") & (d["timestamp"] <= "2019-08-31 23:59")].reset_index(drop=True)
    sc = Scanner(d, S0)
    times = sc.times()
    sigs = BT.collect_signals(sc, times)
    bt = BT.Backtest(d, SB, scanner=sc, replay=sigs, trade_from="2019-05-01")
    bt.run(times)
    return d, sc, times, sigs, bt


def test_fill_next_bar_open_and_accounting(run2019):
    d, sc, times, sigs, bt = run2019
    assert bt.closed, "guard बंद असताना 4 महिन्यांत एकही trade नाही"
    fine_starts = set(sc.frames["5m"]["timestamp"])
    for tr in bt.closed:
        fr = sc.frames[tr.tf]
        assert tr.entry_ts == fr["timestamp"].iloc[tr.entry_idx] and tr.entry_spot == fr["open"].iloc[tr.entry_idx]
        assert tr.entry_ts >= tr.sig.t and tr.exit_ts > tr.entry_ts                 # fill signal close नंतर
        if tr.exit_reason not in ("emergency_short_strike", "expiry_settle", "end_of_data", "premium_stop"):
            assert tr.exit_ts in fine_starts                                       # निर्णय bar close, fill पुढच्या bar च्या open वर
            assert tr.exit_ts.time() != pd.Timestamp("15:30").time()
        assert tr.entry_ts >= pd.Timestamp("2019-05-01")
        p = tr.plan
        assert 0 < p["credit_filled"] < p["width"] and tr.entry_cost > 0
        assert tr.realized <= (p["credit_filled"]) * p["qty"]                     # credit पेक्षा जास्त नफा अशक्य
        assert tr.realized >= -(p["width"] - p["credit_filled"]) * p["qty"] - 5 * tr.entry_cost   # max loss + खर्च
        assert (p["short_k"] < tr.entry_spot) if tr.sig.trade_dir > 0 else (p["short_k"] > tr.entry_spot)
    r = bt.results()
    assert set(r["sized"]) <= {True, False} and np.isfinite(r["R"]).all() and (r["R"] >= -1.2).all()


def test_shadow_trades_do_not_count_in_portfolio(run2019):
    _, _, _, _, bt = run2019
    r = bt.results()
    for day, pnl in bt.day_pnl.items():
        sized = r[(r["sized"]) & (pd.to_datetime(r["exit"]).dt.date == day)]["pnl"].sum()
        assert pnl == pytest.approx(sized, abs=1e-6)                              # day_pnl मध्ये फक्त sized


def test_backtest_truncation_invariance(run2019):
    d, sc, times, sigs, bt = run2019
    cut = pd.Timestamp("2019-07-15 15:30")
    d2 = d[d["timestamp"] < cut].reset_index(drop=True)
    sc2 = Scanner(d2, S0)
    t2 = sc2.times()
    bt2 = BT.Backtest(d2, SB, scanner=sc2, replay=BT.collect_signals(sc2, t2), trade_from="2019-05-01")
    bt2.run(t2)
    a = [(x.sig.t, x.entry_ts, x.exit_ts, x.exit_reason, round(x.realized, 6)) for x in bt.closed if x.exit_ts < cut]
    b = [(x.sig.t, x.entry_ts, x.exit_ts, x.exit_reason, round(x.realized, 6)) for x in bt2.closed if x.exit_ts < cut]
    assert a == b


def test_model_iv_is_causal_and_missing_early():
    days = pd.bdate_range("2019-01-01", periods=40)
    rows = []
    for i, dday in enumerate(days):
        px = 100 * np.exp(0.01 * np.sin(i))
        rows += [(dday + pd.Timedelta(hours=9, minutes=15 + m), px) for m in range(375)]
    df = pd.DataFrame(rows, columns=["timestamp", "close"])
    from elliott import contracts as CT
    cal = CT.TradingCalendar.from_spot(df)
    mp = BT.ModelPricer(df, S0, cal)
    assert mp.iv(days[5].date()) is None                                          # 20 दिवस आधी नाही
    v = mp.iv(days[30].date())
    df2 = df.copy()
    df2.loc[df2["timestamp"].dt.date == days[30].date(), "close"] *= 1.5           # त्याच दिवसाचा बदल IV वर परिणाम नाही
    assert BT.ModelPricer(df2, S0, cal).iv(days[30].date()) == pytest.approx(v)


# ---------------------------------------------------------------- golden matcher
def gsig(t, direction, extreme, setup="S6a", tier="B", inv=22217.0, close=None):
    return NS(t=pd.Timestamp(t), direction=direction, extreme=extreme, comp=(0, 0, 0, close if close is not None else extreme),
              setup=setup, tier=tier, degree=1, hard_inv=inv)


def test_golden_matcher_strictness():
    exp = GD.load_expectations()
    wrong_setup = [gsig("2026-10-05 12:30", "bull_put", 22398.0, setup="S6b")]       # T7 ला S6a हवा
    assert {r["id"]: r for r in GD.evaluate(wrong_setup, exp)}["T7"]["status"] == "FAIL"
    far = [gsig("2026-10-05 12:30", "bull_put", 22420.0)]                            # ±15 बाहेर
    assert {r["id"]: r for r in GD.evaluate(far, exp)}["T7"]["status"] == "FAIL"
    t6 = [gsig("2026-10-05 10:00", "bear_call", 22700.0, "S1", "A")]                 # किंमत वेगळी तरी A-end bear call ⇒ FAIL
    assert {r["id"]: r for r in GD.evaluate(t6, exp)}["T6"]["status"] == "FAIL"
    gap = [gsig("2026-10-06 09:45", "bull_put", 22600.0)]
    assert {r["id"]: r for r in GD.evaluate(gap, exp)}["R-gap-1006"]["status"] == "FAIL"


def test_golden_matcher_levels():
    exp = GD.load_expectations()
    good = [gsig("2026-10-05 12:30", "bull_put", 22398.0), gsig("2026-10-05 13:35", "bull_put", 22480.0, "S13", inv=22396.0),
            gsig("2026-09-29 13:20", "bull_put", 22625.0, "S7", "B"), gsig("2026-09-30 11:00", "bear_call", 22803.0, "S7", "A"),
            gsig("2026-10-01 10:00", "bear_call", 22600.0, "S2", "A")]
    rows = {r["id"]: r for r in GD.evaluate(good, exp)}
    assert all(rows[k]["status"] == "PASS" for k in ("T2", "T3", "T4", "T7", "T8")), rows
    assert rows["T6"]["status"] == "PASS" and rows["T1"]["status"] == "REPORT"
    bad = good + [gsig("2026-10-05 09:55", "bear_call", 22600.0, "S1", "A"), gsig("2026-10-06 09:45", "bear_call", 22614.0)]
    rows = {r["id"]: r for r in GD.evaluate(bad, exp)}
    assert rows["T6"]["status"] == "FAIL" and rows["R-1006-0940"]["status"] == "FAIL"   # A-end bear call / support वर bear call
    miss = {r["id"]: r for r in GD.evaluate(good[1:], exp)}
    assert miss["T7"]["status"] == "FAIL"
    gap = {r["id"]: r for r in GD.evaluate(good + [gsig("2026-09-28 09:30", "bull_put", 22700.0)], exp)}
    assert gap["R-gap-0928"]["status"] == "FAIL"


@pytest.mark.skipif(GD.golden_csv() is None, reason="golden 1m data (trade-data) अजून नाही — VPS export नंतर")
def test_golden_regression_on_real_data():
    from elliott import data_policy as DP
    d = DP.filter_allowed(GD.load_golden(GD.golden_csv()), "golden")
    sc = Scanner(d, S0)
    sigs = []
    for t in sc.times():
        out = sc.step(t)
        if t.date() >= GD.GOLDEN_FROM:
            sigs += out
    rows = GD.evaluate(sigs, reasons=sc.reasons)
    fails = [r for r in rows if r["status"] == "FAIL"]
    assert not fails, "\n".join(f"{r['id']} ({r['level']}): {r['detail']}" for r in fails)


def test_emergency_spot_gap_pricing():
    assert BT.emergency_spot(22100.0, 22150, 1) == 22100.0                          # gap ने strike खाली उघडलं ⇒ open
    assert BT.emergency_spot(22200.0, 22150, 1) == pytest.approx(22149.95)
    assert BT.emergency_spot(23300.0, 23250, -1) == 23300.0 and BT.emergency_spot(23200.0, 23250, -1) == pytest.approx(23250.05)


def test_exits_not_blocked_by_daily_loss_and_entries_are(run2019):
    d, sc, times, sigs, _ = run2019
    s = _cfg(c_min_by_dte=[0.0] * 5, min_credit_pts=0.0, max_daily_loss_pct=0.1)
    bt = BT.Backtest(d, s, scanner=sc, replay=sigs, trade_from="2019-05-01")
    for day in pd.bdate_range("2019-05-01", "2019-08-31"):
        bt.day_pnl[day.date()] = -1e9                                              # दररोज daily loss आधीच गाठलेला
    bt.run(times)
    assert not any(t.sized for t in bt.closed)                                     # sized entries थांबल्या
    assert all(t.exit_reason for t in bt.closed) and not bt.open                   # shadow trades चे exits चालू राहिले


def test_reentry_rules():
    bt = BT.Backtest.__new__(BT.Backtest)
    bt.s, bt.open, bt.key_hist = _cfg(max_reentries=1), [], {}
    sig = NS(key=("k",))
    assert bt._key_filter(sig) is None
    bt.key_hist[sig.key] = ["soft_stop"]
    assert bt._key_filter(sig) is None                                             # soft stop ⇒ एकदा re-entry
    bt.key_hist[sig.key] = ["soft_stop", "soft_stop"]
    assert bt._key_filter(sig) == "no_reentry"                                     # max_reentries ओलांडले
    bt.key_hist[sig.key] = ["premium_stop"]
    assert bt._key_filter(sig) == "no_reentry"
    bt.s = _cfg(reentry_after_premium_stop=True)
    assert bt._key_filter(sig) is None
    bt.key_hist[sig.key] = ["hard_inv"]
    assert bt._key_filter(sig) == "no_reentry"                                     # hard inv नंतर कधीच नाही


def test_random_replay_shape(run2019):
    import importlib.util
    spec = importlib.util.spec_from_file_location("rep", os.path.join(ROOT, "research", "elliott_backtest_report.py"))
    rep = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rep)
    _, sc, _, sigs, _ = run2019
    sub = {t: v for t, v in sigs.items() if t >= pd.Timestamp("2019-05-01")}
    rnd = rep.random_replay(sub, sc, pd.Timestamp("2019-05-01"), pd.Timestamp("2019-08-31"), reps=3)
    flat = [x for v in rnd.values() for x in v]
    assert len(flat) == 3 * sum(len(v) for v in sub.values())
    for x in flat:
        fr = sc.frames[x.ttf]
        assert fr["bar_end"].iloc[x.ttf_idx] == x.t and pd.Timestamp("09:30").time() <= x.t.time() <= pd.Timestamp("14:45").time()
        assert (x.hard_inv < fr["close"].iloc[x.ttf_idx]) if x.trade_dir > 0 else (x.hard_inv > fr["close"].iloc[x.ttf_idx])
    assert len({x.key for x in flat}) == len(flat)


def test_model_iv_varies_and_carries_over_short_days():
    days = pd.bdate_range("2019-01-01", periods=45)
    rows = []
    rng = np.random.default_rng(1)
    px = 100.0
    for i, dday in enumerate(days):
        px *= np.exp(rng.normal(0, 0.01 if i < 30 else 0.03))
        n = 60 if i == 40 else 375                                                 # दिवस 40 = मुहूर्त (लहान session)
        rows += [(dday + pd.Timedelta(hours=9, minutes=15 + m), px) for m in range(n)]
    df = pd.DataFrame(rows, columns=["timestamp", "close"])
    from elliott import contracts as CT
    cal = CT.TradingCalendar.from_spot(df)
    mp = BT.ModelPricer(df, S0, cal)
    assert mp.iv(days[44].date()) > mp.iv(days[29].date())                         # volatility वाढली ⇒ IV वाढला
    assert mp.iv(days[40].date()) is not None                                      # लहान session ⇒ आधीचा IV
