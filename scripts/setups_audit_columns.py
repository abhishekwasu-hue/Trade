"""scripts/setups_audit_columns.py — diagnostic audit columns (a)–(f) for V22 setups (Abhi: TRADE_SESSION_DECISIONS_SENSEX_SETUPS_CD14
§2 a–f; report docs/reports/setups_prA_v1_audit.md). **Diagnostic only**: it reads one finished V22 run (pickle) and recomputes
evidence with the existing decision3 functions; it never changes an engine decision. The fixes live on other branches.

Columns (each uses only bars <= the setup bar; no outcome, no P&L):
  (a) nearest opposite area between entry and target on 15M / 1H / Daily, and R:R against it. Opposite = (bull put) unbroken swing
      highs above the entry — 15M fractal N = 3 in the last 5 sessions, 1H fractal N = 2 in the last 20 sessions, Daily N = 2 in the
      last 126 sessions — plus broken Daily swing lows (closed below since) that are still above the close = flipped supply.
      "Unbroken" = no close beyond it since it formed. Bear call = mirror. R:R = (area − entry) / (entry − SL).
  (b) arrival: "breakout→retest" if a 15M close on the far side of the area happened after the K impulse origin (the impulse that
      opened K was the break of the area itself), else "pullback"; plus K bars that touched the area, the penetration depth (K extreme
      into the band, 1 = far edge) and "edge touch only" (<= 2 candles touched and the K extreme stayed in the near half — Abhi's
      "2-candle touch of the edge"). FAIL = edge touch only, or a breakout→retest whose break bar is inside the current pullback
      window (break at / after the K impulse end ⇒ immediate retest, no impulse away first), or a far-side close never reclaimed.
  (c) crossings: 15M closes switching side of the area band in the 5 days before the setup (closes inside the band ignored) —
      `sr_levels_v3.count_crossings` rule; chop setting (`chop_max_crossings` = 6) ⇒ grade C if more.
  (d) Daily reading, cap, conviction, and whether the protected origin was still PROVISIONAL (engine `prov` stack: a correction
      completion / new leg not yet confirmed by "continuation confirm"; traced from the Daily `why` events) — provisional ⇒ max B.
  (e) a2 `method.zone_study` (arrival → setup bar) handover / absorption, c0 `method.commitment(win=arrival)` body dominance; volume
      = NIFTY futures volume — none exists for 2015–2024 intraday (trade-data futures 5m starts 2026-09) ⇒ NA.
  (f) 5M structure at the setup bar: CHoCH by close (bull: a 5M close above the last 5M swing high before the pullback low; N = 2)
      or "still against".

  python3 scripts/setups_audit_columns.py <rows.pkl> <nifty 1m parquet> [out.json]
"""
import json
import os
import pickle
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from decision3 import method as M        # noqa: E402
from decision3 import settings as S3     # noqa: E402

CHOP_MAX = 6                              # sr_levels_v3.SRConfig.chop_max_crossings (existing setting)
CHOP_DAYS = 5.0                           # sr_levels_v3.SRConfig.chop_lookback_days


def fractal(H, L, n, upto):
    """confirmed (i + n <= upto) fractal pivots: [(kind, price, i)]."""
    out = []
    for i in range(n, upto - n + 1):
        if H[i] > H[i - n:i].max() and H[i] >= H[i + 1:i + n + 1].max():
            out.append(("H", float(H[i]), i))
        if L[i] < L[i - n:i].min() and L[i] <= L[i + 1:i + n + 1].min():
            out.append(("L", float(L[i]), i))
    return out


def opp_areas(df, upto, n, first, d):
    """unbroken opposite swings (bull: highs) + (Daily only, via flip=True caller) — returns [(price, label)]."""
    H, L, C = (df[k].to_numpy(float) for k in ("high", "low", "close"))
    out = []
    for kind, px, i in fractal(H, L, n, upto):
        if i < first:
            continue
        want = "H" if d > 0 else "L"
        if kind != want:
            continue
        after = C[i + 1:upto + 1]
        if len(after) and ((after > px).any() if d > 0 else (after < px).any()):
            continue                                                       # closed beyond ⇒ not an area any more
        out.append((px, i))
    return out


