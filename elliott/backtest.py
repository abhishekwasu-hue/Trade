"""
elliott/backtest.py — E4: event-driven backtest (signals E2 → plan E3 → exits E3), ₹ / R-multiple / % capital
-----------------------------------------------------------------------------------------------------------
🎓 दर scan वेळ t (Scanner.times — सगळ्या TFs चे bar_end):
  1. उघड्या trades: त्यांच्या trigger TF चा bar t ला बंद झाला असेल तर exits.evaluate (ctx इथे मोजतो — real break BreakCache ने,
     C zone उलट reversal, acceptance, trailing D−1 pivot, उलट signal — पुढच्या TTF close पर्यंत टिकणारी नोंद). निर्णय bar close
     वर, **fill पुढच्या bar च्या open वर** (15:30 नंतर ⇒ पुढच्या session चा open); emergency (strike cross) intrabar — gap असेल
     तर bar च्या open वर. Expiry-day तपासणी 5m घड्याळावर (14:45). Expiry close पर्यंत उघडा ⇒ intrinsic वर settle.
  2. Scanner.step(t) ⇒ नवीन signals; fill = पुढच्या TTF bar चा open (त्या bar ची किंमत t नंतरच माहीत; signal bar वर fill नाही).
     Entry filters फक्त नवीन entries थांबवतात: max_open_spreads, max_daily_loss_pct, एका setup-instance वर एकच trade
     (soft stop नंतर max_reentries पर्यंत re-entry; premium stop नंतर reentry_after_premium_stop).
  3. Plan (strikes.plan_spread) — premium = `pricer` (bhavcopy / Upstox / BS). size_zero (default Tier B/C) ⇒ **shadow** 1-lot trade:
     ₹ portfolio मध्ये नाही, पण R-multiple तक्त्यांत (setup ची गुणवत्ता sizing शिवाय दिसावी — E3 शोध).
P&L = (credit − debit) × qty − खर्च (दोन्ही बाजू, तारीखनिहाय) ; R = P&L ÷ max loss ((width − credit) × qty) ; % = P&L ÷ capital.
Premium मॉडेल (`ModelPricer`): data नसताना Black-Scholes, IV = आधीच्या 20 दिवसांचा realized vol — **"model premium"** (उत्तर 4 (b)).
"""
import bisect
import datetime as dt
import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import contracts as CT
from . import costs as CO
from . import exits as EX
from . import pricing as PR
from . import reversal as RV
from . import strikes as SK
from .breaks import frame_index_at
from .settings import TF_MIN
from .trigger import Scanner

CLOSE_T = dt.time(15, 30)


class ModelPricer:
    """BS premium. IV(day) = त्या दिवसाआधीच्या `rv_days` पूर्ण sessions च्या daily close log-returns चा annualised std (causal).
    पूर्ण session नसलेला दिवस (मुहूर्त / outage) ⇒ आधीचा उपलब्ध IV (review: नाहीतर premium None ⇒ खोटा नफा)."""
    source = "model_bs_realized_vol"

    def __init__(self, df1m, s, cal, rv_days=20):
        d = df1m[["timestamp", "close"]].copy()
        d["day"] = pd.to_datetime(d["timestamp"]).dt.date
        closes = d.groupby("day")["close"].last()
        closes = closes[[c in cal._set for c in closes.index]] if cal.days else closes
        r = np.log(closes).diff()
        vol = (r.rolling(rv_days, min_periods=rv_days).std() * math.sqrt(252)).shift(1).dropna()
        self._days = list(vol.index)
        self._vals = vol.to_numpy(float)
        self.cal, self.s = cal, s

    def iv(self, day):
        day = pd.Timestamp(day).date()
        i = bisect.bisect_right(self._days, day) - 1
        if i < 0:
            return None
        v = self._vals[i]
        return float(v) if np.isfinite(v) else None

    def premium(self, opt, k, expiry, ts, spot):
        iv = self.iv(pd.Timestamp(ts).date())
        if iv is None:
            return None
        T = CT.dte_frac(self.cal, ts, expiry, "session_fraction") / 252.0
        return PR.price(spot, k, T, self.s["risk_free_rate"], iv, opt)


