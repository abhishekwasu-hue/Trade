"""opportunity_engine/diagnostics.py — backtest निकालांचं निदान (फक्त अहवाल; engine चे नियम/parameters बदलत नाही).

🎓 काय मोजतो (सर्व तक्ते IS आणि OOS वेगळे, R = साइज-विना `r`):
  A. Exit breakdown — प्रत्येक setup चं exit प्रकार वितरण (SL / T1→BE / T1→TRAIL / T2 / TIME_STOP / FAILED_BREAKOUT / EOD …) + सरासरी R; wins ची रचना
     (किती wins प्रत्यक्षात "T1 वर अर्धं + BE" आहेत) आणि T2 चं अंतर R मध्ये.
  B. MAE/MFE — प्रत्येक trade चा hold दरम्यान आणि EOD पर्यंत max favourable/adverse excursion (R). BE/TRAIL exit नंतर किंमत मूळ SL आधी T2 ला गेली का.
     Counterfactual (फक्त अहवाल): (१) BE/trail न हलवता (T1 partial तसाच), (२) partial नाही आणि BE नाही (पूर्ण position: SL/T2/EOD).
     त्यासाठी exit-management पुन्हा bar-by-bar चालवतो (`risk.on_bar` तोच); "actual" mode ने मूळ R हुबेहूब परत येतो का ते `resim_match` मध्ये तपासतो.
  C. 1R पेक्षा मोठे losses — प्रत्येकाची यादी कारणासह (slippage वाटा, SL पलीकडे open/gap-through, SL बाजू/अंतर तपासणी).
  D. Funnel — पूर्वअट दिवस → trigger (कधीही) → वेळ-खिडकीत → detector फिल्टर (D2 RR) → raw candidates → gate (कोडनिहाय) → risk → validation → score → selector → घेतलेले.
     वेळ-खिडकीबाहेरचे trigger पाहण्यासाठी "shadow" detection: तेच detectors, फक्त वेळ-खिडकी रुंद आणि D2 RR फिल्टर 0 (हे candidates evaluate होत नाहीत — फक्त मोजणी).
  E. D2 वेगळा अहवाल — gap प्रकार, bias, आणि trigger नंतर किती वेळात SL.
"""
from dataclasses import replace

import numpy as np
import pandas as pd

from .backtest import HTF, IS_END, OOS_START, PERIODS, VARIANTS, _trail_stop, make_detectors, split_is_oos, summarize
from .bias import resolve_bias
from .context import trend_sign
from .detectors.gap import BREAKAWAY, RUNAWAY, classify_gap
from .risk import TradePlan, _close_all, _hhmm, _time_of, on_bar, open_position

GO_TYPES = (BREAKAWAY, RUNAWAY)
STAGE_RANK = {"REJECTED_GATE": 1, "REJECTED_RISK": 2, "REJECTED_VALIDATION": 3, "REJECTED_SCORE": 4, "DROPPED": 5, "TAKEN": 6}
STAGE_TEXT = {"REJECTED_GATE": "Gate reject", "REJECTED_RISK": "Risk reject", "REJECTED_VALIDATION": "Validation reject", "REJECTED_SCORE": "Score < 60 reject",
              "DROPPED": "Selector reject", "TAKEN": "घेतलेले"}
CF_MODES = ("actual", "no_be", "no_partial_no_be")


def _period(dates):
    d = pd.to_datetime(pd.Series(dates))
    return np.where(d <= IS_END, PERIODS[0], np.where(d >= OOS_START, PERIODS[1], ""))


def _by_period(df):
    """[(label, part)] — IS आणि OOS (रिकामे भागही, म्हणजे तक्त्यात 0 दिसतं)."""
    if df is None or len(df) == 0:
        return [(PERIODS[0], df), (PERIODS[1], df)]
    return list(zip(PERIODS, split_is_oos(df)))


def _ecfg(bcfg, variant):
    return replace(bcfg.engine, **VARIANTS[variant])


def _day_map(tl):
    return {pd.Timestamp(d.date): d for d in tl.days}


