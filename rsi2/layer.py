"""rsi2/layer.py — थर 6 प्रत्येक बंद candle ला: RSI (15M, 1H), rsi_range + shift, शेवटची divergence, on_K / regular_in_K /
at_impulse_end / cascade, rsi_disagree, labels (निर्णय नाही) आणि थर 4 चं final momentum verdict (संदर्भ)."""
from swings2 import structure as SST

from . import engine as RE


def run(R, trk, f1, L4=None, bars=None):
    out = {}
    bars = range(R.n) if bars is None else bars
    for t in bars:
        I = trk[1].I_at(t)
        st = trk[1].state(t) if I is not None else {}
        rec = f1.out.get(t) if f1 is not None else None
        pref = rec.get("pref") if rec and rec.get("agg") != "none" else None
        r15, r1h = R.classify(t, "15M"), R.classify(t, "1H")
        sp = RE.special(R, I, st, pref, t)
        casc = RE.cascade(R, t)
        s1 = R.st[1]["states"][t] if 1 in R.st else {"trend": None}
        s2 = R.st[2]["states"][t] if 2 in R.st else {"trend": None}
        l4 = (L4 or {}).get(t) or {}
        edge_hit = any(x["L2"]["bar"] >= t - int(R.s["edge_recent_bars"]) and
                       any(bot <= x["L2"]["price"] <= top and role == ("buyer" if x["type"] == RE.REG_BULL else "seller")
                           for bot, top, role in (l4.get("range_zone_bands") or []))
                       for x in R.known(t)[-3:] if x["type"] in (RE.REG_BULL, RE.REG_BEAR))   # bull ⇒ खालची (buyer) कड
        labels, final = RE.mapping(r15, r1h, sp, casc, s1["trend"] == SST.RNG, edge_hit, R.s)
        tr2 = s2["trend"]
        rg = r1h.get("range")
        disagree = bool(rg is not None and ((tr2 == SST.UPT and rg != RE.BULL) or (tr2 == SST.DNT and rg != RE.BEAR)
                                            or (tr2 == SST.RNG and rg != RE.NEUTRAL)))
        last = R.known(t)[-1] if R.known(t) else None
        out[t] = {"bar": t, "rsi15": None if R.r15[t] != R.r15[t] else round(float(R.r15[t]), 2), "rsi_warmup": bool(R.warm[t]),
                  "rsi_range_15m": r15, "rsi_range_1h": r1h, "last": last, "on_K": sp["on_K"], "regular_in_K": sp["regular_in_K"],
                  "at_impulse_end": sp["at_impulse_end"], "cascade": casc, "rsi_disagree": disagree, "labels": labels, "label": final,
                  "momentum": (l4.get("momentum") or {}).get("verdict")}
    return out
