"""paper/engine_entry.py — `signal_source = engine` असलेल्या bot साठी engine चा setup ⇒ (Vision gate + Abhi ✅) ⇒ त्या bot च्याच settings ने
PAPER spread (Abhi P0 #1). Spread selection / strikes / execution: bots चीच existing functions (`strategy.select_credit_spread_itm`,
`select_naked_option_itm`, `trading_engine.open_multi_leg_trade`) — नवीन execution नाही. **फक्त PAPER**; LIVE ⇒ काहीच नाही.
Engine signal एकदाच वापरला जातो (`engine_signal.mark_consumed`); HOLD ⇒ पुढच्या cycle ला पुन्हा (gate चा approval मार्ग).
"""
import pandas as pd

import engine_signal as ES


def fetch_chain(access_token, symbol):
    """(chain, कारण). आज expiry ⇒ पुढची weekly (bots सारखंच)."""
    from classic_sr_reversal_trader import is_todays_expiry_day
    from upstox_api import fetch_upstox_option_chain
    expiry_index = 1 if is_todays_expiry_day(access_token, symbol) else 0
    return fetch_upstox_option_chain(access_token, symbol, expiry_index=expiry_index)


def open_paper(access_token, symbol, settings, direction, level, lot_size, source, entry_tf, lots, naked_lots, chain=None,
               open_fn=None, now=None):
    """bot च्या settings ने PAPER spread (+ naked, settings नुसार). रिटर्न (संदेश-यादी, spot)."""
    import cloud_db
    from strategy import select_credit_spread_itm, select_naked_option_itm
    if open_fn is None:
        from trading_engine import open_multi_leg_trade as open_fn
    raw_chain = chain
    if raw_chain is None:
        raw_chain, why = fetch_chain(access_token, symbol)
        if not raw_chain:
            return [f"option chain नाही ({why})"], None
    spot = raw_chain[0].get("underlying_spot_price")
    step = cloud_db.STRIKE_STEP.get(symbol, cloud_db.STRIKE_STEP["NIFTY"])
    atm = round(spot / step) * step
    common = dict(sl_pct_of_max_loss=None, target_pct_of_max_profit=100, product_type="D", trading_mode="PAPER", trading_style="INTRADAY",
                  sl_pct_of_credit=100, source=source, entry_level_price=level, entry_timeframe=entry_tf, entry_spot_price=spot,
                  direction=direction, entry_reason_tag="ENGINE_SIGNAL")
    out = []
    if settings.get("credit_spread_enabled", True) and lots > 0:
        sp = select_credit_spread_itm(raw_chain, direction, atm, step=step, itm_depth_points=settings["itm_depth_points"],
                                      hedge_width_points=settings["hedge_width_points"])
        if sp is not None:
            ok, resp = open_fn(access_token, symbol, sp, lots=lots, lot_size=lot_size, **common)
            out.append(f"Credit Spread {sp.get('strategy', direction)}: {'✅' if ok else '❌'} {resp}")
    if settings.get("naked_enabled", True) and naked_lots > 0:
        nk = select_naked_option_itm(raw_chain, direction, atm, itm_depth_points=settings.get("naked_itm_depth_points", settings["itm_depth_points"]),
                                     step=step, hedge_enabled=settings.get("naked_hedge_enabled", False),
                                     hedge_width_points=settings.get("naked_hedge_width_points", 150))
        if nk is not None:
            ok, resp = open_fn(access_token, symbol, nk, lots=naked_lots, lot_size=lot_size, **common)
            out.append(f"Naked {nk.get('strategy', direction)}: {'✅' if ok else '❌'} {resp}")
    return out or ["Credit Spread / Naked बंद किंवा strike सापडला नाही"], spot


