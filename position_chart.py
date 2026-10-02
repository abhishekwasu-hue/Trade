"""
position_chart.py
------------------
🎓 "Positions पानावर चार्ट: entry, stop, target ... रेषा" -- एका उघड्या position साठी चार्टवर काढायच्या आडव्या रेषा ठरवणारं गणित (UI नाही).

- MCX futures: Entry = |net_credit|; SL / Target / Manual Override हे ₹ P&L पातळीवरून futures भावात (trading_engine.futures_price_for_pnl_level) -- अचूक.
- NSE (NIFTY/BANKNIFTY/SENSEX) options: Entry = entry_spot_price (नसेल तर entry_level_price). SL / Target फक्त तीन bots साठी (dynamic_sr_instant,
  classic_sr_reversal, srv2_momentum_reversal), त्यांच्या Spot% नियमावरून -- **सध्याच्या settings** वरून (entry नंतर settings बदलल्या असतील तर
  रेषा चुकीची येऊ शकते => 'अंदाजित'), आणि Premium-Points नियम वेगळा आहे (जे आधी घडेल ते लागू) -- म्हणून ही रेषा फक्त Spot% पातळी दाखवते.
  इतर sources (MANUAL, credit_spread_auto_trader ...) ₹ P&L पातळी वापरतात -- त्यांना चार्टवर भावात बदलता येत नाही => फक्त Entry.
- Trailing SL: MCX futures -- engine चंच compute_trailing_sl_level() (peak_pnl + settings चं अंतर) वापरून अचूक futures भावात, आणि peak वाढला की रेषा हलते (live).
  NSE options -- Trailing SL premium-points आधारित असल्याने underlying (spot) चार्टवर रेषा काढता येत नाही (premium -> spot चं खरं रूपांतर नाही); त्याऐवजी
  चार्टखाली स्थिती-ओळ (TSL सक्रिय?, peak, floor) -- nse_trailing_status().
"""
import cloud_db
from trading_engine import compute_trailing_sl_level, futures_price_for_pnl_level

ENTRY_COLOR, SL_COLOR, TARGET_COLOR, OVERRIDE_COLOR, TRAIL_COLOR = "#2962FF", "#F23645", "#089981", "#ff9800", "#ffd54f"

# trading_engine._BROKER_SIDE_SL_SETTINGS_NAMESPACE सारखाच (source -> settings namespace) -- तेच तीन sources Spot% वापरतात.
SPOT_RULE_NAMESPACE = {
    "dynamic_sr_instant": "1m_instant",
    "classic_sr_reversal": "classic_sr_reversal",
    "srv2_momentum_reversal": "15m_dynamic_sr",
}
_BULLISH_STRATEGIES = ("BULL_PUT_SPREAD", "NAKED_CALL")
_BEARISH_STRATEGIES = ("BEAR_CALL_SPREAD", "NAKED_PUT")


def _line(price, title, color, dashed=True, width=2):
    return {"price": round(float(price), 2), "title": title, "color": color, "dashed": dashed, "width": width}


LEVEL_COLOR = "#b0bec5"


def _trigger_level_line(info, reference_price):
    """trade ज्या S/R level मुळे घेतला गेला (entry_level_price) -- Entry भावापासून वेगळा असेल तरच एक अतिरिक्त रेषा."""
    level = info.get("entry_level_price")
    if level is None or (reference_price is not None and abs(float(level) - float(reference_price)) < 0.005):
        return []
    return [_line(level, "Level (trade जिथून घेतला)", LEVEL_COLOR, dashed=True, width=1)]


def mcx_trailing_distance_points(settings, ref_price):
    """MCX monitor (mcx_futures_trader.monitor_symbol) सारखंच trailing अंतर (points): बंद => None; POINTS => trailing_distance_points;
    PERCENT => ref_price (engine सद्य किंमत वापरतो) * trailing_pct / 100 (ref_price नसेल तर None)."""
    if not settings or not settings.get("trailing_sl_enabled", False):
        return None
    if settings.get("sl_target_mode", "POINTS") == "PERCENT":
        return None if not ref_price else float(ref_price) * float(settings.get("trailing_pct", 1.0)) / 100
    distance = settings.get("trailing_distance_points")
    return float(distance) if distance is not None else None


