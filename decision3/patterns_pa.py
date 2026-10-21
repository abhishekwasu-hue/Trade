"""decision3/patterns_pa.py — PA standard §2H (chart patterns from the swings) + §2K (breakout vs fakeout). EVIDENCE / STATE only.

Nothing here blocks or triggers an entry (KB K11.0: patterns are context / area / evidence, never a breakout entry). Track T9 lists the
output as evidence; E4(b) may later read `retest_levels` (hook only — entry_models.py is not touched here).

Method-pure (Abhi's method, KB K11 + KP1–KP5, C-13):
  • Swings = the confirmed swings2 pivots of the timeframe's degree (1H = `level_degree` D2, 15M = one degree below, D1), folded to
    alternate H / L. Only pivots with confirm_bar ≤ t and bars ≤ t are read (no look-ahead).
  • "Equal" = C-13 (`decision3.daily.c13_equal`): the later extreme reaches the earlier swing candle's own area (wick to body) and does
    not go beyond it. "Short of" (lower high / higher low) = `c13_short_of`. "Beyond" = past the earlier extreme. No σ, no MR tolerance.
  • Leg sizes, slopes, depth: compared with the neighbouring legs / swings only. No fixed number in the reading.
  • Broken (method §3 / K6.5, as `trendline.broken_by`): a close beyond the boundary AND a swing formed beyond it (the finest structure
    degree, as `levels._swing_beyond`), with no close back inside between them. A close that comes back first = fakeout (failed
    breakout, K11.16); a wick beyond with the close inside = sweep (K11.15).
  • Retest: after the break, a later candle's wick reaches the boundary from the broken side while its body stays on that side
    (`trendline.touches`). Failed after acceptance = the mirror break back inside (close inside + a swing inside).

Patterns (each with its neckline / boundary lines and a state):
  double / triple top-bottom (K11.8 / K11.9), head & shoulders + inverse (K11.10), triangles sym / asc / desc (K11.4 / K11.5),
  flags + pennants (K11.1 / K11.2), wedges (K11.7), rectangles / ranges (K11.3), broadening (K11.13, contrary evidence only — KP4).

States (K11.0: a pattern is NAMED only after its confirmation; before that it is a candidate, listed but never evidence):
  forming   — candidate: the shape is there, the confirmation is not
  complete  — named: reversal = a close beyond the neckline; triangle / broadening = 5 legs (E confirmed); wedge = 5th push + a close
              beyond the 2–4 line; flag / pennant = the flag's counter-pole end confirmed; rectangle = 2 equal highs + 2 equal lows
  broken    — the boundary is broken by the method's definition (close beyond + swing beyond) = acceptance
  retested  — broken, then a candle came back to the boundary from the broken side and its body stayed there
  failed    — reversal: neckline fakeout (false break, name cancelled) or acceptance beyond the far extreme (continuation);
              any: broken, then reclaimed (close back inside + swing inside); biased continuation pattern broken AGAINST its bias

API (plain dicts):
  breakout_state(A, fine, line, side, start, t)        — §2K for any boundary / level / line (callable bar → price)
  level_breakout(A, fine, lo, hi, side, start, t)      — the same for a horizontal band (areas, range edges)
  find_patterns(A, swings, fine, t, tf, d=None, ts=None) — the core on raw arrays (tests / other frames)
  read_patterns(V, t, d=None, tf="1H")                  — on a V22 state
  retest_levels(V, t, d=None, tf="1H")                  — E4(b) hook: broken pattern boundaries as retest levels
  draw_objects(V, t, d=None, tf="1H")                   — [{kind, tf, t0, t1, p0, p1, label, state, evidence}] for the chart track
Order / broker / AI call नाही.
"""
from bisect import bisect_left, bisect_right
from dataclasses import dataclass

import numpy as np

from .daily import c13_area, c13_equal, c13_short_of

TFS = ("1H", "15M")
REVERSAL = ("double_top", "double_bottom", "triple_top", "triple_bottom", "hs_top", "hs_bottom")
NAMES = {
    "double_top": "double top", "double_bottom": "double bottom", "triple_top": "triple top", "triple_bottom": "triple bottom",
    "hs_top": "head & shoulders", "hs_bottom": "inverse head & shoulders",
    "sym_triangle": "symmetrical triangle", "asc_triangle": "ascending triangle", "desc_triangle": "descending triangle",
    "bull_flag": "bull flag", "bear_flag": "bear flag", "bull_pennant": "bull pennant", "bear_pennant": "bear pennant",
    "falling_wedge": "falling wedge", "rising_wedge": "rising wedge", "rectangle": "rectangle / range", "broadening": "broadening",
}
STATE_WORDS = {"forming": "forming (candidate, not named)", "complete": "complete", "broken": "boundary broken",
               "retested": "broken boundary retested", "failed": "failed"}


@dataclass(frozen=True)
class Sw:
    kind: str
    price: float
    bar: int
    confirm_bar: int


