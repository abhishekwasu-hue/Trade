"""paper/watch.py — PAPER trades ची updates + journal (Abhi P0 #4–#6). `trade_monitor` च्या प्रत्येक cycle नंतर (exit निर्णय झाल्यावर)
best-effort चालतो; कधीच raise नाही ⇒ exits च्या मार्गात नाही (exit निर्णय `trading_engine.manage_open_trades` चाच).

  • नवा PAPER trade (bot sources) ⇒ journal row (bot, signal_source, Vision मत + कारण, approver, engine shadow मत, R:R, entry charges)
    + Telegram "entry fill" (legs, किंमती, net credit, max loss, SL / target).
  • उघडा trade ⇒ दर `update_every_min` मिनिटांनी P&L; SL / target च्या `near_alert_pct` % जवळ ⇒ एकदा इशारा.
  • बंद झाला ⇒ exit charges (order_log च्या exit fills वरून) + net P&L ⇒ journal + Telegram "exit" (कारण, gross, charges, net).
किंमती फक्त API (order_log fills / Upstox LTP) मधून — image मधून कधीच नाही.
"""
import json
import os
import sqlite3

import pandas as pd

from . import config as PC
from . import journal as PJ

BOT_OF_SOURCE = {"dynamic_sr_instant": "dynamic_sr_instant", "srv2_momentum_reversal": "srv2_momentum_reversal",
                 "dynamic_sr_instant_srv3_shadow": "srv3_instant", "manual_paper": "manual", "classic_sr_reversal": "classic_sr"}   # manual = ✋ /paper (paper/manual.py)
DRYRUN_SUFFIX = "_dryrun_shadow"                                        # Sunday dry-run trades ("_shadow" ⇒ P&L / kill-switch बेरजेत नाहीत)
BOT_OF_SOURCE.update({f"{k}{DRYRUN_SUFFIX}": v for k, v in list(BOT_OF_SOURCE.items())})
SS_KEY = {"srv3_instant": "srv3_signal_source"}                        # SR V3 चा signal_source मूळ 5-Min settings मध्ये वेगळ्या key ने
BOT_LABEL = {"dynamic_sr_instant": "5-Min Instant", "srv2_momentum_reversal": "15M Dynamic SR", "srv3_instant": "SR V3 (5-Min)",
             "manual": "✋ Manual", "classic_sr": "Classic SR"}


def _db_path():
    from config import DB_PATH
    return DB_PATH


def _now():
    from config import get_ist_now
    t = pd.Timestamp(get_ist_now())
    return t.tz_localize(None) if t.tzinfo else t


def _say(send, text, tag=""):
    try:
        if send is None:
            from notifications import send_telegram_message as send
        send(f"{tag}{text}")
    except Exception as exc:
        print(f"⚠️ paper update पाठवता आला नाही: {exc}")


def _trades(db_path, since_day):
    if not os.path.exists(db_path):
        return []
    c = sqlite3.connect(db_path, timeout=5)
    c.row_factory = sqlite3.Row
    try:
        q = (f"SELECT * FROM live_trades WHERE mode='PAPER' AND source IN ({','.join('?' * len(BOT_OF_SOURCE))}) "
             "AND (status='OPEN' OR trade_date>=?)")
        return [dict(r) for r in c.execute(q, list(BOT_OF_SOURCE) + [since_day]).fetchall()]
    finally:
        c.close()


def _orders(db_path, trade_id):
    c = sqlite3.connect(db_path, timeout=5)
    c.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in c.execute("SELECT * FROM order_log WHERE trade_id=? ORDER BY rowid", (trade_id,)).fetchall()]
    except sqlite3.Error:
        return []
    finally:
        c.close()


def trade_model(t):
    """Engine entry model of a PAPER trade (live_trades.entry_reason_tag "ENGINE_E1" ⇒ "E1"; model C, DECISIONS 32: "ENGINE_C_A_E2" ⇒
    "C-a · E2" — paper/engine_entry.model_tag / tag_slot), else None."""
    tag = str((t or {}).get("entry_reason_tag") or "")
    if tag.startswith("ENGINE_C_"):
        parts = tag[len("ENGINE_C_"):].split("_")
        return f"C-{parts[0].lower()} · {parts[1].upper()}" if len(parts) == 2 and parts[0] and parts[1].upper().startswith("E") else None
    return tag[len("ENGINE_"):] if tag.startswith("ENGINE_E") else None


def _model_parts(model):
    """trade_model ⇒ (model "E2", family "C" | None, sub-model "C-a" | None)."""
    m = str(model or "")
    if " · " in m:
        sub, e = m.split(" · ", 1)
        return e, "C", sub
    return m, None, None


