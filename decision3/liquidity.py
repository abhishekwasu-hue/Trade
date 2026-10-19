"""decision3/liquidity.py — spec §7: liquidity नकाशा (`liquidity_map`), sweep ⚡ आणि अडकलेले traders (`trapped_zone`).

Pools (t च्या close ला माहीत तेवढेच):
  • buy-side (वर): confirmed D2 swing highs, equal highs (σ_1H × liquidity_eq_sigma), मागच्या दिवसाचा / आठवड्याचा high (PDH / PWH).
  • sell-side (खाली): swing lows, equal lows, PDL / PWL.
Method (default, `liquidity_rule = equal`): equal highs / lows by comparison (the later swing reaches the earlier swing candle's band,
not beyond); sweep ⚡ = beyond and back inside before any swing formed beyond; trapped = with a close beyond (failed breakout); no day /
week pools (P2). Legacy: σ tolerance, PDH / PWH, `accept_closes` closes ⇒ acceptance, `lookback` bars.
फक्त पुरावा / chart (gate नाही). Order / broker call नाही.
"""
import numpy as np


def _method(V):
    """Abhi's method (default, `liquidity_rule = equal`): equal by comparison, sweep / trap by structure, no day / week pools (P2)."""
    return V.s.get("liquidity_rule", "equal") == "equal"


def _equal(A, p1, p2):
    """Method §3 "equal": the later swing (p2) reaches the earlier swing candle's own wick-to-body band and does not go beyond it."""
    o, c = float(A["open"][p1.bar]), float(A["close"][p1.bar])
    if p1.kind == "H":
        return max(o, c) <= p2.price <= p1.price
    return p1.price <= p2.price <= min(o, c)


def pools(V, t):
    """t ला माहीत pools: [{price, side: buy|sell, src}]. Method: structure swings + equal highs / lows by comparison. Legacy
    (`liquidity_rule = sigma`): σ_1H × liquidity_eq_sigma equal pools + PDH / PDL / PWH / PWL (day / week pools)."""
    lv = V.levels
    out = []
    known = list(lv.known_pivots(t))
    for p in known:
        out.append({"price": float(p.price), "side": "buy" if p.kind == "H" else "sell", "src": "swing"})
    if _method(V):                                                         # an equal pair is ONE pool (the earlier, outer extreme)
        eq, drop = [], set()
        for kind in ("H", "L"):
            ps = sorted((p for p in known if p.kind == kind), key=lambda p: p.bar)
            for p1, p2 in zip(ps[:-1], ps[1:]):
                if _equal(lv.A, p1, p2):
                    eq.append({"price": float(p1.price), "side": "buy" if kind == "H" else "sell", "src": "equal"})
                    drop |= {id(p1), id(p2)}
        return [x for p, x in zip(known, out) if id(p) not in drop] + eq
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


def _sweeps_method(V, t, t0):
    """Method §3: a pool (structure swing / equal) poked beyond in t0 … t and back inside before any swing formed beyond it ⇒ sweep ⚡;
    with at least one close beyond before coming back ⇒ trapped (failed breakout). A swing formed beyond ⇒ accepted (no sweep); still
    beyond at t ⇒ not decided yet. Swings = the finest structure degree known by t."""
    A = V.levels.A
    known0 = [p for p in getattr(V.levels, "_known0", []) if p.confirm_bar <= t]
    sw, tr = [], []
    for p in pools(V, t0):
        pr = p["price"]
        sign = 1 if p["side"] == "buy" else -1
        bw = [i for i in range(t0, t + 1) if ((A["high"][i] if sign > 0 else A["low"][i]) - pr) * sign > 0]
        if not bw:
            continue
        f = bw[0]
        if ((A["close"][t] - pr) * sign > 0) or any(q.bar >= f and (q.price - pr) * sign > 0 and q.kind == ("H" if sign > 0 else "L")
                                                    for q in known0):
            continue
        ext = max(A["high"][f:t + 1]) if sign > 0 else min(A["low"][f:t + 1])
        sw.append({**p, "bar": int(f), "extreme": float(ext)})
        if any((A["close"][i] - pr) * sign > 0 for i in range(f, t + 1)):
            tr.append({"lo": min(pr, ext), "hi": max(pr, ext), "kind": "failed_breakout", "side": p["side"], "bar": int(f)})
    return sw, tr


def sweeps_and_traps(V, t, lookback=None, start=None):
    """Sweeps ⚡ आणि trapped zones in the window start … t (method: the caller's structure window — V22 passes the pullback's start;
    pools known at its start). Legacy (`liquidity_rule = sigma`): the last `lookback` bars, `accept_closes` closes ⇒ acceptance."""
    t0 = max(1, int(start)) if start is not None else max(1, t - int(lookback))
    if _method(V):
        return _sweeps_method(V, t, t0)
    A = V.levels.A
    acc = int(V.s["accept_closes"])
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


SRC_EN = {"swing": "swing", "equal": "EQ", "PDH": "PDH", "PDL": "PDL", "PWH": "PWH", "PWL": "PWL"}


def pool_marks(V, t, per_side=None, max_sigma=None):
    """§7.6 chart साठी: t ला माहीत pools पैकी किंमतीच्या जवळचे (प्रत्येक बाजूला `liq_marks_per_side`, `show_distance_sigma` × σ_1H आत),
    duplicate किंमती (σ_1H × liquidity_eq_sigma आत) एक — PDH / PWH / EQ ला swing पेक्षा प्राधान्य. रिटर्न [{price, side, src, label}]."""
    lv = V.levels
    per_side = int(per_side or V.s["liq_marks_per_side"])
    sg = lv.sig1h[t] if np.isfinite(lv.sig1h[t]) else 0.0
    lim = float(max_sigma or V.s["show_distance_sigma"]) * sg if sg > 0 else np.inf
    tol = float(V.s["liquidity_eq_sigma"]) * sg if not _method(V) else 0.0   # method: the equal pool sits at its swing's own price
    c = float(lv.A["close"][t])
    prio = {"PWH": 0, "PWL": 0, "PDH": 1, "PDL": 1, "equal": 2, "swing": 3}
    out = []
    for side in ("buy", "sell"):
        ps = [p for p in pools(V, t) if p["side"] == side and abs(p["price"] - c) <= lim
              and ((p["price"] >= c) if side == "buy" else (p["price"] <= c))]
        ps.sort(key=lambda p: (prio.get(p["src"], 9), abs(p["price"] - c)))
        kept = []
        for p in ps:
            if all(abs(p["price"] - q["price"]) > tol for q in kept):
                kept.append(p)
        kept.sort(key=lambda p: abs(p["price"] - c))
        for p in kept[:per_side]:
            out.append({**p, "label": f"{SRC_EN.get(p['src'], p['src'])} {'BSL' if side == 'buy' else 'SSL'}"})
    return out
