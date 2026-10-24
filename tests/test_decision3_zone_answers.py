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
SIDEWAYS = [(100.9, 101.1, 0.6), (101.1, 101.0, 0.5), (101.0, 101.15, 0.6), (101.15, 101.05, 0.5), (101.05, 101.2, 0.6),
            (101.2, 101.1, 0.5)]                                     # method §3 absorption: small buying candles keep coming, price stuck
LEGACY_K = {"entry_gate": "legacy_k"}                               # Abhi 21 Oct: the old ③ gate + the old visit end (exact old behaviour)
LEGACY_ABSORB = {**S3.load(), "absorption_rule": "strengthening"}     # the #329 read (counter side strengthening), what-if only


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
    # method §3 slow form: candles AND volume — in window 0 … 4 the buying volume is still above the selling volume (no tilt), 0 … 5 tilts
    assert ho["present"] is True and ho["seen_at"] == 5 and ho["cancelled"] is None
    assert M.zone_study(A, 0, 4, d, S)["vol_tilt"] is False and M.zone_study(A, 0, 5, d, S)["vol_tilt"] is True
    cut = {k: v[:t] for k, v in A.items()}                                 # no look-ahead: same answer on data cut at the decision bar
    assert M.handover_episode(cut, 0, t, d, S) == M.handover_episode(A, 0, t, d, S)
    assert M.handover_episode(A, 0, 5, d, S)["present"] is False           # not yet seen before its window closed


@pytest.mark.parametrize("mirror", [False, True], ids=["bear", "bull"])
def test_sticky_handover_is_cancelled_by_a_later_absorption(mirror):
    """Method §3 absorption: after the handover, small buying candles keep coming and price does not move away (a sideways base) ⇒ the
    handover is cancelled. Buying candles growing LARGE (ABSORB) are not absorption under the method — that side taking control is the
    K4 break's business; the #329 "strengthening" read stays a what-if."""
    d = UP if mirror else DOWN
    A = _A(HANDOVER + SIDEWAYS, mirror)
    ho = M.handover_episode(A, 0, len(HANDOVER + SIDEWAYS), d, S)
    assert ho["present"] is False and ho["seen_at"] == 5 and ho["cancelled"] == "absorption" and ho["cancelled_at"] == 13
    z = M.zone_study(A, 0, 13, d, S)
    assert z["absorption"] is True and "keeps coming in small candles and price does not move away (absorption)" in z["line"]
    A2 = _A(HANDOVER + ABSORB, mirror)
    assert M.handover_episode(A2, 0, len(HANDOVER + ABSORB), d, S)["cancelled"] is None
    ho2 = M.handover_episode(A2, 0, len(HANDOVER + ABSORB), d, LEGACY_ABSORB)
    assert ho2["present"] is False and ho2["cancelled"] == "absorption" and ho2["cancelled_at"] == 11


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
    assert sticky["handover"] is True and sticky["wait"] != M.C_NO_HANDOVER and sticky["handover_state"]["seen_at"] == 5
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
    return E3.V22(m15, ltf=split_bars(m15, 15, 3), futures=fut, s=LEGACY_K)


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
    """Legacy Z-1v (`zone_visit_rule = close_away`, what-if): tests.test_decision3_flip._default_case supply 19,432–19,472 (bear call):
    with the handover window intact ⇒ setup at 741. The same bars but 737 closes BELOW the band ⇒ that visit ends; the new visit starts
    at 738 and has too few bars for a handover ⇒ wait. Method §3 (default): that candle closed just outside without a handover, so it is
    not a failed commitment — the SAME visit continues (it starts at 735)."""
    from tests.test_decision3_flip import _HANDOVER
    ok = _visit_case(_HANDOVER).decide(741)
    assert ok["decision"] == "setup" and ok["commit"]["visit_start"] == ok["commit"]["study_from"]
    assert ok["commit"]["visit_start_bar"] == 735 and ok["commit"]["visit_end"] is None
    broken = list(_HANDOVER)
    broken[2] = (19455, 19425, 6e5)                                         # bar 737 closes below the band's low (away from it)
    V = _visit_case(broken)
    r = V.decide(741)
    assert r["commit"]["visit_start_bar"] == 735 and r["commit"]["visit_prev_end"] != str(pd.Timestamp(V._ts[737]))   # same visit
    assert r["decision"] == "wait" and r["commit"]["confirm_wait"] == M.C_ABSORB   # read on the whole visit: the buyers keep coming
    V.s = {**V.s, "zone_visit_rule": "close_away", "commit_volume_rule": "opposite"}
    cm = V._confirm(741, DOWN, r["level"], V.pb.at(741, DOWN))[2]
    assert pd.Timestamp(cm["visit_prev_end"]) == pd.Timestamp(V._ts[737])
    assert cm["visit_start_bar"] == 738 and cm["handover_present"] is False


