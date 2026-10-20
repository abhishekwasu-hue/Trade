"""paper/engine_entry.py — `signal_source = engine` असलेल्या bot साठी engine चा setup ⇒ (Vision gate + Abhi ✅) ⇒ त्या bot च्याच settings ने
PAPER spread (Abhi P0 #1). Spread selection / strikes / execution: bots चीच existing functions (`strategy.select_credit_spread_itm`,
`select_naked_option_itm`, `trading_engine.open_multi_leg_trade`) — नवीन execution नाही. **फक्त PAPER**; LIVE ⇒ काहीच नाही.
Engine signal एकदाच वापरला जातो (`engine_signal.mark_consumed`); HOLD ⇒ पुढच्या cycle ला पुन्हा (gate चा approval मार्ग).
"""
import contextlib
import os

import pandas as pd

import engine_signal as ES

# Abhi (PAPER at the open): the bot whose ✅ opens its PAPER entry at once (Telegram service) ⇒ its dashboard settings key
BOT_SETTINGS_KEY = {"srv2_momentum_reversal": "15m_dynamic_sr"}


@contextlib.contextmanager
def entry_lock(bot, symbol, data_dir=None):
    """One engine-entry cycle per (bot, symbol) at a time — the bot's cron cycle and the Telegram ✅ path never enter twice. Yields True
    when held, False when another cycle holds it (never blocks)."""
    import fcntl
    if data_dir is None:
        from . import config as PC
        data_dir = PC.data_dir()
    os.makedirs(data_dir, exist_ok=True)
    f = open(os.path.join(data_dir, f"engine_entry_{bot}_{str(symbol).upper()}.lock"), "w")
    try:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
    finally:
        f.close()


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
    # Abhi: the spread's target is the dashboard's "Target — % of net premium" (the bot's own path reads the same key); SL / TSL and the
    # naked exits come from the dashboard at exit time (trading_engine.manage_open_trades). No such key ⇒ the old 100 % (other bots).
    spread_target = float(settings.get("spread_target_pct_of_premium", 100))
    out = []
    if settings.get("credit_spread_enabled", True) and lots > 0:
        sp = select_credit_spread_itm(raw_chain, direction, atm, step=step, itm_depth_points=settings["itm_depth_points"],
                                      hedge_width_points=settings["hedge_width_points"])
        if sp is not None:
            ok, resp = open_fn(access_token, symbol, sp, lots=lots, lot_size=lot_size, **{**common, "target_pct_of_max_profit": spread_target})
            out.append(f"Credit Spread {sp.get('strategy', direction)}: {'✅' if ok else '❌'} {resp}")
    if settings.get("naked_enabled", True) and naked_lots > 0:
        nk = select_naked_option_itm(raw_chain, direction, atm, itm_depth_points=settings.get("naked_itm_depth_points", settings["itm_depth_points"]),
                                     step=step, hedge_enabled=settings.get("naked_hedge_enabled", False),
                                     hedge_width_points=settings.get("naked_hedge_width_points", 150))
        if nk is not None:
            ok, resp = open_fn(access_token, symbol, nk, lots=naked_lots, lot_size=lot_size, **common)
            out.append(f"Naked {nk.get('strategy', direction)}: {'✅' if ok else '❌'} {resp}")
    return out or ["Credit Spread / Naked बंद किंवा strike सापडला नाही"], spot


def engine_gate_tags(r, direction, settings=None):
    """Engine row ⇒ Vision row tags["gate"]: area = engine चा पट्टा [lo, hi] (Abhi TA4 — एकच किंमत नाही) ⇒ approval caption / chart / Vision
    audit पट्टाच दाखवतात. SL / target / entry इथे नाहीत (✏️ Modify / R:R वर्तन आधीसारखंच). Band नाही ⇒ area नाही (NA).
    band_warn_pts = bot settings चे `approval_band_warn_pts` (default 150): caption पट्ट्याची रुंदी त्यापेक्षा जास्त ⇒ "merged band — check"
    ओळ दाखवतो — फक्त दाखवणं, निर्णय / gate / order ला हात नाही."""
    from bots_common import plain_text as PT
    import json
    try:
        pay = json.loads(r.get("payload") or "{}")
    except (TypeError, ValueError):
        pay = {}
    lo, hi = r.get("level_lo"), r.get("level_hi")
    area = sorted([float(lo), float(hi)]) if lo is not None and hi is not None else None
    return {"mode": "engine", "side": direction, "area": area, "grade": r.get("grade"), "tf": "15M",
            "trend": pay.get("trend_used") or pay.get("daily_trend"), "form": pay.get("commitment_form"),
            "band_warn_pts": PT.band_warn_pts(settings)}


