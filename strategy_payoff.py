"""
strategy_payoff.py
---------------------
🎓 वापरकर्त्याशी चर्चा करून बांधलेलं module — Sensibull-सारखं Strategy Builder (multi-leg payoff
diagram + combined Greeks) साठी established, टेस्टेड core logic. Dashboard च्या "Strategy Builder"
tab मध्ये वापरलं जातं.

Leg format (dict): {"direction": "BUY"/"SELL", "option_type": "CE"/"PE", "strike": float,
                     "premium": float, "lots": int, "lot_size": int}
Greeks-leg format: वरचंच + {"delta":.., "gamma":.., "theta":.., "vega":..}
"""


def compute_leg_payoff(underlying_price, direction, option_type, strike, premium, lots, lot_size, **_extra):
    """एका leg चा, दिलेल्या underlying price वर, expiry-वेळचा P&L. **_extra -- leg dict मध्ये असलेली
    इतर माहिती (instrument_key, Greeks इ.) सुरक्षितपणे दुर्लक्षित करण्यासाठी."""
    intrinsic = max(underlying_price - strike, 0) if option_type == "CE" else max(strike - underlying_price, 0)
    if direction == "BUY":
        return (intrinsic - premium) * lots * lot_size
    else:
        return (premium - intrinsic) * lots * lot_size


def compute_strategy_payoff_curve(legs, price_range):
    """सर्व legs मिळून, प्रत्येक किमतीला एकूण payoff (list, price_range शीच जुळणारी)."""
    return [sum(compute_leg_payoff(p, **leg) for leg in legs) for p in price_range]


def compute_combined_greeks(legs_with_greeks):
    """
    प्रत्येक leg चे स्वतःचे Greeks, दिशा (BUY=+, SELL=-) आणि lots/lot_size नुसार एकत्र करून, संपूर्ण
    strategy चे निव्वळ Greeks. established fetch_option_greeks() च्या return-format शी सुसंगत
    (delta/gamma/theta/vega keys).
    """
    total = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
    for leg in legs_with_greeks:
        sign = 1 if leg["direction"] == "BUY" else -1
        qty = leg["lots"] * leg["lot_size"]
        for g in total:
            total[g] += sign * leg.get(g, 0.0) * qty
    return total


def find_breakeven_points(price_range, payoff_curve):
    """payoff शून्य ओलांडतो त्या किमती (रेषीय interpolation ने अचूक)."""
    breakevens = []
    for i in range(1, len(payoff_curve)):
        p1, p2 = payoff_curve[i - 1], payoff_curve[i]
        if p1 == 0:
            breakevens.append(round(price_range[i - 1], 2))
        elif (p1 < 0 < p2) or (p1 > 0 > p2):
            x1, x2 = price_range[i - 1], price_range[i]
            breakeven = x1 + (x2 - x1) * (0 - p1) / (p2 - p1)
            breakevens.append(round(breakeven, 2))
    return breakevens


def compute_max_profit_loss(payoff_curve):
    """कमाल नफा आणि कमाल तोटा (दिलेल्या price_range च्या मर्यादेत — त्या पलीकडे unbounded असू शकतं)."""
    return max(payoff_curve), min(payoff_curve)


