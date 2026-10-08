"""tests/test_elliott_e3.py — Elliott E3: expiry calendar / निवड (दुरुस्ती 2), DTE, lot, BS pricing, date-wise costs (STT 0.15%
1 Apr 2026 पासून), strike सूत्र (spec §10 worked example), credit guard / fail actions, sizing, exit priority (§9) आणि
"exits कधीच block नाहीत"."""
import datetime as dt
from types import SimpleNamespace as NS

import pandas as pd
import pytest

from elliott import contracts as CT
from elliott import costs as CO
from elliott import exits as EX
from elliott import pricing as PR
from elliott import settings as S
from elliott import strikes as SK


def _cfg(**k):
    c, e = S.validate(k)
    assert not e, e
    return c


S0 = _cfg()


def weekdays(a, b, minus=()):
    d, out = pd.Timestamp(a).date(), []
    while d <= pd.Timestamp(b).date():
        if d.weekday() < 5 and d not in {pd.Timestamp(x).date() for x in minus}:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


D = lambda x: pd.Timestamp(x).date()                                               # noqa: E731


# ---------------------------------------------------------------- expiry calendar / निवड
def test_rule_expiries_tuesday_era_and_holiday_shift():
    cal = CT.TradingCalendar(weekdays("2026-09-01", "2026-11-30", minus=["2026-10-02", "2026-10-20"]))
    ex = dict(CT.rule_expiries(cal, "2026-09-15", "2026-10-31"))
    assert ex[D("2026-09-29")] == "monthly" and ex[D("2026-10-06")] == "weekly"
    assert D("2026-10-19") in ex and D("2026-10-20") not in ex                     # Tuesday सुट्टी ⇒ आधीचा trading day
    assert ex[D("2026-10-27")] == "monthly"


def test_rule_expiries_thursday_era_and_pre_weekly():
    cal = CT.TradingCalendar(weekdays("2018-01-01", "2024-12-31"))
    ex = {d: k for d, k in CT.rule_expiries(cal, "2018-03-01", "2018-04-30") if D("2018-03-01") <= d <= D("2018-04-30")}
    assert set(ex) == {D("2018-03-29"), D("2018-04-26")} and set(ex.values()) == {"monthly"}   # weekly आधी फक्त monthly
    ex2 = {d: k for d, k in CT.rule_expiries(cal, "2024-10-01", "2024-10-31") if d.month == 10 and d.year == 2024}
    assert D("2024-10-03") in ex2 and ex2[D("2024-10-31")] == "monthly" and all(d.weekday() == 3 for d in ex2)


def test_choose_golden_days():
    cal = CT.TradingCalendar(weekdays("2026-09-01", "2026-11-30", minus=["2026-10-02"]))
    book = CT.ExpiryBook(cal, start="2026-09-01", end="2026-11-30")
    assert book.choose(pd.Timestamp("2026-09-28 10:00"), S0)[0] == D("2026-09-29")   # T1
    assert book.choose(pd.Timestamp("2026-09-29 13:00"), S0)[0] == D("2026-10-06")   # T2: आज expiry ⇒ पुढची
    assert book.choose(pd.Timestamp("2026-10-06 09:45"), S0)[0] == D("2026-10-13")   # T9
    assert book.choose(pd.Timestamp("2026-10-05 12:30"), S0)[0] == D("2026-10-06")   # T7/T8
    assert book.choose(pd.Timestamp("2026-10-05 12:30"), S0, skip=1)[0] == D("2026-10-13")
    assert book.choose(pd.Timestamp("2026-10-05"), _cfg(min_dte_override=2))[0] == D("2026-10-13")


def test_bhavcopy_book_respects_listing_date():
    cal = CT.TradingCalendar(weekdays("2026-09-01", "2026-11-30"))
    bh = pd.DataFrame({"expiry": [D("2026-10-06"), D("2026-10-13")], "kind": ["weekly", "weekly"],
                       "first_seen": [D("2026-09-01"), D("2026-10-07")]})
    book = CT.ExpiryBook(cal, bh)
    assert book.source == "bhavcopy"
    assert book.choose(pd.Timestamp("2026-10-06 10:00"), S0) is None               # 13 Oct अजून listed नाही (causal)
    assert book.choose(pd.Timestamp("2026-10-07 10:00"), S0)[0] == D("2026-10-13")