SL_KIND_LABELS = {"SL": "मूळ SL", "TRAILING": "Trailing", "OVERRIDE": "Manual Override"}


def mcx_sl_price(info, settings=None, ref_price=None):
    """MCX futures trade चा **सध्या लागू** SL भाव आणि प्रकार -> (price | None, kind). kind: "OVERRIDE" (Manual Override -- engine मध्ये trailing ला वगळतो) / "TRAILING"
    (engine चंच compute_trailing_sl_level(): trailing चालू + peak_pnl > 0 + मूळ SL पेक्षा चांगला) / "SL" (मूळ). Chart आणि Positions तक्ता दोघे हेच वापरतात."""
    net_credit, lots, lot_size = info.get("net_credit"), info.get("lots"), info.get("lot_size")
    if net_credit is None:
        return None, "SL"
    override = info.get("manual_sl_override_pnl")
    sl_level = override if override is not None else info.get("sl_pnl_level")
    kind = "OVERRIDE" if override is not None else "SL"
    if override is None:
        distance = mcx_trailing_distance_points(settings, ref_price)
        peak = info.get("peak_pnl")
        if distance is not None and peak is not None and lots and lot_size:
            _, effective = compute_trailing_sl_level(peak, peak, distance, lot_size, lots, atr_multiplier=1.0, original_sl_level=sl_level)
            if effective is not None and effective != sl_level:       # engine चा is_trailing_active
                sl_level, kind = effective, "TRAILING"
    return futures_price_for_pnl_level(net_credit, sl_level, lots, lot_size), kind


def futures_lines(info, settings=None, ref_price=None):
    """MCX futures trade -> [Entry, SL, Target (+ Level)] रेषा (futures भावात). SL रेषा = mcx_sl_price(): Manual Override (नारिंगी) / Trailing (पिवळी, 'SL (Trailing)') / मूळ SL."""
    net_credit, lots, lot_size = info.get("net_credit"), info.get("lots"), info.get("lot_size")
    if net_credit is None:
        return []
    lines = [_line(abs(net_credit), "Entry", ENTRY_COLOR, dashed=False)]
    sl_price, kind = mcx_sl_price(info, settings, ref_price)
    if sl_price is not None:
        title, color = {"OVERRIDE": ("SL (Manual Override)", OVERRIDE_COLOR), "TRAILING": ("SL (Trailing)", TRAIL_COLOR)}.get(kind, ("SL", SL_COLOR))
        lines.append(_line(sl_price, title, color))
    target_price = futures_price_for_pnl_level(net_credit, info.get("target_pnl_level"), lots, lot_size)
    if target_price is not None:
        lines.append(_line(target_price, "Target", TARGET_COLOR))
    return lines + _trigger_level_line(info, abs(net_credit))


