"""market_state/core.py — `read(df1m, asof)` ⇒ trend (F2), impulse / correction (F3), side + कारणं (F4). No-lookahead.

🎓 व्याख्या (KB K1, K2, K3, भाग G; Abhi 2026-10-08 TRADE_CODE_FIX_CROSSVERIFY_PROMPT §2):
  Frames    1m ⇒ NSE 09:15-anchored, CAS bars वगळून (opportunity_engine/cas.py), फक्त bar_end ≤ asof.
  Swings    elliott/swings.py::degree_pivots (ATR14 × mult) — HTF वर trend_swing_atr_mult, trade TF वर trade_swing_atr_mult.
  MR        मागच्या 20 बंद bars चा (high − low) median, चालू bar वगळून (elliott/breaks.py::median_range).
  Trend (F2, HTF = trend_tf 1h / 75m):
            downtrend = LH + LL. Protected LH = शेवटचा LL बनवणाऱ्या leg ची सुरुवात (BOS करणारा high). Uptrend आरसा.
            Counter चाल **correction** राहते — लांबी कितीही असो — जोपर्यंत protected swing चा **real break** (elliott/breaks.py: 0.25 MR
            buffer + displacement / acceptance / failed retest) होत नाही **आणि** नंतर HL (वर) / LH (खाली) confirmed होत नाही.
            Real break झाला पण पुष्टी नाही ⇒ state "testing" (दिशा तीच, side unclear).
            नवा LL (break नंतर सुद्धा) ⇒ break फसला, protected = नव्या LL आधीचा high.
  Impulse (F3, trade TF): trend दिशेचा leg ज्यात तिन्ही: displacement (≥ impulse_disp_min candles: body ≥ disp_body_mr × MR आणि
            body/range ≥ disp_body_frac) **आणि** कमी overlap (efficiency ratio ≥ impulse_er_min किंवा K10.1 overlap < impulse_overlap_max)
            **आणि** BOS (leg मध्ये आधीच्या त्याच प्रकारच्या trade-degree swing पलीकडे close), आकार ≥ impulse_min_mr × MR.
            सगळ्यात ताजा पात्र leg = impulse; त्यानंतर त्याच दिशेने नवं टोक झालं तर impulse चं टोक तिथपर्यंत वाढतं.
  Correction impulse टोकानंतरची चाल. Origin न तोडता (real break नाही) आणि overlapping (B आला / K10.1 overlap ≥ 0.6) ⇒ correction,
            दिशा impulse ची. retrace 38.2–100% = सामान्य; < 38.2% उथळ; origin real break ⇒ "origin_broken" (A3 व्हेटो, side unclear).
            Labels: A = पहिला counter leg, B = पुढचा, C = B नंतरचं counter टोक (त्यानंतरचे legs = C च्या आतले / C नंतरचे).
  Side (F4) trend (testing नाही), HTF structure state (opportunity_engine/structure.py StructureTracker; *_WEAK = त्याच दिशेचा इशारा)
            आणि Elliott vote (gray ⇒ मत नाही) यांपैकी कुणीही विरोधात असेल ⇒ "unclear" + कारण (candidate टाकत नाही; vision ठरवतो).
Defaults [अनुमान]: impulse_er_min 0.45 हा NIFTY 15M वर KB च्या overlap < 0.4 ऐवजी (7 Oct impulse चा K10.1 overlap 0.62) — Abhi च्या मंजुरीसाठी.
"""
import numpy as np
import pandas as pd

from elliott import breaks as BR
from elliott import settings as ES
from elliott import swings as W
from opportunity_engine import cas as CAS
from opportunity_engine.sessions import resample_nse

DEFAULTS = {
    "trend_tf": "1h",                 # F2 HTF: "1h" | "75m"
    "trend_swing_atr_mult": 1.5,      # HTF swings: ATR14 × हे (KB K1: swing ≥ 1.5–2 MR)
    "trade_tf": "15m",
    "trade_swing_atr_mult": 3.0,      # trade-degree swings (Elliott D1; chart_reader swing_atr_mult)
    "impulse_min_mr": 4.0,            # KB भाग B टप्पा 2: impulse ≥ 4 MR
    "impulse_disp_min": 1,            # impulse मध्ये किमान इतक्या displacement candles
    "disp_body_mr": 1.5,              # displacement candle: body ≥ हे × MR …
    "disp_body_frac": 0.6,            # … आणि body ÷ range ≥ हे (chart_reader settings सारखंच)
    "impulse_er_min": 0.45,           # कमी overlap: efficiency ratio (|निव्वळ| ÷ Σ|close बदल|) ≥ हे … [अनुमान, Abhi मंजुरी]
    "impulse_overlap_max": 0.40,      # … किंवा K10.1 overlap ratio < हे (KB K2)
    "correction_overlap_min": 0.60,   # K10.1: correction overlap > 0.6
    "reversal_retrace_min": 0.382,    # POSSIBLE_REVERSAL v2 (Abhi): counter-move ≥ हे **आणि** impulsive (11 Aug 58% सुद्धा)
    "reversal_min_criteria": 3,       # impulsive = 5 निकषांपैकी ≥ हे (counter_score)
    "reversal_internal_atr": 1.5,     # counter-move मधले आतले swings: ATR × हे (gallery internal legs सारखं)
    "retrace_lo": 0.382,
    "retrace_hi": 1.0,
    "htf_days": 60,                   # HTF trend साठी मागचे इतके दिवस
    "trade_days": 20,                 # trade TF swings साठी मागचे इतके दिवस
    "elliott_degrees": (1, 2),        # F4 Elliott vote (trade degree)
}
TF_MIN = {"5m": 5, "15m": 15, "30m": 30, "1h": 60, "75m": 75, "4h": 240, "1d": 1440}
SIDE = {1: "bull_put", -1: "bear_call"}