# ---------------------------------------------------------------------------------------------------------------------
# B. Exit-management पुन्हा चालवणे (actual / counterfactual)
# ---------------------------------------------------------------------------------------------------------------------
def resimulate(tl, day, k, plan, kind, level, ecfg, mode="actual"):
    """entry bar `k` नंतर exit-management bar-by-bar (run_variant सारखंच). mode:
    actual = मूळ नियम (T1 50% + BE, structure trail, HTF WEAK ⇒ BE) · no_be = T1 partial तसाच पण SL मूळ जागीच (BE/trail/WEAK-BE नाही) ·
    no_partial_no_be = T1 ला काहीच बुक नाही, SL मूळ जागीच (पूर्ण position SL/T2/EOD; time stop/failed-breakout तसेच) ·
    plain = T1 + BE, पण trail/WEAK-BE नाही (backtest मधील gate-rejected virtual positions असेच simulate होतात).
    रिटर्न (Position, exit bar index)."""
    cfg = replace(ecfg, t1_book_frac=0.0) if mode == "no_partial_no_be" else ecfg
    pos = open_position(plan, kind, level)
    n = len(day.be)
    direction = plan.direction
    for j in range(k + 1, n):
        t = day.be[j]
        bar = {"open": day.o[j], "high": day.h[j], "low": day.l[j], "close": day.c[j]}
        trail = _trail_stop(day, j, k, direction) if (mode == "actual" and pos.t1_done) else None
        on_bar(pos, bar, cfg, time=t, trail_stop=trail)
        if not pos.closed and mode in ("no_be", "no_partial_no_be") and pos.t1_done:
            pos.sl = plan.sl                                        # BE ला हलवू नका
        if not pos.closed and mode == "actual":
            ps = tl.htf_state(ecfg.primary_htf, t).state
            weak = (ps == "UPTREND_WEAK" and direction == "LONG") or (ps == "DOWNTREND_WEAK" and direction == "SHORT")
            if weak:
                if ecfg.weak_exit == "exit":
                    _close_all(pos, bar["close"], "HTF_WEAK", t)
                elif (pos.sl < plan.entry) if direction == "LONG" else (pos.sl > plan.entry):
                    pos.sl = plan.entry
        if not pos.closed and j == n - 1:
            _close_all(pos, bar["close"], "EOD_DATA", t)
        if pos.closed:
            return pos, j
    return pos, n - 1


def _plan_of(row, ecfg, symbol):
    return TradePlan(direction=row["direction"], entry=float(row["entry"]), sl=float(row["sl"]), t1=float(row["t1"]), t2=float(row["t2"]), risk=float(row["risk"]),
                     slippage=ecfg.slippage_pts.get(symbol, 1.0))


def _eod_index(day, ecfg):
    eod = _hhmm(ecfg.eod_exit)
    for j, t in enumerate(day.be):
        if _time_of(t) >= eod:
            return j
    return len(day.be) - 1


def _excursions(day, a, b, entry, sign, risk):
    """bars a..b (समावेशक) मधला MFE/MAE (R)."""
    if b < a or risk <= 0:
        return 0.0, 0.0
    hi, lo = float(np.max(day.h[a:b + 1])), float(np.min(day.l[a:b + 1]))
    fav = (hi - entry) if sign > 0 else (entry - lo)
    adv = (entry - lo) if sign > 0 else (hi - entry)
    return max(fav, 0.0) / risk, max(adv, 0.0) / risk


def _first_touch(day, a, b, sl, target, sign):
    """bars a..b मध्ये आधी काय: SL (एकाच bar मध्ये दोन्ही ⇒ SL आधी) की target. रिटर्न "SL" | "TARGET" | "NEITHER"."""
    for j in range(a, b + 1):
        hit_sl = day.l[j] <= sl if sign > 0 else day.h[j] >= sl
        if hit_sl:
            return "SL"
        if (day.h[j] >= target) if sign > 0 else (day.l[j] <= target):
            return "TARGET"
    return "NEITHER"


def exit_category(row):
    reason, t1 = row["exit_reason"], bool(row.get("t1_hit"))
    if reason == "SL":
        return "HTF_WEAK→BE" if row.get("exit_at_entry") else "SL"
    if reason == "BE":
        return "T1→BE"
    if reason == "TRAIL_SL":
        return "T1→TRAIL"
    if reason == "T2":
        return "T1→T2"
    if reason in ("EOD", "EOD_DATA"):
        return "T1→EOD" if t1 else "EOD"
    if reason in ("TIME_STOP", "FAILED_BREAKOUT", "HTF_WEAK"):
        return f"T1→{reason}" if t1 else reason
    return str(reason)