def flipped_daily(df, upto, first, d):
    """Daily swing lows (bull; highs for bear) broken by a close since and still beyond the last close ⇒ flipped supply / demand."""
    H, L, C = (df[k].to_numpy(float) for k in ("high", "low", "close"))
    out = []
    for kind, px, i in fractal(H, L, 2, upto):
        if i < first or kind != ("L" if d > 0 else "H"):
            continue
        after = C[i + 1:upto + 1]
        broken = len(after) and ((after < px).any() if d > 0 else (after > px).any())
        if broken and ((C[upto] < px) if d > 0 else (C[upto] > px)):
            out.append((px, i))
    return out


def col_a(r, m15, t, daily, h1):
    d = 1 if r["trade_side"] == ["bull_put"] else -1
    rk = r["risk"] or {}
    e, sl, tg = rk.get("entry"), rk.get("sl"), rk.get("target")
    if e is None or tg is None:
        return {"note": "no risk"}
    day = pd.Timestamp(r["ts"]).normalize()
    cands = []
    # 15M: last 5 sessions
    ts = pd.to_datetime(m15["timestamp"])
    sess = ts.dt.normalize()
    days = sorted(pd.unique(sess[:t + 1]))
    f15 = int((sess >= (days[-5] if len(days) >= 5 else days[0])).to_numpy().argmax())
    for px, i in opp_areas(m15, t, 3, f15, d):
        cands.append((px, f"15M swing {'high' if d > 0 else 'low'} {px:,.0f} ({ts[i]:%d-%b %H:%M})"))
    # 1H: bars complete before the setup bar's end
    hb = h1[h1["bar_end"] <= pd.Timestamp(r["bar_end"])].reset_index(drop=True)
    if len(hb) > 10:
        hs = pd.to_datetime(hb["timestamp"]).dt.normalize()
        hd = sorted(pd.unique(hs))
        fh = int((hs >= (hd[-20] if len(hd) >= 20 else hd[0])).to_numpy().argmax())
        for px, i in opp_areas(hb, len(hb) - 1, 2, fh, d):
            cands.append((px, f"1H swing {'high' if d > 0 else 'low'} {px:,.0f} ({hb['timestamp'].iloc[i]:%d-%b %H:%M})"))
    # Daily: sessions before the setup day
    db = daily[pd.to_datetime(daily["timestamp"]).dt.normalize() < day].reset_index(drop=True)
    fd = max(0, len(db) - 126)
    for px, i in opp_areas(db, len(db) - 1, 2, fd, d):
        cands.append((px, f"Daily swing {'high' if d > 0 else 'low'} {px:,.0f} ({db['timestamp'].iloc[i]:%d-%b-%y})"))
    for px, i in flipped_daily(db, len(db) - 1, fd, d):
        cands.append((px, f"Daily broken {'low ⇒ supply' if d > 0 else 'high ⇒ demand'} {px:,.0f} ({db['timestamp'].iloc[i]:%d-%b-%y})"))
    between = [(px, lab) for px, lab in cands if (e < px < tg) if d > 0] if d > 0 else [(px, lab) for px, lab in cands if tg < px < e]
    if not between:
        return {"area": None, "rr_area": rk.get("rr"), "verdict": "pass"}
    px, lab = min(between, key=lambda x: abs(x[0] - e))
    rr = round(abs(px - e) / abs(e - sl), 2) if sl is not None and e != sl else None
    return {"area": lab, "area_px": round(px, 2), "rr_area": rr, "rr_engine": rk.get("rr"),
            "verdict": "FAIL (R:R < 3 against it)" if rr is not None and rr < 3 else "pass"}


