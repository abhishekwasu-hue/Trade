"""decision3/entry_models5.py — Abhi (DECISIONS 37, owner rule): the entry trigger on 5M for every model (`trigger_tf = 5M`).

WHERE stays as it is (15M / 1H / Daily, read only from bars CLOSED at the 5M close — k(j), decision3/trigger_frame.py): the W state, the D
side (step1 at k), the 1H / Daily areas with their K4 lifecycle (step2 at k), the refined 15M base (RC2, `Reader.refined(k)`), the visit
(`V22.visit(k)` — it ends only by 15M structure), once per model per visit, the clusters (Z-1u) and `max_hits_per_zone` (same
visit_id = area @ the 15M bar that contains the visit's first 5M candle). WHEN moves to 5M — the trigger candle is a 5M candle:

  E1  the first 5M candle of the visit that trades into the refined base known at k(u); it closing beyond the base's far edge ⇒ no E1
      this visit (DECISIONS 23); invalidation = the base's far edge;
  E2  `method.commitment` on the 5M candles (dominant over every other 5M candle of the visit; FUT 5M volume above the average of the
      approach leg's + the visit's opposite-side 5M candles); handover / sharp reversal / absorption read on the visit's 5M candles
      (`trigger_frame.handover5` = method.handover_episode); the FUT data problem counted on 5M bars; invalidation unchanged;
  E3  the 5M CHoCH (`method.ltf_choch`, t_end = the 5M close): the trigger is the 5M candle whose close makes the CHoCH, and it must
      trade into the refined base (Q6 — not relaxed: a CHoCH candle outside the base gives no E3 for that CHoCH);
  E4a a 5M sweep (beyond the far edge / the visit's extreme, closing back inside; a K4 sweep event of the area at its 15M close still
      counts) and the next push = the first confirmed 5M swing (the LTF swing definition of `ltf_choch`) failing inside the sweep extreme;
  E4b the objects known at k (broken areas / lines, `break_known_at`, `broken_back_at`, DEAD); touch + `reversal_form` on 5M candles; a
      line's value at a 5M candle at its float position; approach side (DECISIONS 38) on 5M; the revisit ends by a 15M away swing.

traded_inside / h2_block / beyond are read on the 5M trigger candle (the SAME candle-level code as entry_models.Reader, given the 5M
arrays); the invalidation stays structural (refined base / area / object / sweep extreme) — never the 5M candle's own extreme. A visit may
start on a 5M candle inside the 15M bar in progress (Q1 / Q2). The entry hours are read on the 5M bar start. Every 5M candle u of the
visit is judged with the state known at k(u) (stateless once per visit: the scan of the visit's 5M candles). The 15M Reader and
V22.decide are untouched (`trigger_tf = 15M` = the earlier behaviour, byte-identical). No order, no broker, no AI call."""
import numpy as np
import pandas as pd

from . import entry_models as EM
from . import flip as FL
from . import method as M
from . import pa_evidence as PE
from . import trendline as TL
from . import trigger_frame as TF

MODELS = EM.MODELS
NO_5M = ("no 5M candles for this visit's first 15M bar (outside the 5M history window, engine3_ltf_days) — the 5M models wait "
         "(Q16, data reason)")


class _Candles(EM.Reader):
    """The candle-level helpers of entry_models.Reader (h2_block, outside, off_base, beyond, base_broken, touches, P, retest_ok,
    approach_side) on the 5M arrays — the same code, the 5M candle."""

    def __init__(self, V, F):                                              # noqa: D401 — never calls Reader.__init__ (no memo needed)
        self.V, self.A, self.ts, self.memo, self.side_fn = V, F.A, F.ts, {}, None
        self.on = tuple(MODELS)