def enrich_trades(tl, trades, variant, bcfg):
    """trades DataFrame (run_variant चं) -> निदान columns सह: exit_cat, t2_r, risk_pts, risk_adr, MFE/MAE (hold व EOD पर्यंत), first-touch, BE नंतरचा प्रवास,
    counterfactual R (no_be, no_partial_no_be), resim_match, exit_price, r_no_slip, slip_r, gap_through."""
    if trades is None or len(trades) == 0:
        return pd.DataFrame()
    ecfg = _ecfg(bcfg, variant)
    days = _day_map(tl)
    rows = []
    for _, row in trades.iterrows():
        rec = row.to_dict()
        day = days.get(pd.Timestamp(row["date"]))
        if day is None:
            rows.append(rec)
            continue
        k = day.be.index(row["entry_time"])
        plan = _plan_of(row, ecfg, bcfg.symbol)
        sign, risk = plan.sign, plan.risk
        level = row.get("level")
        level = None if level is None or (isinstance(level, float) and np.isnan(level)) else float(level)
        base_mode = "plain" if bool(row.get("virtual")) else "actual"           # virtual (gate-rejected) positions backtest मध्ये trail/WEAK-BE शिवाय चालतात
        res = {m: resimulate(tl, day, k, plan, row["kind"], level, ecfg, base_mode if m == "actual" else m) for m in CF_MODES}
        pos, xj = res["actual"]
        exit_price = pos.events[-1]["price"] if pos.events else float("nan")
        eod_j = _eod_index(day, ecfg)
        mfe, mae = _excursions(day, k + 1, xj, plan.entry, sign, risk)
        mfe_eod, mae_eod = _excursions(day, k + 1, max(eod_j, xj), plan.entry, sign, risk)
        rec.update({
            "resim_r": round(pos.r_multiple, 6), "resim_match": bool(abs(pos.r_multiple - float(row["r"])) < 1e-6 and pos.exit_reason == row["exit_reason"]),
            "exit_price": exit_price, "exit_at_entry": bool(row["exit_reason"] == "SL" and abs(exit_price - plan.entry) < 1e-9),
            "risk_pts": risk, "risk_adr": risk / day.adr if day.adr and np.isfinite(day.adr) else np.nan,
            "t2_r": abs(plan.t2 - plan.entry) / risk if risk else np.nan,
            "slip_r": -2.0 * plan.slippage / risk if risk else np.nan,
            "r_no_slip": (exit_price - plan.entry) * sign / risk if risk and row["exit_reason"] in ("SL",) else np.nan,
            "gap_through": bool(row["exit_reason"] == "SL" and ((day.o[xj] < pos.sl) if sign > 0 else (day.o[xj] > pos.sl))),
            "mfe_hold_r": mfe, "mae_hold_r": mae, "mfe_eod_r": mfe_eod, "mae_eod_r": mae_eod,
            "bracket_t1": _first_touch(day, k + 1, eod_j, plan.sl, plan.t1, sign), "bracket_t2": _first_touch(day, k + 1, eod_j, plan.sl, plan.t2, sign),
            "minutes_held": (pd.Timestamp(row["exit_time"]) - pd.Timestamp(row["entry_time"])).total_seconds() / 60.0,
            "cf_no_be_r": res["no_be"][0].r_multiple, "cf_no_be_exit": res["no_be"][0].exit_reason,
            "cf_full_r": res["no_partial_no_be"][0].r_multiple, "cf_full_exit": res["no_partial_no_be"][0].exit_reason,
        })
        after = "—"
        if row["exit_reason"] in ("BE", "TRAIL_SL"):
            after = {"SL": "मूळ SL आधी", "TARGET": "T2 गाठलं", "NEITHER": "दोन्ही नाही (EOD)"}[_first_touch(day, xj + 1, eod_j, plan.sl, plan.t2, sign)]
        rec["after_be_exit"] = after
        rows.append(rec)
    out = pd.DataFrame(rows)
    out["exit_cat"] = out.apply(exit_category, axis=1)
    return out


# ---------------------------------------------------------------------------------------------------------------------
# A/B/C/E तक्ते
# ---------------------------------------------------------------------------------------------------------------------
def exit_breakdown(x):
    """period × setup × exit_cat: trades, वाटा %, सरासरी R, एकूण R."""
    rows = []
    for label, part in _by_period(x):
        if part is None or len(part) == 0:
            continue
        for setup, g in part.groupby("setup"):
            for cat, h in g.groupby("exit_cat"):
                rows.append({"period": label, "setup": setup, "exit": cat, "trades": len(h), "वाटा_%": round(100.0 * len(h) / len(g), 1),
                             "avg_r": round(float(h["r"].mean()), 3), "total_r": round(float(h["r"].sum()), 2)})
    return pd.DataFrame(rows)


def win_composition(x):
    """period × setup: wins किती, त्यातले T1→BE किती, सरासरी win, T2 चं median अंतर (R), T1 गाठलेले %, T2 गाठलेले %."""
    rows = []
    for label, part in _by_period(x):
        if part is None or len(part) == 0:
            continue
        for setup, g in part.groupby("setup"):
            w = g[g["r"] > 0]
            rows.append({"period": label, "setup": setup, "trades": len(g), "wins": len(w), "avg_win_r": None if w.empty else round(float(w["r"].mean()), 3),
                         "wins_T1→BE": int((w["exit_cat"] == "T1→BE").sum()), "wins_T1→TRAIL": int((w["exit_cat"] == "T1→TRAIL").sum()),
                         "wins_T1→T2": int((w["exit_cat"] == "T1→T2").sum()), "wins_इतर": int((~w["exit_cat"].isin(["T1→BE", "T1→TRAIL", "T1→T2"])).sum()),
                         "T1_गाठलं_%": round(100.0 * g["t1_hit"].astype(bool).mean(), 1), "T2_गाठलं_%": round(100.0 * (g["exit_cat"] == "T1→T2").mean(), 1),
                         "T2_अंतर_median_R": round(float(g["t2_r"].median()), 2), "T2_अंतर_<1.5R_%": round(100.0 * (g["t2_r"] < 1.5).mean(), 1)})
    return pd.DataFrame(rows)