def process(bot, access_token, symbol, settings, lot_size, source, now=None, has_open=None, gate_fn=None, open_fn=None, chain=None,
            path=None, cutoff=None, vpath=None):
    """engine mode चा एक cycle. रिटर्न संदेश (None = engine mode नाही / नवा setup नाही)."""
    if ES.source_of(settings) != "engine":
        return None
    now = ES._naive(now or ES.now_ist())
    if str(settings.get("trading_mode", "PAPER")).upper() != "PAPER":
        return f"{symbol}: signal_source = engine फक्त PAPER साठी — {settings.get('trading_mode')} ⇒ entry नाही"
    r = ES.pending_entry(bot, symbol, settings, now, path)
    if r is None:
        return f"{symbol}: engine — नवा setup नाही ({ES.opinion(symbol, now, path)})"
    d = int(r["direction"])
    direction = ES.DIR_TXT[d]
    if cutoff is None:                                                   # config.yaml paper.entry_cutoff (manual सारखंच; code मध्ये आकडा नाही)
        from . import config as PC
        cutoff = tuple(int(x) for x in str(PC.load()["entry_cutoff"]).split(":"))
    if (now.hour, now.minute) >= tuple(cutoff):
        ES.mark_consumed(bot, symbol, r["bar_ts"], "SKIPPED_CUTOFF", path)
        return f"{symbol}: engine setup — {cutoff[0]}:{cutoff[1]:02d} नंतर नवीन entry नाही"
    if direction == "BULLISH" and not settings.get("bullish_entry_enabled", True) or direction == "BEARISH" and not settings.get("bearish_entry_enabled", True):
        ES.mark_consumed(bot, symbol, r["bar_ts"], "SKIPPED_DIRECTION_OFF", path)
        return f"{symbol}: engine setup {direction} — त्या दिशेच्या entries बंद"
    if has_open is None:
        from database import has_open_trade_from_source as has_open
    if has_open(symbol, source):
        return f"{symbol}: engine setup — आधीची position उघडी (एका वेळी एकच)"
    lots = int(settings["lots"]) if settings.get("credit_spread_enabled", True) else 0
    naked = int(settings.get("naked_lots", settings["lots"])) if settings.get("naked_enabled", True) else 0
    level = (float(r["level_lo"]) + float(r["level_hi"])) / 2 if r.get("level_lo") is not None else float(r.get("entry") or 0)
    role = "Support" if d > 0 else "Resistance"
    if gate_fn is None:
        from vision.gate import entry_gate as gate_fn
    g = None
    try:
        if chain is None:                                                # चालू spot ⇒ gate चा drift guard (approve ते entry मधली हालचाल)
            chain, _why = fetch_chain(access_token, symbol)
        spot = float(chain[0]["underlying_spot_price"]) if chain and chain[0].get("underlying_spot_price") is not None else None
        if spot is None:
            return f"{symbol}: engine setup {direction} — option chain / spot नाही ⇒ पुढच्या cycle ला"
        g = gate_fn(bot, symbol, "PAPER", direction, level, role, "15M", pd.Timestamp(r["bar_ts"]), spot, lots, naked,
                    tags={"engine": True, "engine_bar": r["bar_ts"], "engine_grade": r.get("grade")}, path=vpath)
    except Exception as exc:
        return f"{symbol}: engine setup — gate त्रुटी ⇒ entry नाही ({exc})"
    if g is None or (g.action == "HOLD" and not getattr(g, "final", False)):
        return f"{symbol}: engine setup {direction} — Vision / ✅ ची वाट ({getattr(g, 'note', 'gate नाही')})"
    if g.action != "ENTER":
        ES.mark_consumed(bot, symbol, r["bar_ts"], f"NOT_ENTERED_{g.action}", path)
        return f"{symbol}: engine setup {direction} — नाकारला ({g.note}) ⇒ entry नाही"
    msgs, _spot = open_paper(access_token, symbol, settings, direction, level, lot_size, source, "ENGINE", min(lots, g.lots),
                             min(naked, g.naked_lots), chain=chain, open_fn=open_fn, now=now)
    ES.mark_consumed(bot, symbol, r["bar_ts"], "EXECUTED", path)
    try:
        from vision.gate import note_execution
        note_execution(g.signal_id, "; ".join(msgs), vpath)
    except Exception:
        pass
    return f"{symbol}: engine setup {direction} ⇒ " + "; ".join(msgs)
