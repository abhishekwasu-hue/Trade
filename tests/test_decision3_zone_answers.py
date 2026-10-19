"""Abhi's final answers on the in-zone study and the flip rule (OPEN_QUESTIONS Z-1p / Z-1q / Z-1r / Z-1s / Z-1t, RF-2, PF-2), mirrored
where a side matters. Synthetic only (CI-safe); the real days (12 / 13 Oct, 29 Sep) are in tests/test_decision3_flip.py.

  • Z-1p (a): the counter side gone from the zone (none in the second half, some in the first) = exhausted ⇒ only the trade side growing;
  • Z-1q (a): a handover, once seen, holds until the commitment — cancelled only by a later absorption or the zone breaking (K4 state);
  • Z-1r (a+): handover + LTF CHoCH + commitment all at the commitment bar, any order; the CHoCH must come after price entered the zone;
  • RF-2 (b): FUT volume gaps — average over the bars that have it, "gaps n/m"; more than `vol_gap_max_frac` ⇒ data problem, no entry,
    one Telegram line (NIFTY / BANKNIFTY, once per symbol per day);
  • Z-1t (a): holdout Daily bars only as level history, only for a window after the holdout end; never a holdout-dated decision;
    "0 Daily bars before window ⇒ Q40 prior levels skipped" logged, never silent;
  • PF-2 (a): the provisional band width (σ_1H missing) is labelled "provisional width" in the level facts and the chart labels.
"""
import logging

import numpy as np
import pandas as pd
import pytest

from decision3 import engine as E3
from decision3 import history as HI
from decision3 import levels as LV
from decision3 import method as M
from decision3 import settings as S3
from tests.test_decision3 import P, m15_from, res_of

S = S3.load()
UP, DOWN = M.UP, M.DOWN
MID = 101.5


def _A(seq, mirror=False):
    """[(open, close, volume)] ⇒ arrays (wick 0.3). mirror: prices reflected around MID (a bear sequence becomes a bull one)."""
    f = (lambda x: 2 * MID - x) if mirror else (lambda x: float(x))
    o = np.array([f(x[0]) for x in seq])
    c = np.array([f(x[1]) for x in seq])
    return {"open": o, "close": c, "high": np.maximum(o, c) + 0.3, "low": np.minimum(o, c) - 0.3, "volume": np.array([x[2] for x in seq], float)}


# bear call at a supply (d = DOWN): trade side = red. First half: buying (counter) candles strong; then selling grows, buying fades.
HANDOVER = [(101.0, 101.8, 1.2), (101.8, 101.6, 0.8), (101.6, 102.3, 1.3), (102.3, 102.1, 0.8),
            (102.1, 101.4, 1.4), (101.4, 101.6, 0.6), (101.6, 100.8, 1.6), (100.8, 100.9, 0.5)]
FADE = [(100.9, 100.85, 0.7), (100.85, 101.0, 0.7), (101.0, 100.95, 0.6), (100.95, 101.05, 0.6)]   # handover read gone, no absorption
ABSORB = [(100.9, 101.9, 1.8), (101.9, 101.7, 0.7), (101.7, 102.6, 2.0), (102.6, 102.4, 0.7)]      # buying candles strengthen again


# ------------------------------------------------------------------------------------------------ Z-1p (a)
@pytest.mark.parametrize("mirror", [False, True], ids=["bear", "bull"])
def test_counter_side_gone_from_the_zone_counts_as_exhausted(mirror):
    d = UP if mirror else DOWN
    gone = [(101.0, 101.6, 1.0), (101.6, 101.45, 0.8), (101.45, 101.9, 1.0), (101.9, 101.75, 0.8),
            (101.75, 101.2, 1.2), (101.2, 100.5, 1.4), (100.5, 99.7, 1.5), (99.7, 98.8, 1.6)]
    z = M.zone_study(_A(gone, mirror), 0, len(gone) - 1, d, S)
    assert z["counter_gone"] is True and z["counter_weakening"] is True
    assert z["trend_growing"] is True and z["handover"] is True and z["absorption"] is False
    assert ("buying" if not mirror else "selling") + " candles gone from the zone (exhausted)" in z["line"]
    shrinking = [(101.0, 101.6, 1.0), (101.6, 100.8, 1.6), (100.8, 101.4, 1.0), (101.4, 100.6, 1.6),
                 (100.6, 100.3, 0.8), (100.3, 100.05, 0.7), (100.05, 99.85, 0.6), (99.85, 99.7, 0.5)]
    z2 = M.zone_study(_A(shrinking, mirror), 0, len(shrinking) - 1, d, S)
    assert z2["counter_gone"] is True and z2["trend_growing"] is False and z2["handover"] is False   # only the trade side decides
    never = [(101.6, 101.45, 0.8), (101.45, 101.3, 0.8)] * 2 + gone[4:]    # no counter candle in either half ⇒ not "gone" (NA)
    z3 = M.zone_study(_A(never, mirror), 0, len(never) - 1, d, S)
    assert z3["counter_gone"] is False and z3["counter_weakening"] is None and z3["handover"] is False


# ------------------------------------------------------------------------------------------------ Z-1q (a)
@pytest.mark.parametrize("mirror", [False, True], ids=["bear", "bull"])
def test_handover_once_seen_holds_until_the_commitment(mirror):
    d = UP if mirror else DOWN
    A = _A(HANDOVER + FADE, mirror)
    t = len(HANDOVER + FADE)
    late = M.zone_study(A, 0, t - 1, d, S)                                 # the commitment bar's own window: no handover read now
    assert late["handover"] is False and late["absorption"] is False
    ho = M.handover_episode(A, 0, t, d, S)
    assert ho["present"] is True and ho["seen_at"] == 4 and ho["cancelled"] is None
    cut = {k: v[:t] for k, v in A.items()}                                 # no look-ahead: same answer on data cut at the decision bar
    assert M.handover_episode(cut, 0, t, d, S) == M.handover_episode(A, 0, t, d, S)
    assert M.handover_episode(A, 0, 4, d, S)["present"] is False           # not yet seen before its window closed