def test_dte_days_and_fraction():
    cal = CT.TradingCalendar(weekdays("2026-09-01", "2026-11-30", minus=["2026-10-02"]))
    assert CT.dte_days(cal, D("2026-10-05"), D("2026-10-06")) == 1                  # Monday → Tuesday
    assert CT.dte_frac(cal, pd.Timestamp("2026-10-05 12:30"), D("2026-10-06")) == pytest.approx((180 + 375) / 375)
    assert CT.dte_frac(cal, pd.Timestamp("2026-10-05 12:30"), D("2026-10-06"), "whole_days") == 1.0
    assert CT.dte_days(cal, D("2026-10-01"), D("2026-10-06")) == 2                  # 2 Oct सुट्टी ⇒ फक्त 5 व 6 Oct
    assert CT.dte_days(cal, D("2026-10-06"), D("2026-10-06")) == 0


def test_lot_size_by_expiry_boundaries_and_bhav_override():
    assert CT.lot_size("2019-06-27") == 75 and CT.lot_size("2022-06-30") == 50
    assert CT.lot_size("2024-04-25") == 50 and CT.lot_size("2024-05-02") == 25          # review: 26 Apr 2024 ⇒ 25
    assert CT.lot_size("2024-11-14") == 25 and CT.lot_size("2024-11-21") == 75
    assert CT.lot_size("2025-12-30") == 75 and CT.lot_size("2026-01-06") == 65          # key = expiry (6 Jan weekly पासून)
    assert CT.lot_size("2026-10-06", {D("2026-10-06"): 75.0}) == 75


def test_calendar_from_spot_drops_muhurat_and_weekend_sessions():
    rows = []
    for d in weekdays("2021-10-25", "2021-11-12", minus=["2021-11-05"]):
        n = 60 if d == D("2021-11-04") else 375                                   # 4 Nov 2021 = दिवाळी मुहूर्त (1 तास)
        rows += [pd.Timestamp(d) + pd.Timedelta(hours=9, minutes=15 + i) for i in range(n)]
    rows += [pd.Timestamp("2021-10-31 18:15") + pd.Timedelta(minutes=i) for i in range(60)]   # रविवार special session
    cal = CT.TradingCalendar.from_spot(pd.DataFrame({"timestamp": rows}))
    assert not cal.is_trading(D("2021-11-04")) and not cal.is_trading(D("2021-10-31"))
    ex = dict(CT.rule_expiries(cal, "2021-10-25", "2021-11-12"))
    assert D("2021-11-03") in ex and D("2021-11-04") not in ex                      # review H1: प्रत्यक्ष expiry 3 Nov
    book = CT.ExpiryBook(cal, start="2021-10-25", end="2021-11-12")
    assert book.choose(pd.Timestamp("2021-11-03 10:00"), S0)[0] == D("2021-11-11")
    assert CT.dte_days(cal, D("2021-11-01"), D("2021-11-03")) == 2


def test_rule_mode_weekly_not_before_listing():
    cal = CT.TradingCalendar(weekdays("2019-01-01", "2019-03-31"))
    book = CT.ExpiryBook(cal, start="2019-01-01", end="2019-03-31")
    assert book.choose(pd.Timestamp("2019-02-08 10:00"), S0)[0] == D("2019-02-28")     # 14 Feb weekly 11 Feb ला listed
    assert book.choose(pd.Timestamp("2019-02-12 10:00"), S0)[0] == D("2019-02-14")


# ---------------------------------------------------------------- pricing
def test_bs_parity_iv_roundtrip_delta():
    S_, K, T, r, sig = 22400.0, 22200.0, 1.48 / 252, 0.065, 0.13
    c, p = PR.price(S_, K, T, r, sig, "CE"), PR.price(S_, K, T, r, sig, "PE")
    import math
    assert c - p == pytest.approx(S_ - K * math.exp(-r * T), abs=1e-6)
    assert PR.implied_vol(p, S_, K, T, r, "PE") == pytest.approx(sig, abs=1e-5)
    assert -0.5 < PR.delta(S_, K, T, r, sig, "PE") < 0 < PR.delta(S_, K, T, r, sig, "CE") < 1
    assert PR.price(S_, K, 0, r, sig, "PE") == 0.0 and PR.implied_vol(0.0, S_, K, T, r, "PE") is None


