"""decision3/trendline.py — थर v2.2 पायरी ⑤ (spec §1 ⑤): K ची आतली तिरकी रेघ आणि तिचा trend-दिशेने close-break ⇒ grade + (gate नाही).

रेघ (t ला माहीत तेवढ्यावरूनच):
  • बिंदू = I_end (K ची सुरुवात) + K मधले confirmed (confirm_bar ≤ t) counter-बाजूचे D`tl_degree` pivots. Bear call (d = DOWN): K वर
    चढते ⇒ खालचे बिंदू (I_end low + L pivots), रेघ चढती; bull put आरसा.
  • शेवटचे दोन बिंदू जे K च्या दिशेने सरकलेत (DOWN ⇒ दुसरा low वर) ⇒ रेघ. स्पर्श = रेघेपासून σ_1H × tl_touch_sigma च्या आत असलेले
    बिंदू (दोन anchors स्वतः = 2 स्पर्श ⇒ spec "K चे ≥ 2 स्पर्श" default ला पूर्ण; जास्त स्पर्श = माहिती; tl_min_touches > 2 ⇒ कडक).
  • Break = रेघ बनल्यानंतरच्या (दुसऱ्या बिंदूचा confirm_bar नंतर) bar चा close रेघेपलीकडे trend-दिशेने (DOWN ⇒ खाली).
रेघ नसेल (बिंदू < 2) ⇒ None (NA ⇒ conviction बेरजेत नाही). Order / broker / AI call नाही.

वरचे σ / स्पर्श-संख्या नियम = `line_rule = "sigma"` (जुनं, what-if). Default `line_rule = "logic"` (method §3 Lines, K6):
  • रेघ = दोन वेगळे reactions (मधे उलट swing — `separate`); स्पर्श = candle ची wick रेघेपर्यंत, body बाजूला (`touches`); संख्या / σ नाही.
  • दोन reactions मधे कोणताही close रेघेपलीकडे नाही; त्यानंतर रेघ तुटते फक्त close पलीकडे + पलीकडे swing ने (`broken_by`, K6.5) —
    परत आलेला close = throw-over, रेघ उभी.
  • K रेघ: trigger = bar t (commitment candle) चा close-through; आधीच गेलेली रेघ ⇒ `broken_before`, trigger नाही.
  • Confluence = रेघ area च्या पट्ट्यातून, किंवा area मधून उठलेली reaction रेघेजवळ वळली (`reaction_touch`, Abhi 4 B) ⇒ तोच area,
    "tl" label + "confluence: line (touch N)" (Abhi L4-g: touches by reactions; नवा / अरुंद पट्टा नाही).
"""
import numpy as np

from . import flip as FL

UP, DOWN = 1, -1


def _logic(s):
    r = s.get("line_rule", "logic")
    if r not in ("logic", "sigma"):
        raise ValueError(f"line_rule {r!r} — logic / sigma पैकी")
    return r == "logic"


def touches(A, b, y, kind):
    """Method §3 Lines: candle b touches a line at price y when its wick reaches the line while its body stays on the respected side —
    swing high (kind "H", line above price): body top ≤ y ≤ high; swing low: low ≤ y ≤ body bottom. A comparison, never a tolerance."""
    o, c = float(A["open"][b]), float(A["close"][b])
    if kind == "H":
        return bool(max(o, c) <= y <= float(A["high"][b]))
    return bool(float(A["low"][b]) <= y <= min(o, c))


def _cb(p):
    """A swing's confirmation bar (the bar it is KNOWN at); swings without one (old callers) ⇒ its own bar."""
    return int(getattr(p, "confirm_bar", p.bar))


def broken_by(A, pivs, kind, line, side, start, end, rule=None):
    """Method §3 / K6.5 (as an area): a line is broken by a close beyond it (`side` +1 = above) AND a swing formed beyond it after that
    close (pivs = swings known at the read bar); a close that comes back before any such swing = a throw-over (noise).
    rule "hold" (BREAK-1, DECISIONS 60 — default): the swing is the HOLD side's own (`flip.hold_kind`: a pullback low above a line broken
    up, a pullback high below a line broken down), and every close from the first one beyond through the bar that CONFIRMS it stays
    beyond (a push that turns back first = a sweep). "swing_beyond" (what-if) = the earlier reading: a swing of `kind` (the line's own
    kind — the push's extreme) beyond, closes beyond up to its bar.
    Bars start … end only. Returns the bar of the close that began that excursion, or None."""
    if FL.hold_rule({"break_hold_rule": rule}) == "follow_through":      # DECISIONS 76 (default): follow-through
        return follow_through_break(A["close"], pivs, line, side, start, end)[0]
    hold = FL.hold_rule({"break_hold_rule": rule}) == "hold"           # None ⇒ the registered default
    want = FL.hold_kind(side > 0) if hold else kind

    def beyond(i):
        return (float(A["close"][i]) - line(i)) * side > 0
    for i in range(start, end + 1):
        if beyond(i) and any(p.kind == want and i <= p.bar <= end and (float(p.price) - line(p.bar)) * side > 0 and
                             (not hold or _cb(p) <= end) and
                             all(beyond(j) for j in range(i, (_cb(p) + 1) if hold else p.bar)) for p in pivs):
            return i
    return None


def separate(pivs, b1, b2, kind):
    """Method §3: two anchors are separate reactions when price left the line between them — a swing of the opposite kind lies between."""
    return any(p.kind != kind and b1 < p.bar < b2 for p in pivs)


def touch_groups(A, known, kind, line, b1, b2, t):
    """Abhi (L4-g 1): touches are counted by REACTIONS, not contacts. A contact = an anchor, or a candle whose wick reaches the line with
    its body on its side (`touches`), b1 … t. Contacts with no real opposite swing of the line's structure between them (`known` = the
    line's own degree) are one touch. Returns the touches in order, each the list of its contact bars."""
    groups = []
    for b in range(int(b1), int(t) + 1):
        if not (b in (b1, b2) or touches(A, b, line(b), kind)):
            continue
        if groups and not separate(known, groups[-1][-1], b, kind):
            groups[-1].append(b)
        else:
            groups.append([b])
    return groups


