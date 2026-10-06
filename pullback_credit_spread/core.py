"""
pullback_credit_spread/core.py
------------------------------
🎓 शुद्ध (network/DB नाही) निर्णय-functions: expiry निवड, strike step, short/long strike (5 modes + guards), credit तपासणी, lots, आणि exit नियम.
सर्व संख्या `settings` मधून (settings.validate ने पूर्ण केलेला dict). Side: "PUT" = bull put (uptrend; strike spot च्या खाली),
"CALL" = bear call (downtrend; strike वर).
"""
import datetime as dt
import math

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------------------------------------------------
# expiry
# ---------------------------------------------------------------------------------------------------------------------
def _d(x):
    return pd.Timestamp(x).date()


def monthly_expiries(expiries):
    """प्रत्येक महिन्यातली शेवटची expiry (instrument master च्या तारखांवरून — वार गृहीत नाही)."""
    by_month = {}
    for e in sorted(_d(x) for x in expiries):
        by_month[(e.year, e.month)] = e
    return sorted(by_month.values())


def select_expiry(expiries, today, settings):
    """instrument master च्या expiries मधून: आज expiry असेल तर नेहमी पुढची; (expiry − आज) दिवस < min_dte ⇒ पुढची. monthly ⇒ महिन्याची शेवटची.
    रिटर्न (date, कारण) किंवा (None, कारण)."""
    today = _d(today)
    ex = sorted(_d(x) for x in expiries if _d(x) >= today)
    if settings["expiry_type"] == "monthly":
        ex = [e for e in monthly_expiries(expiries) if e >= today]
    for e in ex:
        if e == today:
            continue
        if (e - today).days < settings["min_dte"]:
            continue
        return e, f"{e:%d %b} ({(e - today).days} दिवस)"
    return None, "योग्य expiry सापडली नाही"


# ---------------------------------------------------------------------------------------------------------------------
# strikes
# ---------------------------------------------------------------------------------------------------------------------
def strike_step(strikes, fallback=None):
    """instrument master / chain मधल्या strikes वरून step (सर्वात लहान सामान्य अंतर). strikes नाहीत ⇒ fallback."""
    s = sorted({float(x) for x in strikes or []})
    if len(s) < 3:
        return fallback
    diffs = np.diff(s)
    diffs = diffs[diffs > 0]
    if not len(diffs):
        return fallback
    vals, counts = np.unique(np.round(diffs, 4), return_counts=True)
    return float(vals[np.argmax(counts)]) if counts.max() > 1 else float(diffs.min())


def round_far(price, step, side):
    """सुरक्षित बाजूला गोल: PUT ⇒ खाली (दूर), CALL ⇒ वर (दूर)."""
    n = price / step
    return float((math.floor(n + 1e-9) if side == "PUT" else math.ceil(n - 1e-9)) * step)


def _far(a, b, side):
    return min(a, b) if side == "PUT" else max(a, b)


def _dist_pct(strike, spot):
    return abs(strike - spot) / spot * 100


def short_strike(side, spot, settings, step, level=None, chain=None):
    """mode नुसार short strike; मग guards: min_distance_pct (कमी असेल तर दूर ढकलतो), max_distance_pct (ओलांडल्यास entry नाही).
    chain: DataFrame [strike, type ("CE"/"PE"), ltp, delta] (delta/premium modes साठी). रिटर्न (strike, None) किंवा (None, कारण)."""
    mode = settings["strike_mode"]
    sgn = -1 if side == "PUT" else 1
    opt = "PE" if side == "PUT" else "CE"
    if mode == "beyond_level":
        if level is None:
            return None, "level नाही (beyond_level)"
        if settings.get("beyond_level_unit", "pct") == "points":
            raw = level + sgn * settings["beyond_level_buffer_points"]
        else:
            raw = level * (1 + sgn * settings["beyond_level_buffer_pct"] / 100)
        if (raw - spot) * sgn <= 0:
            return None, f"level {level:g} spot च्या चुकीच्या बाजूला (beyond_level)"
    elif mode == "distance_pct":
        raw = spot * (1 + sgn * settings["distance_pct"] / 100)
    elif mode == "strikes_otm":
        atm = round(spot / step) * step
        raw = atm + sgn * settings["strikes_otm"] * step
    elif mode in ("delta", "premium"):
        if chain is None or not len(chain):
            return None, f"option chain नाही ({mode})"
        c = chain[(chain["type"] == opt) & ((chain["strike"] - spot) * sgn > 0)].copy()
        if mode == "delta":
            c = c[c["delta"].notna()]
            if not len(c):
                return None, "delta माहिती नाही"
            c["err"] = (c["delta"].abs() - settings["target_delta"]).abs()
        else:
            c = c[c["ltp"].notna() & (c["ltp"] > 0)]
            if not len(c):
                return None, "premium माहिती नाही"
            c["err"] = (c["ltp"] - settings["target_premium"]).abs()
        best = c.sort_values(["err", "strike"], ascending=[True, sgn < 0]).iloc[0]       # बरोबरी ⇒ दूरचा (सुरक्षित) strike
        raw = float(best["strike"])
    else:
        return None, f"अज्ञात mode {mode}"
    k = round_far(raw, step, side)
    min_k = round_far(spot * (1 + sgn * settings["min_distance_pct"] / 100), step, side)
    if _dist_pct(k, spot) < settings["min_distance_pct"]:
        k = _far(k, min_k, side)
    if (k - spot) * sgn <= 0:
        return None, "strike spot च्या चुकीच्या बाजूला"
    if _dist_pct(k, spot) > settings["max_distance_pct"]:
        return None, f"strike {k:g} spot पासून {_dist_pct(k, spot):.2f}% > कमाल {settings['max_distance_pct']}%"
    return k, None