# ------------------------------------------------------------------------------------------------ swings (confirmed, alternating)
def known_swings(pivs, t):
    """Confirmed swings at bar t (confirm_bar ≤ t, bar ≤ t), in bar order, folded to alternate H / L (a run of the same kind keeps the
    more extreme, as `daily._add`)."""
    ps = sorted((p for p in (pivs or []) if int(p.confirm_bar) <= t and int(p.bar) <= t), key=lambda p: (int(p.bar), int(p.confirm_bar)))
    seq = []
    for p in ps:
        s = Sw(str(p.kind), float(p.price), int(p.bar), int(p.confirm_bar))
        if seq and seq[-1].kind == s.kind:
            if (s.price > seq[-1].price) if s.kind == "H" else (s.price < seq[-1].price):
                seq[-1] = s
            continue
        seq.append(s)
    return seq


class _Fine:
    """The structure swings used for "a swing formed beyond" (finest structure degree), indexed by bar for range lookups."""

    def __init__(self, pivs, t):
        ps = sorted((p for p in (pivs or []) if int(p.confirm_bar) <= t and int(p.bar) <= t), key=lambda p: int(p.bar))
        self.ps = [Sw(str(p.kind), float(p.price), int(p.bar), int(p.confirm_bar)) for p in ps]
        self.bars = [p.bar for p in self.ps]

    def between(self, b0, b1, kind):
        lo, hi = bisect_left(self.bars, b0), bisect_right(self.bars, b1)
        return [p for p in self.ps[lo:hi] if p.kind == kind]


def _as_fine(fine, t):
    return fine if isinstance(fine, _Fine) else _Fine(fine, t)


# ------------------------------------------------------------------------------------------------ C-13 comparisons
class _Cmp:
    def __init__(self, A):
        self.A = A
        self.O, self.C = A["open"], A["close"]

    def area(self, p):
        """C-13: the swing candle's own area, wick to body [lo, hi]."""
        lo, hi = c13_area(self.O, self.A["high"], self.A["low"], self.C, p.bar, p.kind)
        return [round(min(lo, hi), 2), round(max(lo, hi), 2)]

    def rel(self, later, earlier):
        """'beyond' (higher high / lower low), 'equal' (C-13), 'short' (lower high / higher low: short of the earlier candle's area)."""
        if c13_equal(self.O, self.C, later.price, earlier.kind, earlier.bar, earlier.price):
            return "equal"
        if c13_short_of(self.O, self.C, later.price, earlier.kind, earlier.bar):
            return "short"
        return "beyond"

    def side_dir(self, pts):
        """Progression of one side's swings (consecutive, later vs earlier): +1 rising, −1 falling, 0 flat (all equal), None mixed."""
        if len(pts) < 2:
            return None
        rels = {self.rel(b, a) for a, b in zip(pts, pts[1:])}
        if len(rels) != 1:
            return None
        r = rels.pop()
        if r == "equal":
            return 0
        up = (r == "beyond") == (pts[0].kind == "H")
        return 1 if up else -1

    def all_equal_to_ref(self, pts):
        return len(pts) >= 2 and all(self.rel(p, pts[0]) == "equal" for p in pts[1:])


def _legs(W):
    return [abs(b.price - a.price) for a, b in zip(W, W[1:])]


def _shrinking(xs):
    return len(xs) >= 2 and all(b < a for a, b in zip(xs, xs[1:]))


def _expanding(xs):
    return len(xs) >= 2 and all(b > a for a, b in zip(xs, xs[1:]))


# ------------------------------------------------------------------------------------------------ boundary lines
class Line:
    """A boundary: through (b0, y0) with a slope per 15M bar (0 = horizontal)."""

    def __init__(self, b0, y0, slope=0.0, b1=None, y1=None, name="", side=0):
        self.b0, self.y0, self.slope = int(b0), float(y0), float(slope)
        self.b1 = int(b1) if b1 is not None else int(b0)
        self.y1 = float(y1) if y1 is not None else float(y0)
        self.name, self.side = name, side                                  # side: +1 = above price (upper), −1 = below (lower)

    def __call__(self, b):
        return self.y0 + self.slope * (b - self.b0)

    def brief(self, t):
        return {"name": self.name, "p0": [self.b0, round(self.y0, 2)], "p1": [self.b1, round(self.y1, 2)],
                "slope": round(self.slope, 4), "value_t": round(self(t), 2)}


def _through(a, b, name, side):
    sl = (b.price - a.price) / (b.bar - a.bar) if b.bar != a.bar else 0.0
    return Line(a.bar, a.price, sl, b.bar, b.price, name, side)


def _horizontal(a, name, side, b1=None):
    return Line(a.bar, a.price, 0.0, b1 if b1 is not None else a.bar, a.price, name, side)


def _envelope(pts, name, side, cmp):
    """A side's boundary: flat (all C-13 equal to the first) ⇒ horizontal at the first swing; else the line from the first swing through
    the later swing that keeps every swing of the side on / inside it (highs on or below, lows on or above)."""
    if len(pts) < 2:
        return None
    if cmp.all_equal_to_ref(pts):
        return _horizontal(pts[0], name, side, pts[-1].bar)
    a = pts[0]
    sl = [((p.price - a.price) / (p.bar - a.bar), p) for p in pts[1:] if p.bar != a.bar]
    if not sl:
        return None
    s, p = (max if side > 0 else min)(sl, key=lambda x: x[0])
    return Line(a.bar, a.price, s, p.bar, p.price, name, side)