# ---------------------------------------------------------------- costs
def test_stt_dates_and_sides():
    assert CO.rates("2016-05-31")["stt"] == 0.00017 and CO.rates("2016-06-01")["stt"] == 0.0005
    assert CO.rates("2026-03-31")["stt"] == 0.001 and CO.rates("2026-04-01")["stt"] == 0.0015
    sell = CO.leg_cost("2026-10-05", "sell", 40.0, 65, S0)
    buy = CO.leg_cost("2026-10-05", "buy", 40.0, 65, S0)
    assert sell["stt"] == pytest.approx(0.0015 * 40 * 65) and buy["stt"] == 0.0           # §8: ₹40 × 65 ⇒ ≈ ₹3.9
    assert buy["stamp"] > 0 and sell["stamp"] == 0.0 and sell["brokerage"] == 20.0
    o = CO.spread_cost("2026-10-05", 20.0, 12.0, 65, S0, opening=True)
    assert o["stt"] == pytest.approx(0.0015 * 20 * 65) and o["brokerage"] == 40.0
    assert CO.slip(10.0, "buy", S0) == pytest.approx(10.1) and CO.slip(0.05, "sell", S0) == 0.0


# ---------------------------------------------------------------- strikes (spec §10 worked example)
def sig(**k):
    base = dict(trade_dir=1, hard_inv=22217.0, alt_invs=[], tier="B", setup="S6a", extreme=22396.0, sub_origin=22522.0,
                bars_last_subleg=4, points=[22217.0, 22621.0], parent_points=[], parent_pattern="", parent_wave="", pattern="zigzag")
    base.update(k)
    return NS(**base)


def _book():
    cal = CT.TradingCalendar(weekdays("2026-09-01", "2026-11-30", minus=["2026-10-02"]))
    return cal, CT.ExpiryBook(cal, start="2026-09-01", end="2026-11-30")


def test_strike_worked_example_s6a_and_s13():
    cal, book = _book()
    s = _cfg(risk_per_trade_pct=2.0)
    px = {22150: 20.0, 22050: 12.0}
    pf = lambda opt, k, e: px.get(k, 5.0)                                          # noqa: E731
    p = SK.plan_spread(sig(), 22410.0, pd.Timestamp("2026-10-05 12:30"), 0.13, 50.0, cal, book, s, pf)
    assert p["expiry"] == D("2026-10-06") and p["dte_days"] == 1
    assert p["dist_inv"] == pytest.approx(22410 - 22217 + 25) and p["dist_vol"] == pytest.approx(223, abs=2)
    assert (p["opt"], p["short_k"], p["long_k"]) == ("PE", 22150, 22050)          # spec: short 22,150 PE, long 22,050
    pf2 = lambda opt, k, e: {22250: 30.0, 22150: 20.0}.get(k, 5.0)                 # noqa: E731
    p2 = SK.plan_spread(sig(setup="S13", hard_inv=22396.0), 22500.0, pd.Timestamp("2026-10-05 13:30"), 0.13, 50.0, cal, book, s, pf2)
    assert p2["short_k"] == 22250 and p2["dist_vol"] == pytest.approx(211, abs=2)  # spec: 22,250 PE
    p3 = SK.plan_spread(sig(setup="S13", hard_inv=22396.0, alt_invs=[22217.0]), 22500.0, pd.Timestamp("2026-10-05 13:30"), 0.13,
                        50.0, cal, book, s, pf)
    assert p3["inv_far"] == 22217.0 and p3["dist_inv"] == pytest.approx(308) and p3["short_k"] == 22150   # spec: alternate ⇒ 22,150


