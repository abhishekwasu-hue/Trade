"""backtest_review/scan.py — Backtest visual review चं गणित (TRADE_BACKTEST_VISUAL_REVIEW_PROMPT §1–2). Charts / store वेगळे.

  load_period   elliott/data_policy नेच: holdout ला छेदणारी श्रेणी ⇒ HoldoutError; contaminated (Jul–Oct 2026) फक्त "golden" purpose ने
                (logic पडताळणी, tuning नाही). Warm-up (मागचे दिवस) सुद्धा परवानगीतलेच — holdout मधून कधीच नाही.
  scan_day      दिवसाच्या प्रत्येक बंद 15M bar वर: market_state (F1–F4; Elliott इथे नाही — evaluate मध्ये) ⇒ impulse + correction ≥ 38.2%
                असेल तर candidate ⇒ chart_reader.evaluate (code grade, सध्याचे settings) ⇒ status (ENTRY / C / REJECTED) + reason codes.
  trades        ENTRY candidates, एका impulse/correction चा पहिलाच (पुढचे bars त्याच setup चे).
  hindsight     entry नंतरचे पुढचे `days` sessions: target / SL आधी (एकाच bar मध्ये दोन्ही ⇒ SL, सावध), नाहीतर TIME; MFE / MAE (points).
Settings hash = chart_reader settings + market_state DEFAULTS + CAS window (नोंद; बदल ओळखायला).
"""
import hashlib
import json

import numpy as np
import pandas as pd

import market_state as MS
from chart_reader import evaluate as EV
from elliott import data_policy as DP
from opportunity_engine import cas as CAS
from vision_led import candidates as CA

from . import reasons as RC

PERIODS = {"2026_q3": ("2026-07-01", "2026-10-08"), "2024_q1": ("2024-01-01", "2024-03-31")}
WARMUP_DAYS = 95
EVAL_DAYS = 90


def settings_hash(s):
    blob = json.dumps({"chart_reader": s, "market_state": MS.DEFAULTS, "cas": CAS.load_cas_window()}, sort_keys=True, default=str)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:12]


def load_period(m1, start, end):
    """m1 (कुठूनही वाचलेला 1m) ⇒ [start − warm-up, end] आणि परवानगी तपासून. Holdout ⇒ HoldoutError (रिकामं परत नाही)."""
    DP.check_range(start, end, purpose="golden")
    w0 = pd.Timestamp(start) - pd.Timedelta(days=WARMUP_DAYS)
    d = m1[(pd.to_datetime(m1["timestamp"]) >= w0) & (pd.to_datetime(m1["timestamp"]) < pd.Timestamp(end) + pd.Timedelta(days=1))]
    return DP.filter_allowed(d.reset_index(drop=True), "golden")


def days_of(m1, start, end):
    ts = pd.to_datetime(m1["timestamp"])
    d = ts.dt.normalize()
    return sorted(x for x in d.unique() if pd.Timestamp(start) <= x <= pd.Timestamp(end))


def _top_points(r, n=4):
    pts = r.get("points") or {}
    return sorted(((k, v) for k, v in pts.items() if isinstance(v, (int, float)) and v), key=lambda kv: -abs(kv[1]))[:n]


def inv_source(r):
    """SL कोणत्या संदर्भावरून (risk.compute: area / reversal candle / correction टोक यांपैकी सगळ्यात दूरचा)."""
    side = int(r.get("side") or 0)
    act = (r.get("active") or {}).get("area") or {}
    comp = (r.get("reversal") or {}).get("comp")
    ext = (r.get("structure") or {}).get("correction_extreme")
    refs = []
    if act:
        refs.append(("area " + str(act.get("id")), float(act["low"] if side > 0 else act["high"])))
    if comp:
        refs.append(("reversal candle", float(comp[2] if side > 0 else comp[1])))
    if ext is not None:
        refs.append(("correction टोक", float(ext)))
    if not refs or not side:
        return None
    return (min if side > 0 else max)(refs, key=lambda x: x[1])[0]