def _apex(lines, e):
    """Converging upper / lower boundaries: the bar where they meet, after the pattern's last swing `e` (None = parallel / diverging)."""
    up = [ln for ln in lines if ln.side > 0]
    lo = [ln for ln in lines if ln.side < 0]
    if len(up) != 1 or len(lo) != 1:
        return None
    u, l_ = up[0], lo[0]
    ds = u.slope - l_.slope
    if ds >= 0:                                                            # the gap does not shrink
        return None
    gap_e = u(e) - l_(e)
    b = e + gap_e / -ds
    return int(np.floor(b)) if b > e else None


def _first2(pts, name, side, cmp):
    """Elliott boundary (A–C / B–D, 1–3 / 2–4): through the side's first two swings; a flat side (C-13 equal) ⇒ horizontal at the first."""
    if len(pts) < 2:
        return None
    if cmp.rel(pts[1], pts[0]) == "equal":
        return _horizontal(pts[0], name, side, pts[-1].bar)
    return _through(pts[0], pts[1], name, side)


# ------------------------------------------------------------------------------------------------ §2K breakout vs fakeout
def _touch_from(A, b, y, broke_up):
    """Retest touch (as `trendline.touches`): the wick reaches the boundary while the body stays on the broken side."""
    o, c = float(A["open"][b]), float(A["close"][b])
    if broke_up:                                                           # boundary now below price (support): low ≤ y ≤ body bottom
        return bool(float(A["low"][b]) <= y <= min(o, c))
    return bool(max(o, c) <= y <= float(A["high"][b]))


def _values(line, b0, b1):
    bars = np.arange(b0, b1 + 1)
    if isinstance(line, Line):
        return line.y0 + line.slope * (bars - line.b0)
    return np.array([float(line(int(b))) for b in bars], float)


def _accept(A, fine, line, side, start, t):
    """First accepted excursion beyond `line` on `side` (+1 above / −1 below) in bars start … t: a run of closes beyond it and a swing
    (of the beyond kind, confirmed by t) formed beyond it while the closes stayed beyond (the swing's bar may be the bar that closes back,
    as `trendline.broken_by`). Returns (accept, fakeouts, sweeps, open_run): accept = (first close bar, swing) or None; fakeouts = runs
    that came back inside first [(first close bar, back bar)]; sweeps = wick-only bars before the accepted / open run; open_run = the
    first close bar of an unfinished run at t (no swing yet) or None."""
    if start > t:
        return None, [], [], None
    y = _values(line, start, t)
    C = np.asarray(A["close"][start:t + 1], float)
    X = np.asarray((A["high"] if side > 0 else A["low"])[start:t + 1], float)
    bey = (C - y) * side > 0
    wick = ((X - y) * side > 0) & ~bey
    kind = "H" if side > 0 else "L"
    idx = np.flatnonzero(bey)
    runs = []
    if len(idx):
        cut = np.flatnonzero(np.diff(idx) > 1)
        starts = np.r_[idx[0], idx[cut + 1]]
        ends = np.r_[idx[cut], idx[-1]]
        runs = [(start + int(a), start + int(b)) for a, b in zip(starts, ends)]
    back_bars = {r + 1 for _, r in runs}
    sweeps_all = [start + int(k) for k in np.flatnonzero(wick) if start + int(k) not in back_bars]
    fakeouts = []
    for e, r in runs:
        hi_bar = min(r + 1, t)
        sw = [p for p in fine.between(e, hi_bar, kind) if (p.price - float(line(p.bar))) * side > 0]
        if sw:
            return (e, sw[0]), fakeouts, [b for b in sweeps_all if b < e], None
        if r >= t:
            return None, fakeouts, [b for b in sweeps_all if b < e], e
        fakeouts.append((e, r + 1))
    return None, fakeouts, sweeps_all, None


def breakout_state(A, fine, line, side, start, t):
    """§2K for one boundary at bar t (bars start … t, swings confirmed by t). `side` = the break direction (+1 up through it, −1 down).
    state: inside · sweep (wick beyond, close back — no breakout) · beyond (closed beyond, no swing beyond yet — not accepted) ·
    accepted (close beyond + swing beyond = "hold") · retested (accepted, then a candle came back to it and its body stayed beyond) ·
    fakeout (closed beyond, came back inside before any swing beyond — failed breakout) · failed (accepted, then reclaimed: close back
    inside + a swing inside). The state is the latest of these at t. Returns a plain dict with the bars of each event."""
    fine = _as_fine(fine, t)
    out = {"side": int(side), "state": "inside", "first_close": None, "accepted_bar": None, "swing_beyond": None, "retests": [],
           "fakeouts": [], "sweeps": [], "failed_bar": None, "events": []}
    cur, closes = max(int(start), 0), []
    while cur <= t:
        acc, fk, sw, open_run = _accept(A, fine, line, side, cur, t)
        out["fakeouts"] += [list(x) for x in fk]
        out["sweeps"] += sw
        new = [(b, "fakeout") for _, b in fk] + [(b, "sweep") for b in sw]
        out["events"] += new
        closes += [e for e, _ in fk]
        if acc is None:
            if open_run is not None:
                closes.append(open_run)
                out["state"] = "beyond"
                out["events"].append((open_run, "close_beyond"))
            elif new:
                out["state"] = max(new)[1]
            break                                                          # nothing new ⇒ the state stays (inside / failed)
        e, p = acc
        closes.append(e)
        known = max(p.confirm_bar, e)
        out.update(state="accepted", accepted_bar=known, failed_bar=None,
                   swing_beyond={"bar": p.bar, "price": round(p.price, 2), "known_bar": p.confirm_bar})
        out["events"].append((known, "accepted"))
        back = _accept(A, fine, line, -side, p.bar + 1, t)[0]              # the mirror break: close back inside + a swing inside
        stop = back[0] if back else t + 1
        Lv = _values(line, p.bar + 1, t) if p.bar + 1 <= t else []
        rt = [b for k, b in enumerate(range(p.bar + 1, min(stop, t + 1))) if _touch_from(A, b, float(Lv[k]), side > 0)]
        out["retests"] = rt
        if rt:
            out["state"] = "retested"
            out["events"].append((rt[0], "retest"))
        if back is None:
            break
        fb, q = back
        out.update(state="failed", failed_bar=max(q.confirm_bar, fb))
        out["events"].append((max(q.confirm_bar, fb), "failed"))
        cur = q.bar + 1                                                    # a new attempt may start after the reclaim swing
    out["first_close"] = min(closes) if closes else None
    out["events"] = [list(x) for x in sorted(set(out["events"]))]
    out["accepted"] = out["state"] in ("accepted", "retested")
    out["outcome"] = "breakout" if out["accepted"] else ("fakeout" if out["state"] in ("fakeout", "sweep", "failed") else None)
    return out


