"""
pullback_credit_spread/signal.py
--------------------------------
🎓 Entry निर्णय — spec §1 चा क्रम. प्रत्येक पायरीचा ✅/❌ + कारण (Signal Log / dashboard checklist साठी). पहिली ❌ पायरी ⇒ entry नाही
(पुढच्या पायऱ्या "—" म्हणून नोंदवतो; live preview ला संपूर्ण चित्र हवं असेल तर `full=True` ⇒ सर्व पायऱ्या तपासतो, पण ok फक्त सर्व ✅ असतील तर).

Inputs: frames = {tf: DataFrame (timestamp/open/high/low/close)} — फक्त **पूर्ण** bars (caller ची जबाबदारी; `completed()` मदतीला).
levels = [{price, low, high, role ("SUPPORT"/"RESISTANCE"/"ZONE"), role_reversal(bool)}] (level engine adapter मधून — `levels_source.py`).
Breakout वर entry **कधीच** नाही: level चा खरा break (core.real_break) ⇒ idea रद्द.
"""
import pandas as pd

from opportunity_engine.structure import DN, DN_PB, DN_WEAK, RANGE, UP, UP_PB, UP_WEAK, StructureTracker
from price_action import candles as CA
from price_action import legs as LG

from . import core as C
from .settings import tf_minutes

OK, FAIL, SKIP = "✅", "❌", "—"


MIN_LEG_BARS = 30            # legs classifier ला किमान इतके bars (डेटा-पुरेसेपणा; strategy setting नाही)
LEG_BASE = dict(e_hi=0.35, o_lo=0.65, d_k=1.5, d_body=0.5)      # T2.3 चं IS calibration (leg_classifier_g1.md)


def _naive(ts):
    ts = pd.to_datetime(ts)
    if getattr(ts.dt, "tz", None) is not None:
        ts = ts.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    return ts


def completed(df, tf, now):
    """फक्त `now` पर्यंत **संपलेले** bars (timestamp + TF ≤ now). tz-aware timestamps IST naive मध्ये."""
    if df is None or not len(df):
        return df
    d = df.copy()
    d["timestamp"] = _naive(d["timestamp"])
    now = pd.Timestamp(now)
    if now.tzinfo is not None:
        now = now.tz_convert("Asia/Kolkata").tz_localize(None)
    return d[d["timestamp"] + pd.Timedelta(minutes=tf_minutes(tf)) <= now].reset_index(drop=True)


def trend_state(df, tf):
    """StructureTracker (no-lookahead, incremental; bar_end = timestamp + TF) → शेवटची state."""
    tr = StructureTracker(tf)
    step = pd.Timedelta(minutes=tf_minutes(tf))
    for r in df.itertuples(index=False):
        tr.on_bar(pd.Timestamp(r.timestamp) + step, r.open, r.high, r.low, r.close)
    return tr.state


def bias_of(state, settings):
    """UPTREND(+PB) ⇒ LONG; DOWNTREND(+PB) ⇒ SHORT; WEAK/RANGE ⇒ settings नुसार skip (WEAK skip बंद ⇒ मूळ trend दिशा)."""
    if state in (UP, UP_PB):
        return "LONG", None
    if state in (DN, DN_PB):
        return "SHORT", None
    if state in (UP_WEAK, DN_WEAK):
        if settings["skip_on_weak"]:
            return None, f"trend {state} (WEAK) — skip"
        return ("LONG" if state == UP_WEAK else "SHORT"), None
    if state == RANGE:
        return None, "RANGE — दिशा नाही ⇒ skip (range-edge entries v1 मध्ये नाहीत)"
    return None, f"trend {state} — skip"


def pick_level(levels, bias, spot, settings):
    """trend-दिशेचा सर्वात जवळचा level: LONG ⇒ spot च्या खालचा/आसपासचा support; SHORT ⇒ वरचा resistance. max_level_distance_pct आत."""
    want = "SUPPORT" if bias == "LONG" else "RESISTANCE"
    out = []
    for z in levels or []:
        try:
            lo, hi = float(z["low"]), float(z["high"])
        except (KeyError, TypeError, ValueError):
            continue
        if settings["require_role_reversal"] and not z.get("role_reversal"):
            continue
        inside = lo <= spot <= hi
        if not (z.get("role") == want or inside):                    # उलट्या भूमिकेचा level कधीच नाही (breakout-entry टाळण्यासाठी)
            continue
        if inside:
            dist = 0.0
        else:
            edge = hi if bias == "LONG" else lo
            dist = (spot - edge) / spot * 100 * (1 if bias == "LONG" else -1)
            if dist < 0 or dist > settings["max_level_distance_pct"]:
                continue
        out.append((dist, z))
    if not out:
        return None
    return min(out, key=lambda x: x[0])[1]


