"""gallery2/schema.py — एका marked chart ची नोंद (JSON) आणि तिची तपासणी.

```
{"schema": 1, "id": "BANKNIFTY_D_20251215", "symbol": "BANKNIFTY", "timeframe": "D",
 "window": {"start": "2025-12-15 00:00:00", "end": "2026-10-09 00:00:00"}, "split": "dev",
 "legs":  [{"start_bar": 33, "start_ts": "…", "start_price": 61764.85, "end_bar": 74, "end_ts": "…", "end_price": 49954.85,
            "label": "impulse"}],                                      # bar = window मधला index (0 = window चा पहिला bar)
 "trend": [{"from_bar": 0, "from_ts": "…", "state": "down"}],          # state पुढच्या ओळीपर्यंत / window शेवटपर्यंत
 "zones": [{"kind": "supply", "low": 57846.0, "high": 59875.0, "from_bar": 30}],   # from_bar ऐच्छिक
 "marker": "Abhi", "marked_at": "2026-10-12 10:00:00", "notes": ""}
```

तपासणी (`validate`, चुका मराठी/इंग्रजीत यादी म्हणून; रिकामी ⇒ ठीक):
  • id / symbol / timeframe / window / split manifest शी जुळतात; window data policy मध्ये (NIFTY holdout कधीच नाही).
  • legs: start_bar < end_bar, क्रमाने, एकमेकांवर चढत नाहीत (एका leg चा शेवट = पुढच्याची सुरुवात चालते); ts = त्या bar चा timestamp;
    up leg low ⇒ high, down leg high ⇒ low; किंमत त्या bar च्या टोकाशी `PRICE_TOL_MR` × median range (window) आत; label हवा.
  • trend: किमान एक state, from_bar वाढता, state यादीतला; zones: low < high, kind demand / supply, from_bar window मध्ये,
    किंमत window च्या आसपास. Split manifest पेक्षा वेगळा ⇒ चूक (test chart कधीच dev होत नाही).
"""
import math
import numbers

import pandas as pd

from . import data as GD

SCHEMA = 1
LEG_LABELS = ("impulse", "correction", "uncertain")
TREND_STATES = ("up", "down", "range", "uncertain")
ZONE_KINDS = ("demand", "supply")
SPLITS = ("dev", "test")
PRICE_TOL_MR = 0.25            # क्लिक / टाईप केलेली किंमत bar च्या high / low पासून किती दूर चालते (median range च्या भागात)


def ts_str(t):
    return str(pd.Timestamp(t))


def chart_id(symbol, tf, start):
    return f"{symbol}_{tf}_{pd.Timestamp(start):%Y%m%d}" + ("" if tf == "D" else f"{pd.Timestamp(start):%H%M}")


def median_range(bars):
    r = (bars["high"] - bars["low"]).to_numpy(float)
    r = r[r > 0]
    return float(pd.Series(r).median()) if len(r) else 0.0


def leg(bars, b0, b1, label, p0=None, p1=None):
    """दोन bars (window index) ⇒ leg dict. किंमत दिली नाही ⇒ दिशेनुसार bar चे टोक (up: low ⇒ high; down: high ⇒ low; दिशा
    दोन्ही टोकांच्या मधल्या किंमतीवरून)."""
    b0, b1 = int(b0), int(b1)
    h, lo = bars["high"].to_numpy(float), bars["low"].to_numpy(float)
    if p0 is None or p1 is None:
        up = (h[b1] + lo[b1]) >= (h[b0] + lo[b0])
        p0, p1 = (lo[b0], h[b1]) if up else (h[b0], lo[b1])
    ts = bars["timestamp"]
    return {"start_bar": b0, "start_ts": ts_str(ts.iloc[b0]), "start_price": float(p0), "end_bar": b1, "end_ts": ts_str(ts.iloc[b1]),
            "end_price": float(p1), "label": label}