# ---------------------------------------------------------------------------------------------------------------- frames
def frame(df1m, tf, asof, cas=None):
    """1m ⇒ NSE 09:15-anchored TF bars, CAS bars वगळून, फक्त पूर्ण बंद (bar_end ≤ asof). Columns: timestamp, bar_end, OHLC.
    (chart_reader/evaluate.py::frame हेच वापरतो — एकच व्याख्या.)"""
    asof = pd.Timestamp(asof)
    d = df1m[pd.to_datetime(df1m["timestamp"]) + pd.Timedelta(minutes=1) <= asof]
    if tf == "1d":
        if not len(d):
            return pd.DataFrame(columns=["timestamp", "bar_end", "open", "high", "low", "close"])
        out = CAS.daily_levels(d, cas)                                   # high/low CAS वगळून; structure close = CAS आधीचा close
        out = out.assign(close=out["clean_close"].fillna(out["close"])).rename_axis("timestamp").reset_index()
        out["bar_end"] = out["timestamp"] + pd.Timedelta(hours=15, minutes=30)
        out = out[out["bar_end"] <= asof]
        return out[["timestamp", "bar_end", "open", "high", "low", "close"]].reset_index(drop=True)
    r = resample_nse(d, TF_MIN[tf], cas=cas)
    r = r[r["bar_closed"].astype(bool) & (r["bar_end"] <= asof)]
    return r[["timestamp", "bar_end", "open", "high", "low", "close"]].reset_index(drop=True)


# ---------------------------------------------------------------------------------------------------------------- swings
def pivots(fr, atr_mult, tf="15m"):
    """elliott/swings.py confirmed pivots (ATR14 × atr_mult), आलटून-पालटून ⇒ [dict(idx, price, kind, conf, ts)]."""
    if len(fr) < 20:
        return []
    es = {"swing_mode": "atr", "atr_len": 14, "swing_atr_mult": {0: float(atr_mult)}}
    out = []
    for p in W.degree_pivots(fr, 0, es, tf):
        q = {"idx": int(p.bar_idx), "price": float(p.price), "kind": p.kind, "conf": int(p.confirmed_idx), "ts": pd.Timestamp(p.ts)}
        if out and out[-1]["kind"] == q["kind"]:
            if (q["kind"] == "H" and q["price"] >= out[-1]["price"]) or (q["kind"] == "L" and q["price"] <= out[-1]["price"]):
                out[-1] = q
            continue
        out.append(q)
    return out


def label(pvs):
    """HH/LH/EQH, HL/LL/EQL — आधीच्या त्याच प्रकारच्या pivot शी (EQ = 0.05% आत)."""
    last, out = {}, []
    for p in pvs:
        prev = last.get(p["kind"])
        if prev is None:
            lab = p["kind"]
        elif abs(p["price"] - prev) <= 5e-4 * prev:
            lab = "EQ" + p["kind"]
        elif p["kind"] == "H":
            lab = "HH" if p["price"] > prev else "LH"
        else:
            lab = "HL" if p["price"] > prev else "LL"
        out.append(dict(p, label=lab))
        last[p["kind"]] = p["price"]
    return out


def _tentative(fr, pvs):
    """शेवटच्या confirmed pivot नंतरचा चालू extreme (बंद bars पर्यंत) — फक्त चालू leg साठी."""
    if not pvs:
        return None
    last = pvs[-1]
    a = last["idx"] + 1
    if a >= len(fr):
        return None
    if last["kind"] == "H":
        seg = fr["low"].to_numpy(float)[a:]
        j = a + len(seg) - 1 - int(np.argmin(seg[::-1]))
        return {"idx": j, "price": float(seg.min()), "kind": "L", "conf": None, "ts": pd.Timestamp(fr["timestamp"].iloc[j])}
    seg = fr["high"].to_numpy(float)[a:]
    j = a + len(seg) - 1 - int(np.argmax(seg[::-1]))
    return {"idx": j, "price": float(seg.max()), "kind": "H", "conf": None, "ts": pd.Timestamp(fr["timestamp"].iloc[j])}


def _es():
    return dict(ES.DEFAULTS)


def _real_break(fr, start, level, side, es, mr):
    if start >= len(fr):
        return None
    return BR.first_real_break(fr, start, level, side, es, mr=mr)


