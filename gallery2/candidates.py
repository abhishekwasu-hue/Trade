"""gallery2/candidates.py — 40 candidate charts (spec §5) आणि 28 dev / 12 test split. **reader2 / decision3 / trade निकाल वापरत नाही.**

निवड नियम (manifest मध्ये शब्दशः नोंद):
  1. Abhi चे आधीचे marked charts (`data/abhi_cases.json`) आधी — नेहमी dev, `calibration: false` (logic त्यांच्यावरच ठरलं ⇒
     regression only; NIFTY चा case CONTAMINATED काळ).
  2. बाकी प्रत्येक (symbol, TF) साठी: उपलब्ध data वर न चढणाऱ्या, ठराविक लांबीच्या windows ची grid (`WINDOW_BARS`; intraday window session सुरुवातीपासून), policy-बाहेरचे
     आणि Abhi cases वर चढणारे वगळून. NIFTY auto windows फक्त IS (2015–2021): VAL स्वतंत्र चाचणीसाठी जपला (research/golden_gallery
     सारखा), holdout / illustration कधीच नाही. BANKNIFTY ⇒ NIFTY holdout च्या तारखा नाहीत.
  3. प्रत्येक window ला **फक्त किंमतीवरून** वर्णनात्मक tags (`shape`): दिशा up / down / range (net ÷ span), साध्या zigzag (3 × median
     range) वरून सर्वात खोल counter-move deep (≥ 0.618) / shallow (≤ 0.382), flat_ext (b ≥ 0.9 a, c a च्या टोकापलीकडे), impulse
     (दिशा + ER ≥ 0.25 + खोली ≤ 0.5). हे label नाहीत — फक्त विविधता मिळवण्यासाठी (आकडे निकाल पाहून ठरवलेले नाहीत).
  4. Slot quota (`QUOTAS`) पर्यंत seeded RNG ने buckets (impulse, flat_ext, deep, shallow, down, up, range) आळीपाळीने — प्रत्येक
     bucket मधून एक. Data नसलेल्या slot चा (उदा. SENSEX) वाटा उरलेल्या slots ना आळीपाळीने (window संख्येच्या मर्यादेत).
Split: Abhi cases dev; बाकीच्यांमधून 12 test — (symbol, TF) slot च्या आकाराच्या प्रमाणात (largest remainder), slot मध्ये seeded निवड.
एकाच symbol + TF चे windows एकमेकांवर चढत नाहीत (grid) ⇒ test chart चे bars कोणत्याही dev chart मध्ये त्याच TF वर नाहीत.
"""
import json
import math
import os

import numpy as np
import pandas as pd

from . import data as GD
from . import schema as SC

HERE = os.path.dirname(os.path.abspath(__file__))
CASES = os.path.join(HERE, "data", "abhi_cases.json")
WINDOW_BARS = {"D": 160, "1H": 140, "15M": 150}
QUOTAS = {("NIFTY", "D"): 5, ("NIFTY", "1H"): 4, ("NIFTY", "15M"): 5,          # बेरीज 40 (Abhi cases सकट); data नसलेल्या
          ("BANKNIFTY", "D"): 5, ("BANKNIFTY", "1H"): 3, ("BANKNIFTY", "15M"): 5,  # slot चा वाटा उरलेल्या slots ना आळीपाळीने
          ("SENSEX", "D"): 5, ("SENSEX", "1H"): 4, ("SENSEX", "15M"): 4}
BUCKETS = ("impulse", "flat_ext", "deep", "shallow", "down", "up", "range")
ZZ_K, FLAT_K, DIR_FRAC, DEEP, SHALLOW, IMP_FRAC, IMP_DEPTH, FLAT_B, FLAT_C = 3.0, 6.0, 0.4, 0.618, 0.382, 0.7, 0.5, 0.9, 1.2
N_TOTAL, N_TEST, SEED = 40, 12, 7
ORDER_S = {s: i for i, s in enumerate(GD.SYMBOLS)}
ORDER_T = {t: i for i, t in enumerate(GD.TIMEFRAMES)}