def _visit_v(rows, swings=(), d=DOWN, lvl=(100.0, 102.0), s=None):
    """A bare V22 for `visit` (structure): rows = (open, high, low, close); swings = (kind, price, bar, confirm_bar) of the finest
    structure degree; one area born at bar 0."""
    from types import SimpleNamespace as NS
    V = E3.V22.__new__(E3.V22)
    V.s = S3.load(s)
    A = {k: np.array([r[j] for r in rows], float) for j, k in enumerate(("open", "high", "low", "close"))}
    A["volume"] = np.full(len(rows), 1.0)
    V.levels = NS(A=A, _known0=[NS(kind=k, price=float(p), bar=b, confirm_bar=c) for k, p, b, c in swings],
                  L=[NS(born_bar=0, state_at=lambda u: "ACTIVE")])
    V._ts = pd.date_range("2030-01-07 09:15", periods=len(rows), freq="15min").to_numpy()
    V.vol_view = lambda a, t: (A, "raw")
    return V, {"id": 0, "lo": lvl[0], "hi": lvl[1]}


def test_visit_ends_only_by_structure_a_swing_built_away_from_the_area():
    """Method §3 Visit: a supply visit (100–102) — price closes just below and comes back: the same visit; time never ends it. A swing low
    built below the area (confirmed) ends it; the next entry is a new visit whose approach leg starts after that swing."""
    rows = [(98.0, 98.6, 97.8, 98.5), (98.5, 100.6, 98.4, 100.4), (100.4, 100.9, 99.6, 99.8), (99.8, 100.7, 99.7, 100.5),   # 1: enters
            (100.5, 100.8, 99.0, 99.2), (99.2, 99.4, 97.9, 98.1), (98.1, 99.5, 98.0, 99.4), (99.4, 100.9, 99.3, 100.6)]       # 5: swing low
    V, lvl = _visit_v(rows)
    assert V.visit(3, lvl, DOWN)["start"] == 1                              # bar 2 closed just outside, bar 3 back ⇒ the same visit
    assert V.visit(7, lvl, DOWN)["start"] == 1                              # no swing built away yet ⇒ still the same visit
    V2, _ = _visit_v(rows, swings=[("L", 97.9, 5, 7)])
    vi = V2.visit(7, lvl, DOWN)
    assert (vi["start"], vi["prev_end"], vi["ended_by"], vi["approach_from"]) == (7, 5, "swing", 6)
    assert V2.visit(6, lvl, DOWN)["start"] == 1                             # the swing is not known before its confirmation (no look-ahead)
    V3, _ = _visit_v(rows, swings=[("L", 100.5, 3, 5)])                     # a swing low INSIDE the area is not "away from it"
    assert V3.visit(7, lvl, DOWN)["start"] == 1
    mirror = [(2 * 101 - o, 2 * 101 - lo, 2 * 101 - h, 2 * 101 - c) for o, h, lo, c in rows]   # demand 100–102, price from above
    Vm, lm = _visit_v(mirror, swings=[("H", 2 * 101 - 97.9, 5, 7)], d=UP)
    assert (Vm.visit(7, lm, UP)["start"], Vm.visit(7, lm, UP)["ended_by"]) == (7, "swing")