def pullback_quality(df, bias, settings):
    """level कडे येणारा (trend च्या उलट) चालू leg: DANGEROUS ⇒ ❌; require_healthy ⇒ HEALTHY हवा; depth / speed ratio / overlap मर्यादा."""
    if df is None or len(df) < MIN_LEG_BARS:
        return False, "pullback: डेटा अपुरा"
    cfg = LG.LegConfig(**LEG_BASE, r_warn=settings["max_pullback_depth"], r_ok=min(0.5, settings["max_pullback_depth"]))
    legs, swing, internal = LG.build_legs(df, cfg)
    cur = LG.current_leg(df, cfg, legs=legs, swing=swing, internal=internal)
    want_dir = -1 if bias == "LONG" else 1
    lg = cur if (cur is not None and cur.direction == want_dir) else next((x for x in reversed(legs) if x.direction == want_dir), None)
    if lg is None:
        return False, "pullback leg सापडला नाही"
    if lg.role != LG.ROLE_PULLBACK:
        return False, f"level कडे येणारा leg pullback नाही ({lg.role or '—'}{', ' + lg.label if lg.label else ''})"
    f = lg.features
    if lg.label == LG.DANGEROUS_PULLBACK:
        return False, f"pullback DANGEROUS ({' · '.join(lg.reasons)})"
    if settings["require_healthy_pullback"] and lg.label != LG.HEALTHY_PULLBACK:
        return False, f"pullback {lg.label or lg.role} (HEALTHY हवा)"
    depth, sr, ov = f.get("depth"), f.get("speed_ratio"), f.get("overlap")
    if depth is not None and depth > settings["max_pullback_depth"]:
        return False, f"pullback depth {depth:.2f} > {settings['max_pullback_depth']}"
    if sr is not None and sr > settings["max_speed_ratio"]:
        return False, f"speed ratio {sr:.2f} > {settings['max_speed_ratio']}"
    if ov is not None and ov < settings["min_overlap"]:
        return False, f"overlap {ov:.2f} < {settings['min_overlap']}"
    return True, f"{lg.label or lg.role} · depth {depth if depth is not None else '—'} · speed ratio {sr if sr is not None else '—'}"


def approached_from_trend_side(df, lvl, bias, lookback):
    """Pullback = trend च्या बाजूने level कडे येणं: LONG ⇒ मागच्या `lookback` bars पैकी (शेवटचे 3 सोडून) कुठलातरी close zone च्या **वर**;
    SHORT ⇒ खाली. नाहीतर किंमत खालून वर (breakout) आली ⇒ False."""
    c = df["close"].to_numpy(float)
    win = c[-(lookback + 3):-3] if len(c) > 3 else c[:0]
    if not len(win):
        return False
    return bool((win > float(lvl["high"])).any()) if bias == "LONG" else bool((win < float(lvl["low"])).any())