def k_line(V, t, d, k):
    """K (dict, Pullbacks.at) साठी t ला रेघ: {p1, p2, slope, touches, value_t, broken, break_bar} किंवा None."""
    if not k or not k.get("open") or d not in (UP, DOWN):
        return None
    s = V.s
    A = V.levels.A
    deg = int(s["tl_degree"])
    kind = "L" if d == DOWN else "H"                                     # K चा counter-move: DOWN ⇒ K वर (lows ची रेघ)
    pts = [(int(k["i_end_bar"]), float(k["i_end"]))]
    for p in sorted(V.res["pivots"][deg], key=lambda p: p.bar):
        if p.kind == kind and p.bar > k["i_end_bar"] and p.confirm_bar <= t:
            pts.append((int(p.bar), float(p.price)))
    if len(pts) < 2:
        return None
    logic = _logic(s)
    known = [p for p in V.res["pivots"][deg] if p.confirm_bar <= t]
    pair = None
    for j in range(len(pts) - 1, 0, -1):                                 # शेवटची जोडी जी K च्या दिशेने सरकली (logic: दोन वेगळे reactions)
        for i in range(j - 1, -1, -1):
            (b1, y1), (b2, y2) = pts[i], pts[j]
            if b2 > b1 and (y2 - y1) * (-d) > 0 and (not logic or separate(known, b1, b2, kind)):
                pair = (pts[i], pts[j])
                break
        if pair:
            break
    if pair is None:
        return None
    (b1, y1), (b2, y2) = pair
    slope = (y2 - y1) / (b2 - b1)
    if logic:                                                              # method §3: the two anchors (separate reactions) are the line;
        n_t = sum(1 for b, y in pts if b >= b1 and (b in (b1, b2) or touches(A, b, y1 + slope * (b - b1), kind)))   # touches = facts
    else:
        sg = V.levels.sig1h[t] if np.isfinite(V.levels.sig1h[t]) else 0.0
        tol = max(float(s["tl_touch_sigma"]) * sg, 1e-6 * max(abs(y1), abs(y2)))   # σ NaN ⇒ float-त्रुटीमुळे anchor गळू नये
        n_t = sum(1 for b, y in pts if b >= b1 and abs(y - (y1 + slope * (b - b1))) <= tol)
        if n_t < int(s["tl_min_touches"]):
            return None
    conf2 = max([p.confirm_bar for p in V.res["pivots"][deg] if p.bar == b2 and p.kind == kind] or [b2])
    start = max(conf2, b2) + 1
    brk = None
    for i in range(start, t + 1):
        line_i = y1 + slope * (i - b1)
        if (A["close"][i] - line_i) * d > 0:
            brk = i
            break
    out = {"p1": [b1, round(y1, 2)], "p2": [b2, round(y2, 2)], "slope": round(slope, 4), "touches": n_t,
           "value_t": round(y1 + slope * (t - b1), 2), "broken": brk is not None, "break_bar": brk}
    if logic:                                                              # method §3 trigger form: the correction's own line closed through
        def line(b):                                                       # BY the commitment candle (bar t); before it the line is gone only
            return y1 + slope * (b - b1)                                   # by a close beyond + a swing beyond (K6.5) — a close that came
        hk = _known_fine(V, t) if FL.hold_rule(s) == "hold" else None
        gone = broken_by(A, known if hk is None else hk, kind, line, d, start, t - 1, FL.hold_rule(s))   # a throw-over: the line stands
        beyond = (lambda i: (float(A["close"][i]) - line(i)) * d > 0)      # noqa: E731
        now = gone is None and t >= start and beyond(t) and (t == start or not beyond(t - 1))
        out.update(broken=bool(now), broken_before=gone, break_bar=t if now else gone)
    return out


# ------------------------------------------------------------------------------------------------ ② तिरकी S/R (Abhi, 12 Oct)
def swing_line(V, t, d):
    """Trade-बाजूची तिरकी रेघ (spec ② "trend-दिशेची trendline रेघ तिथे (+)"; "तीच साखळी, मृत्यू पलीकडच्या swing ने"), t ला माहीत
    trend-degree (`level_degree`, D2) swings वरून: bear call (d = DOWN) ⇒ उतरती resistance — शेवटचा confirmed swing high (p2) आणि त्याआधीचा
    त्याच्यापेक्षा उंच high (p1) ज्यांच्यामधला कोणताही high रेघेपलीकडे (वर, σ_1H × tl_touch_sigma पेक्षा जास्त) नाही; bull put आरसा (चढती
    support, lows). नवा swing रेघेपलीकडे ⇒ तोच शेवटचा swing ⇒ जुनी रेघ आपोआप मेली; p2 नंतर (t − 1 पर्यंत) एखादा close रेघेपलीकडे ⇒ रेघ
    तुटली (k_line सारखं; t चा स्वतःचा close = ③ breakout तपासणी). रिटर्न {p1, p2, slope, touches, value_t, tol} / None.
    (वरचं = line_rule "sigma". Logic: जोडी = दोन वेगळे reactions, मधे कोणताही close पलीकडे नाही; p2 नंतर रेघ फक्त close + swing
    पलीकडे ने मरते; touches = candle ने; tol = 0.)"""
    if d not in (UP, DOWN):
        return None
    lv = V.levels
    kind = "H" if d == DOWN else "L"
    known = [p for p in lv.known_pivots(t) if p.bar <= t]
    pts = sorted(((int(p.bar), float(p.price)) for p in known if p.kind == kind), key=lambda x: x[0])
    if len(pts) < 2:
        return None
    sg = lv.sig1h[t] if np.isfinite(lv.sig1h[t]) else 0.0
    b2, y2 = pts[-1]
    logic = _logic(V.s)
    tol = 0.0 if logic else max(float(V.s["tl_touch_sigma"]) * sg, 1e-6 * abs(y2))
    for i in range(len(pts) - 2, -1, -1):
        b1, y1 = pts[i]
        if b1 >= b2 or (y2 - y1) * d <= 0:                                 # DOWN ⇒ p2 खाली (lower high); UP ⇒ p2 वर (higher low)
            continue
        slope = (y2 - y1) / (b2 - b1)

        def line(b, y1=y1, b1=b1, slope=slope):
            return y1 + slope * (b - b1)
        if logic:                                                          # method: two separate reactions, and no candle closes through the
            if not separate(known, b1, b2, kind) or \
                    any((lv.A["close"][j] - line(j)) * (-d) > 0 for j in range(b1 + 1, b2)):   # line between them (a wick = touch / sweep)
                continue
            hk = _known_fine(V, t) if FL.hold_rule(V.s) == "hold" else None
            if broken_by(lv.A, known if hk is None else hk, kind, line, -d, b2 + 1, t - 1, FL.hold_rule(V.s)) is not None:   # after p2:
                # a swing beyond that HOLDS (K6.5, BREAK-1);
                continue                                                   # a close that came back = throw-over, the line stands. (Guard: a
                # swing of this kind after p2 is itself the newest pivot ⇒ it becomes p2 and the line is redrawn through it — "same chain")
        else:
            if any((y - line(b)) * (-d) > tol for b, y in pts[i + 1:-1]):  # मधला swing रेघेपलीकडे ⇒ ही जोडी रेघ नाही
                continue
            C = lv.A["close"]
            if any((C[j] - line(j)) * (-d) > 0 for j in range(b2 + 1, t)):  # p2 नंतर (t − 1 पर्यंत) close रेघेपलीकडे ⇒ रेघ तुटली
                continue
        if logic:                                                          # Abhi L4-g (1): touches by reactions (information)
            groups = touch_groups(lv.A, known, kind, line, b1, b2, t)
            return {"p1": [b1, round(y1, 2)], "p2": [b2, round(y2, 2)], "slope": round(slope, 4), "touches": len(groups),
                    "touch_groups": groups, "value_t": round(line(t), 2), "tol": 0.0}
        n_t = sum(1 for b, y in pts[i:] if abs(y - line(b)) <= tol)
        return {"p1": [b1, round(y1, 2)], "p2": [b2, round(y2, 2)], "slope": round(slope, 4), "touches": n_t,
                "value_t": round(line(t), 2), "tol": round(tol, 2)}
    return None