def mae_mfe_table(x):
    rows = []
    for label, part in _by_period(x):
        if part is None or len(part) == 0:
            continue
        for setup, g in part.groupby("setup"):
            rows.append({"period": label, "setup": setup, "trades": len(g),
                         "MFE_hold_median_R": round(float(g["mfe_hold_r"].median()), 2), "MAE_hold_median_R": round(float(g["mae_hold_r"].median()), 2),
                         "MFE_EOD_median_R": round(float(g["mfe_eod_r"].median()), 2), "MAE_EOD_median_R": round(float(g["mae_eod_r"].median()), 2),
                         "MFE_EOD≥1R_%": round(100.0 * (g["mfe_eod_r"] >= 1.0).mean(), 1), "MFE_EOD≥2R_%": round(100.0 * (g["mfe_eod_r"] >= 2.0).mean(), 1),
                         "bracket: T1 आधी (SL पेक्षा)": int((g["bracket_t1"] == "TARGET").sum()), "bracket: T2 आधी (SL पेक्षा)": int((g["bracket_t2"] == "TARGET").sum()),
                         "bracket: SL आधी": int((g["bracket_t2"] == "SL").sum()), "bracket: दोन्ही नाही": int((g["bracket_t2"] == "NEITHER").sum())})
    return pd.DataFrame(rows)


def counterfactual_table(x):
    """actual vs (BE न हलवता) vs (partial + BE दोन्ही नाही) — expectancy, win %, avg win/loss. फक्त अहवाल."""
    rows = []
    for label, part in _by_period(x):
        if part is None or len(part) == 0:
            continue
        for setup, g in list(part.groupby("setup")) + [("सर्व", part)]:
            for name, col in (("actual (सध्याचे नियम)", "r"), ("BE/trail न हलवता (T1 partial तसाच)", "cf_no_be_r"), ("partial नाही + BE नाही (SL/T2/EOD)", "cf_full_r")):
                rows.append({"period": label, "setup": setup, "नियम": name, **summarize(g.assign(_r=g[col].astype(float), exit_time=g["exit_time"]), "_r")})
    return pd.DataFrame(rows)


def be_followup(x):
    """BE/TRAIL exit नंतर किंमत मूळ SL आधी T2 ला गेली का (EOD पर्यंत)."""
    rows = []
    for label, part in _by_period(x):
        if part is None or len(part) == 0:
            continue
        sub = part[part["exit_reason"].isin(["BE", "TRAIL_SL"])]
        for (setup, reason), g in sub.groupby(["setup", "exit_reason"]):
            vc = g["after_be_exit"].value_counts()
            rows.append({"period": label, "setup": setup, "exit": reason, "trades": len(g), "नंतर T2 गाठलं": int(vc.get("T2 गाठलं", 0)),
                         "नंतर मूळ SL आधी": int(vc.get("मूळ SL आधी", 0)), "दोन्ही नाही (EOD)": int(vc.get("दोन्ही नाही (EOD)", 0))})
    return pd.DataFrame(rows)


def big_losses(x, thresh=-1.0):
    """r < thresh असलेले trades — कारणासह."""
    if x is None or len(x) == 0:
        return pd.DataFrame()
    b = x[x["r"] < thresh].copy()
    if b.empty:
        return pd.DataFrame()

    def cause(r):
        if r["exit_reason"] != "SL":
            return f"exit {r['exit_reason']} (SL नाही) — तपासा"
        if r["gap_through"]:
            return "bar SL पलीकडे उघडला (प्रत्यक्षात fill आणखी वाईट; sim मध्ये SL वरच fill)"
        if abs(r["r_no_slip"] + 1.0) < 1e-6 and abs((r["r"] - r["slip_r"]) + 1.0) < 1e-6:
            return f"फक्त slippage: 2×{abs(r['slip_r']) * r['risk_pts'] / 2:.0f} pt / risk {r['risk_pts']:.1f} pt = {r['slip_r']:+.2f}R"
        return "SL fill/गणना अपेक्षेपेक्षा वेगळी — तपासा"

    sl_ok = np.where(b["direction"] == "LONG", b["sl"] < b["entry"], b["sl"] > b["entry"])
    b["sl_बाजू_बरोबर"] = sl_ok
    b["risk_जुळतो"] = (b["risk"] - (b["entry"] - b["sl"]).abs()).abs() < 1e-6
    b["कारण"] = b.apply(cause, axis=1)
    b["period"] = _period(b["date"])
    cols = ["period", "date", "entry_time", "exit_time", "setup", "direction", "gap_type", "bias", "entry", "sl", "exit_price", "risk_pts", "risk_adr", "r", "r_no_slip", "slip_r",
            "gap_through", "sl_बाजू_बरोबर", "risk_जुळतो", "कारण"]
    return b[[c for c in cols if c in b.columns]].sort_values(["period", "setup", "date"]).reset_index(drop=True)