def vision_link(bot, symbol, entry_time, vpath=None, window_min=15, model=None):
    """त्या trade च्या आधीचा EXECUTED vision row (verdict, कारण, approver). नाही ⇒ {}. model (engine entry model) ⇒ फक्त त्याच model चा
    row (एकाच area वर चार cards ⇒ प्रत्येक position ला स्वतःचा)."""
    try:
        from vision import gate as VG
        from vision import store as VS
        t1 = pd.Timestamp(entry_time)
        best = None
        for r in VS.rows_with_status(("EXECUTED",), vpath, 5, bot=bot, symbol=str(symbol).upper()):
            if model is not None:
                tg = VG._row_tags(r)
                m, fam, sub = _model_parts(model)
                if tg.get("entry_model") != m or (str(tg.get("entry_family") or "").upper() or None) != fam or \
                        (fam == "C" and tg.get("entry_sub_model") != sub):
                    continue
            ex = pd.Timestamp(r.get("executed_at") or r.get("decided_at") or r["created_at"])
            if t1 - pd.Timedelta(minutes=window_min) <= ex <= t1 + pd.Timedelta(minutes=1) and (best is None or ex > best[0]):
                best = (ex, r)
        if best is None:
            return {}
        r = best[1]
        return {"vision_signal_id": r["signal_id"], "vision_verdict": r.get("verdict"), "vision_reason": r.get("decision_reason"),
                "approver": r.get("decided_by")}
    except Exception as exc:
        print(f"⚠️ vision link: {exc}")
        return {}


def rr_of(t):
    try:
        sl, tg = float(t.get("sl_pnl_level") or 0), float(t.get("target_pnl_level") or 0)
        return round(tg / abs(sl), 2) if sl < 0 < tg else None
    except (TypeError, ValueError):
        return None


NAKED = ("NAKED_CALL", "NAKED_PUT")


def is_naked(t):
    return str(t.get("strategy") or "").upper() in NAKED


def _num(x):
    return f"{float(x):g}"


# Abhi T-6 (DECISIONS 30, display only): या bots चे exits `trading_engine.manage_open_trades` च्या per-source शाखेत dashboard settings वरून
# (spot % / premium points / TSL / target / next level / EOD / carry-forward) — stored sl_pnl_level (bot ने hard-coded 100% of credit ने
# साठवलेला) ते वापरत नाहीत ⇒ तो "SL" म्हणून कधीच दाखवायचा नाही. Exception: srv2 spread चा target = stored target_pnl_level
# (= spread_target_pct_of_premium × credit, entry वेळी) — engine चा PREMIUM_TARGET तोच तुलना करतो.
# Engine exit source (SHADOW_EXIT_PARENT_SOURCE नंतर) ⇒ settings शाखा. यात नसलेले sources (उदा. "_dryrun_shadow", manual) engine च्या
# generic शाखेत stored ₹ levels वरच बंद होतात ⇒ त्यांच्यासाठी stored levels हेच खरे exits.
ENGINE_SETTINGS_BOT = {"dynamic_sr_instant": "dynamic_sr_instant", "classic_sr_reversal": "classic_sr",
                       "srv2_momentum_reversal": "srv2_momentum_reversal"}
BULLISH = ("BULL_PUT_SPREAD", "NAKED_CALL")                             # trading_engine: direction_bullish = strategy_name in (…)
SRV2_CARRY_CHECK = (15, 10)                                             # trading_engine srv2 spread: `>= (15, 10)` literal (test pins it)


def exit_bot(t):
    """ज्या bot च्या dashboard settings वरून engine हा trade बंद करतो ("dynamic_sr_instant" / "classic_sr" / "srv2_momentum_reversal"),
    stored ₹ levels वर (generic शाखा) ⇒ None."""
    try:
        import trading_engine as TE
        if "entry_level_price" in t and t["entry_level_price"] is None:  # engine: settings शाखा फक्त entry_level_price असल्यास
            return None
        src = str(t.get("source") or "")
        return ENGINE_SETTINGS_BOT.get(TE.SHADOW_EXIT_PARENT_SOURCE.get(src, src))
    except Exception:                                                    # noqa: BLE001
        return None


def _override(t):
    """Positions पानावरचा manual SL override (₹) — engine मध्ये सर्वोच्च प्राधान्य: तो ₹ SL + stored target_level. नाही ⇒ None."""
    v = t.get("manual_sl_override_pnl")
    return float(v) if v is not None else None


def settings_exits(t):
    return exit_bot(t) is not None


def bot_settings(bot, symbol, settings_fn=None):
    """Dashboard settings (run_cycle चाच मार्ग: cloud_db.get_strategy_settings via vision.config.BOT_STRATEGY_KEY). चूक ⇒ None, raise नाही."""
    try:
        if settings_fn is not None:
            return settings_fn(bot, symbol)
        import cloud_db
        from vision import config as VC
        return cloud_db.get_strategy_settings(VC.BOT_STRATEGY_KEY.get(bot, "1m_instant"), symbol)
    except Exception:                                                    # noqa: BLE001
        return None