def reaction_touch(V, t, d, ln):
    """Abhi (layer 4 B): a reaction that rises out of (falls out of) an area and turns at the line is a touch of that line. The turn = a
    swing of the structure (finest degree, confirmed by t ⇒ the move then went away from the line) that stays short of the line; no
    candle closes beyond the line. "The previous touch" = the last turn that reached the line (its second anchor, or a later swing
    whose wick reached it — OPEN_QUESTIONS L4-f).
    Abhi (L4-g): one reaction = the move between two real opposite swings of the line's structure (its degree, `known_pivots`).
    (2) The touch point is the reaction's own turn — its closest approach to the line; a later turn of the SAME reaction that stays away
    does not remove it (the label holds for that visit); a new opposite structure swing starts a new reaction, and the old touch is then
    history. (1) Touches are counted by reactions: the line's contact groups (`touch_groups`) and the earlier reactions that turned at
    the line out of an area (that area alive then); from the third touch on it is a trade location while the line is unbroken.
    Returns {bar, price, leg_from, touch_no, trade_location} or None; `areas_out_of` decides which areas the reaction rose out of."""
    if ln is None or d not in (UP, DOWN):
        return None
    lv = V.levels
    A = lv.A
    kind = "H" if d == DOWN else "L"
    side = 1 if d == DOWN else -1                                          # beyond the line = above (DOWN, a line of highs) / below
    (b1, y1), (b2, _), sl = ln["p1"], ln["p2"], ln["slope"]

    def line(b):
        return y1 + sl * (b - b1)

    def gap(p):                                                            # ≥ 0: the turn stays on the line's side
        return (line(p.bar) - float(p.price)) * side

    def beyond(j):
        return (float(A["close"][j]) - line(j)) * side > 0
    known = [p for p in getattr(lv, "_known0", []) if p.confirm_bar <= t]
    struct = list(lv.known_pivots(t)) if hasattr(lv, "known_pivots") else known   # the line's own structure (its degree)
    cuts = sorted({int(p.bar) for p in struct if p.kind != kind and b2 < p.bar <= t})   # real opposite swings ⇒ reaction boundaries
    turns = sorted((p for p in known if p.kind == kind and b2 < p.bar <= t), key=lambda p: p.bar)
    if not turns or gap(turns[-1]) <= 0:                                   # no turn yet, or the latest one is a candle touch itself
        return None
    prev = max((q.bar for q in turns if gap(q) <= 0), default=b2)          # the last time a candle reached the line
    start = max([prev] + [c for c in cuts if c < turns[-1].bar])           # this reaction began at the later of the two
    if any(c > start for c in cuts):                                       # an opposite structure swing after the turn: the reaction is over
        return None
    since = [q for q in turns if q.bar > start]
    if not since:
        return None
    last = min(since, key=lambda q: (gap(q), q.bar))                       # the reaction's own turn: its closest approach
    if any(beyond(j) for j in range(prev + 1, t + 1)):                     # a close beyond the line (also after the turn: price has gone
        return None                                                        # through, the meeting is over)
    leg = max((q.bar for q in known if q.kind != kind and q.bar < last.bar), default=start)
    no = _touch_no(V, t, d, ln, last.bar, struct, known, kind, gap, beyond)
    return {"bar": int(last.bar), "price": float(last.price), "leg_from": int(leg), "touch_no": no, "trade_location": no >= 3}


def _touch_no(V, t, d, ln, bar, struct, known, kind, gap, beyond):
    """Abhi L4-g (1): the touch number of a reaction turning at `bar` — the line's touches before it, by reactions: its contact groups and
    each earlier reaction (between two opposite structure swings, no contact, no close beyond) whose closest turn rose out of an area
    alive at that time. Events with no opposite structure swing between them are one touch."""
    (b1, _), (b2, _) = ln["p1"], ln["p2"]
    lv = V.levels
    events = [g[0] for g in (ln.get("touch_groups") or [[b1], [b2]]) if g[0] < bar]
    contacts = sorted(b for g in (ln.get("touch_groups") or [[b1], [b2]]) for b in g if b < bar)
    cuts = sorted({int(p.bar) for p in struct if p.kind != kind and b2 < p.bar < bar})
    snap = getattr(lv, "snapshot", None)
    role = "resistance" if d == DOWN else "support"
    for lo, hi in zip([b2] + cuts, cuts):                                  # every completed reaction before this one
        if any(lo < b < hi for b in contacts) or any(beyond(j) for j in range(lo + 1, hi + 1)):
            continue
        tt = [q for q in known if q.kind == kind and lo < q.bar < hi and gap(q) > 0 and q.confirm_bar <= hi]
        if not tt or snap is None:
            continue
        q = min(tt, key=lambda q: (gap(q), q.bar))
        legf = max((p.bar for p in known if p.kind != kind and p.bar < q.bar), default=lo)
        cands = [x for x in snap(int(q.confirm_bar)) if x.get("role") == role]
        if areas_out_of(V, {"bar": int(q.bar), "price": float(q.price), "leg_from": int(legf)}, d, cands):
            events.append(int(q.bar))
    events = sorted(events)
    n = 0
    for i, e in enumerate(events + [bar]):
        if i == 0 or e == b2 or separate(struct, events[i - 1], e, kind):   # the two anchors are two reactions by construction
            n += 1
    return n


