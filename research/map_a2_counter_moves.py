"""research/map_a2_counter_moves.py — नकाशा A2 (P4): IS वरचे सगळे counter-moves, outcome नुसार गट, आणि कोणते पुरावे भेद करतात.
**फक्त अहवाल — कोणताही threshold ठरवत नाही.**

Counter-move = trade-degree (15M, market_state pivots ATR × trade_swing_atr_mult) F3 impulse leg pᵢ → pᵢ₊₁ नंतरचा leg pᵢ₊₁ → pᵢ₊₂,
जो impulse origin (pᵢ) च्या आत राहिला (counter-move दरम्यान origin चा real break नाही — तो S4).
**Decision bar** = pᵢ₊₂ चा confirm bar. प्रत्येक पुरावा फक्त त्या bar पर्यंतच्या data वरून; percentile फक्त त्या bar आधी पूर्ण झालेल्या
counter-moves वरून.
Outcome (फक्त गट पाडण्यासाठी, decision bar नंतरचे bars, horizon bars पर्यंत):
  (a) continuation — impulse टोक (pᵢ₊₁) close ने पुन्हा पार, origin break आधी;
  (b) reversal — origin real break (elliott/breaks.py) आणि नवी दिशा confirm (break नंतर नव्या दिशेचा confirmed swing आणि मग break-टोकापलीकडे
      close);
  (c) अनिर्णित — horizon मध्ये दोन्ही नाही (किंवा origin तुटला पण नवी दिशा confirm नाही). (c) जबरदस्तीने (a) / (b) मध्ये नाही.
पुरावे: overlap ratio (K10.1), ER, legs (आतले swings ATR × 1.5), वेग आणि वेग ÷ impulse वेग, displacement candles, खोली, impulse ची अंतर्गत
1H रचना (शेवटचा HL / LH) close ने तुटली का, overlap चं percentile (आधीच्या पूर्ण counter-moves मध्ये). Futures volume — IS मध्ये data नाही.

    python3 research/map_a2_counter_moves.py --is-data data/nifty50_1min.parquet --out docs/reports/situation_map
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from elliott import breaks as BR                 # noqa: E402
from elliott import data_policy as DP            # noqa: E402
from elliott import settings as ES               # noqa: E402

HORIZON = 400          # bars (~16 sessions) — outcome शोधण्याची मर्यादा (फक्त गटांसाठी) [A1 register]
INTERNAL_ATR = 1.5     # आतले swings (gallery / market_state internal सारखं) [A1 register]
H1_ATR = 1.5           # impulse ची अंतर्गत 1H रचना [A1 register]
PCT_LOOKBACK = 30      # overlap percentile: आधीचे इतके पूर्ण counter-moves [A1 register]


def _internal_legs(fr, a, b):
    from market_state import core as C
    lo = max(0, a - 40)
    sub = fr.iloc[lo: b + 1].reset_index(drop=True)
    pv = [p for p in C.pivots(sub, INTERNAL_ATR) if a - lo < p["idx"] < b - lo and p["conf"] <= b - lo]
    return len(pv) + 1


def _disp(fr, a, b, d, mr, s):
    o, c, h, lo = (fr[k].to_numpy(float)[a:b + 1] for k in ("open", "close", "high", "low"))
    body, rng = np.abs(c - o), np.maximum(h - lo, 1e-9)
    mm = mr[a:b + 1]
    ok = np.isfinite(mm)
    return int(((body >= s["disp_body_mr"] * mm) & (body / rng >= s["disp_body_frac"]) & ((c - o) * d > 0) & ok).sum())


def _outcome(fr, x, p0, p1, d, es, mr):
    """d = impulse दिशा. रिटर्न a / b / c."""
    c = fr["close"].to_numpy(float)
    h, lo = fr["high"].to_numpy(float), fr["low"].to_numpy(float)
    end = min(len(fr) - 1, x + HORIZON)
    seg = c[x + 1:end + 1]
    cont = np.nonzero((seg > p1["price"]) if d > 0 else (seg < p1["price"]))[0]
    k_cont = x + 1 + int(cont[0]) if len(cont) else None
    b = BR.first_real_break(fr, x + 1, p0["price"], "below" if d > 0 else "above", es, mr=mr, end=end)
    if k_cont is not None and (b is None or k_cont < b):
        return "a"
    if b is None:
        return "c"
    from market_state import core as C
    sub = fr.iloc[: end + 1].reset_index(drop=True)
    newkind = "H" if d > 0 else "L"                                     # नव्या (उलट) दिशेचा counter swing
    piv = [p for p in C.pivots(sub.iloc[max(0, b - 60):].reset_index(drop=True), 3.0) if p["kind"] == newkind]
    off = max(0, b - 60)
    for p in piv:
        pi = p["idx"] + off
        if pi <= b:
            continue
        ext = float(lo[b:pi + 1].min()) if d > 0 else float(h[b:pi + 1].max())
        after = c[p["conf"] + off + 1:end + 1]
        if len(after) and (((after < ext) if d > 0 else (after > ext)).any()):
            return "b"
    return "c"


def scan(fr, h1, log=print):
    from market_state import core as C
    s = dict(C.DEFAULTS)
    es = dict(ES.DEFAULTS)
    mr = BR.median_range(fr, 20)
    pv = C.pivots(fr, s["trade_swing_atr_mult"])
    h1pv = C.pivots(h1, H1_ATR, "1h")
    h1_ts = pd.to_datetime(h1["timestamp"]).to_numpy()
    h1_be = pd.to_datetime(h1["bar_end"]).to_numpy()
    c = fr["close"].to_numpy(float)
    out = []
    for i in range(1, len(pv) - 2):
        lm = C.leg_metrics(fr, pv, i, mr, s)
        if not lm["impulse"]:
            continue
        p0, p1, p2 = pv[i], pv[i + 1], pv[i + 2]
        d = lm["dir"]
        if (p2["price"] - p0["price"]) * d <= 0:                          # origin पलीकडे (wick) ⇒ counter-move नाही (S4 / S7)
            continue
        if BR.first_real_break(fr, p1["idx"] + 1, p0["price"], "below" if d > 0 else "above", es, mr=mr, end=p2["conf"]) is not None:
            continue
        x = int(p2["conf"])
        a, b = p1["idx"], p2["idx"]
        size = abs(p1["price"] - p0["price"])
        cm = abs(p2["price"] - p1["price"])
        bars_c, bars_i = max(b - a, 1), max(p1["idx"] - p0["idx"], 1)
        # impulse ची अंतर्गत 1H रचना: impulse मधला शेवटचा HL (up) / LH (down) — decision bar पर्यंत confirmed — close ने तुटला का
        dts = pd.Timestamp(fr["bar_end"].iloc[x])
        kind = "L" if d > 0 else "H"
        inner = [q for q in h1pv if q["kind"] == kind and p0["ts"] < q["ts"] < p1["ts"] and h1_be[q["conf"]] <= np.datetime64(dts)]
        brk1h = None
        if inner:
            lvl = inner[-1]["price"]
            seg = c[a + 1:x + 1]
            brk1h = bool(((seg < lvl) if d > 0 else (seg > lvl)).any())
        rec = {"ts": str(fr["timestamp"].iloc[x]), "dir": d, "impulse": [p0["price"], p1["price"]], "counter_end": p2["price"],
               "depth": round(cm / size, 3) if size else None,
               "overlap": C.overlap_ratio(fr, a + 1, b), "er": C.efficiency(fr, a, b),
               "legs": _internal_legs(fr, a, x), "speed_ratio": round((cm / bars_c) / (size / bars_i), 3) if size else None,
               "displacement": _disp(fr, a + 1, b, -d, mr, s), "impulse_1h_broken": brk1h, "decision_idx": x,
               "outcome": _outcome(fr, x, p0, p1, d, es, mr)}
        out.append(rec)
        if log and len(out) % 200 == 0:
            log(f"  {rec['ts'][:10]}: counter-moves {len(out)}")
    # overlap percentile: आधी पूर्ण झालेल्या (decision bar < हा) counter-moves मध्ये
    for j, r in enumerate(out):
        prev = [q["overlap"] for q in out[:j] if q["decision_idx"] < r["decision_idx"] and q["overlap"] is not None][-PCT_LOOKBACK:]
        r["overlap_pct"] = round(float(np.mean([v <= r["overlap"] for v in prev])), 3) if prev and r["overlap"] is not None else None
    return out


def auc(xa, xb):
    """P(random b > random a) (+ ties/2). Cliff's delta = 2·AUC − 1."""
    xa, xb = np.asarray(xa, float), np.asarray(xb, float)
    if not len(xa) or not len(xb):
        return None
    gt = (xb[:, None] > xa[None, :]).sum() + 0.5 * (xb[:, None] == xa[None, :]).sum()
    return round(float(gt / (len(xa) * len(xb))), 3)


