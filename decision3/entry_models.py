"""decision3/entry_models.py — Abhi 21 Oct: the four ENTRY MODELS that replace the old ③ gate (BOS impulse + K pullback) when
`entry_gate = models` (default). Built ONLY from the outputs the earlier layers already give — nothing new is read, no number:

  ① trend side (V22.step1 / step2: bear_call ⇒ resistance areas when Daily DOWN; bull_put mirror) · ② areas + their K4 state
  (Levels.snapshot / active) · ③-visit (V22.visit, method §3: ends only by structure) · commitment c0 with its volume test
  (method.commitment as V22._confirm calls it) · LTF CHoCH c1 (method.ltf_choch) · lines (trendline.channel_lines, both sides) ·
  the candle-form reader (method.reversal_form) · RSI / zone read / confirming evidence (layer 5 / 6a) for the label.

Armed while price VISITS a valid (alive, not BROKEN / DEAD) trade-side area:
  E1 Aggressive    — defaults (Abhi 21 Oct RC2 / 22 Oct: `entry_area_refine = setup_tf`, `entry_trigger_rule = traded_inside`): the
                     visit's first bar AT the refined 15M base inside the area (no earlier visit bar touched it, none closed beyond its
                     far edge), not closing beyond the base's far edge. Invalidation: beyond the refined base's far edge.
                     `entry_area_refine = area` (what-if / da7cbbc): the first bar of a NEW visit; invalidation beyond the area's far edge.
  E2 Confirmation  — the commitment candle (c0, incl. its volume comparison and the FUT-volume data-problem rule) inside the visit.
                     Invalidation: beyond the visit's extreme.
  E3 Structure     — LTF CHoCH by close inside the visit (c1). Invalidation: beyond the visit's extreme.
  E2 / E3 never fire while the zone study reads absorption without a handover at the trigger bar (Abhi 21 Oct, the 13 Oct principle:
  `Reader.absorbing` — the existing handover_episode + zone_study readers, no number); E1 / E4 do not read it.
  E4 Sweep-retest  — (a) price goes beyond the area / the visit's extreme, closes back inside, and the next push (a swing of the finest
                     structure, confirmed) fails inside the sweep extreme; (b) a BROKEN line (channel_lines, close beyond + swing beyond)
                     or a BROKEN area (K4, broken in the trade direction) is revisited and a rejection candle (reversal_form) closes away
                     from it. Invalidation: beyond the sweep / retest extreme.
Trigger reading (Abhi 22 Oct, corrects the 21 Oct RC3 wording; §3 models / C lifecycle) — `entry_trigger_rule = traded_inside`: the
trigger candle has TRADED inside the visited area (its range overlaps the area's own band) AND — E1 / E2 / E3 / E4 (a), refined base on —
its own range trades into the refined 15M base (Abhi 22 Oct: the refined base exists so entry and invalidation come from the narrow
base; a candle that never touches it brings back the wide invalidation; with `entry_area_refine = area` the visited area is the base) and
price is not beyond the INVALIDATION side (no close beyond the far edge / the model's invalidation; E1: the refined base not already
closed through in the visit). A close OUTSIDE the area on the TRADE-DIRECTION side is allowed — that close is the confirmation (a
commitment / rejection candle trades into the area and closes away from it). E4 (b): the rejection form trades at the retested object
and closes on its trade side. A gap / large candle through the INVALIDATION side is the area being broken (lifecycle), never an entry;
a candle that never traded inside the area never fires. What-ifs: `inside` = the 21 Oct RC3 reading (#364: the close inside the area's
own band), `legacy` = the da7cbbc trigger (no inside check). Edges, trigger and invalidation always come from the actual area being
visited (Z-1u): the overlapping cluster (`entry_cluster_rule = cluster`) only counts one signal per model per place — for E4 (b)
too: overlapping BROKEN areas (and a BROKEN line lying on them) of the same role and break direction revisited together are one
place (one E4 (b) per visit).
A DEAD area (flipped once, broken again — `levels.flip_dead_rule`) is never armed and never an E4 (b) object; the same for a BROKEN
line broken back (a close back beyond it on its original side + a swing of its degree formed there, `trendline.broken_back_at`).
Each model fires at most ONCE per visit (key = area id + visit start + model; the live layer prefixes the symbol): a model fires at bar
t when its condition holds at t and held at no earlier bar of the same visit (each earlier bar read only with what was known at it).
A stop-out never blocks the other models ⇒ up to four entries per visit. Models disarm when the area breaks (K4 "broken" / dead inside
the visit), when the visit ends (structure), or when the trend side changes (the window starts again at the new side's first bar).
The H2 hard rule stays: never a breakout entry — a trigger bar that opens / closes beyond the area's far edge, or a visit that came in
from the trade side, never fires (V22._at_area's own checks). The entry hours are the operational schedule (P2): a model whose bar is
outside them is consumed and listed, never an entry; so is one whose visit has the existing FUT-volume data problem (RF-2 b, Z-1c).
Range (Abhi's method L): the existing Daily RANGE (Q27) state — `Levels.active(t, "RANGE", band)` gives the edge areas (support in the
band's lower half, resistance in its upper half) — is read the same way: bull put at the lower edge, bear call at the upper (E1–E4 a;
E4 b is read for an UP / DOWN trend only); DECISIONS 40: the current Daily / 1H range edges from structure
(`range_edges.trade_edges`) are armed as areas too (trade side, `range_edge_areas`). E4 (b) approach side (DECISIONS 38,
`e4b_approach_rule`): a retest only from the break side. Lines (trendline.channel_lines / channels): both sides, both directions, on the trend
degree (1H) and D1 (15M), whatever the trend; a broken counter channel is listed as evidence (never a gate; a confirming piece of the A / B label under
`label_rule = model`, DECISIONS 54);
E4 (b) reads the main swings' broken lines + broken channel parallels, and `PATTERN_HOOK` (a broken pattern boundary — patterns track).
Bars ≤ t only; LTF bars ≤ the bar's close; swings confirmed by the bar being read. No order, no broker, no AI call.
"""
import numpy as np
import pandas as pd

from . import flip as FL
from . import liquidity as LQ
from . import method as M
from . import pa_evidence as PE
from . import trendline as TL

MODELS = ("E1", "E2", "E3", "E4")
# Hook (Abhi 21 Oct, patterns track): a callable (V, t, d) ⇒ [broken pattern boundary / neckline as a line dict — kind "H" / "L",
# p1 [bar, price], slope, broken True, break_bar, break_side "up" / "down", id, degree] — E4 (b) reads them as broken lines. None = no
# pattern module yet (lines + areas only).
PATTERN_HOOK = None
NAME = {"E1": "Aggressive", "E2": "Confirmation", "E3": "Structure", "E4": "Sweep-retest"}
MARK = {"present": "✓", "absent": "✗", "NA": "NA"}
CONF_NAME = {"volume_growing": "volume growing inside", "rsi_divergence": "RSI divergence", "confluence": "confluence",
             "correction_line_closed_through": "correction line closed through", "counter_channel_broken": "counter channel broken"}
# DECISIONS 54 (owner rule, `label_rule = model`): the five confirming pieces of the A / B label, in this order — each mapped to the fact
# the engine already reads (never a new reading): RSI divergence (layer 5, V22.rsi_divergence), volume growing inside (the zone read's
# trade-side volume rising, flip.zone_read summary vol_rising_trade_side), confluence (L6-a / Z-1u: a line meets the area or a Daily /
# Weekly area overlaps it), correction line closed through (L4: the open pullback's K line broken, trendline.k_line), counter channel
# broken (T3 / K6.5: a channel against the trade broken in the trade direction, Reader.channel_evidence).
LABEL_PIECES = ("rsi_divergence", "volume_growing", "confluence", "correction_line_closed_through", "counter_channel_broken")
LABEL_RULES = ("evidence_count", "model55", "model54", "legacy")
# DECISIONS 58 (owner rule, `label_rule = evidence_count`, default): NO A / B label — every output shows the evidence list + its count
# (information only, no threshold, never blocks); confluence = a DAILY area overlapping the traded area (a Weekly overlap never counts —
# Weekly stays context) or an object of a different kind (a line, a liquidity pool) at the same place. `model55` / `model54` = the A / B
# labels of DECISIONS 55 / 54 (what-ifs); `legacy` = the old 6a set.
# DECISIONS 55 (owner rule, `label_rule = model`): two pieces tightened — "counter channel broken" = only the PULLBACK's (correction's)
# channel at the trend degree (1H; Reader.pullback_channel); "confluence" = only a Daily / Weekly area overlapping the traded area, or an
# object of a different kind (a line, a liquidity pool) lying AT the same place (Reader.same_place) — overlap by comparison, nearness
# never counts. `model54` = the DECISIONS 54 reading of those two pieces (what-if).


def revisit_start(touch_bars, swings, struct=()):
    """DECISIONS 64 (a revisit of a broken object ends by structure, CLAUDE.md "the revisit ends when price leaves it by structure"):
    touch_bars = the bars touching the object; swings = [(bar, does_not_reach)] — the finest swings known (confirmed) at the decision;
    struct = the bars of the structure-degree swings built away that do not reach it (the RC4 end, as before). The revisit starts at
    the first touch and ends when price leaves and builds swings away that do not reach the object again: a structure swing that does
    not reach it, or two consecutive finest swings formed after the start (a swing away and the next turn) that both do not reach it.
    A finest swing that reaches it keeps the revisit going. ⇒ the start bar of the revisit in progress, or None."""
    ev = {}
    for b in touch_bars:
        ev.setdefault(int(b), [False, [], False])[0] = True
    for b, nr in swings:
        ev.setdefault(int(b), [False, [], False])[1].append(bool(nr))
    for b in struct:
        ev.setdefault(int(b), [False, [], False])[2] = True
    start, last_nr = None, False
    for i in sorted(ev):
        tch, sws, st = ev[i]
        if start is not None:
            if i <= start:
                continue
            if st:
                start = None
                continue
            for nr in sws:
                if nr and last_nr:
                    start = None
                    break
                last_nr = nr
            continue
        if tch:
            start, last_nr = i, False
    return start


def side_of(d):
    return "bear_call" if d < 0 else "bull_put"