def areas_out_of(V, rt, d, cands):
    """The areas a reaction-touch rose out of (fell out of): some candle of the reaction leg was inside the area and the turn is beyond the
    area's line-side edge (above it for a line of highs)."""
    if rt is None:
        return []
    A = V.levels.A
    out = []
    for x in cands:
        lo, hi = float(x["lo"]), float(x["hi"])
        inside = any(A["low"][j] <= hi and A["high"][j] >= lo for j in range(rt["leg_from"], rt["bar"] + 1))
        if inside and ((rt["price"] > hi) if d == DOWN else (rt["price"] < lo)):
            out.append(x)
    return out


def _labelled(x, ln, rt=None):
    lab = x.get("confluence_label")
    no = (rt or {}).get("touch_no")
    tag = f"line (touch {no})" if no else "line"                           # Abhi L4-g: the touch number is information
    return {**x, "births": list(x["births"]) + ["tl"], "tl": ln, "confluence_line": True, "line_touch": rt,
            "confluence_label": (lab + "; " + tag) if lab else "confluence: " + tag}


def confluence_areas(V, t, d, cands):
    """Abhi (12 Oct): तिरकी रेघ + horizontal trade-बाजूचा level ⇒ confluence area = दोघांच्या पट्ट्यांचा overlap (रेघेचा पट्टा = t ला
    रेघेची किंमत ± max(σ_1H × tl_touch_sigma, अर्धी किमान level रुंदी); overlap किमान level रुंदीपेक्षा अरुंद ⇒ मध्याभोवती किमान रुंदी).
    cands = ② चे active levels (`Levels.active`, तोच जवळचा-N संच — वेगळी अंतर-मर्यादा नाही); area किंमतीच्या चुकीच्या बाजूला ⇒ नाही. रेघ फक्त t ला माहीत swings वरून (lookahead नाही); स्पर्श < tl_min_touches ⇒
    काहीच नाही. रेघ एकटी area नाही (spec ②: level जन्म a–d; OPEN_QUESTIONS). रिटर्न [area dict] (births + "tl", `tl` = रेघ;
    "tl" grade वाढवत नाही — parent level चा ★ तसाच, confluence फक्त पुरावा-नोंद, OPEN_QUESTIONS D12-6).
    (वरचं = line_rule "sigma". Logic: रेघ t ला area च्या पट्ट्यातून जाते, किंवा area मधून उठलेली reaction रेघेजवळ वळली (Abhi 4 B) ⇒
    तोच area, births + "tl", confluence_line, "confluence: line" — overlap / नवा पट्टा नाही; engine.step2 तो area जागीच बदलतो.)"""
    ln = swing_line(V, t, d)
    if ln is not None and _logic(V.s):                                     # method §3: where a line and an area meet = the strongest
        v = ln["value_t"]                                                  # location — the area itself, labelled (never a new or
        rt = reaction_touch(V, t, d, ln)                                   # narrowed band): the line passes through the area, or a
        out_of = {x["id"] for x in areas_out_of(V, rt, d, cands)}           # reaction rose out of it and turned at the line (Abhi, 4 B)
        return [_labelled(x, ln, rt if x["id"] in out_of else None) for x in cands
                if float(x["lo"]) <= v <= float(x["hi"]) or x["id"] in out_of]
    if ln is None or ln["touches"] < int(V.s["tl_min_touches"]):
        return []
    lv = V.levels
    sg = lv.sig1h[t] if np.isfinite(lv.sig1h[t]) else 0.0
    wmin = float(V.s["level_min_width_sigma"]) * sg
    hw = max(ln["tol"], wmin / 2.0)
    v = ln["value_t"]
    c = float(lv.A["close"][t])
    out = []
    for x in cands:
        lo, hi = max(float(x["lo"]), v - hw), min(float(x["hi"]), v + hw)
        if lo > hi:
            continue
        if hi - lo < wmin:
            m = (lo + hi) / 2.0
            lo, hi = m - wmin / 2.0, m + wmin / 2.0
        if (d == DOWN and hi < c) or (d == UP and lo > c):                 # चुकीच्या बाजूला (resistance close खाली / support वर) ⇒ नाही
            continue
        dist = 0.0 if lo <= c <= hi else (lo - c if c < lo else c - hi)
        out.append({**x, "id": f"{x['id']}+TL", "lo": round(lo, 2), "hi": round(hi, 2), "births": list(x["births"]) + ["tl"],
                    "dist": round(dist, 2), "above": lo > c, "below": hi < c, "tl": ln, "parent_level": x["id"]})
    return sorted(out, key=lambda a: a["dist"])                           # Abhi's method §4: every area ahead, nearest first


# ------------------------------------------------------------------------------------------------ both channel lines (Abhi 21 Oct)
FAMILIES = (("H", 1), ("H", -1), ("L", 1), ("L", -1))                      # (swings of, slope): rising / falling line of highs / lows


