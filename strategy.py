"""Options strategy selection: credit spreads, Iron Condor/Butterfly, PoP-driven strike selection, position sizing."""

def _pop_lookup(raw_chain, side, strike):
    """दिलेल्या strike + side (call/put) साठी option_greeks मधून LTP व PoP मिळवणे."""
    for item in raw_chain:
        if item.get("strike_price") == strike:
            opt = item.get(side, {}) or {}
            greeks = opt.get("option_greeks", {}) or {}
            ltp = (opt.get("market_data", {}) or {}).get("ltp")
            return {
                "strike": strike, "instrument_key": opt.get("instrument_key"),
                "pop": greeks.get("pop"), "ltp": ltp,
            }
    return None

def select_iron_condor(raw_chain, atm_strike, step, hedge_width_points, pop_threshold_pct, max_widen_steps=12):
    """
    ATM पासून दोन्ही बाजूंनी (call व put) समांतर बाहेर सरकत, combined PoP threshold गाठेपर्यंत short strikes शोधणे.
    combined PoP ≈ short_call_pop + short_put_pop − 1 (approximation, exact नाही).
    """
    strikes_available = sorted({item.get("strike_price") for item in raw_chain if item.get("strike_price") is not None})
    if not strikes_available:
        return None

    for n in range(1, max_widen_steps + 1):
        short_call_strike = atm_strike + n * step
        short_put_strike = atm_strike - n * step
        if short_call_strike not in strikes_available or short_put_strike not in strikes_available:
            continue

        short_call = _pop_lookup(raw_chain, "call_options", short_call_strike)
        short_put = _pop_lookup(raw_chain, "put_options", short_put_strike)
        if not short_call or not short_put or short_call["pop"] is None or short_put["pop"] is None:
            continue
        if short_call["ltp"] is None or short_put["ltp"] is None:
            continue

        combined_pop = max(0.0, short_call["pop"] + short_put["pop"] - 1) * 100
        if combined_pop < pop_threshold_pct:
            continue

        long_call_strike = short_call_strike + hedge_width_points
        long_put_strike = short_put_strike - hedge_width_points
        if long_call_strike not in strikes_available or long_put_strike not in strikes_available:
            continue
        long_call = _pop_lookup(raw_chain, "call_options", long_call_strike)
        long_put = _pop_lookup(raw_chain, "put_options", long_put_strike)
        if not long_call or not long_put or long_call["ltp"] is None or long_put["ltp"] is None:
            continue

        net_credit = (short_call["ltp"] - long_call["ltp"]) + (short_put["ltp"] - long_put["ltp"])
        call_side_width = long_call_strike - short_call_strike
        put_side_width = short_put_strike - long_put_strike
        max_loss = max(call_side_width, put_side_width) - net_credit
        if net_credit <= 0 or max_loss <= 0:
            continue

        return {
            "strategy": "IRON_CONDOR",
            "legs": [
                {"role": "long_call_wing", "strike": long_call_strike, "instrument_key": long_call["instrument_key"], "transaction_type": "BUY", "ltp": long_call["ltp"]},
                {"role": "long_put_wing", "strike": long_put_strike, "instrument_key": long_put["instrument_key"], "transaction_type": "BUY", "ltp": long_put["ltp"]},
                {"role": "short_call", "strike": short_call_strike, "instrument_key": short_call["instrument_key"], "transaction_type": "SELL", "ltp": short_call["ltp"]},
                {"role": "short_put", "strike": short_put_strike, "instrument_key": short_put["instrument_key"], "transaction_type": "SELL", "ltp": short_put["ltp"]},
            ],
            "net_credit": round(net_credit, 2),
            "max_profit": round(net_credit, 2),
            "max_loss": round(max_loss, 2),
            "combined_pop_pct": round(combined_pop, 1),
        }
    return None