class Reader:
    """One decision bar's entry-model read for a V22 instance (memoised per V22 across bars: a sequential run reads each bar once)."""

    def __init__(self, V, side_fn=None):
        self.V = V
        self.A = V.levels.A
        self.ts = V._ts
        self.memo = V.__dict__.setdefault("_em_memo", {})
        on = V.s.get("entry_models_on")
        self.on = tuple(MODELS if on is None else on)
        # Model C (DECISIONS 32, decision3/model_c.py): an injected trade side u ⇒ +1 / −1 / 0 (the C window of the counter-trend C leg)
        # replaces step1's Daily side. None (default) ⇒ today's path, byte for byte.
        self.side_fn = side_fn

    # ------------------------------------------------------------------------------------------ small facts
    def uid_of(self, lvl):
        """Abhi A5 / DECISIONS 62: the place's stable id (`Level.uid`) for an armed area / range edge — its visit id and the once-per-
        model-per-visit key use it, so a moved data window (a new `Level.id`) never opens a new visit for the same place. A range edge
        without a parent level ⇒ its own id."""
        lid = lvl.get("parent_level", lvl.get("id"))
        Ls = self.V.levels.L
        L = Ls[lid] if isinstance(lid, (int, np.integer)) and 0 <= int(lid) < len(Ls) else None
        return str(getattr(L, "uid", None) or lvl.get("uid") or lid)

    def T(self, i):
        return None if i is None else str(pd.Timestamp(self.ts[int(i)]))

    def trend_dir(self, u, role):
        """The trade direction for an area of this role at bar u (① as step1 reads it; no trade ⇒ 0). With an injected side (model C) the
        side function decides (its own memo; never the step1 memo)."""
        if self.side_fn is not None:
            return int(self.side_fn(int(u)))
        key = ("trend", int(u))
        if key not in self.memo:
            ok1, _w, _st, ctx = self.V.step1(int(u))
            self.memo[key] = ctx["trend"] if ok1 else None
        tr = self.memo[key]
        return 0 if tr is None else M._dir(tr, role)

    def side_since(self, t, role, d, floor):
        """The first bar ≥ floor from which the trend side stayed d up to t (models re-arm after a trend-side change)."""
        u = int(t)
        while u - 1 >= floor and self.trend_dir(u - 1, role) == d:
            u -= 1
        return u

    def P(self, i, d):
        """The push extreme of bar i on the side beyond the area's far edge (bear call: the high; bull put: −low) — mirrored coordinates."""
        return float(self.A["high"][i]) if d < 0 else -float(self.A["low"][i])

    def Cg(self, i, d):
        return float(self.A["close"][i]) if d < 0 else -float(self.A["close"][i])

    def back(self, x, d):
        return x if d < 0 else -x

    def h2_block(self, i, lvl, d):
        """H2 / P4 (V22._at_area's own checks): bar i gaps or closes beyond the area's far edge ⇒ a breakout, never an entry."""
        far = float(lvl["hi"]) if d < 0 else float(lvl["lo"])
        o, c = float(self.A["open"][i]), float(self.A["close"][i])
        if (o - far) * d < 0:
            return "gap through the far side of the area (breakout)"
        if (c - far) * d < 0:
            return "close through the far side of the area (breakout)"
        return None

    TRIGGER_RULES = ("traded_inside", "inside", "legacy")

    def trigger_rule(self):
        return str(self.V.s.get("entry_trigger_rule", "traded_inside"))

    def outside(self, i, lvl, d):
        """Is bar i a trigger AT the visited area (the actual area being visited, never a cluster's union, Z-1u)? None when it is, else
        the reason (a wait text). Comparison only.
          traded_inside (default, Abhi 22 Oct): bar i's range overlaps the area's band [lo, hi] and it does not close beyond the far edge
            (the invalidation side). A close outside on the TRADE side is allowed — the confirmation (it traded in, closed away).
          inside (#364, what-if): bar i's close inside [lo, hi].
          legacy (da7cbbc): no check (None)."""
        rule = self.trigger_rule()
        if rule == "legacy":
            return None
        lo, hi = float(lvl["lo"]), float(lvl["hi"])
        c = float(self.A["close"][i])
        far = hi if d < 0 else lo
        if (c - far) * d < 0:
            return "close beyond the area's far edge — the area is being broken (lifecycle), not entered"
        if rule == "traded_inside":
            if self.touches(i, lvl):
                return None
            return ("the candle did not trade inside the area — price has left the area on the trade side (the trigger candle must "
                    "trade inside the area)")
        if lo <= c <= hi:
            return None
        return "close outside the area on the trade side — price has left the area (a model fires only while price is inside it)"

    def off_base(self, i, rb):
        """Abhi 22 Oct (`traded_inside`, refined base on — E1 / E2 / E3 / E4 a): the trigger candle ITSELF must trade into the refined
        15M base (its range overlaps the base's band), not only into the wider context area — the refined base exists so entry and
        invalidation come from the narrow base. None ⇒ ok (or no refined base in use / another trigger rule), else the reason (a wait
        text). `inside` / `legacy` (what-ifs) are unchanged: the base reached in the visit is enough there."""
        if rb is None or self.trigger_rule() != "traded_inside" or self.touches(i, rb):
            return None
        return (f"the candle did not trade into the refined 15M base {float(rb['lo']):,.2f}–{float(rb['hi']):,.2f} (only the wider "
                f"context area) — the trigger candle must trade into the refined base (Abhi 22 Oct)")

    def beyond(self, i, inv, d):
        """Bar i's close beyond the model's invalidation price (bear call: above; bull put: below) ⇒ the reason, else None."""
        if inv is None or not self.inside_on():
            return None
        c = float(self.A["close"][i])
        return f"close beyond the invalidation {float(inv):,.2f}" if (c - float(inv)) * d < 0 else None

    def inside_on(self):
        """An inside-the-area reading is on (traded_inside or inside); legacy = the da7cbbc trigger."""
        return self.trigger_rule() != "legacy"

    def base_broken(self, start, u, rb, d):
        """RC3 lifecycle for the refined base: the first bar of the visit (start … u) that CLOSED beyond the base's far edge, or None.
        Such a base is being broken, not entered — E1 never fires on it (its invalidation would sit inside price already traded)."""
        far = self.rb_far(rb, d)
        return next((i for i in range(start, u + 1) if (float(self.A["close"][i]) - far) * d < 0), None)

    def refine_on(self):
        return str(self.V.s.get("entry_area_refine", "setup_tf")) == "setup_tf"

    def touches(self, i, band):
        return float(self.A["low"][i]) <= float(band["hi"]) and float(self.A["high"][i]) >= float(band["lo"])

    @staticmethod
    def rb_far(rb, d):
        if rb.get("inv_far") is not None:                                  # DECISIONS 83 (R5-2): a flipped area's invalidation = the
            return float(rb["inv_far"])                                    # band's far edge (opposite the new trade direction)
        return float(rb["hi"]) if d < 0 else float(rb["lo"])

    @staticmethod
    def farther(a, b, d):
        """The price farther on the invalidation side (bear call: the higher; bull put: the lower)."""
        return max(float(a), float(b)) if d < 0 else min(float(a), float(b))

    def ts64(self):
        """The 15M bar starts as datetime64 (memoised per V)."""
        if ("ts64",) not in self.memo:
            self.memo[("ts64",)] = np.asarray(pd.to_datetime(pd.Series(self.ts)), "datetime64[ns]")
        return self.memo[("ts64",)]

    def turns15(self):
        """A7 (Abhi, DECISIONS 63): the 15M turns the refined base reads — every turn the swing engine confirms on the setup timeframe
        (its finest degree, D0: the 15M chart's own swing highs / lows), in confirmation order. The levels' structure list
        (`Levels._known0`, D1) missed obvious 15M turns inside the band (L5-N03, N07, N04). A V without swing degrees (a test stub) ⇒
        `Levels._known0`."""
        key = ("turns15",)
        if key not in self.memo:
            piv = (getattr(self.V, "res", None) or {}).get("pivots") if isinstance(getattr(self.V, "res", None), dict) else None
            deg = min((k for k, v in (piv or {}).items() if v), default=None)
            src = piv[deg] if deg is not None else getattr(self.V.levels, "_known0", [])
            self.memo[key] = sorted(src, key=lambda p: (int(p.confirm_bar), int(p.bar)))
        return self.memo[key]

    def refine_base_rule(self):
        """Which 15M candle the refined base is (DECISIONS 79): "origin" (owner rule, default) = the area's ORIGIN base on 15M;
        "newest_turn" = the A7 / DECISIONS 63 reading (the newest 15M turn inside the band), what-if only."""
        from . import settings as S3
        r = str((getattr(self.V, "s", None) or {}).get("entry_area_refine_base", S3.DEFAULTS.get("entry_area_refine_base", "origin")))
        if r not in ("origin", "newest_turn"):
            raise ValueError(f"entry_area_refine_base {r!r} — origin / newest_turn")
        return r

    def refined(self, u, lvl, d):
        """The refined 15M base of an area at bar u — DECISIONS 79 (owner rule) by default (`refined_origin`); the A7 newest-turn
        reading (`refined_turn`) only as the what-if `entry_area_refine_base = newest_turn`."""
        if self.refine_base_rule() == "newest_turn":
            return self.refined_turn(u, lvl, d)
        return self.refined_origin(u, lvl, d)

    def hour_start(self):
        """The start of the 1H candle (09:15-anchored, as levels.h1_frame) holding each 15M bar (memoised per V)."""
        if ("h1start",) not in self.memo:
            from . import levels as LVM
            ts = pd.Series(pd.to_datetime(pd.Series(self.ts)).to_numpy())
            g, of = LVM.h1_frame(pd.DataFrame({"timestamp": ts, "open": 0.0, "high": 0.0, "low": 0.0, "close": 0.0}))
            self.memo[("h1start",)] = np.asarray(pd.to_datetime(g["timestamp"]).to_numpy()[of], "datetime64[ns]")
        return self.memo[("h1start",)]

    def base_candle_bars(self, tf, start):
        """The 15M bars inside the higher-TF base candle that starts at `start` (1H: its hour; D: its day; W: its week; memoised)."""
        t = pd.Timestamp(start)
        mk = ("basebars", str(tf), t)
        if mk in self.memo:
            return self.memo[mk]
        ts = pd.to_datetime(pd.Series(self.ts))
        if str(tf) == "1H":
            m = self.hour_start() == np.datetime64(self.hour_start_of(t))
        elif str(tf) == "W":
            iso, ref = ts.dt.isocalendar(), t.isocalendar()
            m = ((iso["year"] == ref[0]) & (iso["week"] == ref[1])).to_numpy()
        else:
            m = (ts.dt.normalize() == t.normalize()).to_numpy()
        self.memo[mk] = np.flatnonzero(m)
        return self.memo[mk]

    def hour_start_of(self, t):
        """The 1H candle start holding time t (a 15M bar start inside the data ⇒ its hour; else t itself)."""
        i = int(np.searchsorted(self.ts64(), np.datetime64(t), side="right")) - 1
        return pd.Timestamp(self.hour_start()[i]) if i >= 0 and self.ts64()[i] == np.datetime64(t) else t

    def refined_origin(self, u, lvl, d):
        """DECISIONS 79 (owner rule, replaces DECISIONS 63 / A7-1): the refined base = the ORIGIN base of the area on 15M — the 15M
        candle(s) inside the area's higher-TF base candle (1H hour / Daily day / Weekly week, `Level.base_ts`; a range edge: its anchor
        swing candle) from which the departure move started, i.e. the 15M candle(s) holding that base candle's extreme on the base's
        side (a supply / H base: its high; a demand / L base: its low), as their wick to body (levels._band_swing: no wick ⇒ the body),
        kept inside the area band. Never a later test / turn candle that merely touched the area. The origin candles are known at the
        area's birth (only bars ≤ its birth bar and ≤ u are read — no look-ahead). The invalidation = its far edge (`rb_far`). The base
        candle has no 15M bars in the data (a prior Daily / Weekly area from before the 15M window) or its origin lies outside the
        visited band ⇒ the area's own band (the higher-TF wick to body itself, `origin` = False). Comparison only."""
        lid = lvl.get("parent_level", lvl.get("id"))
        key = ("rbo", str(lid), float(lvl["lo"]), float(lvl["hi"]), int(u), int(d))
        if key in self.memo:
            return self.memo[key]
        from . import levels as LVM
        lo, hi = float(lvl["lo"]), float(lvl["hi"])
        Ls = self.V.levels.L
        L = Ls[lid] if isinstance(lid, (int, np.integer)) and 0 <= int(lid) < len(Ls) else None
        if L is not None:
            tf, start, born = getattr(L, "tf", None) or lvl.get("tf"), getattr(L, "base_ts", None), int(getattr(L, "born_bar", 0) or 0)
            uid = str(getattr(L, "uid", "") or "").split(":")
            side = uid[1] if len(uid) > 2 and uid[1] in ("H", "L") else ("H" if getattr(L, "role0", None) == LVM.RES else "L")
        else:                                                              # a range edge: its anchor swing candle
            tf, start, born = lvl.get("tf"), lvl.get("anchor_ts"), int(lvl.get("born_bar") or 0)
            edge = lvl.get("range_edge")
            side = ("H" if edge == "upper" else "L") if edge else ("H" if d < 0 else "L")
        A = self.A
        out = None
        dp = getattr(self.V.levels, "dp", None)                            # DECISIONS 84: a data-problem bar is never the origin
        bars = [] if start is None else [int(b) for b in self.base_candle_bars(tf, start) if int(b) <= min(born, int(u))
                                         and not (dp is not None and len(dp) > int(b) and dp[int(b)])]
        if bars:
            ext = (max if side == "H" else min)(float(A["high" if side == "H" else "low"][b]) for b in bars)
            org = [b for b in bars if float(A["high" if side == "H" else "low"][b]) == ext]
            bands = [LVM._band_swing(side, A["open"][b], A["high"][b], A["low"][b], A["close"][b], ext, 0) for b in org]
            blo, bhi = max(min(x[0] for x in bands), lo), min(max(x[1] for x in bands), hi)
            if blo <= bhi:
                b = org[-1]
                out = {"lo": round(blo, 2), "hi": round(bhi, 2), "bar": b, "bars": org, "ts": self.T(b), "price": round(ext, 2),
                       "kind": side, "tf": "15M", "origin": True, "context_id": lid,
                       "context_uid": self.uid_of(lvl) if L is not None else None,
                       "what": f"15M origin base {self.T(org[0])[:16]}{' …' if len(org) > 1 else ''} (the {'high' if side == 'H' else 'low'} "
                               f"of the {lvl.get('tf')} base candle {str(pd.Timestamp(start))[:16]}) of area {self.uid_of(lvl)}"}
        if out is None and (L is not None or start is not None):           # no 15M origin in the data ⇒ the area's own band
            out = {"lo": round(lo, 2), "hi": round(hi, 2), "bar": born, "bars": [], "ts": self.T(born) if born < len(self.ts) else None,
                   "price": round(hi if side == "H" else lo, 2), "kind": side, "tf": lvl.get("tf"), "origin": False, "context_id": lid,
                   "context_uid": self.uid_of(lvl) if L is not None else None,
                   "what": f"the {lvl.get('tf')} area's own band (its base candle has no 15M origin inside the band in the data)"}
        flipped = L is not None and any(k == "flip" and int(b) <= int(u) for b, k, *_ in (getattr(L, "events", None) or []))
        if out is not None and flipped:                                    # DECISIONS 83 (R5-2): a FLIPPED area — the location
            out = {**out, "inv_far": round(hi if d < 0 else lo, 2), "flipped": True,   # stays the original base; the invalidation =
                   "what": out["what"] + " — flipped area: invalidation = the band's far edge"}   # the band's far edge opposite the trade
        self.memo[key] = out
        return out

    def refined_turn(self, u, lvl, d):
        """WHAT-IF (`entry_area_refine_base = newest_turn`; the A7 reading, replaced by DECISIONS 79). RC2 (Abhi 21 Oct, research default `entry_area_refine = setup_tf`, review after replay): the 1H / Daily area (levels'
        TA4 band) is the CONTEXT — where. Inside it, the REFINED BASE on the setup timeframe (15M) by the same TA4 rule — Abhi A7
        (DECISIONS 63): the NEWEST 15M turn of the area's side inside the band, as its wick to body. A turn = a 15M swing (`turns15`: a
        swing high for a supply / bear call, a swing low for a demand / bull put) confirmed by bar u, from the area's own birth turn on
        (the newest such turn known when the area was born, at or after its own base candle; none ⇒ the area's birth bar); it is inside
        the band when its swing candle's wick to body (levels._band_swing: no wick ⇒ the body) trades into the band — a turn whose
        extreme pokes just beyond the band (a sweep) is still the turn at the area. Its band is that wick to body, kept inside the context band (never beyond the
        area, Z-1u). None ⇒ no refined base yet (the models wait). Comparison only, bars ≤ u."""
        lid = lvl.get("parent_level", lvl.get("id"))
        key = ("rb", str(lid), float(lvl["lo"]), float(lvl["hi"]), int(u), int(d))
        if key in self.memo:
            return self.memo[key]
        from . import levels as LVM
        lo, hi = float(lvl["lo"]), float(lvl["hi"])
        kind = "H" if d < 0 else "L"
        L = self.V.levels.L[lid] if isinstance(lid, (int, np.integer)) and 0 <= int(lid) < len(self.V.levels.L) else None
        born = int(getattr(L, "born_bar", 0) or 0) if L is not None else int(lvl.get("born_bar") or 0)   # a range edge: its own birth
        A = self.A
        bts = getattr(L, "base_ts", None) if L is not None else None       # the area's own base candle: a turn from before it (another
        base0 = int(np.searchsorted(self.ts64(), np.datetime64(pd.Timestamp(bts)))) if bts is not None else 0   # era, e.g. a flipped
                                                                           # area's old side) is never its birth turn

        def band(p):
            b = int(p.bar)
            return LVM._band_swing(kind, A["open"][b], A["high"][b], A["low"][b], A["close"][b], float(p.price), 0)

        sw = []
        for p in self.turns15():
            if int(p.confirm_bar) > u:
                break
            if p.kind != kind:
                continue
            blo, bhi = band(p)
            if blo <= hi and bhi >= lo:                                    # its wick to body trades into the band
                sw.append((p, blo, bhi))
        birth = [p for p, _, _ in sw if p.confirm_bar <= born and int(p.bar) >= base0]
        floor = max(int(p.bar) for p in birth) if birth else born
        cands = [x for x in sw if int(x[0].bar) >= floor]
        out = None
        if cands:
            p, blo, bhi = max(cands, key=lambda x: (int(x[0].bar), int(x[0].confirm_bar)))
            b = int(p.bar)
            blo, bhi = max(blo, lo), min(bhi, hi)
            if blo <= bhi:
                out = {"lo": round(blo, 2), "hi": round(bhi, 2), "bar": b, "ts": self.T(b), "price": round(float(p.price), 2),
                       "kind": kind, "tf": "15M", "context_id": lid, "context_uid": self.uid_of(lvl) if L is not None else None,
                       "what": f"15M {'swing high' if kind == 'H' else 'swing low'} {self.T(b)[:16]} inside {lvl.get('tf')} area "
                               f"{self.uid_of(lvl)}"}
        self.memo[key] = out
        return out

    def came_from_trade_side(self, start, lvl, d):
        far = float(lvl["hi"]) if d < 0 else float(lvl["lo"])
        pc = float(self.A["close"][start - 1]) if start > 0 else float(self.A["close"][start])
        return (pc - far) * d < 0

    def data_problem(self, start, t):
        """Abhi RF-2 (b) / Z-1c, the existing data-problem rule: FUT volume given but missing on more than `vol_gap_max_frac` of the
        visit's bars ⇒ a data problem, no entry (fail-closed) — for every model, as for the commitment. FUT not given at all ⇒ None here
        (E2's own c0_volume_required rule; the live feed refuses to run without FUT)."""
        g = self.V.vol_gaps(start, t)
        if g and g["over"]:
            return (f"data problem: FUT volume missing on all {g['m']} visit bars" if g["n"] == g["m"] else
                    f"data problem: FUT volume gaps {g['n']}/{g['m']} bars in the visit (> {g['limit']:.0%}, vol_gap_max_frac)")
        return None

    # ------------------------------------------------------------------------------------------ per-bar conditions (bars ≤ u only)
    def c0(self, u, lvl, d, start, appr):
        """c0 exactly as V22._confirm reads it for this visit at bar u: method.commitment (forms, dominance in the visit, the volume
        comparison with the approach leg + the visit's opposite side; the rejected push excluded) + the FUT-volume data-problem rule."""
        V = self.V
        key = ("c0", lvl.get("parent_level", lvl.get("id")), int(u), int(d), float(lvl["lo"]), float(lvl["hi"]), int(start))
        if key in self.memo:
            return self.memo[key]
        Av, _lab = V.vol_view(start, u)
        ho = V.handover_episode(Av, start, u, d, lvl)
        push = [int(ho["seen_at"]) - 1] if ho.get("form") == "sharp_reversal" and ho.get("seen_at") is not None else []
        ok, why, cm = M.commitment(Av, u, d, lvl, V.s, V._ts, win=start, approach=appr, exclude=push)
        if ok and cm.get("vol_na") and bool(V.s.get("c0_volume_required", True)):
            ok, why = False, "data problem: " + (V.vol_na_reason(u, Av) or "FUT volume missing")
        gaps = V.vol_gaps(start, u)
        if ok and gaps and gaps["over"]:
            ok, why = False, f"data problem: FUT volume gaps {gaps['n']}/{gaps['m']} bars in the visit (> {gaps['limit']:.0%})"
        self.memo[key] = (bool(ok), why, cm)
        return self.memo[key]

    def absorbing(self, u, lvl, d, start):
        """Abhi 21 Oct (13 Oct principle): E2 / E3 never fire while the zone study reads ABSORPTION WITHOUT A HANDOVER at bar u — the
        existing readers only: V22.handover_episode (sticky per visit; a later absorption cancels it) and method.zone_study's absorption
        over the episode's window up to the bar before u (exactly the a2 read method.confirm makes before a commitment). Returns the
        zone study's line when absorbing without a handover, else None. E1 / E4 never read it (no "no entry" forced on them)."""
        V = self.V
        key = ("absorb", lvl.get("parent_level", lvl.get("id")), int(u), int(d), float(lvl["lo"]), float(lvl["hi"]), int(start))
        if key in self.memo:
            return self.memo[key]
        Av, _lab = V.vol_view(start, u)
        ho = V.handover_episode(Av, start, u, d, lvl)
        out = None
        a0 = int(ho.get("window_start", start))
        if not ho.get("present") and u - 1 >= a0:
            zs = M.zone_study(Av, a0, u - 1, d, V.s)
            if zs.get("absorption"):
                out = "absorption without a handover (zone study: " + (zs.get("line") or "the opposite side still absorbing") + ")"
        self.memo[key] = out
        return out

    def c1(self, u, lvl, d, start):
        """c1 exactly as V22._confirm reads it: LTF CHoCH by close from the arrival in the area (method.ltf_choch), LTF bars ≤ bar u's close."""
        V = self.V
        key = ("c1", float(lvl["lo"]), float(lvl["hi"]), int(u), int(d), int(start))
        if key in self.memo:
            return self.memo[key]
        if V.ltf is None:
            out = {"done": False, "code": M.C_LTF_MISSING, "line": "LTF: LTF data missing"}
        else:
            ta = pd.Timestamp(self.ts[start])
            out = M.ltf_choch(V.ltf, d, ta, ta, pd.Timestamp(V.bar_end[int(u)]), lvl=lvl)
        self.memo[key] = out
        return out

    def sweep(self, u, lvl, d, start):
        """E4 (a) at bar u: a sweep bar s (start ≤ s < u) — its push went beyond the area's far edge or beyond the visit's extreme so far
        and it closed back inside (not beyond the far edge), or a K4 "sweep" event of the area (excursion closed back before any swing
        formed beyond) — then no bar went beyond the sweep extreme, and the next push (the first swing of the finest structure on the
        push side after s, confirmed by u) failed inside it. Returns the newest such read or None."""
        V = self.V
        if u <= start:
            return None
        F = self.P_far(lvl, d)
        lid = lvl.get("parent_level", lvl.get("id"))
        L = V.levels.L[lid] if isinstance(lid, (int, np.integer)) and 0 <= int(lid) < len(V.levels.L) else None
        k4 = {int(b) for b, k, _ in (L.events if L is not None else []) if k == "sweep" and start <= b < u}
        kind = "H" if d < 0 else "L"
        sw = sorted((p for p in getattr(V.levels, "_known0", []) if p.kind == kind and p.confirm_bar <= u and start < p.bar <= u),
                    key=lambda p: p.bar)
        if not sw:
            return None
        ix = np.arange(start, u + 1)
        Pv = self.A["high"][ix] if d < 0 else -self.A["low"][ix]
        Cv = self.A["close"][ix] if d < 0 else -self.A["close"][ix]
        pm = np.maximum.accumulate(Pv)                                     # the visit's extreme up to each bar
        sm = np.maximum.accumulate(Pv[::-1])[::-1]                         # the highest push from each bar on
        for j in range(len(ix) - 2, -1, -1):                               # newest sweep first (s < u)
            s = int(ix[j])
            x_s = max(F, float(pm[j - 1])) if j > 0 else F
            if not ((Pv[j] > x_s and Cv[j] <= F) or s in k4):
                continue
            E = float(pm[j])                                               # the sweep extreme (the visit's furthest push up to the sweep)
            if float(sm[j + 1]) > E:
                continue                                                   # price went beyond it afterwards: that sweep failed
            nxt = next((p for p in sw if p.bar > s), None)
            if nxt is None:
                continue
            return {"sweep_bar": s, "sweep_ts": self.T(s), "sweep_extreme": round(self.back(E, d), 2),
                    "swept": "K4 sweep (closed back before a swing formed beyond)" if s in k4 and not Pv[j] > x_s else
                    ("the area's far edge" if x_s == F else "the visit's extreme"),
                    "push_bar": int(nxt.bar), "push_ts": self.T(nxt.bar), "push_price": round(float(nxt.price), 2),
                    "push_known_bar": int(nxt.confirm_bar)}
        return None

    def P_far(self, lvl, d):
        return float(lvl["hi"]) if d < 0 else -float(lvl["lo"])

    def rejection(self, u, d, touch_fn, start, away_fn):
        """E4 (b) at bar u: the candle-form reader finds a reversal form at u (method.reversal_form) and u closes away from the object,
        with u or u − 1 (inside the revisit) touching it."""
        if not (touch_fn(u) or (u - 1 >= start and touch_fn(u - 1))):
            return None
        if not away_fn(u):
            return None
        fm = M.reversal_form(self.A, u, d, self.V.s, self.V._ts)
        return None if fm is None else {"form": fm[0], "merged": int(fm[1])}

    ONE_CANDLE_FORMS = ("pin", "strong_close")                          # method.reversal_form's single-candle forms

    def retest_ok(self, u, form, touch, start, d):
        """E4 (b) at bar u — the inside-the-area rule for a retest (Abhi 21 Oct; the same under `traded_inside`, Abhi 22 Oct, and
        `inside`): the rejection form TRADES at the retested object (a bar of the form touches the broken area's band / the broken line:
        bar u itself for a one-candle form, u or u − 1 for a two-candle form), it closes on the object's trade side (`away`, already read
        by rejection — the confirmation) and not beyond the retest extreme. None ⇒ ok, else why. `legacy`: no check."""
        if not self.inside_on():
            return None
        bars = (u,) if form.get("form") in self.ONE_CANDLE_FORMS else (u, u - 1)
        if not any(i >= start and len(touch(i, i)) > 0 for i in bars):
            return "the rejection candle is not at the retested object (price already away from it)"
        ext = self.back(max(self.P(i, d) for i in range(start, u + 1)), d)
        return self.beyond(u, ext, d)                                      # guard: ext includes bar u, so today it never trips

    APPROACH_RULES = ("break_side", "any")
    FORM_SPAN = {"star": 2, "inside_break": 2}                          # forms read on u − 2 … u; the other two-candle forms: u − 1 … u

    def approach_rule(self):
        r = str(self.V.s.get("e4b_approach_rule", "break_side"))
        if r not in self.APPROACH_RULES:
            raise ValueError(f"e4b_approach_rule {r!r} — {' / '.join(self.APPROACH_RULES)}")
        return r

    def accepted_on_original_side(self, b_end, edge, d, swings):
        """DECISIONS 61 (BREAK-1, owner rule): was price ACCEPTED on the broken object's ORIGINAL side at the 15M bar b_end? The run of
        consecutive 15M closes on the original side ending at b_end HOLDS there when a swing of the hold side (`flip.hold_kind`: above a
        line / area broken down ⇒ a pullback low formed above it; mirror) formed inside that run and was CONFIRMED by b_end (bars ≤ b_end
        only — no look-ahead). One to a few marginal closes there without such a swing = a sweep: still the approach from the break side.
        edge(i) = the object's original-side edge at the 15M bar i; swings(b) = the structure's finest degree swings known by b (the
        swings the K4 hold reads, `Levels._known0` — areas and lines alike). Comparison only."""
        C = self.V.levels.A["close"]
        if b_end < 0 or b_end >= len(C):
            return False

        def orig(i):
            return (float(C[i]) - float(edge(i))) * d < 0
        if not orig(b_end):
            return False
        r0 = int(b_end)
        while r0 - 1 >= 0 and orig(r0 - 1):
            r0 -= 1
        hk = FL.hold_kind(d < 0)
        return any(p.kind == hk and r0 <= int(p.bar) and int(p.confirm_bar) <= b_end and (float(p.price) - float(edge(int(p.bar)))) * d < 0
                   for p in swings(int(b_end)))

    def approach_side(self, u, form, start, edge, d, accepted=None):
        """DECISIONS 38 (live reading check, H2): the retest of an object broken DOWN (bear call) needs price to come back UP to it from
        BELOW and be rejected there; a candle coming DOWN from above (the object's original side, where price was accepted) and closing
        through it is a breakdown candle — never an E4 (b). Mirror for bull puts. edge(i) = the object's original-side edge at bar i (a
        line: its value; a broken support area: its high; a broken resistance area: its low). Comparison only, bars ≤ u:
          • the revisit came from the break side — the close before the revisit's first bar is not beyond the original-side edge;
          • the rejection form's first candle opened from the break side — its open is not beyond the original-side edge (one-candle
            form: bar u; a two-candle form: its first candle).
        DECISIONS 61 (BREAK-1): "where price was accepted" = price HELD there (accepted(i) — the caller's structure test at the closing
        candle i, `accepted_on_original_side`); marginal closes on the original side without a swing held there are a sweep and the
        approach still counts from the break side. accepted None (`break_hold_rule = swing_beyond`, what-if) ⇒ any close there blocks.
        None ⇒ ok, else why (a wait text). `e4b_approach_rule = any` = the earlier reading (no approach check, what-if)."""
        if self.approach_rule() == "any":
            return None
        C, O = self.A["close"], self.A["open"]

        def orig(x, i):                                                    # beyond the object on its ORIGINAL side (bear call: above)
            return (float(x) - float(edge(i))) * d < 0

        def held(i):                                                       # accepted there (a hold), not a sweep (DECISIONS 61)
            return accepted is None or (i >= 0 and bool(accepted(i)))
        word = "above" if d < 0 else "below"
        p = int(start) - 1
        if p >= 0 and orig(C[p], p) and held(p):
            return (f"the revisit came from {word} the broken object (its original side, where price was accepted) — not a retest from "
                    f"the break side (DECISIONS 38, H2)")
        f0 = int(u) if form.get("form") in self.ONE_CANDLE_FORMS else int(u) - self.FORM_SPAN.get(form.get("form"), 1)
        if f0 >= 0 and orig(O[f0], f0) and held(f0 - 1):
            return (f"the rejection candle came from {word} the broken object and closed through it — a breakout / breakdown candle, "
                    f"never an E4 (b) (DECISIONS 38, H2)")
        return None

    # ------------------------------------------------------------------------------------------ one armed area
    def area(self, t, lvl, d):
        """The models' state for one trade-side area at bar t ⇒ (armed dict | None, [fired at t])."""
        V = self.V
        vi = V.visit(t, lvl, d)
        if vi["start"] is None:
            return None, []
        start = int(vi["start"])
        lid = lvl.get("parent_level", lvl.get("id"))
        L = V.levels.L[lid] if isinstance(lid, (int, np.integer)) and 0 <= int(lid) < len(V.levels.L) else None
        uid = self.uid_of(lvl)
        base = {"object": "area", "area_id": lid, "area_uid": uid, "tf": lvl.get("tf"), "role": lvl.get("role"), "lo": lvl["lo"],
                "hi": lvl["hi"], "state": lvl.get("state"), "direction": int(d), "side": side_of(d), "visit_id": f"{uid}@{self.T(start)}",
                "visit_start": self.T(start), "visit_start_bar": start, "labels": lvl.get("confluence_label")}
        models = {}
        if self.came_from_trade_side(start, lvl, d):
            base["disarmed"] = "price came into the area from the trade side (not a pullback — H2)"
            base["models"] = {m: {"status": "disarmed"} for m in MODELS}
            return base, []
        brk = [b for b, k, _ in (L.events if L is not None else []) if k in ("broken", "dead") and start <= b <= t]
        if L is not None and L.dead_bar is not None and start <= L.dead_bar <= t:
            brk.append(int(L.dead_bar))
        if brk:
            base["disarmed"] = f"the area broke inside this visit at {self.T(min(brk))} (K4: a close beyond + a swing beyond)"
            base["models"] = {m: {"status": "disarmed"} for m in MODELS}
            return base, []
        w0 = self.side_since(t, lvl.get("role"), d, start)
        if w0 > start:
            base["side_since"] = self.T(w0)

        def same_visit(u):
            return u == t or V.visit(u, lvl, d)["start"] == start

        def appr_at(u):
            v = vi if u == t else V.visit(u, lvl, d)
            return range(int(v["approach_from"]), start) if v.get("approach_from") is not None else None

        ext = max(self.P(i, d) for i in range(start, t + 1))
        base["visit_extreme"] = round(self.back(ext, d), 2)
        fired = []
        refine = self.refine_on()

        def at_area(u):                                                    # traded inside the visited area's band (traded_inside; the
                                                                           # close inside under `inside`), no breakout bar (H2)
            return self.h2_block(u, lvl, d) is None and self.outside(u, lvl, d) is None

        def ext_at(u):                                                     # the visit's extreme up to bar u (E2 / E3 invalidation)
            return self.back(max(self.P(i, d) for i in range(start, u + 1)), d)

        def rb_ok(u):
            """RC2: the refined base known at bar u and reached by price in this visit (start … u) ⇒ (True, base); no refined base
            yet / not reached ⇒ (False, None) — the models wait. Refinement off ⇒ (True, None): the context area itself."""
            if not refine:
                return True, None
            rb = self.refined(u, lvl, d)
            if rb is None or not any(self.touches(i, rb) for i in range(start, u + 1)):
                return False, None
            return True, rb

        def e1(u):
            if w0 != start or not at_area(u):
                return False, None
            if not refine:
                return u == start, None
            ok, rb = rb_ok(u)                                              # E1 = the first bar of the visit AT the refined base
            if not ok or not self.touches(u, rb) or any(self.touches(i, rb) for i in range(start, u)):
                return False, None
            if self.base_broken(start, u, rb, d) is not None:              # RC3 lifecycle: the base was already closed through in this
                return False, None                                         # visit ⇒ its far edge is not an invalidation any more
            return self.beyond(u, self.rb_far(rb, d), d) is None, rb

        def e23(u, m):
            if not at_area(u):
                return False, None
            ok, rb = rb_ok(u)
            if not ok or self.off_base(u, rb) is not None:                 # Abhi 22 Oct: the trigger candle trades into the base itself
                return False, None
            inv = self.farther(ext_at(u), self.rb_far(rb, d), d) if rb else ext_at(u)
            if self.beyond(u, inv, d) is not None:                         # guard only: inv includes this visit's extreme up to u,
                                                                           # so a close cannot be beyond it today (RC3 stated explicitly)
                return False, None
            if m == "E2":
                hit = self.c0(u, lvl, d, start, appr_at(u))[0]
            else:
                hit = bool(self.c1(u, lvl, d, start).get("done"))
            return bool(hit and self.absorbing(u, lvl, d, start) is None), rb

        def e4(u):
            r = self.sweep(u, lvl, d, start)
            if r is None or not at_area(u) or self.beyond(u, r["sweep_extreme"], d) is not None:   # beyond = guard (the sweep read
                                                                           # already requires no bar beyond its extreme)
                return False, None
            ok, rb = rb_ok(u)
            if not ok or self.off_base(u, rb) is not None:                 # Abhi 22 Oct: the trigger candle trades into the base itself
                return False, None
            return ok, ({**r, "refined": rb} if rb else r)

        conds = {"E1": e1, "E2": lambda u: e23(u, "E2"), "E3": lambda u: e23(u, "E3"), "E4": e4}
        for m in MODELS:
            if m not in self.on:
                models[m] = {"status": "off"}
                continue
            first = None
            for u in range(w0, t + 1):
                ok, info = conds[m](u)
                if ok and same_visit(u):
                    first = (u, info)
                    break
            if first is None:
                models[m] = {"status": "waiting" if m != "E1" else "passed", "waiting": self.waiting(m, t, lvl, d, start, w0, appr_at)}
                continue
            u, info = first
            if u < t:
                models[m] = {"status": "fired_earlier", "at": self.T(u), "bar": int(u)}
                continue
            inv, rule, facts = self.invalidation(m, t, lvl, d, start, info, appr_at(t))
            dp = self.data_problem(start, t)
            if dp:
                models[m] = {"status": "blocked_data_problem", "at": self.T(t), "bar": int(t), "note": dp + " — consumed, not an entry"}
                continue
            if not V.entry_window(t):
                models[m] = {"status": "fired_outside_hours", "at": self.T(t), "bar": int(t),
                             "note": "outside the entry hours (operational schedule) — consumed, not an entry"}
                continue
            models[m] = {"status": "fired", "at": self.T(t), "bar": int(t)}
            rb = (info or {}).get("refined") if m == "E4" else info
            fired.append({"model": m, "variant": "a" if m == "E4" else None, "invalidation": inv, "invalidation_rule": rule,
                          "facts": facts, "refined": rb})
        if getattr(V, "visit_end_new", False) and self.trigger_rule() == "traded_inside" and V.price_away(t, lvl, None):   # B-2: an open visit while price is away from the
            base["away"] = V.AWAY_NA                                       # area — no entry and no RSI read come from it
            for f in fired:
                models[f["model"]] = {"status": "waiting", "waiting": V.AWAY_NA}
            fired = []
        base["models"] = models
        return base, fired

    def waiting(self, m, t, lvl, d, start, w0, appr_at):
        """What an armed model is still waiting for at bar t (the reason text of a wait)."""
        if m == "E1":
            if w0 != start:
                return f"the trend side changed inside this visit ({self.T(w0)}) — E1 re-arms with the next visit"
            if self.refine_on():
                rb = self.refined(t, lvl, d)
                if rb is None:
                    return "no refined base yet: no 15M turn of the area's side inside its band (RC2) — E1 waits"
                base = f"the refined 15M base {rb['lo']:,.2f}–{rb['hi']:,.2f} ({rb['ts'][:16]})"
                brk = self.base_broken(start, t, rb, d)
                if brk is not None:
                    return (f"{base} was closed through in this visit at {self.T(brk)[:16]} (lifecycle: broken, not entered) — E1 "
                            f"re-arms with the next visit")
                touched = [i for i in range(start, t + 1) if self.touches(i, rb)]
                if not touched:
                    return f"waiting for price to reach {base}"
                if int(rb["bar"]) >= start:
                    return (f"{base} is a newer turn formed inside this visit (price was already at it) — E1 fires only on the first "
                            f"arrival at a base known before; E1 re-arms with the next visit")
                why = self.h2_block(touched[0], lvl, d) or self.outside(touched[0], lvl, d) or "it closed beyond the base's far edge"
                return (f"E1 fires only on the visit's first bar at {base}; that bar ({self.T(touched[0])[:16]}) did not qualify: "
                        f"{why} — E1 re-arms with the next visit")
            why = self.h2_block(start, lvl, d) or self.outside(start, lvl, d)
            return (f"E1 fires only on a new visit's first bar (this visit began {self.T(start)})" +
                    (f"; that bar did not qualify: {why}" if why else ""))
        blk = self.h2_block(t, lvl, d) or self.outside(t, lvl, d)
        if blk:
            return blk
        if self.refine_on():
            rb = self.refined(t, lvl, d)
            if rb is None:
                return ("no refined base yet: no 15M turn of the area's side inside its band (RC2) — the models wait")
            if not any(self.touches(i, rb) for i in range(start, t + 1)):
                return f"price has not reached the refined 15M base {rb['lo']:,.2f}–{rb['hi']:,.2f} in this visit yet"
            off = self.off_base(t, rb)
            if off:
                return off
        if m == "E2":
            ok, why, cm = self.c0(t, lvl, d, start, appr_at(t))
            if ok:
                return self.absorbing(t, lvl, d, start) or "no commitment"
            return why or "no commitment"
        if m == "E3":
            ch = self.c1(t, lvl, d, start)
            if ch.get("done"):
                return self.absorbing(t, lvl, d, start) or "no LTF CHoCH yet"
            return ch.get("line") or "no LTF CHoCH yet"
        F = self.P_far(lvl, d)
        if not any(self.P(i, d) > F for i in range(start, t + 1)):
            return "no sweep yet (price has not gone beyond the area's far edge / the visit's extreme and closed back)"
        return "sweep seen; waiting for the next push to fail inside the sweep extreme (a confirmed swing)"

    def invalidation(self, m, t, lvl, d, start, info, appr=None):
        """The model's invalidation — always from the ACTUAL visited area (Z-1u, never a cluster's union). RC2 (refined base on): E1 =
        beyond the refined 15M base's far edge; E2 / E3 = beyond the farther of the refined base's far edge and the visit's extreme;
        refinement off: E1 = the area's far edge, E2 / E3 = the visit's extreme. E4 = its sweep extreme."""
        word = "above" if d < 0 else "below"
        rb = info if m in ("E1", "E2", "E3") and isinstance(info, dict) and "lo" in info else None
        if m == "E1":
            if rb:
                far = self.rb_far(rb, d)
                return (round(far, 2), f"price {word} the refined 15M base's far edge {far:,.2f} (base {rb['ts'][:16]} inside area "
                        f"{lvl.get('id')})", {"refined": rb})
            far = float(lvl["hi"]) if d < 0 else float(lvl["lo"])
            return round(far, 2), f"price {word} the area's far edge {far:,.2f}", {}
        if m in ("E2", "E3"):
            ext = self.back(max(self.P(i, d) for i in range(start, t + 1)), d)
            if m == "E2":
                cm = self.c0(t, lvl, d, start, appr)[2] or {}
                facts = {k: cm.get(k) for k in ("form", "merged", "grade", "body_mult", "vol_mult", "vol_vs", "vol_ref_n")}
            else:
                ch = self.c1(t, lvl, d, start)
                facts = {k: ch.get(k) for k in ("line", "at", "label", "arrival_at")}
            if rb:
                far = self.rb_far(rb, d)
                inv = self.farther(ext, far, d)
                what = "the refined 15M base's far edge" if inv == far and far != ext else "the visit's extreme"
                return round(inv, 2), f"price {word} {what} {inv:,.2f} (refined base {rb['ts'][:16]})", {**facts, "refined": rb}
            return round(ext, 2), f"price {word} the visit's extreme {ext:,.2f}", facts
        return info["sweep_extreme"], f"price {word} the sweep extreme {info['sweep_extreme']:,.2f}", dict(info)

    # ------------------------------------------------------------------------------------------ range edges (concept L)
    RANGE_EDGE_TFS = ("D", "1H")                                        # the area timeframes (15M = the setup TF: refined base / trigger)

    def range_edges_on(self):
        r = str(self.V.s.get("range_edge_areas", "on"))
        if r not in ("on", "off"):
            raise ValueError(f"range_edge_areas {r!r} — on / off")
        return r == "on"

    def range_edge_areas(self, t, trend, act):
        """DECISIONS 40 (concept L, method §8 T7): in a range the range EDGES are the areas — bear call at the upper edge, bull put at
        the lower edge — and E1–E4 apply there as at any area. The edges = `range_edges.trade_edges` (the current Daily / 1H range from
        structure, each edge = its swing candle wick to body, fresh / tested, not broken / flipped / dead — the levels' own K4 machine),
        on the trade side only (P4: Daily DOWN ⇒ the upper edge, UP ⇒ the lower edge, RANGE ⇒ both), ahead of price as `Levels.active`
        reads an area (a resistance not below price, a support not above it). An edge whose band is an already armed area (same band,
        `same_level`) is that area. The visit counts from the bar the range is known (`visit_from`). `range_edge_areas = off` = the
        earlier reading (edges evidence only, what-if). Bars ≤ t only."""
        if not self.range_edges_on() or trend not in ("UP", "DOWN", "RANGE"):
            return []
        from . import range_edges as RE
        try:
            edges = RE.trade_edges(self.V, t, self.RANGE_EDGE_TFS)
        except Exception as exc:                                           # noqa: BLE001 — a reading error arms nothing (logged)
            import logging
            logging.getLogger(__name__).warning("entry models: range edges not read at bar %s: %s", t, exc)
            return []
        ids = {x.get("id") for x in act}
        out = []
        for e in edges:
            d = M._dir(trend, e.get("role"))
            if d == 0 or (e.get("range_edge") == "upper") != (d < 0) or e.get("same_level") in ids:
                continue
            if (d < 0 and e.get("below")) or (d > 0 and e.get("above")) or e.get("id") in ids:
                continue
            ids.add(e.get("id"))
            out.append({**e, "visit_from": int(e.get("born_bar") or 0)})
        return out

    # ------------------------------------------------------------------------------------------ E4 (b): broken objects
    def touch_visit(self, t, oid, born, touches, away_fn_swing, d):
        """A revisit of a broken object, by the visit's own structure rule (V22._visit_structure, sparse): it starts at the first bar
        that touches the object and ends at a swing (the finest structure, confirmed by t) built away from it after the start.
        touches(born, t) = the touching bars (array). RC4 (Abhi 21 Oct, 04 Aug BANKNIFTY: a line ~3,000 pts away held as "revisit in
        progress"): a broken object is being revisited only while price is actually back AT it (a line: the bar's range holds the
        line's value), and the revisit ends when price leaves it by structure — a new swing that does not reach it, on either side."""
        key = ("tv", oid, int(t), int(born), int(d))
        if key in self.memo:
            return self.memo[key]
        kind = "L" if d < 0 else "H"
        if getattr(self.V, "visit_end_new", False):                        # DECISIONS 64: swings away that do not reach it again
            tb = {int(i) for i in touches(born, t)}
            piv = [p for p in self.V.visit_swings() if p.confirm_bar <= t and born <= p.bar <= t]
            st = {int(p.bar) for p in getattr(self.V.levels, "_known0", []) if p.confirm_bar <= t and born <= p.bar <= t and
                  p.kind == kind and away_fn_swing(p)}
            self.memo[key] = revisit_start(tb, [(int(p.bar), bool(away_fn_swing(p))) for p in piv], st)
            return self.memo[key]
        piv = {int(p.bar) for p in getattr(self.V.levels, "_known0", []) if p.confirm_bar <= t and born <= p.bar <= t and
               p.kind == kind and away_fn_swing(p)}
        tb = {int(i) for i in touches(born, t)}
        start = None
        for i in sorted(tb | piv):
            if start is not None:
                if i in piv and i > start:
                    start = None
                continue
            if i in tb:
                start = i
        self.memo[key] = start
        return start

    def broken_objects(self, t, d, extra=None):
        """E4 (b): the trade-direction BROKEN areas (K4 state BROKEN, break_dir = d, a trade location by the existing selection) and the
        trade-direction BROKEN lines (channel_lines: a line of lows broken down for a bear call; of highs broken up for a bull put).
        extra = more broken line dicts (model C's pattern adapter, C-d) — a line carrying `known_bar` is known broken from that bar."""
        V = self.V
        A = self.A
        out = []
        want_state = FL.FLIPPED if FL.hold_rule(V.s) == "follow_through" else FL.BROKEN   # DECISIONS 77: E4 (b) only after BROKEN
        for x in V.levels.snapshot(t):                                     # (follow-through = code FLIPPED); never BEYOND_NOT_BROKEN
            if x.get("state") != want_state or int(x.get("break_dir") or 0) != int(d) or not x.get("trade_location", True):
                continue
            if x.get("broken_at") is None:
                continue
            lo, hi = float(x["lo"]), float(x["hi"])
            out.append(("area", x, lambda b, u, lo=lo, hi=hi: np.flatnonzero((A["low"][b:u + 1] <= hi) & (A["high"][b:u + 1] >= lo)) + b,
                        (lambda i, lo=lo: A["close"][i] < lo) if d < 0 else (lambda i, hi=hi: A["close"][i] > hi),
                        (lambda p, lo=lo, hi=hi: p.price < lo or p.price > hi), int(x["broken_at"]) + 1))   # RC4: away on either side
        want = "down" if d < 0 else "up"
        cands = list(TL.channel_lines(V, t))                                # the main swings' lines (both sides, both directions)
        cands += [c["parallel"] for c in TL.channels(V, t)]                 # + each channel's parallel (its broken line = a retest level)
        if PATTERN_HOOK is not None:                                       # hook: a broken pattern boundary / neckline (patterns track)
            cands += list(PATTERN_HOOK(V, t, d) or [])
        cands += list(extra or [])
        seen = set()
        for ln in cands:
            if not ln.get("broken") or ln.get("break_side") != want or ln["id"] in seen:
                continue
            seen.add(ln["id"])
            k = ln["known_bar"] if ln.get("known_bar") is not None else TL.break_known_at(V, ln)
            if k is None or k > t:
                continue
            if TL.broken_back_at(V, ln, t) is not None:                    # K6.5 mirror / C lifecycle: broken back (a close back on
                continue                                                   # its original side + a swing formed there) ⇒ no retest object

            def lv(i, ln=ln):
                return TL.line_value(ln, i)
            def touch(b, u, ln=ln):                                        # RC4: price actually AT the line — the bar's range holds it
                ii = np.arange(b, u + 1)
                yv = float(ln["p1"][1]) + float(ln["slope"]) * (ii - int(ln["p1"][0]))
                return ii[(A["high"][b:u + 1] >= yv) & (A["low"][b:u + 1] <= yv)]
            away = (lambda i, lv=lv: A["close"][i] < lv(i)) if d < 0 else (lambda i, lv=lv: A["close"][i] > lv(i))

            def aw_sw(p, ln=ln):                                           # RC4: a swing that does not reach the line, either side
                return not len(touch(int(p.bar), int(p.bar)))
            out.append(("line", ln, touch, away, aw_sw, int(k) + 1))
        return out

    def acceptance(self, kind, obj, edge15, d, k_of=None):
        """DECISIONS 61: accepted(i) for `approach_side` — price HELD on the object's original side at the closing candle i (k_of maps a
        candle of another frame — 5M — to the last 15M bar closed with it). None under `break_hold_rule = swing_beyond` (what-if)."""
        V = self.V
        if FL.hold_rule(V.s) != "hold":
            return None
        k0 = getattr(V.levels, "_known_hold", getattr(V.levels, "_known0", None))   # the hold degree (A-L1: D0) — areas and lines
        if kind == "line" and k0 is None:                                  # no finest structure known (old callers) ⇒ the line's own
            g = int(obj.get("degree") or V.s.get("level_degree", 2))       # degree

            def swings(b, g=g):
                return TL._known_deg(V, b, g)
        else:
            k0 = list(k0 or [])

            def swings(b, k0=k0):
                return [p for p in k0 if int(p.confirm_bar) <= b]
        if k_of is None:
            return lambda i: self.accepted_on_original_side(int(i), edge15, d, swings)
        return lambda i: self.accepted_on_original_side(int(k_of[int(i)]), edge15, d, swings)

    def broken(self, t, d, keep=None, extra=None):
        """E4 (b) for every broken object of the trade direction ⇒ ([armed dicts], [fired at t]). keep(kind, obj) (model C: its own
        object filters C-b / C-d / C-e) ⇒ only the objects it keeps; None ⇒ all (today)."""
        V = self.V
        armed, fired = [], []
        if "E4" not in self.on:
            return armed, fired
        for kind, obj, touch, away, aw_sw, born in self.broken_objects(t, d, extra):
            if born > t or (keep is not None and not keep(kind, obj)):
                continue
            oid = obj["id"] if kind == "area" else f"line:{obj['id']}"
            start = self.touch_visit(t, oid, born, touch, aw_sw, d)
            if start is None:
                continue
            role = obj.get("role") if kind == "area" else ("support" if d < 0 else "resistance")
            w0 = self.side_since(t, role, d, start)
            uid = self.uid_of(obj) if kind == "area" else oid
            base = {"object": "broken_" + kind, "area_id": oid, "area_uid": uid, "tf": obj.get("tf") if kind == "area" else "line",
                    "role": role, "lo": obj.get("lo") if kind == "area" else round(TL.line_value(obj, t), 2),
                    "hi": obj.get("hi") if kind == "area" else round(TL.line_value(obj, t), 2), "state": "BROKEN",
                    "direction": int(d), "side": side_of(d), "visit_id": f"{uid}@{self.T(start)}", "visit_start": self.T(start),
                    "visit_start_bar": int(start), "broken_at": self.T(obj.get("broken_at") if kind == "area" else obj.get("break_bar"))}
            if kind == "line":
                base["line"] = {k: obj.get(k) for k in ("id", "family", "tf", "p1", "p2", "slope", "touches", "break_bar", "parallel_of",
                                                         "degree", "kind", "break_side")}
            if kind == "area":
                L = V.levels.L[obj["id"]]
                back = [b for b, k, _ in L.events if k in ("reclaim", "flip", "dead") and start <= b <= t]
                if back:
                    base.update(disarmed=f"the broken area changed state inside the revisit at {self.T(min(back))}",
                                models={"E4": {"status": "disarmed"}})
                    armed.append(base)
                    continue
            if kind == "area":                                             # DECISIONS 38: the object's original-side edge
                e0 = float(obj["hi"]) if d < 0 else float(obj["lo"])
                edge = (lambda i, e0=e0: e0)
            else:
                edge = (lambda i, ln=obj: TL.line_value(ln, i))
            acc = self.acceptance(kind, obj, edge, d)                      # DECISIONS 61: a sweep there is still the break-side approach
            first, appr_why = None, None
            for u in range(w0, t + 1):
                if self.touch_visit(u, oid, born, touch, aw_sw, d) != start:
                    continue
                r = self.rejection(u, d, lambda i: len(touch(i, i)) > 0, start, away)
                if r is not None and self.retest_ok(u, r, touch, start, d) is None:
                    why = self.approach_side(u, r, start, edge, d, accepted=acc)
                    if why is not None:                                    # a breakdown candle / a revisit from the original side
                        appr_why = why
                        continue
                    first = (u, r)
                    break
            if first is None:
                base["models"] = {"E4": {"status": "waiting", "waiting": appr_why or ("revisit in progress; waiting for a rejection candle "
                                                                                      "that closes away from the broken " + kind)}}
            elif first[0] < t:
                base["models"] = {"E4": {"status": "fired_earlier", "at": self.T(first[0]), "bar": int(first[0])}}
            elif self.data_problem(start, t):
                base["models"] = {"E4": {"status": "blocked_data_problem", "at": self.T(t), "bar": int(t),
                                         "note": self.data_problem(start, t) + " — consumed, not an entry"}}
            elif not V.entry_window(t):
                base["models"] = {"E4": {"status": "fired_outside_hours", "at": self.T(t), "bar": int(t),
                                         "note": "outside the entry hours (operational schedule) — consumed, not an entry"}}
            else:
                ext = self.back(max(self.P(i, d) for i in range(start, t + 1)), d)
                word = "above" if d < 0 else "below"
                base["models"] = {"E4": {"status": "fired", "at": self.T(t), "bar": int(t)}}
                fired.append({"model": "E4", "variant": "b", "invalidation": round(ext, 2),
                              "invalidation_rule": f"price {word} the retest extreme {ext:,.2f}",
                              "facts": {**first[1], "object": "broken_" + kind, "retest_extreme": round(ext, 2)}, "obj": base,
                              "kind": kind, "raw": obj, "start": int(start)})
            armed.append(base)
        return armed, fired

    def line_move_from(self, t, ln, d, start):
        """DECISIONS 56 (L5-c, RSI evidence only): the move into the retest of a broken LINE begins — as for a broken area's retest — at the
        last swing built away from the object on the side price comes from: the finest structure's swings (Levels._known0) confirmed by
        bar t, formed at or after the line's break and before the revisit's first bar `start`, beyond the line's value at their own bar
        (bear call: a swing low below the line; bull put: a swing high above it). None ⇒ no such swing known (the RSI read says NA)."""
        kind = "L" if d < 0 else "H"
        bb = ln.get("break_bar")
        bb = int(bb) if bb is not None else int(ln["p1"][0])
        new = getattr(self.V, "visit_end_new", False)                      # DECISIONS 64 (B2): the LAST away swing known at t — it moves
        src = list(getattr(self.V.levels, "_known0", [])) + (list(self.V.visit_swings()) if new else [])   # forward inside the revisit
        end = int(t) + 1 if new else int(start)
        sw = [int(p.bar) for p in src if p.kind == kind and p.confirm_bar <= t and bb <= p.bar < end
              and ((float(p.price) < TL.line_value(ln, int(p.bar))) if d < 0 else (float(p.price) > TL.line_value(ln, int(p.bar))))]
        return max(sw) if sw else None

    # ------------------------------------------------------------------------------------------ evidence (layer 6a builders)
    def label_rule(self):
        r = str(self.V.s.get("label_rule", "evidence_count"))
        r = "model55" if r == "model" else r                               # the DECISIONS 55 name before 58 (what-if alias)
        if r not in LABEL_RULES:
            raise ValueError(f"label_rule {r!r} — {' / '.join(LABEL_RULES)}")
        return r

    def model_conditions(self, fired, trigger_tf="15M"):
        """DECISIONS 54: the fired model's OWN conditions by name, exactly the checks the model made at its trigger (Reader.area /
        Reader.broken and the Reader5 mirrors) — all held, or the model would not have fired. The wording follows the active what-if
        switches (entry_trigger_rule, entry_area_refine, e4b_approach_rule) so it never names a check that was not made."""
        m, var = fired.get("model"), fired.get("variant")
        rule, rb = self.trigger_rule(), fired.get("refined")
        if m == "E4" and var == "b":
            kind = fired.get("kind") or str((fired.get("facts") or {}).get("object", "")).replace("broken_", "")
            form = (fired.get("facts") or {}).get("form")
            out = ["trend side (the trade side)", f"a broken {kind} in the trade direction (not broken back / dead), revisited"]
            if self.approach_rule() == "break_side":
                out.append("the revisit came from the break side (DECISIONS 38)")
            out.append(f"a {trigger_tf} rejection form{f' ({form})' if form else ''} at the object, closing on its trade side")
            if self.inside_on():
                out.append("no close beyond the retest extreme")
            return out
        out = ["trend side (the trade side)", "a pullback visit to an alive trade-side area (not from the trade side, not broken)"]
        if rule == "legacy":
            pass
        elif rb is not None:
            out.append(f"the {trigger_tf} trigger candle traded into the refined 15M base" if rule == "traded_inside" else
                       f"the {trigger_tf} trigger candle at the area (close inside), the refined 15M base reached in the visit")
        else:
            out.append(f"the {trigger_tf} trigger candle traded inside the area" if rule == "traded_inside" else
                       f"the {trigger_tf} trigger candle closed inside the area")
        if m == "E1":
            out.append(f"the visit's first {trigger_tf} candle at the " + ("refined base (not closed through in the visit)" if rb is not None
                                                                         else "area"))
        elif m == "E2":
            out += [f"a {trigger_tf} commitment candle inside the visit with its FUT volume comparison", "no absorption without a handover"]
        elif m == "E3":
            out += ["an LTF CHoCH by close inside the visit", "no absorption without a handover"]
        elif m == "E4":
            sw = (fired.get("facts") or {}).get("swept")
            out += [f"a sweep beyond {sw or 'the far edge / the visit extreme'}, closed back inside",
                    "the next push failed inside the sweep extreme"]
        if rule != "legacy":
            out.append("no close beyond the invalidation")
        return out

    def evidence(self, t, d, lvl, arm, appr=None, move_from=None, cm=None, read_ok=None, fired=None, trigger_tf="15M"):
        """The 6a evidence list + label A / B for an entry at bar t (method.confirming_evidence / method_label / evidence_list — the
        same builders _level_eval uses): required set, confirming pieces, context facts. Never blocks, never changes the entry.
          label_rule = model (default, DECISIONS 54, owner rule; `fired` = the fired model's dict): the required set = the fired
            model's own conditions (model_conditions — every fired entry has it); A = + ≥ 1 of the five confirming pieces
            (LABEL_PIECES), B = the model's conditions only. The old 6a set (handover + c0 + volume + c1) stays as a fact
            (`legacy_required`).
          label_rule = legacy (what-if, or no `fired`): the required set as read (handover + c0 + volume + c1); the label is None when
            it reads absent (6a: A and B both need it)."""
        V = self.V
        A = self.A
        if cm is None:                                                     # a broken line: the same shared confirmation, window = revisit
            Av, vlabel = V.vol_view(arm, t)
            ho = V.handover_episode(Av, arm, t, d, lvl)
            ta = pd.Timestamp(self.ts[arm])
            cf = M.confirm(Av, arm, t, d, lvl, V.s, V._ts, ltf=V.ltf, ltf_times=(ta, ta, pd.Timestamp(V.bar_end[t])), handover=ho,
                           approach=appr)
            cm = dict(cf["commit"] or {})
            cm.update(handover_state={k: v for k, v in ho.items() if k != "events"}, choch=cf["choch"], confirm_wait=cf["wait"],
                      volume_measure=vlabel, arm_bar=int(arm))
            read_ok = bool(cf["ok"]) and not (cf["c0"] and cm.get("vol_na") and bool(V.s.get("c0_volume_required", True)))
        rsi = V.rsi_divergence(t, d, arm, lvl.get("tf", "1H") if lvl.get("tf") in ("1H", "D") else "1H", move_from)
        Av, vlabel = V.vol_view(arm, t)
        zr = FL.zone_read(Av, V.levels.ts.to_numpy(), arm, t, d, lvl, V.s, rsi=rsi, handover=cm.get("handover_state"))
        zr["volume_measure"] = vlabel
        k = V.pb.at(t, d)
        tl = TL.k_line(V, t, d, k) if k and k.get("open") else None
        confirm = M.confirming_evidence(zr, rsi, lvl, tl)
        last3 = range(max(0, t - 2), t + 1)
        sw, tr = LQ.sweeps_and_traps(V, t, start=arm)                    # method §7: the visit's own window
        sd = "buy" if d == M.DOWN else "sell"
        ev = {"level_star": int(lvl.get("sweeps") or 0) >= 1 or any(b in (lvl.get("births") or []) for b in ("b", "c", "d", "a:D"))
              or bool(lvl.get("confluence")), "fresh": lvl.get("fresh"),
              "trap_sweep": int(lvl.get("sweeps") or 0) >= 1 or bool([x for x in sw if x["side"] == sd] or [x for x in tr if x["side"] == sd]),
              "commit_strong": bool(cm.get("big_body") and cm.get("big_range")), "engulf": bool(cm.get("engulf")),
              "against_bodies": any((A["close"][i] - A["open"][i]) * d < 0 and M.candle_read(A, i, V.s, arm)["big_body"] for i in last3),
              "tl_confluence": "tl" in (lvl.get("births") or [])}
        el = M.evidence_list(ev, confirm, bool(read_ok), in_hours=V.entry_window(t))
        # Method §5 / 6a: A = the required set + ≥ 1 confirming piece, B = the required set only — both need the required set. An entry
        # model fired without it (E1 before any commitment, E2 before the LTF CHoCH, …) has no A / B label: the evidence list says ✗.
        label = M.method_label(confirm) if el["required"] == "present" else None
        chx = self.channel_evidence(t, d)
        if fired is not None and self.label_rule() != "legacy":
            tight = None
            if self.label_rule() in ("evidence_count", "model55"):         # DECISIONS 55 / 58: the two tightened pieces
                tight = {"pullback_channel": self.pullback_channel(t, d, arm),
                         "same_place": self.same_place(t, lvl, weekly=self.label_rule() == "model55")}
            return self._model_label(fired, trigger_tf, el, confirm, chx, lvl, cm, zr, rsi, tl, ev, tight)
        marks = [["required set (handover + commitment + volume + LTF CHoCH)", MARK[el["required"]]]] + \
            [[CONF_NAME.get(k2, k2), MARK.get(v, v)] for k2, v in el["confirming"].items()] + \
            [["counter channel broken in the trade direction (handover evidence; context)", "✓" if chx["present"] else "✗"]]
        return {"label": label, "evidence_list": el, "evidence": marks, "confirming": confirm, "commit": cm, "zone_read": zr,
                "rsi": rsi, "trendline": tl, "context": ev, "channel_evidence": chx}

    def _model_label(self, fired, trigger_tf, el, confirm, chx, lvl, cm, zr, rsi, tl, ev, tight=None):
        """DECISIONS 54 / 55 (label_rule = model / model54): the evidence list + A / B for a fired entry — see evidence(). `tight` (55) =
        {"pullback_channel": Reader.pullback_channel, "same_place": Reader.same_place} replaces the confluence and counter-channel
        pieces; None = the DECISIONS 54 reading (model54, what-if)."""
        conds = self.model_conditions(fired, trigger_tf)
        c5 = dict(confirm)
        if tight is not None:
            sp, pc = tight["same_place"], tight["pullback_channel"]
            c5["confluence"] = sp["present"]
            c5["counter_channel_broken"] = pc["present"]
        else:
            if str(lvl.get("tf")) == "line":                               # E4 (b) at a broken line: the line IS the object, never its
                c5["confluence"] = True if lvl.get("confluence") else None   # own confluence; what lies on it is not read here ⇒ NA
            c5["counter_channel_broken"] = bool(chx.get("present"))
        c5 = {k2: c5.get(k2) for k2 in LABEL_PIECES}
        count = self.label_rule() == "evidence_count"                     # DECISIONS 58: no A / B label, the count instead
        label = None if count else M.method_label(c5)

        def w(v):
            return "NA" if v is None else ("present" if v else "absent")
        el2 = {"required": "present", "required_set": f"the {fired.get('model')} model's own conditions", "label_rule": self.label_rule(),
               "model_conditions": {c: "present" for c in conds}, "entry_hours": el.get("entry_hours"),
               "confirming": {k2: w(v) for k2, v in c5.items()}, "context": el.get("context"),
               "legacy_required": el.get("required"),
               "label_pieces": [CONF_NAME[k2] for k2, v in c5.items() if v is True]}
        if count:
            el2.pop("label_pieces")
            el2.update(evidence_count=sum(1 for v in c5.values() if v is True), evidence_of=len(LABEL_PIECES),
                       evidence_present=[CONF_NAME[k2] for k2, v in c5.items() if v is True],
                       evidence_na=[CONF_NAME[k2] for k2, v in c5.items() if v is None])
        if tight is not None:
            el2["confluence_at"] = tight["same_place"]["objects"]
            el2["pullback_channel"] = tight["pullback_channel"]
        mdl = str(fired.get("model")) + (f" ({fired.get('variant')})" if fired.get("model") == "E4" else "")
        marks = ([[f"{mdl} — the model's own conditions (" + ("all held" if count else "required set") + ")", "✓"]] +       # compact first: the card's line is cut
                 [[CONF_NAME[k2], MARK[el2["confirming"][k2]]] for k2 in LABEL_PIECES] +   # by length; each condition by name after
                 [[f"{mdl} condition: {c}", "✓"] for c in conds])
        return {"label": label, "evidence_list": el2, "evidence": marks, "confirming": c5, "commit": cm, "zone_read": zr,
                "rsi": rsi, "trendline": tl, "context": ev, "channel_evidence": chx}

    def pullback_origin(self, t, d, arm):
        """The trend-degree (1H) swing the pullback / correction into the area started from: the newest swing of the trend's side (a
        swing LOW for a bear call — the correction rose from it; a swing HIGH for a bull put) at or before the visit's first bar `arm`,
        known by bar t. None ⇒ not readable."""
        kind = "L" if d < 0 else "H"
        ps = [p for p in TL._known_deg(self.V, t, int(self.V.s.get("level_degree", 2))) if p.kind == kind and int(p.bar) <= int(arm)]
        return max(ps, key=lambda p: int(p.bar)) if ps else None

    def pullback_channel(self, t, d, arm):
        """DECISIONS 55: "counter channel broken" = only the PULLBACK's (correction's) own channel at the trend degree (1H): a channel
        running against the trade (rising for a bear call, falling for a bull put) whose base line is drawn on the correction's own
        swings (both anchors from the pullback's origin on — `pullback_origin`) and whose line broke in the trade direction (K6.5,
        a close beyond + a swing beyond). Comparison only. ⇒ {present (True / False / None = origin not readable), origin, channels}."""
        org = self.pullback_origin(t, d, arm)
        if org is None:
            return {"present": None, "origin": None, "channels": [], "degree": "1H"}
        want, against = ("down", "rising") if d < 0 else ("up", "falling")
        g = int(self.V.s.get("level_degree", 2))
        own = [c for c in TL.channels(self.V, t, g) if c["slope_dir"] == against and int(c["base_line"]["p1"][0]) >= int(org.bar)]
        hits = [{"channel": c["id"], "tf": c["tf"], "state": c["state"], "broken_lines": c["broken_lines"]} for c in own
                if c["broken_side"] == want]
        return {"present": bool(hits), "origin": {"bar": int(org.bar), "ts": self.T(org.bar), "price": round(float(org.price), 2)},
                "channels": hits, "pullback_channels": [c["id"] for c in own], "degree": TL.TF_OF_DEGREE.get(g, f"D{g}")}

    def same_place(self, t, lvl, weekly=False):
        """DECISIONS 55: "confluence" = only (a) a Daily / Weekly area OVERLAPPING the traded area (another alive area of a higher
        timeframe than the traded one — method §1 — bands overlap),
        or (b) an object of a different kind AT the same place — a line whose value at bar t lies inside the area's band (the trade-side
        line through the area; an unbroken trend-degree line), or a liquidity pool (an equal highs / lows pool, method §3 "equal" — a
        plain swing inside the band is the area's own reaction) whose price lies inside it. A broken-line object (E4 b): an alive area
        whose band holds the line's value. Overlap by comparison only — nearness (a reaction turning at a line outside the band) never
        counts. DECISIONS 58 (`weekly = False`, default): a Weekly area never counts (Weekly stays context) — a 1H traded area counts an
        overlapping Daily area; a Daily traded area counts no other area (another Daily = the same timeframe, never merged — Z-1u; only
        a line / pool there); a broken-line object counts a 1H / Daily area holding it. `weekly = True` = the DECISIONS 55 reading.
        ⇒ {present, objects: [words]}."""
        V = self.V
        lo, hi = float(lvl["lo"]), float(lvl["hi"])
        own = lvl.get("parent_level", lvl.get("id"))
        objs = []
        snap = V.levels.snapshot(t) or []
        if str(lvl.get("tf")) == "line":                                   # the object is a line: an area (different kind) holding it
            for x in snap:
                if (weekly or x.get("tf") != "W") and float(x["lo"]) <= lo <= float(x["hi"]):
                    objs.append(f"{x.get('tf')} area {x.get('id')} {float(x['lo']):,.2f}–{float(x['hi']):,.2f}")
            return {"present": bool(objs), "objects": objs}
        rank = {"15M": 0, "1H": 1, "D": 2, "W": 3}                        # method §1: a HIGHER-timeframe area at the same place
        r0 = rank.get(str(lvl.get("tf")), 1)                               # (a Daily traded area: a Weekly one; never same-TF areas)
        for x in snap:
            if (x.get("id") == own or x.get("tf") not in (("D", "W") if weekly else ("D",)) or rank.get(str(x.get("tf")), 0) <= r0
                    or float(x["hi"]) < lo or float(x["lo"]) > hi):
                continue
            objs.append(f"{x.get('tf')} area {x.get('id')} {float(x['lo']):,.2f}–{float(x['hi']):,.2f}")
        ln = lvl.get("tl")
        if isinstance(ln, dict) and ln.get("value_t") is not None and lo <= float(ln["value_t"]) <= hi:
            objs.append(f"line {ln.get('id', '')} {float(ln['value_t']):,.2f}".replace("  ", " "))
        g = int(V.s.get("level_degree", 2))
        for c in TL.channel_lines(V, t, g):
            if not c.get("broken") and lo <= float(TL.line_value(c, t)) <= hi:
                objs.append(f"{c['tf']} {c['family']} {float(TL.line_value(c, t)):,.2f}")
        for p in LQ.pools(V, t):
            if p.get("src") == "equal" and lo <= float(p["price"]) <= hi:
                objs.append(f"liquidity pool (equal {'highs' if p['side'] == 'buy' else 'lows'}) {float(p['price']):,.2f}")
        return {"present": bool(objs), "objects": list(dict.fromkeys(objs))}

    def channel_evidence(self, t, d):
        """Abhi 21 Oct: a channel running AGAINST the trade (rising for a bear call, falling for a bull put) whose line broke in the trade
        direction (K6.5) = handover evidence — listed with the channel / line ids; never a gate. DECISIONS 54 (`label_rule = model`): one of
        the five confirming pieces of the A / B label ("counter channel broken"); `legacy`: context only, not in the label."""
        V = self.V
        want, against = ("down", "rising") if d < 0 else ("up", "falling")
        hits = []
        for g in TL.line_degrees(V):
            for c in TL.channels(V, t, g):
                if c["slope_dir"] == against and c["broken_side"] == want:
                    hits.append({"channel": c["id"], "tf": c["tf"], "state": c["state"], "broken_lines": c["broken_lines"]})
        return {"present": bool(hits), "channels": hits}