def _broken_at(C, pivs, kind, line, side, start, end, hold=False):
    """`broken_by` (method §3 / K6.5: a close beyond AND a swing of `kind` formed beyond after it, no close back between) — the same
    answer, read run by run instead of bar by bar (the earliest excursion close that a later swing beyond confirms). hold (BREAK-1,
    DECISIONS 60): the caller passes the hold side's kind (`flip.hold_kind`) and the closes must stay beyond from the run's first close
    through the swing's CONFIRMATION bar (a confirming bar that already closed back = no hold — the #373 lesson, mirrored for lines)."""
    if end < start:
        return None
    b = np.arange(start, end + 1)
    bey = (C[start:end + 1] - np.array([line(i) for i in b])) * side > 0
    best = None
    for p in pivs:
        pb = int(p.bar)
        if p.kind != kind or not (start <= pb <= end) or (float(p.price) - line(pb)) * side <= 0:
            continue
        j = pb - start                                                     # the run of beyond closes that reaches p (bars i … p.bar − 1)
        if hold:                                                           # the run holds p's own bar … its confirmation bar
            cb = _cb(p)
            if cb > end or not bool(bey[j:cb - start + 1].all()):
                continue
            i = j
            while i > 0 and bey[i - 1]:
                i -= 1
            best = i + start if best is None else min(best, i + start)
            continue
        if j > 0 and bey[j - 1]:
            i = j - 1
            while i > 0 and bey[i - 1]:
                i -= 1
        elif bey[j]:
            i = j
        else:
            continue
        best = i + start if best is None else min(best, i + start)
    return best


def follow_through_break(C, known, line, side, start, end):
    """DECISIONS 76 (owner rule; lines as areas, every TF): a line is BROKEN when, after a close beyond it (`side` +1 = above), a candle
    of the line's chart CLOSES beyond the most recent prior confirmed swing of the line's own TF on the far side (DECISIONS 82) (`known` = the swings the
    line is drawn on: a swing high above the line for a break up, a swing low below it for a break down — formed before the
    excursion's first close, its extreme beyond the line at the judged bar, confirmed by that bar); fresh ground (none) ⇒ a new own-TF
    swing forms beyond from the excursion on, is confirmed, and a candle closes beyond it. A close back on the line's side first = a
    false break (the excursion ends); a wick through the swing that closes back = a sweep of that swing. Bars start … end only; swings
    confirmed by the judged bar only. Returns (excursion start, known bar, open excursion start): the first two = the break (None if
    none), the last = the start of the excursion still beyond at `end` without follow-through (BEYOND_NOT_BROKEN) or None."""
    if end < start:
        return None, None, None
    kind = "H" if side > 0 else "L"
    ps = [p for p in known if p.kind == kind]
    pb = np.array([int(p.bar) for p in ps], int)
    pp = np.array([float(p.price) for p in ps], float)
    pc = np.array([_cb(p) for p in ps], int)
    ex = None
    for u in range(int(start), int(end) + 1):
        lu = float(line(u))
        if (float(C[u]) - lu) * side <= 0:
            ex = None
            continue
        if ex is None:
            ex = u
        if not len(ps):
            continue
        ok = (pc <= u) & ((pp - lu) * side > 0)
        pre = ok & (pb < ex)
        pool = pre if pre.any() else (ok & (pb >= ex))
        if not pool.any():
            continue
        ix = np.flatnonzero(pool)                                          # DECISIONS 82: the MOST RECENT swing beyond (its bar)
        tgt = float(pp[ix[np.lexsort((pc[ix], pb[ix]))[-1]]])
        if (float(C[u]) - tgt) * side > 0:
            return ex, u, None
    return None, None, ex


def _pair_ok(C, known, b1, y1, b2, y2, kind):
    """Method §3 Lines (logic): two separate reactions and no candle closes through the line between them (a wick = touch / sweep)."""
    if not separate(known, b1, b2, kind):
        return False
    side = 1 if kind == "H" else -1                                        # beyond a line of highs = above; of lows = below
    if b2 - b1 < 2:
        return True
    j = np.arange(b1 + 1, b2)
    return not bool((((C[b1 + 1:b2] - (y1 + (y2 - y1) / (b2 - b1) * (j - b1))) * side) > 0).any())


def _known_deg(V, t, g):
    """Swings of degree g known by bar t (confirm_bar ≤ t), in bar order. The trend degree (`level_degree`) = the Levels' own pivots."""
    lv = V.levels
    if g == int(V.s.get("level_degree", 2)):
        return sorted((p for p in lv.known_pivots(t) if p.bar <= t), key=lambda p: p.bar)
    res = getattr(lv, "res", None) or {}
    return sorted((p for p in (res.get("pivots") or {}).get(g, []) if p.confirm_bar <= t and p.bar <= t), key=lambda p: p.bar)


def _known_fine(V, t):
    """BREAK-1 (DECISIONS 60, areas AND lines alike): the swings that prove a HOLD beyond a line are the hold degree (A-L1, DECISIONS
    71: a D0 swing, `break_hold_degree`; the degree stays a setting), exactly the swings the K4 area hold reads
    (`Levels._known_hold`), confirmed by bar t, in bar order. A 1H line's own degree (D2) would almost never show a pullback swing on the
    far side before price leaves again."""
    lv = V.levels
    k0 = getattr(lv, "_known_hold", getattr(lv, "_known0", None))     # A-L1 (DECISIONS 71): the hold degree (D0 default)
    if k0 is None:
        return None
    return sorted((p for p in k0 if int(p.confirm_bar) <= t and int(p.bar) <= t), key=lambda p: p.bar)


TF_OF_DEGREE = {2: "1H", 1: "15M"}


def line_degrees(V):
    """The structures the lines are drawn on: the trend degree (`level_degree`, the 1H areas' own swings — the main swings) and the
    finest structure below it (D1, the 15M structure) — Abhi 21 Oct "on each timeframe"."""
    g = int(V.s.get("level_degree", 2))
    return tuple(dict.fromkeys((g, 1)))


def channel_lines(V, t, degree=None):
    """Abhi 21 Oct — lines on BOTH sides and in BOTH directions, whatever the Daily trend: for each family (a rising / falling line
    through swing highs / lows of `degree`, default the trend degree `level_degree`, known by t) the newest line by the method §3 logic
    (`swing_line`'s own pair rule: two separate reactions, no close through between them), with its anchors, touches (by reactions,
    `touch_groups`) and break state by the existing definition (a close beyond + a swing beyond — K6.5, `broken_by`). A swing that breaks
    a line is itself the newest swing, so the line through it is the chain's new line; the line it broke is kept as that family's
    `broken` line (the newest broken one), so a retest of it can be read.
    Returns [{family, kind, slope_dir, degree, tf, p1, p2, slope, touches, touch_groups, value_t, broken, break_bar, break_side, state,
    id}]. `swing_line` (the trade-side line the decision has always used — confluence, ② labels) is unchanged."""
    g = int(V.s.get("level_degree", 2)) if degree is None else int(degree)
    memo = V.__dict__.setdefault("_chan_memo", {})
    if (t, g) in memo:
        return memo[(t, g)]
    out = lines_on(V.levels.A, _known_deg(V, t, g), t, g, TF_OF_DEGREE.get(g, f"D{g}"), f"D{g}", FL.hold_rule(V.s),
                   hold_known=_known_fine(V, t))
    memo[(t, g)] = out
    return out


