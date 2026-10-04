"""opportunity_engine/refresh.py — Structure Journal ची रोजची (EOD) आणि intraday पुन्हा-गणना + साठवणं + 09:00 brief (spec §2.5). कुठलाही order नाही.

🎓 `compute_snapshot()` शुद्ध (DB/network नाही) — Upstox 5M + Daily वरून journal → levels → context → bias. `refresh_symbol()` data-fetch/store/notify *injected* —
त्यामुळे चाचण्या नेटवर्क/DB शिवाय. अपूर्ण इतिहास (failed chunks) असेल तर आजचं साठवणं वगळतो (जुनं, बरोबर असलेलं तसंच राहतं) — refresh_market_zones.py चाच धडा.
Intraday: प्रत्येक closed 15M bar नंतर (script चालवणारा cron). Live आणि backtest साठी journal logic एकच; इथे फक्त "सद्य स्थिती" साठवली जाते.
"""
from dataclasses import dataclass
from typing import Any, Dict, List

import pandas as pd

from . import report as R
from . import store
from .bias import pullback_watch_zone, resolve_bias
from .config import EngineConfig, TF_LABEL
from .context import build_context
from .visual_audit import consensus as CONS
from .zones import build_levels

SYMBOLS = ("NIFTY", "BANKNIFTY", "SENSEX")
STORED_TFS = ("1d", "4h", "1h", "15m")                  # state/events साठवायचे TFs (5M खूप बारीक)
EVENT_LOOKBACK_BARS = {"1d": 600, "4h": 600, "1h": 600, "15m": 400}


@dataclass
class Snapshot:
    frames: Dict[str, Any]
    journal: Any
    levels: List[dict]
    rejected: List[dict]
    sweeps: List[dict]
    context: Any
    bias: Any
    watch: Any
    price: float
    symbol: str
    consensus: Any = None


def compute_snapshot(df_5m, df_daily, symbol, cfg=None, now=None, visual_records=None, feedback=None):
    """Upstox 5M + Daily -> Snapshot. बंद झालेल्या bars फक्त (`now` नंतरचे वगळले).
    `cfg.consensus_mode` off नसेल तर आजचे visual audit records (EOD/pre-market run चे; इथे API call नाही) + feedback वरून Dual-Eye consensus levels."""
    cfg = cfg or EngineConfig()
    frames, journal = R.bundle_from_live(df_5m, df_daily, cfg, now=now)
    if "5m" not in frames or frames["5m"].empty:
        raise ValueError("5M डेटा रिकामा आहे")
    price = float(frames["5m"][frames["5m"]["bar_closed"]]["close"].iloc[-1])
    res = build_levels(journal, frames, symbol, price, cfg, fine=frames["5m"])
    levels, consensus_info = res["levels"], None
    if cfg.consensus_mode != "off":
        pool = [z for z in res["rejected"] if z.get("status") != "BROKEN" and z.get("kind") in ("DEMAND", "SUPPLY", "SUPPORT", "RESISTANCE")]
        levels, consensus_info = CONS.apply(res["levels"], pool, visual_records or [], cfg.consensus_mode, feedback)
    ctx = build_context(journal, levels=levels, daily_df=frames.get("1d"), price=price, cfg=cfg, flips=res["rejected"])
    bias = resolve_bias(ctx, cfg)
    watch = pullback_watch_zone(ctx, bias.direction) if bias.direction else None
    snap = Snapshot(frames, journal, res["levels"], res["rejected"], res["sweeps"], ctx, bias, watch, price, symbol)
    snap.consensus = consensus_info
    return snap


def recent_events(snap, tfs=STORED_TFS):
    """साठवण्यायोग्य tracker events (प्रत्येक TF चे शेवटचे ~N bars मधले)."""
    out = []
    for tf in tfs:
        tr = snap.journal.trackers.get(tf)
        if tr is None:
            continue
        floor = max(len(tr.c) - EVENT_LOOKBACK_BARS.get(tf, 400), 0)
        out += [e for e in tr.events if e["bar_idx"] >= floor and e["type"] in store.EVENT_TYPES_STORED]
    return out