@dataclass
class Trade:
    sig: object
    plan: dict
    st: object                          # exits.TradeState
    tf: str
    entry_idx: int                      # fill bar (TTF index)
    entry_ts: pd.Timestamp
    entry_spot: float
    sized: bool                         # false ⇒ shadow (1 lot, ₹ portfolio बाहेर)
    inv_from: int                       # hard inv चा real-break कुठल्या bar पासून मोजायचा
    entry_cost: float
    realized: float = 0.0               # partial exits चा ₹ (खर्चानंतर)
    exit_ts: object = None
    exit_reason: str = ""
    exit_debit: float = float("nan")
    breached: bool = False              # spot ने short strike ओलांडला (कधीही)
    opp_flag: bool = False              # मागच्या TTF close पासून उलट (same degree) signal आला
    exp_checked: bool = False           # expiry-day 14:45 तपासणी झाली
    deferred: int = 0                   # premium नाही म्हणून पुढे ढकललेले exits
    tp_tight: bool = False              # opposite_candle_action = tighten_profit_target
    events: list = field(default_factory=list)
    notes: list = field(default_factory=list)           # log-only घटना (opposite_candle) — fills नाहीत
    opp_on: bool = False
    exit_price_src: str = ""            # forced exit चा premium स्रोत: pricer / model_fallback / full_width


def _dte_bucket(n):
    return str(min(max(int(n), 1), 5)) + ("+" if n >= 5 else "")


def emergency_spot(o, k, d):
    """क्रम 0 exit चा spot: bar उघडतानाच strike पलीकडे (gap) ⇒ open; नाहीतर strike ओलांडतानाचा भाव."""
    if d > 0:
        return o if o < k else k - CO.TICK
    return o if o > k else k + CO.TICK


def collect_signals(sc, times):
    """Scanner एकदाच चालवून {t: [Signal]} (variants replay साठी)."""
    out = {}
    for t in times:
        sg = sc.step(t)
        if sg:
            out[t] = sg
    return out