def loss_size_summary(x):
    """period × setup: SL trades, avg loss, median risk pts, median slip_r, risk < 20 pt चा वाटा."""
    rows = []
    for label, part in _by_period(x):
        if part is None or len(part) == 0:
            continue
        for setup, g in part.groupby("setup"):
            s = g[g["exit_reason"] == "SL"]
            losses = g[g["r"] < 0]
            rows.append({"period": label, "setup": setup, "losses": len(losses), "avg_loss_r": None if losses.empty else round(float(losses["r"].mean()), 3),
                         "SL_exits": len(s), "SL_avg_r": None if s.empty else round(float(s["r"].mean()), 3),
                         "SL_risk_median_pts": None if s.empty else round(float(s["risk_pts"].median()), 1), "SL_slip_median_R": None if s.empty else round(float(s["slip_r"].median()), 3),
                         "SL_risk_adr_median": None if s.empty else round(float(s["risk_adr"].median()), 3), "<-1R_losses": int((g["r"] < -1.0).sum()),
                         "gap_through": int(s["gap_through"].sum()) if len(s) else 0})
    return pd.DataFrame(rows)


def _ttsl_bucket(m):
    for lim, lab in ((5, "≤5 मि"), (15, "6–15 मि"), (30, "16–30 मि"), (60, "31–60 मि"), (120, "61–120 मि")):
        if m <= lim:
            return lab
    return ">120 मि"


def d2_report(x, setup="D2"):
    """D2: gap प्रकार, bias, trigger नंतर SL किती वेळात. रिटर्न dict of DataFrames."""
    out = {}
    if x is None or len(x) == 0 or (x["setup"] == setup).sum() == 0:
        return {"by_gap_type": pd.DataFrame(), "by_bias": pd.DataFrame(), "time_to_sl": pd.DataFrame()}
    d = x[x["setup"] == setup].copy()
    for by in ("gap_type", "bias"):
        rows = []
        for label, part in _by_period(d):
            if part is None or len(part) == 0:
                continue
            for key, g in part.groupby(by):
                rows.append({"period": label, by: key, **summarize(g, "r"), "SL_exits": int((g["exit_reason"] == "SL").sum())})
        out[f"by_{by}"] = pd.DataFrame(rows)
    sl = d[d["exit_reason"] == "SL"].copy()
    rows = []
    order = ["≤5 मि", "6–15 मि", "16–30 मि", "31–60 मि", "61–120 मि", ">120 मि"]
    for label, part in _by_period(sl):
        if part is None or len(part) == 0:
            continue
        b = part["minutes_held"].map(_ttsl_bucket)
        vc = b.value_counts()
        rows.append({"period": label, "SL_trades": len(part), "median_मि": round(float(part["minutes_held"].median()), 1),
                     "median_bars": round(float(part["bars"].median()), 1), **{lab: int(vc.get(lab, 0)) for lab in order}})
    out["time_to_sl"] = pd.DataFrame(rows)
    return out


# ---------------------------------------------------------------------------------------------------------------------
# D. Funnel
# ---------------------------------------------------------------------------------------------------------------------
def _minutes(ts):
    t = pd.Timestamp(ts)
    return t.hour * 60 + t.minute


def _in_window(setup, t, ecfg):
    m = _minutes(t)
    hm = lambda s: int(s[:2]) * 60 + int(s[3:])                  # noqa: E731
    if setup == "D1":
        return m <= hm(ecfg.d1_window_end)
    if setup == "D2":
        return m <= hm(ecfg.d2_window_end)
    if setup == "D3":
        return hm(ecfg.d3_window_start) <= m <= hm(ecfg.d3_window_end)
    if setup == "D6":
        return hm(ecfg.d6_window_start) <= m <= hm(ecfg.d6_window_end)
    if setup == "D10":
        return hm(ecfg.d10_window_start) <= m <= hm(ecfg.d10_window_end)
    return True


