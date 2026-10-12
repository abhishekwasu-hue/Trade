"""scripts/setups_trend_audit.py — "trend first" audit of V22 setups against a pre-declared 6-month Daily structure rule
(Abhi: TRADE_SESSION_DECISIONS_SENSEX_SETUPS_CD14 §2; report docs/reports/setups_prA_v1_audit.md).

Rule (declared before any audit row was computed; never fitted to outcomes — no P&L, no bar after the setup):
  * Daily sessions strictly BEFORE the setup day; window = the last 126 sessions (~6 months).
  * Swings: fractal pivots, N = 5 each side (high[i] > max of the 5 before, >= max of the 5 after; low mirrored), confirmed inside the
    window (i + 5 <= last session); alternating in confirm order, same kind twice ⇒ the more extreme one (as decision3.daily._add).
  * Last two swing highs (H1, H2) and lows (L1, L2): HH + HL ⇒ UP · LH + LL ⇒ DOWN · otherwise RANGE.
  * Flags (row ambiguous — Abhi confirms): few (< 2 highs or lows), mixed (RANGE), broken (last close already beyond the latest
    opposite swing), equal (|H2 − H1| or |L2 − L1| <= 0.25 × median range of the last 10 sessions — the engine's RANGE tol).
  * Verdict: bull_put needs UP, bear_call needs DOWN; against ⇒ FAIL; RANGE ⇒ ambiguous.

  python3 scripts/setups_trend_audit.py <rows.pkl>     (pickle: {"setups": [V22 rows], "daily_df": Daily OHLC} from one V22 run)

Report only (stdout); no order / broker / network call. NIFTY holdout rows are refused (elliott.data_policy).
"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # pickle rows carry decision3 objects
N, WIN = 5, 126


def swings(d):
    H, L = d["high"].to_numpy(float), d["low"].to_numpy(float)
    raw = []
    for i in range(N, len(d) - N):
        if H[i] > H[i - N:i].max() and H[i] >= H[i + 1:i + N + 1].max():
            raw.append(("H", float(H[i]), i, i + N))
        if L[i] < L[i - N:i].min() and L[i] <= L[i + 1:i + N + 1].min():
            raw.append(("L", float(L[i]), i, i + N))
    raw.sort(key=lambda p: (p[3], p[2]))
    seq = []
    for p in raw:
        if seq and seq[-1][0] == p[0]:
            if (p[1] > seq[-1][1]) if p[0] == "H" else (p[1] < seq[-1][1]):
                seq[-1] = p
            continue
        seq.append(p)
    return seq


def expected(daily, setup_ts):
    """6-month structure known before the setup day ⇒ {reading, flags, H, L, close, dates}."""
    day = pd.Timestamp(setup_ts).normalize()
    d = daily[pd.to_datetime(daily["timestamp"]).dt.normalize() < day].tail(WIN).reset_index(drop=True)
    seq = swings(d)
    hs = [p for p in seq if p[0] == "H"]
    ls = [p for p in seq if p[0] == "L"]
    c = float(d["close"].iloc[-1])
    if len(hs) < 2 or len(ls) < 2:
        return {"reading": "RANGE", "flags": ["few"], "H": hs[-2:], "L": ls[-2:], "close": c, "dates": d["timestamp"]}
    (h1, h2), (l1, l2) = hs[-2:], ls[-2:]
    flags = []
    if h2[1] > h1[1] and l2[1] > l1[1]:
        rd = "UP"
    elif h2[1] < h1[1] and l2[1] < l1[1]:
        rd = "DOWN"
    else:
        rd = "RANGE"
        flags.append("mixed")
    if (rd == "UP" and c < l2[1]) or (rd == "DOWN" and c > h2[1]):
        flags.append("broken")
    tol = 0.25 * float(np.median((d["high"] - d["low"]).to_numpy(float)[-10:]))
    if abs(h2[1] - h1[1]) <= tol or abs(l2[1] - l1[1]) <= tol:
        flags.append("equal")
    return {"reading": rd, "flags": flags, "H": [h1, h2], "L": [l1, l2], "close": c, "dates": d["timestamp"]}


def verdict(side, reading):
    if reading == "RANGE":
        return "ambiguous"
    return "pass" if reading == {"bull_put": "UP", "bear_call": "DOWN"}[side] else "FAIL"


def audit(setups, daily):
    out = []
    for r in setups:
        side = r["trade_side"][0] if len(r["trade_side"]) == 1 else "?"
        e = expected(daily, r["ts"])
        out.append({"ts": r["ts"][:16], "side": side, "engine": f"{r['daily_trend']} {r['daily_phase']}", "rule": e["reading"],
                    "flags": e["flags"], "verdict": verdict(side, e["reading"]),
                    "H": [(round(p[1], 2), str(e["dates"].iloc[p[2]])[:10]) for p in e["H"]],
                    "L": [(round(p[1], 2), str(e["dates"].iloc[p[2]])[:10]) for p in e["L"]], "close": round(e["close"], 2)})
    return out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    o = pickle.load(open(argv[0], "rb"))
    daily = o["daily_df"]
    from elliott import data_policy as DP
    assert all(DP.period(t) != "HOLDOUT" for t in pd.to_datetime(daily["timestamp"])), "holdout rows in the Daily frame"
    rows = audit(o["setups"], daily)
    for x in rows:
        print(x["ts"], x["side"], x["engine"], "| rule", x["rule"], ",".join(x["flags"]) or "-", "H", x["H"], "L", x["L"],
              "close", x["close"], "=>", x["verdict"])
    from collections import Counter
    print(dict(Counter(x["verdict"] for x in rows)))


if __name__ == "__main__":
    main()