def candidate_record(r, ms, bar):
    act = (r.get("active") or {}).get("area") or {}
    rk = r.get("risk") or {}
    return {"bar_start": pd.Timestamp(bar["timestamp"]), "bar_end": pd.Timestamp(bar["bar_end"]), "side": int(r.get("side") or 0),
            "code_side": ms.get("side"), "side_reasons": ms.get("side_reasons") or [], "status": RC.status(r), "codes": RC.codes(r),
            "grade": r.get("grade"), "total": r.get("total"), "entry_px": rk.get("entry"), "inv": rk.get("invalidation"),
            "targets": rk.get("targets"), "rr": rk.get("rr"), "inv_src": inv_source(r),
            "rev_comp": (r.get("reversal") or {}).get("comp"), "rev_status": (r.get("reversal") or {}).get("status"), "area": {k: act.get(k) for k in ("id", "tool", "low", "high", "slope", "anchors",
                                                                                               "value") if k in act} or None,
            "confluence": (r.get("active") or {}).get("confluence") or [], "top_points": _top_points(r),
            "ctype": (r.get("structure") or {}).get("correction_type"), "story": (r.get("story") or [])[:10],
            "impulse": ms.get("impulse"), "labels": (ms.get("correction") or {}).get("labels") or [], "trend": ms.get("trend"),
            "lq": ((r.get("kb") or {}).get("LQ") or {}).get("pts"), "mr": r.get("mr"),
            "elliott": (r.get("elliott") or {}).get("line"), "areas": compact_areas(r)}


def compact_areas(r, tools=("a", "b", "c", "d", "f"), n=10):
    """1H / दिवस charts साठी मोठे areas (horizontal, flip, base, range edge, trendline) — फक्त ठोस, BROKEN / MAGNET नाहीत."""
    out = []
    for z in (r.get("areas") or {}).get("candidates") or []:
        if z.get("tool") in tools and z.get("kind") == "solid" and z.get("state") not in ("BROKEN", "MAGNET", "DEAD") and \
                (z.get("tool") != "f" or z.get("valid")):
            out.append({k: z.get(k) for k in ("id", "tool", "low", "high", "slope", "anchors", "value", "state") if k in z})
    return out[:n]


def scan_day(m1, day, s, frames=None, trig=None, eval_fn=None, state_fn=None, profile="srv2", pullback_min=None):
    """एका दिवसाचे candidates (बंद 15M bars, क्रमाने). eval_fn / state_fn tests साठी बदलता येतात."""
    eval_fn = eval_fn or (lambda w, asof: EV.evaluate(w, profile, asof, s=s))
    state_fn = state_fn or (lambda asof: MS.read(m1, asof, run_elliott=False, frames=frames))
    pullback_min = CA.DEFAULTS["pullback_min"] if pullback_min is None else pullback_min
    trig = trig if trig is not None else MS.frame(m1, "15m", pd.Timestamp(day) + pd.Timedelta(days=1))
    day = pd.Timestamp(day).normalize()
    idx = np.nonzero((pd.to_datetime(trig["timestamp"]).dt.normalize() == day).to_numpy())[0]
    tsv = pd.to_datetime(m1["timestamp"]).to_numpy(dtype="datetime64[ns]")
    out = []
    for j in idx:
        bar = trig.iloc[j]
        asof = pd.Timestamp(bar["bar_end"])
        ms = state_fn(asof)
        imp = CA.impulse_from_state(ms, trig.iloc[: j + 1])
        if imp is None or imp["retrace"] < pullback_min:
            continue
        a = int(np.searchsorted(tsv, np.datetime64(asof - pd.Timedelta(days=EVAL_DAYS), "ns")))
        b = int(np.searchsorted(tsv, np.datetime64(asof, "ns")))
        r = eval_fn(m1.iloc[a:b].reset_index(drop=True), asof)
        out.append(candidate_record(r, ms, bar))
    return out


