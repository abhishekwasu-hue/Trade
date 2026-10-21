"""paper/engine_entry.py — `signal_source = engine` असलेल्या bot साठी engine चा setup ⇒ (Vision gate + Abhi ✅) ⇒ त्या bot च्याच settings ने
PAPER spread (Abhi P0 #1). Spread selection / strikes / execution: bots चीच existing functions (`strategy.select_credit_spread_itm`,
`select_naked_option_itm`, `trading_engine.open_multi_leg_trade`) — नवीन execution नाही. **फक्त PAPER**; LIVE ⇒ काहीच नाही.
Engine signal एकदाच वापरला जातो (`engine_signal.mark_consumed`); HOLD ⇒ पुढच्या cycle ला पुन्हा (gate चा approval मार्ग).
Entry models E1–E4 (decision3 rows with payload `entries`): the engine only generates signals — each entry is its own signal
(idempotency key (bot, symbol, visit_id, model) persisted in the engine store, `engine_signal.claim_entry` ⇒ at most one signal per model
per visit; its own Vision card / ✅; `engine3_model_eN_on` = which models produce signals). Execution = today's path and today's
dashboard settings exactly (lots, legs, naked_lots, strikes, SL / target / TSL, one position at a time); the position is tagged
entry_reason_tag "ENGINE_EN" (journal / summary only). Rows without `entries` ⇒ today's single-setup path.
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
               open_fn=None, now=None, reason_tag="ENGINE_SIGNAL"):
    """bot च्या settings ने PAPER spread (+ naked, settings नुसार). रिटर्न (संदेश-यादी, spot). reason_tag = live_trades.entry_reason_tag
    (entry models: "ENGINE_E1" … — the model of the position; display / per-model open check only, exits never read it)."""
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
                  direction=direction, entry_reason_tag=reason_tag)
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
            "band_warn_pts": PT.band_warn_pts(settings), "band_warn_rule": PT.band_warn_rule(settings),   # layer 6b (default points)
            "areas": engine_areas(pay), "reader": engine_reader(pay)}


def engine_reader(pay):
    """Approval card summary (`approval_card_layout = summary`, default classic = today's card): the engine row's own reader facts
    (engine3_live.reader_facts: layer 6a evidence list, ① trend / ③ area, handover form, LTF label) passed through as they are. Not a
    dict (older row, dropped by the payload size cap) ⇒ None ⇒ the card omits those pieces. Never raises."""
    try:
        x = pay.get("reader")
        return dict(x) if isinstance(x, dict) else None
    except Exception:                                                     # noqa: BLE001 — display only
        return None


def engine_areas(pay):
    """Layer 6b: the decision's own areas for the Vision chart (`vision_chart_band_finder = method`, off by default): the traded area +
    the watch list from the engine row payload — {role, lo, hi, tf, state, confluence_label}, one base each, nothing re-found. None when
    the payload carries neither (dropped by the payload size cap, or an older row)."""
    try:                                                                  # a display field must never block an entry (review #355)
        keep = ("id", "role", "lo", "hi", "tf", "state", "confluence_label")
        rows = [x for x in [pay.get("level")] + list(pay.get("watch_list") or []) if isinstance(x, dict) and x.get("lo") is not None]
        if not rows:
            return None
        out, seen = [], set()
        for x in rows:
            k = repr((x.get("id"), x.get("lo"), x.get("hi")))                 # repr: an unhashable id cannot raise
            if k not in seen:
                seen.add(k)
                out.append({k2: x.get(k2) for k2 in keep})
        return out
    except Exception as exc:                                               # noqa: BLE001 — display only ⇒ NA, logged once
        global _AREAS_WARNED
        if not _AREAS_WARNED:
            _AREAS_WARNED = True
            print(f"⚠️ engine_areas (display only, ignored): {type(exc).__name__}: {str(exc)[:120]}")
        return None


_AREAS_WARNED = False


def process(bot, access_token, symbol, settings, lot_size, source, now=None, has_open=None, gate_fn=None, open_fn=None, chain=None,
            path=None, cutoff=None, vpath=None, symbols_fn=None):
    """engine mode चा एक cycle. रिटर्न संदेश (None = engine mode नाही / नवा setup नाही). One cycle per (bot, symbol) at a time
    (`entry_lock`: the cron cycle and the Telegram ✅ path). Entry models (rows with `entries`): every pending entry is its own signal
    (`_process_models`); execution = today's path and dashboard settings exactly (has_open = the bot's one-position rule)."""
    if ES.source_of(settings) != "engine":
        return None
    with entry_lock(bot, symbol, os.path.dirname(path) if path else None) as held:
        if not held:
            return f"{symbol}: engine — another entry cycle is running (cron / ✅) ⇒ this one skips"
        return _process(bot, access_token, symbol, settings, lot_size, source, now, has_open, gate_fn, open_fn, chain, path, cutoff,
                        vpath, symbols_fn)


def _cutoff(cutoff):
    if cutoff is None:                                                   # config.yaml paper.entry_cutoff (manual सारखंच; code मध्ये आकडा नाही)
        from . import config as PC
        cutoff = tuple(int(x) for x in str(PC.load()["entry_cutoff"]).split(":"))
    return tuple(cutoff)


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
    ents = ES.pending_entries(bot, symbol, settings, now, path)
    if ents is not None:                                                 # decision3 entry models (rows with `entries`)
        return _process_models(bot, access_token, symbol, settings, lot_size, source, now, ents, has_open, gate_fn, open_fn,
                               chain, path, cutoff, vpath)
    r = ES.pending_entry(bot, symbol, settings, now, path)               # older rows (no `entries`) ⇒ today's single-setup path
    if r is None:
        return f"{symbol}: engine — नवा setup नाही ({ES.opinion(symbol, now, path)})"
    d = int(r["direction"])
    direction = ES.DIR_TXT[d]
    cutoff = _cutoff(cutoff)
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


# ------------------------------------------------------------------------------------------------ entry models E1–E4 (decision3 `entries`)
MODEL_DEFAULT_ON = True


def model_key(model, what):
    """Dashboard key: model_key("E1", "on") ⇒ "engine3_model_e1_on" (15M SRv2 page, engine block)."""
    return f"engine3_model_{str(model).lower()}_{what}"


def model_on(settings, model):
    """Dashboard `engine3_model_eN_on` (default True) — a SIGNAL switch only (which models produce signals / cards); execution never
    reads it. "false" / "0" / "no" / "off" ⇒ False; None / "" ⇒ default. Never raises."""
    v = (settings or {}).get(model_key(model, "on"))
    if v is None or (isinstance(v, str) and not v.strip()):
        return MODEL_DEFAULT_ON
    if isinstance(v, str):
        return v.strip().lower() not in ("false", "0", "no", "off")
    try:
        return bool(v)
    except Exception:                                                    # noqa: BLE001
        return MODEL_DEFAULT_ON


def model_tag(model):
    """live_trades.entry_reason_tag of a model's PAPER position ("ENGINE_E1" …) — journal / summary label only (exits never read it)."""
    return f"ENGINE_{str(model).upper()}"


