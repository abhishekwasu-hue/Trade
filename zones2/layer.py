"""zones2/layer.py — थर 4 प्रत्येक बंद candle ला (D1 trade degree): trade बाजू, पुढचे / उलट zones, "K area मध्ये", confluence, I-profile,
आणि थर 3 चं momentum item 9 (absorption, फक्त zone) भरून **तेच function** पुन्हा ⇒ एकच final verdict (थर 5 / 6 / 7 हाच वापरतात)."""
import pandas as pd

from patterns2 import momentum as MO
from pivots import engine as PE

from . import engine as ZE


def k_last_start(res, I, t):
    """K चा शेवटचा (K-दिशेचा) D0 leg ज्या pivot पासून सुरू झाला त्याचा bar (I खाली ⇒ K वर ⇒ शेवटचा D0 L)."""
    kind = "L" if I["dir"] < 0 else "H"
    ps = [p for p in res["pivots"][0] if p.confirm_bar <= t and p.kind == kind and p.bar >= I["end"].bar]
    return ps[-1].bar if ps else I["end"].bar


def run(Z, f1, f2=None, bars=None):
    """Z = zones2.engine.Zones (run(snap_bars) नंतर). रिटर्न {bar: रेकॉर्ड}."""
    res = Z.res
    s = Z.s
    hy, hy_key, last_t = MO.Hysteresis(f1.s["hysteresis_bars"]), None, None
    out = {}
    full = PE.complete_sessions(res["m15"])
    sess_of = {}
    for j, d in enumerate(Z.day):
        if full.get(pd.Timestamp(d)) and Z.segs[j] is not None:
            sess_of.setdefault(pd.Timestamp(d), []).append(j)
    sp_cache = {}
    bars = sorted(Z.snap) if bars is None else bars
    for t in bars:
        zones = Z.snap.get(t)
        if zones is None:
            continue
        rec = f1.out.get(t, {})
        st = rec.get("l2") or {}
        I = f1.trk.I_at(t)
        st1 = Z.st[1]["states"][t] if 1 in Z.st else None
        st2 = Z.st[2]["states"][t] if 2 in Z.st else None
        side = ZE.trade_side(Z, st, st1, st2)
        sig = Z.sig[t]
        c = Z.A["c"][t]
        r = {"bar": t, "side": side, "k_area": {"ans": "NA"}, "confluence": [], "next": [], "opp": [], "momentum": None,
             "open_noise": bool((Z.ts[t] - Z.day[t]) < pd.Timedelta(hours=9, minutes=15 + int(s["open_noise_min"]))),
             "range_zones": [z["id"] for z in zones if z["flags"]["d"]],
             "range_zone_bands": [(z["bottom"], z["top"], z["role"]) for z in zones if z["flags"]["d"] and z["status"] != "dead"]}
        if side in (ZE.SELLER, ZE.BUYER):
            above = side == ZE.SELLER
            tz = sorted([z for z in zones if z["role"] == side and z["status"] != "dead"
                         and ((z["bottom"] >= c if above else z["top"] <= c) or z["bottom"] <= c <= z["top"])],
                        key=lambda z: abs((z["bottom"] if above else z["top"]) - c))
            oz = sorted([z for z in zones if z["role"] != side and z["status"] != "dead"], key=lambda z: abs((z["top"] + z["bottom"]) / 2 - c))
            r["next"], r["opp"] = [z["id"] for z in tz[:int(s["next_trade"])]], [z["id"] for z in oz[:int(s["next_opp"])]]
        if I is not None and st.get("K") is not None:
            st2_ = dict(st, i_end_bar=I["end"].bar)
            ka = ZE.k_area(Z, zones, st2_, t, k_last_start(res, I, t), htf_trend=None if st2 is None else st2["trend"])
            r["k_area"] = ka
            if ka.get("band"):
                mid = (ka["band"][0] + ka["band"][1]) / 2
                extras = [(f"Fib {nm}", v) for nm, v in ZE.fib_levels(st["I"], s)]
                if rec.get("c_eq_a") is not None:
                    extras.append(("C = A", rec["c_eq_a"]))
                prof = ZE.profile(Z.A, Z.lg["vol"], range(I["origin"].bar + 1, I["end"].bar + 1), sig, s)
                if prof is not None:
                    extras += [("I POC", prof[0]), ("I VAL", prof[1]), ("I VAH", prof[2])]
                    r["i_profile"] = [round(x, 2) for x in prof]
                dk = (pd.Timestamp(Z.day[t]), Z.segs[t], round(float(sig), 6))       # σ दिवसाचा (एकच); key मध्ये स्पष्ट
                if dk not in sp_cache:                                           # 5 पूर्ण sessions (Abhi निर्णय); कमी ⇒ NA
                    same = {d: b for d, b in sess_of.items() if Z.segs[b[0]] == Z.segs[t]}
                    sp_cache[dk] = ZE.sessions_profile(Z.A, Z.lg["vol"], Z.day, same, t, sig, s)
                sp = sp_cache[dk]
                r["sessions_profile"] = None if sp is None else [round(x, 2) for x in sp]
                if sp is not None:
                    n5 = int(s["profile_sessions"])
                    extras += [(f"{n5}S POC", sp[0]), (f"{n5}S VAL", sp[1]), (f"{n5}S VAH", sp[2])]
                others = [z for z in zones if z["id"] != ka.get("zone")]
                extras += [(f"zone {z['id']}", (z["top"] + z["bottom"]) / 2) for z in others]
                r["confluence"] = ZE.confluence(mid, sig, s, extras)
            if rec.get("momentum") is not None:
                trade = [z for z in zones if z["role"] == (ZE.SELLER if I["dir"] < 0 else ZE.BUYER) and z["status"] != "dead"
                         and not (z["pivot_bar"] is not None and z["pivot_bar"] > I["end"].bar)]

                def zone_fn(price, tt, trade=trade):
                    return any(z["bottom"] <= price <= z["top"] for z in trade)
                key = (I["origin"].bar, I["ends"][0].bar)
                if key != hy_key or last_t != t - 1:                              # नवा I / K किंवा मध्ये momentum नसलेली candle ⇒ नवी hysteresis
                    hy, hy_key = MO.Hysteresis(f1.s["hysteresis_bars"]), key
                last_t = t
                m = f1.momentum(rec, st, I, t, zone_fn=zone_fn, hyst=False)
                m["raw_verdict"] = m["verdict"]
                m["verdict"] = hy.step(m["verdict"], bool(m["danger"]))
                r["momentum"] = m
        out[t] = r
    return out


def zone_json(z):
    keep = ("id", "top", "bottom", "role", "status", "pending", "accept", "degree", "k", "visits", "touch_score", "sweeps_all", "breaker",
            "flip_bar", "retest", "spring", "age", "score", "stars", "parts")
    j = {k: z[k] for k in keep}
    f = z["flags"]
    j["flags"] = {"c": None if f["c"] is None else {k: v for k, v in f["c"].items()}, "d": f["d"], "e": f["e"]}
    return j