# ---------------------------------------------------------------------------------------------------------------- F2 trend
def trend(fr, s=None, es=None):
    """HTF trend (F2 + KB K1). रिटर्न {dir (+1/−1/0), state ("trend" | "testing" | "range"), protected {price, ts, kind}, break_ts, swings,
    events}. Downtrend उलटायला (uptrend आरसा), क्रमाने:
      1. protected LH चा real break (elliott/breaks.py) ⇒ "testing" (CHoCH = इशारा);
      2. break नंतर confirmed HL (LL च्या वर);
      3. मग break-नंतरच्या high च्या वर close ⇒ REVERSAL_CONFIRMED (K1: "LH, मग CHoCH नंतरच्या low खाली close" चा आरसा).
    त्याआधी नवा LL ⇒ break फसला (BOS), protected = नव्या LL आधीचा high. A1 (Abhi K-10): testing मध्ये जुन्या टोकापलीकडे **close** ⇒
    लगेच BREAK_FAILED (pivot confirm ची वाट नाही), protected = break नंतरचं उलट टोक. KB K1 चा "4 swings निर्णयाशिवाय ⇒ RANGE" नियम F2 ने बदलला
    (Abhi 2026-10-08: counter चाल लांबी कितीही असो correction) ⇒ दिशा ठरल्यावर range मध्ये परत जात नाही."""
    s = {**DEFAULTS, **(s or {})}
    es = es or _es()
    out = {"dir": 0, "state": "range", "protected": None, "break_ts": None, "swings": [], "events": []}
    pv = label(pivots(fr, s["trend_swing_atr_mult"], s["trend_tf"]))
    out["swings"] = pv
    if len(pv) < 4:
        return out
    mr = BR.median_range(fr, es["median_range_n"])
    h, lo, c = (fr[k].to_numpy(float) for k in ("high", "low", "close"))
    ts = fr["timestamp"]
    st = {"d": 0, "prot": None, "ext": None, "brk": None, "hl": None, "post": None, "since": 0}

    def ev(k, name, **kw):
        out["events"].append({"ts": pd.Timestamp(ts.iloc[k]), "event": name, **kw})

    def advance(upto):
        """bars ≤ upto पर्यंत: protected चा real break, आणि (HL/LH झाला असेल तर) पुष्टीचा close."""
        d = st["d"]
        if not d or st["prot"] is None:
            return
        if st["brk"] is None:
            b = BR.first_real_break(fr, max(st["prot"]["idx"] + 1, st["since"]), st["prot"]["price"], "above" if d < 0 else "below", es,
                                    mr=mr, end=upto)
            if b is not None:
                st["brk"] = b
                ev(b, "REAL_BREAK", dir=d, protected=st["prot"]["price"])
        if st["brk"] is not None and st["ext"] is not None:
            # A1 (Abhi K-10): testing मध्ये जुन्या trend टोकापलीकडे close ⇒ break failed ⇒ जुना trend तात्काळ परत (pivot confirm ची वाट नाही)
            b0 = st["brk"]
            seg = c[b0 + 1:upto + 1]
            fail = np.nonzero(seg > st["ext"])[0] if d > 0 else np.nonzero(seg < st["ext"])[0]
            rev = None
            if st["hl"] is not None and st["hl"]["conf"] <= upto:
                a0 = st["hl"]["conf"] + 1
                hit0 = np.nonzero(c[a0:upto + 1] > st["post"])[0] if d < 0 else np.nonzero(c[a0:upto + 1] < st["post"])[0]
                rev = a0 + int(hit0[0]) if len(hit0) else None
            if len(fail) and (rev is None or b0 + 1 + int(fail[0]) < rev):
                f = b0 + 1 + int(fail[0])
                j = b0 + int(np.argmin(lo[b0:f + 1])) if d > 0 else b0 + int(np.argmax(h[b0:f + 1]))
                prot = {"idx": j, "price": float(lo[j] if d > 0 else h[j]), "kind": "L" if d > 0 else "H", "ts": pd.Timestamp(ts.iloc[j]),
                        "conf": f}
                new_ext = float(h[b0:f + 1].max()) if d > 0 else float(lo[b0:f + 1].min())
                ev(f, "BREAK_FAILED", dir=d, protected=prot["price"], old_extreme=st["ext"])
                st.update(prot=prot, ext=max(new_ext, st["ext"]) if d > 0 else min(new_ext, st["ext"]), brk=None, hl=None, post=None,
                          since=f + 1)
                advance(upto)                                            # नव्या protected चा break याच टप्प्यात?
                return
        if st["hl"] is not None and st["hl"]["conf"] <= upto:
            a = st["hl"]["conf"] + 1
            seg = c[a:upto + 1]
            hit = np.nonzero(seg > st["post"])[0] if d < 0 else np.nonzero(seg < st["post"])[0]
            bad = np.nonzero(seg < st["hl"]["price"])[0] if d < 0 else np.nonzero(seg > st["hl"]["price"])[0]
            if len(bad) and (not len(hit) or bad[0] < hit[0]):               # पुष्टीआधी HL (LH) च्या पलीकडे close ⇒ तो HL रद्द
                st.update(hl=None, post=None)
                return
            if len(hit):
                k = a + int(hit[0])
                b0 = st["brk"]
                new_ext = float(h[b0:k + 1].max()) if d < 0 else float(lo[b0:k + 1].min())
                ev(k, "REVERSAL_CONFIRMED", dir=-d, protected=st["hl"]["price"])
                st.update(d=-d, prot=st["hl"], ext=new_ext, brk=None, hl=None, post=None, since=k + 1)

    for i, p in enumerate(pv):
        prev_opp = next((q for q in reversed(pv[:i]) if q["kind"] != p["kind"]), None)
        if st["d"] == 0:
            if p["label"] == "LL" and prev_opp is not None and prev_opp["label"] == "LH":
                st.update(d=-1, prot=prev_opp, ext=p["price"])
            elif p["label"] == "HH" and prev_opp is not None and prev_opp["label"] == "HL":
                st.update(d=1, prot=prev_opp, ext=p["price"])
            if st["d"]:
                out["events"].append({"ts": p["ts"], "event": "TREND", "dir": st["d"], "protected": st["prot"]["price"]})
            continue
        advance(p["conf"])
        d = st["d"]
        ext_kind = "L" if d < 0 else "H"
        if p["kind"] == ext_kind and (p["price"] - st["ext"]) * d > 0:      # नवं टोक ⇒ BOS (break असेल तर फसला)
            st.update(ext=p["price"], prot=prev_opp, brk=None, hl=None, post=None)
            out["events"].append({"ts": p["ts"], "event": "BOS", "dir": d, "protected": prev_opp["price"] if prev_opp else None})
            continue
        if st["brk"] is not None and st["hl"] is None and p["kind"] == ext_kind and p["idx"] > st["brk"]:
            b0 = st["brk"]
            post = float(h[b0:p["idx"] + 1].max()) if d < 0 else float(lo[b0:p["idx"] + 1].min())
            st.update(hl=p, post=post)                                   # HL (downtrend उलटताना) — आता post-break high वर close हवा
    advance(len(fr) - 1)
    d, prot, brk = st["d"], st["prot"], st["brk"]
    out["dir"] = d
    out["state"] = "range" if d == 0 else ("testing" if brk is not None else "trend")
    out["protected"] = None if prot is None else {"price": round(prot["price"], 2), "ts": prot["ts"], "kind": prot["kind"]}
    out["break_ts"] = None if brk is None else pd.Timestamp(ts.iloc[brk])
    out["extreme"] = None if st["ext"] is None else round(float(st["ext"]), 2)
    return out