# ---------------------------------------------------------------------------------------------------------------- shape tags
def zigzag(h, lo, thr):
    """साधा directional-change zigzag (thr = किंमत अंतर) ⇒ [(bar, price, "H" | "L")], शेवटचा टोक तात्पुरता."""
    n = len(h)
    if n < 2 or thr <= 0:
        return []
    piv, dirn, hi_i, lo_i, ext = [], 0, 0, 0, 0
    for i in range(1, n):
        if dirn == 0:
            hi_i = i if h[i] > h[hi_i] else hi_i
            lo_i = i if lo[i] < lo[lo_i] else lo_i
            if h[hi_i] - lo[lo_i] >= thr:
                if hi_i > lo_i:
                    piv, dirn, ext = [(lo_i, lo[lo_i], "L")], 1, hi_i
                else:
                    piv, dirn, ext = [(hi_i, h[hi_i], "H")], -1, lo_i
        elif dirn == 1:
            if h[i] >= h[ext]:
                ext = i
            elif h[ext] - lo[i] >= thr:
                piv.append((ext, h[ext], "H"))
                dirn, ext = -1, i
        else:
            if lo[i] <= lo[ext]:
                ext = i
            elif h[i] - lo[ext] >= thr:
                piv.append((ext, lo[ext], "L"))
                dirn, ext = 1, i
    if dirn:
        piv.append((ext, h[ext] if dirn == 1 else lo[ext], "H" if dirn == 1 else "L"))
    return piv


def shape(bars):
    """Window चे वर्णनात्मक आकडे + tags (फक्त OHLC; median-range units / ratios — label नाहीत).
    depth = मुख्य चालीतल्या (window चा टोकाचा low ⇒ high, किंवा उलट) सर्वात मोठ्या counter-swing चा, त्या क्षणापर्यंतच्या चालीशी
    retracement (चालीचा ≥ 1/3 भाग झाल्यावरच मोजतो). flat_ext = मोठ्या zigzag (`FLAT_K` × MR) वर a, b, c: b ≥ 0.9 a आणि c ≥ 1.2 a
    (c, a च्या टोकापलीकडे)."""
    h, lo = bars["high"].to_numpy(float), bars["low"].to_numpy(float)
    o, c = bars["open"].to_numpy(float), bars["close"].to_numpy(float)
    mr = SC.median_range(bars)
    span = float(h.max() - lo.min()) if len(h) else 0.0
    frac = float((c[-1] - o[0]) / span) if span > 0 else 0.0
    path = float(np.abs(np.diff(c)).sum())
    er = float(abs(c[-1] - c[0]) / path) if path > 0 else 0.0
    regime = "up" if frac >= DIR_FRAC else ("down" if frac <= -DIR_FRAC else "range")
    piv = zigzag(h, lo, ZZ_K * mr)
    depth = None
    if regime != "range":
        d = 1 if regime == "up" else -1
        i0, i1 = (int(lo.argmin()), int(h.argmax())) if d > 0 else (int(h.argmax()), int(lo.argmin()))
        p0, move = (lo[i0] if d > 0 else h[i0]), span
        inner = [p for p in piv if i0 <= p[0] <= i1]
        ratios = []
        for k in range(1, len(inner) - 1):
            ext, back = inner[k], inner[k + 1]
            so_far = (ext[1] - p0) * d
            if so_far >= move / 3 and (back[1] - ext[1]) * d < 0:
                ratios.append(abs(back[1] - ext[1]) / so_far)
        depth = float(max(ratios)) if ratios else 0.0
    fp = zigzag(h, lo, FLAT_K * mr)
    mv = [fp[i + 1][1] - fp[i][1] for i in range(len(fp) - 1)]
    flat_ext = any(abs(mv[i + 1]) >= FLAT_B * abs(mv[i]) and abs(mv[i + 2]) >= FLAT_C * abs(mv[i]) for i in range(len(mv) - 2))
    tags = [regime]
    if depth is not None:
        if depth >= DEEP:
            tags.append("deep")
        elif depth <= SHALLOW:
            tags.append("shallow")
        if abs(frac) >= IMP_FRAC and depth <= IMP_DEPTH:
            tags.append("impulse")
    if flat_ext:
        tags.append("flat_ext")
    stats = {"net_over_span": round(frac, 3), "er": round(er, 3), "swings": len(piv),
             "max_counter_depth": None if depth is None else round(depth, 3), "span_mr": round(span / mr, 1) if mr > 0 else None}
    return sorted(tags, key=BUCKETS.index), stats