def test_visit_ends_when_a_commitment_after_the_handover_closes_outside(monkeypatch):
    """Method §3 Visit: "a commitment fails and closes outside (then the move is gone; no chasing)" — the commitment is the dominant
    trade-side candle AFTER the handover. The same candle without a handover present is only a candle that closed outside."""
    rows = [(98.0, 98.6, 97.8, 98.5), (98.5, 100.6, 98.4, 100.4), (100.4, 100.9, 100.1, 100.3), (100.3, 100.5, 97.6, 97.8),   # 3: dominant
            (97.8, 100.7, 97.7, 100.5)]                                                                                         # red, closes out
    V, lvl = _visit_v(rows, s=LEGACY_K)                                     # Abhi 21 Oct: this end is legacy_k only (the new default: the
    # same visit continues — tests/test_decision3_entry_models.py)
    monkeypatch.setattr(V, "handover_episode", lambda A, a, t, d, l: {"present": False})
    assert V.visit(4, lvl, DOWN)["start"] == 1                              # no handover ⇒ the same visit
    monkeypatch.setattr(V, "handover_episode", lambda A, a, t, d, l: {"present": True})
    V._visit_memo, V._fco_memo = {}, {}                                    # a new "world" for the same bars (the memo is per world)
    vi = V.visit(4, lvl, DOWN)
    assert (vi["start"], vi["prev_end"], vi["ended_by"]) == (4, 3, "commitment") and "no chasing" not in str(vi["why"])
    gone = V.visit(3, lvl, DOWN)                                            # at its own bar it is still the commitment being judged
    assert gone["start"] == 1


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
@pytest.mark.parametrize("rule", ["method", "strengthening"])
def test_absorption_gate_restarts_after_a_zone_break_like_the_episode(rule):
    tail = SIDEWAYS if rule == "method" else ABSORB
    s = {**S3.load(), "absorption_rule": rule}
    A = _A(HANDOVER + tail + [(101.1, 101.15, 0.5)])
    t = len(HANDOVER + tail)
    lvl = {"lo": 100.0, "hi": 103.0}
    full = M.zone_study(A, 0, t - 1, DOWN, s)
    late = M.zone_study(A, 8, t - 1, DOWN, s)
    assert full["absorption"] is True and late["absorption"] is False
    ho = M.handover_episode(A, 0, t, DOWN, s, broken=lambda u: u == 7)
    assert ho["window_start"] == 8
    cf = M.confirm(A, 0, t, DOWN, lvl, {**s, "ltf_choch": False}, handover=ho)
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
    """Method §3 fast form: the dominant opposite candle must close beyond the push candle's BODY (not its extreme, no body cover).
    Candle 2 opens below candle 1's body top and closes below its body (short of its low) ⇒ a fast-form handover under the method; the
    #329 read (body cover + close beyond the low) names both of its missing parts. A close inside the push body ⇒ not a handover."""
    A, i = _pair(c2_close=98.6, o2=99.1)
    sr = M.sharp_reversal(A, i, DOWN, 100.0, 102.0, S, a0=0)
    assert sr["found"] is True and sr["parts"] == {"c1_rejected": True, "c2_dominant": True, "c2_closes_beyond_push_body": True}
    old = M.sharp_reversal(A, i, DOWN, 100.0, 102.0, {**S, "fast_form_rule": "engulf"}, a0=0)
    assert old["found"] is False and old["parts"]["c2_engulfs_body"] is False and old["parts"]["c2_closes_beyond_c1"] is False
    assert "does not cover candle 1's body" in old["why"] and "does not close beyond candle 1's low" in old["why"]
    A3, i3 = _pair(c2_close=99.1, o2=99.15)                                # closes inside the push candle's body (99.0 – 99.2)
    A3["high"][i3 - 1] = 101.5
    sr3 = M.sharp_reversal(A3, i3, DOWN, 100.0, 102.0, S, a0=0)
    assert sr3["found"] is False and "does not close beyond the push candle's body" in sr3["why"]
    assert M.sharp_reversal(A, 0, DOWN, 100.0, 102.0, a0=0)["why"] == "candle 1 is not inside the visit"
    with pytest.raises(ValueError, match="fast_form_rule"):
        M.sharp_reversal(A, i, DOWN, 100.0, 102.0, {**S, "fast_form_rule": "swallow"}, a0=0)


def test_commitment_dominance_and_volume_are_comparisons_within_the_visit():
    """Abhi: dominant = larger than every other candle of the visit; volume = higher than the average of its comparison set (here the
    visit's opposite-side candles)."""
    A, i = _pair()
    A["volume"] = np.array([500.0, 900.0])                                  # candle 2 (commitment) volume above the opposite-side candle 1?
    lvl = {"lo": 100.0, "hi": 102.0}
    ok, why, cm = M.commitment(A, i, DOWN, lvl, S, win=0)
    assert cm.get("body_mult") is not None and cm["body_mult"] > 1.0
    A["volume"] = np.array([900.0, 500.0])
    ok2, why2, cm2 = M.commitment(A, i, DOWN, lvl, S, win=0)
    assert ok and cm["vol_vs"] == "the average of the visit's opposite-side candles" and not ok2 and "low volume" in why2
    assert "not higher than the average of the visit's opposite-side candles" in why2   # no approach leg given ⇒ named as compared
    red = {k: v.copy() for k, v in A.items()}
    red["open"][0], red["close"][0] = 99.4, 99.2                             # candle 1 red too ⇒ no opposite-side candle in the visit
    ok3, why3, cm3 = M.commitment(red, i, DOWN, lvl, S, win=0)              # Abhi (L3-c): never an automatic pass — no approach leg known
    assert not ok3 and "nothing to compare" in why3 and cm3.get("wait") == "no_volume_reference"   # no opposite candle ⇒ no commitment
    legacy = {**S, "commit_volume_rule": "opposite"}
    ok4, _, cm4 = M.commitment(red, i, DOWN, lvl, legacy, win=0)
    assert ok4 and cm4["vol_vs"] == "no opposite-side candle in this visit" and cm4["grade"] == "B"   # the #329 fail-safe, what-if only