# ---------------------------------------------------------------------------------------------------------------- F3 legs
def _mr_at(mr, i):
    v = mr[min(max(i, 0), len(mr) - 1)] if len(mr) else np.nan
    return float(v) if np.isfinite(v) else float("nan")


def overlap_ratio(fr, a, b):
    """K10.1: [a, b] मधल्या bars पैकी मागच्या bar शी > 50% (स्वतःच्या range च्या) overlap असलेल्यांचं प्रमाण."""
    h, lo = fr["high"].to_numpy(float)[a:b + 1], fr["low"].to_numpy(float)[a:b + 1]
    if len(h) < 2:
        return None
    rng = np.maximum(h - lo, 1e-9)
    ov = np.maximum(0.0, np.minimum(h[1:], h[:-1]) - np.maximum(lo[1:], lo[:-1])) / rng[1:]
    return round(float((ov > 0.5).mean()), 3)


def efficiency(fr, a, b):
    c = fr["close"].to_numpy(float)[a:b + 1]
    path = float(np.abs(np.diff(c)).sum())
    return round(abs(c[-1] - c[0]) / path, 3) if path > 0 else 0.0


def leg_metrics(fr, pvs, i, mr, s):
    """pvs[i] → pvs[i+1] leg चे F3 गुण: size_mr, disp, er, overlap, bos (level | None), impulse (bool)."""
    a, b = pvs[i], pvs[i + 1]
    ia, ib = a["idx"], b["idx"]
    dirn = 1 if b["price"] > a["price"] else -1
    m = _mr_at(mr, ib)
    o, h, lo, c = (fr[x].to_numpy(float)[ia + 1:ib + 1] for x in ("open", "high", "low", "close"))
    mm = mr[ia + 1:ib + 1]
    body, rng = np.abs(c - o), np.maximum(h - lo, 1e-9)
    disp = int(((body >= s["disp_body_mr"] * mm) & (body / rng >= s["disp_body_frac"]) & ((c - o) * dirn > 0)).sum()) if len(c) else 0
    same = [q for q in pvs[:i] if q["kind"] == b["kind"]]
    bos = None
    if same and len(c):
        lvl = same[-1]["price"]
        if ((c > lvl) if dirn > 0 else (c < lvl)).any():
            bos = lvl
    er, ov = efficiency(fr, ia, ib), overlap_ratio(fr, ia, ib)
    size = abs(b["price"] - a["price"]) / m if np.isfinite(m) and m > 0 else 0.0
    low_overlap = er >= s["impulse_er_min"] or (ov is not None and ov < s["impulse_overlap_max"])
    imp = bool(size >= s["impulse_min_mr"] and disp >= s["impulse_disp_min"] and low_overlap and bos is not None)
    return {"dir": dirn, "from": round(a["price"], 2), "to": round(b["price"], 2), "from_ts": a["ts"], "to_ts": b["ts"],
            "start_idx": ia, "end_idx": ib, "bars": ib - ia, "size_mr": round(size, 2), "disp": disp, "er": er, "overlap": ov,
            "bos": None if bos is None else round(bos, 2), "low_overlap": bool(low_overlap), "impulse": imp}


def impulse(fr, pvs, trend_dir, mr, s):
    """F3: trend दिशेचा (trend 0 ⇒ कुठलीही) सगळ्यात ताजा पात्र impulse leg; त्यानंतर त्याच दिशेने नवं टोक ⇒ टोक वाढवा."""
    best = None
    for i in range(len(pvs) - 1):
        lm = leg_metrics(fr, pvs, i, mr, s)
        if lm["impulse"] and (trend_dir == 0 or lm["dir"] == trend_dir):
            best = (i, lm)
    if best is None:
        return None
    i, lm = best
    for q in pvs[i + 2:]:                                                # नंतर impulse दिशेने नवं टोक ⇒ impulse चालूच
        if q["kind"] == pvs[i + 1]["kind"] and (q["price"] - lm["to"]) * lm["dir"] > 0:
            ob = _real_break(fr, lm["end_idx"] + 1, lm["from"], "below" if lm["dir"] > 0 else "above", _es(), mr)
            if ob is not None and ob < q["idx"]:
                break                                                    # मधे origin चा real break ⇒ हा वेगळा leg, विस्तार नाही
            lm.update(to=round(q["price"], 2), to_ts=q["ts"], end_idx=q["idx"], bars=q["idx"] - lm["start_idx"], extended=True)
    return lm