@pytest.mark.parametrize("mirror", [False, True], ids=["bear", "bull"])
def test_sticky_handover_is_cancelled_by_a_later_absorption(mirror):
    d = UP if mirror else DOWN
    A = _A(HANDOVER + ABSORB, mirror)
    ho = M.handover_episode(A, 0, len(HANDOVER + ABSORB), d, S)
    assert ho["present"] is False and ho["seen_at"] == 4 and ho["cancelled"] == "absorption" and ho["cancelled_at"] == 11


@pytest.mark.parametrize("mirror", [False, True], ids=["bear", "bull"])
def test_sticky_handover_is_cancelled_by_the_zone_breaking(mirror):
    d = UP if mirror else DOWN
    A = _A(HANDOVER + FADE, mirror)
    t = len(HANDOVER + FADE)
    ho = M.handover_episode(A, 0, t, d, S, broken=lambda u: u >= 9)
    assert ho["present"] is False and ho["cancelled"] == "zone broken" and ho["cancelled_at"] == 9
    early = M.handover_episode(A, 0, t, d, S, broken=lambda u: u == 2)     # a break BEFORE any handover: nothing to cancel, the read
    assert early["cancelled"] is None                                       # restarts after the break (the broken bars never count)
    assert {k: early[k] for k in ("present", "seen_at")} == {k: M.handover_episode(A, 3, t, d, S)[k] for k in ("present", "seen_at")}


def test_confirm_uses_the_sticky_handover_not_the_commitment_bar_window():
    A = _A(HANDOVER + FADE)
    t = len(HANDOVER + FADE) - 1
    lvl = {"lo": 100.0, "hi": 103.0}
    s = {**S, "ltf_choch": False}
    plain = M.confirm(A, 0, t, DOWN, lvl, s)
    assert plain["handover"] is False and plain["wait"] == M.C_NO_HANDOVER
    sticky = M.confirm(A, 0, t, DOWN, lvl, s, handover=M.handover_episode(A, 0, t, DOWN, s))
    assert sticky["handover"] is True and sticky["wait"] != M.C_NO_HANDOVER and sticky["handover_state"]["seen_at"] == 4
    gone = M.confirm(A, 0, t, DOWN, lvl, s, handover={"present": False, "cancelled": "zone broken"})
    assert gone["wait"] == M.C_NO_HANDOVER and "handover cancelled (zone broken)" in gone["why"]


def test_engine_zone_break_cancels_the_handover_through_the_k4_state(monkeypatch):
    from tests.test_decision3_flip import _HANDOVER, _default_case
    V = _default_case(_HANDOVER)
    r = V.decide(741)
    lvl = r["level"]
    hs = r["commit"]["handover_state"]
    assert hs["present"] is True and hs["seen_ts"] and r["decision"] == "setup"
    L = V.levels.L[lvl["id"]]
    real = L.state_at
    monkeypatch.setattr(L, "state_at", lambda u: "BROKEN" if u >= 740 else real(u))
    ho = V.handover_episode(V.vol_view(735, 741)[0], 735, 741, DOWN, lvl)
    assert ho["present"] is False and ho["cancelled"] == "zone broken" and ho["cancelled_at"] == 740


# ------------------------------------------------------------------------------------------------ Z-1r (a+)
def _ltf(rows, start="2030-01-07 10:00", minutes=5):
    ts = pd.date_range(start, periods=len(rows), freq=f"{minutes}min")
    df = pd.DataFrame({"timestamp": ts, "open": [r[0] for r in rows], "high": [r[1] for r in rows], "low": [r[2] for r in rows],
                       "close": [r[3] for r in rows]})
    return M.ltf_frame(df, minutes)


def test_a_choch_before_price_entered_the_zone_does_not_count():
    """Bull put at a demand 100–101. The 5M CHoCH (close above the lower high) happened BEFORE price came down into the zone; after the
    arrival price has not closed above the post-arrival lower high ⇒ no CHoCH yet (pending), never the old one."""
    rows = [(106, 106.5, 104.0, 104.2), (104.2, 104.4, 103.0, 103.2), (103.2, 105.6, 103.1, 105.5),   # context: low 103, CHoCH 105.5
            (105.5, 105.7, 103.5, 103.6), (103.6, 103.8, 102.2, 102.4),                                 # the arm bar starts (10:15)
            (102.4, 102.5, 100.6, 100.8), (100.8, 102.7, 100.7, 102.5), (102.5, 102.6, 100.3, 100.5),   # arrival 10:25, LH 102.7, LL
            (100.5, 101.2, 100.4, 101.0)]                                                               # no close above 102.7 yet
    L = _ltf(rows)
    ch = M.ltf_choch(L, UP, "2030-01-07 10:00", "2030-01-07 10:15", "2030-01-07 10:45", lvl={"lo": 100.0, "hi": 101.0})
    assert ch["done"] is False and ch["code"] == M.C_LTF_PENDING
    assert ch["arrival_at"].startswith("2030-01-07 10:25")
    rows2 = rows + [(101.0, 103.0, 100.9, 102.9)]                         # closes above the post-arrival lower high ⇒ CHoCH now
    ch2 = M.ltf_choch(_ltf(rows2), UP, "2030-01-07 10:00", "2030-01-07 10:15", "2030-01-07 10:50", lvl={"lo": 100.0, "hi": 101.0})
    assert ch2["done"] is True and pd.Timestamp(ch2["at"]) == pd.Timestamp("2030-01-07 10:50")   # the post-arrival CHoCH candle
    assert pd.Timestamp(ch2["at"]) > pd.Timestamp(ch2["arrival_at"]) > pd.Timestamp("2030-01-07 10:15")   # after the arrival, not the arm
    old = M.ltf_choch(_ltf(rows2), UP, "2030-01-07 10:00", "2030-01-07 10:00", "2030-01-07 10:50", lvl={"lo": 100.0, "hi": 101.0})
    assert old["at"] == ch2["at"]                                           # the context CHoCH (10:10 close 105.5) is never reported