def long_strike(side, short_k, settings, step):
    w = settings["width_points"] if settings["width_mode"] == "points" else settings["width_strikes"] * step
    w = max(step, math.ceil(w / step - 1e-9) * step)
    return short_k - w if side == "PUT" else short_k + w


def credit_check(short_ltp, long_ltp, short_k, long_k, settings):
    """net credit (प्रति unit) आणि guards. रिटर्न (credit, width, कारण|None)."""
    if short_ltp is None or long_ltp is None:
        return None, abs(short_k - long_k), "premium माहिती नाही"
    credit = float(short_ltp) - float(long_ltp)
    width = abs(short_k - long_k)
    if credit < settings["min_credit"]:
        return credit, width, f"credit {credit:.2f} < किमान {settings['min_credit']}"
    if width > 0 and credit / width < settings["min_credit_to_width_ratio"]:
        return credit, width, f"credit/width {credit / width:.3f} < किमान {settings['min_credit_to_width_ratio']}"
    return credit, width, None


# ---------------------------------------------------------------------------------------------------------------------
# risk
# ---------------------------------------------------------------------------------------------------------------------
def lots_for(capital, credit, width, lot_size, settings, event_day=False):
    """Lots = floor(capital × risk% ÷ प्रति lot max loss); max_lots cap; event दिवशी × गुणक. रिटर्न (lots, max_loss_per_lot, कारण|None)."""
    max_loss_unit = max(width - credit, 0.0)
    per_lot = max_loss_unit * lot_size
    if per_lot <= 0:
        return 0, per_lot, "max loss शून्य/अवैध"
    lots = math.floor(capital * settings["risk_per_trade_pct"] / 100 / per_lot)
    if event_day:
        lots = math.floor(lots * settings["event_day_size_multiplier"])
    lots = min(lots, settings["max_lots"])
    return (lots, per_lot, None) if lots >= 1 else (0, per_lot, "धोका-मर्यादेत एकही lot बसत नाही")


def capacity_ok(open_total, open_symbol, todays_loss, settings):
    if open_total >= settings["max_open_spreads"]:
        return False, f"एकूण उघडे spreads {open_total} ≥ {settings['max_open_spreads']}"
    if open_symbol >= settings["max_open_spreads_per_symbol"]:
        return False, f"या symbol चे उघडे spreads {open_symbol} ≥ {settings['max_open_spreads_per_symbol']}"
    if todays_loss >= settings["daily_loss_cap"] > 0:
        return False, f"आजचा तोटा ₹{todays_loss:,.0f} ≥ मर्यादा ₹{settings['daily_loss_cap']:,.0f}"
    return True, None


# ---------------------------------------------------------------------------------------------------------------------
# events
# ---------------------------------------------------------------------------------------------------------------------
def _hhmm(s):
    hh, mm = (int(x) for x in s.split(":"))
    return dt.time(hh, mm)