def _num(x):
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if f == f else None


def entry_area(e):
    """The entry's own area [lo, hi] (sorted) or None."""
    a = e.get("area") if isinstance(e.get("area"), dict) else {}
    lo, hi = _num(a.get("lo")), _num(a.get("hi"))
    return sorted([lo, hi]) if lo is not None and hi is not None else None


def entry_level(r, e):
    """Gate level of one entry: the middle of its area; no area ⇒ its entry_ref; else the row's area (as the single-setup path)."""
    a = entry_area(e)
    if a is not None:
        return (a[0] + a[1]) / 2
    if _num(e.get("entry_ref")) is not None:
        return float(e["entry_ref"])
    if r.get("level_lo") is not None and r.get("level_hi") is not None:
        return (float(r["level_lo"]) + float(r["level_hi"])) / 2
    return float(r.get("entry") or 0)


def entry_gate_tags(r, e, direction, settings=None):
    """One entry ⇒ Vision row tags: today's engine tags (`engine_gate_tags`) with the entry's own area / label, + the model fields the
    card shows (model label, invalidation as info, evidence) and the gate keys (model, visit). Display + dedupe only."""
    g = engine_gate_tags(r, direction, settings)
    a = entry_area(e)
    ar = e.get("area") if isinstance(e.get("area"), dict) else {}
    if a is not None:
        g["area"] = a
        areas = list(g.get("areas") or [])
        if not any(isinstance(x, dict) and _num(x.get("lo")) == a[0] and _num(x.get("hi")) == a[1] for x in areas):
            areas.insert(0, {"id": ar.get("id"), "role": "support" if int(e["direction"]) > 0 else "resistance", "lo": a[0], "hi": a[1],
                             "tf": ar.get("tf"), "state": ar.get("state"), "confluence_label": None})
        g["areas"] = areas
    if e.get("label") in ("A", "B"):
        g["grade"] = e["label"]
    ev = e.get("evidence")
    if isinstance(ev, dict) and ("required" in ev or "confirming" in ev):   # the 6a evidence list in the reader's own shape
        g["reader"] = {**(g.get("reader") or {}), "evidence_list": ev}
    return {"engine": True, "engine_bar": r["bar_ts"], "engine_grade": e.get("label") or r.get("grade"), "gate": g,
            "entry_model": str(e["model"]).upper(), "entry_name": e.get("name") or ES.MODEL_NAMES.get(str(e["model"]).upper()),
            "entry_label": ES.model_label(e), "entry_visit": str(e["visit_id"]), "entry_area_id": ar.get("id"),
            "entry_trigger_ts": None if e.get("trigger_ts") is None else str(e["trigger_ts"]), "entry_ref": e.get("entry_ref"),
            "entry_invalidation": e.get("invalidation"), "entry_evidence": ev}