def _rs(x):
    return f"₹{x:+,.0f}" if x else "₹0"


def _spot(x):
    return f"spot {x:,.1f}" if x is not None else "spot level NA"


def exit_plan(t, bot, ss):
    """Engine च्या शाखेचे आकडे या position साठी (display only): premium points × lots × lot_size ⇒ ₹; spot % ⇒ entry spot पासून spot
    किंमत (option P&L मध्ये थेट ₹ नाही). Engine प्रमाणे: spot anchor = entry_spot_price, नसल्यास entry_level_price. चूक ⇒ KeyError इ. (caller पकडतो)."""
    naked = is_naked(t)
    pre = "naked_" if naked else "spread_"
    qty = _qty(t)                                                        # engine: premium_pnl_points = current_pnl / (lots × lot_size)
    bull = str(t.get("strategy") or "").upper() in BULLISH
    sgn = 1 if bull else -1
    a = t.get("entry_spot_price")
    a = t.get("entry_level_price") if a is None else a
    a = float(a) if a is not None else None

    def lvl(pct, fav):
        return None if a is None else round(a * (1 + sgn * (1 if fav else -1) * float(pct) / 100.0), 1)
    srv2_spread = bot == "srv2_momentum_reversal" and not naked
    pl = {"naked": naked, "qty": qty, "bull": bull, "srv2_spread": srv2_spread,
          "sl_pct": ss[f"{pre}sl_spot_pct"], "sl_pts": float(ss[f"{pre}sl_premium_points"]),
          "tsl_pct": ss[f"{pre}tsl_spot_pct"], "tsl_pts": float(ss[f"{pre}tsl_premium_points"]),
          "trail": bool(ss.get(f"{pre}trailing_sl_enabled")), "trail_pts": float(ss.get(f"{pre}trailing_distance_points") or 0)}
    pl.update(sl_spot=lvl(pl["sl_pct"], False), sl_rs=-pl["sl_pts"] * qty, tsl_spot=lvl(pl["tsl_pct"], True), tsl_rs=pl["tsl_pts"] * qty)
    if srv2_spread:                                                      # PREMIUM_TARGET: current_pnl >= stored target_level
        pct = ss["spread_target_pct_of_premium"]
        credit = float(t.get("net_credit") or 0) * qty
        tg = t.get("target_pnl_level")
        pl.update(tg_pct=pct, tg_rs=float(tg) if tg is not None else credit * float(pct) / 100.0, credit_rs=credit,
                  cf_pct=ss["carry_forward_min_profit_pct"], cf_rs=credit * float(ss["carry_forward_min_profit_pct"]) / 100.0)
    else:
        pl.update(tg_spot_pct=ss[f"{pre}target_spot_pct"], tg_pts=float(ss[f"{pre}target_premium_points"]),
                  tg_spot=lvl(ss[f"{pre}target_spot_pct"], True), tg_rs=float(ss[f"{pre}target_premium_points"]) * qty)
    return pl


def _next_level(t, bot, pl, level_fn):
    """Next-level exit नियम (engine प्रमाणे) + आत्ताचा तो level (best-effort). लागू नाही ⇒ None."""
    tf = str(t.get("entry_timeframe") or "").upper()
    if bot in ("dynamic_sr_instant", "srv3_instant") and tf == "5M":
        tfs, name = ("5M",), "5M"
    elif pl["srv2_spread"]:
        tfs = (t.get("entry_timeframe"),) if t.get("entry_timeframe") else ("15M", "30M", "60M")
        name = t.get("entry_timeframe") or "15M/30M/60M"
    else:
        return None
    txt = f"next {name} S/R level reached ⇒ exit"
    try:
        if t.get("entry_level_price") is not None:
            if level_fn is None:
                import cloud_db
                level_fn = cloud_db.get_next_level_in_direction
            nl = level_fn(t["symbol"], float(t["entry_level_price"]), pl["bull"], timeframe_suffixes=tfs)
            if nl is not None:
                txt += f" (now {_spot(float(nl))})"
    except Exception:                                                    # noqa: BLE001
        pass
    return txt


