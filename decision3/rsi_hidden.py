"""decision3/rsi_hidden.py — PA standard §2J (J.2): HIDDEN RSI divergence as CONTINUATION evidence. Evidence only — never a gate, never a
trigger, never part of the conviction label (track T9 wires it into the evidence list later; nothing on the live path reads this module).

Method words. In an uptrend pullback, price makes a HIGHER LOW while RSI makes a LOWER LOW (hidden bull); in a downtrend pullback, price
makes a LOWER HIGH while RSI makes a HIGHER HIGH (hidden bear). The pullback held its structure while momentum dipped further — the trend's
side is still in control (continuation).

Two labelled readings (both returned; `frame.kind` says which):

1. CLASSIC — the reading (lead decision, provisional; OPEN_QUESTIONS): the CURRENT PULLBACK'S LOW against the TREND'S PREVIOUS HIGHER LOW,
   across the impulse (mirror: the pullback's high against the previous lower high), at the trend's structure degree (`level_degree`, the
   degree whose BOS makes the impulse — `V.pb`), swings confirmed by t. The previous higher low = the impulse's origin swing; the pullback's
   low = the most extreme confirmed swing of that degree after the impulse end. No impulse known ⇒ the last two same-kind swings of that
   degree with an opposite swing between them.
2. INSIDE THE MOVE — the regular divergence's own frame (Abhi L5-a, `V22.rsi_divergence`): between the consecutive pushes inside the
   move into the area (from `move_from`, the last swing built away from the area) at the highest degree with at least two pushes. A swing
   from before the move began is never compared.

Owner of the RSI and the pairs: `rsi2.engine.Divergence` (Wilder RSI(14) per data segment; RSI at a swing = its extreme inside the swing's
own span, between the neighbouring opposite swings of that degree). rsi2 computes hidden pairs only when `div_hidden` is on; its default
stays OFF and the live reader's instance (`V22._rsi`, regular only, engine.py:541 / :554) is untouched — this module builds its OWN
instance with `div_hidden = True` (same frame, same swings2 result `V.res`), cached on the V22 object as `_rsi_hidden`. Turning hidden on
never changes the regular records (each type keeps its own count chain).

Strictness (method words): "higher low" / "lower high" — an EQUAL low / high is a double bottom / top, not a hidden divergence here. A
pair whose second swing is later overtaken (price trades below the higher low / above the lower high, by t) no longer stands.

No look-ahead: everything is read from bars ≤ t (rsi2 history(t); pivots with confirm_bar ≤ t; RSI only up to the swing's confirm bar;
`V.pb` is sequential). No numbers in the reading (RSI period 14 is the indicator's definition, owned by rsi2). RSI is the only indicator.
"""
import pandas as pd