def test_commitment_volume_is_compared_with_the_approach_leg_and_the_opposite_side_without_the_push():
    """Method §3 Commitment (Abhi, L3-c): volume higher than the AVERAGE of the approach leg's candles and the visit's opposite-side
    candles; the rejected push and the commitment itself are not part of that comparison; one heavy candle never decides."""
    rows = [(97.0, 97.6, 96.8, 97.5), (97.5, 98.4, 97.4, 98.3), (98.3, 99.2, 98.2, 99.1),          # approach leg (bars 0–2)
            (99.0, 101.5, 98.5, 99.2), (99.3, 99.6, 97.0, 97.2)]                                  # push (3) + commitment (4)
    A = {k: np.array([r[j] for r in rows], float) for j, k in enumerate(("open", "high", "low", "close"))}
    lvl = {"lo": 100.0, "hi": 102.0}
    A["volume"] = np.array([300.0, 400.0, 500.0, 3000.0, 900.0])           # the push has the largest volume — excluded
    ok, why, cm = M.commitment(A, 4, DOWN, lvl, S, win=3, approach=range(0, 3), exclude=[3])
    assert ok and cm["vol_vs"] == "the average of the approach leg's candles" and cm["vol_ref_n"] == 3 and cm["vol_mult"] == 2.25
    ok2, why2, _ = M.commitment(A, 4, DOWN, lvl, S, win=3, approach=range(0, 3))   # push not excluded ⇒ average 1,050 ⇒ low volume
    assert not ok2 and "low volume" in why2
    A["volume"][0] = 1000.0                                                 # one approach candle heavier than the commitment (a pullback
    ok3, why3, cm3 = M.commitment(A, 4, DOWN, lvl, S, win=3, approach=range(0, 3), exclude=[3])   # may start on heavy volume): the
    assert ok3 and cm3["vol_ref_avg"] == 633.3                              # average decides, not the largest candle
    A["volume"][:3] = 1000.0                                                # the leg as a whole heavier ⇒ low volume
    ok4, why4, _ = M.commitment(A, 4, DOWN, lvl, S, win=3, approach=range(0, 3), exclude=[3])
    assert not ok4 and "average of the approach leg" in why4
    A["volume"][:3] = 900.0                                                 # equal to the average ⇒ not higher ⇒ low volume (strict)
    ok5, why5, _ = M.commitment(A, 4, DOWN, lvl, S, win=3, approach=range(0, 3), exclude=[3])
    assert not ok5 and "low volume" in why5
    with pytest.raises(ValueError, match="commit_volume_rule"):
        M.commitment(A, 4, DOWN, lvl, {**S, "commit_volume_rule": "x"}, win=3)


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
def _mirror(mirror):
    f = (lambda x: 2 * MID - x) if mirror else (lambda x: float(x))     # noqa: E731
    sw = (lambda k: ("L" if k == "H" else "H")) if mirror else (lambda k: k)   # noqa: E731
    return f, sw


def _break_case(beyond_swing, mirror=False, tail=None, last=None):
    """resistance 116.3–118 (a D2 high at 118); price closes above it; with `beyond_swing` a finer swing forms above the band before
    price returns, otherwise price returns inside first. `tail` = closes after that (with `last` = an extra finer swing). mirror ⇒
    support breaking down (every price reflected, H ⇄ L)."""
    f, sw = _mirror(mirror)
    closes = list(np.linspace(110, 118, 9)) + list(np.linspace(118, 112, 7))[1:] + [114, 116, 118.6, 119.4, 120.2, 119.0, 118.4] + \
        (tail if tail is not None else [117.0, 115.0, 113.0])
    m = m15_from([f(c) for c in closes], wick=0.3)
    p2 = [P(sw("H"), f(118), 8, 10)]
    p1 = [P(sw("H"), f(118), 8, 10), P(sw("L"), f(112), 14, 16)] + ([P(sw("H"), f(120.5), 20, 22)] if beyond_swing else []) + \
        ([P(sw(last[0]), f(last[1]), last[2], last[3])] if last else [])
    return m, LV.Levels(res_of(m, p2, p1)), f


def _zone(lv, f):
    return [L for L in lv.L if abs(L.anchor - f(118)) < 1e-6][0]


@pytest.mark.parametrize("mirror", [False, True], ids=["resistance-up", "support-down"])
@pytest.mark.usefixtures("earlier_break_reading")   # BREAK-1: the earlier reading, what-if (tests/test_break_hold.py = default)
def test_structural_break_needs_a_swing_formed_beyond_the_area(mirror):
    """Abhi's method §3: broken = a close beyond AND a swing formed beyond; a poke that returns inside before any swing forms beyond is
    a sweep (role kept). No count of closes. Mirror: support breaking down."""
    m, lv, f = _break_case(True, mirror)
    Z = _zone(lv, f)
    brk = [b for b, k, _ in Z.events if k == "broken"]
    assert brk == [22] and "a swing formed beyond it" in [d for b, k, d in Z.events if k == "broken"][0]   # the swing's confirm bar
    m, lv, f = _break_case(False, mirror)
    Z = _zone(lv, f)
    assert not [k for _, k, _ in Z.events if k in ("broken", "flip")] and Z.count("sweep", len(m) - 1) >= 1
    assert Z.role_at(len(m) - 1) == (LV.SUP if mirror else LV.RES)
    assert S3.DEFAULTS["break_rule"] == "structure"
    with pytest.raises(ValueError, match="break_rule"):
        LV.Levels(res_of(m, [P("H", 118, 8, 10)]), s={"break_rule": "two_closes"})