def correction(fr, pvs, imp, mr, s, es):
    """Impulse टोकानंतरची चाल (F3): labels A/B/C, retrace, overlapping, origin real break."""
    e = imp["end_idx"]
    d = imp["dir"]
    after = [p for p in pvs if p["idx"] > e]
    pts = [{"idx": e, "price": imp["to"], "kind": "H" if d > 0 else "L", "ts": imp["to_ts"]}] + after
    h, lo = fr["high"].to_numpy(float), fr["low"].to_numpy(float)
    out = {"labels": [], "retrace": None, "extreme": None, "extreme_ts": None, "overlapping": False, "overlap": None,
           "origin_broken": False, "origin_break_ts": None, "status": "none", "legs": len(pts) - 1}
    if e + 1 >= len(fr):
        out["status"] = "not_started"
        return out
    seg = slice(e + 1, len(fr))
    j = e + 1 + (int(np.argmax(h[seg])) if d < 0 else int(np.argmin(lo[seg])))
    ext = float(h[j] if d < 0 else lo[j])
    size = abs(imp["to"] - imp["from"])
    out.update(extreme=round(ext, 2), extreme_ts=pd.Timestamp(fr["timestamp"].iloc[j]),
               retrace=round(abs(ext - imp["to"]) / size, 3) if size > 0 else None)
    b = _real_break(fr, e + 1, imp["from"], "below" if d > 0 else "above", es, mr)
    if b is not None:
        out.update(origin_broken=True, origin_break_ts=pd.Timestamp(fr["timestamp"].iloc[b]))
    # labels (trade-degree pivots): A, B, मग C = B नंतरचं counter टोक
    names = []
    if len(pts) >= 2:
        names.append(("A", pts[0], pts[1]))
    if len(pts) >= 3:
        names.append(("B", pts[1], pts[2]))
    if len(pts) >= 3:
        cseg = slice(pts[2]["idx"] + 1, len(fr))
        if pts[2]["idx"] + 1 < len(fr):
            k = pts[2]["idx"] + 1 + (int(np.argmax(h[cseg])) if d < 0 else int(np.argmin(lo[cseg])))
            cpx = float(h[k] if d < 0 else lo[k])
            if (cpx - pts[2]["price"]) * (-d) > 0:
                names.append(("C", pts[2], {"idx": k, "price": cpx, "ts": pd.Timestamp(fr["timestamp"].iloc[k])}))
    tent = None
    if len(pts) == 1:                                                    # अजून confirmed counter pivot नाही ⇒ A चालू (tentative)
        names.append(("A", pts[0], {"idx": j, "price": ext, "ts": out["extreme_ts"]}))
        tent = "A"
    elif len(pts) == 2 and pts[1]["idx"] + 1 < len(fr):                  # A confirmed ⇒ B चालू (A टोकानंतरचं impulse-दिशेचं टोक)
        bseg = slice(pts[1]["idx"] + 1, len(fr))
        k = pts[1]["idx"] + 1 + (int(np.argmin(lo[bseg])) if d < 0 else int(np.argmax(h[bseg])))
        bpx = float(lo[k] if d < 0 else h[k])
        if (bpx - pts[1]["price"]) * d > 0:
            names.append(("B", pts[1], {"idx": k, "price": bpx, "ts": pd.Timestamp(fr["timestamp"].iloc[k])}))
            tent = "B"
    if len(pts) >= 3 and pts[-1]["idx"] <= pts[2]["idx"]:
        tent = "C"                                                       # C चं टोक अजून confirmed pivot नाही
    out["labels"] = [{"label": n, "from": round(a["price"], 2), "to": round(z["price"], 2), "from_ts": a["ts"], "to_ts": z["ts"],
                      "tentative": n == tent} for n, a, z in names]
    ov = overlap_ratio(fr, e + 1, len(fr) - 1)
    out["overlap"] = ov
    out["overlapping"] = bool(len(pts) >= 3 or (ov is not None and ov >= s["correction_overlap_min"]))
    r = out["retrace"] or 0.0
    if out["origin_broken"]:
        out["status"] = "origin_broken"
    elif r < s["retrace_lo"]:
        out["status"] = "shallow"
    elif r <= s["retrace_hi"] and out["overlapping"]:
        out["status"] = "correction"
    else:
        out["status"] = "unclear"                                       # overlapping नाही (एक सरळ counter leg) — अजून A
    return out


# ---------------------------------------------------------------------------------------------------------------- F4
def structure_state(fr, tf):
    """opportunity_engine/structure.py::StructureTracker (HTF) — शेवटची state."""
    from opportunity_engine.structure import StructureTracker
    tr = StructureTracker(tf)
    for r in fr.itertuples(index=False):
        tr.on_bar(pd.Timestamp(r.bar_end), r.open, r.high, r.low, r.close)
    return tr.state, tr.protected_level()


def _state_dir(state):
    if state in ("UPTREND", "UPTREND_PULLBACK"):
        return 1, False
    if state in ("DOWNTREND", "DOWNTREND_PULLBACK"):
        return -1, False
    if state == "UPTREND_WEAK":
        return 1, True
    if state == "DOWNTREND_WEAK":
        return -1, True
    return 0, False


def elliott_vote(df1m, asof, degrees, es=None):
    """Elliott count engine चा vote (trade degrees): {degree: {"up", "down", "gray", "dir"}}. अपयश ⇒ {} (मत नाही)."""
    es = es or _es()
    try:
        from elliott.counts import CountEngine
        md = W.multi_degree(df1m, es, now=asof)
        snap = CountEngine(md, es).snapshot(asof)
    except Exception as exc:                                             # Elliott अपयश ⇒ मत नाही, पण कारण नोंदवा (गुपचूप नाही)
        return {"error": f"{type(exc).__name__}: {str(exc)[:120]}"}
    out = {}
    for d in degrees:
        v = snap.degrees.get(d)
        if v is None:
            continue
        up = float(v.vote_up) if np.isfinite(v.vote_up) else None
        dn = float(v.vote_down) if np.isfinite(v.vote_down) else None
        dr = 0 if v.gray or up is None else (1 if up > (dn or 0) else -1)
        out[d] = {"up": None if up is None else round(up, 3), "down": None if dn is None else round(dn, 3), "gray": bool(v.gray), "dir": dr}
    return out