def brief_text(snap, now=None):
    """09:00 ची मराठी "structure वही" (Telegram): प्रत्येक TF चा state + protected, आजचा bias, जवळचे FRESH zones, उघडे gaps, pullback watch."""
    ctx, bias = snap.context, snap.bias
    now = now or ctx.time
    lines = [f"🎯 {snap.symbol} — Opportunity Engine वही ({pd.Timestamp(now).strftime('%d %b %H:%M')})", f"किंमत: {snap.price:,.2f}"]
    for tf in ("1d", "4h", "1h", "15m"):
        st = ctx.get(tf)
        if st is None:
            continue
        prot = f", protected {st.protected:,.0f}" if st.protected is not None else ""
        rng = f", range {st.range_low:,.0f}–{st.range_high:,.0f}" if st.range_high is not None and st.range_low is not None else ""
        lines.append(f"• {TF_LABEL[tf]}: {R.STATE_LABEL.get(st.state, st.state)}{prot}{rng}")
    lines.append(f"Bias: {bias.label} — " + "; ".join(bias.reasons))
    price = snap.price
    fresh = [z for z in snap.levels if z["kind"] in ("DEMAND", "SUPPLY") and z["freshness"] == "FRESH" and z["quality_grade"] in ("A", "B")]
    above = sorted([z for z in fresh if z["low"] > price], key=lambda z: z["low"])[:2]
    below = sorted([z for z in fresh if z["high"] < price], key=lambda z: -z["high"])[:2]
    for label, zs in (("वरचे FRESH zones", above), ("खालचे FRESH zones", below)):
        if zs:
            lines.append(f"{label}: " + ", ".join(f"{TF_LABEL[z['tf']]} {z['kind']} {z['low']:,.0f}–{z['high']:,.0f} ({z['quality_grade']})" for z in zs))
    gaps = [z for z in snap.levels if z["kind"] == "GAP" and z.get("gap_status") in ("UNFILLED", "PARTIAL")]
    if gaps:
        lines.append("उघडे gaps: " + ", ".join(f"{z['low']:,.0f}–{z['high']:,.0f} ({z['gap_status']})" for z in gaps[:3]))
    if snap.watch:
        w = snap.watch
        lines.append(f"Pullback watch zone: {w['zone_low']:,.0f}–{w['zone_high']:,.0f} ({w['reason']})")
    lines.append("⚠️ फक्त माहिती — कुठलाही trade होत नाही.")
    return "\n".join(lines)


VISUAL_CACHE = "data/oe_visual_audit.jsonl"


def _visual_inputs(symbol, cfg, now):
    """consensus_mode off नसेल तेव्हाच: आजचे visual records (स्थानिक JSONL — run_visual_audit.py चा) + Supabase feedback."""
    if cfg.consensus_mode == "off":
        return None, None
    from .visual_audit import store as VS
    day = pd.Timestamp(now if now is not None else pd.Timestamp.now()).normalize()
    recs = [r for r in VS.read_jsonl(VISUAL_CACHE) if r.get("symbol") == symbol and pd.Timestamp(r["audit_date"]).normalize() == day]
    fb, _ = VS.load_feedback(symbol)
    return recs, fb


def _failed(df):
    return df is not None and getattr(df, "attrs", {}).get("failed_chunks", 0) > 0


def refresh_symbol(symbol, token, fetch, store_mod=store, cfg=None, now=None, mode="eod", notify=None, send_brief=False, dry_run=False, conn_factory=None):
    """एका symbol साठी: fetch → compute → (dry_run नसेल तर) साठवणं → ऐच्छिक brief. `fetch(token, symbol, interval, lookback_days)` -> DataFrame.
    रिटर्न (ok, संदेश)."""
    cfg = cfg or EngineConfig()
    five_days, daily_days = (180, 900) if mode == "eod" else (120, 900)
    df5 = fetch(token, symbol, "5minute", five_days)
    daily = fetch(token, symbol, "day", daily_days)
    if df5 is None or df5.empty:
        return False, f"{symbol}: 5M डेटा मिळाला नाही — काहीही साठवलं नाही"
    if _failed(df5) or _failed(daily):
        return False, f"{symbol}: इतिहासाचे काही chunks मिळाले नाहीत — या वेळचं साठवणं वगळलं (जुनंच कायम राहील)"
    try:
        vis, fb = _visual_inputs(symbol, cfg, now)
        snap = compute_snapshot(df5, daily, symbol, cfg, now=now, visual_records=vis, feedback=fb)
        if snap.consensus and snap.consensus.get("fallback") and notify is not None:
            notify(f"⚠️ {symbol}: consensus_mode=gate पण आजचा visual run उपलब्ध नाही — आज score mode वर fallback.")
    except Exception as exc:                                            # अपुरा/विचित्र डेटा — exception बाहेर नाही
        return False, f"{symbol}: गणना अयशस्वी ({type(exc).__name__}: {exc})"
    summary = f"{symbol}: bias {snap.bias.label}; levels {len(snap.levels)} (नाकारलेले {len(snap.rejected)}); " + ", ".join(
        f"{TF_LABEL[tf]} {snap.context.state_name(tf)}" for tf in ("1d", "4h", "1h") if snap.context.state_name(tf))
    if dry_run:
        return True, summary + " [dry-run: साठवलं नाही]"
    if not store_mod.ensure_tables(conn_factory):
        return False, f"{symbol}: Supabase जोडणी/tables अयशस्वी — साठवलं नाही"
    old_zones = store_mod.load_zones(symbol, conn_factory)
    states = [snap.journal.snapshot(tf) for tf in STORED_TFS if tf in snap.journal.trackers and snap.journal.trackers[tf].c]
    all_zones = snap.levels + snap.rejected
    events = recent_events(snap) + store.zone_transition_events(symbol, old_zones if old_zones is not None else None, all_zones, snap.context.time)
    ok_state = store_mod.save_structure_state(symbol, states, conn_factory)
    ok_zones = store_mod.save_zones(symbol, all_zones, conn_factory)
    n_events = store_mod.append_events(symbol, events, conn_factory)
    if not (ok_state and ok_zones):
        return False, f"{symbol}: साठवणं अर्धवट अयशस्वी (state={ok_state}, zones={ok_zones})"
    if send_brief and notify is not None:
        notify(brief_text(snap))
    return True, summary + f"; नवीन events {n_events}"