@pytest.mark.usefixtures("earlier_break_reading")   # BREAK-1: the earlier reading, what-if (tests/test_break_hold.py = default)
def test_a_d0_wiggle_beyond_the_area_is_not_a_swing_for_the_break():
    """Method §3 "small wiggles inside a leg are not swings": the swing formed beyond must be of the structure (Abhi's approved D1 / D2,
    swings2 `structure_degrees`). The same turn beyond the band only at D0 ⇒ sweep; at D1 ⇒ broken."""
    m, _, f = _break_case(False)
    res = res_of(m, [P("H", 118, 8, 10)], [P("H", 118, 8, 10), P("L", 112, 14, 16)])
    res["pivots"][0] = [P("H", 120.5, 20, 22)]
    Z = _zone(LV.Levels(res), f)
    assert not [b for b, k, _ in Z.events if k == "broken"] and Z.count("sweep", len(m) - 1) >= 1
    res["pivots"][1] = res["pivots"][1] + [P("H", 120.5, 20, 22)]
    assert [b for b, k, _ in _zone(LV.Levels(res), f).events if k == "broken"] == [22]


@pytest.mark.parametrize("mirror", [False, True], ids=["resistance", "support"])
@pytest.mark.usefixtures("earlier_break_reading")   # BREAK-1: the earlier reading, what-if (tests/test_break_hold.py = default)
def test_structural_reclaim_mirrors_the_break(mirror):
    """The break's mirror (OPEN_QUESTIONS L2-b): a BROKEN area is reclaimed by a close back on its role side (outside the band) AND a
    swing formed there. Like the break, the swing counts when it is confirmed on a bar that itself closes back inside the band; a close
    back inside BEFORE the swing is confirmed ends the attempt (as a poke back inside ends the break's excursion ⇒ sweep)."""
    # bars 22 … 28: the break confirms at 22; closes below the band from 23; the swing low at 25 confirms at 28, which closes inside
    m, lv, f = _break_case(True, mirror, tail=[117.0, 115.0, 113.0, 111.0, 112.5, 114.0, 117.3], last=("L", 110.7, 25, 28))
    Z = _zone(lv, f)
    ev = [(b, k) for b, k, _ in Z.events if k in ("broken", "reclaim", "flip")]
    assert ev == [(22, "broken"), (28, "reclaim")] and Z.state_at(len(m) - 1) != "BROKEN"
    assert Z.role_at(len(m) - 1) == (LV.SUP if mirror else LV.RES)
    # the same swing, but price closes back inside the band (bar 26) before it is confirmed ⇒ no reclaim yet: still BROKEN
    m, lv, f = _break_case(True, mirror, tail=[117.0, 115.0, 113.0, 111.0, 117.2, 117.4, 117.3], last=("L", 110.7, 25, 28))
    Z = _zone(lv, f)
    assert [(b, k) for b, k, _ in Z.events if k in ("broken", "reclaim", "flip")] == [(22, "broken")]
    assert Z.state_at(len(m) - 1) == "BROKEN"
    # the break side behaves the same way: a swing beyond confirmed only after price is back inside ⇒ sweep, not broken
    m, lv, f = _break_case(False, mirror, last=("H", 120.5, 20, 23))     # closes inside at 22, the swing above confirms at 23
    Z = _zone(lv, f)
    assert not [k for _, k, _ in Z.events if k == "broken"] and Z.count("sweep", len(m) - 1) >= 1


@pytest.mark.parametrize("mirror", [False, True], ids=["equal-highs", "equal-lows"])
def test_equal_highs_by_comparison_and_every_area_ahead_is_armed(mirror):
    """Abhi's method §3 "equal": a later swing high that reaches the earlier swing's own band and does not go beyond it ⇒ the same area
    reacted twice (liquidity "d"), no σ tolerance. §4 Watch: every valid area ahead in the trend direction is armed, nearest first.
    Mirror: equal lows, support areas armed below price in a rising trend."""
    f, sw = _mirror(mirror)
    closes = list(np.linspace(110, 118, 9)) + list(np.linspace(118, 112, 7))[1:] + list(np.linspace(112, 117.9, 7))[1:] + \
        list(np.linspace(117.9, 111, 6))[1:]
    m = m15_from([f(c) for c in closes], wick=0.3)
    lv = LV.Levels(res_of(m, [P(sw("H"), f(118), 8, 10), P(sw("L"), f(112), 14, 16), P(sw("H"), f(117.9), 20, 22)]))
    Z = _zone(lv, f)
    assert "d" in Z.births or any(x.get("inside") == "d" for x in Z.lineage)   # the second top is inside the first top's band
    assert S3.DEFAULTS["liquidity_rule"] == "equal"
    far = LV.Levels(res_of(m, [P(sw("H"), f(118), 8, 10), P(sw("L"), f(112), 14, 16), P(sw("H"), f(116.5), 20, 22)]))   # not equal
    Zf = _zone(far, f)
    assert "d" not in Zf.births and not any(x.get("inside") == "d" for x in Zf.lineage)
    t = len(m) - 1
    act = lv.active(t, "UP" if mirror else "DOWN")
    assert act and [x["dist"] for x in act] == sorted(x["dist"] for x in act)   # nearest first, no count cap
    side = LV.SUP if mirror else LV.RES
    assert len(act) == len([x for x in lv.snapshot(t) if x["role"] == side and x["below"] == mirror and x.get("state") != "BROKEN"
                            and x.get("trade_location", True)])