def decide_side(tr, imp, corr, st_state, ew):
    """F4: (side, reasons). side = "bull_put" / "bear_call" / "unclear"."""
    reasons = []
    if imp is None:
        return "unclear", ["trade-degree impulse नाही (F3: displacement + कमी overlap + BOS)"]
    d = imp["dir"]
    if corr is not None and corr["status"] == "origin_broken":
        reasons.append(f"impulse origin {imp['from']:,.1f} चा real break ⇒ pullback नाही")
    if tr["dir"] == -d:
        reasons.append(f"HTF trend {'up' if tr['dir'] > 0 else 'down'} impulse विरुद्ध")
    if tr["state"] == "testing" and tr["dir"] == d:
        reasons.append(f"HTF protected {tr['protected']['price']:,.1f} चा real break झाला, HL/LH पुष्टी बाकी ⇒ trend तपासणीत")
    sd, weak = _state_dir(st_state)
    if sd == -d and not weak:
        reasons.append(f"HTF structure state {st_state} विरुद्ध")
    opp = [k for k, v in (ew or {}).items() if k != "error" and v["dir"] == -d]
    if opp:
        reasons.append("Elliott vote विरुद्ध (D" + ", D".join(map(str, opp)) + ")")
    return ("unclear", reasons) if reasons else (SIDE[d], [])


# ---------------------------------------------------------------------------------------------------------------- read
def full_frames(df1m, s=None):
    """Backtest / scan साठी: संपूर्ण data चे trend_tf आणि trade_tf frames एकदाच (read(frames=…) मध्ये asof ने कापले जातात)."""
    s = {**DEFAULTS, **(s or {})}
    end = pd.to_datetime(df1m["timestamp"]).max() + pd.Timedelta(minutes=1)
    return {tf: frame(df1m, tf, end) for tf in {s["trend_tf"], s["trade_tf"]}}


def _slice(fr, t0, asof):
    return fr[(fr["timestamp"] >= t0) & (fr["bar_end"] <= asof)].reset_index(drop=True)


def _internal(fr, a, b, atr_mult):
    """[a, b] मधले आतले swings (ATR × atr_mult, confirmed, b पर्यंतच्या bars वर) ⇒ [(idx, price, kind)]."""
    sub = fr.iloc[: b + 1].reset_index(drop=True)
    return [(p["idx"], p["price"], p["kind"]) for p in pivots(sub, atr_mult) if a < p["idx"] < b]