def read(V, t, trend, act, side_fn=None, keep=None, extra=None, prefix="", broken_on=True):
    """Abhi 21 Oct — the entry models at decision bar t for the step2 watch-list `act` (trade side, alive, not BROKEN). Returns
    {entries, armed, waiting (text), best (row area dict), best_eval (6a facts for the row)}.
    Model C (decision3/model_c.py) only: side_fn = its injected trade side, keep / extra = its E4 (b) objects, prefix = its cluster ids
    ("MC…", never clashing with the Daily side's "C…"), broken_on = False reads the areas only. The defaults = today's path."""
    R = Reader(V) if side_fn is None else Reader(V, side_fn)          # the default call exactly as before (model C only injects)
    A = R.A
    edges_fn = getattr(R, "range_edge_areas", None)                    # (a stub reader in tests may not have it)
    if edges_fn is not None and side_fn is None and keep is None and extra is None:   # DECISIONS 40 (concept L): range edges = areas
        act = list(act) + edges_fn(t, trend, act)
    armed, entries, cands = [], [], []
    first_area = None
    for lvl in act:
        d = M._dir(trend, lvl["role"])
        if d == 0:
            continue
        cands.append((lvl, d))
        a, fired = R.area(t, lvl, d)
        if a is None:
            continue
        armed.append(a)
        first_area = first_area or (lvl, d, a)
        for f in fired:
            entries.append((f, lvl, d, a))
    if str(V.s.get("entry_cluster_rule", "cluster")) == "cluster":         # one location = one overlapping cluster (lead, provisional)
        entries = clusters(armed, entries, cands, prefix=prefix + "C")
    if trend in ("UP", "DOWN") and broken_on:
        d = M._dir(trend)
        b_armed, b_fired = R.broken(t, d) if keep is None and extra is None else R.broken(t, d, keep, extra)
        armed.extend(b_armed)
        b_entries = [(f, None, d, f["obj"]) for f in b_fired]
        if str(V.s.get("entry_cluster_rule", "cluster")) == "cluster":     # Z-1u for E4 (b) too: overlapping broken areas = one place
            b_entries = clusters(b_armed, b_entries, obj=("broken_area", "broken_line"), prefix=prefix + "CB")
        entries.extend(b_entries)
    out = []
    for f, lvl, d, a in entries:
        if f["model"] != "E4" or f["variant"] == "a":
            vi = V.visit(t, lvl, d)
            cm6 = V._confirm(t, d, lvl, {})
            ok6, why6, cm = cm6
            ev = R.evidence(t, d, lvl, int(vi["start"]), cm=cm, read_ok=ok6, move_from=cm.get("move_from_bar"), fired=f)
            area = {k: lvl.get(k) for k in ("id", "tf", "role", "lo", "hi", "state", "births", "confluence_label")}
            area["uid"] = a.get("area_uid")
            if lvl.get("range_edge"):                                      # DECISIONS 40: a range edge (card / audit wording)
                area["range_edge"] = lvl["range_edge"]
            arm0, mf0 = int(vi["start"]), cm.get("move_from_bar")
        elif f["kind"] == "area":
            x = f["raw"]
            lvl2 = {**x, "visit_from": f["start"]}
            cm6 = V._confirm(t, d, lvl2, {})
            if getattr(V, "visit_end_new", False):                         # DECISIONS 64: the last swing built away known at t (the
                cm6[2]["move_from_bar"] = V.move_from(t, float(x["lo"]), float(x["hi"]), d)   # break's own swing beyond or later)
            ev = R.evidence(t, d, lvl2, f["start"], cm=cm6[2], read_ok=cm6[0], move_from=cm6[2].get("move_from_bar"), fired=f)
            area = {k: x.get(k) for k in ("id", "tf", "role", "lo", "hi", "state", "births", "confluence_label")}
            area["uid"] = a.get("area_uid")
            lvl = lvl2
            arm0, mf0 = int(f["start"]), cm6[2].get("move_from_bar")
        else:
            ln = f["raw"]
            v = round(TL.line_value(ln, t), 2)
            lvl = {"id": f"line:{ln['id']}", "lo": v, "hi": v, "tf": "line", "role": a["role"], "births": ["tl"], "sweeps": 0,
                   "fresh": None, "confluence_line": True, "confluence": []}
            mf0 = R.line_move_from(t, ln, d, f["start"])                    # DECISIONS 56 (L5-c): the move into the line's retest
            ev = R.evidence(t, d, lvl, f["start"], move_from=mf0, fired=f)
            area = {"id": lvl["id"], "tf": "line", "role": a["role"], "lo": v, "hi": v, "state": "BROKEN", "line": a.get("line")}
            arm0 = int(f["start"])
        # T9 (PA evidence wiring, CLAUDE.md "evidence is listed and never blocks"): every PA track's facts for this entry — read after
        # the decision, never fed back into it (the entry's fields above are unchanged; tests/test_pa_evidence.py pins it).
        pa_ev = PE.for_entry(V, t, d, {**area, "object": a["object"]}, lvl=lvl, arm=arm0, move_from=mf0)
        m = f["model"]
        name = NAME[m] + (f" ({f['variant']})" if m == "E4" else "")
        cl = f.get("cluster")
        vid, vstart = (cl["visit_id"], cl["visit_start"]) if cl else (a["visit_id"], a["visit_start"])
        out.append({"model": m, "name": name, "direction": int(d), "side": side_of(d), "object": a["object"],
                    "area": {**area, "object": a["object"]}, "visit_id": vid, "visit_start": vstart, "cluster": cl,
                    "area_visit_id": a["visit_id"], "area_visit_start": a["visit_start"], "refined_base": f.get("refined"),
                    "key": f"{vid.split('@')[0]}|{vstart}|{m}", "trigger_bar": int(t), "trigger_ts": R.T(t),
                    "trigger_bar_end": str(V.bar_end[t]), "entry_ref": round(float(A["close"][t]), 2),
                    "invalidation": f["invalidation"], "invalidation_rule": f["invalidation_rule"], "facts": f.get("facts") or {},
                    "label": ev["label"], "evidence": ev["evidence"], "evidence_list": ev["evidence_list"],
                    "channel_evidence": ev["channel_evidence"], "pa_evidence": pa_ev,
                    "confirming": ev["confirming"], "_eval": ev, "_lvl": lvl})
    return {"entries": out, "armed": armed, "first_area": first_area, "reader": R}


