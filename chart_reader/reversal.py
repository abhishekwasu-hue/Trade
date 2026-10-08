"""chart_reader/reversal.py — reversal हा पुरावा (evidence), हो/नाही gate नाही (Abhi 2026-10-08).

🎓 मुख्य व्याख्या `elliott/reversal.py` (composite 1–3 बंद candles; ATR touch; invalidation). `soft=True` ने:
  पक्के:  touch + reclaim (touched level च्या पलीकडे close), hard invalidation, close location trade दिशेने: CL 0.40–0.60 ⇒
          follow-through ची वाट; CL < 0.40 (close trade विरुद्ध टोकाला) ⇒ "against" — reversal नाही
  पुरावा: elliott 0–1 score `raw`, आणि त्यावर आधी ठरवलेले modifiers ⇒ `s` (grade मध्ये RV = 50 × (s − 0.30)):
           range < strength_min × MR  ⇒ × max(rev_weak_floor, range ÷ (strength_min × MR))
           range > strength_max × MR आणि CL < 0.6 (climax extension) ⇒ − rev_climax_penalty  (रुंद reclaim ⇒ दंड नाही; risk R:R नियमात)
           N ≥ 2 आणि शेवटची candle विरुद्ध ⇒ − rev_last_against_penalty ·  N = 3 ⇒ − rev_n3_penalty
  0.60 cutoff फक्त label साठी (strong / medium / weak). `price_action/candles.py` चा 0–100 breakdown फक्त narrative / log / vision.
Caller ने फक्त **बंद** bars द्यायचे (j = शेवटचा बंद bar).
"""
import numpy as np

from elliott import reversal as RV
from price_action import candles as CA

from .grade import reversal_label

_FIRM_ORDER = {RV.NO_DATA: 0, RV.NO_TOUCH: 1, RV.INV: 2, RV.NO_RECLAIM: 3, "against": 4, RV.INDECISIVE: 5}
_STATUS = {RV.NO_DATA: "no_data", RV.NO_TOUCH: "no_touch", RV.INV: "beyond_inv", RV.NO_RECLAIM: "no_reclaim",
           "against": "against", RV.INDECISIVE: "wait_followthrough"}


def adjust(w, es, s):
    """एका soft window चा raw score ⇒ s (modifiers सह). रिटर्न (s, लागू modifiers)."""
    v, mods = float(w["score"]), []
    fl = w.get("flags") or []
    if "weak" in fl and w.get("rng_ratio"):
        f = max(s["rev_weak_floor"], float(w["rng_ratio"]) / float(es["strength_min"]))
        v *= f
        mods.append(f"weak ×{f:.2f}")
    if "climax" in fl:
        v -= s["rev_climax_penalty"]
        mods.append(f"climax −{s['rev_climax_penalty']}")
    if "last_against" in fl:
        v -= s["rev_last_against_penalty"]
        mods.append(f"last candle against −{s['rev_last_against_penalty']}")
    if w["n"] >= 3:
        v -= s["rev_n3_penalty"]
        mods.append(f"N={w['n']} −{s['rev_n3_penalty']}")
    return float(np.clip(v, 0.0, 1.0)), mods


def evaluate(b, j, dirn, levels, tol, es, s, inv=None, frame=None, n_max=None, **kw):
    """b = elliott Bars (बंद bars), j = शेवटचा बंद bar. रिटर्न dict: status ("ok" / "wait_followthrough" / "no_touch" / "no_reclaim" /
    "beyond_inv" / "no_data"), s, raw, n, label, flags, mods, touched, comp, close_loc, rng_ratio, parts, candles (0–100 breakdown)."""
    nmax = int(n_max or es["touch_reclaim_window"])
    wins = [RV.evaluate_window(b, j, n, dirn, levels, tol, es, inv=inv, soft=True, **kw) for n in range(1, nmax + 1)]
    if 1 <= j < b.n:                                                     # follow-through (legacy): मागचा N अनिर्णयी + हा bar दिशेने
        prev = RV.evaluate_window(b, j - 1, nmax, dirn, levels, tol, es, inv=inv, soft=True, **kw)
        if prev["reason"] == RV.INDECISIVE and dirn * (b.c[j] - b.o[j]) > 0:
            wins.append(RV.evaluate_window(b, j, nmax + 1, dirn, levels, tol, es, inv=inv, soft=True, **kw))
    ok = []
    band_lo = float(es.get("indecision_band", RV.INDECISION)[0])
    for w in wins:
        if w["ok"] and w["close_loc"] is not None and w["close_loc"] < band_lo:
            w["reason"] = "against"                                      # close trade विरुद्ध टोकाला ⇒ reversal नाहीच (पक्की अट)
            w["ok"] = False
        if w["ok"]:
            sv, mods = adjust(w, es, s)
            ok.append((sv, -w["n"], w, mods))
    out = {"status": None, "s": None, "raw": None, "n": None, "label": "none", "flags": [], "mods": [], "touched": None, "comp": None,
           "close_loc": None, "rng_ratio": None, "parts": {}, "candles": {}}
    if ok:
        sv, _, w, mods = max(ok, key=lambda x: (x[0], x[1]))
        out.update(status="ok", s=round(sv, 4), raw=round(float(w["score"]), 4), n=w["n"], label=reversal_label(sv, s), flags=list(w["flags"]),
                   mods=mods, touched=w["touched"], comp=w["comp"], close_loc=w["close_loc"], rng_ratio=w["rng_ratio"], parts=w["parts"])
    else:
        w = max(wins, key=lambda x: _FIRM_ORDER.get(x["reason"], -1))
        out.update(status=_STATUS.get(w["reason"], str(w["reason"])), n=w["n"], touched=w["touched"], comp=w["comp"],
                   close_loc=w["close_loc"], rng_ratio=w["rng_ratio"])
    if frame is not None and out["n"] and out["touched"] is not None:
        try:
            c = CA.evaluate_window(frame.iloc[: j + 1], min(out["n"], CA.MAX_N + 1), float(out["touched"]),
                                   "BULLISH" if dirn > 0 else "BEARISH")
            out["candles"] = {"score": c["score"], "components": c["components"], "label": c["label"], "reason": c["reason"]}
        except Exception as exc:                                         # breakdown फक्त माहिती — निर्णयावर परिणाम नाही
            out["candles"] = {"error": f"{type(exc).__name__}"}
    return out