UP, DOWN = 1, -1
SIDE = {UP: "bull", DOWN: "bear"}
PUSH_KIND = {UP: "L", DOWN: "H"}                                        # an uptrend pullback's pushes are its lows (and the mirror)
HELD = {UP: "higher low", DOWN: "lower high"}                           # the pullback held its structure (strict — equal is not)
CLASSIC, INSIDE = "classic (across the impulse)", "inside the move"
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
    2. a decision row (`V.decide(t)`) ⇒ its `commit.move_from_bar` / `arm_bar` (no commit facts but a level ⇒ that level, as 3.);
    3. an area `lvl` ⇒ V.visit (the same visit `_confirm` reads): move_from = approach_from − 1, arm = visit start;
    4. else the K pullback (`V.pb.at(t, d)`): the pullback begins at the impulse end (`i_end_bar`), `pullback_K`.
    Returns {kind, move_from, arm, why}; move_from None ⇒ not known (NA)."""
    if move_from is not None:
        return {"kind": "zone_move", "move_from": int(move_from), "arm": None if arm is None else int(arm),
                "why": "the move into the area (from its own swing)"}
    if row is not None and (row.get("commit") or {}).get("move_from_bar") is None and row.get("level") and lvl is None:
        lvl = row["level"]                                              # ③ not reached ⇒ no commit facts: read the area's own visit
        row = None
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
        mf = vi.get("move_from") if "move_from" in vi else (
            (int(vi["approach_from"]) - 1) if vi.get("approach_from") is not None else None)   # DECISIONS 64: the last away swing
        if vi.get("start") is not None and hasattr(V, "away_na") and V.away_na(t, lvl) is not None:
            return {"kind": "zone_move", "move_from": None, "arm": None, "why": V.AWAY_NA}
        if vi.get("start") is None or mf is None:
            return {"kind": "zone_move", "move_from": None, "arm": None,
                    "why": "the move into the area is not known (" + (vi.get("why") or "no swing built away from the area yet") + ")"}
        return {"kind": "zone_move", "move_from": int(mf), "arm": int(vi["start"]),
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


def _inside(V, t, d, frame, D):
    side, kind = SIDE[d], PUSH_KIND[d]
    word = "lows" if kind == "L" else "highs"
    base = {"reading": INSIDE, "kb": "PA standard §2J (J.2) · layer 5 frame (Abhi L5-a)", "t": int(t), "d": int(d),
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
        st = [f"hidden {side} divergence (inside the move, D{g}, {y['status']}): price {y['price_rel']} "
              f"{y['L1']['price']:,.2f} → {y['L2']['price']:,.2f} while RSI {y['L1']['rsi']:.2f} → {y['L2']['rsi']:.2f} "
              f"({'lower low' if d == UP else 'higher high'}) — continuation evidence for the {'up' if d == UP else 'down'}trend"]
    else:
        st = [f"no hidden {side} divergence between the pushes ({word}) inside the "
              f"{'pullback' if frame['kind'] == 'pullback_K' else 'move into the area'} at D{g}"
              + (f" ({len(broken)} formed earlier, then price went beyond its L2)" if broken else "")]
    return {**base, "found": bool(out), "divergences": out, "overtaken": broken, "degree": g, "pushes": count, "statements": st}


def _rsi_at(D, p, known, side):
    """RSI at a swing (rsi2's rule): its extreme inside the swing's own span — between the neighbouring opposite swings of its degree
    known by t — never past the swing's confirm bar (no look-ahead). None ⇒ warm-up / NaN."""
    opp = sorted(q.bar for q in known if q.kind != p.kind)
    before = [x for x in opp if x < p.bar]
    after = [x for x in opp if x > p.bar]
    lo = before[-1] + 1 if before else p.bar
    hi = max(p.bar, min(int(p.confirm_bar), after[0] - 1) if after else int(p.confirm_bar))
    return D._rsi_ext(p.bar, side, lo, hi)


def _classic(V, t, d, D):
    """CLASSIC hidden divergence: the current pullback's low (high) against the trend's previous higher low (lower high) across the
    impulse, at the trend's structure degree (`level_degree`), swings confirmed by t."""
    side, kind = SIDE[d], PUSH_KIND[d]
    opp_kind = "H" if kind == "L" else "L"
    word, prev = ("low", "higher low") if kind == "L" else ("high", "lower high")
    g = int((getattr(V, "s", None) or {}).get("level_degree", 2))
    base = {"reading": CLASSIC, "kb": "PA standard §2J (J.2) · classic hidden divergence (lead decision, provisional)", "t": int(t),
            "d": int(d), "side": side, "frame": {"kind": "classic_across_impulse", "degree": g}, "role": ROLE, "divergences": [],
            "overtaken": [], "degree": g}
    if isinstance(D, str):
        return {**base, "found": None, "na": "rsi2 Divergence (hidden on) failed — " + D, "statements": []}
    if g not in D.piv:
        return {**base, "found": None, "na": f"the trend's structure degree D{g} is not computed by rsi2",
                "statements": [f"hidden {side} divergence (classic): NA — D{g} not computed by rsi2"]}
    known = [p for p in D.piv[g] if p.confirm_bar <= t]
    k = V.pb.at(t, d) if getattr(V, "pb", None) is not None else None
    if k and k.get("i_end_bar") is not None and k.get("origin_bar") is not None:
        ie = int(k["i_end_bar"])
        a = next((p for p in known if p.kind == kind and p.bar == int(k["origin_bar"])), None)
        if a is None:
            a = next((p for p in reversed(known) if p.kind == kind and p.bar < ie), None)
        cands = [p for p in known if p.kind == kind and p.bar > ie]
        imp = {"bar": ie, "time": str(D.B.ts.iloc[ie]), "price": round(float(k["i_end"]), 2), "from": "the trend's impulse (BOS, V.pb)"}
    else:
        ks = [p for p in known if p.kind == kind]
        mids = [q for q in known if q.kind == opp_kind and ks and q.bar < ks[-1].bar]
        if len(ks) < 2 or not mids:
            return {**base, "found": False, "statements": [f"no hidden {side} divergence (classic, D{g}): fewer than two swing {word}s "
                                                           f"with an impulse between them known by t"]}
        ip = mids[-1]
        a = next((p for p in reversed(ks) if p.bar < ip.bar), None)
        cands = [p for p in ks if p.bar > ip.bar]
        imp = {"bar": int(ip.bar), "time": str(D.B.ts.iloc[ip.bar]), "price": round(float(ip.price), 2),
               "from": "the opposite swing between the two (no impulse known)"}
    base["frame"]["impulse"] = imp
    if a is None:
        return {**base, "found": False, "statements": [f"no hidden {side} divergence (classic, D{g}): the trend's previous {prev} "
                                                       f"(before the impulse) is not known"]}
    if not cands:
        return {**base, "found": False, "statements": [f"no hidden {side} divergence (classic, D{g}): the current pullback has no "
                                                       f"confirmed swing {word} of this degree yet (impulse end {imp['time'][:16]})"]}
    b = min(cands, key=lambda p: (p.price * d, -p.bar))                 # the pullback's extreme (later bar on a tie)
    if D.seg[a.bar] != D.seg[b.bar]:
        return {**base, "found": False, "statements": [f"no hidden {side} divergence (classic, D{g}): the swings are in different "
                                                       f"data segments"]}
    ra, rb = _rsi_at(D, a, known, side), _rsi_at(D, b, known, side)
    if ra is None or rb is None:
        return {**base, "found": None, "na": "RSI not available at a swing (warm-up)",
                "statements": [f"hidden {side} divergence (classic, D{g}): NA — RSI not available at a swing (warm-up)"]}
    dp = float(b.price - a.price)
    if kind == "L":
        rel = "equal low" if dp == 0 else ("higher low" if dp > 0 else "lower low")
    else:
        rel = "equal high" if dp == 0 else ("lower high" if dp < 0 else "higher high")
    r1, r2 = float(ra[0]), float(rb[0])
    rsi_beyond = r2 < r1 if d == UP else r2 > r1                         # RSI makes a lower low (higher high) — strict
    B = D.B
    gone = (B.L[b.bar + 1:t + 1] < b.price).any() if d == UP else (B.H[b.bar + 1:t + 1] > b.price).any()

    def pt(p, rv):
        return {"bar": int(p.bar), "time": str(B.ts.iloc[p.bar]), "price": round(float(p.price), 2), "rsi": round(r1 if p is a else r2, 2),
                "rsi_bar": int(rv[1])}
    rec = {"degree": g, "status": "confirmed", "status_by": "swings confirmed by t", "bars": int(b.bar - a.bar), "price_rel": rel,
           "rsi_diff": round(r2 - r1, 2), "count": None, "known_time": str(B.ts.iloc[max(a.confirm_bar, b.confirm_bar)]),
           "L1": pt(a, ra), "L2": pt(b, rb), "impulse": imp}
    mid = B.H[a.bar + 1:b.bar] if kind == "H" else B.L[a.bar + 1:b.bar]   # the trend's previous swing must be the extreme up to the
    clear = not len(mid) or (float(mid.max()) <= a.price if kind == "H" else float(mid.min()) >= a.price)   # pullback (rsi2's rule)
    rec["consecutive"] = bool(clear)
    is_div = rel == HELD[d] and rsi_beyond and clear
    rw = "lower low" if d == UP else "higher high"
    if is_div and not gone:
        st = [f"hidden {side} divergence (classic, across the impulse, D{g}): the pullback's {word} {b.price:,.2f} is a {rel} than the "
              f"trend's previous {prev} {a.price:,.2f} (impulse to {imp['price']:,.2f}) while RSI {r1:.2f} → {r2:.2f} ({rw}) — "
              f"continuation evidence for the {'up' if d == UP else 'down'}trend"]
    elif is_div:
        st = [f"no hidden {side} divergence (classic, D{g}): it formed ({a.price:,.2f} → {b.price:,.2f}, RSI {r1:.2f} → {r2:.2f}), "
              f"then price went beyond the pullback's {word}"]
    elif not clear:
        st = [f"no hidden {side} divergence (classic, D{g}): price went beyond the {word} {a.price:,.2f} between it and the pullback's "
              f"{word} {b.price:,.2f} — not the trend's previous {prev}"]
    else:
        st = [f"no hidden {side} divergence (classic, D{g}): the pullback's {word} {b.price:,.2f} vs the trend's previous {prev} "
              f"{a.price:,.2f}: price {rel}, RSI {r1:.2f} → {r2:.2f}"]
    return {**base, "found": bool(is_div and not gone), "divergences": [rec] if is_div and not gone else [],
            "overtaken": [rec] if is_div and gone else [], "pair": rec, "statements": st}


def _side(V, t, d, frame, D):
    c, i = _classic(V, t, d, D), _inside(V, t, d, frame, D)
    return {"concept": "rsi_hidden_divergence", "t": int(t), "d": int(d), "side": SIDE[d], "role": ROLE,
            "reading": CLASSIC, "found": c["found"], "classic": c, "inside_move": i, "statements": c["statements"] + i["statements"]}


def read_hidden_divergence(V, t, d=None, *, move_from=None, arm=None, lvl=None, row=None):
    """Hidden RSI divergence at closed bar t (bars ≤ t only). d = +1 (uptrend pullback: higher low + RSI lower low) / −1 (mirror);
    d None ⇒ from the decision row (its trade side) when given, else both sides ({"bull": …, "bear": …}; the inside-the-move read then
    uses each side's K-pullback frame). Per side: {found (= the CLASSIC read: True / False / None = NA), reading, classic {frame
    classic_across_impulse, divergences, overtaken, pair, statements}, inside_move {frame zone_move / pullback_K, divergences,
    overtaken, degree, pushes, statements}, statements}. Frame of the inside read: see `frame_of`."""
    t = int(t)
    if d is None and row is not None:
        from decision3 import method as M
        lv = row.get("level") or {}
        d = M._dir(row.get("trend_used"), lv.get("role")) or None
    D = hidden_reader(V)
    if d is None:
        return {"concept": "rsi_hidden_divergence", "t": t, "role": ROLE,
                "bull": _side(V, t, UP, frame_of(V, t, UP), D), "bear": _side(V, t, DOWN, frame_of(V, t, DOWN), D)}
    d = UP if int(d) > 0 else DOWN
    return _side(V, t, d, frame_of(V, t, d, move_from, arm, lvl, row), D)


def draw_objects(V, t, d=None, *, read=None, tf="15M", **kw):
    """Chart objects (track T8) for the hidden divergences read at t — both readings, named in the label: per divergence one
    price-pane line L1 → L2 (`rsi_hidden_div`) and its RSI-pane line (`rsi_hidden_div_rsi`, p0 / p1 = RSI). Shape {kind, tf, t0, t1,
    p0, p1, label, state, evidence}; state = forming / confirmed / overtaken. `read` may be a whole read, one side, or one reading."""
    r = read if read is not None else read_hidden_divergence(V, t, d, **kw)
    sides = [r[k] for k in ("bull", "bear") if isinstance(r.get(k), dict)] if "bull" in r else [r]
    reads = [x for s in sides for x in ([s["classic"], s["inside_move"]] if "classic" in s else [s])]
    out = []
    for x in reads:
        for y, state in [(y, y["status"]) for y in x.get("divergences") or []] + [(y, "overtaken") for y in x.get("overtaken") or []]:
            lab = (f"hidden {x['side']} div ({x.get('reading', INSIDE)}) · D{y['degree']} · {state} · "
                   f"RSI {y['L1']['rsi']:.2f} → {y['L2']['rsi']:.2f}")
            ev = (f"{y['price_rel']} with RSI {'lower low' if x['side'] == 'bull' else 'higher high'} ({x.get('reading', INSIDE)}) — "
                  f"continuation ({'not standing: price went beyond L2' if state == 'overtaken' else 'evidence only'})")
            out.append({"kind": "rsi_hidden_div", "tf": tf, "t0": y["L1"]["time"], "t1": y["L2"]["time"], "p0": y["L1"]["price"],
                        "p1": y["L2"]["price"], "label": lab, "state": state, "evidence": ev})
            out.append({"kind": "rsi_hidden_div_rsi", "tf": tf, "t0": y["L1"]["time"], "t1": y["L2"]["time"], "p0": y["L1"]["rsi"],
                        "p1": y["L2"]["rsi"], "label": lab, "state": state, "evidence": ev})
    return out