class Backtest:
    def __init__(self, df1m, s, pricer=None, cal=None, book=None, shadow=True, scanner=None, structure_free_exits=False,
                 replay=None, trade_from=None, entry_until=None, entry_filters=True):
        """replay = {t: [Signal]} (आधीच्या scanner run चे) ⇒ scanner पुन्हा चालवत नाही (variants: फक्त trading settings वेगळे).
        trade_from / entry_until ⇒ entries ची खिडकी (warm-up / split embargo). entry_filters=False ⇒ max_open, daily loss,
        एक-trade-प्रति-setup सगळे बंद (baseline तुलनेत दोन्ही बाजूंना सारखं)."""
        self.s = s
        self.sc = scanner or Scanner(df1m, s)
        self.replay = replay
        self.trade_from = None if trade_from is None else pd.Timestamp(trade_from)
        self.entry_until = None if entry_until is None else pd.Timestamp(entry_until)
        self.filters = entry_filters
        self.cal = cal or CT.TradingCalendar.from_spot(df1m, min_bars=s.get("full_session_min_bars", CT.FULL_SESSION_MIN_BARS))
        self.book = book or CT.ExpiryBook(self.cal)
        self.pricer = pricer or ModelPricer(df1m, s, self.cal)
        # review fix 1: forced exits (emergency / end_of_data) ला premium नसेल तर intrinsic नाही (strike जवळ ≈ 0 ⇒ जवळजवळ पूर्ण credit — आशावादी).
        # आधी model price (primary pricer model नसेल तर), तोही नसेल तर पूर्ण width (सर्वात वाईट).
        self.fallback_pricer = None if isinstance(self.pricer, ModelPricer) else ModelPricer(df1m, s, self.cal)
        self.shadow = shadow
        self.sfe = structure_free_exits                # baseline तुलनेसाठी: structure-आधारित exits बंद
        self.open, self.closed, self.skipped = [], [], []
        self.day_pnl = {}
        self.key_hist = {}                             # setup key → exit reasons
        self.fine = self.sc.frames["5m"] if "5m" in self.sc.frames else self.sc.frames[min(self.sc.frames, key=TF_MIN.get)]
        self._fine_ts = self.fine["timestamp"].to_numpy("datetime64[ns]")
        self._last_px = None

    # ------------------------------------------------------------------------------------------------ pricing
    def _spread(self, tr, ts, spot):
        p = tr.plan
        a = self.pricer.premium(p["opt"], p["short_k"], p["expiry"], ts, spot)
        b = self.pricer.premium(p["opt"], p["long_k"], p["expiry"], ts, spot)
        return None if a is None or b is None else (a, b)

    def _debit(self, tr, ts, spot):
        px = self._spread(tr, ts, spot)
        if px is None:
            self._last_px = None
            return None
        self._last_px = (CO.slip(px[0], "buy", self.s), CO.slip(px[1], "sell", self.s))
        return self._last_px[0] - self._last_px[1]

    def _forced_debit(self, tr, ts, spot):
        """Forced exit (emergency / end_of_data) चा debit: pricer → model fallback → पूर्ण width. रिटर्न (debit, स्रोत)."""
        debit = self._debit(tr, ts, spot)
        if debit is not None:
            return debit, "pricer"
        if self.fallback_pricer is not None:
            p = tr.plan
            a = self.fallback_pricer.premium(p["opt"], p["short_k"], p["expiry"], ts, spot)
            b = self.fallback_pricer.premium(p["opt"], p["long_k"], p["expiry"], ts, spot)
            if a is not None and b is not None:
                self._last_px = (CO.slip(a, "buy", self.s), CO.slip(b, "sell", self.s))
                return self._last_px[0] - self._last_px[1], "model_fallback"
        w = float(tr.plan["width"])
        self._last_px = (w, 0.0)                                                    # closing खर्च: short leg = width, long ≈ 0
        return w, "full_width"

    def _next_open(self, t):
        """t नंतर सुरू होणारा पहिला (finest TF) bar: (timestamp, open) — 15:30 नंतर ⇒ पुढच्या session चा open (gap सह)."""
        i = int(np.searchsorted(self._fine_ts, np.datetime64(pd.Timestamp(t), "ns"), "left"))
        if i >= len(self.fine):
            return None
        return pd.Timestamp(self.fine["timestamp"].iloc[i]), float(self.fine["open"].iloc[i])

    # ------------------------------------------------------------------------------------------------ entries
    def _key_filter(self, sig):
        s = self.s
        if any(t.sig.key == sig.key for t in self.open):
            return "same_setup_open"
        hist = self.key_hist.get(sig.key, [])
        if hist:
            reentries = len(hist)
            last = hist[-1]
            ok = (last == "soft_stop") or (last == "premium_stop" and s["reentry_after_premium_stop"])
            if not ok or reentries > s["max_reentries"]:
                return "no_reentry"
        return None

    def _portfolio_filter(self, day):
        s = self.s
        if sum(t.sized for t in self.open) >= s["max_open_spreads"]:
            return "max_open_spreads"
        if self.day_pnl.get(day, 0.0) <= -s["capital"] * s["max_daily_loss_pct"] / 100.0:
            return "max_daily_loss"
        return None

    def _enter(self, sig):
        s = self.s
        fr = self.sc.frames[sig.ttf]
        j = sig.ttf_idx + 1
        if j >= len(fr):
            self.skipped.append((sig, "no_fill_bar"))
            return
        fill_ts = pd.Timestamp(fr["timestamp"].iloc[j])
        spot = float(fr["open"].iloc[j])
        if self.filters:
            why = self._key_filter(sig)
            if why:
                self.skipped.append((sig, why))
                return
        mr = float(self.sc.cache[sig.ttf].mr[sig.ttf_idx]) if np.isfinite(self.sc.cache[sig.ttf].mr[sig.ttf_idx]) else 0.0
        pf = lambda opt, k, e: self.pricer.premium(opt, k, e, fill_ts, spot)          # noqa: E731
        slip = s["slippage_ticks"] * CO.TICK
        iv = self.pricer.iv(fill_ts.date())
        plan = SK.plan_spread(sig, spot, fill_ts, iv, mr, self.cal, self.book, s, pf, slip_pts=slip, context="backtest")
        sized = True
        if plan == "size_zero" and self.shadow:
            plan = SK.plan_spread(sig, spot, fill_ts, iv, mr, self.cal, self.book, {**s, "min_one_lot": True}, pf, slip_pts=slip,
                                  context="backtest")
            sized = False
        if isinstance(plan, str):
            self.skipped.append((sig, plan))
            return
        if sized and self.filters:                                                     # portfolio मर्यादा फक्त sized trades ना
            why = self._portfolio_filter(fill_ts.date())
            if why:
                self.skipped.append((sig, why))
                return
        if plan["credit"] <= 0:
            self.skipped.append((sig, "credit_after_slippage"))
            return
        sp, lp = CO.slip(plan["short_px"], "sell", s), CO.slip(plan["long_px"], "buy", s)
        plan["credit_filled"] = plan["credit"]
        cost = CO.spread_cost(fill_ts, sp, lp, plan["qty"], s, opening=True)["total"]
        st = EX.TradeState(sig, plan, fill_ts, plan["credit"], plan["lots"], sig.hard_inv)
        self.open.append(Trade(sig, plan, st, sig.ttf, j, fill_ts, spot, sized, sig.ttf_idx + 1, cost))

    # ------------------------------------------------------------------------------------------------ exits
    def _hard_broken(self, tr, t, j, side):
        """Hard inv (count मेला) — count engine सारख्याच confirmation TF वर (F4, `break_confirm_tf`). Progressive inv नंतर
        (inv_from) फक्त त्या bar पासूनचे bars."""
        conf = getattr(self.sc, "confirm", None)
        if conf is None:
            return self.sc.cache[tr.tf].confirm_index(tr.inv_from, tr.st.hard_inv, side, j) is not None
        sig = tr.sig
        deg, start = (sig.inv_degree, sig.inv_start_ts) if getattr(sig, "inv_start_ts", None) is not None \
            else (sig.degree, sig.wave_start_ts)
        if tr.inv_from > tr.entry_idx:                                    # progressive inv: नवा level, त्या bar पासूनचे bars
            fr = self.sc.frames[tr.tf]                                     # (TF निवड मूळ count च्या wave start वरूनच)
            since = pd.Timestamp(fr["timestamp"].iloc[min(tr.inv_from, len(fr) - 1)])
            return conf.broken(deg, start, tr.st.hard_inv, side, t, since=since)
        return conf.broken(deg, start, tr.st.hard_inv, side, t)

    def _parent_broken(self, tr, t, j, side):
        """§7 प्रसार 4: parent (D+1) चा inv तुटला — parent count सारख्याच confirmation TF वर (F4). Parent start नसेल ⇒ trade TF."""
        sig, conf = tr.sig, getattr(self.sc, "confirm", None)
        levels = [lv for lv, sd, _ in sig.parent_invs if sd == side]
        if conf is None or getattr(sig, "parent_start_ts", None) is None:
            return any(self.sc.cache[tr.tf].confirm_index(tr.entry_idx, lv, side, j) is not None for lv in levels)
        return any(conf.broken(sig.degree + 1, sig.parent_start_ts, lv, side, t) for lv in levels)

    def _trail(self, tr, t):
        d = max(tr.sig.degree - 1, 0)                     # D0 ला खाली degree नाही ⇒ D0 चेच pivots (नोंद)
        piv, _ = self.sc.eng.known(d, t)
        kind = "L" if tr.sig.trade_dir > 0 else "H"
        cand = [p.price for p in piv if p.kind == kind and p.ts >= tr.entry_ts]
        return cand[-1] if cand else None

    def _close(self, tr, ts, reason, debit_pts, lots=None, extra_cost=0.0):
        s = self.s
        lots = tr.st.lots_open if lots is None else lots
        qty = lots * tr.plan["lot"]
        pr = self._last_px
        cost = (CO.spread_cost(ts, pr[0], pr[1], qty, s, opening=False)["total"] if pr else 0.0) + extra_cost
        pnl = (tr.st.entry_credit - debit_pts) * qty - cost - tr.entry_cost * (lots / tr.plan["lots"])
        tr.realized += pnl
        tr.st.lots_open -= lots
        if tr.sized:
            self.day_pnl[ts.date()] = self.day_pnl.get(ts.date(), 0.0) + pnl
        tr.events.append((ts, reason, lots, debit_pts))
        if tr.st.lots_open <= 0:
            tr.exit_ts, tr.exit_reason, tr.exit_debit = ts, reason, debit_pts
            self.open.remove(tr)
            self.closed.append(tr)
            self.key_hist.setdefault(tr.sig.key, []).append(reason)

    def _exit_next_open(self, tr, t, reason, lots=None):
        """Bar close वर निर्णय ⇒ fill पुढच्या bar च्या open वर (entry सारखंच; 15:30 नंतर ⇒ पुढच्या session चा open).
        Premium मिळाला नाही ⇒ exit पुढे ढकल (खोटा नफा नाही)."""
        nx = self._next_open(t)
        exp_close = pd.Timestamp.combine(tr.plan["expiry"], CLOSE_T)
        if nx is None or nx[0] >= exp_close:
            return False                                                              # expiry settle करेल
        ts, spot = nx
        debit = self._debit(tr, ts, spot)
        if debit is None:
            tr.deferred += 1
            return False
        self._close(tr, ts, reason, min(debit, tr.plan["width"]), lots=lots)
        return True

    def _manage(self, tr, t):
        s, sig = self.s, tr.sig
        fr = self.sc.frames[tr.tf]
        j = frame_index_at(fr, t)
        if j < tr.entry_idx or pd.Timestamp(fr["bar_end"].iloc[j]) != t:
            return
        self._last_px = None
        o, h, l, c = (float(fr[k].iloc[j]) for k in ("open", "high", "low", "close"))
        d = sig.trade_dir
        k = tr.plan["short_k"]
        if (l < k) if d > 0 else (h > k):
            tr.breached = True
        cache = self.sc.cache[tr.tf]
        side = "below" if d > 0 else "above"
        ctx = {"bar": (o, h, l, c), "atr": float(self.sc.atr[tr.tf][j]) if np.isfinite(self.sc.atr[tr.tf][j]) else 0.0,
               "iv": self.pricer.iv(t.date()), "expiry_day": False}                    # expiry check 5m घड्याळावर (_expiry_check)
        mark = self._debit(tr, t, c)
        ctx["mark"] = mark
        if s["hard_stop_eval"] == "intrabar":
            ctx["mark_worst"] = self._debit(tr, t, l if d > 0 else h)
        if not self.sfe:
            ctx["hard_broken"] = self._hard_broken(tr, t, j, side)
            ctx["parent_broken"] = self._parent_broken(tr, t, j, side)
            ctx["soft_broken"] = cache.confirm_index(tr.entry_idx, sig.soft_stop, side, j) is not None
            zone = EX.c_zone(sig, s)
            if zone and sig.tier == "B":
                tol = s["zone_tol_atr"] * ctx["atr"]
                ctx["opposite_reversal"] = EX.c_zone_reversal(self.sc.bars[tr.tf], j, sig, s, tol, min_start=tr.entry_idx)
                far = max(zone) if d > 0 else min(zone)
                ctx["c_zone_accepted"] = cache.confirm_index(tr.entry_idx, far, "above" if d > 0 else "below", j) is not None
            ctx["trail_level"] = self._trail(tr, t)
            ctx["opposite_signal"] = tr.opp_flag
            tr.opp_flag = False
            # addendum §5: position विरुद्ध reversal composite (pullback origin H वर नकार) — **कधीच थेट exit नाही**
            opp = RV.evaluate(self.sc.bars[tr.tf], j, -d, [sig.sub_origin], s["zone_tol_atr"] * ctx["atr"], s,
                              min_start=tr.entry_idx)["ok"]
            if opp and not tr.opp_on:                                                   # सलग bars वर एकदाच नोंद
                tr.notes.append((t, "opposite_candle"))
                if s["opposite_candle_action"] == "tighten_profit_target":
                    tr.tp_tight = True
            tr.opp_on = opp
            se = {**s, "tp_pct_credit": [x / 2.0 for x in s["tp_pct_credit"]]} if tr.tp_tight else s
            r = EX.evaluate(tr.st, ctx, se)
        else:
            # structure-free (baseline तुलना): फक्त emergency, premium stop, profit %
            r = EX.evaluate(tr.st, ctx, {**s, "progress_bars_mult": 0.0, "progressive_inv": False, "tierB_exit_mode": "fixed_mult",
                                         "tierB_target_mult": 1e9, "tierA_target_fibs": [1e9]})
        if r["move_inv"] is not None:
            tr.inv_from = j + 1
        if r["exit"] == "emergency_short_strike":                                     # intrabar — लगेच, gap असेल तर open वर
            # review fix 2: bar च्या **सुरुवातीच्या** वेळी price (cross bar मध्ये कधीही झाला असेल; शेवटच्या वेळी price केल्यास
            # bar भराचा time decay मिळतो ⇒ 1-DTE वर तोटा कमी दिसतो). Conservative मर्यादा.
            t0 = pd.Timestamp(fr["timestamp"].iloc[j])
            debit, src = self._forced_debit(tr, t0, emergency_spot(o, k, d))
            tr.exit_price_src = src
            self._close(tr, t, r["exit"], min(debit, tr.plan["width"]))
        elif r["exit"] == "premium_stop" and s["hard_stop_eval"] == "intrabar":
            stop = s["hard_stop_mult"] * tr.st.entry_credit
            gap = self._debit(tr, pd.Timestamp(fr["timestamp"].iloc[j]), o)            # open चा spot ⇒ bar start ची वेळ (decay नाही)
            debit = max(stop, gap) if gap is not None else stop                       # gap ने stop पलीकडे उघडलं ⇒ open
            self._close(tr, t, r["exit"], min(debit, tr.plan["width"]))
        elif r["exit"] is not None:
            self._exit_next_open(tr, t, r["exit"])
        elif r["partial_lots"] and tr.st.lots_open > r["partial_lots"]:
            if not self._exit_next_open(tr, t, "partial", lots=r["partial_lots"]):
                tr.st.partial_done = False                                            # partial झालाच नाही ⇒ पुढच्या bar ला पुन्हा

    def _expiry_check(self, tr, t):
        """§9 क्रम 7 — expiry दिवशी expiry_exit_time नंतरचा पहिला 5m close: short ITM किंवा < hold SD ⇒ exit (एकदाच)."""
        s = self.s
        if tr.exp_checked or t.date() != tr.plan["expiry"]:
            return
        if t.time() < dt.time(*map(int, s["expiry_exit_time"].split(":"))):
            return
        j = frame_index_at(self.fine, t)
        if j < 0 or pd.Timestamp(self.fine["bar_end"].iloc[j]) != t:
            return
        tr.exp_checked = True
        c = float(self.fine["close"].iloc[j])
        k, d = tr.plan["short_k"], tr.sig.trade_dir
        iv = self.pricer.iv(t.date())
        left = (pd.Timestamp.combine(t.date(), CLOSE_T) - t).total_seconds() / 60.0
        itm = (c < k) if d > 0 else (c > k)
        if itm or not iv or abs(c - k) < s["expiry_hold_min_dist_sd"] * EX.sd_remaining(c, iv, left):
            self._last_px = None
            if not self._exit_next_open(tr, t, "expiry_day_risk"):
                tr.exp_checked = False

    def _settle_expired(self, t):
        for tr in list(self.open):
            exp_close = pd.Timestamp.combine(tr.plan["expiry"], CLOSE_T)
            if t >= exp_close:
                j = frame_index_at(self.fine, exp_close)
                spot = float(self.fine["close"].iloc[j]) if j >= 0 else tr.entry_spot
                p, d = tr.plan, tr.sig.trade_dir
                intr_s = max(0.0, (p["short_k"] - spot) if d > 0 else (spot - p["short_k"]))
                intr_l = max(0.0, (p["long_k"] - spot) if d > 0 else (spot - p["long_k"]))
                self._last_px = None
                stt = CO.settle_cost(exp_close, intr_l, spot, tr.st.lots_open * p["lot"])
                self._close(tr, exp_close, "expiry_settle", intr_s - intr_l, extra_cost=stt)

    def _finish(self, t):
        """Data संपला: उरलेले trades शेवटच्या bar च्या close वर बंद ("end_of_data" — report मध्ये वेगळे मोजले जातात)."""
        for tr in list(self.open):
            j = frame_index_at(self.fine, t)
            spot = float(self.fine["close"].iloc[j])
            debit, src = self._forced_debit(tr, t, spot)
            tr.exit_price_src = src
            self._close(tr, t, "end_of_data", min(debit, tr.plan["width"]))

    # ------------------------------------------------------------------------------------------------ run
    def run(self, times=None, end=None):
        self._last_px = None
        last = None
        for t in (self.sc.times() if times is None else times):
            if end is not None and t > end:
                break
            last = t
            self._settle_expired(t)
            sigs = self.replay.get(t, []) if self.replay is not None else self.sc.step(t)
            for sg in sigs:                                                           # उलट signal ची नोंद (पुढच्या TTF close पर्यंत)
                for tr in self.open:
                    if sg.degree == tr.sig.degree and sg.trade_dir == -tr.sig.trade_dir:
                        tr.opp_flag = True
            for tr in list(self.open):
                self._manage(tr, t)
                if tr in self.open:
                    self._expiry_check(tr, t)
            if (self.trade_from is None or t >= self.trade_from) and (self.entry_until is None or t <= self.entry_until):
                for sg in sigs:
                    self._enter(sg)
        if last is not None and self.open:
            self._finish(last)
        return self.closed

    # ------------------------------------------------------------------------------------------------ results
    def results(self):
        rows = []
        for tr in self.closed:
            p, sg = tr.plan, tr.sig
            ml = (p["width"] - p["credit_filled"]) * p["qty"]
            rows.append({"t": sg.t, "fill": tr.entry_ts, "exit": tr.exit_ts, "setup": sg.setup, "tier": sg.tier, "degree": sg.degree,
                         "dir": sg.direction, "ttf": tr.tf, "dte": p["dte_days"], "dte_b": _dte_bucket(p["dte_days"]),
                         "expiry": p["expiry"], "short_k": p["short_k"], "long_k": p["long_k"], "credit": p["credit_filled"],
                         "lots": p["lots"], "qty": p["qty"], "pnl": tr.realized, "R": tr.realized / ml if ml > 0 else np.nan,
                         "pct_cap": tr.realized / self.s["capital"] * 100.0, "reason": tr.exit_reason, "breach": tr.breached,
                         "sized": tr.sized, "max_loss_hit": tr.exit_debit >= p["width"] - 1e-9 if tr.exit_debit == tr.exit_debit else False,
                         "next_weekly": p["next_weekly"], "over_budget": p.get("over_budget", False), "deferred": tr.deferred,
                         "exit_price_src": tr.exit_price_src})
        return pd.DataFrame(rows)