def col_b(r, A, t):
    d = 1 if r["trade_side"] == ["bull_put"] else -1
    lv, k = r["level"], r["K"] or {}
    C, H, L = A["close"], A["high"], A["low"]
    o = k.get("origin_bar")
    if o is None:
        return {"arrival": "NA"}
    far = [i for i in range(int(o), t) if ((C[i] < lv["lo"]) if d > 0 else (C[i] > lv["hi"]))]
    k0 = k.get("k_open_bar") or t
    touch = [i for i in range(int(k0), t + 1) if ((L[i] <= lv["hi"]) if d > 0 else (H[i] >= lv["lo"]))]
    ext = k.get("k_ext")
    width = max(lv["hi"] - lv["lo"], 1e-9)
    pen = ((lv["hi"] - ext) if d > 0 else (ext - lv["lo"])) / width if ext is not None else None
    edge = len(touch) <= 2 and (pen is None or pen < 0.5)                  # Abhi: "a 2-candle touch of the edge", not INTO the area
    out = {"touch_bars": len(touch), "penetration": None if pen is None else round(pen, 2), "edge_touch_only": bool(edge)}
    if far:
        brk = next((i for i in range(far[-1] + 1, t + 1) if ((C[i] > lv["hi"]) if d > 0 else (C[i] < lv["lo"]))), None)
        i_end = k.get("i_end_bar")
        immediate = brk is not None and i_end is not None and brk >= int(i_end)   # break inside the current pullback window ⇒ no
        bad = brk is None or immediate or edge                             # impulse away from the area between break and retest
        return {"arrival": "breakout→retest" if brk is not None else "far side, no reclaim", "break_bar": brk,
                "bars_since_break": None if brk is None else t - brk, "immediate_retest": bool(immediate), **out,
                "verdict": "FAIL" if bad else "pass"}
    return {"arrival": "pullback", **out, "verdict": "FAIL" if edge else "pass"}


def col_c(r, m15, t):
    lv = r["level"]
    ts = pd.to_datetime(m15["timestamp"])
    since = ts[t] - pd.Timedelta(days=CHOP_DAYS)
    C = m15["close"].to_numpy(float)
    last, n = 0, 0
    for i in range(int((ts > since).to_numpy().argmax()), t):
        side = 1 if C[i] > lv["hi"] else (-1 if C[i] < lv["lo"] else 0)
        if side and last and side != last:
            n += 1
        if side:
            last = side
    return {"crossings_5d": n, "tests": lv.get("tests"), "sweeps": lv.get("sweeps"), "fresh": lv.get("fresh"),
            "chop_grade_C": n > CHOP_MAX}


def prov_trail(states):
    """engine prov stack (approx.) from Daily why events: push = new leg / A1 completion; confirm = "continuation confirm";
    restore = "वर परत". Returns list[bool] provisional per Daily state."""
    out, depth = [], 0
    for x in states:
        w = x.why or ""
        if "continuation confirm" in w:
            depth = 0
        elif "वर परत" in w:
            depth = max(0, depth - 1)
        elif w.startswith("नवा impulse") or "correction (A1) संपली" in w:
            depth += 1
        if x.trend not in ("UP", "DOWN") or x.phase == "origin_broken" or w.startswith(("LH + close", "HL + close", "origin तुटला + उलट",
                                                                                          "origin तुटल्यानंतर")):
            depth = 0                                                      # नवा trend / restore अपयशी ⇒ stack रिकामा
        out.append(depth > 0)
    return out


def col_d(r, states, prov):
    import bisect
    kats = [x.known_at for x in states]
    j = bisect.bisect_right(kats, pd.Timestamp(r["bar_end"])) - 1
    x = states[j]
    p = bool(prov[j])
    conv = r.get("conviction")
    return {"daily": f"{x.trend} {x.phase}/{x.counter or '-'}", "protected": None if x.protected is None else round(x.protected.price, 2),
            "provisional": p, "cap": r.get("trend_cap"), "conviction": conv,
            "respected": (not p) or conv in ("B", None)}


def col_e(r, A, t, tss, s):
    d = 1 if r["trade_side"] == ["bull_put"] else -1
    lv, k = r["level"], r["K"] or {}
    k0 = int(k.get("k_open_bar") or t)
    a = next((i for i in range(k0, t + 1) if ((A["low"][i] <= lv["hi"]) if d > 0 else (A["high"][i] >= lv["lo"]))), t)
    zs = M.zone_study(A, a, t, d, s)
    ok, why, cm = M.commitment(A, t, d, lv, s, tss, win=a)
    hv = "handover" if zs.get("handover") else ("absorption" if zs.get("absorption") else
                                                 ("no handover" if zs.get("handover") is not None else "too few bars"))
    return {"arrival_bar": a, "window_bars": t - a + 1, "a2": hv, "a2_line": zs.get("line"),
            "c0_body_mult": cm.get("body_mult"), "c0_ok": bool(ok), "c0_why": why, "volume": "NA (no futures volume 2015-2024)"}


