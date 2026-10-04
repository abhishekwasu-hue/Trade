"""opportunity_engine/positional.py — Positional mode (spec §9, §12): EOD ला Structure Journal वरून पुढच्या session साठी credit-spread **सूचना** आणि
index-level backtest (hold 5 दिवस: expiry-close win % आणि touch %). कुठलाही order नाही; option premium/IV चा हिशोब नाही (फक्त index किंमत).

🎓 नियम:
  • Daily आणि 4H दोन्ही UPTREND (UPTREND/UPTREND_PULLBACK) ⇒ BULL_PUT · दोन्ही DOWNTREND ⇒ BEAR_CALL · दोन्ही RANGE ⇒ IRON_CONDOR.
    दोन्हीपैकी कुठलाही WEAK ⇒ नवीन spread नाही, फक्त "आधीचा spread adjust करा" alert. INIT / Daily-4H मतभेद ⇒ सूचना नाही.
  • Short strike: किंमतीच्या त्या बाजूचा सर्वात जवळचा anchor — HTF (Daily/4H) protected level, FRESH demand/supply zone (1H/4H/Daily) चा बाहेरचा किनारा,
    RANGE मध्ये range कड — त्याच्या पलीकडे `pos_strike_buffer_adr × ADR`, आणि किंमतीपासून दूर round (`cloud_db.STRIKE_STEP`).
  • Hedge (long) strike: short पासून `pos_hedge_steps` strikes आणखी दूर.
"""
import math
import numpy as np
import pandas as pd

from .context import is_weak, trend_sign

STRIKE_STEP = {"NIFTY": 50, "BANKNIFTY": 100, "SENSEX": 100}      # cloud_db.STRIKE_STEP ची प्रत (package मध्ये DB import नको — guard test); test ने दोन्ही जुळतात हे तपासलं
ZONE_TFS = ("1h", "4h", "1d")
STRATEGY_TEXT = {"BULL_PUT": "Bull Put spread", "BEAR_CALL": "Bear Call spread", "IRON_CONDOR": "Iron Condor"}


def strike_step(symbol):
    return STRIKE_STEP.get(symbol, 50)


def _anchors(ctx, price, side):
    """side −1 = किंमतीखालचे (put), +1 = वरचे (call). रिटर्न [(price, कारण)]."""
    out = []
    for tf in ("1d", "4h"):
        st = ctx.get(tf)
        if st is None:
            continue
        if st.protected is not None and (st.protected - price) * side > 0:
            out.append((float(st.protected), f"{tf.upper()} protected {st.protected:,.0f}"))
        edge = st.range_low if side < 0 else st.range_high
        if st.state == "RANGE" and edge is not None and (edge - price) * side > 0:
            out.append((float(edge), f"{tf.upper()} range {'low' if side < 0 else 'high'} {edge:,.0f}"))
    kinds = ("DEMAND", "SUPPORT") if side < 0 else ("SUPPLY", "RESISTANCE")
    for lv in ctx.levels:
        if lv.get("tf") not in ZONE_TFS or lv.get("kind") not in kinds or lv.get("freshness") != "FRESH" or lv.get("status") == "BROKEN" \
                or lv.get("reject_reason"):
            continue
        edge = float(lv.get("outer_low", lv["low"])) if side < 0 else float(lv.get("outer_high", lv["high"]))
        if (edge - price) * side > 0:
            out.append((edge, f"{lv['tf'].upper()} FRESH {lv['kind']} {lv['low']:,.0f}–{lv['high']:,.0f}"))
    return out


def _strike(anchor, side, adr, step, cfg):
    raw = anchor + side * cfg.pos_strike_buffer_adr * adr
    return int(math.floor(raw / step) * step) if side < 0 else int(math.ceil(raw / step) * step)


def _leg(ctx, price, side, adr, step, cfg):
    anchors = _anchors(ctx, price, side)
    if not anchors:
        return None
    anchor, why = min(anchors, key=lambda a: abs(a[0] - price))       # सर्वात जवळचा आधार (पहिली संरक्षक भिंत)
    short = _strike(anchor, side, adr, step, cfg)
    return {"short": short, "long": short + side * cfg.pos_hedge_steps * step, "anchor": anchor, "anchor_reason": why,
            "distance_adr": round(abs(short - price) / adr, 2)}