def _eod_text(t, bot, ss, pl):
    if pl["srv2_spread"]:                                                # carry-forward check (engine: trade_style कोणताही)
        h, m = SRV2_CARRY_CHECK
        return (f"carry-forward check {h}:{m:02d}: P&L below {_num(pl['cf_pct'])}% of credit (₹{pl['cf_rs']:,.0f}) ⇒ exit, "
                f"else carried forward")
    if str(t.get("trade_style") or "INTRADAY").upper() != "INTRADAY":
        return "EOD exit: none (not intraday)"
    if bot == "srv2_momentum_reversal":
        return f"EOD exit {int(ss['naked_eod_hour'])}:{int(ss['naked_eod_minute']):02d} (never carried forward)"
    import trading_engine as TE
    h, m = ((TE.CLASSIC_SR_EOD_HOUR, TE.CLASSIC_SR_EOD_MINUTE) if bot == "classic_sr" else (TE.DYNAMIC_SR_EOD_HOUR, TE.DYNAMIC_SR_EOD_MINUTE))
    return f"EOD exit {h}:{m:02d}"


def exit_rules_text(t, bot, ss, level_fn=None):
    """Entry card: engine खरंच वापरतो ते exits, dashboard मूल्यांसह, प्रत्येक स्वतःच्या unit मध्ये + या position साठी ₹ (Abhi T-1 / T-6,
    display only). Naked आणि spread दोन्ही. Exit logic इथे नाही; कधीच raise नाही."""
    try:
        if not ss:
            return "exits: dashboard settings unavailable"
        bot = exit_bot(t) or bot
        pl = exit_plan(t, bot, ss)
        sl = (f"SL: spot {_num(pl['sl_pct'])}% against or premium −{_num(pl['sl_pts'])} pts "
              f"({_spot(pl['sl_spot'])} · {_rs(pl['sl_rs'])})")
        tsl = f"TSL: spot {_num(pl['tsl_pct'])}% in favour or premium +{_num(pl['tsl_pts'])} pts ⇒ SL to entry"
        if pl["trail"]:
            tsl += f", then trail {_num(pl['trail_pts'])} pts"
        tsl += f" (activates at {_spot(pl['tsl_spot'])} · {_rs(pl['tsl_rs'])}"
        tsl += f"; trail ₹{pl['trail_pts'] * pl['qty']:,.0f})" if pl["trail"] else ")"
        if pl["srv2_spread"]:
            tg = f"target: {_num(pl['tg_pct'])}% of credit ({_rs(pl['tg_rs'])})"
        else:
            tg = (f"target: spot {_num(pl['tg_spot_pct'])}% in favour or premium +{_num(pl['tg_pts'])} pts "
                  f"({_spot(pl['tg_spot'])} · {_rs(pl['tg_rs'])})")
        rules = [sl, tsl, tg]
        nl = _next_level(t, bot, pl, level_fn)
        if nl:
            rules.append(nl)
        return " · ".join(rules + [_eod_text(t, bot, ss, pl)]) + " (whichever first)"
    except Exception as exc:                                             # noqa: BLE001
        return f"exits: dashboard settings (NA: {exc})"


def naked_exit_text(t, bot, ss, level_fn=None):
    """Naked leg (Abhi T-1): exits ₹ level वर नाहीत — dashboard नियम (exit_rules_text)."""
    return exit_rules_text(t, bot, ss, level_fn)


def _stored(x):
    return f"₹{float(x):,.0f}" if x is not None else "—"


def premium_rr(pl):
    """R:R फक्त premium thresholds वरून (target ₹ / premium SL ₹) — stored 100%-credit SL वरून नाही. नाही ⇒ None."""
    try:
        return round(pl["tg_rs"] / abs(pl["sl_rs"]), 2) if pl["sl_rs"] < 0 < pl["tg_rs"] else None
    except (KeyError, TypeError, ZeroDivisionError):
        return None