def build_ready_made_strategy(strategy_name, atm_strike, hedge_width=100):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — Sensibull-सारख्या established रणनीती-नावांसाठी,
    leg-रचना (direction, option_type, strike) परत करणे. Premium इथे भरलं जात नाही (ते live option
    chain मधून Dashboard कडून वेगळं भरलं जातं) — फक्त संरचना.
    """
    templates = {
        "Buy Call": [("BUY", "CE", atm_strike)],
        "Sell Put": [("SELL", "PE", atm_strike)],
        "Bull Call Spread": [("BUY", "CE", atm_strike), ("SELL", "CE", atm_strike + hedge_width)],
        "Bull Put Spread": [("SELL", "PE", atm_strike), ("BUY", "PE", atm_strike - hedge_width)],
        "Buy Put": [("BUY", "PE", atm_strike)],
        "Sell Call": [("SELL", "CE", atm_strike)],
        "Bear Put Spread": [("BUY", "PE", atm_strike), ("SELL", "PE", atm_strike - hedge_width)],
        "Bear Call Spread": [("SELL", "CE", atm_strike), ("BUY", "CE", atm_strike + hedge_width)],
        "Short Straddle": [("SELL", "CE", atm_strike), ("SELL", "PE", atm_strike)],
        "Long Straddle": [("BUY", "CE", atm_strike), ("BUY", "PE", atm_strike)],
        "Short Strangle": [("SELL", "CE", atm_strike + hedge_width), ("SELL", "PE", atm_strike - hedge_width)],
        "Long Strangle": [("BUY", "CE", atm_strike + hedge_width), ("BUY", "PE", atm_strike - hedge_width)],
        "Iron Condor": [
            ("SELL", "CE", atm_strike + hedge_width), ("BUY", "CE", atm_strike + 2 * hedge_width),
            ("SELL", "PE", atm_strike - hedge_width), ("BUY", "PE", atm_strike - 2 * hedge_width),
        ],
    }
    if strategy_name not in templates:
        return None
    return [{"direction": d, "option_type": ot, "strike": float(s), "lots": 1} for d, ot, s in templates[strategy_name]]


def build_strategy_result_from_legs(legs, payoff_curve):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — Strategy Builder मधून थेट execution साठी, legs
    (direction/option_type/strike/premium/lots/lot_size/instrument_key) पासून established
    open_multi_leg_trade() ला अपेक्षित strategy_result dict तयार करणे. max_loss/max_profit
    payoff-curve वरूनच (प्रति-lot, lot_size ने भागून) काढले जातात — कारण Strategy Builder मध्ये
    कुठलेही ठराविक (Credit Spread सारखे) सूत्र लागू होत नाही, संपूर्ण, अचूक payoff-गणनाच वापरायला हवी.
    """
    lot_size = legs[0]["lot_size"]
    net_credit_per_lot = sum(
        (leg["premium"] if leg["direction"] == "SELL" else -leg["premium"]) * leg["lots"]
        for leg in legs
    )
    max_profit_total, max_loss_total = max(payoff_curve), min(payoff_curve)
    max_profit_per_lot = max_profit_total / lot_size
    # 🎓 established convention (select_credit_spread_fixed_strikes()) मध्ये max_loss नेहमी **धन**
    # (नुकसानाची रक्कम) असतो, payoff-curve चं raw किमान मूल्य (जे ऋण असतं) नाही — trading_engine.py चं
    # sl_pnl_level = -(max_loss * sl_pct/100) हे सूत्र धन max_loss गृहीत धरतं. इथे abs() ने दुरुस्त.
    max_loss_per_lot = abs(max_loss_total) / lot_size

    result_legs = [
        {"role": f"LEG{i + 1}_{leg['direction']}_{leg['option_type']}", "strike": leg["strike"],
         "instrument_key": leg["instrument_key"], "transaction_type": leg["direction"]}
        for i, leg in enumerate(legs)
    ]
    return {
        "legs": result_legs, "net_credit": net_credit_per_lot,
        "max_profit": max_profit_per_lot, "max_loss": max_loss_per_lot,
        "strategy_type": "CUSTOM_MULTI_LEG", "is_credit_strategy": net_credit_per_lot > 0,
    }


READY_MADE_CATEGORIES = {
    "Bullish": ["Buy Call", "Sell Put", "Bull Call Spread", "Bull Put Spread"],
    "Bearish": ["Buy Put", "Sell Call", "Bear Put Spread", "Bear Call Spread"],
    "Neutral": ["Short Straddle", "Short Strangle", "Iron Condor"],
    "Others": ["Long Straddle", "Long Strangle"],
}


def build_default_price_range(underlying_price, num_points=100, range_pct=5.0):
    """सद्य किमतीच्या भोवती ±range_pct% चा, payoff-diagram साठी योग्य price range."""
    lo = underlying_price * (1 - range_pct / 100)
    hi = underlying_price * (1 + range_pct / 100)
    step = (hi - lo) / (num_points - 1)
    return [round(lo + i * step, 2) for i in range(num_points)]