def report(rows):
    df = pd.DataFrame(rows)
    n = df["outcome"].value_counts().to_dict()
    L = ["# नकाशा A2: counter-moves — continuation (a) वि. reversal (b) (IS 2015–2021)", "",
         "**फक्त अहवाल; कोणताही threshold ठरवलेला नाही.** पुरावे decision bar (counter-move च्या शेवटच्या pivot चा confirm bar) पर्यंतच्या data "
         "वरून; outcome फक्त गट पाडण्यासाठी. AUC = P(reversal चं मूल्य > continuation चं मूल्य); 0.5 ⇒ भेद नाही; Cliff's δ = 2·AUC − 1.", "",
         f"n: (a) continuation {n.get('a', 0)} · (b) reversal {n.get('b', 0)} · (c) अनिर्णित {n.get('c', 0)}", "",
         "| पुरावा | (a) median [IQR] | (b) median [IQR] | AUC (b>a) | Cliff's δ | n (a / b) |", "|---|---|---|---|---|---|"]
    stats = {}
    for col in ("depth", "overlap", "er", "legs", "speed_ratio", "displacement", "overlap_pct"):
        a_ = df.loc[df["outcome"] == "a", col].dropna().astype(float)
        b_ = df.loc[df["outcome"] == "b", col].dropna().astype(float)
        if not len(a_) or not len(b_):
            continue
        A = auc(a_, b_)
        q = lambda v: f"{v.median():.2f} [{v.quantile(.25):.2f}–{v.quantile(.75):.2f}]"      # noqa: E731
        stats[col] = {"auc": A, "delta": round(2 * A - 1, 3), "n_a": len(a_), "n_b": len(b_), "med_a": float(a_.median()), "med_b": float(b_.median())}
        L.append(f"| {col} | {q(a_)} | {q(b_)} | {A} | {round(2 * A - 1, 3)} | {len(a_)} / {len(b_)} |")
    for col in ("impulse_1h_broken",):
        a_ = df.loc[(df["outcome"] == "a") & df[col].notna(), col].astype(bool)
        b_ = df.loc[(df["outcome"] == "b") & df[col].notna(), col].astype(bool)
        if len(a_) and len(b_):
            stats[col] = {"p_a": round(float(a_.mean()), 3), "p_b": round(float(b_.mean()), 3), "n_a": len(a_), "n_b": len(b_)}
            L.append(f"| {col} (प्रमाण True) | {a_.mean():.2f} | {b_.mean():.2f} | — | फरक {b_.mean() - a_.mean():+.2f} | {len(a_)} / {len(b_)} |")
    L += ["", "Futures volume: IS (2015–2021) मध्ये futures volume data नाही ⇒ इथे मोजलेलं नाही (Jul–Oct 2026 फक्त illustration).",
          "", "**वाचन (Abhi साठी, निर्णय नाही):** AUC 0.5 पासून जितका दूर तितका भेद मजबूत. G-MAP1 ला Abhi \"मजबूत / कमकुवत\" यादी गोठवेल; "
          "मग VAL वर एकदाच तीच तुलना."]
    return "\n".join(L) + "\n", stats