def level_breakout(A, fine, lo, hi, side, start, t):
    """§2K for a horizontal band (an area, a range edge): up (+1) through its top, down (−1) through its bottom."""
    y = float(hi) if side > 0 else float(lo)
    return breakout_state(A, fine, lambda b: y, side, start, t)


# ------------------------------------------------------------------------------------------------ pattern detectors (on swings)
def _double_triple(S, j, cmp):
    """Double / triple top (bottom mirror) ending at swing j. Double: L0, H1, N, H2 — H2 equal H1 (C-13), the rise came from clearly below
    the neckline (N short of L0). Triple: L0, H1, N1, H2, N2, H3 — H2, H3 equal H1, neckline = the lower trough, L0 clearly below it."""
    out = None
    if j >= 5:
        L0, H1, N1, H2, N2, H3 = S[j - 5:j + 1]
        neck = min((N1, N2), key=lambda p: p.price) if H3.kind == "H" else max((N1, N2), key=lambda p: p.price)
        if cmp.rel(H2, H1) == "equal" and cmp.rel(H3, H1) == "equal" and cmp.rel(neck, L0) == "short":
            out = ("triple_top" if H3.kind == "H" else "triple_bottom", [L0, H1, N1, H2, N2, H3], neck, H1)
    if out is None and j >= 3:
        L0, H1, N, H2 = S[j - 3:j + 1]
        if cmp.rel(H2, H1) == "equal" and cmp.rel(N, L0) == "short":
            out = ("double_top" if H2.kind == "H" else "double_bottom", [L0, H1, N, H2], N, H1)
    if out is None:
        return None
    fam, W, neck, ext = out
    top = W[-1].kind == "H"
    far = max((p for p in W if p.kind == W[-1].kind), key=lambda p: p.price) if top else \
        min((p for p in W if p.kind == W[-1].kind), key=lambda p: p.price)
    return {"family": fam, "swings": W, "bias": -1 if top else 1,
            "lines": [_horizontal(neck, "neckline", -1 if top else 1, W[-1].bar)],
            "far": _horizontal(far, "tops" if top else "bottoms", 1 if top else -1, W[-1].bar),
            "facts": {"neckline": round(neck.price, 2), "extreme": round(far.price, 2)}}


def _head_shoulders(S, j, cmp):
    """H&S top ending at swing j (inverse = mirror): L0, LS, N1, HD, N2, RS — the head beyond both shoulders, the right shoulder short of
    the head (a lower high: Dow LH), each shoulder above the opposite trough, the rise came from clearly below the left trough (N1 short
    of L0). Neckline = the line through N1 and N2."""
    if j < 5:
        return None
    L0, LS, N1, HD, N2, RS = S[j - 5:j + 1]
    top = RS.kind == "H"
    if not (cmp.rel(HD, LS) == "beyond" and cmp.rel(RS, HD) == "short" and cmp.rel(N1, L0) == "short"):
        return None
    sd = 1 if top else -1
    if not ((LS.price - N2.price) * sd > 0 and (RS.price - N1.price) * sd > 0):
        return None
    return {"family": "hs_top" if top else "hs_bottom", "swings": [L0, LS, N1, HD, N2, RS], "bias": -sd,
            "lines": [_through(N1, N2, "neckline", -sd)], "far": _horizontal(HD, "head", sd, RS.bar),
            "facts": {"head": round(HD.price, 2), "shoulders": [round(LS.price, 2), round(RS.price, 2)]}}