def exit_status_text(t, bot, ss, p=None):
    """Periodic line / /positions: आत्ताचे खरे exits (TSL स्थिती live_trades.tsl_activated, trail floor peak_pnl वरून — engine प्रमाणे).
    p (चालू P&L ₹) दिला ⇒ प्रत्येक ₹ उंबरठ्यापर्यंतचे अंतर. कधीच raise नाही."""
    try:
        to_sl = (lambda x: f" पर्यंत ₹{p - x:,.0f}") if p is not None else (lambda x: "")       # SL पर्यंत किती जागा
        to_tg = (lambda x: f" पर्यंत ₹{x - p:,.0f}") if p is not None else (lambda x: "")       # target पर्यंत किती बाकी
        ov = _override(t)
        if ov is not None:                                               # engine: override ⇒ फक्त हा ₹ SL + stored target (+ EOD)
            tg = t.get("target_pnl_level")
            return (f"manual SL override {_rs(ov)}{to_sl(ov)} · "
                    + (f"target {_rs(float(tg))}{to_tg(float(tg))}" if tg is not None else "target —"))
        if not ss:
            return "exits: dashboard settings unavailable"
        bot = exit_bot(t) or bot
        pl = exit_plan(t, bot, ss)
        if t.get("tsl_activated"):
            floor = 0.0
            if pl["trail"] and t.get("peak_pnl") is not None:
                floor = max(0.0, float(t["peak_pnl"]) - pl["trail_pts"])   # engine: breakeven (0) आधी, मग peak − distance
            sl = (f"TSL active ⇒ SL trailing +{_num(round(floor, 1))} pts ({_rs(floor * pl['qty'])}){to_sl(floor * pl['qty'])}" if floor > 0
                  else f"TSL active ⇒ SL locked at entry (₹0){to_sl(0.0)}")
        else:
            sl = (f"SL {_spot(pl['sl_spot'])} or premium −{_num(pl['sl_pts'])} pts ({_rs(pl['sl_rs'])}){to_sl(pl['sl_rs'])} · "
                  f"TSL not active (at {_spot(pl['tsl_spot'])} or {_rs(pl['tsl_rs'])})")
        if pl["srv2_spread"]:
            tg = f"target {_num(pl['tg_pct'])}% of credit ({_rs(pl['tg_rs'])}){to_tg(pl['tg_rs'])}"
        else:
            tg = f"target {_spot(pl['tg_spot'])} or premium +{_num(pl['tg_pts'])} pts ({_rs(pl['tg_rs'])}){to_tg(pl['tg_rs'])}"
        return f"{sl} · {tg}"
    except Exception as exc:                                             # noqa: BLE001
        return f"exits: dashboard settings (NA: {exc})"


def near_levels(t, bot, ss):
    """"जवळ" इशाऱ्यांसाठी ₹ उंबरठे — settings-driven bots: फक्त प्रामाणिकपणे ₹ मध्ये मोजता येणारे (premium-points SL, TSL सक्रिय
    नसतानाच; target: premium points / srv2 spread चा credit %). Spot % बाजू watcher कडे spot नसल्याने इशाऱ्यात नाही (exit मात्र engine करतो).
    रिटर्न (sl_rs | None, target_rs | None, sl_label, target_label). इतर (manual / generic) ⇒ stored levels (तेच exits वापरतात)."""
    sl, tg = t.get("sl_pnl_level"), t.get("target_pnl_level")
    if _override(t) is not None:                                         # engine: override सर्व शाखांच्या आधी
        sl = _override(t)
        return sl, tg, f"manual SL override ₹{sl:,.0f}", f"target ₹{float(tg or 0):,.0f}"
    if not settings_exits(t):
        return sl, tg, f"SL ₹{float(sl or 0):,.0f}", f"target ₹{float(tg or 0):,.0f}"
    try:
        pl = exit_plan(t, exit_bot(t), ss) if ss else None
    except Exception:                                                    # noqa: BLE001
        pl = None
    if pl is None:
        return None, None, "", ""
    slv = None if t.get("tsl_activated") else pl["sl_rs"]
    tlab = (f"target {_num(pl['tg_pct'])}% of credit {_rs(pl['tg_rs'])}" if pl["srv2_spread"]
            else f"target premium +{_num(pl['tg_pts'])} pts = {_rs(pl['tg_rs'])}; or {_spot(pl['tg_spot'])}, whichever first")
    return (slv, pl["tg_rs"], f"premium SL −{_num(pl['sl_pts'])} pts = {_rs(pl['sl_rs'])}; or {_spot(pl['sl_spot'])}, whichever first",
            tlab)


def _qty(t):
    return int(t.get("lots") or 0) * int(t.get("lot_size") or 0)


def entry_prices(t, orders):
    legs = PJ.load_legs(t.get("legs_json"))
    n = len(legs)
    ent = {o["instrument_key"]: o.get("fill_price") for o in orders[:n] if o.get("fill_price") is not None}
    return {lg["instrument_key"]: ent.get(lg["instrument_key"], lg.get("ltp")) for lg in legs}


def pnl_now(t, entry_px, ltp):
    """चालू P&L (₹): SELL legs ⇒ (entry − ltp), BUY ⇒ (ltp − entry), × lots × lot_size. LTP नसलेला leg ⇒ None."""
    q = _qty(t) * float(t.get("pnl_multiplier") or 1.0)
    tot = 0.0
    for lg in PJ.load_legs(t.get("legs_json")):
        k = lg["instrument_key"]
        if ltp.get(k) is None or entry_px.get(k) is None:
            return None
        d = float(entry_px[k]) - float(ltp[k])
        tot += d if str(lg.get("transaction_type")).upper() == "SELL" else -d
    return round(tot * q, 2)


def _legs_text(t, entry_px):
    out = []
    for lg in PJ.load_legs(t.get("legs_json")):
        px = entry_px.get(lg["instrument_key"])
        out.append(f"{lg.get('transaction_type')} {lg.get('strike')} {lg.get('option_type') or ''} @ {px if px is not None else 'NA'}")
    return " · ".join(out)