def _process_models(bot, access_token, symbol, settings, lot_size, source, now, ents, has_open, gate_fn, open_fn, chain, path,
                    cutoff, vpath):
    """Entry models: the engine only generates signals — each pending entry is its own signal (idempotency key, Vision card, ✅);
    execution is today's path with today's dashboard settings (lots / naked_lots / legs / strikes / SL / target / TSL) and today's
    bot-wide one-position rule, checked again for every entry (an entry opened earlier in this cycle counts). One entry's error never
    stops the others. Returns the lines joined."""
    if not ents:
        return f"{symbol}: engine — नवा entry नाही ({ES.opinion(symbol, now, path)})"
    cutoff = _cutoff(cutoff)
    if has_open is None:
        from database import has_open_trade_from_source as has_open
    if gate_fn is None:
        from vision.gate import entry_gate as gate_fn
    box = {"chain": chain}
    out = []
    for r, e in ents:
        try:
            out.append(_one_entry(bot, access_token, symbol, settings, lot_size, source, now, r, e, has_open, gate_fn, open_fn,
                                  box, path, cutoff, vpath))
        except Exception as exc:                                         # noqa: BLE001 — this entry only; no position
            out.append(f"{symbol} {ES.model_label(e)}: त्रुटी ⇒ entry नाही ({type(exc).__name__}: {exc})")
    return "\n".join(out)


def _one_entry(bot, access_token, symbol, settings, lot_size, source, now, r, e, has_open, gate_fn, open_fn, box, path, cutoff,
               vpath):
    m, visit, bar = e["model"], e["visit_id"], r["bar_ts"]
    d = int(e["direction"])
    direction = ES.DIR_TXT[d]
    who = f"{symbol} {ES.model_label(e)} {direction}"

    def done(status):
        ES.claim_entry(bot, symbol, visit, m, status, bar, path)
    if not model_on(settings, m):
        done("SKIPPED_MODEL_OFF")
        return f"{who}: model OFF (dashboard) ⇒ skip"
    if (now.hour, now.minute) >= cutoff:
        done("SKIPPED_CUTOFF")
        return f"{who}: {cutoff[0]}:{cutoff[1]:02d} नंतर नवीन entry नाही"
    if direction == "BULLISH" and not settings.get("bullish_entry_enabled", True) or direction == "BEARISH" and not settings.get("bearish_entry_enabled", True):
        done("SKIPPED_DIRECTION_OFF")
        return f"{who}: त्या दिशेच्या entries बंद"
    if has_open(symbol, source):                                         # today's rule (bot-wide): one position at a time
        return f"{who}: आधीची position उघडी (एका वेळी एकच) ⇒ पुढच्या cycle ला"
    lots = int(settings["lots"]) if settings.get("credit_spread_enabled", True) else 0          # today's dashboard lots / legs
    naked = int(settings.get("naked_lots", settings["lots"])) if settings.get("naked_enabled", True) else 0
    level = entry_level(r, e)
    role = "Support" if d > 0 else "Resistance"
    if box.get("chain") is None:                                         # चालू spot ⇒ gate चा drift guard (one fetch per cycle)
        box["chain"], _why = fetch_chain(access_token, symbol)
    chain = box["chain"]
    spot = float(chain[0]["underlying_spot_price"]) if chain and chain[0].get("underlying_spot_price") is not None else None
    if spot is None:
        return f"{who}: option chain / spot नाही ⇒ पुढच्या cycle ला"
    try:
        g = gate_fn(bot, symbol, "PAPER", direction, level, role, "15M", pd.Timestamp(bar), spot, lots, naked,
                    tags=entry_gate_tags(r, e, direction, settings), path=vpath)
    except Exception as exc:
        return f"{who}: gate त्रुटी ⇒ entry नाही ({exc})"
    if g is None or (g.action == "HOLD" and not getattr(g, "final", False)):
        return f"{who}: Vision / ✅ ची वाट ({getattr(g, 'note', 'gate नाही')})"
    if g.action != "ENTER":
        done(f"NOT_ENTERED_{g.action}")
        return f"{who}: नाकारला ({g.note}) ⇒ entry नाही"
    if not ES.claim_entry(bot, symbol, visit, m, "ENTERING", bar, path):   # at most once per visit per model (persisted)
        return f"{who}: या visit साठी {m} आधीच घेतला ⇒ दुसरी position नाही"
    try:
        msgs, _spot = open_paper(access_token, symbol, settings, direction, level, lot_size, source, "ENGINE", min(lots, g.lots),
                                 min(naked, g.naked_lots), chain=chain, open_fn=open_fn, now=now, reason_tag=model_tag(m))
    except Exception as exc:                                             # noqa: BLE001 — claimed ⇒ never a second try for this visit
        ES.set_entry_status(bot, symbol, visit, m, f"OPEN_FAILED: {type(exc).__name__}: {exc}", path)
        return f"{who}: PAPER open त्रुटी ⇒ position नाही ({type(exc).__name__}: {exc})"
    ES.set_entry_status(bot, symbol, visit, m, "EXECUTED", path)
    try:
        from vision.gate import note_execution
        note_execution(g.signal_id, "; ".join(msgs), vpath)
    except Exception:                                                    # noqa: BLE001
        pass
    return f"{who} ⇒ " + "; ".join(msgs)


