"""
mcx_filters.py
----------------
🎓 MCX Futures Trader चे entry filters — शुद्ध functions (DB/network नाही), जेणेकरून replay (mcx_trade_replay.py) आणि bot
(mcx_futures_trader.py, टप्पा 1) **तंतोतंत तेच** नियम वापरतील. संदर्भ: GOLD 22 Sep–1 Oct च्या 9 PAPER trades पैकी 6 LONG पडत्या
बाजारात support touch वर घेतले गेले आणि सर्व SL झाले.

  • supertrend_block(mode, …): "off" | "both_against" (1H आणि 4H दोन्ही विरुद्ध ⇒ block — जुना नियम) | "htf_against" (4H विरुद्ध ⇒ block).
  • sl_cooldown_block(…): त्या symbol वर SL/trailing-SL **तोट्याने** बंद झालेल्या trade नंतर `minutes` (60) मिनिटं नवीन entry नाही.
  • sl_level_direction_block(…): ज्या level वर आज SL (तोटा) लागला, त्या level वर आज त्याच दिशेने entry नाही (Multi-Hit max-2 पेक्षा वेगळा).
  • cascade_block(…) — "broken-support cascade" (pure price action, 30M): मागच्या 2 MCX sessions मध्ये 30M **close** ने तुटलेल्या
    support (confirmed 30M swing low) च्या खालच्या level वर LONG फक्त 30M bullish CHoCH नंतर — break नंतरचा शेवटचा lower-high
    (confirmed swing high) 30M close ने वर तुटला असेल तर. Resistance साठी उलट.
सर्व functions फक्त दिलेले (आधीच "entry आधी पूर्ण झालेले") bars पाहतात — no-lookahead caller ची जबाबदारी.
"""
import pandas as pd

from price_action import candles as PA
from signals import find_swings

SUPERTREND_MODES = ("off", "both_against", "htf_against")


def effective_supertrend_mode(settings):
    """settings -> supertrend_filter_mode ("off"/"both_against"/"htf_against"). जुनी सेटिंग entry_supertrend_filter_enabled=True आणि mode "off"
    असेल तर "both_against" (आधीचं वर्तन जसंच्या तसं). अनोळखी मूल्य ⇒ "off"."""
    mode = settings.get("supertrend_filter_mode", "off")
    if mode not in SUPERTREND_MODES:
        mode = "off"
    if mode == "off" and settings.get("entry_supertrend_filter_enabled", False):
        mode = "both_against"
    return mode


def supertrend_block(mode, direction, dir_1h, dir_4h):
    """रिटर्न (blocked, कारण). डेटा नसेल (None) ⇒ block नाही (fail-open, जुन्या gate प्रमाणे)."""
    if mode == "both_against":
        if dir_1h is None or dir_4h is None:
            return False, None
        if direction == "BULLISH" and dir_1h == "BEARISH" and dir_4h == "BEARISH":
            return True, "1H आणि 4H दोन्ही Supertrend BEARISH — Bullish trade थांबवला"
        if direction == "BEARISH" and dir_1h == "BULLISH" and dir_4h == "BULLISH":
            return True, "1H आणि 4H दोन्ही Supertrend BULLISH — Bearish trade थांबवला"
        return False, None
    if mode == "htf_against":
        if dir_4h is None:
            return False, None
        if direction == "BULLISH" and dir_4h == "BEARISH":
            return True, "4H Supertrend BEARISH (मोठा trend खाली) — Bullish trade थांबवला"
        if direction == "BEARISH" and dir_4h == "BULLISH":
            return True, "4H Supertrend BULLISH (मोठा trend वर) — Bearish trade थांबवला"
        return False, None
    return False, None


def _is_sl_loss(t):
    return "SL" in str(t.get("exit_reason") or "").upper() and (t.get("realized_pnl") is not None and float(t["realized_pnl"]) < 0)