def lines_on(A, known, t, degree, tf, prefix, rule=None, hold_known=None):
    """T3 — the core of `channel_lines` for ANY timeframe: A = that timeframe's bars (open / high / low / close arrays; bar index = A's),
    known = its own swings known at its bar t (kind, price, bar), in bar order. The same method §3 / K6.5 reading on every timeframe;
    ids are "<prefix>:<kind><+|->:<b1>-<b2>". rule = `break_hold_rule` (None ⇒ the registered default; BREAK-1); hold_known = the
    swings that prove a hold (the finest structure, `_known_fine`; None ⇒ `known`). Comparison only."""
    rule = FL.hold_rule({"break_hold_rule": rule})
    hk = known if hold_known is None else hold_known
    g = degree
    C = A["close"]
    out = []
    for kind, sd in FAMILIES:
        side = 1 if kind == "H" else -1
        pts = [(int(p.bar), float(p.price)) for p in known if p.kind == kind]
        bars = np.array([b for b, _ in pts], int)
        ys = np.array([y for _, y in pts], float)
        cur = brk = None
        for k2 in range(len(pts) - 1, 0, -1):
            b2, y2 = pts[k2]
            if cur is not None and b2 < cur["p1"][0]:                      # older than the live line's own first anchor: history
                break
            cand = np.flatnonzero(((y2 - ys[:k2]) * sd > 0) & (bars[:k2] < b2))[::-1]
            if (kind == "H") == (sd > 0) and len(cand):                    # rising highs / falling lows: a close beyond p2's own price
                seg = C[:b2]                                               # between the anchors is beyond the line too ⇒ no older p1
                bad = np.flatnonzero((seg - y2) * side > 0)
                if len(bad):
                    cand = cand[bars[cand] >= bad[-1]]
            pair = None
            for k1 in cand:
                b1, y1 = pts[int(k1)]
                if _pair_ok(C, known, b1, y1, b2, y2, kind):
                    pair = (b1, y1)
                    break
            if pair is None:
                continue
            b1, y1 = pair
            slope = (y2 - y1) / (b2 - b1)

            def line(b, y1=y1, b1=b1, slope=slope):
                return y1 + slope * (b - b1)
            kb = beyond = None
            if rule == "follow_through":                                   # DECISIONS 76: a close beyond + follow-through
                bb, kb, beyond = follow_through_break(C, known, line, side, b2 + 1, t)
            else:
                bb = _broken_at(C, hk if rule == "hold" else known, FL.hold_kind(side > 0) if rule == "hold" else kind, line, side, b2 + 1,
                                t, hold=rule == "hold")                    # BREAK-1 what-if: a close beyond + a swing that HOLDS beyond
            groups = touch_groups(A, known, kind, line, b1, b2, t if bb is None else bb)
            x = {"family": f"{'rising' if sd > 0 else 'falling'} line of {'highs' if kind == 'H' else 'lows'}", "kind": kind,
                 "slope_dir": "rising" if sd > 0 else "falling", "degree": g, "tf": tf,
                 "p1": [b1, round(y1, 2)], "p2": [b2, round(y2, 2)],
                 "slope": round(slope, 4), "touches": len(groups), "touch_groups": groups, "value_t": round(line(t), 2),
                 "broken": bb is not None, "break_bar": bb, "break_side": "up" if side > 0 else "down",
                 "state": "BROKEN" if bb is not None else (FL.BEYOND if beyond is not None else "ACTIVE"),
                 "id": f"{prefix}:{kind}{'+' if sd > 0 else '-'}:{b1}-{b2}"}
            if rule == "follow_through":
                x["break_known_bar"] = kb                                  # DECISIONS 76: the follow-through close (the break is known)
                x["beyond_at"] = beyond
            if bb is None and cur is None:
                cur = x
            elif bb is not None:
                if brk is None:
                    brk = x
                break                                                      # the newest broken line of this family found
        out.extend(z for z in (cur, brk) if z is not None)
    return out


def channels(V, t, degree=None):
    """Abhi 21 Oct — CHANNELS: each line of `channel_lines` with its parallel through the opposite extreme of the same move (the
    lowest low between the anchors of a line of highs; the highest high for a line of lows). The parallel's break = the same K6.5 rule
    (a close beyond + a swing of its kind beyond). State at t: "inside" (the close between the two lines, none broken), "outside" (no
    break), "<lower|upper> line broken", or "retest of the broken <lower|upper> line" (bar t's wick reaches the broken line again);
    a broken line whose break was undone by structure (`broken_back_at`, DECISIONS 39) reads "<lower|upper> line broken, then broken
    back (…)" — never a retest (display / evidence words only).
    Facts / evidence only (a broken rising channel in a downtrend = handover evidence); a broken line is a retest level (E4 b).
    Returns [{id, tf, degree, slope_dir, base, parallel, upper_t, lower_t, state, broken_side, broken_lines}]."""
    g = int(V.s.get("level_degree", 2)) if degree is None else int(degree)
    memo = V.__dict__.setdefault("_chanl_memo", {})
    if (t, g) in memo:
        return memo[(t, g)]
    out = channels_on(V.levels.A, _known_deg(V, t, g), channel_lines(V, t, g), t, g, FL.hold_rule(V.s), hold_known=_known_fine(V, t))
    memo[(t, g)] = out
    return out