def models_summary(day, db_path=None, vpath=None):
    """Entry models of the day: {model: {"cards", "positions", "open", "stopped", "target", "other"}} — cards = Vision signals carrying
    that model (dry-run left out), positions = PAPER trades tagged "ENGINE_EN" (live_trades.entry_reason_tag). Only models with
    activity. Read only; a part that cannot be read stays 0."""
    import sqlite3
    from . import watch as PW
    out = {}

    def slot(m):
        return out.setdefault(m, {"cards": 0, "positions": 0, "open": 0, "stopped": 0, "target": 0, "other": 0})
    try:
        from vision import gate as VG
        from vision import store as VS
        for r in VS.list_signals(day, vpath):
            t = VG._row_tags(r)
            if t.get("entry_model") and not t.get("dry_run"):
                slot(str(t["entry_model"]).upper())["cards"] += 1
    except Exception as exc:                                             # noqa: BLE001
        print(f"⚠️ models_summary (vision): {type(exc).__name__}: {exc}")
    try:
        if db_path is None:
            from config import DB_PATH as db_path
        if os.path.exists(db_path):
            c = sqlite3.connect(db_path, timeout=5)
            try:
                rows = c.execute("SELECT entry_reason_tag, status, exit_reason FROM live_trades WHERE mode='PAPER' "
                                 "AND substr(entry_time,1,10)=? AND entry_reason_tag LIKE 'ENGINE_E%'", (str(day),)).fetchall()
            finally:
                c.close()
            for tag, status, why in rows:
                x = slot(str(tag)[len("ENGINE_"):])
                x["positions"] += 1
                x["open" if str(status).upper() == "OPEN" else PW.exit_kind(why)] += 1
    except Exception as exc:                                             # noqa: BLE001
        print(f"⚠️ models_summary (trades): {type(exc).__name__}: {exc}")
    return dict(sorted(out.items()))


def models_summary_text(day, db_path=None, vpath=None):
    """One plain line for the Telegram summaries (15:45 / /today): "Entry models today: E1 — Aggressive 2 cards, 1 position (open 0,
    stopped 1, target 0) · …". No entry-model activity ⇒ "" (the summary stays today's)."""
    try:
        d = models_summary(day, db_path, vpath)
    except Exception:                                                    # noqa: BLE001 — display only
        return ""
    if not d:
        return ""
    parts = [f"{ES.model_label({'model': m})} {x['cards']} card{'s' if x['cards'] != 1 else ''}, {x['positions']} "
             f"position{'s' if x['positions'] != 1 else ''} (open {x['open']}, stopped {x['stopped']}, target {x['target']}"
             + (f", other exit {x['other']}" if x["other"] else "") + ")" for m, x in d.items()]
    return "<b>Entry models today</b>: " + " · ".join(parts) + "."


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