def nse_trailing_status(symbol, info, get_settings=None):
    """NSE options trade -> चार्टखालची Trailing SL स्थिती-ओळ (premium-points आधारित, म्हणून spot चार्टवर रेषा नाही), किंवा None (हा source Spot%/premium नियम वापरत नाही).
    engine प्रमाणे: TSL (Breakeven) सक्रिय झाल्यावरच premium trailing सुरू; floor = peak premium pts - trailing अंतर. peak_pnl शेवटच्या monitor cycle पर्यंतचा."""
    get_settings = get_settings or cloud_db.get_strategy_settings
    namespace = SPOT_RULE_NAMESPACE.get(info.get("source"))
    strategy = info.get("strategy")
    if namespace is None or strategy not in _BULLISH_STRATEGIES + _BEARISH_STRATEGIES:
        return None
    try:
        settings = get_settings(namespace, symbol)
        prefix = "naked" if strategy.startswith("NAKED") else "spread"
        enabled = bool(settings.get(f"{prefix}_trailing_sl_enabled", False))
        distance = float(settings.get(f"{prefix}_trailing_distance_points", 0))
    except Exception:
        return None
    activated = bool(info.get("tsl_activated"))
    parts = ["TSL (Breakeven) सक्रिय ✅ — SL आता Entry (premium) वर सुरक्षित" if activated else "TSL (Breakeven) अजून सक्रिय नाही"]
    if not enabled:
        parts.append("Trailing SL बंद (settings)")
    elif not activated:
        parts.append(f"Trailing SL चालू (अंतर {distance:g} pts) — TSL सक्रिय झाल्यावर सुरू होईल")
    else:
        peak = info.get("peak_pnl")
        if peak is None:
            parts.append(f"Trailing SL चालू (अंतर {distance:g} pts) — peak अजून नोंदलेला नाही")
        else:
            floor = float(peak) - distance
            qty = (info.get("lots") or 0) * (info.get("lot_size") or 0)
            rupees = f" (≈ ₹{floor * qty:,.0f})" if qty else ""
            parts.append(f"Trailing floor: peak +{float(peak):.1f} pts − {distance:g} = +{floor:.1f} pts{rupees}")
    return " · ".join(parts) + ". (Premium आधारित, शेवटच्या monitor cycle पर्यंत — spot चार्टवर रेषा काढता येत नाही.)"


def spot_rule_lines(symbol, info, get_settings=None):
    """NSE options trade -> ([रेषा], टीप). टीप = वापरकर्त्याला चार्टखाली दाखवायचा मजकूर (अंदाजित/का रेषा नाहीत)."""
    get_settings = get_settings or cloud_db.get_strategy_settings
    anchor = info.get("entry_spot_price") if info.get("entry_spot_price") is not None else info.get("entry_level_price")
    if anchor is None:
        return [], "या trade ला entry spot भाव साठवलेला नाही -- चार्टवर रेषा काढता येत नाहीत."
    lines = [_line(anchor, "Entry (spot)", ENTRY_COLOR, dashed=False)] + _trigger_level_line(info, anchor)
    source, strategy = info.get("source"), info.get("strategy")
    namespace = SPOT_RULE_NAMESPACE.get(source)
    if namespace is None or strategy not in _BULLISH_STRATEGIES + _BEARISH_STRATEGIES:
        return lines, ("या trade चा SL/Target ₹ P&L पातळीवर आहे (Spot% नियमावर नाही) -- म्हणून चार्टवर फक्त Entry spot दाखवला आहे.")
    try:
        settings = get_settings(namespace, symbol)
        prefix = "naked" if strategy.startswith("NAKED") else "spread"
        sl_pct, target_pct = float(settings[f"{prefix}_sl_spot_pct"]), float(settings[f"{prefix}_target_spot_pct"])
    except Exception:
        return lines, "Strategy settings वाचता आल्या नाहीत -- चार्टवर फक्त Entry spot दाखवला आहे."
    bullish = strategy in _BULLISH_STRATEGIES
    sl_price = anchor * (1 - sl_pct / 100) if bullish else anchor * (1 + sl_pct / 100)
    target_price = anchor * (1 + target_pct / 100) if bullish else anchor * (1 - target_pct / 100)
    lines.append(_line(sl_price, f"SL (Spot {sl_pct:g}%)", SL_COLOR))
    lines.append(_line(target_price, f"Target (Spot {target_pct:g}%)", TARGET_COLOR))
    return lines, (
        "⚠️ SL/Target रेषा Spot% नियमाच्या आहेत, **सध्याच्या settings** वरून (अंदाजित -- entry नंतर settings बदलल्या असतील तर वेगळ्या असू शकतात). "
        "Premium-Points नियम वेगळा आहे -- Spot% किंवा Premium-Points, जे आधी घडेल तेव्हा exit होतो. Trailing SL premium आधारित असल्याने रेषा नाही, खाली स्थिती-ओळ आहे."
    )