def _uid_key(a):
    """A5: an armed object's stable place id (its `area_uid`; a line / range edge ⇒ its own id) — for ordering and cluster ids."""
    return str(a.get("area_uid") or a.get("area_id"))


def clusters(armed, entries, cands=(), obj="area", prefix="C"):
    """Lead's provisional rule (Abhi may override; `entry_cluster_rule = cluster`): areas of the same role on the same side whose bands
    overlap, visited together (all armed at this bar), are ONE place — at most one signal per model per overlapping cluster per visit.

    Abhi 21 Oct (Z-1u, areas are never merged): the cluster is used ONLY to COUNT "one signal per model per place". The area's edges, the
    trigger check (inside the area) and the invalidation always come from the ACTUAL area price is visiting (the specific base whose
    model fired) — never from the union of the cluster's bands, never from another member's visit. The cluster carries no band.

    Cluster = the connected overlapping bands of one (role, direction) among the armed (visited, not disarmed) areas and the other valid
    trade-side areas of the watch-list (`cands` = [(lvl, d)] — not visited yet, they still belong to the place); its anchor = the visited
    member whose visit began first (the cluster's visit, so a later-joining area never opens a new one: visit_id = the anchor's — the
    counting key). A model already fired on any member earlier in this visit ⇒ a new firing on another member is consumed, not a signal;
    several members firing the same model at this bar ⇒ one signal (the anchor's if it fired, else the earliest visit). The signal keeps
    its own area, its own trigger and its own invalidation; the cluster lists its member areas (ids + their own bands) for the card. A
    single area = a cluster of one (unchanged). Returns the kept (f, lvl, d, a) list; member statuses are annotated.

    `obj = ("broken_area", "broken_line")` (prefix "CB"): the same count for E4 (b) — BROKEN areas and BROKEN lines of the same role and
    break direction revisited together whose bands overlap (a line = its value at this bar) are one place ⇒ one E4 (b) per place per
    visit (Abhi: one signal per model per place). Each signal keeps its own object, retest extreme and invalidation."""
    objs = (obj,) if isinstance(obj, str) else tuple(obj)
    pool = [a for a in armed if a.get("object") in objs and not a.get("disarmed")]
    seen = {(str(a.get("area_id")), int(a["direction"])) for a in armed if a.get("object") in objs}
    for lvl, d in cands:                                                   # watch-list areas not visited now: part of the place
        lid = lvl.get("parent_level", lvl.get("id"))
        if (str(lid), int(d)) in seen:
            continue
        seen.add((str(lid), int(d)))
        pool.append({"object": "area", "area_id": lid, "area_uid": lvl.get("uid"), "tf": lvl.get("tf"), "role": lvl.get("role"),
                     "lo": lvl["lo"], "hi": lvl["hi"],
                     "state": lvl.get("state"), "direction": int(d), "visit_start_bar": None, "visit_id": None, "_unvisited": True})
    groups = []
    for a in sorted(pool, key=lambda x: (str(x.get("role")), int(x["direction"]), float(x["lo"]))):
        g = groups[-1] if groups else None
        if g and g["role"] == a.get("role") and g["d"] == int(a["direction"]) and float(a["lo"]) <= g["reach"]:
            g["m"].append(a)
            g["reach"] = max(g["reach"], float(a["hi"]))                   # overlap test only (membership), never an edge
        else:
            groups.append({"role": a.get("role"), "d": int(a["direction"]), "reach": float(a["hi"]), "m": [a]})
    of = {}
    for g in groups:
        mem = g["m"]
        vis = [x for x in mem if not x.get("_unvisited")]
        if not vis:
            continue
        anchor = min(vis, key=lambda x: (int(x["visit_start_bar"]), _uid_key(x)))   # A5: ties by the stable place id (never a list index)
        info = {"id": f"{prefix}{_uid_key(anchor)}", "anchor": anchor["area_id"], "anchor_uid": anchor.get("area_uid"),
                "visit_id": anchor["visit_id"], "visit_start": anchor["visit_start"], "n": len(mem),
                "members": [{**{k: x.get(k) for k in ("area_id", "area_uid", "tf", "role", "lo", "hi", "state", "visit_id")},
                             "visited": not x.get("_unvisited")} for x in mem],
                "use": "count only: one signal per model per place (edges, trigger and invalidation = the visited area, Z-1u)"}
        for x in vis:
            x["cluster"] = {k: info[k] for k in ("id", "anchor", "visit_id", "n")}
            of[id(x)] = (info, vis, anchor)
    keep, chosen = {}, {}
    order = sorted(range(len(entries)), key=lambda i: (0 if of.get(id(entries[i][3])) and entries[i][3] is of[id(entries[i][3])][2]
                                                       else 1, int(entries[i][3].get("visit_start_bar") or 0),
                                                       _uid_key(entries[i][3])))
    for i in order:
        f, lvl, d, a = entries[i]
        g = of.get(id(a))
        if g is None:
            keep[i] = (f, lvl, d, a)
            continue
        info, mem, _anchor = g
        m = f["model"]
        earlier = [x for x in mem if (x.get("models") or {}).get(m, {}).get("status") == "fired_earlier"]
        why = None
        if earlier:
            why = (f"{m} already fired in this cluster's visit on area {earlier[0]['area_id']} at "
                   f"{earlier[0]['models'][m].get('at')} — one place, one signal per model")
        elif (info["id"], m) in chosen:
            why = f"{m} fired on overlapping area {chosen[(info['id'], m)]} at this bar — one place, one signal per model"
        if why:
            a["models"][m] = {**a["models"][m], "status": "cluster_consumed", "note": why}
            continue
        chosen[(info["id"], m)] = a["area_id"]
        f = dict(f)                                                        # its own area, trigger and invalidation — unchanged
        f["cluster"] = info
        keep[i] = (f, lvl, d, a)
    return [keep[i] for i in range(len(entries)) if i in keep]               # the readers' own order


