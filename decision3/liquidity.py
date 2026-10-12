"""decision3/liquidity.py — spec §7: liquidity नकाशा (`liquidity_map`), sweep ⚡ आणि अडकलेले traders (`trapped_zone`).

Pools (t च्या close ला माहीत तेवढेच):
  • buy-side (वर): confirmed D2 swing highs, equal highs (σ_1H × liquidity_eq_sigma), मागच्या दिवसाचा / आठवड्याचा high (PDH / PWH).
  • sell-side (खाली): swing lows, equal lows, PDL / PWL.
Sweep: किंमत pool पलीकडे (wick किंवा < accept_closes closes) आणि लवकर परत आत close ⇒ ⚡ (acceptance नाही).
Trapped zone: (a) failed breakout — pool पलीकडे ≥ 1 close, मग परत आत `accept_closes` closes ⇒ breakout traders अडकले; पट्टा = [pool, पलीकडचं टोक].
  (b) late_counter — K चा शेवटचा counter push आधीच्या (confirmed D1) counter टोकापलीकडे नवं टोक करून परत आला (close आधीच्या टोकाच्या
      trend-बाजूला) ⇒ उशिरा आलेले counter-trend traders अडकले; पट्टा = [आधीचं टोक, नवं टोक] (`counter_traps`).
  (c) engulfed_counter — K मध्ये trend-विरुद्ध मोठी (candle_read big_body) candle आणि लगेच पुढची trend-दिशेची candle जिची body तिची body
      गिळते ⇒ ते अडकले; पट्टा = त्या counter candle ची body (`counter_traps`).
§7.3 SL: trapped zone च्या पलीकडे (`method.risk`, setting `sl_beyond_trapped`) — तिथे ते exit करतात आणि किंमत आपल्या दिशेने येते.
फक्त पुरावा / chart / SL (gate नाही). Order / broker call नाही. Thresholds नवे नाहीत: candle_read (candle_avg_n) आणि D1 pivots.
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
        before = ((A["high"][t0 - 1] if sign > 0 else A["low"][t0 - 1]) - pr) * sign > 0           # window आधीचा bar (t0 ≥ 1)
        if beyond_w[0] and before:
            continue                                                     # आधीच पलीकडे होती ⇒ pool मधून "गेली" नाही (impulse pool ओलांडून गेला) — sweep नाही
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


def counter_traps(A, t, d, k, s, pivots=None):
    """§7.3 (b) + (c): K (pullback) मधले अडकलेले counter-trend traders — [{lo, hi, kind, side, bar}]. d = trade दिशा (UP ⇒ bull put;
    counter = sellers, side "sell"; DOWN ⇒ counter = buyers, side "buy"). फक्त t च्या close पर्यंतची माहिती (pivots confirm_bar ≤ t).
    K उघडी नाही ⇒ []."""
    from . import method as M
    if not k or not k.get("open") or k.get("k_open_bar") is None:
        return []
    k0 = int(k["k_open_bar"])
    side = "sell" if d == M.UP else "buy"
    out = []
    # (b) late counter push: नवं counter टोक आधीच्या confirmed counter टोकापलीकडे, मग close परत trend-बाजूला
    kx, kb = k.get("k_ext"), k.get("k_ext_bar")
    ie = k.get("i_end_bar")
    ie = k0 if ie is None else int(ie)
    if kx is not None and kb is not None and kb < t and pivots:
        kind = "L" if d == M.UP else "H"                                  # counter पुश चं टोक (UP trend ⇒ pullback खाली ⇒ L)
        prev = [p for p in pivots if p.kind == kind and p.confirm_bar <= t and ie < p.bar < kb and (float(p.price) - kx) * d > 0]   # Pullbacks.legs सारखंच: I_end नंतरचे
        if prev:
            pp = float(max(prev, key=lambda p: p.bar).price)             # शेवटचं आधीचं counter टोक
            if (float(A["close"][t]) - pp) * d > 0:                      # परत: close आधीच्या टोकाच्या trend-बाजूला
                out.append({"lo": min(pp, kx), "hi": max(pp, kx), "kind": "late_counter", "side": side, "bar": int(kb)})
    # (c) counter-trend मोठी candle लगेच trend-दिशेच्या candle ने गिळली (body engulf)
    for i in range(max(k0, 1), t):
        j = i + 1
        oi, ci = float(A["open"][i]), float(A["close"][i])
        oj, cj = float(A["open"][j]), float(A["close"][j])
        if (ci - oi) * d >= 0 or (cj - oj) * d <= 0:
            continue                                                     # i counter-trend आणि j trend-दिशेची हवी
        if not M.candle_read(A, i, s)["big_body"]:
            continue
        lo_i, hi_i = min(oi, ci), max(oi, ci)
        if min(oj, cj) <= lo_i and max(oj, cj) >= hi_i:
            out.append({"lo": lo_i, "hi": hi_i, "kind": "engulfed_counter", "side": side, "bar": int(i)})
    return out


def sl_edge(traps, d, k0=None):
    """§7.3 SL साठी trapped zones ची दूरची कड (UP ⇒ सर्वात खालचा lo; DOWN ⇒ सर्वात वरचा hi); नाही ⇒ None.
    k0 दिला ⇒ फक्त K मध्ये (bar ≥ k0) बनलेले zones — K आधीचा (impulse मधला) pool-cross SL ला लागत नाही."""
    from . import method as M
    if k0 is not None:
        traps = [x for x in traps if x.get("bar") is None or int(x["bar"]) >= int(k0)]
    if not traps:
        return None
    return min(x["lo"] for x in traps) if d == M.UP else max(x["hi"] for x in traps)


SRC_EN = {"swing": "swing", "equal": "EQ", "PDH": "PDH", "PDL": "PDL", "PWH": "PWH", "PWL": "PWL"}


def pool_marks(V, t, per_side=None, max_sigma=None):
    """§7.6 chart साठी: t ला माहीत pools पैकी किंमतीच्या जवळचे (प्रत्येक बाजूला `liq_marks_per_side`, `show_distance_sigma` × σ_1H आत),
    duplicate किंमती (σ_1H × liquidity_eq_sigma आत) एक — PDH / PWH / EQ ला swing पेक्षा प्राधान्य. रिटर्न [{price, side, src, label}]."""
    lv = V.levels
    per_side = int(per_side or V.s["liq_marks_per_side"])
    sg = lv.sig1h[t] if np.isfinite(lv.sig1h[t]) else 0.0
    lim = float(max_sigma or V.s["show_distance_sigma"]) * sg if sg > 0 else np.inf
    tol = float(V.s["liquidity_eq_sigma"]) * sg
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