def blackout(now, expiries, settings):
    """नवीन entry साठी blackout? (bool, कारण). Exits वर परिणाम नाही. `expiries` = instrument master च्या सर्व expiry तारखा (आज expiry
    असेल तर सकाळी blackout — निवडलेली expiry कधीच आजची नसते, म्हणून सर्व यादी तपासतो). Event दिवशी फक्त start–end window."""
    if not settings["event_blackout_enabled"]:
        return False, None
    now = pd.Timestamp(now)
    if is_event_day(now, settings):
        a, b = settings["event_blackout_start"], settings["event_blackout_end"]
        if (not a or now.time() >= _hhmm(a)) and (not b or now.time() < _hhmm(b)):
            return True, f"event दिवस {now:%d %b} ({a}–{b})"
    until = settings["blackout_expiry_morning_until"]
    if until and any(_d(e) == now.date() for e in (expiries or [])) and now.time() < _hhmm(until):
        return True, f"आज expiry — सकाळ ({until} पर्यंत)"
    return False, None


def is_event_day(now, settings):
    days = {x.strip() for x in str(settings["event_dates"] or "").split(",") if x.strip()}
    return pd.Timestamp(now).strftime("%Y-%m-%d") in days


# ---------------------------------------------------------------------------------------------------------------------
# exits
# ---------------------------------------------------------------------------------------------------------------------
def real_break(bars, level_lo, level_hi, side, settings):
    """confirm-TF च्या **पूर्ण** bars वर level चा खरा break? side PUT (support खाली तुटणं) / CALL (resistance वर).
    खरा break = आधी योग्य बाजूला असलेली किंमत दूरची कड ± break_buffer पलीकडे close ने ओलांडते, आणि त्यानंतरचे no_reclaim_bars सलग closes आत परत
    आले नाहीत. नाहीतर (परत आत close) =
    false break ⇒ exit नाही. रिटर्न (bool, कारण)."""
    if bars is None or not len(bars):
        return False, None
    c = bars["close"].to_numpy(float)
    buf = settings["break_buffer_pct"] / 100
    n = settings["no_reclaim_bars"]
    if side == "PUT":
        thr = level_lo * (1 - buf)
        beyond, inside = c < thr, c >= level_lo
    else:
        thr = level_hi * (1 + buf)
        beyond, inside = c > thr, c <= level_hi
    idx = [i for i in np.where(beyond)[0] if i > 0 and not beyond[i - 1]]      # फक्त ओलांडण्याचा क्षण (आधी आत/योग्य बाजूला होता)
    for i in idx:
        after = inside[i + 1:i + 1 + n]
        if len(after) >= n and not after.any():
            return True, f"level {level_lo:g}–{level_hi:g} चा खरा break ({n} bars reclaim नाही)"
    return False, None


def exit_decision(pos, spread_price, spot, now, settings, break_bars=None):
    """उघड्या spread साठी exit? pos: {side, short_k, credit, expiry, level_lo, level_hi}. क्रम: hard stop (logic काहीही असो) → profit target →
    spot stop → real break → time exit. रिटर्न (reason|None, detail)."""
    credit = pos["credit"]
    if spread_price is not None and credit > 0 and spread_price >= settings["hard_stop_credit_multiple"] * credit:
        return "HARD_STOP", f"spread {spread_price:.2f} ≥ {settings['hard_stop_credit_multiple']}× credit {credit:.2f}"
    if spread_price is not None and credit > 0 and (credit - spread_price) >= settings["profit_target_pct_of_credit"] / 100 * credit:
        return "TARGET", f"नफा {credit - spread_price:.2f} ≥ {settings['profit_target_pct_of_credit']}% credit"
    sd = settings["spot_stop_distance_pct"]
    if sd > 0 and spot is not None:
        gap = (spot - pos["short_k"]) / pos["short_k"] * 100 * (1 if pos["side"] == "PUT" else -1)
        if gap <= sd:
            return "SPOT_STOP", f"spot short strike पासून {gap:.2f}% (≤ {sd}%)"
    if settings["real_break_exit"] and pos.get("level_lo") is not None:
        bb = break_bars
        if bb is not None and len(bb) and pos.get("entry_time") is not None and "timestamp" in bb.columns:
            bb = bb[pd.to_datetime(bb["timestamp"]) >= pd.Timestamp(pos["entry_time"])]     # entry नंतरचेच bars
        ok, why = real_break(bb, pos["level_lo"], pos["level_hi"], pos["side"], settings)
        if ok:
            return "REAL_BREAK", why
    if pos.get("expiry") is not None:
        now = pd.Timestamp(now)
        if now.date() > _d(pos["expiry"]):
            return "TIME_EXIT", "expiry उलटून गेली (वेळ-exit चुकला)"
        if settings["time_exit"] and now.date() == _d(pos["expiry"]) and now.time() >= _hhmm(settings["time_exit"]):
            return "TIME_EXIT", f"expiry दिवस {settings['time_exit']}"
    return None, None