def test_default_path_reports_the_choch_time_relative_to_the_arm_and_all_three_parts():
    from tests.test_decision3_flip import _HANDOVER, _default_case
    r = _default_case(_HANDOVER).decide(741)
    cm = r["commit"]
    assert r["decision"] == "setup" and cm["handover_present"] and cm["choch"]["done"] and cm["form"]
    assert cm["choch_vs_arm"].startswith("CHoCH at") and "after arrival" in cm["choch_vs_arm"]
    assert pd.Timestamp(cm["choch"]["at"]) > pd.Timestamp(cm["study_from"])


# ------------------------------------------------------------------------------------------------ RF-2 (b)
def _gap_case(drop):
    from tests.ltf_fixtures import split_bars
    from tests.test_decision3_flip import _HANDOVER
    from tests.test_decision3_method import _abc_m15
    m15 = _abc_m15()
    vol = np.full(len(m15), 3e5)
    for j, (o_, c_, v_) in enumerate(_HANDOVER):
        m15.loc[735 + j, ["open", "close", "high", "low"]] = [o_, c_, max(o_, c_) + 2, min(o_, c_) - 2]
        vol[735 + j] = v_
    m15.loc[741, ["open", "high"]] = [19440, 19443]
    vol[741] = 1.2e6
    fut = pd.DataFrame({"timestamp": [t + pd.Timedelta(minutes=5 * j) for t in m15["timestamp"] for j in range(3)],
                        "volume": np.repeat(vol / 3.0, 3), "expiry": pd.Timestamp("2030-03-28")})
    fut = fut[~fut["timestamp"].dt.floor("15min").isin(set(m15["timestamp"].iloc[list(drop)]))]
    return E3.V22(m15, ltf=split_bars(m15, 15, 3), futures=fut)


def test_fut_gaps_below_the_limit_average_over_bars_with_volume_and_report_gaps():
    r = _gap_case([736, 737, 738]).decide(741)                             # 3 of 7 window bars without FUT (43 % ≤ 50 %)
    g = r["commit"]["vol_gaps"]
    assert (g["n"], g["m"], g["over"], g["limit"]) == (3, 7, False, S3.DEFAULTS["vol_gap_max_frac"])
    assert r["decision"] == "setup" and not r["commit"].get("data_problem")
    assert "FUT volume gaps: 3/7" in r["volume_measure"] and r["commit"]["vol_mult"] > 1.0


def test_fut_gaps_above_the_limit_are_a_data_problem_no_entry():
    r = _gap_case([735, 736, 737, 738]).decide(741)                        # 4 of 7 (57 % > 50 %)
    assert r["decision"] == "wait" and r["checklist"]["⑥"][0] is False
    assert r["commit"]["data_problem"].startswith("data problem: FUT volume gaps 4/7")
    nc = _gap_case([741]).decide(741)                                      # the commitment candle without its own FUT volume ⇒ no entry
    assert nc["decision"] == "wait" and "data problem" in nc["checklist"]["⑥"][1] and nc["commit"]["vol_gaps"]["n"] == 1


def test_fut_gaps_setting_is_registered():
    assert S3.DEFAULTS["vol_gap_max_frac"] == 0.5 and "vol_gap_max_frac" in S3.REGISTER
    V = _gap_case([735, 736, 737, 738])
    assert V.vol_gaps(735, 741)["over"] is True
    V.s = {**V.s, "vol_gap_max_frac": 0.6}                                 # the limit is a setting, not a constant
    assert V.vol_gaps(735, 741) == {"n": 4, "m": 7, "frac": 0.571, "limit": 0.6, "over": False}


def test_fut_gaps_data_problem_sends_one_telegram_line_per_symbol_per_day_nifty_banknifty_only(tmp_path, monkeypatch):
    import json

    from scripts import engine_signal_run as ESR
    monkeypatch.setenv("ENGINE_SIGNAL_DB", str(tmp_path / "es.db"))
    sent = []
    dp = "data problem: FUT volume gaps 4/7 bars in the zone window (> 50%, vol_gap_max_frac)"

    def run(sym, tok):
        return {"bar_ts": "2030-01-07 10:15", "decision": "wait", "skipped": "test", "payload": json.dumps({"data_problem": dp})}
    for k in range(3):
        ESR.main(["--symbols", "NIFTY,BANKNIFTY,SENSEX"], token_fn=lambda: "tok", run_fn=run, market_fn=lambda: True, send=sent.append,
                 alert_path=str(tmp_path / "a.json"), now=pd.Timestamp("2030-01-07 10:16") + pd.Timedelta(minutes=15 * k),
                 symbols_fn=lambda: ["NIFTY", "BANKNIFTY", "SENSEX"])
    assert len(sent) == 2 and all("data problem: FUT volume gaps" in x for x in sent)
    assert not any("SENSEX" in x for x in sent)


# ------------------------------------------------------------------------------------------------ Z-1t (a): holdout guard
def _daily(start, end, px=22000.0):
    d = pd.bdate_range(start, end)
    c = px + 50 * np.sin(np.arange(len(d)) / 5.0)
    return pd.DataFrame({"timestamp": d, "open": c - 10, "high": c + 40, "low": c - 40, "close": c + 10})


def test_holdout_daily_bars_are_level_history_only_after_the_holdout_end_and_logged(caplog):
    fr = [_daily("2023-01-02", "2024-03-29"), _daily("2024-04-01", "2026-06-30"), _daily("2026-07-01", "2026-09-30")]
    with caplog.at_level(logging.WARNING, logger="decision3.history"):
        h, n = HI.level_history_daily("NIFTY", fr, "2026-07-01")
    assert n == len(pd.bdate_range("2024-04-01", "2026-06-30")) and h["timestamp"].max() < pd.Timestamp("2026-07-01")
    assert f"holdout daily bars used as level history: {n} bars" in caplog.text
    lines = []
    HI.level_history_daily("NIFTY", fr, "2026-10-01", log_fn=lines.append)
    assert lines == [HI.HOLDOUT_LINE.format(n=n)]
    from elliott import data_policy as DP
    for ws in ("2025-03-03", "2026-06-30"):                                # a window inside the holdout ⇒ refused
        with pytest.raises(DP.HoldoutError):
            HI.level_history_daily("NIFTY", fr, ws)
    h2, n2 = HI.level_history_daily("NIFTY", fr, "2024-02-01")             # a window before the holdout: no holdout row reaches it
    assert n2 == 0 and h2["timestamp"].max() < pd.Timestamp("2024-02-01")
    hb, nb = HI.level_history_daily("BANKNIFTY", fr, "2025-03-03")          # the holdout seal is NIFTY's only
    assert nb == 0 and len(hb)


