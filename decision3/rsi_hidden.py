"""decision3/rsi_hidden.py — PA standard §2J (J.2): HIDDEN RSI divergence as CONTINUATION evidence. Evidence only — never a gate, never a
trigger, never part of the conviction label (track T9 wires it into the evidence list later; nothing on the live path reads this module).

Method words. In an uptrend pullback, price makes a HIGHER LOW while RSI makes a LOWER LOW (hidden bull); in a downtrend pullback, price
makes a LOWER HIGH while RSI makes a HIGHER HIGH (hidden bear). The pullback held its structure while momentum dipped further — the trend's
side is still in control (continuation). It is the mirror of the regular divergence (layer 5, `V22.rsi_divergence`), read in the SAME
frame (Abhi L5-a): between the consecutive pushes INSIDE the move into the area — the move begins at the last swing built away from the
area (`move_from`) — at the highest swings2 degree at which that move shows at least two pushes (confirmed swings of the pullback's push
side, after `move_from`, known by t). A swing from before the move began is never compared.

Owner of the RSI and the pairs: `rsi2.engine.Divergence` (Wilder RSI(14) per data segment; RSI at a swing = its extreme inside the swing's
own span; consecutive pushes; forming / confirmed). rsi2 computes hidden pairs only when `div_hidden` is on; its default stays OFF and the
live reader's instance (`V22._rsi`, regular only, engine.py:541 / :554) is untouched — this module builds its OWN instance with
`div_hidden = True` (same frame, same swings2 result `V.res`), cached on the V22 object as `_rsi_hidden`. Turning hidden on never changes
the regular records (each type keeps its own count chain).

Strictness (method words): "higher low" / "lower high" — an EQUAL low / high is a double bottom / top, not a hidden divergence here (rsi2
marks it hidden when RSI is lower; this module does not). A hidden pair whose L2 is later overtaken (price trades below the higher low /
above the lower high, by t) no longer stands — the newer pair is judged on its own (same rule as the regular one).

No look-ahead: everything is read from bars ≤ t (rsi2 history(t): confirmed by t + forming at t; pivots with confirm_bar ≤ t).
No numbers in the reading (RSI period 14 is the indicator's definition, owned by rsi2). RSI is the only indicator.
"""
import pandas as pd

UP, DOWN = 1, -1
SIDE = {UP: "bull", DOWN: "bear"}
PUSH_KIND = {UP: "L", DOWN: "H"}                                        # an uptrend pullback's pushes are its lows (and the mirror)
HELD = {UP: "higher low", DOWN: "lower high"}                           # the pullback held its structure (strict — equal is not)
ROLE = "evidence only (continuation) — never a gate, never a trigger, not part of the label"


def hidden_reader(V):
    """The rsi2 Divergence with hidden pairs ON for V's 15M frame (built once per V22 object, cached as `V._rsi_hidden`; a test may set
    it). The regular reader `V._rsi` and the rsi2 defaults are never touched. Failure ⇒ the reason string (the read is then NA)."""
    D = getattr(V, "_rsi_hidden", None)
    if D is None:
        try:
            from rsi2 import engine as RE
            D = RE.Divergence(V.m15[["timestamp", "open", "high", "low", "close"]], "15M", s={"div_hidden": True}, res=V.res, areas=False)
        except Exception as exc:                                        # noqa: BLE001 — evidence only ⇒ NA with the reason
            D = f"{type(exc).__name__}: {exc}"
        V._rsi_hidden = D
    return D


def _ts(V, D, i):
    if i is None:
        return None
    try:
        return str(pd.Timestamp(V._ts[int(i)]))[:16]
    except Exception:                                                   # noqa: BLE001 — a stand-in V without _ts
        return str(pd.Timestamp(D.B.ts.iloc[int(i)]))[:16]