def select_iron_butterfly(raw_chain, atm_strike, hedge_width_points, pop_threshold_pct):
    """
    दोन्ही short legs ATM वर (call व put), wings ATM ± hedge_width_points वर.
    combined PoP इथे wing (long) legs च्या pop वरून अंदाजित — 'किंमत wings च्या आत राहण्याची शक्यता' साठी एक proxy (approximation).
    """
    short_call = _pop_lookup(raw_chain, "call_options", atm_strike)
    short_put = _pop_lookup(raw_chain, "put_options", atm_strike)
    long_call_strike = atm_strike + hedge_width_points
    long_put_strike = atm_strike - hedge_width_points
    long_call = _pop_lookup(raw_chain, "call_options", long_call_strike)
    long_put = _pop_lookup(raw_chain, "put_options", long_put_strike)

    if not all([short_call, short_put, long_call, long_put]):
        return None
    if any(x["ltp"] is None for x in [short_call, short_put, long_call, long_put]):
        return None
    if long_call["pop"] is None or long_put["pop"] is None:
        return None

    combined_pop = max(0.0, long_call["pop"] + long_put["pop"] - 1) * 100
    if combined_pop < pop_threshold_pct:
        return None

    net_credit = (short_call["ltp"] - long_call["ltp"]) + (short_put["ltp"] - long_put["ltp"])
    max_loss = hedge_width_points - net_credit
    if net_credit <= 0 or max_loss <= 0:
        return None

    return {
        "strategy": "IRON_BUTTERFLY",
        "legs": [
            {"role": "long_call_wing", "strike": long_call_strike, "instrument_key": long_call["instrument_key"], "transaction_type": "BUY", "ltp": long_call["ltp"]},
            {"role": "long_put_wing", "strike": long_put_strike, "instrument_key": long_put["instrument_key"], "transaction_type": "BUY", "ltp": long_put["ltp"]},
            {"role": "short_call_atm", "strike": atm_strike, "instrument_key": short_call["instrument_key"], "transaction_type": "SELL", "ltp": short_call["ltp"]},
            {"role": "short_put_atm", "strike": atm_strike, "instrument_key": short_put["instrument_key"], "transaction_type": "SELL", "ltp": short_put["ltp"]},
        ],
        "net_credit": round(net_credit, 2),
        "max_profit": round(net_credit, 2),
        "max_loss": round(max_loss, 2),
        "combined_pop_pct": round(combined_pop, 1),
    }

def select_credit_spread(raw_chain, direction, hedge_width_points, pop_threshold_pct):
    """
    Upstox च्या option_greeks.pop (Probability of Profit, आधीच API मध्ये उपलब्ध) वापरून
    क्रेडिट स्प्रेड निवडणे:
    BULLISH -> Bull Put Spread (जवळचा OTM Put विकणे + आणखी दूरचा Put विकत घेणे - हेज)
    BEARISH -> Bear Call Spread (जवळचा OTM Call विकणे + आणखी दूरचा Call विकत घेणे - हेज)
    """
    if direction not in ("BULLISH", "BEARISH"):
        return None
    side = "put_options" if direction == "BULLISH" else "call_options"

    candidates = []
    for item in raw_chain:
        opt = item.get(side, {}) or {}
        greeks = opt.get("option_greeks", {}) or {}
        pop = greeks.get("pop")
        ltp = (opt.get("market_data", {}) or {}).get("ltp")
        instrument_key = opt.get("instrument_key")
        strike = item.get("strike_price")
        if pop is None or ltp is None or not instrument_key or strike is None or ltp <= 0:
            continue
        candidates.append({"strike": strike, "instrument_key": instrument_key, "pop": pop, "ltp": ltp})

    if not candidates:
        return None

    # शॉर्ट लेग: स्पॉटच्या सर्वात जवळच्या strike पासून सुरुवात करून, PoP >= threshold मिळेपर्यंत बाहेर जाणे
    if direction == "BULLISH":
        candidates_sorted = sorted(candidates, key=lambda c: -c["strike"])   # जवळपासून (उंच strike) खाली
    else:
        candidates_sorted = sorted(candidates, key=lambda c: c["strike"])    # जवळपासून (कमी strike) वर

    short_leg = next((c for c in candidates_sorted if c["pop"] * 100 >= pop_threshold_pct), None)
    if short_leg is None:
        return None

    # लाँग लेग (हेज): hedge_width_points इतकी आणखी दूर
    if direction == "BULLISH":
        target = short_leg["strike"] - hedge_width_points
        pool = [c for c in candidates if c["strike"] <= target]
        long_leg = max(pool, key=lambda c: c["strike"]) if pool else None
    else:
        target = short_leg["strike"] + hedge_width_points
        pool = [c for c in candidates if c["strike"] >= target]
        long_leg = min(pool, key=lambda c: c["strike"]) if pool else None

    if long_leg is None:
        return None

    net_credit = short_leg["ltp"] - long_leg["ltp"]
    spread_width = abs(short_leg["strike"] - long_leg["strike"])
    max_profit = net_credit
    max_loss = spread_width - net_credit

    if net_credit <= 0 or max_loss <= 0:
        return None

    return {
        "strategy": "BULL_PUT_SPREAD" if direction == "BULLISH" else "BEAR_CALL_SPREAD",
        "short_leg": short_leg,
        "long_leg": long_leg,
        "net_credit": round(net_credit, 2),
        "spread_width": spread_width,
        "max_profit": round(max_profit, 2),
        "max_loss": round(max_loss, 2),
        "short_pop_pct": round(short_leg["pop"] * 100, 1),
    }

def compute_position_size(available_margin, risk_pct, max_loss_per_unit, lot_size):
    """उपलब्ध मार्जिन × रिस्क% वरून लॉट्सची संख्या ठरवणे."""
    if not available_margin or max_loss_per_unit <= 0 or lot_size <= 0:
        return 0, 0.0
    risk_amount = available_margin * (risk_pct / 100.0)
    max_loss_per_lot = max_loss_per_unit * lot_size
    lots = int(risk_amount // max_loss_per_lot) if max_loss_per_lot > 0 else 0
    return lots, risk_amount