def test_bear_call_strikes_and_sizing():
    cal, book = _book()
    sg = sig(trade_dir=-1, hard_inv=23190.0, tier="A", setup="S7")
    p = SK.plan_spread(sg, 22790.0, pd.Timestamp("2026-10-07 10:00"), 0.13, 50.0, cal, book, S0, lambda o, k, e: 30.0 if k == 23250 else 10.0)
    assert p["opt"] == "CE" and p["short_k"] == 23250 and p["long_k"] == 23350 and p["expiry"] == D("2026-10-13")
    assert p["lots"] == int(10_000 // ((100 - 20.0) * 65))                          # ₹10L × 1% × Tier A 1.0


def test_delta_guard_uses_bs_without_delta_fn_and_min_one_lot():
    cal, book = _book()
    t = pd.Timestamp("2026-10-05 12:30")
    near = sig(tier="A", hard_inv=22380.0)                                         # inv जवळ ⇒ short strike spot जवळ
    T = 1.48 / 252
    bs = lambda o, k, e: PR.price(22410.0, k, T, 0.065, 0.13, o)                    # noqa: E731
    p = SK.plan_spread(near, 22410.0, t, 0.13, 0.0, cal, book, _cfg(min_dist_pts=0.0, k_sd=0.5, c_min_by_dte=[0.0] * 5,
                                                                                                    max_short_delta=0.2), bs)
    assert p == "guard_delta"                                                     # BS delta ≈ 0.22 > 0.2 — guard गुपचूप बंद नाही
    r = SK.plan_spread(sig(), 22410.0, t, 0.13, 50.0, cal, book, _cfg(min_one_lot=True),
                       lambda o, k, e: 20.0 if k == 22150 else 12.0, context="backtest")
    assert r["lots"] == 1 and r["over_budget"] and 0 < r["short_delta"] < 0.3
    assert SK.plan_spread(sig(), 22410.0, t, None, 50.0, cal, book, S0, lambda o, k, e: 20.0) == "no_iv"


def test_sizing_tier_of_A_default_and_risk_budget_legacy():
    # F1: lot 65, credit 8 ⇒ प्रति-lot तोटा (100 − 8) × 65 = ₹5,980. tier_of_A: A = max(1, 10,000 // 5,980) = 1 ⇒ B = round(0.5) → किमान 1,
    # C = round(0.25) = 0 (किमान 0 ⇒ size_zero). risk_budget (जुनं): B budget ₹5,000 < ₹5,980 ⇒ size_zero.
    cal, book = _book()
    t = pd.Timestamp("2026-10-05 12:30")
    px = lambda o, k, e: 20.0 if k == 22150 else 12.0                               # noqa: E731
    lots = {tier: SK.plan_spread(sig(tier=tier), 22410.0, t, 0.13, 50.0, cal, book, S0, px) for tier in "ABC"}
    assert lots["A"]["lots"] == 1 and lots["B"]["lots"] == 1 and lots["C"] == "size_zero"
    assert lots["B"]["over_budget"]                                                 # Tier B किमान 1 lot ⇒ budget ओलांडतो (नोंद)
    old = _cfg(sizing_mode="risk_budget")
    assert SK.plan_spread(sig(), 22410.0, t, 0.13, 50.0, cal, book, old, px) == "size_zero"
    assert SK.plan_spread(sig(tier="C"), 22410.0, t, 0.13, 50.0, cal, book, _cfg(tier_mult=[1.0, 0.5, 0.0]), px) == "size_zero"


def test_sizing_tier_ratio_survives_lot_eras():
    # Era-wise lot (25/50/75/65): मोठ्या capital वर A:B:C ≈ 1 : 0.5 : 0.25 टिकतं
    for lot in (25, 50, 75, 65):
        per_lot = 92.0 * lot
        base = 1e7 * 0.01
        a = SK.size_lots("A", 1.0, base, per_lot, S0)
        b = SK.size_lots("B", 0.5, base, per_lot, S0)
        c = SK.size_lots("C", 0.25, base, per_lot, S0)
        assert a >= 4 and abs(b - a * 0.5) <= 0.5 and abs(c - a * 0.25) <= 0.5
    assert SK.size_lots("B", 0.5, 1e4, 5980.0, _cfg(tierB_min_lots=2)) == 1             # किमान A पेक्षा जास्त नाही
    assert SK.size_lots("B", 0.5, 3e4, 5980.0, _cfg(tierB_min_lots=2)) == 3              # A 5 ⇒ round(2.5) = 3 (half-up)
    assert SK.size_lots_detail("C", 0.25, 1e4, 5980.0, _cfg(min_one_lot=True), context="backtest") == (1, "min_one_lot")   # shadow
    assert SK.size_lots_detail("C", 0.25, 1e4, 5980.0, _cfg(min_one_lot=True)) == (0, "")                 # PAPER / LIVE: risk cap
    assert SK.size_lots_detail("C", 0.25, 1e4, 5980.0, _cfg(tierC_min_lots=1)) == (1, "tier_floor")
    assert SK.size_lots_detail("A", 1.0, 1e3, 5980.0, S0, context="backtest") == (1, "a_min_one")
    assert SK.size_lots("C", 0.0, 1e6, 5980.0, S0) == 0                             # गुणक 0 ⇒ skip


def test_tierA_min_one_lot_only_in_backtest_by_default():
    """Review fix 3: 1 lot चा तोटा (₹5,980) budget (₹1,000) पेक्षा जास्त ⇒ PAPER / LIVE मध्ये 0 lots (risk cap); backtest मध्ये 1 (over_budget)."""
    assert S0["tierA_min_one_lot"] == "backtest_only"
    assert SK.size_lots_detail("A", 1.0, 1e3, 5980.0, S0) == (0, "")                                   # default context = paper
    assert SK.size_lots_detail("A", 1.0, 1e3, 5980.0, S0, context="live") == (0, "")
    assert SK.size_lots_detail("B", 0.5, 1e3, 5980.0, _cfg(tierB_min_lots=1)) == (0, "")              # floor ≤ A = 0
    assert SK.size_lots_detail("A", 1.0, 1e3, 5980.0, _cfg(tierA_min_one_lot="always")) == (1, "a_min_one")
    assert SK.size_lots_detail("A", 1.0, 1e3, 5980.0, _cfg(tierA_min_one_lot="never"), context="backtest") == (0, "")
    assert SK.size_lots_detail("A", 1.0, 1e4, 5980.0, S0) == (1, "")                                   # budget मध्ये बसतो ⇒ बदल नाही
    cal, book = _book()
    t = pd.Timestamp("2026-10-05 12:30")
    px = lambda o, k, e: 20.0 if k == 22150 else 12.0                               # noqa: E731
    tiny = _cfg(capital=1e5)                                                        # budget ₹1,000 < प्रति-lot ₹5,980
    for tier in "ABC":
        assert SK.plan_spread(sig(tier=tier), 22410.0, t, 0.13, 50.0, cal, book, tiny, px) == "size_zero"
    p = SK.plan_spread(sig(tier="A"), 22410.0, t, 0.13, 50.0, cal, book, tiny, px, context="backtest")
    assert p["lots"] == 1 and p["over_budget"] and p["size_floor"] == "a_min_one"


def test_trading_mode_and_live_approved_settings():
    """Review fix 4 (spec B7): default PAPER; LIVE फक्त live_approved सह."""
    assert S0["trading_mode"] == "PAPER" and S0["live_approved"] is False
    c, e = S.validate({"trading_mode": "LIVE"})
    assert c["trading_mode"] == "PAPER" and any("live_approved" in x for x in e)
    c, e = S.validate({"trading_mode": "LIVE", "live_approved": True})
    assert c["trading_mode"] == "LIVE" and not e
    assert S.validate({"trading_mode": "paper"}) == (S0, [])                                          # spec चं lowercase
    assert S.effective_trading_mode({"trading_mode": "LIVE"}) == "PAPER"
    assert S.effective_trading_mode({"trading_mode": "live", "live_approved": "true"}) == "PAPER"      # string "true" ≠ मंजुरी
    assert S.effective_trading_mode(c) == "LIVE" and S.effective_trading_mode({}) == "PAPER"


def test_guard_fail_actions():
    cal, book = _book()
    low = lambda o, k, e: 3.0 if k == 22150 else 1.0                                # credit 2 ⇒ 0.02 < 0.06
    t = pd.Timestamp("2026-10-05 12:30")
    assert SK.plan_spread(sig(), 22410.0, t, 0.13, 50.0, cal, book, S0, low) == "guard_credit_width"
    nxt = lambda o, k, e: (3.0 if k == 22150 else 1.0) if e == D("2026-10-06") else (k - 21000) * 0.2   # noqa: E731
    p = SK.plan_spread(sig(tier="A"), 22410.0, t, 0.13, 50.0, cal, book, _cfg(credit_fail_action="try_next_weekly"), nxt)
    assert isinstance(p, dict) and p["next_weekly"] and p["expiry"] == D("2026-10-13")
    assert SK.plan_spread(sig(tier="A"), 22410.0, t, 0.13, 50.0, cal, book, S0, lambda o, k, e: 30.0 if k == 22150 else 10.0,
                          delta_fn=lambda o, k, e: -0.35) == "guard_delta"
    assert SK.plan_spread(sig(), 22410.0, t, 0.13, 50.0, cal, book, S0, lambda o, k, e: None) == "no_price"
    bh = pd.DataFrame({"expiry": [D("2026-10-06")], "kind": ["weekly"], "first_seen": [D("2026-09-01")]})
    only = CT.ExpiryBook(cal, bh)                                                   # पुढची weekly listed नाही ⇒ खरं कारण टिकतं
    assert SK.plan_spread(sig(tier="A"), 22410.0, t, 0.13, 50.0, cal, only, _cfg(credit_fail_action="try_next_weekly"),
                          low) == "guard_credit_width"
    wide = lambda o, k, e: {22150: 4.0, 22100: 2.0, 22050: 1.5, 22000: 0.9, 21950: 0.5}.get(k, 0.0)   # noqa: E731
    p = SK.plan_spread(sig(tier="A"), 22410.0, t, 0.13, 50.0, cal, book, _cfg(credit_fail_action="widen_width", width_pts=50,
                       c_min_by_dte=[0.01, 0.08, 0.1, 0.12, 0.12]), wide)
    assert p["width"] == 150 and p["credit"] == pytest.approx(3.1)                 # min_credit साठीच widen उपयोगी


# ---------------------------------------------------------------- exits (§9 priority)
def state(sg=None, credit=10.0, lots=4, short_k=22150):
    sg = sg or sig()
    return EX.TradeState(sg, {"short_k": short_k}, pd.Timestamp("2026-10-05 12:35"), credit, lots, sg.hard_inv)


BAR = (22420.0, 22440.0, 22400.0, 22430.0)
LEG = _cfg(progress_mode="legacy")


def test_priority_order():
    st = state()
    r = EX.evaluate(st, {"bar": (22420, 22440, 22140, 22300), "hard_broken": True, "mark": 50.0}, S0)
    assert r["exit"] == "emergency_short_strike" and r["priority"] == 0              # intrabar strike cross सर्वात आधी
    assert EX.evaluate(state(), {"bar": BAR, "hard_broken": True, "mark": 50.0}, S0)["exit"] == "hard_inv"
    assert EX.evaluate(state(), {"bar": BAR, "parent_broken": True}, S0)["exit"] == "parent_inv_cascade"
    assert EX.evaluate(state(), {"bar": BAR, "mark": 20.0, "soft_broken": True}, S0)["exit"] == "premium_stop"
    assert EX.evaluate(state(), {"bar": BAR, "mark": 9.0, "soft_broken": True}, S0)["exit"] == "soft_stop"


def test_premium_stop_bar_close_vs_intrabar():
    ctx = {"bar": BAR, "mark": 15.0, "mark_worst": 25.0}
    assert EX.evaluate(state(), ctx, S0)["exit"] is None                            # bar close (default) ⇒ wick वर नाही
    assert EX.evaluate(state(), ctx, _cfg(hard_stop_eval="intrabar"))["exit"] == "premium_stop"


def test_soft_stop_actions():
    r = EX.evaluate(state(), {"bar": BAR, "soft_broken": True}, _cfg(soft_stop_action="reduce"))
    assert r["exit"] is None and r["partial_lots"] == 2 and "soft_stop" in r["alerts"]
    r = EX.evaluate(state(), {"bar": BAR, "soft_broken": True}, _cfg(soft_stop_action="alert"))
    assert r["exit"] is None and r["partial_lots"] == 0
    r = EX.evaluate(state(), {"bar": BAR, "lower_broken": True}, S0)
    assert r["exit"] is None and "lower_inv" in r["alerts"]


def test_tier_b_c_zone_exits():
    sg = sig()                                                                      # S6a: B end 22,396, A = 404 ⇒ C=1.0A 22,800
    assert EX.c_zone(sg, S0) == pytest.approx([22396 + f * 404 for f in S0["zone_fibs_c"]])
    assert EX.evaluate(state(sg), {"bar": BAR, "opposite_reversal": True}, S0)["exit"] == "c_zone_opposite_reversal"
    hit = (22700, 22805, 22690, 22780)
    assert EX.evaluate(state(sg), {"bar": hit}, S0)["exit"] is None                 # default: zone गाठणं पुरेसं नाही (§14 Q4)
    assert EX.evaluate(state(sg), {"bar": hit}, _cfg(tierB_exit_mode="fixed_mult"))["exit"] == "c_zone_fixed_target"
    s13 = sig(setup="S13", hard_inv=22396.0, parent_points=[22217.0, 22621.0, 22396.0], points=[22396.0, 22520.0])
    assert EX.c_zone(s13, S0)[1] == pytest.approx(22800.0)                         # parent B end + 1.0 × parent A


def test_tier_a_partial_then_progressive_inv():
    sg = sig(tier="A", setup="S1", points=[22000.0, 22300.0], extreme=22150.0, sub_origin=22250.0)
    st = state(sg)
    r = EX.evaluate(st, {"bar": (22280, 22310, 22270, 22300)}, S0)                  # (i) टोक 22,300 ओलांडलं
    assert r["move_inv"] == 22150.0 and st.hard_inv == 22150.0 and r["exit"] is None
    r = EX.evaluate(st, {"bar": (22400, 22455, 22390, 22450)}, S0)                  # T1 = 22,150 + 300 = 22,450
    assert r["partial_lots"] == 2 and st.partial_done and r["exit"] is None
    assert EX.evaluate(state(sg), {"bar": (22400, 22455, 22390, 22450)}, _cfg(tierA_target_action="exit_all"))["exit"] == "tierA_target"


def test_progress_off_by_default_and_correction_time():
    st = state()
    for _ in range(10):
        assert EX.evaluate(st, {"bar": BAR}, S0)["exit"] is None                    # F2: default off ⇒ वेळेवरून exit नाही
    sg = sig(corr_bars=6, bars_from_extreme=1, prev_leg_bars=10)
    ct = _cfg(progress_mode="correction_time", progress_bars_mult=1.0)
    st = state(sg)
    for _ in range(6):                                                              # 1 + 6 ≥ 6 bars पण spread नफ्यात, नवीन टोक नाही
        assert EX.evaluate(st, {"bar": BAR, "mark": 8.0}, ct)["exit"] is None
    assert EX.evaluate(st, {"bar": BAR, "mark": 12.0}, ct)["exit"] == "progress_time"   # मुदत संपली + तोट्यात
    st = state(sg)
    for _ in range(4):
        EX.evaluate(st, {"bar": BAR, "mark": 8.0}, ct)
    assert EX.evaluate(st, {"bar": (22400, 22410, 22390, 22400), "mark": 8.0}, ct)["exit"] == "progress_time"  # मुदत संपली + नवीन टोक (22,390 < 22,396)
    st = state(sg)
    assert EX.evaluate(st, {"bar": (22400, 22410, 22380, 22400), "mark": 8.0}, ct)["exit"] is None  # नवीन टोक पण मुदत बाकी
    for _ in range(4):
        EX.evaluate(st, {"bar": BAR, "mark": 8.0}, ct)
    assert EX.evaluate(st, {"bar": BAR, "mark": 8.0}, ct)["exit"] == "progress_time"     # मुदत संपली + आधी नवीन टोक
    wave1 = _cfg(progress_mode="correction_time", progress_ref="wave1")
    st = state(sg)
    for _ in range(8):
        assert EX.evaluate(st, {"bar": BAR, "mark": 12.0}, wave1)["exit"] is None   # मुदत 10 bars
    assert EX.evaluate(st, {"bar": BAR, "mark": 12.0}, wave1)["exit"] == "progress_time"


def test_profit_progress_expiry_thesis():
    assert EX.evaluate(state(), {"bar": BAR, "mark": 4.9}, S0)["exit"] == "profit_pct"          # Tier B 50%
    assert EX.evaluate(state(), {"bar": BAR, "mark": 5.1}, S0)["exit"] is None
    st = state()
    for _ in range(3):
        assert EX.evaluate(st, {"bar": BAR}, LEG)["exit"] is None
    assert EX.evaluate(st, {"bar": BAR}, LEG)["exit"] == "progress_time"            # 4 bars, H (22,522) ओलांडला नाही
    st2 = state()
    EX.evaluate(st2, {"bar": (22500, 22540, 22490, 22530)}, LEG)                      # H ओलांडला
    for _ in range(5):
        assert EX.evaluate(st2, {"bar": BAR}, LEG)["exit"] is None
    near = {"bar": (22200, 22210, 22180, 22190), "expiry_day": True, "past_exit_time": True, "minutes_left": 120, "iv": 0.13}
    assert EX.evaluate(state(), near, _cfg(progress_bars_mult=0.0))["exit"] == "expiry_day_risk"
    far = {**near, "bar": (22600, 22610, 22590, 22600)}
    assert EX.evaluate(state(), far, _cfg(progress_bars_mult=0.0))["exit"] is None
    assert EX.evaluate(state(), {"bar": BAR, "opposite_signal": True}, _cfg(progress_bars_mult=0.0))["exit"] == "thesis_complete"


def test_touch_is_not_cross_and_emergency_check_is_pure():
    st = state()
    assert EX.evaluate(st, {"bar": (22200, 22210, 22150, 22200)}, _cfg(progress_bars_mult=0.0))["exit"] is None   # फक्त स्पर्श
    assert EX.emergency_check(st, 22149.95) and not EX.emergency_check(st, 22150.0)
    b0 = st.bars
    EX.emergency_check(st, 22100.0)
    assert st.bars == b0                                                          # tick वर state बदलत नाही


def test_reduce_applies_once():
    st = state(lots=8)
    s = _cfg(soft_stop_action="reduce", progress_bars_mult=0.0)
    lots = [EX.evaluate(st, {"bar": BAR, "soft_broken": True}, s)["partial_lots"] for _ in range(3)]
    assert lots == [4, 0, 0]


def test_bear_call_exit_branches():
    sg = sig(trade_dir=-1, tier="A", setup="S1", points=[23000.0, 22700.0], extreme=22850.0, sub_origin=22750.0,
             hard_inv=23000.0, bars_last_subleg=4)
    st = state(sg, short_k=23150)
    assert EX.evaluate(st, {"bar": (23100, 23160, 23090, 23120)}, S0)["exit"] == "emergency_short_strike"
    st = state(sg, short_k=23150)
    r = EX.evaluate(st, {"bar": (22720, 22730, 22690, 22700)}, S0)                  # (i) टोक 22,700 ओलांडलं
    assert r["move_inv"] == 22850.0 and st.crossed_h is True
    r = EX.evaluate(st, {"bar": (22580, 22590, 22545, 22560)}, S0)                  # T1 = 22,850 − 300 = 22,550
    assert r["partial_lots"] == 2
    st2 = state(sg, short_k=23150)
    for _ in range(3):
        EX.evaluate(st2, {"bar": (22800, 22810, 22790, 22800)}, _cfg(progress_mode="legacy"))
    assert EX.evaluate(st2, {"bar": (22800, 22810, 22790, 22800)}, _cfg(progress_mode="legacy"))["exit"] == "progress_time"
    ex = {"bar": (23160, 23195, 23140, 23190), "expiry_day": True, "past_exit_time": True, "minutes_left": 30, "iv": 0.13}
    assert EX.evaluate(state(sg, short_k=23200), ex, _cfg(progress_bars_mult=0.0))["exit"] == "expiry_day_risk"


def test_expiry_day_without_iv_exits_and_tier_b_fallback_target():
    ctx = {"bar": (22600, 22610, 22590, 22600), "expiry_day": True, "past_exit_time": True}
    assert EX.evaluate(state(), ctx, _cfg(progress_bars_mult=0.0))["exit"] == "expiry_day_no_iv"
    demoted = sig(tier="B", setup="S2", points=[22000.0, 22300.0], extreme=22150.0, sub_origin=22250.0)
    assert EX.c_zone(demoted, S0) == []
    assert EX.evaluate(state(demoted), {"bar": (22400, 22455, 22390, 22450)}, S0)["exit"] == "t1_target_bounded"


def test_tier_b_acceptance_trailing_and_s8_own_w():
    sg = sig()
    st = state(sg)
    r = EX.evaluate(st, {"bar": (22800, 22900, 22790, 22880), "c_zone_accepted": True, "trail_level": 22600.0,
                         "opposite_reversal": True}, _cfg(progress_bars_mult=0.0))
    assert r["exit"] is None and st.hard_inv == 22600.0                            # zone ओलांडला ⇒ hold + trailing
    EX.evaluate(st, {"bar": BAR, "c_zone_accepted": True, "trail_level": 22500.0}, _cfg(progress_bars_mult=0.0))
    assert st.hard_inv == 22600.0                                                  # inv फक्त trade च्या बाजूने सरकतो
    s8 = sig(setup="S8", pattern="wxy", points=[22000.0, 22400.0], parent_points=[21000.0, 23000.0], extreme=22200.0)
    assert EX.c_zone(s8, S0)[1] == pytest.approx(22600.0)                          # Y ≈ स्वतःचा W (400)


def test_exits_never_blocked_by_entry_settings():
    ctx = {"bar": BAR, "hard_broken": True}
    for k in ({"entry_end": "09:45"}, {"vote_min": 0.99}, {"max_daily_loss_pct": 0.1}, {"max_open_spreads": 1},
              {"htf_gate_enabled": True}, {"setups_enabled": []}):
        assert EX.evaluate(state(), dict(ctx), _cfg(**k))["exit"] == "hard_inv"


def test_settings_e3_validation():
    c, e = S.validate({"tier_mult": "1,0.5", "inv_buffer_mr": 0.1, "width_pts": 120})
    assert c["tier_mult"] == [1.0, 0.5, 0.25] and c["inv_buffer_mr"] == c["break_buffer_mr"] and c["width_pts"] == 100 and len(e) == 3