def shadow_detect(tl, variant, bcfg, progress=None):
    """तेच detectors दोन स्वतंत्र प्रतींमध्ये (वेगवेगळी detector memory) — फक्त *काय trigger झालं* ते मोजण्यासाठी (evaluate नाही, trade नाही):
    `orig` = मूळ वेळ-खिडकी, फक्त D2 RR फिल्टर 0 (⇒ RR मुळे वगळलेले दिसतात) · `wide` = वेळ-खिडकी 09:15–15:30 (⇒ खिडकीबाहेरचे trigger दिसतात).
    दोन प्रती वेगळ्या कारण D3 एकदा signal दिल्यावर zone "used" करतो — खिडकीबाहेरच्या signal ने खिडकीतला signal लपू नये.
    रिटर्न (days DataFrame, shadow candidates DataFrame; column `source` = orig/wide)."""
    ecfg = _ecfg(bcfg, variant)
    wide = replace(ecfg, d1_window_end="15:30", d2_window_end="15:30", d3_window_start="09:15", d3_window_end="15:30", d2_min_rr=0.0,
                   d6_window_start="09:15", d6_window_end="15:30", d10_window_start="09:15", d10_window_end="15:30")
    orig = replace(ecfg, d2_min_rr=0.0)
    sets = {"orig": make_detectors(bcfg.detectors, orig), "wide": make_detectors(bcfg.detectors, wide)}
    day_rows, cand_rows = [], []
    for di, day in enumerate(tl.days):
        info = replace(day.info)
        ctx0 = tl.context(day.open_t, day, info.open)
        classify_gap(info, ctx0, resolve_bias(ctx0, ecfg), ecfg)
        has_gap_zone = any(lv.get("kind") == "GAP" and lv.get("gap_status") in ("UNFILLED", "PARTIAL") for lv in day.levels)
        fill_time = None
        if info.gap_dir != 0:
            hit = np.nonzero(day.l <= info.pdc)[0] if info.gap_dir > 0 else np.nonzero(day.h >= info.pdc)[0]
            fill_time = day.be[int(hit[0])] if len(hit) else None
        day_rows.append({"date": day.date, "gap_type": info.gap_type, "gap_dir": info.gap_dir, "gap_pct": info.gap_pct, "has_gap_zone": has_gap_zone, "gap_fill_time": fill_time,
                         "primary_state": ctx0.state_name(ecfg.primary_htf)})
        mems = {"orig": {}, "wide": {}}
        for k in range(ecfg.or_bars, len(day.be)):
            t = day.be[k]
            ctx = tl.context(t, day, day.c[k])
            df15 = day.df15[day.df15["bar_end"] <= t]
            vol, vol_med = tl.volume(day.g5 + k)
            base = {"5m": day.df5.iloc[:k + 1], "15m": df15, "info": info, "rr5": tl.rr(5, day.g5 + k), "rr15": None,
                    "ev15": [e for e in day.ev15 if e["time"] <= t], "vol5": vol, "vol_med5": vol_med}             # run_variant सारखाच इनपुट
            if len(df15):
                base["rr15"] = tl.rr(15, day.g15 + len(df15) - 1)
            bias_now = resolve_bias(ctx, ecfg)
            for src, dets in sets.items():
                bars = {**base, "state": mems[src]}
                for det in dets:
                    for c in det.detect(ctx, bars, bias_now, t):
                        risk = abs(c.entry - c.sl_ref)
                        rr_pdc = abs(c.entry - info.pdc) / risk if (c.setup_id == "D2" and risk > 0) else np.nan
                        cand_rows.append({"source": src, "date": day.date, "time": t, "setup": c.setup_id, "direction": c.direction, "entry": c.entry, "sl_ref": c.sl_ref,
                                          "in_window": _in_window(c.setup_id, t, ecfg), "rr_pdc": rr_pdc,
                                          "passes_filter": bool(c.setup_id != "D2" or rr_pdc >= ecfg.d2_min_rr)})
        if progress and di % 100 == 0:
            progress(di, len(tl.days), day.date)
    return pd.DataFrame(day_rows), pd.DataFrame(cand_rows)


def _precondition(setup, days):
    if setup == "D1":
        return days["gap_type"].isin(GO_TYPES)
    if setup == "D2":
        return ~days["gap_type"].isin(GO_TYPES) & (days["gap_dir"] != 0)
    if setup == "D3":
        return days["has_gap_zone"].astype(bool)
    if setup == "D6" and "primary_state" in days.columns:
        return days["primary_state"].map(trend_sign).fillna(0) != 0
    if setup == "D10" and "primary_state" in days.columns:
        return (days["primary_state"].map(trend_sign).fillna(0) != 0) | (days["primary_state"] == "RANGE")
    return pd.Series(True, index=days.index)


PRECOND_TEXT = {"D1": "gap BREAKAWAY/RUNAWAY (bias-दिशेचा)", "D2": "gap SMALL/EXHAUSTION/COMMON (gap ≠ 0)", "D3": "UNFILLED/PARTIAL gap zone उपलब्ध",
                "D6": "09:15 ला primary HTF trend (UP/DOWN)", "D10": "09:15 ला primary HTF trend किंवा RANGE"}