def channels_on(A, known, lines, t, degree, rule=None, hold_known=None):
    """T3 — the core of `channels` for ANY timeframe (A, known, t as in `lines_on`; lines = its `lines_on` result)."""
    rule = FL.hold_rule({"break_hold_rule": rule})
    hk = known if hold_known is None else hold_known
    g = degree
    C = A["close"]
    out = []
    for ln in lines:
        (b1, _y1), (b2, _y2) = ln["p1"], ln["p2"]
        seg = np.arange(int(b1), int(b2) + 1)
        if ln["kind"] == "H":
            bo = int(seg[np.argmin(A["low"][seg])])
            yo, pk, pside = float(A["low"][bo]), "L", -1
        else:
            bo = int(seg[np.argmax(A["high"][seg])])
            yo, pk, pside = float(A["high"][bo]), "H", 1
        sl = float(ln["slope"])

        def par(b, yo=yo, bo=bo, sl=sl):
            return yo + sl * (b - bo)
        pkb = pbey = None
        if rule == "follow_through":                                       # DECISIONS 76 (as the base line)
            pb, pkb, pbey = follow_through_break(C, known, par, pside, int(b2) + 1, t)
        else:
            pb = _broken_at(C, hk if rule == "hold" else known, FL.hold_kind(pside > 0) if rule == "hold" else pk, par, pside, int(b2) + 1,
                            t, hold=rule == "hold")                        # BREAK-1 what-if (as the base line)
        pl = {"family": f"{ln['slope_dir']} line of {'lows' if pk == 'L' else 'highs'} (parallel)", "kind": pk,
              "slope_dir": ln["slope_dir"], "degree": g, "tf": ln["tf"], "p1": [bo, round(yo, 2)], "p2": [bo + 1, round(par(bo + 1), 2)],
              "slope": ln["slope"], "value_t": round(par(t), 2), "broken": pb is not None, "break_bar": pb,
              "break_side": "up" if pside > 0 else "down",
              "state": "BROKEN" if pb is not None else (FL.BEYOND if pbey is not None else "ACTIVE"),
              "id": f"{ln['id']}|par", "parallel_of": ln["id"]}
        if rule == "follow_through":
            pl["break_known_bar"], pl["beyond_at"] = pkb, pbey
        up_, lo_ = (ln, pl) if ln["kind"] == "H" else (pl, ln)
        ut, lt = line_value(up_, t), line_value(lo_, t)
        broken = [x for x in (up_, lo_) if x["broken"]]
        if broken:
            x = max(broken, key=lambda z: z["break_bar"])
            nm = "upper" if x is up_ else "lower"
            v = line_value(x, t)
            back = broken_back_on(C, hk if rule == "hold" else known, x, t, rule)   # K6.5 mirror (DECISIONS 39): undone by structure
            retest = (A["high"][t] >= v) if x["break_side"] == "down" else (A["low"][t] <= v)
            if back is not None:                                          # display: never "retest of the broken …" once broken back
                state = f"{nm} line broken, then broken back ⇒ dead (closed back and held on its original side)"
            else:
                state = f"retest of the broken {nm} line" if retest else f"{nm} line broken"
            bside = x["break_side"]
        else:
            state = "inside" if lt <= C[t] <= ut else "outside (no break)"
            bside = None
        out.append({"id": f"ch:{ln['id']}", "tf": ln["tf"], "degree": g, "slope_dir": ln["slope_dir"], "base": ln["id"],
                    "base_line": ln, "parallel": pl, "upper_t": round(ut, 2), "lower_t": round(lt, 2), "state": state,
                    "broken_side": bside, "broken_lines": [x["id"] for x in broken]})
    return out


# ------------------------------------------------------------------------------------------------ T3: channels per timeframe
CHANNEL_TFS = ("W", "D", "1H", "15M")    # the timeframes with structure swings (5M = the LTF-CHoCH swing only: OPEN_QUESTIONS T3-1)


def _htf_lines(V, t, tf):
    """Daily / Weekly lines + channels at the 15M bar t: the same core on that timeframe's candles closed by t, through the swings
    `mtf_state.swings` reads its state from (the Daily / Weekly fold's own swings, alternated; confirmed by t). Cached per closed candle.
    Returns (lines, channels, structure word)."""
    from . import mtf_state as MS
    F = MS.frame(V, t, tf)
    if F is None or not F["n"]:
        return [], [], None
    n = int(F["n"])
    memo = V.__dict__.setdefault("_chan_tf_memo", {})
    if (tf, n) in memo:
        return memo[(tf, n)]
    ext, _inn, deg, _ = MS.swings(V, t, tf)
    A = {k: np.asarray(F[c], float)[:n] for k, c in (("open", "o"), ("high", "h"), ("low", "l"), ("close", "c"))}
    known = sorted((p for p in ext if int(p.bar) < n and int(p.confirm_bar) < n), key=lambda p: p.bar)
    rule = FL.hold_rule(V.s)
    lines = lines_on(A, known, n - 1, None, tf, tf, rule)
    chans = channels_on(A, known, lines, n - 1, None, rule)
    for x in lines + [c["parallel"] for c in chans]:                      # the candles' own times (bars are that timeframe's index)
        x["structure"] = deg
        x["ts"] = [str(F["ts"].iloc[int(x["p1"][0])]), str(F["ts"].iloc[min(int(x["p2"][0]), n - 1)])]
    memo[(tf, n)] = out = (lines, chans, deg)
    return out


def channels_by_tf(V, t):
    """T3 (§2E per timeframe): {tf: {"structure", "lines", "channels"}} for W, D, 1H, 15M at the 15M bar t, each read on its own swings
    and bars by the same method §3 / K6.5 core. 1H / 15M = the existing degrees of the 15M chart (`line_degrees`, unchanged — the rows'
    `channel_lines` / `channels`); D / W = their own candles (`_htf_lines`). Evidence / display only: the E4 (b) objects stay the trend
    degree's lines (`entry_models.Reader.broken_objects`), so nothing here changes an entry. Missing Daily / Weekly data ⇒ "na"."""
    out = {}
    for tf in CHANNEL_TFS:
        if tf in ("D", "W"):
            try:
                lines, chans, deg = _htf_lines(V, t, tf)
            except (AttributeError, KeyError, TypeError, ValueError, IndexError) as exc:   # no Daily / Weekly candles ⇒ said
                out[tf] = {"structure": None, "lines": [], "channels": [], "na": type(exc).__name__}
                continue
            out[tf] = {"structure": deg, "lines": lines, "channels": chans}
            continue
        gs = [g for g in line_degrees(V) if TF_OF_DEGREE.get(g) == tf]
        out[tf] = {"structure": ", ".join(f"D{g}" for g in gs) or None,
                   "lines": [x for g in gs for x in channel_lines(V, t, g)], "channels": [c for g in gs for c in channels(V, t, g)]}
    return out