def sl_cooldown_block(prior_trades, now, minutes=60):
    """prior_trades: त्याच symbol चे बंद trades [{exit_time, exit_reason, realized_pnl, …}]. रिटर्न (blocked, कारण)."""
    now = pd.Timestamp(now)
    recent = [t for t in prior_trades if t.get("exit_time") is not None and _is_sl_loss(t)
              and pd.Timestamp(now) - pd.Timedelta(minutes=minutes) <= pd.Timestamp(t["exit_time"]) <= now]
    if not recent:
        return False, None
    last = max(recent, key=lambda t: pd.Timestamp(t["exit_time"]))
    left = minutes - (now - pd.Timestamp(last["exit_time"])).total_seconds() / 60
    return True, (f"{pd.Timestamp(last['exit_time']):%H:%M} ला SL/Trailing-SL ने तोटा (₹{float(last['realized_pnl']):,.0f}) — "
                  f"{minutes} मिनिटांचा cooldown, अजून {left:.0f} मिनिटं नवीन entry नाही")


def sl_level_direction_block(prior_trades, now, level, direction, tol_pct=0.05):
    """आज (now च्या तारखेला) त्याच level (±tol_pct%) वर, त्याच दिशेने SL (तोटा) लागला असेल तर block. रिटर्न (blocked, कारण)."""
    now = pd.Timestamp(now)
    for t in prior_trades:
        if t.get("exit_time") is None or not _is_sl_loss(t) or pd.Timestamp(t["exit_time"]).date() != now.date() or pd.Timestamp(t["exit_time"]) > now:
            continue
        lv = t.get("entry_level_price")
        if lv is None or t.get("direction") != direction:
            continue
        if abs(float(lv) - float(level)) <= float(level) * tol_pct / 100.0:
            return True, (f"आज याच level ({float(lv):,.2f}) वर {'LONG' if direction == 'BULLISH' else 'SHORT'} trade SL ने तोट्यात गेला "
                          f"({pd.Timestamp(t['exit_time']):%H:%M}) — आज याच दिशेने पुन्हा entry नाही")
    return False, None


def _session_dates(df):
    return pd.to_datetime(df["timestamp"]).dt.date


def cascade_block(df30, direction, level, sessions=2, swing_order=3, lookback_sessions=6):
    """df30 = entry आधीचे **पूर्ण** 30M bars (timestamp/high/low/close). रिटर्न (blocked, कारण, तपशील dict).
    LONG: मागच्या `sessions` sessions मध्ये एखादा confirmed 30M swing low (level च्या वर) close ने तुटला ⇒ cascade. मग त्या break नंतर
    तयार झालेला शेवटचा confirmed swing high (lower-high) 30M close ने वर तुटला असेल (bullish CHoCH) तरच परवानगी. SHORT उलट."""
    info = {"cascade": False, "broken_level": None, "break_time": None, "choch_level": None, "choch": None}
    if df30 is None or len(df30) < 2 * swing_order + 3:
        return False, None, info
    df = df30.reset_index(drop=True)
    dates = _session_dates(df)
    uniq = sorted(dates.unique())
    recent_dates = set(uniq[-sessions:])
    window_dates = set(uniq[-lookback_sessions:])
    df = df[dates.isin(window_dates).to_numpy()].reset_index(drop=True)
    dates = _session_dates(df)
    n = len(df)
    hi, lo, cl = df["high"].to_numpy(float), df["low"].to_numpy(float), df["close"].to_numpy(float)
    sh, sl = find_swings(df, order=swing_order)
    long = direction == "BULLISH"
    pivots = [i for i in (sl if long else sh) if i <= n - 1 - swing_order]
    best = None                                                  # सर्वात अलीकडचा break
    for i in pivots:
        p = lo[i] if long else hi[i]
        if (p <= level) if long else (p >= level):
            continue                                             # cascade म्हणजे level च्या वरचा support (SHORT: खालचा resistance) तुटलेला
        for j in range(i + 1, n):
            broke = cl[j] < p if long else cl[j] > p
            if broke:
                if dates.iloc[j] in recent_dates and (best is None or j > best[1]):
                    best = (i, j, p)
                break
    if best is None:
        return False, None, info
    i, j, p = best
    info.update({"cascade": True, "broken_level": float(p), "break_time": str(df["timestamp"].iloc[j])})
    opp = [k for k in (sh if long else sl) if j <= k <= n - 1 - swing_order]
    if not opp:
        return True, (f"{'Support' if long else 'Resistance'} {p:,.2f} 30M close ने तुटला ({df['timestamp'].iloc[j]:%d %b %H:%M}) — त्यानंतर "
                      f"30M {'lower-high' if long else 'higher-low'} अजून तयार झाला नाही, CHoCH नाही ⇒ {'LONG' if long else 'SHORT'} थांबवला"), info
    k = opp[-1]
    lvl = hi[k] if long else lo[k]
    info["choch_level"] = float(lvl)
    after = cl[k + 1:]
    choch = bool((after > lvl).any()) if long else bool((after < lvl).any())
    info["choch"] = choch
    if choch:
        return False, None, info
    return True, (f"{'Support' if long else 'Resistance'} {p:,.2f} 30M close ने तुटला ({df['timestamp'].iloc[j]:%d %b %H:%M}) — शेवटचा "
                  f"{'lower-high' if long else 'higher-low'} {lvl:,.2f} अजून 30M close ने {'वर' if long else 'खाली'} तुटलेला नाही (CHoCH नाही) ⇒ "
                  f"{'LONG' if long else 'SHORT'} थांबवला"), info