def _contracting(S, j, cmp):
    """Triangle ending at swing j: origin O + 4 (A–D, forming) or 5 (A–E, complete) points, every leg smaller than the one before
    (K11.5), highs falling + lows rising = symmetrical; highs equal (C-13) + lows rising = ascending; highs falling + lows equal =
    descending (K11.4 barrier). Leg A must not break structure (A-end not beyond the swing of its kind before O): a leg that does is the
    impulse INTO the triangle, so the triangle starts one swing later. Boundaries = the A–C and B–D lines.
    Broadening (K11.13) = the mirror: every leg larger, highs rising + lows falling (envelope lines)."""
    found = []
    for n in (6, 5):
        if j - n + 1 < 0:
            continue
        W = S[j - n + 1:j + 1]
        P = W[1:]
        hs, ls = [p for p in P if p.kind == "H"], [p for p in P if p.kind == "L"]
        hd, ld = cmp.side_dir(hs), cmp.side_dir(ls)
        legs = _legs(W)
        fam = None
        if _shrinking(legs):
            fam = {(-1, 1): "sym_triangle", (0, 1): "asc_triangle", (-1, 0): "desc_triangle"}.get((hd, ld))
            k = j - n                                                      # the swing before the origin (same kind as A-end)
            if fam and (k < 0 or cmp.rel(W[1], S[k]) == "beyond"):        # leg A broke structure ⇒ it is the impulse into the
                fam = None                                                 # triangle, not its first leg (unknown origin ⇒ no name)
        elif _expanding(legs) and (hd, ld) == (1, -1):
            fam = "broadening"
        if fam:
            bias = {"asc_triangle": 1, "desc_triangle": -1}.get(fam, 0)
            mk = _envelope if fam == "broadening" else _first2
            up, lo = mk(hs, "upper", 1, cmp), mk(ls, "lower", -1, cmp)
            if up is None or lo is None:
                continue
            found.append({"family": fam, "swings": W, "bias": bias, "lines": [up, lo], "legs_done": len(P),
                          "facts": {"legs": len(P), "highs": hd, "lows": ld}})
            break
    return found


def _wedge(S, j, cmp):
    """Wedge (diagonal, K11.7) ending at swing j: origin O + W1…W4 (forming, 2 touches a line) or W1…W5. Falling wedge: O a high, highs
    (W2, W4) falling and lows (W1, W3, W5) falling (lower lows), the pushes O→W1, W2→W3, W4→W5 each smaller than the one before, and the
    2–4 line (through the highs) falls faster than the 1–3 line (converging). Rising wedge = mirror. KP3: read as ENDING."""
    for n in (6, 5):
        if j - n + 1 < 0:
            continue
        W = S[j - n + 1:j + 1]
        O, P = W[0], W[1:]
        falling = O.kind == "H"
        hs, ls = [p for p in P if p.kind == "H"], [p for p in P if p.kind == "L"]
        want = -1 if falling else 1
        if cmp.side_dir(hs) != want or cmp.side_dir(ls) != want:
            continue
        pushes = [abs(W[k + 1].price - W[k].price) for k in range(0, len(W) - 1, 2)]
        if not _shrinking(pushes):
            continue
        up, lo = _first2(hs, "upper", 1, cmp), _first2(ls, "lower", -1, cmp)
        if up is None or lo is None or not (up.slope < lo.slope if falling else lo.slope > up.slope):
            continue
        l24, l13 = (up, lo) if falling else (lo, up)
        l24.name, l13.name = "2-4 line", "1-3 line"
        facts = {"pushes": len(pushes), "legs": len(P)}
        if len(P) >= 5:
            W3, W5 = P[2], P[4]
            facts["final_leg_short"] = cmp.rel(W5, W3) != "beyond"         # 5 did not go beyond 3 ⇒ "incomplete wedge" evidence
        return {"family": "falling_wedge" if falling else "rising_wedge", "swings": W, "bias": 1 if falling else -1,
                "lines": [up, lo], "legs_done": len(P), "line24": l24.name, "facts": facts}
    return None


def _flag(S, j, cmp, lo_bound):
    """Flag / pennant (K11.1 / K11.2) ending at swing j: a pole leg O→P that broke structure (P beyond the swing of its kind before O),
    then the flag F = P … j (≥ 2 highs and 2 lows) whose every leg is smaller than the pole and which stays short of the pole's origin.
    Up pole: highs and lows falling or flat (sloping against the pole / flat; both flat = a rectangle, reported there) = bull flag;
    highs falling + lows rising (converging) = bull pennant. Down pole mirror."""
    for i in range(j - 4, max(lo_bound, 1) - 1, -1):
        X, O, P = S[i - 1], S[i], S[i + 1]
        F = S[i + 1:j + 1]
        if len(F) < 4:
            continue
        hs, ls = [p for p in F if p.kind == "H"], [p for p in F if p.kind == "L"]
        hd, ld = cmp.side_dir(hs), cmp.side_dir(ls)
        if hd is None or ld is None:                                       # a mixed side stays mixed for every earlier pole
            break
        up = P.kind == "H"
        pole = abs(P.price - O.price)
        if cmp.rel(P, X) != "beyond":
            continue
        if any(lg >= pole for lg in _legs(F)):
            continue
        if any(((q.price - O.price) * (1 if up else -1)) <= 0 for q in F):   # never back to / past the pole's origin
            continue
        against = -1 if up else 1
        fam = None
        if (hd, ld) == (-1, 1):
            fam = "bull_pennant" if up else "bear_pennant"
        elif hd in (against, 0) and ld in (against, 0) and (hd, ld) != (0, 0):
            fam = "bull_flag" if up else "bear_flag"
        if fam is None:
            continue
        upl, lol = _envelope(hs, "upper", 1, cmp), _envelope(ls, "lower", -1, cmp)
        if upl is None or lol is None:
            continue
        deep = max(abs(q.price - P.price) for q in F)
        return {"family": fam, "swings": [O] + F, "bias": 1 if up else -1, "lines": [upl, lol],
                "facts": {"pole": [round(O.price, 2), round(P.price, 2)], "depth_of_pole": round(deep / pole, 3) if pole else None,
                          "flag_swings": len(F)}}
    return None