def trades(cands, trig=None, days=3):
    """ENTRY candidates ⇒ trades: एका वेळी एकच position — आधीचा trade (hindsight नुसार) target / SL / time ने बंद होईपर्यंत नवीन entry नाही
    (त्याच correction मधली नंतरची entry सुद्धा, आधीचा बंद झाल्यावर — 7 Oct: 09:30 नंतर 12:15). trig नसेल ⇒ प्रति impulse पहिलाच."""
    seen, out, busy_until = set(), [], None
    for c in cands:
        if c["status"] != "ENTRY":
            continue
        if trig is None:
            imp = c.get("impulse") or {}
            key = (c["side"], imp.get("from"), imp.get("to"))
            if key in seen:
                continue
            seen.add(key)
            out.append(c)
            continue
        if busy_until is not None and pd.Timestamp(c["bar_start"]) <= busy_until:
            continue
        h = hindsight(trig, c, days)
        c["hindsight"] = h
        out.append(c)
        busy_until = pd.Timestamp(h["at"]) if h.get("at") else pd.Timestamp.max
    return out


def hindsight(trig, c, days=3):
    """entry नंतरचे bars (फक्त अहवाल — निर्णयात कधीच नाही). रिटर्न {result: TARGET / SL / TIME, at, exit, mfe, mae}."""
    side, entry, inv = c["side"], c.get("entry_px"), c.get("inv")
    tg = (c.get("targets") or [{}])[0].get("price") if c.get("targets") else None
    if entry is None or inv is None or tg is None:
        return {"result": "NA"}
    after = trig[pd.to_datetime(trig["timestamp"]) > pd.Timestamp(c["bar_start"])]
    sess = pd.to_datetime(after["timestamp"]).dt.normalize().unique()[:int(days)]
    after = after[pd.to_datetime(after["timestamp"]).dt.normalize().isin(sess)]
    mfe = mae = 0.0
    for r in after.itertuples():
        fav = (r.high - entry) if side > 0 else (entry - r.low)
        adv = (entry - r.low) if side > 0 else (r.high - entry)
        mfe, mae = max(mfe, fav), max(mae, adv)
        hit_sl = (r.low <= inv) if side > 0 else (r.high >= inv)
        hit_tg = (r.high >= tg) if side > 0 else (r.low <= tg)
        if hit_sl:
            return {"result": "SL", "at": str(r.timestamp), "exit": float(inv), "mfe": round(mfe, 2), "mae": round(mae, 2),
                    "both_same_bar": bool(hit_tg)}
        if hit_tg:
            return {"result": "TARGET", "at": str(r.timestamp), "exit": float(tg), "mfe": round(mfe, 2), "mae": round(mae, 2)}
    last = float(after["close"].iloc[-1]) if len(after) else None
    return {"result": "TIME", "at": None if not len(after) else str(after["timestamp"].iloc[-1]), "exit": last, "mfe": round(mfe, 2),
            "mae": round(mae, 2)}


def day_story(cands, ms_close):
    """दिवसाखालची एक ओळ: code ची गोष्ट."""
    n = {k: sum(c["status"] == k for c in cands) for k in ("ENTRY", "C", "REJECTED")}
    tr = (ms_close or {}).get("trend") or {}
    dn = {1: "up", -1: "down", 0: "range"}
    imp = (ms_close or {}).get("impulse") or {}
    head = f"trend {dn.get(tr.get('dir'), '—')}{' (testing)' if tr.get('state') == 'testing' else ''}"
    if imp:
        head += f" · impulse {imp['from']:,.0f}→{imp['to']:,.0f}"
    corr = (ms_close or {}).get("correction") or {}
    if corr.get("labels"):
        head += " · " + "-".join(x["label"] for x in corr["labels"]) + f" ({corr.get('status')})"
    head += f" · side {(ms_close or {}).get('side', '—')}"
    common = pd.Series([code for c in cands for code in c["codes"]]).value_counts().head(3).to_dict() if cands else {}
    return head + f" · candidates {len(cands)} (✅ {n['ENTRY']}, 🟡 {n['C']}, ✖ {n['REJECTED']})" + \
        (" · नकार: " + ", ".join(f"{k}×{v}" for k, v in common.items()) if common else "")