def test_at_the_area_is_a_visit_in_progress_never_a_count_of_candles():
    """③ (method §3 Visit / §4): at the area ⇔ a visit is in progress (structure) — not "the last touch within N candles"; bar t never
    gaps or closes through the far side (no breakout entry); price came in from the side away from the trade."""
    rows = [(98.0, 98.6, 97.8, 98.5), (98.5, 100.6, 98.4, 100.4), (100.4, 100.9, 99.6, 99.8), (99.8, 99.9, 98.9, 99.0),
            (99.0, 99.5, 98.8, 99.3), (99.3, 100.2, 98.9, 100.1), (100.1, 100.4, 98.2, 98.4)]        # bar 5 back in, bar 6 from inside
    V, lvl = _visit_v(rows)
    ok, why = V._at_area(6, DOWN, lvl)
    assert ok and "visit in progress since" in why and "touch_window_bars" not in S3.REGISTER["zone_visit_rule"][3]
    assert V._at_area(4, DOWN, lvl) == (False, "price has moved away from the area — no chasing")   # P4: never away from the area
    up = rows[:3] + [(101.0, 103.5, 100.9, 103.2)]                          # closes through the supply's far side ⇒ breakout, no
    V2, _ = _visit_v(up)
    assert V2._at_area(3, DOWN, lvl) == (False, "close through the far side of the area (breakout) ⇒ no")
    V3, _ = _visit_v([(104.0, 104.2, 103.0, 103.1), (101.5, 101.8, 101.0, 101.2)])   # came down INTO a supply from above
    assert V3._at_area(1, DOWN, lvl)[1] == "price came into the area from the trade side (not a pullback)"
    V4, _ = _visit_v([(98.0, 98.6, 97.8, 98.5)])
    assert V4._at_area(0, DOWN, lvl) == (False, "no visit in progress")


def test_absorption_and_the_slow_handover_exclude_each_other():
    """Review probe (supply 100–103): buyers shrink, sellers grow, volume tilts to the sellers ⇒ a slow handover — never absorption on
    the same window (absorption = the trade side NOT growing while small opposite candles keep coming and price stays). Mirror too."""
    oc = [(99.5, 101.0, 900), (101.0, 102.0, 800), (102.0, 101.5, 500), (101.5, 101.8, 300), (101.8, 101.0, 900), (101.0, 101.2, 200),
          (101.2, 99.4, 3000)]
    for mirror in (False, True):
        A = _A([(o, c, v / 1000.0) for o, c, v in oc], mirror)
        d = UP if mirror else DOWN
        t = len(oc) - 1
        z = M.zone_study(A, 0, t - 1, d, S)
        assert z["handover"] is True and z["absorption"] is False
        ho = M.handover_episode(A, 0, t, d, S)
        cf = M.confirm(A, 0, t, d, {"lo": min(2 * MID - 103, 100.0) if mirror else 100.0, "hi": max(2 * MID - 100, 103.0) if mirror else 103.0},
                       {**S, "ltf_choch": False}, handover=ho)
        assert cf["wait"] != M.C_ABSORB


@pytest.mark.parametrize("mirror", [False, True], ids=["supply", "demand"])
def test_no_chase_a_commitment_far_from_the_area_is_not_at_the_area(mirror):
    """Review probe: after a push into a supply (100–102) small red candles drift far below without a swing built away (the visit is
    still open) — a big red candle there is a chase, never "at the area" (P4). Mirror: demand."""
    rows = [(97.0, 97.6, 96.8, 97.5), (97.5, 101.8, 97.4, 100.0), (100.0, 100.5, 99.3, 99.4), (99.4, 99.5, 98.6, 98.7),
            (98.7, 98.8, 97.9, 98.0), (98.0, 98.1, 97.2, 97.3), (97.3, 97.4, 96.5, 96.6), (96.6, 96.7, 95.8, 95.9),
            (95.9, 96.0, 95.1, 95.2), (95.2, 95.3, 92.0, 92.1)]
    if mirror:
        rows = [(202 - o, 202 - lo, 202 - h, 202 - c) for o, h, lo, c in rows]
    d = UP if mirror else DOWN
    V, lvl = _visit_v(rows, d=d)
    t = len(rows) - 1
    assert V.visit(t, lvl, d)["start"] == 1                                 # the visit itself is still open (no swing built away)
    assert V._at_area(t, d, lvl) == (False, "price has moved away from the area — no chasing")


def test_legacy_visit_rule_needs_the_legacy_volume_rule():
    """A legacy visit rule knows no approach leg — paired with the method's volume rule V22 refuses to start (never a half-rule)."""
    with pytest.raises(ValueError, match="approach leg"):
        E3.V22(_abc(), s={"zone_visit_rule": "close_away"})
    E3.V22(_abc(), s={"zone_visit_rule": "close_away", "commit_volume_rule": "opposite"})   # the legacy pair starts


def _abc():
    from tests.test_decision3_method import _abc_m15
    return _abc_m15()