def _rectangle(S, j, cmp, lo_bound):
    """Rectangle / range (K11.3): the longest run of swings ending at j whose highs are all C-13 equal to its first high and whose lows
    are all equal to its first low, with ≥ 2 of each (two reactions on each edge). Edges = horizontal at those first swings; each edge's
    C-13 area (wick to body) is given as its band (the area for §2L)."""
    best = None
    for i in range(j - 3, lo_bound - 1, -1):
        W = S[i:j + 1]
        hs, ls = [p for p in W if p.kind == "H"], [p for p in W if p.kind == "L"]
        rels = [cmp.rel(p, hs[0]) for p in hs[1:]] + [cmp.rel(p, ls[0]) for p in ls[1:]]
        if all(r == "equal" for r in rels):
            best = W
        elif "short" in rels:                                              # a later swing short of the edge: no earlier reference
            break                                                          # makes it equal; a later swing BEYOND it may still be
    if best is None:
        return None
    hs, ls = [p for p in best if p.kind == "H"], [p for p in best if p.kind == "L"]
    return {"family": "rectangle", "swings": best, "bias": 0,
            "lines": [_horizontal(hs[0], "upper edge", 1, best[-1].bar), _horizontal(ls[0], "lower edge", -1, best[-1].bar)],
            "facts": {"touches_high": len(hs), "touches_low": len(ls), "upper_band": cmp.area(hs[0]), "lower_band": cmp.area(ls[0])}}


# ------------------------------------------------------------------------------------------------ pattern state
def _state(A, fine, pat, t):
    """The pattern's state at t from its boundaries' §2K states (bars after the pattern's last swing … t)."""
    fam, e = pat["family"], pat["swings"][-1].bar
    apex = _apex(pat["lines"], e)
    pat["apex"] = apex
    upto = t if apex is None else min(t, apex)                             # past the apex the converging lines are no boundary
    pat["upto"] = upto
    bnd = {}
    for ln in pat["lines"]:
        bnd[ln.name] = breakout_state(A, fine, ln, ln.side, e + 1, upto)
    pat["boundaries"] = bnd
    why = ""
    if fam in REVERSAL:
        nk = bnd["neckline"]
        far = breakout_state(A, fine, pat["far"], pat["far"].side, e + 1, t)
        pat["far_state"] = far
        far_first = far["accepted_bar"] is not None and (nk["first_close"] is None or far["first_close"] < nk["first_close"])
        if far_first:
            st, why = "failed", "accepted beyond the pattern's extreme before the neckline broke ⇒ continuation, not a reversal"
        elif nk["state"] == "beyond":
            st, why = "complete", "closed beyond the neckline (named); no swing beyond it yet"
        elif nk["state"] == "accepted":
            st, why = "broken", "neckline broken: close beyond + swing beyond"
        elif nk["state"] == "retested":
            st, why = "retested", "neckline broken, then retested from the broken side"
        elif nk["state"] in ("fakeout", "failed") or nk["fakeouts"] or nk["failed_bar"] is not None:
            st, why = "failed", ("neckline closed through and came back inside (false break) ⇒ name cancelled"
                                 if nk["state"] == "fakeout" else "neckline broken, then reclaimed (close + swing back inside)")
        else:
            st, why = "forming", "neckline not closed through yet (candidate)"
        pat.update(state=st, why=why, break_side=nk["side"] if nk["first_close"] is not None else None,
                   named=nk["first_close"] is not None and not far_first)   # K11.0: named once it closed beyond the neckline
        return pat
    # continuation / range shapes: an accepted boundary decides (the earliest acceptance); else the boundary with the latest event
    if fam in ("falling_wedge", "rising_wedge"):
        b24 = bnd[pat["line24"]]
        base = "complete" if pat["legs_done"] >= 5 and b24["first_close"] is not None else "forming"
    elif fam in ("sym_triangle", "asc_triangle", "desc_triangle", "broadening"):
        base = "complete" if pat["legs_done"] >= 5 else "forming"
    elif fam.endswith("_flag") or fam.endswith("_pennant"):
        last = pat["swings"][-1]
        base = "complete" if (last.kind == "L") == (pat["bias"] > 0) else "forming"
    else:                                                                  # rectangle: 2 + 2 reactions ⇒ named
        base = "complete"
    st, side = base, None
    acc = [(b["accepted_bar"], name, b) for name, b in bnd.items() if b["state"] in ("accepted", "retested", "failed")]
    ev = [(b["events"][-1][0], name, b) for name, b in bnd.items() if b["events"]]
    pick = min(acc, key=lambda x: x[0]) if acc else (max(ev, key=lambda x: x[0]) if ev else None)
    if pick is not None:
        _, name, b = pick
        side = b["side"]
        against = pat["bias"] != 0 and side != pat["bias"] and fam != "rectangle"
        if b["state"] in ("accepted", "retested"):
            if against:
                st, why = "failed", f"{name} broken against the pattern's bias ⇒ the pattern is invalid"
            else:
                st = "broken" if b["state"] == "accepted" else "retested"
                why = f"{name} broken: close beyond + swing beyond" + (", then retested" if st == "retested" else "")
        elif b["state"] == "failed":
            st, why = "failed", f"{name} broken, then reclaimed (close + swing back inside)"
        elif b["state"] == "fakeout":
            why = f"{name}: closed through and came back inside (fakeout); the pattern stands"
        elif b["state"] == "sweep":
            why = f"{name}: swept (wick beyond, close back inside)"
        elif b["state"] == "beyond":
            why = f"{name}: closed beyond, no swing beyond yet (not accepted)"
    if pick is None and apex is not None and t > apex:
        st, why = "failed", "the apex passed without a close beyond either line (expired)"
    if not why:
        why = {"complete": "named", "forming": "candidate (not named yet)"}.get(base, "")
    if base == "forming" and why and st != "forming":
        why += " — the shape itself is still a candidate (not named)"
    pat.update(state=st, why=why, break_side=side, named=base == "complete")
    return pat