def from_points(bars, points, labels):
    """Abhi चे क्लिक केलेले बिंदू [(bar, "H" | "L"), …] (साखळी) ⇒ legs. labels[i] = leg i (बिंदू i ⇒ i+1) चा label."""
    h, lo = bars["high"].to_numpy(float), bars["low"].to_numpy(float)
    out = []
    for i in range(len(points) - 1):
        (b0, k0), (b1, k1) = points[i], points[i + 1]
        p0 = h[int(b0)] if k0 == "H" else lo[int(b0)]
        p1 = h[int(b1)] if k1 == "H" else lo[int(b1)]
        out.append(leg(bars, b0, b1, labels[i] if i < len(labels) else None, p0, p1))
    return out


def to_points(legs):
    """legs (साखळी) ⇒ (बिंदू, labels, साखळी तुटली का). तुटलेल्या जागी नवा बिंदू (मधला leg "uncertain" होत नाही — त्या gap चा leg
    वेगळा label None ⇒ जतन करण्याआधी Abhi ला निवडावा लागतो)."""
    pts, labels, broken = [], [], False
    for lg in sorted(legs or [], key=lambda x: x["start_bar"]):
        k0 = "L" if lg["end_price"] > lg["start_price"] else "H"
        k1 = "H" if k0 == "L" else "L"
        if not pts:
            pts.append((int(lg["start_bar"]), k0))
        elif pts[-1][0] != int(lg["start_bar"]):
            broken = True
            labels.append(None)
            pts.append((int(lg["start_bar"]), k0))
        pts.append((int(lg["end_bar"]), k1))
        labels.append(lg.get("label"))
    return pts, labels, broken


def new_record(cand, legs=(), trend=(), zones=(), marker="Abhi", notes="", now=None):
    now = pd.Timestamp(now) if now is not None else pd.Timestamp.now("UTC").tz_localize(None).floor("s")
    return {"schema": SCHEMA, "id": cand["id"], "symbol": cand["symbol"], "timeframe": cand["timeframe"],
            "window": {"start": ts_str(cand["start"]), "end": ts_str(cand["end"])}, "split": cand["split"],
            "legs": list(legs), "trend": list(trend), "zones": list(zones), "marker": marker or "Abhi", "marked_at": ts_str(now),
            "notes": notes or ""}


def _num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def validate(rec, cand, bars=None):
    """चुका (strings) ची यादी; रिकामी ⇒ ठीक. `bars` = `data.load_window(cand)` (नसेल ⇒ फक्त रचना + policy तपासणी)."""
    err = []
    if rec.get("schema") != SCHEMA:
        err.append(f"schema {rec.get('schema')!r} ≠ {SCHEMA}")
    for k in ("id", "symbol", "timeframe", "split"):
        if rec.get(k) != cand.get(k):
            err.append(f"{k} {rec.get(k)!r} ≠ manifest {cand.get(k)!r}")
    if rec.get("split") not in SPLITS:
        err.append(f"split {rec.get('split')!r}")
    w = rec.get("window") or {}
    try:
        if pd.Timestamp(w.get("start")) != pd.Timestamp(cand["start"]) or pd.Timestamp(w.get("end")) != pd.Timestamp(cand["end"]):
            err.append("window manifest शी जुळत नाही")
        GD.window_allowed(cand["symbol"], cand["start"], cand["end"], exception=bool(cand.get("holdout_dates_exception")))
    except GD.DP.HoldoutError as exc:
        err.append(f"holdout: {exc}")
    except (TypeError, ValueError) as exc:
        err.append(f"window: {exc}")
    if not str(rec.get("marker") or "").strip():
        err.append("marker रिकामा")
    try:
        pd.Timestamp(rec.get("marked_at"))
    except (TypeError, ValueError):
        err.append("marked_at तारीख नाही")
    n = len(bars) if bars is not None else None
    err += _legs(rec.get("legs") or [], bars, n)
    if not any(t.get("state") in TREND_STATES for t in rec.get("trend") or []):
        err.append("trend: किमान एक trend state हवा (from_bar + up / down / range / uncertain)")
    err += _trend(rec.get("trend") or [], bars, n)
    err += _zones(rec.get("zones") or [], bars, n)
    return err


def _bar_ok(b, n):
    return isinstance(b, numbers.Integral) and not isinstance(b, bool) and b >= 0 and (n is None or b < n)


