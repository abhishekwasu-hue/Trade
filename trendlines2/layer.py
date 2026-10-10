"""trendlines2/layer.py — थर 5 प्रत्येक बंद candle ला (D1 trade degree): trade-बाजूच्या रेघा (वर्गासह), K sloping area, K आधार /
टोक रेघा आणि आधार-रेघ break घटना, intersection; थर 4 चा "K area मध्ये" = zone **किंवा** रेघ (स्रोत स्पष्ट)."""

from zones2 import engine as ZE
from zones2 import layer as ZL

from . import engine as TE


def run(E, trk, f1, Z=None, L4=None, bars=None):
    res = E.res
    out = {}
    bars = range(E.n) if bars is None else bars
    for t in bars:
        I = trk[1].I_at(t)
        st = trk[1].state(t) if I is not None else {}
        r = {"bar": t, "ts": str(E.ts.iloc[t]), "side": None, "lines": [], "k_area_line": {"ans": "NA"}, "k_base": None, "k_tip": None, "k_lines": None,
             "k_area": None, "next_line": None}
        if I is None or not st.get("K"):
            out[t] = r
            continue
        kind = "H" if I["dir"] < 0 else "L"
        r["side"] = ZE.SELLER if kind == "H" else ZE.BUYER
        k_start = ZL.k_last_start(res, I, t)
        K = st["K"]
        k_ext = K.get("extreme")
        o = I["origin"]
        A = E.A
        i_slope = (I["end"].price - o.price) / max(I["end"].bar - o.bar, 1)
        lines = TE.tradeable(E, t, kind, k_start, k_ext, I["dir"])
        r["lines"] = [E.line_json(L, t, name, cls, i_slope) for L, name, cls in lines]
        tl = [x for x in r["lines"] if x["class"] == "trade-योग्य"]
        if tl:
            c = A["c"][t]
            r["next_line"] = min(tl, key=lambda x: abs(x["value_now"] - c))["value_now"]
        zones = None
        if Z is not None and t in Z.snap:
            zones = [z for z in Z.snap[t] if z["role"] == r["side"] and z["status"] != "dead"
                     and not (z["pivot_bar"] is not None and z["pivot_bar"] > I["end"].bar)]
        r["k_area_line"] = TE.k_sloping_area(E, lines, t, k_start, zones)
        rec = f1.out.get(t) if f1 is not None else None
        kl = TE.k_lines(E, rec, I, t)
        if kl is not None:
            r["k_lines"] = {"base": E.line_json(kl["base"], t, "K आधार", "K"), "tip": None if kl["tip"] is None else
                            E.line_json(kl["tip"], t, "K टोक", "K")}
            r["k_base"] = TE.k_base_break(E, kl["base"], t, I["end"].bar)
            r["k_tip"] = TE.tip_touch(E, kl["tip"], t, I["end"].bar)
        za = (L4 or {}).get(t, {}).get("k_area") if L4 else None
        la = r["k_area_line"]
        if za is not None and za.get("ans", "").startswith("हो"):
            r["k_area"] = {"ans": za["ans"], "source": "zone", "zone": za.get("zone"), "line": la.get("line") if la["ans"].startswith("हो")
                           else None, "intersection": la.get("intersection")}
        elif la["ans"].startswith("हो"):
            r["k_area"] = {"ans": la["ans"], "source": "रेघ", "line": la["line"], "intersection": la.get("intersection")}
        else:
            r["k_area"] = {"ans": "नाही", "source": None}
        out[t] = r
    return out
