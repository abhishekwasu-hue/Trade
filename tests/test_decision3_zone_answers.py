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
    assert ch2["done"] is True and ch2["after_arrival"] is True and pd.Timestamp(ch2["at"]) > pd.Timestamp(ch2["arrival_at"])


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
    lv = LV.Levels(res)
    Z = [L for L in lv.L if abs(L.anchor - 120) < 1e-6][0]
    first_day_end = max(i for i in range(lv.n) if lv.ts.iloc[i].normalize() == days[0])
    x0 = [x for x in lv.snapshot(Z.born_bar) if x["id"] == Z.id][0]
    assert x0["provisional_width"] is True and x0["width_note"] == "provisional width"
    x1 = [x for x in lv.snapshot(first_day_end + 1) if x["id"] == Z.id][0]
    assert x1["provisional_width"] is False and x1["width_note"] is None   # σ_1H known ⇒ the spec width, label gone
    assert LV.width_tag(x0) == ", provisional width" and LV.width_tag(x1) == ""
