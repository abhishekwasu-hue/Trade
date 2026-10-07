"""
elliott/golden.py — E4: golden-file regression (NIFTY 25 Sep – 6 Oct 2026; docs/reports/elliott_golden_expectations.json)
-------------------------------------------------------------------------------------------------------------------
🎓 Abhi चे screenshots वरून अपेक्षा (±tolerance_pts). स्तर (उत्तर 8):
  must      bot ने हा trade **निवडायला** हवा (signal + दिशा + दिवस/वेळ + किंमत) — नाहीतर FAIL (कारणासह)
  must_not  bot ने हा trade घेतला ⇒ FAIL (T6 A-end bear calls, 6 Oct 09:40 bear call 22,614, gap दिवसांचे opening window)
  verify    जुळलं नाही तर FAIL नाही — report (reversal candle data वर पडताळा)
  report    Tier C — घेतला/नाही दोन्ही चालतं; फक्त report
"Trade निवडला" = E2 signal (setup + strike plan स्तर). Sizing (₹10L वर Tier B 0 lot — E3 शोध) वेगळं report — golden चा भाग नाही.
हा काळ CONTAMINATED: logic इथूनच ठरलं ⇒ फक्त regression, edge चा पुरावा नाही.
"""
import datetime as dt
import json
import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPECT = os.path.join(ROOT, "docs", "reports", "elliott_golden_expectations.json")
WINDOWS = {"morning": ("09:15", "12:00"), "afternoon": ("12:00", "15:30")}


def load_expectations(path=EXPECT):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _windows(day, time):
    """त्या दिवसाच्या वेळ-खिडक्या [(start, end)]."""
    d = pd.Timestamp(day)
    if time is None:
        return [(d + pd.Timedelta("09:15:00"), d + pd.Timedelta("15:30:00"))]
    if isinstance(time, str) and time in WINDOWS:
        a, b = WINDOWS[time]
        return [(d + pd.Timedelta(a + ":00"), d + pd.Timedelta(b + ":00"))]
    times = time if isinstance(time, list) else [time]
    out = []
    for x in times:
        c = d + pd.Timedelta(x + ":00")
        out.append((c - pd.Timedelta("20min"), c + pd.Timedelta("40min")))     # screenshot वेळ ≈; signal bar close नंतरचा
    return out


def _in(t, wins):
    return any(a <= t <= b for a, b in wins)


def _near(x, target, tol):
    return target is None or (x is not None and abs(x - target) <= tol)


def _price_of(sig):
    return sig.extreme


def _setup_code(e):
    """JSON setup मजकुरातला S-code (उदा. "B -> C (S6a)" ⇒ "S6a"); नसेल ⇒ None."""
    import re
    m = re.search(r"\((S\d+[a-c]?)\)", e.get("setup") or "")
    return m.group(1) if m else None


def match(signals, e, tol, strict=True):
    """एका अपेक्षेशी जुळणारे signals. strict (must/verify/report): वेळ + दिशा + किंमत (correction extreme ±tol) + JSON मध्ये
    दिलेले असतील तर setup code आणि tier. must_not: फक्त वेळ + दिशा (किंमत filter नाही — review: नाहीतर खोटा PASS)."""
    wins = _windows(e["date"], e.get("time"))
    code, tier = _setup_code(e), e.get("tier")
    out = []
    for s in signals:
        if not _in(pd.Timestamp(s.t), wins):
            continue
        if e.get("spread") and s.direction != e["spread"]:
            continue
        if strict:
            if e.get("price") is not None and not _near(_price_of(s), e["price"], tol):
                continue
            if code and s.setup != code:
                continue
            if tier and s.tier != tier:
                continue
        out.append(s)
    return out


def evaluate(signals, exp=None, reasons=None):
    """[{id, level, status, detail}] — status: PASS / FAIL / REPORT. reasons = scanner.reasons (FAIL चं कारण शोधायला).
    Invalidation (JSON) gating नाही (screenshot ±) — detail मध्ये फरक दाखवतो."""
    exp = exp or load_expectations()
    tol = exp.get("tolerance_pts", 15)
    rows = []
    for e in exp["trades"]:
        lvl = e["level"]
        m = match(signals, e, tol, strict=lvl != "must_not")
        if lvl == "must":
            st = "PASS" if m else "FAIL"
        elif lvl == "must_not":
            st = "FAIL" if m else "PASS"
        else:
            st = "REPORT"
        inv = e["invalidation"][0] if e.get("invalidation") else None
        det = "; ".join(f"{pd.Timestamp(s.t):%m-%d %H:%M} {s.setup}/{s.tier} D{s.degree} extreme {s.extreme:.0f} inv {s.hard_inv:.0f}"
                        + (f" (अपेक्षित {inv}, फरक {s.hard_inv - inv:+.0f})" if inv else "") for s in m) or "जुळणारा signal नाही"
        if st == "FAIL" and lvl == "must" and reasons is not None:
            wins = _windows(e["date"], e.get("time"))
            rs = [r for r in reasons if _in(pd.Timestamp(r[0]), wins)]
            top = pd.Series([f"D{r[1]}:{r[3]}" for r in rs]).value_counts().head(5) if rs else None
            loose = match(signals, e, tol, strict=False)
            det += " · त्या वेळची कारणं: " + (", ".join(f"{k} ×{v}" for k, v in top.items()) if top is not None else "—")
            if loose:
                det += " · वेळ+दिशा जुळणारे (setup/किंमत वेगळे): " + "; ".join(
                    f"{pd.Timestamp(x.t):%H:%M} {x.setup}/{x.tier} extreme {x.extreme:.0f}" for x in loose)
        rows.append({"id": e["id"], "level": lvl, "status": st, "setup": e.get("setup"), "detail": det})
    for r in exp.get("rejections", []):
        day = pd.Timestamp(r["date"])
        if r.get("time"):
            m = match(signals, {**r, "spread": r.get("spread")}, tol, strict=False)
        else:                                                                       # opening gap window: 09:45 पर्यंत संपणारा signal
            m = [s for s in signals if pd.Timestamp(s.t).normalize() == day.normalize()
                 and pd.Timestamp(s.t) <= day + pd.Timedelta("09:45:00")]
        rows.append({"id": r["id"], "level": r["level"], "status": "FAIL" if m else "PASS", "setup": r.get("rule"),
                     "detail": "; ".join(f"{pd.Timestamp(s.t):%m-%d %H:%M} {s.direction} {s.setup}" for s in m) or "—"})
    return rows


def golden_csv(trade_data=None):
    base = trade_data or os.environ.get("TRADE_DATA", os.path.join(os.path.dirname(ROOT), "trade-data"))
    p = os.path.join(base, "upstox", "NIFTY_1m_2026-07-01_2026-10-06.csv.gz")
    return p if os.path.exists(p) else None


def load_golden(path):
    d = pd.read_csv(path, parse_dates=["timestamp"])
    return d[["timestamp", "open", "high", "low", "close"]].sort_values("timestamp").reset_index(drop=True)


GOLDEN_FROM = dt.date(2026, 9, 25)