def on_entry(t, orders, send=None, jpath=None, tag="", ss_settings=None, engine_opinion=None, level_fn=None):
    bot = BOT_OF_SOURCE[t["source"]]
    model = trade_model(t)
    link = vision_link(bot, t["symbol"], t["entry_time"], model=model) if model else vision_link(bot, t["symbol"], t["entry_time"])
    if engine_opinion is None:
        try:
            import engine_signal as ES
            engine_opinion = ES.opinion(t["symbol"], t["entry_time"])
        except Exception as exc:
            engine_opinion = f"engine: NA ({exc})"
    src = "own"
    try:
        import engine_signal as ES
        src = ES.source_of(ss_settings or {}, SS_KEY.get(bot, "signal_source"))
    except Exception:
        pass
    rr = rr_of(t)
    if bot == "manual":                                                  # ✋ /paper: signal_source MANUAL, R:R = spot SL / T वरून, profile नोंद
        from . import manual as PM
        src, rr = "MANUAL", PM.rr_for_trade(t["trade_id"], jpath)
        prof = PM.profile_for_trade(t["trade_id"], jpath)
        engine_opinion = f"{engine_opinion} · profile: {prof or '—'}"
    epx = entry_prices(t, orders)
    eo = orders[:len(PJ.load_legs(t.get("legs_json")))] or PJ.legs_orders(PJ.load_legs(t.get("legs_json")), _qty(t), prices=epx)
    ech = PJ.order_charges(eo, t["symbol"])
    lot_size = int(t.get("lot_size") or 0)
    lots = int(t.get("lots") or 0)
    net_credit_total = round(float(t.get("net_credit") or 0) * lots * lot_size, 2)
    max_loss_total = round(abs(float(t.get("max_loss") or 0)) * lots * lot_size, 2)
    row = {"trade_id": t["trade_id"], "bot": bot, "source": t["source"], "symbol": t["symbol"], "signal_source": src,
           "direction": None, "strategy": t.get("strategy"), "engine_opinion": engine_opinion, "rr": rr, "entry_time": t["entry_time"],
           "lots": lots, "lot_size": lot_size, "net_credit": net_credit_total, "max_loss": max_loss_total,
           "sl_pnl_level": t.get("sl_pnl_level"), "target_pnl_level": t.get("target_pnl_level"), "legs_json": t.get("legs_json"),
           "entry_charges": ech, "last_update_at": t["entry_time"], "near_alerts": "[]", "dry_run": 1 if tag else 0, **link}
    PJ.upsert(row, jpath)
    v = link.get("vision_verdict") or "—"
    ml = f" · {_model_label(model)}" if model else ""                 # engine entry model ("E1 — Aggressive")
    if is_naked(t) and settings_exits(t):                                # naked: ₹ target / R:R नाहीत ⇒ premium paid + dashboard नियम
        risk = (f"premium paid ₹{abs(net_credit_total):,.0f}\n"
                f"{naked_exit_text(t, bot, ss_settings, level_fn)}\n")
    elif settings_exits(t):                                              # spread (T-6): stored 100%-credit SL नाही ⇒ engine चे खरे exits
        try:
            prr = premium_rr(exit_plan(t, exit_bot(t), ss_settings)) if ss_settings else None
        except Exception:                                                # noqa: BLE001
            prr = None
        risk = (f"net credit ₹{net_credit_total:,.0f} · max loss ₹{max_loss_total:,.0f} · "
                f"R:R (premium SL) {prr if prr is not None else 'NA'}\n"
                f"{exit_rules_text(t, bot, ss_settings, level_fn)}\n")
    elif is_naked(t) and bot != "manual":                                # generic शाखा (उदा. dry-run): stored ₹ SL हाच exit; target नाही
        risk = f"premium paid ₹{abs(net_credit_total):,.0f} · SL {_stored(t.get('sl_pnl_level'))} (stored ₹ level)\n"
    else:
        risk = (f"net credit ₹{net_credit_total:,.0f} · max loss ₹{max_loss_total:,.0f} · SL ₹{t.get('sl_pnl_level') or 0:,.0f} · "
                f"target ₹{t.get('target_pnl_level') or 0:,.0f} · R:R {row['rr'] if row['rr'] is not None else 'NA'}\n")
    _say(send, f"🟢 <b>PAPER entry</b> · {BOT_LABEL.get(bot, bot)}{ml} · {t['symbol']} {t.get('strategy') or ''}\n"
               f"legs: {_legs_text(t, epx)}\n"
               f"{risk}"
               f"entry charges ₹{ech:,.0f} · Vision: {v} · approver: {link.get('approver') or '—'} · signal_source: {src}\n"
               f"{engine_opinion}", tag)
    return row