class Reader5(EM.Reader):
    """The entry models at the 5M decision candle j. Structure (areas, K4, refined base, visit, side, E4 b objects) from the 15M state
    at k(u) — the inherited Reader methods on the 15M arrays; the trigger candle and the in-visit reads on the 5M arrays."""

    def __init__(self, V, j, side_fn=None):
        super().__init__(V, side_fn)
        self.memo = V.__dict__.setdefault("_em5_memo", {})                # never the 15M memo (5M keys are prefixed "5:")
        self.hmemo = V.__dict__.setdefault("_ho5_memo", {})
        self.F = TF.of(V)
        self.A5 = self.F.A
        self.c5 = _Candles(V, self.F)
        self.j = int(j)
        self.k = int(self.F.k_of[self.j]) if self.F.n else -1

    # ------------------------------------------------------------------------------------------ 5M facts (indices = 5M candles)
    def T5(self, i):
        return self.F.T(i)

    def P(self, i, d):                                                     # the 5M push extreme (used by the inherited invalidation)
        return float(self.A5["high"][i]) if d < 0 else -float(self.A5["low"][i])

    def entry_window5(self, j):
        """Operational schedule (P1 / P2) on the 5M bar start: `entry_open(s)` … `entry_end` (end exclusive)."""
        if bool(self.V.s.get("session_windows", False)):
            return True
        hm = pd.Timestamp(self.F.ts[int(j)]).strftime("%H:%M")
        return M.entry_open(self.V.s) <= hm < self.V.s["entry_end"]

    def _born(self, lvl):
        """The bar a visit of this area may start from (as V22.visit reads it): the level's birth, or `visit_from` for a revisit."""
        lid = lvl.get("parent_level", lvl.get("id"))
        L = self.V.levels.L
        born = L[lid].born_bar if isinstance(lid, (int, np.integer)) and 0 <= int(lid) < len(L) else 0
        if lvl.get("visit_from") is not None:
            born = max(int(born), int(lvl["visit_from"]))
        return int(born)

    def visit5(self, u, lvl, d):
        """The visit in progress at the 5M candle u, read with the 15M structure closed at k(u) (V22.visit(k(u))) plus the 5M candles of the
        15M bar in progress (Q1 / Q2): {start5 (the first 5M candle of the visit trading into the area), s15 (the 15M bar that contains
        it — k(u) + 1 while that bar is in progress), vid (its 15M bin start: the visit id), approach_from15, why, data}. start5 None ⇒ no
        visit (why) or no 5M candles for it (data)."""
        lid = lvl.get("parent_level", lvl.get("id"))
        key = ("5:visit", str(lid), float(lvl["lo"]), float(lvl["hi"]), int(d), lvl.get("visit_from"), int(u))
        if key in self.memo:
            return self.memo[key]
        F, c5 = self.F, self.c5
        ku = int(F.k_of[int(u)])
        out = {"start5": None, "s15": None, "vid": None, "approach_from15": None, "move_from15": None, "why": "no closed 15M bar yet",
               "data": None}
        if ku >= 0:
            vi = self.V.visit(ku, lvl, d)
            if vi["start"] is not None:
                s15 = int(vi["start"])
                ch = F.children(s15, upto=u)
                if not ch:
                    out.update(s15=s15, why=None, data=NO_5M, vid=self.T(s15))
                else:
                    tch = [i for i in ch if c5.touches(i, lvl)]
                    st = tch[0] if tch else ch[0]
                    out.update(start5=int(st), s15=s15, vid=self.T(s15), approach_from15=vi.get("approach_from"), why=None,
                               move_from15=vi.get("move_from") if "move_from" in vi else
                               ((int(vi["approach_from"]) - 1) if vi.get("approach_from") is not None else None))
            else:
                out["why"] = vi.get("why") or "no visit in progress"
                if self._born(lvl) <= ku:                                  # a new visit may start inside the 15M bar in progress
                    tch = [i for i in F.children(ku + 1, upto=u) if c5.touches(i, lvl)]
                    if tch:
                        lo, hi = float(lvl["lo"]), float(lvl["hi"])
                        sw = self.V._away_swings(ku, lo, hi, d)
                        if getattr(self.V, "visit_end_new", False) and lvl.get("visit_from") is not None and \
                                lvl.get("broken_at") is not None:          # a broken object's revisit: away swings from the break
                            sw = [b for b in sw if b >= int(lvl["broken_at"])]
                        out.update(start5=int(tch[0]), s15=ku + 1, vid=F.bin_T(tch[0]), why=None,
                                   approach_from15=(sw[-1] + 1) if sw else None, move_from15=sw[-1] if sw else None)
        self.memo[key] = out
        return out

    def appr5(self, v):
        """The approach leg on 5M: the 5M candles from the first one of the 15M bar after the approach's swing up to the visit."""
        af = v.get("approach_from15")
        if af is None or v.get("start5") is None:
            return None
        a5 = self.F.first_at_or_after(self.V._ts[int(af)]) if int(af) < len(self.V._ts) else int(v["start5"])
        return range(min(int(a5), int(v["start5"])), int(v["start5"]))

    def ho5(self, u, lvl, d, start):
        """The handover episode on the visit's 5M candles start … u (method.handover_episode, resumable)."""
        lid = lvl.get("parent_level", lvl.get("id"))
        Ls = self.V.levels.L
        L = Ls[lid] if isinstance(lid, (int, np.integer)) and 0 <= int(lid) < len(Ls) else None
        F = self.F
        broken = None if L is None else (lambda e: int(F.k_of[int(e)]) >= 0 and L.state_at(int(F.k_of[int(e)])) in (FL.BROKEN, FL.DEAD))
        sharp = None
        lo, hi = float(lvl["lo"]), float(lvl["hi"])
        if bool(self.V.s.get("sharp_reversal_handover", True)):
            sharp = lambda i, a0: M.sharp_reversal(self.A5, i, d, lo, hi, self.V.s, a0=a0)  # noqa: E731
        key = (str(lid), lo, hi, int(d), int(start))
        return TF.handover5(self.A5, start, u, d, self.V.s, broken=broken, sharp=sharp, memo=self.hmemo, key=key)

    def c0(self, u, lvl, d, start, appr):
        """c0 on the 5M candle u (method.commitment on the 5M arrays: dominance in the visit, FUT 5M volume vs the approach leg + the
        visit's opposite side; the rejected push excluded) + the FUT-volume data-problem rule on 5M bars."""
        V = self.V
        key = ("5:c0", str(lvl.get("parent_level", lvl.get("id"))), int(u), int(d), float(lvl["lo"]), float(lvl["hi"]), int(start))
        if key in self.memo:
            return self.memo[key]
        ho = self.ho5(u, lvl, d, start)
        push = [int(ho["seen_at"]) - 1] if ho.get("form") == "sharp_reversal" and ho.get("seen_at") is not None else []
        ok, why, cm = M.commitment(self.A5, u, d, lvl, V.s, self.F.ts, win=start, approach=appr, exclude=push)
        if ok and cm.get("vol_na") and bool(V.s.get("c0_volume_required", True)):
            ok, why = False, "data problem: " + (self.F.vol_na_reason(u) or "FUT volume missing")
        gaps = self.F.vol_gaps(start, u, V.s.get("vol_gap_max_frac", 0.5))
        if ok and gaps and gaps["over"]:
            ok, why = False, f"data problem: FUT 5M volume gaps {gaps['n']}/{gaps['m']} 5M bars in the visit (> {gaps['limit']:.0%})"
        self.memo[key] = (bool(ok), why, cm)
        return self.memo[key]

    def absorbing(self, u, lvl, d, start):
        """E2 / E3 gate (Abhi 21 Oct, 13 Oct principle) on the visit's 5M candles: absorption without a handover at the 5M candle u."""
        key = ("5:absorb", str(lvl.get("parent_level", lvl.get("id"))), int(u), int(d), float(lvl["lo"]), float(lvl["hi"]), int(start))
        if key in self.memo:
            return self.memo[key]
        ho = self.ho5(u, lvl, d, start)
        out = None
        a0 = int(ho.get("window_start", start))
        if not ho.get("present") and u - 1 >= a0:
            zs = M.zone_study(self.A5, a0, u - 1, d, self.V.s)
            if zs.get("absorption"):
                out = "absorption without a handover (zone study on 5M: " + (zs.get("line") or "the opposite side still absorbing") + ")"
        self.memo[key] = out
        return out

    def c1(self, u, lvl, d, start):
        """The 5M CHoCH by close (method.ltf_choch) from the visit's first 5M candle, 5M bars ≤ the 5M candle u's close."""
        V = self.V
        key = ("5:c1", float(lvl["lo"]), float(lvl["hi"]), int(u), int(d), int(start))
        if key in self.memo:
            return self.memo[key]
        if V.ltf is None:
            out = {"done": False, "code": M.C_LTF_MISSING, "line": "LTF: LTF data missing"}
        else:
            ta = pd.Timestamp(self.F.ts[int(start)])
            out = M.ltf_choch(V.ltf, d, ta, ta, pd.Timestamp(self.F.end[int(u)]), lvl=lvl)
        self.memo[key] = out
        return out

    def choch_candle(self, ch, u):
        """Q6: the E3 trigger is the 5M candle whose close makes the CHoCH."""
        return bool(ch.get("done")) and ch.get("at") is not None and pd.Timestamp(ch["at"]) == pd.Timestamp(self.F.end[int(u)])

    def ltf_pivots(self, kind):
        """The LTF swing definition (method.ltf_choch): a 5M swing high at i — high above the previous candle's and not below the next's
        (confirmed at i + 1); a swing low mirrored. ⇒ sorted bars."""
        key = ("5:piv", kind)
        if key not in self.memo:
            H, Lo = self.A5["high"], self.A5["low"]
            n = len(H)
            if kind == "H":
                ok = [i for i in range(1, n - 1) if H[i] > H[i - 1] and H[i] >= H[i + 1]]
            else:
                ok = [i for i in range(1, n - 1) if Lo[i] < Lo[i - 1] and Lo[i] <= Lo[i + 1]]
            self.memo[key] = ok
        return self.memo[key]

    def sweep(self, u, lvl, d, start):
        """E4 (a) on 5M at the candle u: a sweep candle s (start ≤ s < u) — its push beyond the area's far edge or the visit's extreme so far,
        closing back not beyond the far edge, or the last 5M candle of a 15M bar with a K4 "sweep" event of the area — then no candle beyond
        the sweep extreme, and the next push (the first confirmed 5M swing on the push side after s, confirmed by u) failed inside it."""
        if u <= start:
            return None
        F = self.F
        Fe = self.P_far(lvl, d)
        lid = lvl.get("parent_level", lvl.get("id"))
        Ls = self.V.levels.L
        L = Ls[lid] if isinstance(lid, (int, np.integer)) and 0 <= int(lid) < len(Ls) else None
        k4 = set()
        for b, k, _ in (L.events if L is not None else []):
            if k == "sweep" and 0 <= int(b) < len(self.V.bar_end):
                c = F.last_child_closing(self.V.bar_end[int(b)])
                if c is not None and start <= c < u:
                    k4.add(int(c))
        kind = "H" if d < 0 else "L"
        sw = [i for i in self.ltf_pivots(kind) if start < i and i + 1 <= u]
        if not sw:
            return None
        ix = np.arange(start, u + 1)
        Pv = F.A["high"][ix] if d < 0 else -F.A["low"][ix]
        Cv = F.A["close"][ix] if d < 0 else -F.A["close"][ix]
        pm = np.maximum.accumulate(Pv)
        sm = np.maximum.accumulate(Pv[::-1])[::-1]
        for jj in range(len(ix) - 2, -1, -1):
            s = int(ix[jj])
            x_s = max(Fe, float(pm[jj - 1])) if jj > 0 else Fe
            if not ((Pv[jj] > x_s and Cv[jj] <= Fe) or s in k4):
                continue
            E = float(pm[jj])
            if float(sm[jj + 1]) > E:
                continue
            nxt = next((i for i in sw if i > s), None)
            if nxt is None:
                continue
            px = float(F.A["high"][nxt]) if d < 0 else float(F.A["low"][nxt])
            return {"sweep_bar": s, "sweep_ts": self.T5(s), "sweep_extreme": round(self.back(E, d), 2), "tf": "5M",
                    "swept": "K4 sweep (closed back before a swing formed beyond)" if s in k4 and not Pv[jj] > x_s else
                    ("the area's far edge" if x_s == Fe else "the visit's extreme"),
                    "push_bar": int(nxt), "push_ts": self.T5(nxt), "push_price": round(px, 2), "push_known_bar": int(nxt) + 1}
        return None

    def data_problem(self, start, t):
        g = self.F.vol_gaps(start, t, self.V.s.get("vol_gap_max_frac", 0.5))
        if g and g["over"]:
            return (f"data problem: FUT 5M volume missing on all {g['m']} 5M visit bars" if g["n"] == g["m"] else
                    f"data problem: FUT 5M volume gaps {g['n']}/{g['m']} 5M bars in the visit (> {g['limit']:.0%}, vol_gap_max_frac)")
        return None

    def rejection5(self, u, d, touch_fn, start, away_fn):
        if not (touch_fn(u) or (u - 1 >= start and touch_fn(u - 1))):
            return None
        if not away_fn(u):
            return None
        fm = M.reversal_form(self.A5, u, d, self.V.s, self.F.ts)
        return None if fm is None else {"form": fm[0], "merged": int(fm[1])}

    def side_from(self, j, role, d, floor):
        """The first 5M candle ≥ floor from which the trend side (step1 at the closed 15M bar k(u)) stayed d up to j."""
        u = int(j)
        while u - 1 >= floor and int(self.F.k_of[u - 1]) >= 0 and self.trend_dir(int(self.F.k_of[u - 1]), role) == d:
            u -= 1
        return u

    # ------------------------------------------------------------------------------------------ one armed area
    def area5(self, lvl, d):
        """The models' state for one trade-side area at the 5M candle j ⇒ (armed dict | None, [fired at j])."""
        V, F, c5, j, k = self.V, self.F, self.c5, self.j, self.k
        vi = self.visit5(j, lvl, d)
        lid = lvl.get("parent_level", lvl.get("id"))
        if vi["start5"] is None and vi.get("data") is None:
            return None, []
        base = {"object": "area", "area_id": lid, "tf": lvl.get("tf"), "role": lvl.get("role"), "lo": lvl["lo"], "hi": lvl["hi"],
                "state": lvl.get("state"), "direction": int(d), "side": EM.side_of(d), "visit_id": f"{lid}@{vi['vid']}",
                "visit_start": vi["vid"], "visit_start_bar": vi["start5"] if vi["start5"] is not None else -1,
                "visit_start5": self.T5(vi["start5"]), "trigger_tf": "5M", "labels": lvl.get("confluence_label")}
        if vi["start5"] is None:                                           # Q16: no 5M candles for this visit ⇒ the models wait
            base["models"] = {m: {"status": "waiting" if m in self.on else "off", "waiting": vi["data"]} for m in MODELS}
            return base, []
        start, s15 = int(vi["start5"]), int(vi["s15"])
        Ls = V.levels.L
        L = Ls[lid] if isinstance(lid, (int, np.integer)) and 0 <= int(lid) < len(Ls) else None
        if self.came_from_trade_side(s15, lvl, d):                         # 15M state (the close before the visit's 15M bar)
            base["disarmed"] = "price came into the area from the trade side (not a pullback — H2)"
            base["models"] = {m: {"status": "disarmed"} for m in MODELS}
            return base, []
        brk = [b for b, kk, _ in (L.events if L is not None else []) if kk in ("broken", "dead") and s15 <= b <= k]
        if L is not None and L.dead_bar is not None and s15 <= L.dead_bar <= k:
            brk.append(int(L.dead_bar))
        if brk:
            base["disarmed"] = f"the area broke inside this visit at {self.T(min(brk))} (K4: a close beyond + a swing beyond)"
            base["models"] = {m: {"status": "disarmed"} for m in MODELS}
            return base, []
        w0 = self.side_from(j, lvl.get("role"), d, start)
        if w0 > start:
            base["side_since"] = self.T5(w0)

        def same_visit(u):
            return u == j or self.visit5(u, lvl, d)["start5"] == start

        ext = max(self.P(i, d) for i in range(start, j + 1))
        base["visit_extreme"] = round(self.back(ext, d), 2)
        refine = self.refine_on()
        lk = (str(lid), float(lvl["lo"]), float(lvl["hi"]), int(d), start)

        def at_area(u):
            return c5.h2_block(u, lvl, d) is None and c5.outside(u, lvl, d) is None

        def ext_at(u):
            return self.back(max(self.P(i, d) for i in range(start, u + 1)), d)

        def rb_ok(u):
            if not refine:
                return True, None
            ku = int(F.k_of[u])
            rb = self.refined(ku, lvl, d) if ku >= 0 else None
            if rb is None or not any(c5.touches(i, rb) for i in range(start, u + 1)):
                return False, None
            return True, rb

        def e1(u):
            if not at_area(u):
                return False, None
            if not refine:
                return u == start, None
            ok, rb = rb_ok(u)
            if not ok or not c5.touches(u, rb) or any(c5.touches(i, rb) for i in range(start, u)):
                return False, None
            if c5.base_broken(start, u, rb, d) is not None:
                return False, None
            return c5.beyond(u, self.rb_far(rb, d), d) is None, rb

        def e23(u, m):
            if not at_area(u):
                return False, None
            ok, rb = rb_ok(u)
            if not ok or c5.off_base(u, rb) is not None:
                return False, None
            inv = self.farther(ext_at(u), self.rb_far(rb, d), d) if rb else ext_at(u)
            if c5.beyond(u, inv, d) is not None:
                return False, None
            if m == "E2":
                hit = self.c0(u, lvl, d, start, self.appr5(self.visit5(u, lvl, d)))[0]
            else:
                hit = self.choch_candle(self.c1(u, lvl, d, start), u)
            return bool(hit and self.absorbing(u, lvl, d, start) is None), rb

        def e4(u):
            r = self.sweep(u, lvl, d, start)
            if r is None or not at_area(u) or c5.beyond(u, r["sweep_extreme"], d) is not None:
                return False, None
            ok, rb = rb_ok(u)
            if not ok or c5.off_base(u, rb) is not None:
                return False, None
            return ok, ({**r, "refined": rb} if rb else r)

        conds = {"E1": e1, "E2": lambda u: e23(u, "E2"), "E3": lambda u: e23(u, "E3"), "E4": e4}

        def cond(m, u):
            key = ("5:cond", m) + lk + (int(u),)
            if key not in self.memo:
                self.memo[key] = conds[m](u)
            return self.memo[key]
        models, fired = {}, []
        for m in MODELS:
            if m not in self.on:
                models[m] = {"status": "off"}
                continue
            first = None
            for u in range(w0, j + 1):
                if m == "E1" and w0 != start:
                    break
                if not same_visit(u):
                    continue
                ok, info = cond(m, u)
                if ok:
                    first = (u, info)
                    break
            if first is None:
                models[m] = {"status": "waiting" if m != "E1" else "passed", "waiting": self.waiting5(m, lvl, d, start, w0, vi)}
                continue
            u, info = first
            if u < j:
                models[m] = {"status": "fired_earlier", "at": self.T5(u), "bar": int(u)}
                continue
            inv, rule, facts = self.invalidation(m, j, lvl, d, start, info, self.appr5(vi))
            dp = self.data_problem(start, j)
            if dp:
                models[m] = {"status": "blocked_data_problem", "at": self.T5(j), "bar": int(j), "note": dp + " — consumed, not an entry"}
                continue
            if not self.entry_window5(j):
                models[m] = {"status": "fired_outside_hours", "at": self.T5(j), "bar": int(j),
                             "note": "outside the entry hours (operational schedule) — consumed, not an entry"}
                continue
            models[m] = {"status": "fired", "at": self.T5(j), "bar": int(j)}
            rb = (info or {}).get("refined") if m == "E4" else info
            fired.append({"model": m, "variant": "a" if m == "E4" else None, "invalidation": inv, "invalidation_rule": rule,
                          "facts": {**(facts or {}), "trigger_tf": "5M"}, "refined": rb})
        base["models"] = models
        return base, fired

    def waiting5(self, m, lvl, d, start, w0, vi):
        """What an armed model is still waiting for at the 5M candle j (the reason text of a wait)."""
        c5, j, k = self.c5, self.j, self.k
        if m == "E1":
            if w0 != start:
                return f"the trend side changed inside this visit ({self.T5(w0)}) — E1 re-arms with the next visit"
            if self.refine_on():
                rb = self.refined(k, lvl, d) if k >= 0 else None
                if rb is None:
                    return "no refined base yet: no 15M turn of the area's side inside its band (RC2) — E1 waits"
                base = f"the refined 15M base {rb['lo']:,.2f}–{rb['hi']:,.2f} ({rb['ts'][:16]})"
                brk = c5.base_broken(start, j, rb, d)
                if brk is not None:
                    return (f"{base} was closed through in this visit at the 5M candle {self.T5(brk)[:16]} (lifecycle: broken, not "
                            f"entered) — E1 re-arms with the next visit")
                touched = [i for i in range(start, j + 1) if c5.touches(i, rb)]
                if not touched:
                    return f"waiting for a 5M candle to reach {base}"
                why = c5.h2_block(touched[0], lvl, d) or c5.outside(touched[0], lvl, d) or "it closed beyond the base's far edge"
                return (f"E1 fires only on the visit's first 5M candle at {base}; that candle ({self.T5(touched[0])[:16]}) did not "
                        f"qualify: {why} — E1 re-arms with the next visit")
            return f"E1 fires only on a new visit's first 5M candle (this visit began {self.T5(start)})"
        blk = c5.h2_block(j, lvl, d) or c5.outside(j, lvl, d)
        if blk:
            return blk + " (5M candle)"
        if self.refine_on():
            rb = self.refined(k, lvl, d) if k >= 0 else None
            if rb is None:
                return "no refined base yet: no 15M turn of the area's side inside its band (RC2) — the models wait"
            if not any(c5.touches(i, rb) for i in range(start, j + 1)):
                return f"price has not reached the refined 15M base {rb['lo']:,.2f}–{rb['hi']:,.2f} in this visit yet (5M)"
            off = c5.off_base(j, rb)
            if off:
                return off.replace("the candle", "the 5M candle", 1)
        if m == "E2":
            ok, why, _cm = self.c0(j, lvl, d, start, self.appr5(vi))
            if ok:
                return self.absorbing(j, lvl, d, start) or "no commitment"
            return (why or "no commitment") + " (5M)"
        if m == "E3":
            ch = self.c1(j, lvl, d, start)
            if ch.get("done"):
                return self.absorbing(j, lvl, d, start) or (f"the 5M CHoCH candle ({str(ch.get('at'))[:16]}) did not qualify as the "
                                                             f"trigger (it must trade into the refined base) — waiting for a new CHoCH")
            return ch.get("line") or "no 5M CHoCH yet"
        Fe = self.P_far(lvl, d)
        if not any(self.P(i, d) > Fe for i in range(start, j + 1)):
            return "no 5M sweep yet (price has not gone beyond the area's far edge / the visit's extreme and closed back)"
        return "5M sweep seen; waiting for the next 5M push to fail inside the sweep extreme (a confirmed 5M swing)"

    # ------------------------------------------------------------------------------------------ E4 (b) on 5M
    def _touch5(self, kind, obj):
        A5, F = self.A5, self.F
        if kind == "area":
            lo, hi = float(obj["lo"]), float(obj["hi"])
            return lambda b, u: np.flatnonzero((A5["low"][b:u + 1] <= hi) & (A5["high"][b:u + 1] >= lo)) + b
        p0, y0, sl = int(obj["p1"][0]), float(obj["p1"][1]), float(obj["slope"])

        def touch(b, u):
            ii = np.arange(b, u + 1)
            yv = y0 + sl * (F.pos[b:u + 1] - p0)
            return ii[(A5["high"][b:u + 1] >= yv) & (A5["low"][b:u + 1] <= yv)]
        return touch

    def touch_visit5(self, u, oid, born5, born15, touch, aw_sw, d):
        """A revisit of a broken object on 5M (entry_models.Reader.touch_visit): it starts at the first 5M candle touching the object and
        ends at a 15M swing of the finest structure (confirmed by k(u)) built away from it after the start (RC4)."""
        key = ("5:tv", oid, int(u), int(born5), int(d))
        if key in self.memo:
            return self.memo[key]
        F = self.F
        ku = int(F.k_of[int(u)])
        kind = "L" if d < 0 else "H"
        if getattr(self.V, "visit_end_new", False):                        # DECISIONS 64: swings away that do not reach it again
            def at5(p):                                                    # the 5M candle closing with the swing's 15M bar
                c = F.last_child_closing(self.V.bar_end[int(p.bar)])
                return c if c is not None else F.index_of_end(self.V.bar_end[int(p.bar)])
            sw = [(int(at5(p)), bool(aw_sw(p))) for p in self.V.visit_swings()
                  if p.confirm_bar <= ku and born15 <= p.bar <= ku and at5(p) >= 0]
            st = {int(at5(p)) for p in getattr(self.V.levels, "_known0", [])
                  if p.confirm_bar <= ku and born15 <= p.bar <= ku and p.kind == kind and aw_sw(p) and at5(p) >= 0}
            tb = {int(i) for i in touch(int(born5), int(u))} if born5 <= u else set()
            self.memo[key] = EM.revisit_start(tb, sw, st)
            return self.memo[key]
        piv = set()
        for p in getattr(self.V.levels, "_known0", []):
            if p.confirm_bar <= ku and born15 <= p.bar <= ku and p.kind == kind and aw_sw(p):
                c = F.last_child_closing(self.V.bar_end[int(p.bar)])
                c = c if c is not None else F.index_of_end(self.V.bar_end[int(p.bar)])
                if c >= 0:
                    piv.add(int(c))
        tb = {int(i) for i in touch(int(born5), int(u))} if born5 <= u else set()
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

    def broken5(self, d, keep=None, extra=None):
        """E4 (b) on 5M for every broken object of the trade direction known at k ⇒ ([armed dicts], [fired at j])."""
        V, F, c5, j, k = self.V, self.F, self.c5, self.j, self.k
        armed, fired = [], []
        if "E4" not in self.on or k < 0:
            return armed, fired
        for kind, obj, _t15, _a15, aw_sw, born in self.broken_objects(k, d, extra):
            if born > k or (keep is not None and not keep(kind, obj)):
                continue
            born5 = F.first_at_or_after(V.bar_end[int(born) - 1]) if int(born) >= 1 else 0
            if born5 > j:
                continue
            oid = obj["id"] if kind == "area" else f"line:{obj['id']}"
            touch = self._touch5(kind, obj)
            start = self.touch_visit5(j, oid, born5, int(born), touch, aw_sw, d)
            if start is None:
                continue
            role = obj.get("role") if kind == "area" else ("support" if d < 0 else "resistance")
            w0 = self.side_from(j, role, d, start)
            val = round(F.line_value(obj, j), 2) if kind == "line" else None
            base = {"object": "broken_" + kind, "area_id": oid, "tf": obj.get("tf") if kind == "area" else "line",
                    "role": role, "lo": obj.get("lo") if kind == "area" else val, "hi": obj.get("hi") if kind == "area" else val,
                    "state": "BROKEN", "direction": int(d), "side": EM.side_of(d), "visit_id": f"{oid}@{F.bin_T(start)}",
                    "visit_start": F.bin_T(start), "visit_start_bar": int(start), "visit_start5": self.T5(start), "trigger_tf": "5M",
                    "broken_at": self.T(obj.get("broken_at") if kind == "area" else obj.get("break_bar"))}
            if kind == "line":
                base["line"] = {kk: obj.get(kk) for kk in ("id", "family", "tf", "p1", "p2", "slope", "touches", "break_bar", "parallel_of",
                                                            "degree", "kind", "break_side")}
            if kind == "area":
                L = V.levels.L[obj["id"]]
                b0 = int(F.b_of[start])
                back = [b for b, kk, _ in L.events if kk in ("reclaim", "flip", "dead") and b0 <= b <= k]
                if back:
                    base.update(disarmed=f"the broken area changed state inside the revisit at {self.T(min(back))}",
                                models={"E4": {"status": "disarmed"}})
                    armed.append(base)
                    continue
                e0 = float(obj["hi"]) if d < 0 else float(obj["lo"])
                edge = (lambda i, e0=e0: e0)
                away = (lambda i, lo=float(obj["lo"]): self.A5["close"][i] < lo) if d < 0 else \
                    (lambda i, hi=float(obj["hi"]): self.A5["close"][i] > hi)
            else:
                edge = (lambda i, ln=obj: F.line_value(ln, i))
                away = (lambda i, ln=obj: self.A5["close"][i] < F.line_value(ln, i)) if d < 0 else \
                    (lambda i, ln=obj: self.A5["close"][i] > F.line_value(ln, i))
            first, appr_why = None, None
            for u in range(w0, j + 1):
                if self.touch_visit5(u, oid, born5, int(born), touch, aw_sw, d) != start:
                    continue
                key = ("5:e4b", oid, int(start), int(d), int(u))
                if key not in self.memo:
                    r = self.rejection5(u, d, lambda i: len(touch(i, i)) > 0, start, away)
                    res = (None, None)
                    if r is not None and c5.retest_ok(u, r, touch, start, d) is None:
                        res = (r, c5.approach_side(u, r, start, edge, d))
                    self.memo[key] = res
                r, why = self.memo[key]
                if r is None:
                    continue
                if why is not None:
                    appr_why = why
                    continue
                first = (u, r)
                break
            if first is None:
                base["models"] = {"E4": {"status": "waiting", "waiting": appr_why or ("revisit in progress; waiting for a 5M rejection "
                                                                                      "candle that closes away from the broken " + kind)}}
            elif first[0] < j:
                base["models"] = {"E4": {"status": "fired_earlier", "at": self.T5(first[0]), "bar": int(first[0])}}
            elif self.data_problem(start, j):
                base["models"] = {"E4": {"status": "blocked_data_problem", "at": self.T5(j), "bar": int(j),
                                         "note": self.data_problem(start, j) + " — consumed, not an entry"}}
            elif not self.entry_window5(j):
                base["models"] = {"E4": {"status": "fired_outside_hours", "at": self.T5(j), "bar": int(j),
                                         "note": "outside the entry hours (operational schedule) — consumed, not an entry"}}
            else:
                ext = self.back(max(self.P(i, d) for i in range(start, j + 1)), d)
                word = "above" if d < 0 else "below"
                base["models"] = {"E4": {"status": "fired", "at": self.T5(j), "bar": int(j)}}
                fired.append({"model": "E4", "variant": "b", "invalidation": round(ext, 2),
                              "invalidation_rule": f"price {word} the retest extreme {ext:,.2f}",
                              "facts": {**first[1], "object": "broken_" + kind, "retest_extreme": round(ext, 2), "trigger_tf": "5M"},
                              "obj": base, "kind": kind, "raw": obj, "start": int(start)})
            armed.append(base)
        return armed, fired

    # ------------------------------------------------------------------------------------------ the required set on 5M (Q9)
    def confirm5(self, lvl, d, start, appr):
        """The shared confirmation (method.confirm: a2 handover + c0 + c1) read on the visit's 5M candles start … j — the required set
        of the evidence list (Q9: read on 5M at the trigger). ⇒ (read_ok, cm)."""
        V, F, j = self.V, self.F, self.j
        ho = self.ho5(j, lvl, d, start)
        ta = pd.Timestamp(F.ts[int(start)])
        cf = M.confirm(self.A5, start, j, d, lvl, V.s, F.ts, ltf=V.ltf, ltf_times=(ta, ta, pd.Timestamp(F.end[j])), handover=ho,
                       approach=appr)
        cm = dict(cf["commit"] or {})
        cm.update(handover_state={kk: v for kk, v in ho.items() if kk != "events"} | {"tf": "5M"}, choch=cf["choch"],
                  confirm_wait=cf["wait"], volume_measure="raw FUT 5M volume per 5M bar (no time-slot baseline)", arm_bar5=int(start),
                  tf="5M")
        ok = bool(cf["ok"]) and not (cf["c0"] and cm.get("vol_na") and bool(V.s.get("c0_volume_required", True)))
        return ok, cm