def _legs(legs, bars, n):
    err = []
    tol = PRICE_TOL_MR * median_range(bars) if bars is not None and len(bars) else None
    prev_end = -1
    for i, lg in enumerate(legs, 1):
        b0, b1 = lg.get("start_bar"), lg.get("end_bar")
        p0, p1 = _num(lg.get("start_price")), _num(lg.get("end_price"))
        if not (_bar_ok(b0, n) and _bar_ok(b1, n)):
            err.append(f"leg {i}: bar index window बाहेर ({b0}, {b1})")
            continue
        if b1 <= b0:
            err.append(f"leg {i}: end_bar {b1} ≤ start_bar {b0}")
        if b0 < prev_end:
            err.append(f"leg {i}: आधीच्या leg वर चढतो (start {b0} < आधीचा end {prev_end}) — legs क्रमाने, overlap नाही")
        prev_end = max(prev_end, b1)
        if lg.get("label") not in LEG_LABELS:
            err.append(f"leg {i}: label {lg.get('label')!r} — {LEG_LABELS} पैकी हवा")
        if p0 is None or p1 is None or p0 == p1:
            err.append(f"leg {i}: किंमत चुकीची ({lg.get('start_price')}, {lg.get('end_price')})")
            continue
        if bars is None:
            continue
        ts = bars["timestamp"]
        for side, b, key in (("start", b0, "start_ts"), ("end", b1, "end_ts")):
            if lg.get(key) is not None and pd.Timestamp(lg[key]) != pd.Timestamp(ts.iloc[b]):
                err.append(f"leg {i}: {key} {lg[key]} ≠ bar {b} चा {ts.iloc[b]}")
        up = p1 > p0
        h, lo = bars["high"].to_numpy(float), bars["low"].to_numpy(float)
        want0, want1 = (lo[b0], h[b1]) if up else (h[b0], lo[b1])
        for side, p, wv in (("start", p0, want0), ("end", p1, want1)):
            if abs(p - wv) > tol:
                ext = ("low" if side == "start" else "high") if up else ("high" if side == "start" else "low")
                err.append(f"leg {i}: {side} {p:g} हा bar चा {ext} ({wv:g}) नाही (tol {tol:.2f})")
    return err


def _trend(trend, bars, n):
    err, prev = [], -1
    for i, t in enumerate(trend, 1):
        b = t.get("from_bar")
        if not _bar_ok(b, n):
            err.append(f"trend {i}: from_bar {b!r} window बाहेर")
            continue
        if b <= prev:
            err.append(f"trend {i}: from_bar {b} वाढता हवा")
        prev = b
        if t.get("state") not in TREND_STATES:
            err.append(f"trend {i}: state {t.get('state')!r} — {TREND_STATES} पैकी")
        if bars is not None and t.get("from_ts") is not None and pd.Timestamp(t["from_ts"]) != pd.Timestamp(bars["timestamp"].iloc[b]):
            err.append(f"trend {i}: from_ts bar {b} शी जुळत नाही")
    return err


def _zones(zones, bars, n=None):
    err = []
    if bars is not None and len(bars):
        lo_w, hi_w = float(bars["low"].min()), float(bars["high"].max())
        pad = hi_w - lo_w
    for i, z in enumerate(zones, 1):
        lo, hi = _num(z.get("low")), _num(z.get("high"))
        if z.get("kind") not in ZONE_KINDS:
            err.append(f"zone {i}: kind {z.get('kind')!r} — demand / supply")
        if z.get("from_bar") is not None and not _bar_ok(z.get("from_bar"), n):
            err.append(f"zone {i}: from_bar {z.get('from_bar')!r} window बाहेर")
        if lo is None or hi is None or not lo < hi:
            err.append(f"zone {i}: low < high हवं ({z.get('low')}, {z.get('high')})")
            continue
        if bars is not None and len(bars) and (lo < lo_w - pad or hi > hi_w + pad):
            err.append(f"zone {i}: {lo:g}–{hi:g} chart च्या किंमत-पट्ट्यापासून खूप दूर")
    return err