def _model_label(model):
    try:
        import engine_signal as ES
        m, fam, sub = _model_parts(model)
        return ES.model_label({"model": m, "family": fam, "sub_model": sub})
    except Exception:                                                    # noqa: BLE001
        return str(model)


def exit_kind(reason):
    """exit_reason ⇒ "target" / "stopped" / "other" (exit_head and the per-model day summary read it the same way)."""
    r = str(reason or "").upper()
    if "TARGET" in r:
        return "target"
    if r in ("SL", "TSL_SL", "PCT_TRAILING_SL", "MANUAL_SL_OVERRIDE") or r.endswith("_SL"):
        return "stopped"
    return "other"


def exit_head(reason):
    """Abhi: SL hit and target hit each read as such on Telegram (any other exit: "PAPER exit")."""
    k = exit_kind(reason)
    if k == "target":
        return "🎯 <b>PAPER target hit</b>"
    if k == "stopped":
        return "🛑 <b>PAPER SL hit</b>"
    return "🔴 <b>PAPER exit</b>"


def on_exit(t, orders, j, send=None, jpath=None, tag=""):
    legs = PJ.load_legs(t.get("legs_json"))
    xo = orders[len(legs):]
    if not xo:                                                           # exit fills नाहीत ⇒ entry किंमतींच्या उलट बाजू (अंदाज) — legs वरून
        xo = PJ.legs_orders(legs, _qty(t), exit_=True)
    xch = PJ.order_charges(xo, t["symbol"])
    gross = float(t.get("realized_pnl") or 0.0)
    net = round(gross - float(j.get("entry_charges") or 0.0) - xch, 2)
    PJ.upsert({"trade_id": t["trade_id"], "exit_time": t.get("exit_time"), "exit_reason": t.get("exit_reason"), "gross_pnl": gross,
               "exit_charges": xch, "net_pnl": net}, jpath)
    model = trade_model(t)
    ml = f" · {_model_label(model)}" if model else ""                    # engine entry model ("E1 — Aggressive")
    _say(send, f"{exit_head(t.get('exit_reason'))} · {BOT_LABEL.get(j['bot'], j['bot'])}{ml} · {t['symbol']} · कारण: {t.get('exit_reason')}\n"
               f"gross ₹{gross:,.0f} − charges ₹{float(j.get('entry_charges') or 0) + xch:,.0f} ⇒ <b>net ₹{net:,.0f}</b>", tag)
    return net


def on_open(t, orders, j, access_token, now, cfg, send=None, jpath=None, tag="", ltp_fn=None, ss=None):
    """ss = dashboard settings (dict) किंवा ते आणणारं zero-arg callable (फक्त गरज असेल तेव्हाच network)."""
    every = int(cfg.get("update_every_min") or 30)
    near = float(cfg.get("near_alert_pct") or 80) / 100.0
    last = pd.Timestamp(j.get("last_update_at") or t["entry_time"])
    alerts = json.loads(j.get("near_alerts") or "[]")
    bot = j.get("bot") or BOT_OF_SOURCE.get(t.get("source"), "")
    due = now - last >= pd.Timedelta(minutes=every)
    if settings_exits(t):                                                # T-6: stored 100%-credit SL नाही ⇒ dashboard settings वरून
        if not due and "sl" in alerts and "target" in alerts:
            return None
        try:
            ss = ss() if callable(ss) else ss
        except Exception:                                                # noqa: BLE001
            ss = None
    sl, tg, sl_lab, tg_lab = near_levels(t, bot, ss)
    if not due and (sl is None or "sl" in alerts) and (tg is None or "target" in alerts):
        return None
    epx = entry_prices(t, orders)
    if ltp_fn is None:
        from upstox_api import fetch_ltp_map as ltp_fn
    ltp = ltp_fn(access_token, list(epx)) if access_token else {}
    p = pnl_now(t, epx, ltp or {})
    if p is None:
        return None
    msgs = []
    if sl is not None and float(sl) < 0 and p <= near * float(sl) and "sl" not in alerts:
        alerts.append("sl")
        msgs.append(f"⚠️ SL जवळ: P&L ₹{p:,.0f} ({sl_lab})")
    if tg is not None and float(tg) > 0 and p >= near * float(tg) and "target" not in alerts:
        alerts.append("target")
        msgs.append(f"🎯 target जवळ: P&L ₹{p:,.0f} ({tg_lab})")
    upd = {"trade_id": t["trade_id"], "near_alerts": json.dumps(alerts)}
    if due:
        upd["last_update_at"] = str(now)
        if settings_exits(t):                                            # T-6: engine चे खरे exits (TSL स्थितीसह), ₹0 / 100%-credit SL नाही
            msgs.append(f"⏱ P&L ₹{p:,.0f} · {exit_status_text(t, bot, ss, p)}")
        else:                                                            # manual / generic: stored ₹ levels हेच exits; नसलेला ⇒ "—" (₹0 नाही)
            sl_t = f"SL ₹{float(sl):,.0f} पर्यंत ₹{p - float(sl):,.0f}" if sl is not None else "SL —"
            tg_t = f"target ₹{float(tg):,.0f} पर्यंत ₹{float(tg) - p:,.0f}" if tg is not None else "target —"
            msgs.append(f"⏱ P&L ₹{p:,.0f} · {sl_t} · {tg_t}")
    PJ.upsert(upd, jpath)
    if msgs:
        _say(send, f"📊 {BOT_LABEL.get(j['bot'], j['bot'])} · {t['symbol']} {t.get('strategy') or ''}\n" + "\n".join(msgs), tag)
    return p