def suggest(ctx, price, cfg, symbol="NIFTY", adr=None, step=None):
    """Context (EOD) -> सूचना dict: strategy (BULL_PUT/BEAR_CALL/IRON_CONDOR/None), put/call legs, reasons (मराठी), alert."""
    adr = float(adr if adr is not None else ctx.adr)
    step = int(step or strike_step(symbol))
    d, h4 = ctx.get("1d"), ctx.get("4h")
    out = {"symbol": symbol, "price": float(price), "strategy": None, "put": None, "call": None, "alert": None, "reasons": [],
           "state_1d": d.state if d else None, "state_4h": h4.state if h4 else None, "adr": adr, "step": step}
    if d is None or h4 is None or "INIT" in (d.state, h4.state):
        out["reasons"].append("Daily/4H structure अजून तयार नाही — सूचना नाही")
        return out
    if not np.isfinite(adr) or adr <= 0:
        out["reasons"].append("ADR उपलब्ध नाही — सूचना नाही")
        return out
    if is_weak(d.state) or is_weak(h4.state):
        out["alert"] = (f"Daily {d.state}, 4H {h4.state} — WEAK: नवीन positional spread नको; आधीचा spread असेल तर धोक्याच्या बाजूचा leg adjust/कमी करा")
        out["reasons"].append("WEAK state")
        return out
    sd, s4 = trend_sign(d.state), trend_sign(h4.state)
    if sd > 0 and s4 > 0:
        out["strategy"] = "BULL_PUT"
    elif sd < 0 and s4 < 0:
        out["strategy"] = "BEAR_CALL"
    elif d.state == "RANGE" and h4.state == "RANGE":
        out["strategy"] = "IRON_CONDOR"
    else:
        out["reasons"].append(f"Daily {d.state} आणि 4H {h4.state} — मतभेद, सूचना नाही")
        return out
    if out["strategy"] in ("BULL_PUT", "IRON_CONDOR"):
        out["put"] = _leg(ctx, price, -1, adr, step, cfg)
    if out["strategy"] in ("BEAR_CALL", "IRON_CONDOR"):
        out["call"] = _leg(ctx, price, 1, adr, step, cfg)
    need = {"BULL_PUT": ("put",), "BEAR_CALL": ("call",), "IRON_CONDOR": ("put", "call")}[out["strategy"]]
    if any(out[k] is None for k in need):
        out["reasons"].append("त्या बाजूला protected level / FRESH zone सापडला नाही — strike ठरवता येत नाही")
        out["strategy"] = None
        return out
    out["reasons"].append(f"Daily {d.state}, 4H {h4.state} ⇒ {STRATEGY_TEXT[out['strategy']]}")
    return out


def suggestion_text(s):
    """Telegram/page साठी एक-दोन ओळी."""
    head = f"📐 {s['symbol']} positional (पुढचा session):"
    if s.get("alert"):
        return f"{head} ⚠️ {s['alert']}"
    if not s.get("strategy"):
        return f"{head} सूचना नाही — " + "; ".join(s.get("reasons") or [])
    parts = [f"{head} {STRATEGY_TEXT[s['strategy']]}"]
    if s.get("put"):
        p = s["put"]
        parts.append(f"Sell {p['short']} PE / Buy {p['long']} PE ({p['anchor_reason']} खाली, {p['distance_adr']} ADR दूर)")
    if s.get("call"):
        c = s["call"]
        parts.append(f"Sell {c['short']} CE / Buy {c['long']} CE ({c['anchor_reason']} वर, {c['distance_adr']} ADR दूर)")
    return " · ".join(parts) + " — फक्त सूचना, order नाही."


# ---------------------------------------------------------------------------------------------------------------------
# Backtest (index-level): सूचना D दिवसाच्या open आधी (= D−1 EOD, as-of journal), hold `pos_hold_days` sessions (D … D+4)
# ---------------------------------------------------------------------------------------------------------------------
def backtest(tl, cfg, symbol="NIFTY"):
    """Timeline -> DataFrame (प्रत्येक दिवसाची सूचना + निकाल): touch = hold दरम्यान किंमत short strike ला पोहोचली; win = शेवटच्या दिवसाचा close
    short strike च्या सुरक्षित बाजूला (expiry-close proxy). IS/OOS विभागणी `summary()` करतो."""
    rows = []
    days = tl.days
    hold = int(cfg.pos_hold_days)
    step = STRIKE_STEP.get(symbol, 50)
    for i, day in enumerate(days):
        if i + hold > len(days):
            break
        price = float(day.info.pdc)                                     # D−1 चा close (EOD सूचनेची किंमत)
        ctx = tl.context(day.open_t, day, price)
        s = suggest(ctx, price, cfg, symbol, adr=day.adr, step=step)
        if not s["strategy"]:
            continue
        span = days[i:i + hold]
        lo = min(float(np.min(d.l)) for d in span)
        hi = max(float(np.max(d.h)) for d in span)
        last_close = float(span[-1].c[-1])
        row = {"date": day.date, "strategy": s["strategy"], "price": price, "state_1d": s["state_1d"], "state_4h": s["state_4h"],
               "put_short": None, "call_short": None, "touch": False, "win": True, "exit_date": span[-1].date, "last_close": last_close}
        if s["put"]:
            row["put_short"] = s["put"]["short"]
            row["put_dist_adr"] = s["put"]["distance_adr"]
            row["touch"] = row["touch"] or lo <= s["put"]["short"]
            row["win"] = row["win"] and last_close > s["put"]["short"]
        if s["call"]:
            row["call_short"] = s["call"]["short"]
            row["call_dist_adr"] = s["call"]["distance_adr"]
            row["touch"] = row["touch"] or hi >= s["call"]["short"]
            row["win"] = row["win"] and last_close < s["call"]["short"]
        rows.append(row)
    return pd.DataFrame(rows)


def summary(df, is_end=pd.Timestamp("2021-12-31")):
    """strategy × (IS / OOS) : सूचना, win %, touch % — IS आणि OOS वेगळे."""
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=["period", "strategy", "n", "win_pct", "touch_pct"])
    d = df.copy()
    d["period"] = np.where(pd.to_datetime(d["date"]) <= is_end, "IS 2015→2021", "OOS 2022→")
    g = d.groupby(["period", "strategy"]).agg(n=("win", "size"), win_pct=("win", "mean"), touch_pct=("touch", "mean")).reset_index()
    g["win_pct"] = (g["win_pct"] * 100).round(1)
    g["touch_pct"] = (g["touch_pct"] * 100).round(1)
    return g