def test_the_sealed_holdout_file_is_readable_only_as_nifty_level_history_after_the_holdout_end(tmp_path):
    from elliott import data_policy as DP
    p = tmp_path / "nifty50_daily_extension.parquet"
    _daily("2024-04-01", "2026-08-20").to_parquet(p)
    with pytest.raises(DP.HoldoutError):
        HI.read_level_history(str(p), "NIFTY", "2026-05-04")
    with pytest.raises(DP.HoldoutError):
        HI.read_level_history(str(p), "BANKNIFTY", "2026-08-03")
    with pytest.raises(DP.HoldoutError):                                    # the research loader still refuses it
        DP.load_parquet(str(p))
    h = HI.read_level_history(str(p), "NIFTY", "2026-07-01")
    assert len(h) and h["timestamp"].max() < pd.Timestamp("2026-07-01")


def test_v22_never_produces_a_holdout_dated_decision():
    from elliott import data_policy as DP
    sealed = HI.sealed_fn("NIFTY")
    closes = list(np.linspace(22000, 22300, 60)) + list(np.linspace(22300, 22100, 40))
    bad = m15_from(closes, start="2026-06-25")                            # 25–30 Jun = holdout dates
    with pytest.raises(DP.HoldoutError):
        E3.V22(bad, daily_df=_daily("2026-01-02", "2026-06-24"), sealed=sealed)
    good = m15_from(closes, start="2026-07-06")
    hist, n = HI.level_history_daily("NIFTY", [_daily("2025-01-01", "2026-07-03", 22100.0)], "2026-07-06", log_fn=lambda _m: None)
    assert n > 0
    V = E3.V22(good, daily_df=HI.daily_warmup("NIFTY", good, hist), sealed=sealed)
    rows = V.run()
    assert rows and all(not sealed(pd.Timestamp(r["ts"])) and pd.Timestamp(r["ts"]) >= DP.CONTAMINATED_START for r in rows)
    assert all(set(p) == {"src", "kind", "price", "role"} for p in V.levels.prior)   # Q40 prior levels: price only, no holdout date
    with pytest.raises(DP.HoldoutError):                                    # belt and braces: decide() on a sealed bar
        V.m15.loc[0, "timestamp"] = pd.Timestamp("2026-06-30 09:15")
        V.decide(0)


# ------------------------------------------------------------------------------------------------ Z-1t: never silent
def test_prior_levels_skipped_is_logged_when_no_daily_bar_precedes_the_window(caplog):
    m = m15_from(list(np.linspace(100, 120, 30)), wick=0.3)
    with caplog.at_level(logging.WARNING, logger="decision3.levels"):
        lv = LV.Levels(res_of(m, [P("H", 118, 8, 10)]), daily_df=None)
    assert lv.prior_note == "0 Daily bars before window ⇒ Q40 prior levels skipped" and lv.prior_note in caplog.text
    caplog.clear()
    d = _daily("2029-09-03", "2030-01-04", 110.0)
    with caplog.at_level(logging.WARNING, logger="decision3.levels"):
        lv2 = LV.Levels(res_of(m, [P("H", 118, 8, 10)]), daily_df=d)
    assert lv2.prior_note is None and "Q40 prior levels skipped" not in caplog.text


# ------------------------------------------------------------------------------------------------ PF-2 (a)
def test_provisional_width_is_labelled_in_the_level_facts_and_chart_labels():
    m = m15_from(list(np.linspace(100, 120, 20)) + list(np.linspace(120, 110, 20)), wick=0.3)
    res = res_of(m, [P("H", 120, 19, 21)])
    days = sorted(res["sigma_1h"])
    res["sigma_1h"] = {d: (np.nan if d == days[0] else 4.0) for d in days}   # σ_1H missing on the first session only
    plain = LV.Levels(res)                                                 # Abhi Z-1x: no min width ⇒ nothing provisional, no label
    assert not any(x["provisional_width"] for x in plain.snapshot(plain.n - 1))
    lv = LV.Levels(res, s={"level_min_width_sigma": 0.15})                 # PF-2 only with the legacy min width (what-if)
    Z = [L for L in lv.L if abs(L.anchor - 120) < 1e-6][0]
    first_day_end = max(i for i in range(lv.n) if lv.ts.iloc[i].normalize() == days[0])
    x0 = [x for x in lv.snapshot(Z.born_bar) if x["id"] == Z.id][0]
    assert x0["provisional_width"] is True and x0["width_note"] == "provisional width"
    x1 = [x for x in lv.snapshot(first_day_end + 1) if x["id"] == Z.id][0]
    assert x1["provisional_width"] is False and x1["width_note"] is None   # σ_1H known ⇒ the spec width, label gone
    assert LV.width_tag(x0) == ", provisional width" and LV.width_tag(x1) == ""


# ------------------------------------------------------------------------------------------------ Abhi Z-1u: one timeframe per band
def _z1u_levels(monkeypatch, prior, s=None, extra=()):
    """A 1H D2 swing high 118 (band from its own candle) + Q40 prior bands injected at bar 0 (role, lo, hi, birth, anchor)."""
    monkeypatch.setattr(LV.Levels, "_prior_levels", lambda self: [tuple(x) for x in prior])
    closes = list(np.linspace(110, 118, 9)) + list(np.linspace(118, 112, 7))[1:] + list(np.linspace(112, 117.6, 6))[1:]
    m = m15_from(closes, wick=0.3)
    return m, LV.Levels(res_of(m, [P("H", 118, 8, 10)] + list(extra)), s=s)