@pytest.mark.parametrize("mirror", [False, True], ids=["supply", "demand"])
def test_commitment_volume_merged_pair_and_missing_volume(mirror):
    """Method §3 Commitment volume: a merged (2-candle) commitment leaves both its candles out of the comparison; compared bars without
    FUT volume are counted (`vol_ref_gaps`), never zero; all compared bars without volume ⇒ NA (the data-problem rule). Mirror too."""
    f = (lambda x: 2 * MID - x) if mirror else (lambda x: float(x))
    rows = [(97.0, 97.6, 96.8, 97.5), (97.5, 98.4, 97.4, 98.3), (98.3, 99.2, 98.2, 99.1),                # approach (0–2)
            (99.0, 101.5, 98.5, 99.2), (99.3, 99.6, 97.0, 97.2)]                                         # push (3), commitment (4)
    rows = [(f(o), max(f(h), f(lo)), min(f(h), f(lo)), f(c)) for o, h, lo, c in rows]
    A = {k: np.array([r[j] for r in rows], float) for j, k in enumerate(("open", "high", "low", "close"))}
    d = UP if mirror else DOWN
    lvl = {"lo": min(f(100.0), f(102.0)), "hi": max(f(100.0), f(102.0))}
    A["volume"] = np.array([300.0, np.nan, 500.0, 2000.0, 900.0])
    ok, _, cm = M.commitment(A, 4, d, lvl, S, win=3, approach=range(0, 3), exclude=[3])
    assert ok and cm["vol_ref_n"] == 2 and cm["vol_ref_gaps"] == 1          # bar 1 has no FUT volume: counted, not averaged as zero
    A["volume"] = np.array([np.nan, np.nan, np.nan, 2000.0, 900.0])
    ok2, _, cm2 = M.commitment(A, 4, d, lvl, S, win=3, approach=range(0, 3), exclude=[3])
    assert cm2["vol_na"] is True and cm2["grade"] == "B"                    # nothing with volume ⇒ NA (V22: data problem, no entry)
    sr = M.sharp_reversal(A, 4, d, lvl["lo"], lvl["hi"], S, a0=3)           # the same pair read as the fast form, mirrored
    assert sr["found"] is True and sr["parts"]["c2_closes_beyond_push_body"] is True


@pytest.mark.parametrize("mirror", [False, True], ids=["demand", "supply"])
def test_merged_commitment_leaves_both_its_candles_out_of_the_volume_comparison(mirror):
    """A merged (2-candle) commitment — here an inside bar broken in the trade direction — is one commitment: its first candle (t − 1)
    is not compared with it, however heavy its volume."""
    f = (lambda x: 2 * MID - x) if mirror else (lambda x: float(x))
    rows = [(104.0, 104.2, 103.0, 103.2), (103.2, 103.4, 102.2, 102.4),                                   # approach down (0–1)
            (102.4, 102.6, 100.2, 100.4), (100.5, 101.6, 100.4, 101.2), (101.2, 102.4, 101.1, 102.3)]   # q (2), inside (3), break (4)
    rows = [(f(o), max(f(h), f(lo)), min(f(h), f(lo)), f(c)) for o, h, lo, c in rows]
    A = {k: np.array([r[j] for r in rows], float) for j, k in enumerate(("open", "high", "low", "close"))}
    A["volume"] = np.array([300.0, 300.0, 400.0, 5000.0, 900.0])            # the inside candle (part of the commitment) is the heaviest
    d = DOWN if mirror else UP
    lvl = {"lo": min(f(100.0), f(101.0)), "hi": max(f(100.0), f(101.0))}
    ok, why, cm = M.commitment(A, 4, d, lvl, {**S, "c0_dominance": False}, win=2, approach=range(0, 2))
    assert cm["merged"] == 2 and ok and cm["vol_ref_n"] == 3, (why, cm)     # bars 0, 1, 2 — the inside candle 3 is not averaged in



def test_failed_commitment_memo_never_mixes_a_tl_area_with_its_parent():
    """Review: a TL confluence area shares its parent's id (`parent_level`) but has its own, narrower band — the failed-commitment read
    depends on the band, so the answer must not depend on which of the two is read first."""
    rows = [(97.0, 97.6, 96.8, 97.5), (97.5, 98.4, 97.4, 98.3), (98.3, 100.4, 98.2, 100.2),
            (100.2, 101.5, 99.0, 99.3), (99.3, 99.6, 97.0, 97.2)]
    tl = {"id": "0+TL", "parent_level": 0, "lo": 101.6, "hi": 101.8}
    fresh = {}
    for key in ("parent", "tl"):
        V, parent = _visit_v(rows)
        fresh[key] = V._failed_commit_outside(4, 2, parent if key == "parent" else tl, DOWN)
    for first in ("parent", "tl"):
        V, parent = _visit_v(rows)
        lv = {"parent": parent, "tl": tl}
        order = [first, "tl" if first == "parent" else "parent"]
        assert {k: V._failed_commit_outside(4, 2, lv[k], DOWN) for k in order} == fresh


