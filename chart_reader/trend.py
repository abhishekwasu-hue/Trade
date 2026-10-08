"""chart_reader/trend.py — HTF trend (HH/HL वि. LH/LL, confirmed swings; close-only breaks) आणि ताकद.

🎓 `opportunity_engine.structure.StructureTracker` (no-lookahead) — PCS `trend_state` तोच. UPTREND / UPTREND_PULLBACK ⇒ up, मजबूत;
UPTREND_WEAK ⇒ up, कमकुवत होतोय (CHoCH); DOWN बाजू आरसा; RANGE ⇒ range (range edge = शेवटच्या range च्या वरच्या/खालच्या 15% मध्ये).
अनेक HTF दिले तर पहिला (मोठा) TF निर्णायक; बाकी फक्त नोंद.
"""
from opportunity_engine.structure import DN, DN_PB, DN_WEAK, RANGE, UP, UP_PB, UP_WEAK
from pullback_credit_spread.signal import trend_state


def _map(state):
    if state in (UP, UP_PB):
        return "up", "strong"
    if state == UP_WEAK:
        return "up", "weakening"
    if state in (DN, DN_PB):
        return "down", "strong"
    if state == DN_WEAK:
        return "down", "weakening"
    if state == RANGE:
        return "range", "unclear"
    return "unclear", "unclear"


def read(frames, tfs, lookback=60):
    """frames = {tf: बंद bars}; tfs = HTF क्रम (मोठा आधी). रिटर्न {htf, trend_strength, at_range_edge, states{tf: state}, line}."""
    states = {}
    for tf in tfs:
        df = frames.get(tf)
        if df is not None and len(df) >= 10:
            states[tf] = trend_state(df, tf)
    main = next((states[tf] for tf in tfs if tf in states), None)
    htf, strength = _map(main)
    edge = False
    if htf == "range":
        df = frames[next(tf for tf in tfs if tf in states)].tail(lookback)
        hi, lo, c = float(df["high"].max()), float(df["low"].min()), float(df["close"].iloc[-1])
        edge = hi > lo and ((c - lo) / (hi - lo) <= 0.15 or (hi - c) / (hi - lo) <= 0.15)
    line = f"HTF trend {htf} ({strength})" + (" · range edge" if edge else "") + (f" · {', '.join(f'{k} {v}' for k, v in states.items())}"
                                                                                    if states else " · डेटा नाही")
    return {"htf": htf, "trend_strength": strength, "at_range_edge": edge, "states": states, "line": line}