# ---------------------------------------------------------------------------------------------------------------- windows
def _overlaps(a0, a1, b0, b1):
    return pd.Timestamp(a0) <= pd.Timestamp(b1) and pd.Timestamp(b0) <= pd.Timestamp(a1)


def grid(bars, n, intraday=False):
    """न चढणाऱ्या n-bar windows (index जोड्या). Intraday ⇒ प्रत्येक window session च्या पहिल्या bar ने सुरू."""
    if not intraday:
        return [(i, i + n - 1) for i in range(0, len(bars) - n + 1, n)]
    day = bars["timestamp"].dt.normalize().to_numpy()
    starts = np.flatnonzero(np.r_[True, day[1:] != day[:-1]])
    out, i = [], 0
    for st in starts:
        if st >= i and st + n <= len(bars):
            out.append((int(st), int(st + n - 1)))
            i = st + n
    return out


def _cand(symbol, tf, source, w, origin, **extra):
    tags, stats = shape(w)
    c = {"id": SC.chart_id(symbol, tf, w["timestamp"].iloc[0]), "symbol": symbol, "timeframe": tf, "source": source,
         "start": SC.ts_str(w["timestamp"].iloc[0]), "end": SC.ts_str(w["timestamp"].iloc[-1]), "n_bars": int(len(w)),
         "origin": origin, "calibration": True, "holdout_dates_exception": False, "tags": tags, "stats": stats}
    c.update(extra)
    return c


def pool(slot, cases):
    """एका slot चे सगळे policy-योग्य grid windows (Abhi cases वर न चढणारे)."""
    bars, n = slot["bars"].reset_index(drop=True), WINDOW_BARS[slot["timeframe"]]
    out = []
    for a, b in grid(bars, n, intraday=slot["timeframe"] != "D"):
        w = bars.iloc[a:b + 1].reset_index(drop=True)
        s, e = w["timestamp"].iloc[0], w["timestamp"].iloc[-1]
        try:
            GD.window_allowed(slot["symbol"], s, e)
        except GD.DP.HoldoutError:
            continue
        if any(k["symbol"] == slot["symbol"] and k["timeframe"] == slot["timeframe"] and _overlaps(s, e, k["start"], k["end"]) for k in cases):
            continue
        out.append(_cand(slot["symbol"], slot["timeframe"], slot["source"], w, "auto"))
    return out


def pick(cands, q, rng):
    chosen = []
    while len(chosen) < q:
        moved = False
        for b in BUCKETS:
            if len(chosen) >= q:
                break
            el = [c for c in cands if b in c["tags"] and c not in chosen]
            if el:
                chosen.append(el[int(rng.integers(len(el)))])
                moved = True
        if not moved:
            break
    return chosen