def test_the_approach_leg_runs_across_a_gap_and_an_earlier_visit():
    """Abhi (L3-c, P2): the leg that brought price into the area starts at the last swing built away from the area — never at a gap,
    a session change or the end of an earlier visit (a failed commitment). No such swing known ⇒ the approach is unknown (None)."""
    rows = [(97.0, 97.6, 96.8, 97.5), (97.5, 98.6, 97.4, 98.5), (98.5, 100.6, 98.4, 100.4), (100.4, 100.5, 98.0, 98.2),   # 2 visit; 3 red
            (100.6, 101.5, 100.5, 101.2)]                                                                                    # 4: gap back in
    V, lvl = _visit_v(rows, swings=[("L", 96.8, 0, 1)], s=LEGACY_K)        # the commitment end = legacy_k (Abhi 21 Oct)
    V.handover_episode = lambda A, a, t, d, l: {"present": True}            # bar 3 = a failed commitment after a handover ⇒ visit ends
    vi = V.visit(4, lvl, DOWN)
    assert (vi["start"], vi["prev_end"], vi["ended_by"]) == (4, 3, "commitment")
    assert vi["approach_from"] == 1                                         # from the swing low (bar 0) — across the earlier visit and gap
    V2, _ = _visit_v(rows, s=LEGACY_K)
    V2.handover_episode = lambda A, a, t, d, l: {"present": True}
    assert V2.visit(4, lvl, DOWN)["approach_from"] is None                  # no structure swing known ⇒ approach unknown, never invented


def test_legs_arrays_have_no_session_breaks_by_default():
    """Method P2: the G4 approach read sees one continuous chart — only the data's first bar is "first" (no gap removed)."""
    from decision3 import flip as FL
    ts = pd.to_datetime(["2030-01-07 15:00", "2030-01-07 15:15", "2030-01-08 09:15", "2030-01-08 09:30"]).to_numpy()
    A = {k: np.arange(4, dtype=float) for k in ("open", "high", "low", "close")}
    assert list(FL.legs_arrays(A, ts, S)["first"]) == [True, False, False, False]
    assert list(FL.legs_arrays(A, ts, {**S, "session_windows": True})["first"]) == [True, False, True, False]   # legacy what-if



def test_a_swing_on_the_touching_candle_does_not_empty_the_approach_leg():
    """Review: the visit's first candle pokes into the supply and itself becomes a swing low below it — the approach leg still runs from
    the swing BEFORE the visit (never from the touching candle itself, which would leave nothing to compare)."""
    rows = [(97.0, 97.6, 96.8, 97.5), (97.5, 98.6, 97.4, 98.5), (98.5, 100.4, 96.5, 96.9), (96.9, 99.0, 96.8, 98.8)]
    V, lvl = _visit_v(rows, swings=[("L", 96.8, 0, 1), ("L", 96.5, 2, 3)])
    vi = V.visit(3, lvl, DOWN)
    assert vi["start"] == 2 and vi["approach_from"] == 1



def test_a_swing_on_the_first_visit_candle_starts_the_next_leg_after_a_failed_commitment():
    """Review: the visit's first candle is itself a swing built away and the visit ends with a failed commitment — the next visit's
    approach leg starts after that swing, not after the older one."""
    rows = [(97.0, 97.6, 96.8, 97.5), (97.5, 98.6, 97.4, 98.5), (98.5, 100.4, 96.5, 96.9), (96.9, 99.0, 96.8, 98.8),
            (98.8, 99.2, 97.6, 97.8), (97.8, 98.0, 97.0, 97.8), (97.8, 100.5, 97.7, 100.2)]
    V, lvl = _visit_v(rows, swings=[("L", 96.8, 0, 1), ("L", 96.5, 2, 3)], s=LEGACY_K)
    V._failed_commit_outside = lambda i, *a: i == 4                         # the visit (from bar 2) ends at bar 4
    vi = V.visit(6, lvl, DOWN)
    assert (vi["start"], vi["prev_end"], vi["ended_by"], vi["approach_from"]) == (6, 4, "commitment", 3)


def test_a_merged_commitment_keeps_its_first_candle_out_of_the_average_even_when_it_is_opposite_coloured():
    """Review (L3-c average): a two-candle commitment (here a star) is one commitment — its first candle (t − 1), red = the opposite
    side for a demand area, never enters the average, however heavy; without the merge it would (it is an opposite-side candle)."""
    rows = [(104.0, 104.2, 103.0, 103.2), (103.2, 103.4, 102.2, 102.4),                                   # approach down (0–1)
            (102.4, 102.6, 100.2, 100.4), (101.4, 101.6, 100.4, 100.6), (100.8, 102.4, 100.7, 102.3)]   # q (2), red star (3), up (4)
    A = {k: np.array([r[j] for r in rows], float) for j, k in enumerate(("open", "high", "low", "close"))}
    A["volume"] = np.array([300.0, 300.0, 400.0, 5000.0, 900.0])
    ok, why, cm = M.commitment(A, 4, UP, {"lo": 100.0, "hi": 101.0}, {**S, "c0_dominance": False}, win=2, approach=range(0, 2))
    assert cm["merged"] == 2 and ok and cm["vol_ref_n"] == 3 and cm["vol_ref_avg"] == 333.3, (why, cm)