def col_f(r, m1, A, m15):
    d = 1 if r["trade_side"] == ["bull_put"] else -1
    k = r["K"] or {}
    end = pd.Timestamp(r["ts"]) + pd.Timedelta(minutes=15)
    i_end = k.get("i_end_bar")
    if i_end is None:
        return {"ltf": "NA"}
    start = pd.Timestamp(m15["timestamp"].iloc[int(i_end)])
    x = m1[(m1["timestamp"] >= start) & (m1["timestamp"] < end)].set_index("timestamp")
    b5 = x.resample("5min", origin="start_day", offset="15min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    b5 = b5.reset_index()
    if len(b5) < 6:
        return {"ltf": "NA (few 5M bars)"}
    H, L, C = (b5[c].to_numpy(float) for c in ("high", "low", "close"))
    n = len(b5) - 1
    ext = int(np.argmin(L) if d > 0 else np.argmax(H))                    # pullback extreme on 5M
    piv = [p for p in fractal(H, L, 2, n) if p[0] == ("H" if d > 0 else "L") and p[2] < ext]
    if not piv:
        return {"ltf": "no 5M swing before the pullback extreme", "ext_time": f"{b5['timestamp'].iloc[ext]:%H:%M}"}
    px, pi = piv[-1][1], piv[-1][2]
    hit = next((i for i in range(ext + 1, n + 1) if ((C[i] > px) if d > 0 else (C[i] < px))), None)
    if hit is None:
        return {"ltf": f"still against (last 5M {'LH' if d > 0 else 'HL'} {px:,.0f} at {b5['timestamp'].iloc[pi]:%d-%b %H:%M}, no close beyond)",
                "choch": False}
    return {"ltf": f"CHoCH by close at {b5['timestamp'].iloc[hit]:%d-%b %H:%M} ({C[hit]:,.0f} beyond {px:,.0f})", "choch": True}


def hourly(m15):
    x = m15.copy()
    x["timestamp"] = pd.to_datetime(x["timestamp"])
    x["bar_end"] = pd.to_datetime(x["bar_end"])
    x["_h"] = x["timestamp"].dt.normalize() + ((x["timestamp"] - x["timestamp"].dt.normalize() - pd.Timedelta(minutes=15))
                                               // pd.Timedelta(hours=1)) * pd.Timedelta(hours=1) + pd.Timedelta(minutes=15)
    g = x.groupby("_h", sort=True)
    return g.agg(timestamp=("timestamp", "first"), open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
                 bar_end=("bar_end", "last")).reset_index(drop=True)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    o = pickle.load(open(argv[0], "rb"))
    from elliott import data_policy as DP
    m15 = o["m15"].reset_index(drop=True)
    assert all(DP.period(t) != "HOLDOUT" for t in pd.to_datetime(m15["timestamp"]).dt.normalize().unique())
    m1 = pd.read_parquet(argv[1])
    m1["timestamp"] = pd.to_datetime(m1["timestamp"])
    m1 = m1[m1["timestamp"] < DP.HOLDOUT_START]
    A = {k: m15[k].to_numpy(float) for k in ("open", "high", "low", "close")}
    tss = pd.to_datetime(m15["timestamp"]).to_numpy()
    s = S3.load()
    h1 = hourly(m15)
    prov = prov_trail(o["daily_states"])
    rows = []
    for r in o["setups"]:
        t = int(r["bar"])
        row = {"ts": r["ts"][:16], "side": r["trade_side"][0], "level": f"{r['level']['lo']:,.0f}–{r['level']['hi']:,.0f}",
               "a": col_a(r, m15, t, o["daily_df"], h1), "b": col_b(r, A, t), "c": col_c(r, m15, t), "d": col_d(r, o["daily_states"], prov),
               "e": col_e(r, A, t, tss, s), "f": col_f(r, m1, A, m15)}
        rows.append(row)
        print(json.dumps(row, default=str, ensure_ascii=False))
    if len(argv) > 2:
        json.dump(rows, open(argv[2], "w"), default=str, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