def _primary_reason(row):
    st = row["status"]
    if st == "REJECTED_GATE":
        return (row.get("gate_codes") or "").split(",")[0] or "?"
    if st in ("REJECTED_RISK", "DROPPED"):
        return str(row.get("reasons") or "").split(" | ")[0].replace("Risk: ", "").replace("Selector: ", "")
    return ""


def funnel(decisions, days, shadow, bcfg, variant):
    """period × setup funnel (दिवस आणि candidates). प्रत्येक (दिवस, setup) साठी त्या दिवशीचा सर्वात पुढचा टप्पा गणला जातो."""
    ecfg = _ecfg(bcfg, variant)
    dec = decisions.copy() if decisions is not None and len(decisions) else pd.DataFrame(columns=["date", "setup", "status", "gate_codes", "reasons", "time"])
    dec["rank"] = dec["status"].map(STAGE_RANK).fillna(0)
    dec["primary"] = dec.apply(_primary_reason, axis=1) if len(dec) else []
    rows = []
    days = days.copy()
    days["period"] = _period(days["date"])
    sh = shadow.copy() if shadow is not None and len(shadow) else pd.DataFrame(columns=["source", "date", "time", "setup", "in_window", "passes_filter"])
    sh["period"] = _period(sh["date"]) if len(sh) else []
    dec["period"] = _period(dec["date"]) if len(dec) else []
    for label in PERIODS:
        dd = days[days["period"] == label]
        n_years = max(len(dd) / 248.0, 1e-9)
        for setup in bcfg.detectors:
            def add(stage, n_days, n_cands=None, note=""):
                rows.append({"period": label, "setup": setup, "टप्पा": stage, "दिवस": int(n_days), "दिवस/वर्ष": round(n_days / n_years, 1),
                             "candidates": None if n_cands is None else int(n_cands), "टीप": note})
            pre = dd[_precondition(setup, dd)]
            pre_dates = set(pre["date"])
            s_all = sh[(sh["period"] == label) & (sh["setup"] == setup)]
            s = s_all[s_all["source"] == "wide"]                       # कधीही (रुंद खिडकी)
            s_orig = s_all[s_all["source"] == "orig"]                  # मूळ खिडकी (RR फिल्टर 0)
            d_ = dec[(dec["period"] == label) & (dec["setup"] == setup)]
            add("1. ट्रेडिंग दिवस", len(dd))
            add("2. पूर्वअट", len(pre), note=PRECOND_TEXT.get(setup, ""))
            if setup == "D2":
                fill_before = 0
                first_trig = s.groupby("date")["time"].min().to_dict() if len(s) else {}
                end_m = _minutes(pd.Timestamp("2000-01-01 " + ecfg.d2_window_end))
                for date, ft in zip(pre["date"], pre["gap_fill_time"]):
                    first = first_trig.get(date)
                    if ft is not None and not pd.isna(ft) and _minutes(ft) <= end_m and (first is None or pd.Timestamp(ft) < pd.Timestamp(first)):
                        fill_before += 1
                add("2a. (D2) trigger आधीच gap भरला ⇒ रद्द", fill_before, note=f"{ecfg.d2_window_end} पूर्वी PDC गाठलं, त्याआधी trigger नाही")
            in_w = s_orig[s_orig["in_window"].astype(bool)]
            trig_days = (set(s["date"]) | set(in_w["date"])) & pre_dates
            add("3. trigger (कधीही, shadow)", len(trig_days), len(s), note="वेळ-खिडकी रुंद करून मोजलं")
            add("4. trigger वेळ-खिडकीत", len(set(in_w["date"])), len(in_w), note="बाहेरच: " + str(len(trig_days - set(in_w["date"]))) + " दिवस")
            if setup == "D2":
                f = in_w[in_w["passes_filter"].astype(bool)]
                add("4a. (D2) RR ≥ 1.5 (PDC पर्यंत)", len(set(f["date"])), len(f))
            raw_days = set(d_["date"])
            shadow_ok = set(in_w[in_w["passes_filter"].astype(bool)]["date"])
            add("5. raw candidates (evaluate ला गेलेले)", len(raw_days), len(d_),
                note=f"shadow शी तफावत: {len(raw_days ^ shadow_ok)} दिवस (0 अपेक्षित)")
            if len(d_):
                best = d_.sort_values("rank").groupby("date").tail(1)
            else:
                best = d_
            for st in ("REJECTED_GATE", "REJECTED_RISK", "REJECTED_VALIDATION", "REJECTED_SCORE", "DROPPED", "TAKEN"):
                b = best[best["status"] == st]
                c = d_[d_["status"] == st]
                add(f"6. शेवटचा टप्पा: {STAGE_TEXT[st]}", len(b), len(c))
                if st in ("REJECTED_GATE", "REJECTED_RISK", "DROPPED") and len(b):
                    for reason, g in b.groupby("primary"):
                        add(f"   └ {reason}", len(g), int((c["primary"] == reason).sum()))
    return pd.DataFrame(rows)


