"""decision3/liquidity.py — spec §7: liquidity नकाशा (`liquidity_map`), sweep ⚡ आणि अडकलेले traders (`trapped_zone`).

Pools (t च्या close ला माहीत तेवढेच):
  • buy-side (वर): confirmed D2 swing highs, equal highs (σ_1H × liquidity_eq_sigma), मागच्या दिवसाचा / आठवड्याचा high (PDH / PWH).
  • sell-side (खाली): swing lows, equal lows, PDL / PWL.
Sweep: किंमत pool पलीकडे (wick किंवा < accept_closes closes) आणि लवकर परत आत close ⇒ ⚡ (acceptance नाही).
Trapped zone: (a) failed breakout — pool पलीकडे ≥ 1 close, मग परत आत `accept_closes` closes ⇒ breakout traders अडकले; पट्टा = [pool, पलीकडचं टोक].
फक्त पुरावा / chart (gate नाही). Order / broker call नाही.
"""
import numpy as np


def pools(V, t):
    """t ला माहीत pools: [{price, side: buy|sell, src}]"""
    lv = V.levels
    out = []
    for p in lv.known_pivots(t):
        out.append({"price": float(p.price), "side": "buy" if p.kind == "H" else "sell", "src": "swing"})
    eq = float(V.s["liquidity_eq_sigma"]) * (lv.sig1h[t] if np.isfinite(lv.sig1h[t]) else 0.0)
    for side in ("buy", "sell"):
        xs = sorted(x["price"] for x in out if x["side"] == side and x["src"] == "swing")
        for a, b in zip(xs[:-1], xs[1:]):
            if b - a <= eq:
                out.append({"price": (a + b) / 2, "side": side, "src": "equal"})
    ts = lv.ts
    day = ts[t].normalize()
    prev = ts[ts.dt.normalize() < day]
    if len(prev):
        pdx = prev.dt.normalize() == prev.iloc[-1].normalize()
        idx = prev[pdx].index
        out.append({"price": float(lv.A["high"][idx].max()), "side": "buy", "src": "PDH"})
        out.append({"price": float(lv.A["low"][idx].min()), "side": "sell", "src": "PDL"})
        wk = ts.dt.to_period("W-FRI")
        pw = ts[(wk < wk[t])]
        if len(pw):
            wi = pw[wk[pw.index] == wk[pw.index[-1]]].index
            out.append({"price": float(lv.A["high"][wi].max()), "side": "buy", "src": "PWH"})
            out.append({"price": float(lv.A["low"][wi].min()), "side": "sell", "src": "PWL"})
    return out


def sweeps_and_traps(V, t, lookback):
    """शेवटच्या `lookback` bars मधले sweeps ⚡ आणि trapped zones (pools t-lookback ला माहीत असलेले)."""
    A = V.levels.A
    acc = int(V.s["accept_closes"])
    t0 = max(1, t - lookback)
    ps = pools(V, t0)
    sw, tr = [], []
    for p in ps:
        pr = p["price"]
        sign = 1 if p["side"] == "buy" else -1
        beyond_c = [(A["close"][i] - pr) * sign > 0 for i in range(t0, t + 1)]
        beyond_w = [((A["high"][i] if sign > 0 else A["low"][i]) - pr) * sign > 0 for i in range(t0, t + 1)]
        if not any(beyond_w):
            continue
        first = beyond_w.index(True)
        seq = beyond_c[first:]
        runs, cur = [], 0
        for x in seq:
            cur = cur + 1 if x else 0
            runs.append(cur)
        if max(runs) >= acc or seq[-1]:
            continue                                                     # acceptance पलीकडे / अजून पलीकडे ⇒ sweep नाही
        ext = max(A["high"][t0:t + 1]) if sign > 0 else min(A["low"][t0:t + 1])
        sw.append({**p, "bar": t0 + first, "extreme": float(ext)})
        tail_in = 0
        for x in reversed(seq):
            if x:
                break
            tail_in += 1
        if any(seq) and tail_in >= acc:
            tr.append({"lo": min(pr, ext), "hi": max(pr, ext), "kind": "failed_breakout", "side": p["side"], "bar": t0 + first})
    return sw, tr