def waiting_text(armed, limit=3):
    """The wait reason: what each armed model is waiting for (nearest armed areas first)."""
    if not armed:
        return "no armed area: price is not visiting a valid trade-side area"
    parts = []
    for a in armed[:limit]:
        if a.get("disarmed"):
            parts.append(f"{a['object']} {a['area_id']} {a['lo']:,.0f}–{a['hi']:,.0f}: disarmed — {a['disarmed']}")
            continue
        ms = []
        for m, st in (a.get("models") or {}).items():
            s = st.get("status")
            if s in ("waiting", "passed"):
                ms.append(f"{m} {s}: {str(st.get('waiting'))[:90]}")
            elif s in ("fired_earlier", "fired_outside_hours", "blocked_data_problem"):
                ms.append(f"{m} {s.replace('_', ' ')} {str(st.get('at'))[11:16]}")
            elif s == "cluster_consumed":
                ms.append(f"{m} consumed (overlapping cluster {(a.get('cluster') or {}).get('id')})")
            elif s == "off":
                ms.append(f"{m} off")
        parts.append(f"{a['object']} {a['area_id']} {a['lo']:,.0f}–{a['hi']:,.0f} (visit {str(a['visit_start'])[:16]}): " + " · ".join(ms))
    more = f" · +{len(armed) - limit} more armed" if len(armed) > limit else ""
    return " | ".join(parts) + more