def split(charts, n_test, seed):
    """Abhi cases dev; बाकीतून n_test test — slot आकाराच्या प्रमाणात (largest remainder), slot मध्ये seeded. ids चा set."""
    elig = sorted((c for c in charts if c["origin"] != "abhi_case"), key=lambda c: c["id"])
    slots = {}
    for c in elig:
        slots.setdefault((c["symbol"], c["timeframe"]), []).append(c["id"])
    if not elig:
        return set()
    share = {k: n_test * len(v) / len(elig) for k, v in slots.items()}
    alloc = {k: int(math.floor(v)) for k, v in share.items()}
    for k in sorted(share, key=lambda k: (-(share[k] - alloc[k]), ORDER_S[k[0]], ORDER_T[k[1]]))[: n_test - sum(alloc.values())]:
        alloc[k] += 1
    rng = np.random.default_rng(seed + 1000)
    test = set()
    for k in sorted(slots, key=lambda k: (ORDER_S[k[0]], ORDER_T[k[1]])):
        ids = sorted(slots[k])
        test |= {ids[i] for i in rng.choice(len(ids), size=min(alloc[k], len(ids)), replace=False)}
    return test


def build(slots, cases, seed=SEED, n_total=N_TOTAL, n_test=N_TEST, quotas=None, missing=()):
    """slots = [{"symbol", "timeframe", "source", "bars", "rule"}] (data असलेले); cases = [{"symbol", "timeframe", "source", "bars"
    (window चे bars), "key", "note", "holdout_dates_exception"}]. रिटर्न manifest dict (deterministic — वेळ / host नाही)."""
    quotas = dict(QUOTAS if quotas is None else quotas)
    rng = np.random.default_rng(seed)
    chosen = []
    for k in cases:
        GD.window_allowed(k["symbol"], k["bars"]["timestamp"].iloc[0], k["bars"]["timestamp"].iloc[-1],
                          exception=bool(k.get("holdout_dates_exception")))
        chosen.append(_cand(k["symbol"], k["timeframe"], k["source"], k["bars"].reset_index(drop=True), "abhi_case",
                            calibration=False, holdout_dates_exception=bool(k.get("holdout_dates_exception")),
                            case=k["key"], note=k.get("note", "")))
    pools = {}
    for sl in sorted(slots, key=lambda s: (ORDER_S[s["symbol"]], ORDER_T[s["timeframe"]])):
        pools[(sl["symbol"], sl["timeframe"])] = pool(sl, chosen)
    q = {k: max(0, min(quotas.get(k, 0) - sum(1 for c in chosen if (c["symbol"], c["timeframe"]) == k), len(pl)))
         for k, pl in pools.items()}
    deficit = n_total - len(chosen) - sum(q.values())
    while deficit > 0:                                               # data नसलेल्या slots चा वाटा ⇒ उरलेल्या slots ना आळीपाळीने
        moved = False
        for k in pools:
            if deficit > 0 and q[k] < len(pools[k]):
                q[k] += 1
                deficit -= 1
                moved = True
        if not moved:
            break
    for k, pl in pools.items():
        chosen += pick(pl, q[k], rng)
    chosen = chosen[:n_total]
    test = split(chosen, n_test, seed)
    chosen.sort(key=lambda c: (ORDER_S[c["symbol"]], ORDER_T[c["timeframe"]], c["start"]))
    for i, c in enumerate(chosen, 1):
        c["n"] = i
        c["split"] = "test" if c["id"] in test else "dev"
    overlap = sorted([a["id"], b["id"]] for a in chosen for b in chosen if a["split"] == "test" and b["split"] == "dev"
                     and a["symbol"] == b["symbol"] and _overlaps(a["start"], a["end"], b["start"], b["end"]))
    counts = {s: {t: sum(1 for c in chosen if c["symbol"] == s and c["timeframe"] == t) for t in GD.TIMEFRAMES} for s in GD.SYMBOLS}
    return {"schema": 1, "seed": seed, "n_total": len(chosen), "n_dev": sum(c["split"] == "dev" for c in chosen),
            "n_test": sum(c["split"] == "test" for c in chosen), "counts": counts,
            "window_bars": WINDOW_BARS, "quotas": {f"{s}/{t}": v for (s, t), v in quotas.items()},
            "auto_per_slot": {f"{s}/{t}": v for (s, t), v in q.items()},
            "selection_rule": __doc__.split("निवड नियम (manifest मध्ये शब्दशः नोंद):")[1].split("Split:")[0].strip(),
            "split_rule": "Abhi cases ⇒ dev. बाकीतून 12 test: (symbol, TF) slot आकाराच्या प्रमाणात (largest remainder), slot मध्ये "
                          "numpy default_rng(seed + 1000) ने. Test labels sealed — फक्त acceptance (gallery2.store.load_labels).",
            "sources": {sl["symbol"] + "/" + sl["timeframe"]: {"source": sl["source"], "rule": sl.get("rule", "")}
                        for sl in sorted(slots, key=lambda s: (ORDER_S[s["symbol"]], ORDER_T[s["timeframe"]]))},
            "missing": list(missing),
            "cross_tf_overlap": {"rule": "एकाच symbol + TF वर test आणि dev windows कधीच चढत नाहीत (grid). वेगळ्या TF वर त्याच तारखा "
                                         "चालतात (CR-Q16) — या जोड्या [test, dev]:", "pairs": overlap},
            "charts": chosen}