def frame_of(V, t, d, move_from=None, arm=None, lvl=None, row=None):
    """The reading frame at bar t for trade direction d (+1 = uptrend pullback / bull call, −1 = mirror), first that is known:
    1. `move_from` given (the decision's `commit.move_from_bar`) — exactly the regular divergence's frame (`zone_move`);
    2. a decision row (`V.decide(t)`) ⇒ its `commit.move_from_bar` / `arm_bar`;
    3. an area `lvl` ⇒ V.visit (the same visit `_confirm` reads): move_from = approach_from − 1, arm = visit start;
    4. else the K pullback (`V.pb.at(t, d)`): the pullback begins at the impulse end (`i_end_bar`), `pullback_K`.
    Returns {kind, move_from, arm, why}; move_from None ⇒ not known (NA)."""
    if move_from is not None:
        return {"kind": "zone_move", "move_from": int(move_from), "arm": None if arm is None else int(arm),
                "why": "the move into the area (from its own swing)"}
    if row is not None:
        cm = row.get("commit") or {}
        mf = cm.get("move_from_bar")
        return {"kind": "zone_move", "move_from": None if mf is None else int(mf),
                "arm": None if cm.get("arm_bar") is None else int(cm["arm_bar"]),
                "why": "the move into the area (decision row)" if mf is not None else
                       "the move into the area is not known (no visit / no swing built away from the area yet)"}
    if lvl is not None:
        k = V.pb.at(t, d) or {}
        k0 = k.get("k_open_bar") if k.get("k_open_bar") is not None else t
        vi = V.visit(t, lvl, d, k0)
        if vi.get("start") is None or vi.get("approach_from") is None:
            return {"kind": "zone_move", "move_from": None, "arm": None,
                    "why": "the move into the area is not known (" + (vi.get("why") or "no swing built away from the area yet") + ")"}
        return {"kind": "zone_move", "move_from": int(vi["approach_from"]) - 1, "arm": int(vi["start"]),
                "why": "the move into the area (from its own swing)"}
    k = V.pb.at(t, d) if getattr(V, "pb", None) is not None else None
    if not k or k.get("i_end_bar") is None:
        return {"kind": "pullback_K", "move_from": None, "arm": None, "why": "no trend-side impulse (BOS) ⇒ no pullback to read"}
    return {"kind": "pullback_K", "move_from": int(k["i_end_bar"]), "arm": None,
            "why": "the pullback after the impulse end" + ("" if k.get("open") else " (K not open yet)")}


def _brief(x):
    keep = ("degree", "status", "status_by", "bars", "price_rel", "rsi_diff", "count", "known_time")
    return {**{k: x.get(k) for k in keep}, "L1": {k: x["L1"][k] for k in ("bar", "time", "price", "rsi")},
            "L2": {k: x["L2"][k] for k in ("bar", "time", "price", "rsi")}}


def _one(V, t, d, frame, D):
    side, kind = SIDE[d], PUSH_KIND[d]
    word = "lows" if kind == "L" else "highs"
    base = {"concept": "rsi_hidden_divergence", "kb": "PA standard §2J (J.2) · layer 5 frame (Abhi L5-a)", "t": int(t), "d": int(d),
            "side": side, "frame": {**frame, "move_from_time": _ts(V, D, frame["move_from"]) if not isinstance(D, str) else None},
            "role": ROLE}
    if isinstance(D, str):
        return {**base, "found": None, "na": "rsi2 Divergence (hidden on) failed — " + D, "divergences": [], "statements": []}
    if frame["move_from"] is None:
        return {**base, "found": None, "na": frame["why"], "divergences": [], "degree": None, "pushes": None,
                "statements": [f"hidden {side} divergence: NA — {frame['why']}"]}
    mf, arm = int(frame["move_from"]), frame.get("arm")
    have = sorted(int(g) for g in D.degrees)
    count = {g: sum(1 for p in D.piv[g] if p.kind == kind and mf < p.bar <= t and p.confirm_bar <= t) for g in have}
    two = [g for g in have if count[g] >= 2]
    if not two:
        return {**base, "found": False, "divergences": [], "degree": None, "pushes": count,
                "statements": [f"no hidden {side} divergence: the {'pullback' if frame['kind'] == 'pullback_K' else 'move into the area'} "
                               f"shows fewer than two pushes ({word}) at any degree (from {_ts(V, D, mf)})"]}
    g = max(two)                                                        # the highest degree with at least two pushes inside the move
    B = D.B

    def still_holds(x):                                                 # a later lower low (higher high) beyond L2 breaks the held low
        b, p = int(x["L2"]["bar"]), float(x["L2"]["price"])
        return not (B.L[b + 1:t + 1] < p).any() if d == UP else not (B.H[b + 1:t + 1] > p).any()
    out, broken = [], []
    for x in D.history(t):
        if not (x["side"] == side and x["type"] == "hidden" and x["price_rel"] == HELD[d] and int(x["degree"]) == g
                and int(x["L1"]["bar"]) > mf and (arm is None or int(x["L2"]["bar"]) >= int(arm))):
            continue
        (out if still_holds(x) else broken).append(_brief(x))
    if out:
        y = out[-1]
        st = [f"hidden {side} divergence (D{g}, {y['status']}): price {y['price_rel']} "
              f"{y['L1']['price']:,.2f} → {y['L2']['price']:,.2f} while RSI {y['L1']['rsi']:.2f} → {y['L2']['rsi']:.2f} "
              f"({'lower low' if d == UP else 'higher high'}) — continuation evidence for the {'up' if d == UP else 'down'}trend"]
    else:
        st = [f"no hidden {side} divergence between the pushes ({word}) inside the "
              f"{'pullback' if frame['kind'] == 'pullback_K' else 'move into the area'} at D{g}"
              + (f" ({len(broken)} formed earlier, then price went beyond its L2)" if broken else "")]
    return {**base, "found": bool(out), "divergences": out, "overtaken": broken, "degree": g, "pushes": count, "statements": st}