def compact_channels(chans):
    """A channel list for the row / payload: the base line dict left out (its id stays in `base`), as the row's `channels`."""
    return [{k: v for k, v in c.items() if k != "base_line"} for c in chans]


def line_value(ln, b):
    """The price of a line dict (`channel_lines` / `channels` / `swing_line`) at bar b."""
    (b1, y1) = ln["p1"]
    return float(y1) + float(ln["slope"]) * (int(b) - int(b1))


def broken_back_at(V, ln, t, known=False):
    """K6.5 mirror for a BROKEN line (method §3 "as an area"; BREAK-1, DECISIONS 60 — broken back ⇒ DEAD by the same test opposite):
    after the break's own excursion, a close back beyond the line on its ORIGINAL side starts an attempt; price HOLDS there when a swing
    of the hold side (`flip.hold_kind`: a pullback low above a line broken down, mirror), of the line's own degree, formed from the
    attempt's first close on is CONFIRMED while every close is still back — the confirming bar too (a break-back bar that already
    closed through again = no hold, the #373 lesson mirrored); a close that is not back first ends the attempt (a sweep of the retest —
    the line stays broken). Returns the attempt's first close (a bar) of the first completed attempt known by bar t, else None;
    known=True ⇒ the bar it became KNOWN (the confirming bar — the chart stamp, DECISIONS 63). Once broken back the line is dead —
    never an E4 (b) object again (DECISIONS 39). `break_hold_rule = swing_beyond` (what-if) = the earlier reading (the push's own
    extreme back there counted; the confirming bar could close through again). Comparison only; bars ≤ t."""
    if not ln.get("broken") or ln.get("break_bar") is None:
        return None
    g = int(ln.get("degree") or V.s.get("level_degree", 2))
    rule = FL.hold_rule(V.s)
    sw = _known_fine(V, int(t)) if rule == "hold" else None                 # BREAK-1: the hold read on the finest structure
    return broken_back_on(V.levels.A["close"], _known_deg(V, int(t), g) if sw is None else sw, ln, t, rule, known_bar=known)


def _break_side(ln):
    bs = ln.get("break_side")                                              # the break side (a line of highs is broken upward)
    return (1 if bs == "up" else -1) if bs in ("up", "down") else (1 if ln["kind"] == "H" else -1)


def broken_back_on(C, known, ln, t, rule=None, known_bar=False):
    """The core of `broken_back_at` on ANY timeframe's closes C and its swings `known` (of the line's own degree, known by bar t: kind,
    price, bar, confirm_bar) — the same reading, used by `channels_on` for its state words on every timeframe (display)."""
    if not ln.get("broken") or ln.get("break_bar") is None:
        return None
    side = _break_side(ln)
    t = int(t)
    run_end = int(ln["break_bar"])                                         # skip the break's own closes beyond
    while run_end <= t and (float(C[run_end]) - line_value(ln, run_end)) * side > 0:
        run_end += 1
    if run_end > t:
        return None
    if FL.hold_rule({"break_hold_rule": rule}) == "follow_through":      # DECISIONS 76: broken back by the same test ⇒ DEAD
        kb = ln.get("break_known_bar")
        kb = int(ln["break_bar"]) if kb is None else int(kb)
        line = (lambda i, ln=ln: line_value(ln, i))
        b0, k1, _ = follow_through_break(C, [p for p in known if _cb(p) <= t], line, -side, kb + 1, t)
        if b0 is None:
            return None
        return k1 if known_bar else b0
    hold = FL.hold_rule({"break_hold_rule": rule}) == "hold"
    back_kind = FL.hold_kind(side < 0) if hold else ("L" if side > 0 else "H")   # hold: price back on the original side HOLDS there
    piv = [p for p in known if _cb(p) <= t and p.kind == back_kind and int(p.bar) >= run_end
           and (float(p.price) - line_value(ln, int(p.bar))) * -side > 0]
    if not piv:
        return None
    att = None
    for u in range(run_end, t + 1):
        back = (float(C[u]) - line_value(ln, u)) * -side > 0
        if hold and not back:                                              # the confirming bar itself must still be back
            att = None
            continue
        if back and att is None:
            att = u
        if att is not None and any(int(p.bar) >= att and _cb(p) <= u for p in piv):
            return u if known_bar else att
        if not back:
            att = None
    return None


def break_known_at(V, ln):
    """The bar from which a broken line is KNOWN broken (DECISIONS 63 — the chart stamp): the confirmation of the first swing that
    proves the break after the break close (K6.5; BREAK-1: the hold side's own swing, confirmed while the closes are still beyond)."""
    if not ln.get("broken"):
        return None
    if FL.hold_rule(V.s) == "follow_through" and ln.get("break_known_bar") is not None:
        return int(ln["break_known_bar"])                                  # DECISIONS 76: the follow-through close
    side = _break_side(ln)
    bb = int(ln["break_bar"])
    C = V.levels.A["close"]
    run_end = bb                                                           # the excursion's closes beyond: bb … run_end − 1
    while run_end < len(C) and (float(C[run_end]) - line_value(ln, run_end)) * side > 0:
        run_end += 1
    g = int(ln.get("degree") or V.s.get("level_degree", 2))
    pv = V.levels._pv_sorted if g == int(V.s.get("level_degree", 2)) else \
        list(((getattr(V.levels, "res", None) or {}).get("pivots") or {}).get(g, []))
    if FL.hold_rule(V.s) == "hold":
        want = FL.hold_kind(side > 0)
        k0 = getattr(V.levels, "_known_hold", getattr(V.levels, "_known0", None))
        pv = pv if k0 is None else k0                                      # BREAK-1: the hold degree (A-L1: D0; as the area hold)
        cands = [_cb(p) for p in pv if p.kind == want and bb <= int(p.bar) and _cb(p) < run_end
                 and (float(p.price) - line_value(ln, p.bar)) * side > 0]
    else:
        cands = [int(p.confirm_bar) for p in pv if p.kind == ln["kind"] and bb <= int(p.bar) <= run_end
                 and (float(p.price) - line_value(ln, p.bar)) * side > 0]
    return min(cands) if cands else None