# ------------------------------------------------------------------------------------------------ core
def _role(pat, d):
    """KB K11.0 roles: P (inside the pullback), A (in the area / handover), E (reversal warning / contrary). d = trade side (+1 / −1)."""
    if d not in (1, -1):
        return None
    fam, bias = pat["family"], pat["bias"]
    if fam == "rectangle":
        return "A"
    if fam == "broadening":
        return "E"
    if fam in REVERSAL:
        return "A" if bias == d else "E"
    if bias == 0:
        return "P"
    return "P" if bias == d else "E"


def _evidence(pat, tf, d):
    nm = NAMES[pat["family"]]
    ln = pat["lines"][0]
    if pat.get("break_side") is not None:                                  # the decisive boundary
        ln = next((x for x in pat["lines"] if pat["boundaries"][x.name]["side"] == pat["break_side"]), ln)
    lvl = f"{ln.name} {ln.y1:,.2f}" if ln.slope == 0 else f"{ln.name} (sloped, {ln(pat['upto']):,.2f} at bar {pat['upto']})"
    role = pat.get("role")
    tag = {"E": " — against the trade side [E]", "A": " — on the trade side [A]", "P": " — pullback shape [P]"}.get(role, "")
    return f"{tf} {nm}: {STATE_WORDS[pat['state']]} · {lvl}{tag}"


def _brief(pat, tf, t, ts, d):
    sw = pat["swings"]

    def stamp(b):
        return str(ts[b]) if ts is not None else int(b)
    out = {"family": pat["family"], "name": NAMES[pat["family"]], "tf": tf, "state": pat["state"], "why": pat["why"],
           "named": bool(pat["named"]), "bias": pat["bias"], "role": _role(pat, d), "apex_bar": pat.get("apex"),
           "swings": [{"kind": p.kind, "price": round(p.price, 2), "bar": p.bar, "ts": stamp(p.bar), "known_bar": p.confirm_bar}
                      for p in sw],
           "start_bar": sw[0].bar, "end_bar": sw[-1].bar, "known_bar": max(p.confirm_bar for p in sw),
           "lines": [{**ln.brief(t), "until_bar": pat["upto"], "value_until": round(ln(pat["upto"]), 2)} for ln in pat["lines"]],
           "boundaries": pat["boundaries"], "break_side": pat.get("break_side"),
           "facts": pat.get("facts", {})}
    if "far_state" in pat:
        out["far"] = {**pat["far"].brief(t), "state": pat["far_state"]["state"]}
    out["evidence"] = _evidence({**pat, "role": out["role"]}, tf, d) if out["named"] else None
    return out


def find_patterns(A, swings, fine, t, tf="1H", d=None, ts=None, lo_end=0):
    """All pattern families at bar t from `swings` (pattern-degree pivots) and `fine` (structure swings for "swing beyond"). For each
    family: the most recent candidate (forming) and the most recent named instance, among the shapes that END at swing index ≥ `lo_end`
    (0 = all; a shape may start earlier). Returns a list of plain dicts, newest first."""
    t = int(t)
    S = known_swings(swings, t)
    fine = _as_fine(fine, t)
    cmp = _Cmp(A)
    seen, out = {}, []

    def take(p):
        if p is None:
            return
        fam, b0, b1 = p["family"], p["swings"][0].bar, p["swings"][-1].bar
        if (fam, False) in seen and (fam, True) in seen:
            return
        if any(q["family"] == fam and q["start_bar"] <= b0 and b1 <= q["end_bar"] for q in out):
            return                                                          # part of a newer shape of the same family
        p = _state(A, fine, p, t)
        key = (fam, bool(p["named"]))
        if key in seen:
            return
        seen[key] = _brief(p, tf, t, ts, d)
        out.append(seen[key])

    for j in range(len(S) - 1, max(lo_end, 3) - 1, -1):
        take(_double_triple(S, j, cmp))
        take(_head_shoulders(S, j, cmp))
        for p in _contracting(S, j, cmp):
            take(p)
        take(_wedge(S, j, cmp))
        take(_flag(S, j, cmp, 0))
        take(_rectangle(S, j, cmp, 0))
    out.sort(key=lambda p: (-p["end_bar"], p["family"]))
    return out


# ------------------------------------------------------------------------------------------------ V22 wrappers
def _arrays(V):
    lv = getattr(V, "levels", None)
    if lv is not None and getattr(lv, "A", None) is not None:
        return lv.A
    m = V.res["m15"]
    return {k: m[k].to_numpy(float) for k in ("open", "high", "low", "close")}