def read_hidden_divergence(V, t, d=None, *, move_from=None, arm=None, lvl=None, row=None):
    """Hidden RSI divergence at closed bar t (bars ≤ t only). d = +1 (uptrend pullback: higher low + RSI lower low) / −1 (mirror);
    d None ⇒ from the decision row (its trade side) when given, else both sides each in its own K-pullback frame
    ({"bull": …, "bear": …}). Frame: see `frame_of`. Returns plain dicts: {found (True / False / None = NA), divergences [{degree,
    status, L1, L2, price_rel, rsi_diff, count, …}], overtaken, degree, pushes, frame, statements, role}."""
    t = int(t)
    if d is None and row is not None:
        from decision3 import method as M
        lv = row.get("level") or {}
        d = M._dir(row.get("trend_used"), lv.get("role")) or None
    D = hidden_reader(V)
    if d is None:
        return {"concept": "rsi_hidden_divergence", "t": t, "role": ROLE,
                "bull": _one(V, t, UP, frame_of(V, t, UP), D), "bear": _one(V, t, DOWN, frame_of(V, t, DOWN), D)}
    d = UP if int(d) > 0 else DOWN
    return _one(V, t, d, frame_of(V, t, d, move_from, arm, lvl, row), D)


def draw_objects(V, t, d=None, *, read=None, tf="15M", **kw):
    """Chart objects (track T8) for the hidden divergences read at t: per divergence one price-pane line L1 → L2
    (`rsi_hidden_div`) and its RSI-pane line (`rsi_hidden_div_rsi`, p0 / p1 = RSI). Shape {kind, tf, t0, t1, p0, p1, label, state,
    evidence}; state = forming / confirmed / overtaken."""
    r = read if read is not None else read_hidden_divergence(V, t, d, **kw)
    reads = [r[k] for k in ("bull", "bear") if isinstance(r.get(k), dict)] if "bull" in r else [r]
    out = []
    for x in reads:
        for y, state in [(y, y["status"]) for y in x.get("divergences") or []] + [(y, "overtaken") for y in x.get("overtaken") or []]:
            lab = f"hidden {x['side']} div · D{y['degree']} · {state} · RSI {y['L1']['rsi']:.2f} → {y['L2']['rsi']:.2f}"
            ev = (f"{y['price_rel']} with RSI {'lower low' if x['side'] == 'bull' else 'higher high'} — continuation "
                  f"({'not standing: price went beyond L2' if state == 'overtaken' else 'evidence only'})")
            out.append({"kind": "rsi_hidden_div", "tf": tf, "t0": y["L1"]["time"], "t1": y["L2"]["time"], "p0": y["L1"]["price"],
                        "p1": y["L2"]["price"], "label": lab, "state": state, "evidence": ev})
            out.append({"kind": "rsi_hidden_div_rsi", "tf": tf, "t0": y["L1"]["time"], "t1": y["L2"]["time"], "p0": y["L1"]["rsi"],
                        "p1": y["L2"]["rsi"], "label": lab, "state": state, "evidence": ev})
    return out