def test_daily_and_weekly_bands_are_never_merged_into_the_1h_band_confluence_is_a_label(monkeypatch):
    m, lv = _z1u_levels(monkeypatch, [(LV.RES, 116.0, 125.0, "a:D-prior", 124.0), (LV.RES, 110.0, 130.0, "a:W-prior", 129.0)])
    t = len(m) - 1
    snap = {x["tf"]: x for x in lv.snapshot(t)}
    h, d, w = snap["1H"], snap["D"], snap["W"]
    assert (d["lo"], d["hi"], w["lo"], w["hi"]) == (116.0, 125.0, 110.0, 130.0)          # each band its own, never merged
    assert h["hi"] == 118.0 and h["lo"] > 116.0 and h["births"] == ["a:D2"]              # the 1H band from its own swing candle only
    assert h["confluence_label"] == "confluence: Daily 116–125; Weekly 110–130" and h["trade_location"]
    assert not d["trade_location"] and "1H band is the location" in d["not_location_why"]
    assert not w["trade_location"] and "context only" in w["not_location_why"]
    assert [x["id"] for x in lv.active(t, "DOWN")] == [h["id"]]                         # the narrower 1H band is the location


def test_a_daily_band_without_a_1h_zone_over_it_stays_a_location(monkeypatch):
    m, lv = _z1u_levels(monkeypatch, [(LV.RES, 121.0, 126.0, "a:D-prior", 126.0)])
    d = [x for x in lv.snapshot(len(m) - 1) if x["tf"] == "D"][0]
    assert d["trade_location"] and d["confluence"] == []


def test_bands_are_built_never_widened_same_timeframe_lineage(monkeypatch):
    """`Levels._born`: a birth inside an alive same-timeframe, same-role band = that zone (lineage, band unchanged); one overlapping it
    partly builds its own band (lineage recorded); another timeframe is never related by lineage — only by the confluence label. No
    band ever changes, and no level of the run ever had its band widened."""
    m, lv = _z1u_levels(monkeypatch, [])
    t = len(m) - 1
    Z = [L for L in lv.L if L.tf == "1H"][0]
    lo, hi = Z.band_at(t)
    same = lv._born(t, LV.RES, lo + 0.1, hi - 0.1, "a:D2", hi - 0.1)
    assert same is Z and Z.band_at(t) == (lo, hi) and Z.lineage[-1]["inside"] == "a:D2"
    part = lv._born(t, LV.RES, hi - 0.2, hi + 3.0, "a:D2", hi + 3.0)
    assert part is not Z and part.band_at(t) == (hi - 0.2, hi + 3.0) and part.lineage[-1]["overlaps"] == Z.id and Z.band_at(t) == (lo, hi)
    d = lv._born(t, LV.RES, lo - 5.0, hi + 5.0, "a:D-prior", hi + 5.0)
    assert d.tf == "D" and d.lineage == [] and Z.band_at(t) == (lo, hi) and part.band_at(t) == (hi - 0.2, hi + 3.0)
    for L in lv.L:
        assert len({(round(a_, 6), round(b_, 6)) for _, a_, b_ in L.bands}) == 1


def test_trade_band_max_width_setting_none_reports_set_excludes(monkeypatch):
    m, lv = _z1u_levels(monkeypatch, [])                                   # Abhi Z-1x (final): no number caps a zone ⇒ report only
    t = len(m) - 1
    assert S3.DEFAULTS["trade_band_max_sigma"] is None and "trade_band_max_sigma" in S3.REGISTER
    x = [y for y in lv.snapshot(t) if y["tf"] == "1H"][0]
    assert x["width"] > 0 and x["width_sigma"] == round(x["width"] / 10.0, 2) and x["trade_location"]   # None ⇒ report only
    _, lv2 = _z1u_levels(monkeypatch, [], s={"trade_band_max_sigma": x["width_sigma"] / 2})
    assert all(y["width_sigma"] <= x["width_sigma"] / 2 for y in lv2.active(t, "DOWN"))   # no traded band wider than the setting
    assert not [y for y in lv2.snapshot(t) if y["id"] == x["id"]][0]["trade_location"]


# ------------------------------------------------------------------------------------------------ Abhi Z-1v: handover per visit
def _visit_case(window):
    from tests.test_decision3_flip import _default_case
    return _default_case(window)


def test_a_close_outside_the_band_away_from_it_ends_the_visit_the_next_needs_a_new_handover():
    """tests.test_decision3_flip._default_case supply 19,432–19,472 (bear call): with the handover window intact ⇒ setup at 741. The
    same bars but 737 closes BELOW the band (away from it, no commitment) ⇒ that visit ends; the new visit starts at 738 and has too
    few bars for a handover ⇒ wait — the earlier handover never carries over."""
    from tests.test_decision3_flip import _HANDOVER
    ok = _visit_case(_HANDOVER).decide(741)
    assert ok["decision"] == "setup" and ok["commit"]["visit_start"] == ok["commit"]["study_from"]
    assert ok["commit"]["visit_start_bar"] == 735 and ok["commit"]["visit_end"] is None
    broken = list(_HANDOVER)
    broken[2] = (19455, 19425, 6e5)                                         # bar 737 closes below the band's low (away from it)
    V = _visit_case(broken)
    r = V.decide(741)
    cm = r["commit"]
    assert pd.Timestamp(cm["visit_prev_end"]) == pd.Timestamp(V._ts[737])
    assert cm["visit_start_bar"] == 738 and r["decision"] == "wait" and cm["handover_present"] is False
    assert "no handover" in r["checklist"]["⑥"][1]


def test_visit_is_not_defined_by_touch_window_bars():
    """touch_window_bars only says how far the commitment candle may be from the last touch (③); the visit (handover window) ends only on
    a close outside the band, away from it — non-touching bars that close inside the band's reach do not end it."""
    from tests.test_decision3_flip import _HANDOVER
    V = _visit_case(_HANDOVER)
    lvl = V.decide(741)["level"]
    for tw in (1, 3, 6):
        V.s = {**V.s, "touch_window_bars": tw}
        assert V.visit(741, lvl, DOWN)["start"] == 735
    legacy = {**V.s, "zone_visit_rule": "touch_window", "touch_window_bars": 3}
    V.s = legacy
    assert V.visit(741, lvl, DOWN, k0=700)["start"] is not None              # the legacy rule stays available for old tests only


