"""
pullback_credit_spread/preview.py
---------------------------------
🎓 Dashboard चा "आत्ता signal आला तर" live preview — **फक्त वाचन, order नाही**. दोन स्रोत:
  • live    — Upstox (token असेल तर): candles, instrument master expiries, option chain (LTP + delta), spot.
  • offline — NIFTY offline 1M डेटा (2015 → 2024-03; holdout नाही) निवडलेल्या वेळी; expiries = त्या आठवड्यांचे गुरुवार-नियम (अंदाज);
              premium = Black-Scholes model (IV ≈ σ20 वार्षिक) — **अंदाज** म्हणून स्पष्ट लेबल.
दोन्हीमध्ये तोच `signal.evaluate_entry` (एकच code).
"""
import math

import numpy as np
import pandas as pd

from . import levels_source as LS
from . import signal as SG
from .settings import tf_minutes

RULE = {"5m": "5min", "15m": "15min", "30m": "30min", "1h": "60min", "4h": "240min", "1d": "1D"}
LOT_FALLBACK = {"NIFTY": 75, "BANKNIFTY": 35, "SENSEX": 20}
STEP_FALLBACK = {"NIFTY": 50, "BANKNIFTY": 100, "SENSEX": 100}


def needed_tfs(settings):
    tfs = {settings["trend_tf"], settings["level_tf"], settings["break_confirm_tf"], "1d"}
    if settings["htf_veto_tf"] != "none":
        tfs.add(settings["htf_veto_tf"])
    if settings["entry_candle_tf"] != "same":
        tfs.add(settings["entry_candle_tf"])
    return sorted(tfs, key=tf_minutes)


# ---------------------------------------------------------------------------------------------------------------------
# premium model (offline / backtest) — Black-Scholes, r = 0
# ---------------------------------------------------------------------------------------------------------------------
def _ncdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bs(spot, strike, t_years, iv, opt):
    """(price, delta). t ≤ 0 ⇒ intrinsic."""
    if t_years <= 0 or iv <= 0:
        intr = max(spot - strike, 0.0) if opt == "CE" else max(strike - spot, 0.0)
        return intr, (1.0 if intr > 0 else 0.0) * (1 if opt == "CE" else -1)
    v = iv * math.sqrt(t_years)
    d1 = (math.log(spot / strike) + 0.5 * v * v) / v
    d2 = d1 - v
    if opt == "CE":
        return spot * _ncdf(d1) - strike * _ncdf(d2), _ncdf(d1)
    return strike * _ncdf(-d2) - spot * _ncdf(-d1), _ncdf(d1) - 1


def years_to_expiry(now, expiry):
    """trading-वर्ष (252) मध्ये: आजच्या उरलेल्या सत्राचा भाग + मधले पूर्ण trading दिवस + expiry दिवसाचं सत्र — σ20×√252 शी सुसंगत."""
    now, exp = pd.Timestamp(now), pd.Timestamp(expiry)
    sess = 375.0                                                     # 09:15–15:30 मिनिटं
    rem_today = min(max((now.normalize() + pd.Timedelta(hours=15, minutes=30) - now).total_seconds() / 60, 0), sess) / sess
    if exp.normalize() == now.normalize():
        return rem_today / 252
    mid = max(int(np.busday_count(now.date() + pd.Timedelta(days=1), exp.date())), 0)
    return (rem_today + mid + 1) / 252


def model_chain(spot, step, expiry, now, iv, n=40):
    """spot भोवती ±n strikes चा model chain: DataFrame [strike, type, ltp, delta]. T = trading-वर्षांत (years_to_expiry)."""
    t = years_to_expiry(now, expiry)
    atm = round(spot / step) * step
    rows = []
    for k in (atm + step * i for i in range(-n, n + 1)):
        for opt in ("CE", "PE"):
            p, d = bs(spot, k, t, iv, opt)
            rows.append((float(k), opt, round(max(p, 0.05), 2), round(d, 3)))
    return pd.DataFrame(rows, columns=["strike", "type", "ltp", "delta"])


def weekly_thursdays(day, n=6):
    """offline अंदाज: पुढचे n गुरुवार (instrument master उपलब्ध नसल्याने — live मध्ये master वापरतो)."""
    d = pd.Timestamp(day).normalize()
    first = d + pd.Timedelta(days=(3 - d.weekday()) % 7)
    return [(first + pd.Timedelta(weeks=i)).date() for i in range(n)]


# ---------------------------------------------------------------------------------------------------------------------
# offline
# ---------------------------------------------------------------------------------------------------------------------
def nifty_lot_size(day):
    """offline preview साठी अंदाजे ऐतिहासिक NIFTY lot (वापरकर्ता preview मध्ये बदलू शकतो): 2015-11 पूर्वी 25, 2021-07 → 2024-04 = 50,
    अन्यथा 75."""
    d = pd.Timestamp(day)
    if d < pd.Timestamp("2015-11-01"):
        return 25
    return 50 if pd.Timestamp("2021-07-01") <= d < pd.Timestamp("2024-04-26") else 75