# ---------------------------------------------------------------------------------------------------------------- real data
AUTO = {("NIFTY", "D"): "nifty_1m_repo", ("NIFTY", "1H"): "nifty_1m_repo", ("NIFTY", "15M"): "nifty_1m_repo",
        ("BANKNIFTY", "D"): "banknifty_D", ("BANKNIFTY", "1H"): "banknifty_1H", ("BANKNIFTY", "15M"): "banknifty_15M"}


def load_cases(path=CASES):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def real_inputs(cases_path=CASES):
    """या machine वरचा data ⇒ (slots, cases, missing). NIFTY auto = फक्त IS; data नाही ⇒ missing मध्ये नोंद (data शोधून काढत नाही)."""
    slots, missing = [], []
    for sym in GD.SYMBOLS:
        for tf in GD.TIMEFRAMES:
            key = AUTO.get((sym, tf))
            if key is None:
                missing.append({"symbol": sym, "timeframe": tf, "why": "repo / trade-data मध्ये या symbol चा OHLC source नाही"})
                continue
            try:
                if sym == "NIFTY":
                    bars = GD.tf_frame(key, tf, GD.DP.IS_START, GD.DP.IS_END)
                    bars = bars[(bars["timestamp"] >= GD.DP.IS_START) & (bars["timestamp"] <= GD.DP.IS_END)]
                    rule = "IS 2015–2021 फक्त (VAL जपला; holdout / illustration नाही)"
                else:
                    bars = GD.tf_frame(key, tf)
                    rule = "उपलब्ध सगळा data, NIFTY holdout तारखा वगळून"
            except GD.DataMissing as exc:
                missing.append({"symbol": sym, "timeframe": tf, "why": str(exc)})
                continue
            first, last = bars["timestamp"].min(), bars["timestamp"].max()
            slots.append({"symbol": sym, "timeframe": tf, "source": key, "bars": bars.reset_index(drop=True),
                          "rule": f"{rule}; data {first:%Y-%m-%d} → {last:%Y-%m-%d}, {len(bars)} bars"})
    cases = []
    for k in load_cases(cases_path):
        exc = bool(k.get("holdout_dates_exception"))
        try:
            fr = GD.tf_frame(k["source"], k["timeframe"], k["start"], k["end"], exception=exc)
        except GD.DataMissing as exc_:
            missing.append({"symbol": k["symbol"], "timeframe": k["timeframe"], "why": f"Abhi case {k['key']}: {exc_}"})
            continue
        ts = fr["timestamp"]
        w = fr[(ts >= pd.Timestamp(k["start"])) & (ts <= pd.Timestamp(k["end"]))].reset_index(drop=True)
        cases.append({**k, "bars": w})
    return slots, cases, missing