# ------------------------------------------------------------------------------------------------ review notes
def test_absorption_gate_restarts_after_a_zone_break_like_the_episode():
    A = _A(HANDOVER + ABSORB + [(102.4, 102.5, 0.7)])
    t = len(HANDOVER + ABSORB)
    lvl = {"lo": 100.0, "hi": 103.0}
    full = M.zone_study(A, 0, t - 1, DOWN, S)
    late = M.zone_study(A, 8, t - 1, DOWN, S)
    assert full["absorption"] is True and late["absorption"] is False
    ho = M.handover_episode(A, 0, t, DOWN, S, broken=lambda u: u == 7)
    assert ho["window_start"] == 8
    cf = M.confirm(A, 0, t, DOWN, lvl, {**S, "ltf_choch": False}, handover=ho)
    assert cf["absorption"] is False                                        # the gate reads the same post-break window


@pytest.mark.parametrize("mirror", [False, True], ids=["bull", "bear"])
def test_engine_reclaim_before_the_first_post_break_swing_confirms_is_a_sweep_not_a_flip(mirror):
    """Abhi Z-1s: no swing beyond the zone ⇒ the first swing after the break flips it ON CONFIRMATION — but a reclaim (accept_closes
    back on the role's side) that comes BEFORE that swing is confirmed is a sweep ★: role kept, never a flip."""
    f = (lambda x: 2 * MID - x) if mirror else (lambda x: float(x))
    sw = (lambda k: ("L" if k == "H" else "H")) if mirror else (lambda k: k)
    anchors = [(0, 100), (8, 118), (16, 106), (22, 121), (28, 112), (34, 110)]
    closes = [float(anchors[0][1])]
    for (b0, p0), (b1, p1) in zip(anchors[:-1], anchors[1:]):
        closes += list(np.linspace(p0, p1, b1 - b0 + 1)[1:])
    m = m15_from([f(c) for c in closes], wick=0.3)
    p2 = [P(sw("H"), f(118), 8, 10), P(sw("L"), f(106), 16, 18), P(sw("H"), f(121), 22, 30)]   # confirmed late (bar 30)
    dz = [L for L in LV.Levels(res_of(m, p2)).L if abs(L.anchor - f(118)) < 1e-6][0]   # method §3: back inside before a swing formed
    assert not [k for _, k, _ in dz.events if k in ("broken", "flip", "dead")] and dz.count("sweep", len(m) - 1) >= 1   # beyond ⇒ sweep
    assert dz.role_at(len(m) - 1) == (LV.SUP if mirror else LV.RES)
    lv = LV.Levels(res_of(m, p2), s={"break_rule": "closes"})             # legacy break rule: broken, then reclaimed ⇒ sweep, no flip
    Z = [L for L in lv.L if abs(L.anchor - f(118)) < 1e-6][0]
    ev = [(b, k) for b, k, _ in Z.events if k in ("broken", "reclaim", "flip", "dead")]
    t_rc = next(b for b, k in ev if k == "reclaim")
    assert [k for _, k in ev][:2] == ["broken", "reclaim"] and t_rc < 30 and Z.count("flip", len(m) - 1) == 0
    assert Z.state_at(len(m) - 1) in ("ACTIVE", "TESTED") and Z.role_at(len(m) - 1) == (LV.SUP if mirror else LV.RES)
    assert Z.count("sweep", len(m) - 1) >= 1


def test_band_facts_reclaim_before_the_first_post_break_swing_confirms_is_a_sweep():
    from facts import validity as FV
    hi = [96.5, 97.0, 96.0, 97.5, 96.5, 97.2, 96.0, 97.4, 96.4, 97.0] * 2 + [99.0, 100.0, 96.0, 95.5, 95.0, 94.8]
    cl = [h - 0.6 for h in hi]
    lo = [h - 1.0 for h in hi]
    ts = pd.date_range("2030-01-07 09:15", periods=len(hi), freq="15min")
    B = FV.bars_of(pd.DataFrame({"timestamp": ts, "open": cl, "high": hi, "low": lo, "close": cl}))
    x = {"lo": 95.0, "hi": 98.0, "breaks": [{"bar": 20, "dir": "up"}, {"bar": 22, "dir": "down"}]}   # swing @21 confirms at 23
    f = LV.band_flip_facts(B, len(hi) - 1, x, start=0)
    assert f["flip_state"] == "ACTIVE" and f["flipped_at"] is None and [w["bar"] for w in f["sweeps"]] == [22]


# ------------------------------------------------------------------------------------------------ live: per-timeframe bands, confluence label
def test_live_watched_levels_show_only_location_bands_with_confluence_as_a_label():
    import engine3_live as L3
    from bots_common import plain_text as PT
    from scripts import level_gate_preopen as PO
    snap = [{"id": 1, "tf": "1H", "role": "resistance", "lo": 22543.75, "hi": 22621.8, "state": "TESTED", "trade_location": True,
             "confluence_label": "confluence: Weekly 22,476–22,795"},
            {"id": 2, "tf": "W", "role": "resistance", "lo": 22475.85, "hi": 22794.7, "state": "FLIPPED", "trade_location": False},
            {"id": 3, "tf": "D", "role": "resistance", "lo": 22725.45, "hi": 22809.9, "state": "FLIPPED", "trade_location": True}]
    keep = L3.tradeable_levels(snap)
    assert [x["id"] for x in keep] == [1, 3]                                # the Weekly band never shows as an area
    rows = PO.engine_zone_rows(snap)
    assert list(rows["zone_type"]) == ["ENGINE_LEVEL_1H|confluence: Weekly 22,476–22,795", "ENGINE_LEVEL_1D"]
    assert PT.tf_word(rows["zone_type"].iloc[0]) == "1H" and PT.zone_note(rows["zone_type"].iloc[0]) == "confluence: Weekly 22,476–22,795"
    words = PO.area_words("BEARISH", 22543.75, 22621.8, rows["zone_type"].iloc[0], 22400.0)
    assert words.startswith("supply 22,544–22,622 (1H,") and words.endswith("; confluence: Weekly 22,476–22,795), 78 pts wide")
    from bots_common import level_reaction as LR
    areas = PO.trade_side_areas(rows, PO.ENGINE_TFS, 22400.0, {"ok": True, "trend": "DOWN", "sides": {LR.BEAR}}, 3)
    assert {round(a[1]) for a in areas} == {22544, 22725}