def _ts(V):
    lv = getattr(V, "levels", None)
    if lv is not None and getattr(lv, "ts", None) is not None:
        return list(lv.ts)
    m = (getattr(V, "res", None) or {}).get("m15")
    return list(m["timestamp"]) if m is not None else None


def degree_of(V, tf):
    """1H = the trend degree (`level_degree`, D2); 15M = one degree below (D1)."""
    if tf not in TFS:
        raise ValueError(f"patterns_pa: tf {tf!r} — {' / '.join(TFS)}")
    s = getattr(V, "s", None) or {}
    top = int(s.get("level_degree", 2))
    return top if tf == "1H" else max(top - 1, 0)


def fine_degree(V):
    """"A swing formed beyond" = a swing of the finest structure degree (as `levels._run`: swings2 structure_degrees)."""
    from swings2 import settings as S2
    res = V.res
    low = min((res.get("settings") or S2.DEFAULTS).get("structure_degrees", S2.DEFAULTS["structure_degrees"]))
    return next((d for d in sorted(res["pivots"]) if d >= low and res["pivots"].get(d)), low)


def _bound(V, deg, t, S):
    """Relevance by structure: a shape must END in the current leg of the next higher degree or in the full swing before it (from that
    degree's 3rd-last confirmed swing on). Fewer such swings ⇒ the whole known history."""
    hi = sorted(int(p.bar) for p in (V.res["pivots"].get(deg + 1) or []) if int(p.confirm_bar) <= t)
    if len(hi) < 3:
        return 0
    return next((k for k, p in enumerate(S) if p.bar >= hi[-3]), 0)


def read_patterns(V, t, d=None, tf="1H"):
    """Chart patterns at bar t on the timeframe's swings (evidence only). d = trade side (+1 bull put / −1 bear call / None) — only the
    K11.0 role tag depends on it. Returns {tf, degree, patterns, evidence, candidates, retest_levels}."""
    deg = degree_of(V, tf)
    A = _arrays(V)
    piv = V.res["pivots"].get(deg) or []
    S = known_swings(piv, t)
    lo = _bound(V, deg, t, S)
    fine = _Fine(V.res["pivots"].get(fine_degree(V)) or [], t)
    pats = find_patterns(A, piv, fine, t, tf=tf, d=d, ts=_ts(V), lo_end=lo)
    return {"tf": tf, "degree": deg, "patterns": pats,
            "evidence": [p["evidence"] for p in pats if p["named"]],
            "candidates": [f"{tf} {p['name']} (candidate)" for p in pats if not p["named"]],
            "retest_levels": _retest(pats, t)}


def _retest(pats, t):
    out = []
    for p in pats:
        if p["state"] not in ("broken", "retested") or not p["named"]:     # K11.0: a candidate's line is not a pattern boundary
            continue
        for ln in p["lines"]:
            b = p["boundaries"].get(ln["name"])
            if not b or b["state"] not in ("accepted", "retested") or b["side"] != p["break_side"] or ln["until_bar"] < t:
                continue                                                   # only the decisive break, while it is still a boundary
            out.append({"src": "pattern", "pattern": p["family"], "tf": p["tf"], "boundary": ln["name"], "p0": ln["p0"],
                        "p1": ln["p1"], "slope": ln["slope"], "value_t": ln["value_t"],
                        "role": "support" if b["side"] > 0 else "resistance", "break_dir": b["side"],
                        "accepted_bar": b["accepted_bar"], "swing_beyond": b["swing_beyond"], "retests": b["retests"],
                        "state": b["state"]})
    return out


def retest_levels(V, t, d=None, tf="1H"):
    """E4(b) hook (wiring in T9; entry_models.py untouched): every accepted (broken) pattern boundary at t as a retest level — the line
    (p0, slope ⇒ value at any bar), its new role (support after an up-break, resistance after a down-break), the swing beyond, retests."""
    return read_patterns(V, t, d=d, tf=tf)["retest_levels"]


def draw_objects(V, t, d=None, tf="1H", read=None):
    """Objects for the chart track: one "pattern" object per pattern (its swings as `points`) and one "pattern_boundary" per line,
    drawn from its first anchor to bar t (converging lines: to their apex). {kind, tf, t0, t1, p0, p1, label, state, evidence}."""
    r = read or read_patterns(V, t, d=d, tf=tf)
    ts = _ts(V)

    def stamp(b):
        return str(ts[b]) if ts is not None else int(b)
    objs = []
    for p in r["patterns"]:
        pr = [s["price"] for s in p["swings"]]
        objs.append({"kind": "pattern", "tf": tf, "t0": stamp(p["start_bar"]), "t1": stamp(p["end_bar"]), "p0": min(pr), "p1": max(pr),
                     "label": p["name"], "state": p["state"], "evidence": p["evidence"],
                     "points": [[s["ts"], s["price"]] for s in p["swings"]]})
        for ln in p["lines"]:
            b = p["boundaries"].get(ln["name"], {})
            objs.append({"kind": "pattern_boundary", "tf": tf, "t0": stamp(ln["p0"][0]), "t1": stamp(ln["until_bar"]), "p0": ln["p0"][1],
                         "p1": ln["value_until"], "label": f"{p['name']} {ln['name']}", "state": b.get("state"),
                         "evidence": p["evidence"]})
    return objs