def main(argv=None):
    import market_state as MS
    ap = argparse.ArgumentParser()
    ap.add_argument("--is-data", default=os.path.join(ROOT, "data", "nifty50_1min.parquet"))
    ap.add_argument("--start", default="2015-02-01")
    ap.add_argument("--end", default="2021-12-31")
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "reports", "situation_map"))
    a = ap.parse_args(argv)
    raw = pd.read_parquet(a.is_data) if a.is_data.endswith(".parquet") else pd.read_csv(a.is_data, parse_dates=["timestamp"])
    ts = pd.to_datetime(raw["timestamp"])
    raw["timestamp"] = ts.dt.tz_localize(None) if ts.dt.tz is not None else ts
    raw = DP.filter_allowed(raw, "golden")
    raw = raw[(raw["timestamp"] >= pd.Timestamp(a.start)) & (raw["timestamp"] < pd.Timestamp(a.end) + pd.Timedelta(days=1))]
    fr = MS.full_frames(raw)
    rows = scan(fr["15m"].reset_index(drop=True), fr["1h"].reset_index(drop=True))
    os.makedirs(a.out, exist_ok=True)
    md, stats = report(rows)
    open(os.path.join(a.out, "A2_counter_moves.md"), "w", encoding="utf-8").write(md)
    json.dump({"stats": stats, "rows": rows}, open(os.path.join(a.out, "A2_counter_moves.json"), "w", encoding="utf-8"), ensure_ascii=False,
              indent=1, default=str)
    print(md[:1500])


if __name__ == "__main__":
    main()