def test_unknown_zone_visit_rule_fails_loudly():
    """Reviewer (Z-1v): a typo in `zone_visit_rule` must never silently pick a visit rule — V22 refuses at start, and again if the setting
    is changed later (visit() checks too)."""
    from tests import oct12_fixture as F
    m15, fut, ltf = F.build(mirror=False)
    with pytest.raises(ValueError, match="unknown zone_visit_rule 'close-away'"):
        E3.V22(m15, s={"zone_visit_rule": "close-away"}, ltf=ltf, futures=fut)
    V = E3.V22(m15, ltf=ltf, futures=fut)
    V.s["zone_visit_rule"] = "touch"
    with pytest.raises(ValueError, match="unknown zone_visit_rule 'touch'"):
        V.visit(len(m15) - 1, {"lo": 1.0, "hi": 2.0, "id": None}, -1)


def test_live_row_payload_carries_the_level_timeframe_and_confluence_label():
    """Abhi Z-1u: the engine_signal row payload keeps the 1H zone's own timeframe and its "confluence: Daily …" label (evidence only)."""
    import json
    import engine3_live as L
    r = {"bar_end": "2030-03-04 10:00:00", "decision": "wait", "checklist": {"①": [True, ""]}, "conviction": None, "risk": None,
         "level": {"id": 7, "tf": "1H", "role": "resistance", "lo": 22543.75, "hi": 22621.8,
                   "confluence_label": "confluence: Daily 22,476–22,795"}}
    lv = json.loads(L.row_from_v22("NIFTY", r, lambda: "2030-03-04 10:00:05")["payload"])["level"]
    assert lv["tf"] == "1H" and lv["confluence_label"] == "confluence: Daily 22,476–22,795" and (lv["lo"], lv["hi"]) == (22543.75, 22621.8)


# ------------------------------------------------------------------------------------------------ Abhi Z-1z / Z-1y / Z-1x (logic, no numbers)
def _pair(c2_close=97.2, o2=99.5, earlier=()):
    """supply 100–102 (bear call): candle 1 pushes into the zone and is rejected by an upper wick longer than its body; candle 2 = a red
    candle. earlier = (open, high, low, close) candles of the visit before candle 1."""
    rows = list(earlier) + [(99.0, 101.5, 98.5, 99.2), (o2, max(o2, 99.6), 97.0, c2_close)]
    A = {k: np.array([r[j] for r in rows], float) for j, k in enumerate(("open", "high", "low", "close"))}
    return A, len(rows) - 1


def test_two_candle_push_rejected_and_swallowed_is_a_handover_by_comparison_only():
    """Abhi Z-1z: a push rejected and immediately swallowed by a dominant opposite candle is a handover in itself — no minimum count,
    no ratio, no volume in this read (volume is the commitment's own comparison)."""
    A, i = _pair()
    sr = M.sharp_reversal(A, i, DOWN, 100.0, 102.0, a0=0)
    assert sr["found"] is True and all(sr["parts"].values())
    ho = M.handover_episode(A, 0, i, DOWN, S, sharp=lambda j, a0: M.sharp_reversal(A, j, DOWN, 100.0, 102.0, a0=a0))
    assert ho["present"] is True and ho["form"] == "sharp_reversal" and ho["seen_at"] == i          # candle 2 = the commitment bar
    for k in ("study_min_bars", "commit_dom_mult", "sharp_rej_wick_body"):
        assert k not in S3.DEFAULTS                                       # Abhi: no numbers in the reading rules
    big = (99.0, 99.9, 96.0, 96.2)                                        # an earlier visit candle larger than candle 2 ⇒ not dominant
    A2, i2 = _pair(earlier=[big])
    sr2 = M.sharp_reversal(A2, i2, DOWN, 100.0, 102.0, a0=0)
    assert sr2["found"] is False and sr2["parts"]["c2_dominant"] is False and "as large or larger" in sr2["why"]


def test_two_candle_read_names_every_missing_part():
    """Not swallowed: candle 2 opens below candle 1's body top and closes short of candle 1's low ⇒ not a handover; both parts named."""
    A, i = _pair(c2_close=98.6, o2=99.1)
    sr = M.sharp_reversal(A, i, DOWN, 100.0, 102.0, a0=0)
    assert sr["found"] is False and sr["parts"]["c2_engulfs_body"] is False and sr["parts"]["c2_closes_beyond_c1"] is False
    assert "does not cover candle 1's body" in sr["why"] and "does not close beyond candle 1's low" in sr["why"]
    assert M.sharp_reversal(A, 0, DOWN, 100.0, 102.0, a0=0)["why"] == "candle 1 is not inside the visit"


def test_commitment_dominance_and_volume_are_comparisons_within_the_visit():
    """Abhi: dominant = larger than every other candle of the visit; volume = larger than the opposite side's candles of the visit."""
    A, i = _pair()
    A["volume"] = np.array([500.0, 900.0])                                  # candle 2 (commitment) volume above the opposite-side candle 1?
    lvl = {"lo": 100.0, "hi": 102.0}
    ok, why, cm = M.commitment(A, i, DOWN, lvl, S, win=0)
    assert cm.get("body_mult") is not None and cm["body_mult"] > 1.0
    A["volume"] = np.array([900.0, 500.0])
    ok2, why2, cm2 = M.commitment(A, i, DOWN, lvl, S, win=0)
    assert ok and cm["vol_vs"] == "opposite-side candles" and not ok2 and "not larger than the opposite-side candles" in why2 and "low volume" in why2
    red = {k: v.copy() for k, v in A.items()}
    red["open"][0], red["close"][0] = 99.4, 99.2                             # candle 1 red too ⇒ no opposite-side candle in the visit
    ok3, _, cm3 = M.commitment(red, i, DOWN, lvl, S, win=0)
    assert ok3 and cm3["vol_vs"] == "no opposite-side candle in this visit" and cm3["grade"] == "B"   # nothing compared ⇒ fail-safe cap B