def process(bot, access_token, symbol, settings, lot_size, source, now=None, has_open=None, gate_fn=None, open_fn=None, chain=None,
            path=None, cutoff=None, vpath=None, symbols_fn=None):
    """engine mode चा एक cycle. रिटर्न संदेश (None = engine mode नाही / नवा setup नाही). One cycle per (bot, symbol) at a time
    (`entry_lock`: the cron cycle and the Telegram ✅ path)."""
    if ES.source_of(settings) != "engine":
        return None
    with entry_lock(bot, symbol, os.path.dirname(path) if path else None) as held:
        if not held:
            return f"{symbol}: engine — another entry cycle is running (cron / ✅) ⇒ this one skips"
        return _process(bot, access_token, symbol, settings, lot_size, source, now, has_open, gate_fn, open_fn, chain, path, cutoff,
                        vpath, symbols_fn)


def _process(bot, access_token, symbol, settings, lot_size, source, now, has_open, gate_fn, open_fn, chain, path, cutoff, vpath,
             symbols_fn):
    now = ES._naive(now or ES.now_ist())
    if str(settings.get("trading_mode", "PAPER")).upper() != "PAPER":
        return f"{symbol}: signal_source = engine फक्त PAPER साठी — {settings.get('trading_mode')} ⇒ entry नाही"
    if symbols_fn is None:
        import cloud_db
        symbols_fn = cloud_db.get_signal_symbols
    if str(symbol).upper() not in [str(x).upper() for x in symbols_fn()]:   # dashboard signal_symbols बाहेर (उदा. SENSEX) ⇒ approval / entry नाही
        return f"{symbol}: signal_symbols मध्ये नाही (dashboard) ⇒ engine entry नाही"
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
                    tags={"engine": True, "engine_bar": r["bar_ts"], "engine_grade": r.get("grade"), "gate": engine_gate_tags(r, direction, settings)},
                    path=vpath)
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


def enter_now(bot, symbol, send=None, settings_fn=None, token_fn=None, cycle_fn=None):
    """Abhi (PAPER at the open): on ✅ the PAPER entry is placed at once — the Telegram service runs the bot's own engine cycle for that
    symbol (`bot_hooks.pre_cycle`: instrument / token / lot size / pause ⇒ `process` ⇒ gate ENTER ⇒ `open_paper` with the dashboard's
    lots / strikes / target). The same lock as the cron cycle ⇒ never two entries. PAPER only (pre_cycle / process refuse LIVE). Never
    raises; returns the cycle's message (None = not an engine bot)."""
    key = BOT_SETTINGS_KEY.get(bot)
    if key is None:
        return None
    try:
        if settings_fn is None:
            import cloud_db
            settings_fn = cloud_db.get_strategy_settings
        settings = settings_fn(key, symbol)
        if str(settings.get("trading_mode", "PAPER")).upper() != "PAPER":
            msg = f"{symbol}: {settings.get('trading_mode')} ⇒ no PAPER entry on ✅ (LIVE never from here)"
        elif not settings.get("symbol_enabled", str(symbol).upper() == "NIFTY"):
            msg = f"{symbol}: 15M SRv2 switched off (symbol_enabled) ⇒ no entry on ✅"
        else:
            if token_fn is None:
                import cloud_db
                token_fn = lambda: cloud_db.get_effective_upstox_token(None)   # noqa: E731
            if cycle_fn is None:
                from . import bot_hooks as BH
                cycle_fn = lambda tok: BH.pre_cycle(bot, tok, symbol, settings, None, source=bot, send=send).msg   # noqa: E731
            msg = cycle_fn(token_fn())
    except Exception as exc:                                             # noqa: BLE001 — the cron cycle still enters on its next minute
        msg = f"{symbol}: PAPER entry on ✅ failed ({type(exc).__name__}: {exc}) ⇒ the bot's next cycle enters"
    if send is not None and msg:
        try:
            send(f"⚡ PAPER on ✅ · {msg}")
        except Exception:                                                # noqa: BLE001
            pass
    return msg