def gate_code_counts(decisions):
    """gate ने नाकारलेल्या candidates मधील *सर्व* कोड (एका candidate ला अनेक कोड असू शकतात) — period × setup × code."""
    if decisions is None or len(decisions) == 0:
        return pd.DataFrame()
    g = decisions[decisions["status"] == "REJECTED_GATE"].copy()
    if g.empty:
        return pd.DataFrame()
    g["period"] = _period(g["date"])
    g["code"] = g["gate_codes"].fillna("").str.split(",")
    g = g.explode("code")
    out = g.groupby(["period", "setup", "code"]).agg(candidates=("code", "size"), दिवस=("date", "nunique")).reset_index()
    return out[out["period"] != ""].sort_values(["period", "setup", "candidates"], ascending=[True, True, False]).reset_index(drop=True)


def funnel_by_year(decisions, days, trades, bcfg):
    """setup × वर्ष: पूर्वअट दिवस, raw-candidate दिवस, घेतलेले trades."""
    rows = []
    days = days.copy()
    days["year"] = pd.to_datetime(days["date"]).dt.year
    dec = decisions if decisions is not None and len(decisions) else pd.DataFrame(columns=["date", "setup"])
    tr = trades if trades is not None and len(trades) else pd.DataFrame(columns=["date", "setup"])
    for setup in bcfg.detectors:
        for y, dd in days.groupby("year"):
            pre = int(_precondition(setup, dd).sum())
            dy = dec[(dec["setup"] == setup) & (pd.to_datetime(dec["date"]).dt.year == y)] if len(dec) else dec
            ty = tr[(tr["setup"] == setup) & (pd.to_datetime(tr["date"]).dt.year == y)] if len(tr) else tr
            rows.append({"setup": setup, "वर्ष": int(y), "period": PERIODS[0] if y <= IS_END.year else PERIODS[1], "ट्रेडिंग दिवस": len(dd), "पूर्वअट दिवस": pre,
                         "raw-candidate दिवस": int(dy["date"].nunique()) if len(dy) else 0, "घेतलेले trades": len(ty)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------------------------------------
# सर्व एकत्र
# ---------------------------------------------------------------------------------------------------------------------
def run_diagnostics(tl, result, variant, bcfg, progress=None):
    """result = run_variant चा dict. रिटर्न {नाव: DataFrame}."""
    x = enrich_trades(tl, result["trades"], variant, bcfg)
    days, shadow = shadow_detect(tl, variant, bcfg, progress)
    d2 = d2_report(x)
    vx = enrich_trades(tl, result["virtual"], variant, bcfg) if result.get("virtual") is not None and len(result["virtual"]) else pd.DataFrame()
    d2v = d2_report(vx)
    out = {
        "A_exit_breakdown": exit_breakdown(x) if len(x) else pd.DataFrame(),
        "A_win_composition": win_composition(x) if len(x) else pd.DataFrame(),
        "B_mae_mfe": mae_mfe_table(x) if len(x) else pd.DataFrame(),
        "B_counterfactual": counterfactual_table(x) if len(x) else pd.DataFrame(),
        "B_be_followup": be_followup(x) if len(x) else pd.DataFrame(),
        "C_loss_size": loss_size_summary(x) if len(x) else pd.DataFrame(),
        "C_big_losses": big_losses(x),
        "D_funnel": funnel(result["decisions"], days, shadow, bcfg, variant),
        "D_gate_codes": gate_code_counts(result["decisions"]),
        "D_by_year": funnel_by_year(result["decisions"], days, result["trades"], bcfg),
        "E_d2_by_gap_type": d2["by_gap_type"], "E_d2_by_bias": d2["by_bias"], "E_d2_time_to_sl": d2["time_to_sl"],
        "E_d2_virtual_by_gap_type": d2v["by_gap_type"], "E_d2_virtual_by_bias": d2v["by_bias"],
        "trades_enriched": x, "shadow_days": days, "shadow_candidates": shadow,
    }
    if len(x) and "resim_match" in x.columns:
        out["check_resim"] = pd.DataFrame([{"trades": len(x), "resim जुळले": int(x["resim_match"].sum()), "न जुळलेले": int((~x["resim_match"].astype(bool)).sum())}])
    return out


__all__ = ["run_diagnostics", "enrich_trades", "resimulate", "shadow_detect", "funnel", "exit_breakdown", "win_composition", "mae_mfe_table", "counterfactual_table",
           "be_followup", "big_losses", "loss_size_summary", "d2_report", "gate_code_counts", "funnel_by_year", "HTF"]