def test_far_swing_is_the_structural_swing_a_sweep_wick_beyond_the_band_is_not():
    """Abhi Z-1y (a): band 100–102 broken upward; swing highs beyond it: 106 (its candle closed 104 — structural) and 103 (a wick whose
    candle closed back inside at 101 — a sweep). The far swing is 106, never the sweep wick 103 (that would flip on every false break)."""
    from types import SimpleNamespace as N
    from decision3 import flip as FL
    known = [N(kind="H", price=106.0, bar=2, confirm_bar=3), N(kind="H", price=103.0, bar=5, confirm_bar=6)]
    closes = np.array([100, 101, 104, 101, 100, 101, 100, 99, 101, 103], float)
    assert FL.far_swing(known, 100.0, 102.0, True, 8, closes).price == 106.0
    assert FL.far_swing(known, 100.0, 102.0, True, 8).price == 103.0                     # without closes (old callers): unchanged
    assert FL.structural(101.0, 100.0, 102.0, True) is False and FL.structural(99.0, 100.0, 102.0, False) is True


def test_zone_width_has_no_number_cap_and_no_min_width():
    """Abhi Z-1x (final): a zone is its own base / reaction candles — never widened by a minimum width, never capped by a number; a zone
    that looks too wide is a construction problem (Z-1u), not a setting. No dashboard width setting."""
    import cloud_db
    import engine3_live as L3
    assert S3.DEFAULTS["trade_band_max_sigma"] is None and S3.DEFAULTS["level_min_width_sigma"] == 0.0
    assert "engine3_band_max_sigma" not in L3.DEFAULTS and "engine3_band_max_sigma" not in cloud_db.STRATEGY_SETTINGS_DEFAULTS["15m_dynamic_sr"]
    assert LV._band_swing("H", 10.0, 12.0, 9.0, 10.5, 12.0, 0.0) == (10.5, 12.0)   # wick-to-body only
    assert LV._band_swing("H", 10.0, 12.0, 9.0, 12.0, 12.0, 0.0) == (10.0, 12.0)   # closed at its high ⇒ its body (never one price)
    assert LV._band_swing("L", 9.0, 12.0, 9.0, 9.0, 9.0, 0.0) == (9.0, 12.0)       # no wick, no body ⇒ the whole candle


# ------------------------------------------------------------------------------------------------ Abhi's method §3: sweep / broken
def _break_case(beyond_swing):
    """resistance 116.3–118 (a D2 high at 118); price closes above it; with `beyond_swing` a finer swing forms above the band before
    price returns, otherwise price returns inside first."""
    closes = list(np.linspace(110, 118, 9)) + list(np.linspace(118, 112, 7))[1:] + [114, 116, 118.6, 119.4, 120.2, 119.0, 118.4, 117.0, 115.0, 113.0]
    m = m15_from(closes, wick=0.3)
    p2 = [P("H", 118, 8, 10)]
    p1 = [P("H", 118, 8, 10), P("L", 112, 14, 16)] + ([P("H", 120.5, 20, 22)] if beyond_swing else [])
    return m, LV.Levels(res_of(m, p2, p1))


def test_structural_break_needs_a_swing_formed_beyond_the_area():
    """Abhi's method §3: broken = a close beyond AND a swing formed beyond; a poke that returns inside before any swing forms beyond is
    a sweep (role kept). No count of closes."""
    m, lv = _break_case(beyond_swing=True)
    Z = [L for L in lv.L if abs(L.anchor - 118) < 1e-6][0]
    brk = [b for b, k, _ in Z.events if k == "broken"]
    assert brk and brk[0] >= 22 and "a swing formed beyond it" in [d for b, k, d in Z.events if k == "broken"][0]
    m, lv = _break_case(beyond_swing=False)
    Z = [L for L in lv.L if abs(L.anchor - 118) < 1e-6][0]
    assert not [k for _, k, _ in Z.events if k in ("broken", "flip")] and Z.count("sweep", len(m) - 1) >= 1 and Z.role_at(len(m) - 1) == LV.RES
    assert S3.DEFAULTS["break_rule"] == "structure"
    with pytest.raises(ValueError, match="break_rule"):
        LV.Levels(res_of(m, [P("H", 118, 8, 10)]), s={"break_rule": "two_closes"})



def test_equal_highs_by_comparison_and_every_area_ahead_is_armed():
    """Abhi's method §3 "equal": a later swing high that reaches the earlier swing's own band and does not go beyond it ⇒ the same area
    reacted twice (liquidity "d"), no σ tolerance. §4 Watch: every valid area ahead in the trend direction is armed, nearest first."""
    closes = list(np.linspace(110, 118, 9)) + list(np.linspace(118, 112, 7))[1:] + list(np.linspace(112, 117.9, 7))[1:] + \
        list(np.linspace(117.9, 111, 6))[1:]
    m = m15_from(closes, wick=0.3)
    lv = LV.Levels(res_of(m, [P("H", 118, 8, 10), P("L", 112, 14, 16), P("H", 117.9, 20, 22)]))
    Z = [L for L in lv.L if abs(L.anchor - 118) < 1e-6][0]
    assert "d" in Z.births or any(x.get("inside") == "d" for x in Z.lineage)   # the second top is inside the first top's band
    assert S3.DEFAULTS["liquidity_rule"] == "equal"
    far = LV.Levels(res_of(m, [P("H", 118, 8, 10), P("L", 112, 14, 16), P("H", 116.5, 20, 22)]))   # 116.5 is below the band ⇒ not equal
    Zf = [L for L in far.L if abs(L.anchor - 118) < 1e-6][0]
    assert "d" not in Zf.births and not any(x.get("inside") == "d" for x in Zf.lineage)
    t = len(m) - 1
    act = lv.active(t, "DOWN")
    assert [x["dist"] for x in act] == sorted(x["dist"] for x in act)          # nearest first, no count cap
    assert len(act) == len([x for x in lv.snapshot(t) if x["role"] == LV.RES and not x["below"] and x.get("state") != "BROKEN"
                            and x.get("trade_location", True)])