def next_level_target(levels, entry_price, direction, min_distance):
    """🎓 वापरकर्त्याची निवड "Target = पुढचा level": LONG ⇒ entry च्या वर किमान `min_distance` अंतरावरचा सर्वात जवळचा level; SHORT ⇒ खालचा.
    levels = किंमतींची यादी (bot चे ACTIVE levels). रिटर्न level किंवा None (नसेल तर caller नेहमीचा points/% target वापरतो)."""
    entry = float(entry_price)
    if direction == "BULLISH":
        above = sorted(float(lv) for lv in levels if float(lv) - entry >= min_distance)
        return above[0] if above else None
    below = sorted((float(lv) for lv in levels if entry - float(lv) >= min_distance), reverse=True)
    return below[0] if below else None


# ---------------------------------------------------------------------------------------------------------------------
# 🎓 Candle confirmation gate — LOGIC-BASED (वापरकर्त्याची अंतिम रचना): composite rejection candle + rejection_score; नियम
# price_action/candles.py मध्ये (pattern-नावांवर निर्णय नाही). इथे MCX-विशिष्ट: कोणत्या TF वर तपासायचं, 50/50 split, pullback.
# ---------------------------------------------------------------------------------------------------------------------
CANDLE_TF_MODES = ("chart", "30M", "60M")


def candle_tf_for(mode, timeframe_suffix, settings):
    """"chart" (डीफॉल्ट) ⇒ level ज्या TF चा त्याच TF च्या candles (30M/60M); SR V3 levels ना TF नसतो ⇒ bot चा timeframe_choice
    (60M निवडलं असेल तर 60M, नाहीतर 30M). "30M"/"60M" ⇒ override."""
    if mode in ("30M", "60M"):
        return mode
    if timeframe_suffix in ("30M", "60M"):
        return timeframe_suffix
    return "60M" if (settings or {}).get("timeframe_choice") == "60M" else "30M"


def rejection_confirmation(frames, tf, direction, level, settings):
    """त्या TF च्या पूर्ण candles वर PA.evaluate_rejection (k / min score settings मधून). रिटर्न result dict ("tf" सकट)."""
    s = settings or {}
    res = PA.evaluate_rejection((frames or {}).get(tf), level, direction, k=max(1.0, float(s.get("candle_k", 1.2))),
                                min_score=float(s.get("candle_min_score", 60)))
    res["tf"] = tf
    return res


def split_lots(lots):
    """50/50 split: lots ≥ 2 ⇒ (लगेच, pullback) = (ceil, floor); lots < 2 ⇒ None (split नाही — पूर्ण quantity लगेच)."""
    lots = int(lots)
    if lots < 2:
        return None
    return lots - lots // 2, lots // 2


def pullback_reached(direction, price, pullback):
    """भाग 2: BULLISH ⇒ भाव pullback पर्यंत खाली आला; BEARISH ⇒ वर आला."""
    return float(price) <= pullback if direction == "BULLISH" else float(price) >= pullback