def offline_inputs(df1m, asof, settings):
    """NIFTY 1M (holdout-cut) → asof पर्यंतचे पूर्ण frames, spot, σ20 IV, model chain, अंदाजे expiries."""
    asof = pd.Timestamp(asof)
    d = df1m[df1m["timestamp"] < asof]
    d = d[d["timestamp"] >= asof - pd.Timedelta(days=400)]
    if d.empty:
        return None
    spot = float(d["close"].iloc[-1])
    frames = {}
    for tf in needed_tfs(settings):
        kw = {} if tf == "1d" else {"origin": "start_day", "offset": "9h15min"}          # NSE सत्र 09:15 पासून (Upstox सारखे bins)
        r = d.set_index("timestamp")[["open", "high", "low", "close"]].resample(RULE[tf], label="left", closed="left", **kw).agg(
            {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna().reset_index()
        frames[tf] = SG.completed(r, tf, asof)
    daily = frames.get("1d")
    lr = np.diff(np.log(daily["close"].to_numpy(float))) if daily is not None and len(daily) > 21 else np.array([])
    iv = float(np.std(lr[-20:], ddof=1) * math.sqrt(252)) if len(lr) >= 20 else 0.15
    expiries = weekly_thursdays(asof, n=10)                         # monthly + मोठा min_dte साठी पुरेसे आठवडे
    return {"frames": frames, "spot": spot, "iv": iv, "expiries": expiries, "step": STEP_FALLBACK["NIFTY"], "lot_size": nifty_lot_size(asof)}


def run_preview(inputs, settings, capital, now, chain=None, open_total=0, open_symbol=0, todays_loss=0.0):
    """inputs (offline_inputs / live) → evaluate_entry(full=True) + levels. chain नसेल तर निवडलेल्या expiry साठी model chain."""
    levels, lwhy = LS.get_levels(settings["level_engine"], inputs["frames"], settings["level_tf"], inputs["spot"])
    from . import core as C
    expiry, _ = C.select_expiry(inputs["expiries"], pd.Timestamp(now).date(), settings)
    model = False
    if chain is None and expiry is not None:
        chain, model = model_chain(inputs["spot"], inputs["step"], expiry, now, inputs.get("iv") or 0.15), True
    r = SG.evaluate_entry(inputs["frames"], levels, settings, now, inputs["spot"], expiries=inputs["expiries"], chain=chain,
                          step=inputs["step"], lot_size=inputs["lot_size"], capital=capital, open_total=open_total,
                          open_symbol=open_symbol, todays_loss=todays_loss, full=True)
    r["levels"], r["levels_note"], r["model_premium"] = levels, lwhy, model
    sides = [r["side"]] if r["side"] else ["PUT", "CALL"]                 # trend नसेल तर दोन्ही बाजूंचा "signal आला तर" अंदाज
    r["hypothetical"] = [hypothetical_plan(sd, inputs, settings, levels, chain, expiry, capital, now) for sd in sides]
    return r


def hypothetical_plan(side, inputs, settings, levels, chain, expiry, capital, now):
    """"आत्ता या बाजूने signal आला तर": जवळचा level, short/long strike, credit, max loss, lots — checklist शिवाय (फक्त माहिती)."""
    from . import core as C
    spot, step = inputs["spot"], inputs["step"]
    lvl = SG.pick_level(levels, "LONG" if side == "PUT" else "SHORT", spot, settings)
    out = {"side": side, "label": "Bull put" if side == "PUT" else "Bear call", "expiry": expiry, "level": lvl}
    k, why = C.short_strike(side, spot, settings, step, level=(lvl["low"] if side == "PUT" else lvl["high"]) if lvl else None, chain=chain)
    out.update(short_k=k, note=why)
    if k is None:
        return out
    lk = C.long_strike(side, k, settings, step)
    out["long_k"] = lk
    if chain is not None and len(chain):
        opt = "PE" if side == "PUT" else "CE"
        ltp = {(float(x.strike), x.type): x.ltp for x in chain.itertuples(index=False)}
        credit, width, cwhy = C.credit_check(ltp.get((k, opt)), ltp.get((lk, opt)), k, lk, settings)
        out.update(credit=credit, width=width, credit_note=cwhy)
        if credit is not None and width:
            lots, per_lot, lwhy = C.lots_for(capital, credit, width, inputs["lot_size"], settings, event_day=C.is_event_day(now, settings))
            out.update(lots=lots, max_loss=per_lot * max(lots, 1), max_loss_per_lot=per_lot, lots_note=lwhy)
    return out