def read5(V, j, trend, act, side_fn=None, keep=None, extra=None, prefix="", broken_on=True):
    """entry_models.read at the 5M decision candle j (trigger_tf = 5M): `act` = step2's watch-list at k(j). Same outputs; every entry
    carries trigger_tf "5M", the 5M trigger candle (ts, close, OHLC), context_bar_ts (the last closed 15M bar) and entry_ref = the 5M
    close."""
    R = Reader5(V, j) if side_fn is None else Reader5(V, j, side_fn)
    F, k = R.F, R.k
    if k < 0:
        return {"entries": [], "armed": [], "first_area": None, "reader": R}
    if side_fn is None and keep is None and extra is None:                 # DECISIONS 40 (concept L): range edges = areas (15M at k)
        act = list(act) + R.range_edge_areas(k, trend, act)
    armed, entries, cands = [], [], []
    first_area = None
    for lvl in act:
        d = M._dir(trend, lvl["role"])
        if d == 0:
            continue
        cands.append((lvl, d))
        a, fired = R.area5(lvl, d)
        if a is None:
            continue
        armed.append(a)
        first_area = first_area or (lvl, d, a)
        for f in fired:
            entries.append((f, lvl, d, a))
    if str(V.s.get("entry_cluster_rule", "cluster")) == "cluster":
        entries = EM.clusters(armed, entries, cands, prefix=prefix + "C")
    if trend in ("UP", "DOWN") and broken_on:
        d = M._dir(trend)
        b_armed, b_fired = R.broken5(d) if keep is None and extra is None else R.broken5(d, keep, extra)
        armed.extend(b_armed)
        b_entries = [(f, None, d, f["obj"]) for f in b_fired]
        if str(V.s.get("entry_cluster_rule", "cluster")) == "cluster":
            b_entries = EM.clusters(b_armed, b_entries, obj=("broken_area", "broken_line"), prefix=prefix + "CB")
        entries.extend(b_entries)
    A5 = F.A
    out = []
    for f, lvl, d, a in entries:
        start5 = int(a["visit_start_bar"])
        arm15 = min(int(F.b_of[start5]), k)
        if f["model"] != "E4" or f["variant"] == "a":
            vi = R.visit5(j, lvl, d)
            ok5, cm5 = R.confirm5(lvl, d, start5, R.appr5(vi))
            mf = vi.get("move_from15")              # DECISIONS 64 (B2): the last away swing at k
            area = {kk: lvl.get(kk) for kk in ("id", "tf", "role", "lo", "hi", "state", "births", "confluence_label")}
            if lvl.get("range_edge"):
                area["range_edge"] = lvl["range_edge"]
        elif f["kind"] == "area":
            x = f["raw"]
            lvl = {**x, "visit_from": arm15}
            ok5, cm5 = R.confirm5(lvl, d, start5, None)
            # L5-a (RSI evidence only, never a gate): the move into the retest of the broken area begins at the last swing built away
            # from it — the same visit / approach the 15M path reads (V._confirm's move_from_bar on the area counted from its break).
            # Without it the RSI read said "the move into the zone is not known" although that swing exists (layer 5 gallery, C-L5-1).
            vb = R.visit5(j, lvl, d)
            mf = vb.get("move_from15")
            area = {kk: x.get(kk) for kk in ("id", "tf", "role", "lo", "hi", "state", "births", "confluence_label")}
        else:
            ln = f["raw"]
            v = round(F.line_value(ln, j), 2)
            lvl = {"id": f"line:{ln['id']}", "lo": v, "hi": v, "tf": "line", "role": a["role"], "births": ["tl"], "sweeps": 0,
                   "fresh": None, "confluence_line": True, "confluence": []}
            ok5, cm5 = R.confirm5(lvl, d, start5, None)
            mf = R.line_move_from(k, ln, d, arm15)                         # DECISIONS 56 (L5-c): the move into the line's retest
            area = {"id": lvl["id"], "tf": "line", "role": a["role"], "lo": v, "hi": v, "state": "BROKEN", "line": a.get("line")}
        if mf is not None:
            cm5["move_from_bar"] = mf
        ev = EM.Reader.evidence(R, k, d, lvl, arm15, cm=cm5, read_ok=ok5, move_from=mf)   # confirming pieces / zone read at 15M (k)
        ev["evidence_list"] = {**ev["evidence_list"], "entry_hours": "inside" if R.entry_window5(j) else "outside (operational)"}
        pa_ev = PE.for_entry(V, k, d, {**area, "object": a["object"]}, lvl=lvl, arm=arm15, move_from=mf)
        m = f["model"]
        name = EM.NAME[m] + (f" ({f['variant']})" if m == "E4" else "")
        cl = f.get("cluster")
        vid, vstart = (cl["visit_id"], cl["visit_start"]) if cl else (a["visit_id"], a["visit_start"])
        facts = dict(f.get("facts") or {})
        if m == "E3":                                                      # the CHoCH level (card: the 5M CHoCH line)
            facts["choch_level"] = R.c1(j, lvl, d, start5).get("lh")
        lv = [[F.T(i), round(F.line_value(f["raw"], i), 2)] for i in range(start5, j + 1)] if f.get("kind") == "line" else None
        f = {**f, "facts": facts}
        ohlc = {kk: round(float(A5[kk][j]), 2) for kk in ("open", "high", "low", "close")}
        vol5 = A5["volume_raw"][j]
        out.append({"model": m, "name": name, "direction": int(d), "side": EM.side_of(d), "object": a["object"],
                    "area": {**area, "object": a["object"]}, "visit_id": vid, "visit_start": vstart, "cluster": cl,
                    "area_visit_id": a["visit_id"], "area_visit_start": a["visit_start"], "refined_base": f.get("refined"),
                    "key": f"{vid.split('@')[0]}|{vstart}|{m}", "trigger_tf": "5M", "trigger_bar": int(j), "trigger_ts": F.T(j),
                    "trigger_bar_end": F.E(j), "trigger_ohlc": ohlc, "trigger_volume": None if not np.isfinite(vol5) else float(vol5),
                    "trigger_bar15_ts": F.bin_T(j), "context_bar": int(k), "context_bar_ts": str(pd.Timestamp(V._ts[k])),
                    "context_bar_end": str(V.bar_end[k]), "visit_start5": a.get("visit_start5"), "line_values": lv,
                    "entry_ref": round(float(A5["close"][j]), 2),
                    "invalidation": f["invalidation"], "invalidation_rule": f["invalidation_rule"], "facts": f.get("facts") or {},
                    "label": ev["label"], "evidence": ev["evidence"], "evidence_list": ev["evidence_list"],
                    "channel_evidence": ev["channel_evidence"], "pa_evidence": pa_ev,
                    "confirming": ev["confirming"], "_eval": ev, "_lvl": lvl})
    return {"entries": out, "armed": armed, "first_area": first_area, "reader": R}