def evaluate_entry(frames, levels, settings, now, spot, expiries=None, chain=None, step=None, lot_size=None, capital=None,
                   open_total=0, open_symbol=0, todays_loss=0.0, full=False):
    """रिटर्न {"ok", "side", "steps": [(नाव, ✅/❌/—, तपशील)], "plan": {...}}. ok = सर्व पायऱ्या ✅ (mode OFF असला तरी गणित होतं — order
    पाठवणं runner चं काम)."""
    steps, plan = [], {"spot": spot}
    failed = [False]

    def add(name, ok, detail):
        if failed[0] and not full:
            steps.append((name, SKIP, ""))
            return
        steps.append((name, OK if ok else FAIL, detail or ""))
        if not ok:
            failed[0] = True

    frames = {tf: completed(df, tf, now) for tf, df in (frames or {}).items() if df is not None}   # no-lookahead: फक्त संपलेले bars
    expiry, ewhy = C.select_expiry(expiries or [], pd.Timestamp(now).date(), settings) if expiries else (None, "expiries नाहीत")
    plan["expiry"] = expiry
    bo, bwhy = C.blackout(now, expiries, settings)
    add("1. Event blackout", not bo, bwhy or "blackout नाही")

    tdf = frames.get(settings["trend_tf"])
    state = trend_state(tdf, settings["trend_tf"]) if tdf is not None and len(tdf) else None
    bias, twhy = bias_of(state, settings) if state else (None, "trend डेटा नाही")
    veto_tf = settings["htf_veto_tf"]
    if bias and veto_tf != "none" and frames.get(veto_tf) is not None and len(frames[veto_tf]):
        vstate = trend_state(frames[veto_tf], veto_tf)
        vb = "LONG" if vstate in (UP, UP_PB, UP_WEAK) else "SHORT" if vstate in (DN, DN_PB, DN_WEAK) else None
        if vb and vb != bias:
            twhy, bias = f"HTF {veto_tf} trend {vstate} उलट — veto", None
    plan["bias"] = bias
    side = "PUT" if bias == "LONG" else "CALL" if bias == "SHORT" else None
    plan["side"] = side
    add("2. Trend", bias is not None, twhy or f"{state} ⇒ {bias} ({'bull put' if bias == 'LONG' else 'bear call'})")

    lvl = pick_level(levels, bias, spot, settings) if bias else None
    plan["level"] = lvl
    add("3. Level", lvl is not None, (f"{lvl['low']:,.1f}–{lvl['high']:,.1f} ({lvl.get('role')}{', role reversal' if lvl.get('role_reversal') else ''})"
                                      if lvl else "trend-दिशेचा योग्य level नाही"))

    ldf = frames.get(settings["level_tf"])
    pq, pwhy = pullback_quality(ldf, bias, settings) if bias else (False, "trend नाही")
    add("4. Pullback quality", pq, pwhy)

    etf = settings["level_tf"] if settings["entry_candle_tf"] == "same" else settings["entry_candle_tf"]
    edf = frames.get(etf)
    rev = None
    if lvl is not None and edf is not None and len(edf):
        ref = lvl["high"] if bias == "LONG" else lvl["low"]
        rev = CA.evaluate_rejection(edf, ref, "BULLISH" if bias == "LONG" else "BEARISH", k=settings["reversal_strength_k"],
                                    min_score=settings["min_rejection_score"], touch_pct=settings["touch_pct"],
                                    max_range_mult=settings["max_range_mult"])
    plan["reversal"] = rev
    add("5. Logical reversal", bool(rev and rev["ok"]),
        (f"score {rev['score']} ({rev.get('label')})" if rev and rev["ok"] else f"reversal नाही ({(rev or {}).get('reason') or 'level/डेटा नाही'})"))

    bdf = frames.get(settings["break_confirm_tf"])
    broke, approached = False, None
    if lvl is not None and bdf is not None and len(bdf):
        broke, _ = C.real_break(bdf.tail(settings["break_lookback_bars"]), float(lvl["low"]), float(lvl["high"]), side, settings)
    if lvl is not None and ldf is not None and len(ldf):
        approached = approached_from_trend_side(ldf, lvl, bias, settings["approach_lookback_bars"])
    gwhy = ("level चा खरा break ⇒ idea रद्द" if broke else
            "किंमत trend च्या बाजूने level कडे आली नाही (breakout/चुकीची दिशा) ⇒ entry नाही" if approached is False else
            "break नाही; किंमत trend च्या बाजूने आली" if approached else "level/डेटा नाही")
    add("6. Breakout guard", (not broke) and bool(approached), gwhy)

    short_k = long_k = None
    if side and step:
        short_k, kwhy = C.short_strike(side, spot, settings, step, level=(lvl["low"] if side == "PUT" else lvl["high"]) if lvl else None, chain=chain)
        if short_k is not None:
            long_k = C.long_strike(side, short_k, settings, step)
    else:
        kwhy = "step/बाजू नाही"
    plan.update(short_k=short_k, long_k=long_k)
    add("7a. Expiry", expiry is not None, ewhy)
    add("7b. Strike", short_k is not None, kwhy if short_k is None else f"short {short_k:g} / long {long_k:g}")

    credit = width = None
    if short_k is not None and chain is not None and len(chain):
        opt = "PE" if side == "PUT" else "CE"
        ltp = {(float(r.strike), r.type): r.ltp for r in chain.itertuples(index=False)}
        credit, width, cwhy = C.credit_check(ltp.get((short_k, opt)), ltp.get((long_k, opt)), short_k, long_k, settings)
    else:
        cwhy = "option chain नाही"
    plan.update(credit=credit, width=width)
    add("7c. Credit", cwhy is None, cwhy or f"credit {credit:.2f} / width {width:g}")

    lots = per_lot = None
    if credit is not None and width and lot_size and capital:
        lots, per_lot, lwhy = C.lots_for(capital, credit, width, lot_size, settings, event_day=C.is_event_day(now, settings))
    else:
        lwhy = "credit/lot size/capital नाही"
    cap_ok, capwhy = C.capacity_ok(open_total, open_symbol, todays_loss, settings)
    plan.update(lots=lots, max_loss=(per_lot * lots if per_lot and lots else None))
    add("8. Risk / size", bool(lots) and cap_ok, capwhy or lwhy or f"{lots} lots · max loss ₹{per_lot * lots:,.0f}")

    ok = all(s[1] == OK for s in steps)
    return {"ok": ok, "side": side, "steps": steps, "plan": plan}