def run_cycle(access_token, now=None, db_path=None, send=None, jpath=None, cfg=None, ltp_fn=None, tag="", settings_fn=None, spot_fn=None,
              close_fn=None, level_fn=None):
    """एक cycle. रिटर्न {"entries", "exits", "updates"} (मोजणी). कधीच raise नाही. level_fn = next S/R level (default cloud_db, best-effort)."""
    out = {"entries": 0, "exits": 0, "updates": 0}
    try:
        now = pd.Timestamp(now or _now())
        cfg = cfg or PC.load()
        db_path = db_path or _db_path()
        for t in _trades(db_path, (now - pd.Timedelta(days=1)).strftime("%Y-%m-%d")):
            try:
                orders = _orders(db_path, t["trade_id"])
                j = PJ.get(t["trade_id"], jpath)
                bot = BOT_OF_SOURCE[t["source"]]
                memo = {}

                def _ss(_b=bot, _s=t["symbol"], _m=memo):                # एका cycle मध्ये एकदाच, गरज असेल तेव्हाच
                    if "ss" not in _m:
                        _m["ss"] = bot_settings(_b, _s, settings_fn)
                    return _m["ss"]
                if j is None:
                    j = on_entry(t, orders, send, jpath, tag, _ss(), level_fn=level_fn)
                    out["entries"] += 1
                if t["status"] == "OPEN" and BOT_OF_SOURCE[t["source"]] == "manual":
                    from . import manual as PM                           # ✋ तुमचा spot SL / T ⇒ बंद (exit संदेश पुढच्या cycle ला on_exit)
                    if PM.spot_exit(t, access_token, spot_fn, close_fn, jpath, send, tag):
                        continue
                if t["status"] == "OPEN":
                    if on_open(t, orders, j, access_token, now, cfg, send, jpath, tag, ltp_fn, ss=_ss) is not None:
                        out["updates"] += 1
                elif t["status"] == "CLOSED" and not j.get("exit_time"):
                    on_exit(t, orders, j, send, jpath, tag)
                    out["exits"] += 1
            except Exception as exc:
                print(f"⚠️ paper watch ({t.get('trade_id')}): {type(exc).__name__}: {exc}")
    except Exception as exc:
        print(f"⚠️ paper watch: {type(exc).__name__}: {exc}")
    return out


def run_locked(access_token, **kw):
    """Exit-monitor lock **सुटल्यानंतर** बोलवायचं (network calls मुळे पुढचा exit cycle अडू नये); स्वतःचा lock ("paper_watch") ⇒ दोन monitor
    scripts एकाच वेळी ⇒ दुहेरी संदेश / exit नाहीत. कधीच raise नाही."""
    try:
        from process_lock import ProcessLock, ProcessLockHeld
    except Exception as exc:
        print(f"⚠️ paper watch lock: {exc}")
        return None
    try:
        with ProcessLock("paper_watch"):
            if not _due(kw.get("cfg")):                                  # throttle: TSL loop (5 s) मध्ये प्रत्येक cycle ला network नको
                return None
            return run_cycle(access_token, **kw)
    except ProcessLockHeld:
        return None
    except Exception as exc:
        print(f"⚠️ paper watch: {type(exc).__name__}: {exc}")
        return None


def _due(cfg=None, state_path=None, now=None):
    """शेवटच्या run पासून `watch_min_interval_sec` (config.yaml paper) झाले का; झाले ⇒ timestamp नोंदवून True. वाचता / लिहिता आलं नाही ⇒ True."""
    import time
    cfg = cfg or PC.load()
    p = state_path or os.path.join(PC.data_dir(), "paper_watch_last.json")
    t = time.time() if now is None else now
    try:
        with open(p, encoding="utf-8") as f:
            last = float(json.load(f).get("t") or 0)
    except (OSError, ValueError):
        last = 0.0
    if t - last < float(cfg.get("watch_min_interval_sec") or 0):
        return False
    try:
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"t": t}, f)
    except OSError:
        pass
    return True
