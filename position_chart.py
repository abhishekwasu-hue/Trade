"""
position_chart.py
------------------
🎓 "Positions पानावर चार्ट: entry, stop, target ... रेषा" -- एका उघड्या position साठी चार्टवर काढायच्या आडव्या रेषा ठरवणारं गणित (UI नाही).

- MCX futures: Entry = |net_credit|; SL / Target / Manual Override हे ₹ P&L पातळीवरून futures भावात (trading_engine.futures_price_for_pnl_level) -- अचूक.
- NSE (NIFTY/BANKNIFTY/SENSEX) options: Entry = entry_spot_price (नसेल तर entry_level_price). SL / Target फक्त तीन bots साठी (dynamic_sr_instant,
  classic_sr_reversal, srv2_momentum_reversal), त्यांच्या Spot% नियमावरून -- **सध्याच्या settings** वरून (entry नंतर settings बदलल्या असतील तर
  रेषा चुकीची येऊ शकते => 'अंदाजित'), आणि Premium-Points नियम वेगळा आहे (जे आधी घडेल ते लागू) -- म्हणून ही रेषा फक्त Spot% पातळी दाखवते.
  इतर sources (MANUAL, credit_spread_auto_trader ...) ₹ P&L पातळी वापरतात -- त्यांना चार्टवर भावात बदलता येत नाही => फक्त Entry.
- Trailing stop ची live पातळी जाणूनबुजून नाही (साठवलेली नसते; नंतरच्या टप्प्यात).
"""
import cloud_db
from trading_engine import futures_price_for_pnl_level

ENTRY_COLOR, SL_COLOR, TARGET_COLOR, OVERRIDE_COLOR = "#2962FF", "#F23645", "#089981", "#ff9800"

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


def futures_lines(info):
    """MCX futures trade -> [Entry, SL, Target] रेषा (futures भावात). Manual Override सेट असेल तर तोच SL (वेगळ्या रंगात)."""
    net_credit, lots, lot_size = info.get("net_credit"), info.get("lots"), info.get("lot_size")
    if net_credit is None:
        return []
    lines = [_line(abs(net_credit), "Entry", ENTRY_COLOR, dashed=False)]
    override = info.get("manual_sl_override_pnl")
    sl_level = override if override is not None else info.get("sl_pnl_level")
    sl_price = futures_price_for_pnl_level(net_credit, sl_level, lots, lot_size)
    if sl_price is not None:
        lines.append(_line(sl_price, "SL (Manual Override)" if override is not None else "SL", OVERRIDE_COLOR if override is not None else SL_COLOR))
    target_price = futures_price_for_pnl_level(net_credit, info.get("target_pnl_level"), lots, lot_size)
    if target_price is not None:
        lines.append(_line(target_price, "Target", TARGET_COLOR))
    return lines + _trigger_level_line(info, abs(net_credit))


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
        "Premium-Points नियम वेगळा आहे -- Spot% किंवा Premium-Points, जे आधी घडेल तेव्हा exit होतो. Trailing SL इथे दाखवलेला नाही."
    )