def counter_score(fr, e, x, imp, mr, s, ep=None):
    """Counter-move (impulse टोक e ⇒ counter टोक x) impulsive आहे का — Abhi चे 5 निकष, ≥ reversal_min_criteria ⇒ impulsive:
    (1) 5 legs किंवा कमी overlap, (2) displacement candles, (3) गती मागच्या impulse पेक्षा जास्त, (4) impulse ची सुरुवात close ने तुटली,
    (5) वाटेत उथळ pauses (आतले pullbacks ≤ 38.2%). रिटर्न (count, {निकष: bool}). Corrective (3 legs, overlap, संथ) ⇒ कमी count."""
    d = -int(imp["dir"])                                                   # counter दिशा
    o, h, lo, c = (fr[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    mm = mr[e + 1:x + 1] if len(mr) else np.array([])
    body, rng = np.abs(c[e + 1:x + 1] - o[e + 1:x + 1]), np.maximum(h[e + 1:x + 1] - lo[e + 1:x + 1], 1e-9)
    disp = int(((body >= s["disp_body_mr"] * mm) & (body / rng >= s["disp_body_frac"]) & ((c[e + 1:x + 1] - o[e + 1:x + 1]) * d > 0)).sum()) \
        if len(mm) == len(body) else 0
    inner = _internal(fr, e, x, s["reversal_internal_atr"])
    legs = len(inner) + 1
    ov = overlap_ratio(fr, e + 1, x)
    xp = float(h[x] if d > 0 else lo[x])
    ep = float(imp["to"]) if ep is None else float(ep)
    speed_c = abs(xp - ep) / max(x - e, 1)
    speed_i = abs(float(imp["to"]) - float(imp["from"])) / max(int(imp["end_idx"]) - int(imp["start_idx"]), 1)
    seg = c[e + 1:x + 1]
    origin = bool(((seg > float(imp["from"])) if d > 0 else (seg < float(imp["from"]))).any())
    pulls = []
    for i in range(1, len(inner)):
        a, b = inner[i - 1], inner[i]
        prev = inner[i - 2][1] if i >= 2 else ep
        if (b[1] - a[1]) * d < 0:                                          # counter विरुद्ध pullback
            up = abs(a[1] - prev)
            pulls.append(abs(a[1] - b[1]) / up if up > 0 else 1.0)
    er = efficiency(fr, e, x)                                              # F3 "कमी overlap" = ER ≥ impulse_er_min किंवा K10.1 overlap कमी
    crit = {"legs5_or_low_overlap": bool(legs >= 5 or er >= s["impulse_er_min"] or (ov is not None and ov < s["impulse_overlap_max"])),
            "displacement": bool(disp >= s["impulse_disp_min"]),
            "faster_than_impulse": bool(speed_c > speed_i),
            "impulse_origin_broken": origin,
            "shallow_pauses": bool(pulls and all(p <= s["retrace_lo"] for p in pulls))}      # pause नसेल ⇒ हा निकष नाही (दुहेरी गुण नको)
    return sum(crit.values()), crit


def _reversal_state(fr, pv, imp, e, ep, x, mr, s):
    """Counter leg (e: सुरुवात index, ep: सुरुवातीचा भाव ⇒ x: counter टोक) impulsive असेल तर रचनेने स्थिती: active / cancelled / new_trend."""
    d = -int(imp["dir"])
    n, crit = counter_score(fr, e, x, imp, mr, s, ep)
    if n < int(s["reversal_min_criteria"]):
        return None
    c = fr["close"].to_numpy(float)
    after = c[x + 1:]
    out = {"dir": d, "score": n, "criteria": crit, "x_idx": x, "start_idx": e, "start": round(float(ep), 2), "state": "active"}
    if len(after) and (((after < ep) if d > 0 else (after > ep)).any()):
        out.update(state="cancelled", why=f"(a) counter-move ची सुरुवात {ep:,.1f} close ने पुन्हा ⇒ जुना trend")
        return out
    inner = [p for p in _internal(fr, e, x, s["reversal_internal_atr"]) if p[2] == ("L" if d > 0 else "H")]
    if inner and len(after):
        lvl = float(inner[-1][1])
        hit = np.nonzero((after < lvl) if d > 0 else (after > lvl))[0]
        if len(hit):
            b = x + 1 + int(hit[0])
            er, ov = efficiency(fr, x, b), overlap_ratio(fr, x, b)
            o = fr["open"].to_numpy(float)
            bd = (c[x + 1:b + 1] - o[x + 1:b + 1]) * (-d)                 # जुन्या trend दिशेचे bodies
            disp = int((bd >= s["disp_body_mr"] * mr[x + 1:b + 1]).sum()) if len(mr) > b else 0
            if disp >= s["impulse_disp_min"] or er >= s["impulse_er_min"] or (ov is not None and ov < s["impulse_overlap_max"]):
                out.update(state="cancelled", why=f"(b) शेवटचा आतला swing {lvl:,.1f} impulsive leg ने तुटला ⇒ जुना trend")
                return out
    conf = [p for p in pv if p["idx"] > x and p["kind"] == ("L" if d > 0 else "H") and (p["price"] - ep) * d > 0]
    if conf:
        out.update(state="new_trend", why=f"(c) नव्या दिशेत {'HL' if d > 0 else 'LH'} {conf[-1]['price']:,.1f} confirm ⇒ नवीन trend "
                                          "(wave (2) setup ची वाट)")
    return out


def possible_reversal(fr, pv, imp, corr, mr, s, tr=None):
    """POSSIBLE_REVERSAL (Abhi 2026-10-08, v2): impulse नंतरची counter-move impulse च्या ≥ reversal_retrace_min (38.2%) खोल **आणि**
    impulsive (counter_score ≥ reversal_min_criteria). HTF protected तोडणारी counter-move ⇒ trend / testing प्रश्न ⇒ इथे नाही.
    दोन counter legs तपासतो: (i) impulse टोक ⇒ correction टोक (पूर्ण counter-move); (ii) (i) नसेल / रद्द झाली असेल तर ताजा leg —
    impulse दिशेचा शेवटचा confirmed swing ⇒ त्यानंतरचं टोक (उदा. 11 Aug: 10 Aug high ⇒ 11 Aug घसरण, impulse च्या 58%).
    Flag चा शेवट फक्त रचनेने: (a) leg ची सुरुवात close ने पुन्हा ⇒ cancelled; (b) leg मधला शेवटचा आतला swing impulsive leg ने तुटला ⇒
    cancelled; (c) नव्या दिशेत HL / LH confirm ⇒ new_trend (wave (2) setup). 61.8% परत गेल्याने flag संपत नाही (wave (2)).
    रिटर्न {"state", "dir", retrace, score, criteria, reason, start, x_idx} किंवा None."""
    if not imp or not corr or corr.get("extreme_ts") is None:
        return None
    d = -int(imp["dir"])
    size = abs(float(imp["to"]) - float(imp["from"]))
    prot = ((tr or {}).get("protected") or {}).get("price")
    if size <= 0 or (tr or {}).get("state") == "testing":
        return None
    ts = pd.to_datetime(fr["timestamp"])
    h, lo = fr["high"].to_numpy(float), fr["low"].to_numpy(float)
    e = int(imp["end_idx"])
    cands = []
    x = int(np.searchsorted(ts.to_numpy(), np.datetime64(pd.Timestamp(corr["extreme_ts"]))))
    if e + 1 < x < len(fr):
        cands.append((e, float(imp["to"]), x))
    ends = [p for p in pv if p["idx"] > e and p["kind"] == ("H" if d < 0 else "L")]           # impulse दिशेचे swings (counter ची सुरुवात)
    if ends:
        p = ends[-1]
        if p["idx"] + 1 < len(fr):
            seg = slice(p["idx"] + 1, len(fr))
            x2 = p["idx"] + 1 + (int(np.argmax(h[seg])) if d > 0 else int(np.argmin(lo[seg])))
            if x2 > p["idx"] + 1:
                cands.append((p["idx"], float(p["price"]), x2))
    best = None
    full_checked = False
    for i, (a, ap, xx) in enumerate(cands):
        if i > 0 and full_checked and (best is None or best["state"] != "cancelled"):
            break                                                          # ताजा leg फक्त पूर्ण counter-move रद्द झाल्यावर (C leg ≠ reversal)
        xp = float(h[xx] if d > 0 else lo[xx])
        depth = abs(float(imp["to"]) - xp) / size
        if depth < s["reversal_retrace_min"]:
            continue
        cl = fr["close"].to_numpy(float)[a + 1:xx + 1]
        if prot is not None and int((tr or {}).get("dir") or 0) == -d and len(cl) and ((cl - float(prot)) * d > 0).any():
            continue                                                       # protected close ने तुटला ⇒ market_state trend / testing प्रश्न
        st = _reversal_state(fr, pv, imp, a, ap, xx, mr, s)
        full_checked = full_checked or a == e
        if st is None:
            continue
        st["retrace"] = round(depth, 3)
        st["leg"] = "full" if i == 0 and a == e else "latest"
        best = st
        if st["state"] != "cancelled":
            break
    if best is None:
        return None
    names = [k for k, v in best["criteria"].items() if v]
    best["reason"] = (f"POSSIBLE_REVERSAL ({best['state']}): counter-move {best['retrace']:.0%} ({best['leg']} leg, {best['start']:,.1f} पासून), "
                      f"impulsive {best['score']}/5 ({', '.join(names)})"
                      + (f" · {best['why']}" if best.get("why") else " ⇒ जुन्या trend दिशेने trade नाही"))
    return best


def read(df1m, asof, s=None, es=None, run_elliott=True, frames=None):
    """Market state at `asof` (फक्त bar_end ≤ asof चे बंद bars). JSON-able dict.
    frames = full_frames(df1m) (ऐच्छिक, scan वेगवान): तेच bars asof ने कापून — df1m वरून काढल्यासारखंच उत्तर (test)."""
    s = {**DEFAULTS, **(s or {})}
    es = es or _es()
    asof = pd.Timestamp(asof)
    t0 = asof - pd.Timedelta(days=int(s["htf_days"]))
    t1 = asof - pd.Timedelta(days=int(s["trade_days"]))
    d1 = None
    if frames is None or run_elliott:
        d1 = df1m[(pd.to_datetime(df1m["timestamp"]) >= t0.normalize()) & (pd.to_datetime(df1m["timestamp"]) + pd.Timedelta(minutes=1) <= asof)]
        d1 = d1.reset_index(drop=True)
    if frames is not None:
        htf, trade = _slice(frames[s["trend_tf"]], t0.normalize(), asof), _slice(frames[s["trade_tf"]], t1.normalize(), asof)
    else:
        htf = frame(d1, s["trend_tf"], asof)
        trade = frame(d1[pd.to_datetime(d1["timestamp"]) >= t1.normalize()], s["trade_tf"], asof)
    tr = trend(htf, s, es)
    st_state, st_prot = structure_state(htf, s["trend_tf"]) if len(htf) else ("INIT", None)
    mr = BR.median_range(trade, 20) if len(trade) else np.array([])
    pv = label(pivots(trade, s["trade_swing_atr_mult"], s["trade_tf"]))
    tent = _tentative(trade, pv)
    pv_t = pv + ([tent] if tent else [])
    imp = impulse(trade, pv_t, tr["dir"], mr, s) if len(pv_t) >= 2 else None
    corr = correction(trade, pv, imp, mr, s, es) if imp else None
    ew = elliott_vote(d1, asof, s["elliott_degrees"], es) if (run_elliott and imp) else {}
    rev = possible_reversal(trade, pv, imp, corr, mr, s, tr)
    side, why = decide_side(tr, imp, corr, st_state, ew)
    if rev and rev["state"] in ("active", "new_trend"):
        side, why = "unclear", why + [rev["reason"]]
    mr_now = float(np.median((trade["high"] - trade["low"]).to_numpy(float)[-20:])) if len(trade) else float("nan")
    out = {"asof": asof, "tf": {"trend": s["trend_tf"], "trade": s["trade_tf"]}, "mr": round(mr_now, 2) if np.isfinite(mr_now) else None,
           "trend": {k: v for k, v in tr.items() if k != "swings"}, "trend_swings": tr["swings"][-8:],
           "structure_state": st_state, "structure_protected": st_prot,
           "impulse": imp, "correction": corr, "elliott": ew, "side": side, "side_reasons": why, "possible_reversal": rev,
           "swings": pv[-12:], "tentative": tent}
    out["lines"] = lines(out)
    return out


def lines(ms):
    """गोष्टीच्या ओळी (KB K1/K2/K3 संदर्भ)."""
    tr, imp, corr = ms["trend"], ms["impulse"], ms["correction"]
    dn = {1: "up", -1: "down", 0: "range"}
    p = tr.get("protected")
    L = [f"[K1] HTF ({ms['tf']['trend']}) trend {dn[tr['dir']]}" + (f" · protected {p['kind']} {p['price']:,.1f} ({p['ts']:%d %b %H:%M})" if p else "")
         + (" · real break झाला, पुष्टी बाकी" if tr["state"] == "testing" else "") + f" · structure state {ms['structure_state']}"]
    if imp:
        L.append(f"[K2] impulse {dn[imp['dir']]} {imp['from']:,.1f} → {imp['to']:,.1f} ({imp['size_mr']}× MR, {imp['bars']} bars, "
                 f"displacement {imp['disp']}, ER {imp['er']}, overlap {imp['overlap']}, BOS {imp['bos']:,.1f})")
    else:
        L.append("[K2] trade-degree impulse नाही")
    if corr:
        lab = " · ".join(f"{x['label']} {x['from']:,.1f}→{x['to']:,.1f}" for x in corr["labels"]) or "—"
        L.append(f"[K2/K3] correction {corr['status']}: {lab} · retrace {corr['retrace']:.0%}" if corr["retrace"] is not None
                 else f"[K2/K3] correction {corr['status']}")
    if ms["elliott"].get("error"):
        L.append(f"[K3] Elliott vote: गणना अपयशी ({ms['elliott']['error']}) ⇒ F4 मध्ये मत नाही")
    elif ms["elliott"]:
        L.append("[K3] Elliott vote: " + ", ".join(f"D{k} {'gray' if v['gray'] else ('up' if v['dir'] > 0 else 'down')}"
                                                   for k, v in ms["elliott"].items()))
    L.append(f"[F4] side {ms['side']}" + (" — " + "; ".join(ms["side_reasons"]) if ms["side_reasons"] else ""))
    return L
