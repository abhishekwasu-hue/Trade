"""Opportunity Engine page (PR-1a) — Structure वही (Daily/4H/1H/15M/5M trend state), zones/levels (Level Quality सकट) आणि Structure accuracy CSV.
🎓 फक्त वाचन आणि प्रदर्शन: कुठलाही trade/order/DB write नाही, कुठलाही bot हे वापरत नाही; indicator-मुक्त (फक्त किंमत + ref_range मोजपट्टी).
PR-1a मध्ये पाया (trend state) बरोबर आहे का ते तुम्ही चार्टवर पडताळता — त्यानंतरच bias/detectors/backtest (PR-1b/1c)."""
import hashlib
import json
import os

import numpy as np
import pandas as pd
import streamlit as st

import real_nifty_data
from opportunity_engine import report as R
from opportunity_engine import risk as RISK
from opportunity_engine import backtest as BT
from opportunity_engine import diagnostics as DG
from opportunity_engine.visual_audit import auditor as VA
from opportunity_engine.visual_audit import evaluate as VEV
from opportunity_engine.visual_audit import store as VS
from opportunity_engine import sessions as OE_SESSIONS
from opportunity_engine.bias import apply_gate, resolve_bias
from opportunity_engine.config import EngineConfig
from opportunity_engine.context import build_context
from opportunity_engine.detectors.base import Candidate
from opportunity_engine.config import TF_LABEL
from opportunity_engine.zones import build_levels
from safe_widgets import safe_number_input
from tradingview_chart import build_lightweight_chart_html
from ui_headers import mega_header, sub_header, HDR_BLUE, HDR_TEAL, HDR_PURPLE, HDR_ORANGE
from upstox_api import fetch_candles

SRC_OFFLINE = "Offline NIFTY (खरा डेटा, 2015 → 2024-03-27)"
SRC_LIVE = "Upstox (लाईव्ह, सध्याचा symbol)"
CHART_TFS = ["1d", "4h", "1h", "15m", "5m"]
SUPPORTED_SYMBOLS = ("NIFTY", "BANKNIFTY", "SENSEX")        # NSE/BSE index session (09:15–15:30); MCX (09:00–23:30) साठी session वेगळं — PR-1a मध्ये नाही


@st.cache_resource(show_spinner=False, max_entries=4)
def _offline_bundle(start, end):
    df = real_nifty_data.load_nifty_1min(start, end)
    if df is None or df.empty:
        return None, None
    return R.bundle_from_fine(df)


@st.cache_resource(show_spinner=False, ttl=300, max_entries=4)
def _live_bundle(token_hash, token, symbol, days):
    df5 = fetch_candles(token, symbol, 0, interval="5minute", lookback_days=int(days))
    daily = fetch_candles(token, symbol, 0, interval="day", lookback_days=900)
    if df5 is None or df5.empty:
        return None, None
    return R.bundle_from_live(df5, daily)


@st.cache_resource(show_spinner=False, max_entries=2)
def _run_backtest(start, end, variants, detectors):
    """offline NIFTY 1M -> backtest (warm-up के लिए start से ~2 वर्षं आधीपासून डेटा). जड (cached)."""
    warm = max(pd.Timestamp("2015-01-09"), pd.Timestamp(start) - pd.Timedelta(days=730))
    df = real_nifty_data.load_nifty_1min(warm, end)
    if df is None or df.empty:
        return None
    frames = OE_SESSIONS.build_frames(df)
    bcfg = BT.BacktestConfig(start=start, end=end, variants=tuple(variants), detectors=tuple(detectors))
    return BT.run_backtest(frames, bcfg)


@st.cache_resource(show_spinner=False, max_entries=4)
def _run_diagnostics(start, end, variants, detectors, variant):
    """निदान (फक्त अहवाल) — त्याच cached backtest निकालावर."""
    result = _run_backtest(start, end, variants, detectors)
    if result is None:
        return None
    bcfg = BT.BacktestConfig(start=start, end=end, variants=tuple(variants), detectors=tuple(detectors))
    return DG.run_diagnostics(result.timeline, result.results[variant], variant, bcfg)


DIAG_TABLES = (
    ("check_resim", "तपासणी: exit-management पुन्हा चालवून मूळ R हुबेहूब आला का"),
    ("A_exit_breakdown", "A. Exit प्रकार वितरण (setup-निहाय, सरासरी R)"),
    ("A_win_composition", "A. Wins ची रचना (T1→BE / T1→TRAIL / T1→T2) आणि T2 चं अंतर (R)"),
    ("B_mae_mfe", "B. MAE / MFE (hold दरम्यान आणि EOD पर्यंत, R)"),
    ("B_counterfactual", "B. Counterfactual (फक्त अहवाल): BE न हलवता · partial + BE नाही"),
    ("B_be_followup", "B. BE/TRAIL exit नंतर: मूळ SL आधी T2 गाठलं का"),
    ("C_loss_size", "C. Loss आकार (SL risk pts, slippage वाटा)"),
    ("C_big_losses", "C. −1R पेक्षा मोठे losses — कारणासह"),
    ("D_funnel", "D. Funnel: पूर्वअट → trigger → वेळ-खिडकी → raw → gate → risk → validation → score → selector → घेतलेले"),
    ("D_gate_codes", "D. Gate कोड (सर्व कोड, candidates/दिवस)"),
    ("D_by_year", "D. वर्षनिहाय: पूर्वअट दिवस → raw-candidate दिवस → trades"),
    ("E_d2_by_gap_type", "E. D2: gap प्रकारानुसार"),
    ("E_d2_by_bias", "E. D2: bias नुसार"),
    ("E_d2_time_to_sl", "E. D2: trigger नंतर SL किती वेळात"),
    ("E_d2_virtual_by_gap_type", "E. D2 (gate ने नाकारलेले, virtual): gap प्रकारानुसार"),
)


def _render_backtest_tab(symbol):
    sub_header("🧪 Backtest (D1 Gap-Go · D2 Gap-Fade · D3 Gap-Retest · D6 HTF Zone Pullback · D10 Trap) — खरा offline NIFTY डेटा", HDR_ORANGE)
    st.caption("Live आणि backtest साठी एकच निर्णय-साखळी (gate → risk → validation → score → selector). R-आधारित (spot points; option P&L नाही). Index डेटात volume नाही ⇒ volume 'N/A'. "
               "निकाल जसे आले तसे — ट्यूनिंग नाही. IS = 2015→2021, OOS = 2022→; verdict फक्त अहवाल (OOS ≥30 trades ∧ expectancy>0 ⇒ KEEP).")
    if symbol != "NIFTY":
        st.warning("Backtest साठी offline डेटा फक्त NIFTY चा आहे.")
        return
    c1, c2, c3, c4 = st.columns(4)
    start = c1.date_input("पासून", value=pd.Timestamp("2022-01-01").date(), min_value=pd.Timestamp("2015-06-01").date(), max_value=pd.Timestamp("2024-03-27").date(), key="oe_bt_start")
    end = c2.date_input("पर्यंत", value=pd.Timestamp("2024-03-27").date(), min_value=pd.Timestamp("2015-06-01").date(), max_value=pd.Timestamp("2024-03-27").date(), key="oe_bt_end")
    variants = c3.multiselect("Variants", list(BT.VARIANTS), default=["V1"], key="oe_bt_variants", format_func=lambda v: f"{v}: {BT.VARIANT_TEXT[v]}")
    detectors = c4.multiselect("Detectors", list(BT.DETECTORS), default=list(BT.DETECTORS), key="oe_bt_detectors")
    st.caption("⏱️ लांब कालावधी (उदा. 2015→2024, तिन्ही variants) ≈ 10–15 मिनिटं घेतो. जलद तपासणीसाठी कमी कालावधी/एक variant. पूर्ण निकाल CLI: `python3 run_opportunity_backtest.py`.")
    want_diag = st.checkbox("🔬 निदान पण दाखवा (exit / MAE-MFE / counterfactual / मोठे losses / funnel / D2 — IS आणि OOS वेगळे; वेळ आणखी लागतो)", key="oe_bt_diag")
    if not st.button("▶️ Backtest चालवा", key="oe_bt_run"):
        return
    if not variants or not detectors:
        st.warning("किमान एक variant आणि एक detector निवडा.")
        return
    with st.spinner("Timeline + replay चालू आहे…"):
        result = _run_backtest(pd.Timestamp(start), pd.Timestamp(end), tuple(variants), tuple(detectors))
    if result is None:
        st.warning("या कालावधीचा डेटा मिळाला नाही.")
        return
    sub_header("Variants तुलना", HDR_BLUE)
    st.dataframe(result.comparison, width="stretch", hide_index=True)
    vt = result.variant_tables()
    st.markdown("**§3.4: variants — IS आणि OOS वेगळे** (R साइज-विना; शेवटचा column साइज-सह)")
    st.dataframe(vt["variants_is_oos"], width="stretch", hide_index=True)
    st.markdown("**वर्षनिहाय expectancy R (trades)**")
    st.dataframe(vt["variants_yearwise"], width="stretch", hide_index=True)
    for v in variants:
        tables = result.tables(v)
        r = result.results[v]
        sub_header(f"{v}: {BT.VARIANT_TEXT[v]}", HDR_PURPLE)
        st.dataframe(tables["summary"], width="stretch", hide_index=True)
        st.markdown("**Setup verdict** (OOS ≥ 30 trades ∧ expectancy > 0 ⇒ KEEP; नाहीतर REVIEW — फक्त अहवाल)")
        st.dataframe(tables["verdicts"], width="stretch", hide_index=True)
        st.markdown("**Aligned vs counter-trend (gate ने नाकारलेले, size=0 simulate)**")
        st.dataframe(tables["aligned_vs_counter"], width="stretch", hide_index=True)
        tr = r["trades"]
        if len(tr):
            eq = tr.sort_values("exit_time").assign(equity_R=lambda d: d["r_weighted"].cumsum()).set_index("exit_time")["equity_R"]
            st.line_chart(eq)
        if len(tables["wait_pullback"]):
            st.markdown("**`WAIT_PULLBACK_END` bias असताना** — candidates, टप्पे, घेतलेल्यांचा आणि नाकारलेल्यांचा (virtual) निकाल (IS/OOS वेगळे)")
            st.dataframe(tables["wait_pullback"], width="stretch", hide_index=True)
        with st.expander("Breakdowns — सर्व IS आणि OOS वेगळे (setup / setup×वेळ / bias / Daily state / score / वेळ / वर्ष / exit / gap प्रकार / HTF_WAIT_PULLBACK breakouts)", expanded=False):
            for key in ("by_setup", "by_setup_tod", "by_bias", "by_state_1d", "by_score_bucket", "by_tod", "by_year", "by_gap_type", "by_exit_reason", "wait_pullback_breakouts"):
                if len(tables[key]):
                    st.markdown(f"*{key[3:] if key.startswith('by_') else key}*")
                    st.dataframe(tables[key], width="stretch", hide_index=True)
        with st.expander(f"Trades ({len(tr)})", expanded=False):
            st.dataframe(tr.drop(columns=["commentary"], errors="ignore"), width="stretch", hide_index=True)
            st.download_button("⬇️ Trades CSV", data=tr.to_csv(index=False), file_name=f"oe_{v}_trades.csv", mime="text/csv", key=f"oe_bt_dl_trades_{v}")
        with st.expander(f"Decisions — का घेतलं / का नाकारलं ({len(r['decisions'])})", expanded=False):
            st.dataframe(r["decisions"].drop(columns=["commentary"], errors="ignore"), width="stretch", hide_index=True)
            st.download_button("⬇️ Decisions CSV", data=r["decisions"].to_csv(index=False), file_name=f"oe_{v}_decisions.csv", mime="text/csv", key=f"oe_bt_dl_dec_{v}")
        if len(tr):
            pick = st.selectbox("Trade निवडा (दिवसाचा चार्ट + entry/SL/T1/T2)", list(range(len(tr))), key=f"oe_bt_pick_{v}",
                                format_func=lambda i: f"{tr.iloc[i]['date']:%Y-%m-%d} {tr.iloc[i]['setup']} {tr.iloc[i]['direction']} R={tr.iloc[i]['r']:.2f} ({tr.iloc[i]['exit_reason']})")
            row = tr.iloc[pick]
            day = next((d for d in result.timeline.days if d.date == row["date"]), None)
            if day is not None:
                dfc = day.df5.assign(timestamp=day.df5["bar_start"], volume=0, oi=0)[["timestamp", "open", "high", "low", "close", "volume", "oi"]]
                lines = [{"price": float(row[k]), "title": label, "color": color, "dashed": k != "entry", "width": 2}
                         for k, label, color in (("entry", "Entry", "#2962ff"), ("sl", "SL", "#ff1744"), ("t1", "T1", "#00c853"), ("t2", "T2", "#00bfa5"))]
                st.components.v1.html(build_lightweight_chart_html(dfc, symbol=symbol, timeframe_label="5M", height=500, trade_lines=lines), height=550, scrolling=False)
                st.write(row.get("commentary", ""))
        if want_diag:
            with st.spinner(f"{v}: निदान चालू आहे…"):
                diag = _run_diagnostics(pd.Timestamp(start), pd.Timestamp(end), tuple(variants), tuple(detectors), v)
            with st.expander(f"🔬 {v}: निदान (फक्त अहवाल — नियम/parameters बदलले नाहीत)", expanded=False):
                for key, title in DIAG_TABLES:
                    table = (diag or {}).get(key)
                    if table is not None and len(table):
                        st.markdown(f"**{title}**")
                        st.dataframe(table, width="stretch", hide_index=True)


def _chart_df(frames, tf, bars):
    df = frames[tf].tail(int(bars)).copy()
    df["timestamp"] = df["bar_start"]
    df["oi"] = 0
    return df[["timestamp", "open", "high", "low", "close", "volume", "oi"]]


VISUAL_PNG_ROOT = os.path.join("data", "visual_audit")
VISUAL_CACHE = os.path.join("data", "oe_visual_audit.jsonl")
FEWSHOT_DIR = os.path.join("data", "visual_fewshot")


def _visual_record(cache, audit_date, symbol, tf):
    key = f"{audit_date}|{symbol}|{tf}"
    return next((r for r in VS.read_jsonl(cache) if VS.cache_key(r) == key), None)


def _fewshot_example(rec, feedback, png_path):
    """audit record + वापरकर्त्याचा feedback -> few-shot उदाहरण (chart + योग्य उत्तर). CORRECT ⇒ VALID, WRONG ⇒ SPURIOUS; SHIFT ची दिशा माहीत नाही ⇒ model चंच उत्तर."""
    data = (rec.get("overlay") or {}).get("data") or {}
    verdicts = []
    for v in data.get("verdicts", []):
        lid = next((l["level_id"] for l in rec["labels"] if l["label"] == v["label"]), None)
        fb = feedback.get(lid)
        verdict = "VALID" if fb == "CORRECT" else "SPURIOUS" if fb == "WRONG" else v["verdict"]
        verdicts.append({**v, "verdict": verdict})
    with open(png_path, "rb") as fh:
        img = VA.b64(fh.read())
    return {"image_b64": img, "prompt": VA.overlay_text(rec["symbol"], rec["tf"], rec["labels"], rec.get("engine_state")),
            "answer": {"verdicts": verdicts, "missing": data.get("missing", []), "trend_state": data.get("trend_state", "UNCLEAR"),
                       "agrees_with_engine_state": bool(data.get("agrees_with_engine_state"))}}


def _render_visual_tab(symbol):
    """👁️ Visual Audit (spec §17.6): chart image + levels तक्ता (engine grade, model verdict + कारण, consensus) + feedback + मतभेद + date picker."""
    sub_header("👁️ Visual Audit — गणिताचे levels वि. vision model ची नजर (Dual-Eye)", HDR_PURPLE)
    st.caption("EOD/pre-market run (`run_visual_audit.py`) चे निकाल. `consensus_mode` डीफॉल्ट **off** — फक्त माहिती; तुलना अहवाल (backfill + 3 modes) पाहून तुम्ही mode बदलाल. "
               "Live intraday loop मध्ये API call नाही.")
    dates = VS.load_dates(symbol)
    if not dates:
        st.info("अजून कुठलाही visual audit साठवलेला नाही (किंवा Supabase जोडणी नाही). VPS वर `run_visual_audit.py` चालल्यावर इथे दिसेल.")
        return
    c1, c2 = st.columns(2)
    audit_date = c1.selectbox("तारीख (audit_date)", dates, key="oe_va_date", format_func=lambda d: pd.Timestamp(d).strftime("%d %b %Y"))
    tf = c2.radio("Chart", ["1d", "1h", "15m"], horizontal=True, key="oe_va_tf", format_func=lambda t: TF_LABEL[t])
    df = VS.load_audit(symbol, audit_date)
    feedback, fb_df = VS.load_feedback(symbol)
    png = os.path.join(VISUAL_PNG_ROOT, str(pd.Timestamp(audit_date).date()), f"{symbol}_{tf}_overlay.png")
    if os.path.exists(png):
        st.image(png, caption=f"{symbol} {TF_LABEL[tf]} — engine levels (L1…)", width="stretch")
    else:
        st.caption("Chart image या सर्व्हरवर नाही (images VPS च्या data/visual_audit/ मध्ये साठतात).")
    rows = df[df["tf"] == tf].copy() if df is not None and len(df) else pd.DataFrame()
    if not len(rows):
        st.info("या तारखेला/या chart साठी audit rows नाहीत.")
        return
    rows["तुमचा निर्णय"] = rows["level_id"].map(feedback)
    rows["मतभेद"] = np.where((rows["engine_grade"] == "A") & (rows["model_verdict"] == "SPURIOUS"), "⚠️ A-grade पण model SPURIOUS",
                             np.where((rows["model_verdict"] == "VALID") & (rows["तुमचा निर्णय"] == "WRONG"), "⚠️ model VALID पण तुम्ही WRONG", ""))
    show = rows[["label", "kind", "zone_low", "zone_high", "engine_grade", "model_verdict", "model_reason", "consensus_class", "तुमचा निर्णय", "मतभेद"]]
    st.dataframe(show.sort_values("label"), width="stretch", hide_index=True)
    sub_header("तुमचा feedback (✅ बरोबर / ❌ चूक / ↕ shift)", HDR_TEAL)
    f1, f2 = st.columns([2, 3])
    pick = f1.selectbox("Level", list(rows["level_id"]), key="oe_va_level",
                        format_func=lambda lid: f"{rows.set_index('level_id').loc[lid, 'label']} — {rows.set_index('level_id').loc[lid, 'kind']} "
                                                f"{rows.set_index('level_id').loc[lid, 'zone_low']:,.0f}–{rows.set_index('level_id').loc[lid, 'zone_high']:,.0f}")
    verdict = f1.radio("निर्णय", ["CORRECT", "WRONG", "SHIFT"], horizontal=True, key="oe_va_verdict",
                       format_func=lambda v: {"CORRECT": "✅ बरोबर", "WRONG": "❌ चूक", "SHIFT": "↕ shift"}[v])
    note = f2.text_input("टीप (ऐच्छिक)", key="oe_va_note")
    if f2.button("💾 Feedback साठवा", key="oe_va_save"):
        ok = VS.save_feedback(pick, symbol, tf, verdict, note)
        (st.success if ok else st.error)("Feedback साठवला — पुढच्या दिवसांच्या consensus मध्ये प्राधान्याने." if ok else "Feedback साठवता आला नाही (Supabase?).")
    rec = _visual_record(VISUAL_CACHE, pd.Timestamp(audit_date).date(), symbol, tf)
    if rec is not None and os.path.exists(png) and st.button("📌 हे chart few-shot उदाहरण म्हणून जतन करा (तुमच्या feedback सह)", key="oe_va_fewshot"):
        os.makedirs(FEWSHOT_DIR, exist_ok=True)
        path = os.path.join(FEWSHOT_DIR, f"{pd.Timestamp(audit_date).date()}_{symbol}_{tf}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(_fewshot_example(rec, feedback, png), fh, ensure_ascii=False)
        st.success(f"उदाहरण जतन: {path}. VISUAL_AUDIT_FEWSHOT=<n> ने वापरात (प्रत्येक उदाहरण ≈ 1,200 image + ~400 text input tokens).")
    with st.expander("📈 Evaluate (agreement matrix, तयारी)", expanded=False):
        all_rows = VS.load_audit(symbol)
        ok, msg = VEV.readiness(all_rows)
        (st.success if ok else st.info)(msg)
        mats = VEV.agreement_matrix(all_rows, feedback)
        if len(mats["grade_vs_model"]):
            st.markdown("**Engine grade × model verdict**")
            st.dataframe(mats["grade_vs_model"], width="stretch")
        if mats["model_vs_user"] is not None:
            st.markdown("**Model verdict × तुमचा निर्णय**")
            st.dataframe(mats["model_vs_user"], width="stretch")
        runs = VS.load_runs(symbol, 60)
        if runs is not None and len(runs):
            st.markdown("**Runs (calls / tokens)**")
            st.dataframe(runs, width="stretch", hide_index=True)


def _render_bias_tab(ctx, symbol, price):
    """आजचा bias, Daily veto स्थिती, pullback watch, आणि "candidate tester" (detectors PR-1c मध्ये; तोपर्यंत गृहीत candidate वर gate/risk तपासा)."""
    cfg = EngineConfig()
    bias = resolve_bias(ctx, cfg)
    sub_header("आजचा Bias", HDR_TEAL)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Bias", bias.label)
    m2.metric("Primary HTF", f"{TF_LABEL[cfg.primary_htf]}: {R.STATE_LABEL.get(bias.primary_state, bias.primary_state)}")
    m3.metric("1H पुष्टी", R.STATE_LABEL.get(bias.one_h_state, bias.one_h_state or "—"))
    m4.metric("Daily (veto)", R.STATE_LABEL.get(bias.daily_state, bias.daily_state or "—"))
    st.write(" · ".join(bias.reasons))
    if bias.daily_early_reversal_long or bias.daily_early_reversal_short:
        st.info("Daily CHoCH च्या स्थितीत (early reversal) — veto नाही, पण Structure score मध्ये Daily-aligned गुण अर्धे आणि Daily resistance/supply location rule कडक.")
    watch = None
    if bias.direction:
        from opportunity_engine.bias import pullback_watch_zone
        watch = pullback_watch_zone(ctx, bias.direction)
    if watch:
        st.caption(f"Pullback watch zone (counter-trend breakout आला तर इथे वाट): {watch['zone_low']:,.2f} – {watch['zone_high']:,.2f} ({watch['reason']})")
    sub_header("🧪 Candidate tester (गृहीत trade वर gate + risk plan)", HDR_PURPLE)
    st.caption("Detectors (Gap/Trendline/Zone-Pullback…) PR-1c मध्ये येतील; तोपर्यंत एखादा गृहीत trade टाकून Bias/Gate/Daily-veto/Risk नियम तपासा. कुठलाही order होत नाही.")
    c1, c2, c3, c4, c5 = st.columns(5)
    direction = c1.selectbox("दिशा", ["LONG", "SHORT"], key="oe_t_dir")
    setup = c2.selectbox("Setup", ["D6", "D3", "D4", "D10", "D2", "D7", "D8", "D1", "D5", "D9"], key="oe_t_setup")
    entry = float(c3.number_input("Entry", value=float(round(price, 2)), step=1.0, key="oe_t_entry"))
    default_sl = round(price - 25.0, 2) if direction == "LONG" else round(price + 25.0, 2)
    sl_ref = float(c4.number_input("SL (structural level)", value=float(default_sl), step=1.0, key=f"oe_t_sl_{direction}"))
    kind = c5.selectbox("प्रकार", ["PULLBACK_END", "BREAKOUT", "REVERSAL"], key="oe_t_kind")
    cand = Candidate(setup_id=setup, direction=direction, time=ctx.time, entry=entry, sl_ref=sl_ref, kind=kind)
    gate = apply_gate(cand, bias, ctx, cfg)
    if gate.passed:
        st.success("Gate: पास ✅")
    else:
        st.warning("Gate: नाकारला ❌ — " + " · ".join(f"{c} ({t})" for c, t in zip(gate.codes, gate.reasons)))
        if gate.pullback_in_progress:
            st.info("हा pullback मानला (trade नाही) — PULLBACK_IN_PROGRESS" + (f"; watch zone {gate.watch['zone_low']:,.0f}–{gate.watch['zone_high']:,.0f}" if gate.watch else ""))
    ref = ctx.get("15m").ref_range if ctx.get("15m") else None
    plan = RISK.plan_trade(cand, ctx, cfg, ref, ctx.adr, symbol)
    st.dataframe(pd.DataFrame([{"Entry": plan.entry, "SL (buffer सह)": round(plan.sl, 2), "T1 (1R)": round(plan.t1, 2), "T2": round(plan.t2, 2), "Risk pts": round(plan.risk, 2),
                                "ADR": None if ctx.adr != ctx.adr else round(ctx.adr, 1), "Risk/ADR": None if plan.adr_ratio is None else round(plan.adr_ratio, 2),
                                "HTF अडथळा (R)": None if plan.rr_to_opposing is None else round(plan.rr_to_opposing, 2),
                                "Risk नियम": "ठीक" if plan.ok else ", ".join(plan.rejects)}]), width="stretch", hide_index=True)


def render():
    symbol = st.session_state["symbol"]
    token_input = st.session_state["token_input"]

    mega_header(f"🎯 {symbol} — Opportunity Engine (PR-1a: Structure + Levels)", HDR_BLUE)
    st.caption(
        "Price-action structure (HH/HL/LH/LL, BOS/CHoCH/Reversal) + Supply/Demand/S-R/Gap levels + Level Quality grade — **फक्त वाचन आणि प्रदर्शन**. "
        "कुठलाही trade/order होत नाही, कुठलाही bot हे वापरत नाही. Indicator-मुक्त (EMA/RSI/ATR/Supertrend नाही). "
        "पाया (trend state) चार्टवर तुम्ही पडताळल्यावरच पुढचे टप्पे."
    )
    if symbol not in SUPPORTED_SYMBOLS:
        st.warning(f"Opportunity Engine (PR-1a) फक्त {', '.join(SUPPORTED_SYMBOLS)} साठी (NSE/BSE session 09:15–15:30). {symbol} साठी session वेगळं असल्याने इथे दाखवलं जात नाही.")
        return
    c1, c2 = st.columns([2, 3])
    with c1:
        source = st.radio("डेटा स्रोत", [SRC_OFFLINE, SRC_LIVE], key="oe_source")
    with c2:
        if source == SRC_OFFLINE:
            sc1, sc2 = st.columns(2)
            start = sc1.date_input("पासून", value=pd.Timestamp("2023-04-01").date(), min_value=pd.Timestamp("2015-01-09").date(),
                                   max_value=pd.Timestamp("2024-03-27").date(), key="oe_start")
            end = sc2.date_input("पर्यंत", value=pd.Timestamp("2024-03-27").date(), min_value=pd.Timestamp("2015-01-09").date(),
                                 max_value=pd.Timestamp("2024-03-27").date(), key="oe_end")
        else:
            days = safe_number_input("किती दिवसांचा 5M इतिहास", value=120, min_value=30, max_value=400, step=10, key="oe_days")

    try:
        with st.spinner("Structure journal मोजत आहे..."):
            if source == SRC_OFFLINE:
                if symbol != "NIFTY":
                    st.warning(f"Offline डेटा फक्त NIFTY चा आहे — {symbol} साठी 'Upstox (लाईव्ह)' निवडा.")
                    return
                frames, journal = _offline_bundle(pd.Timestamp(start), pd.Timestamp(end))
            else:
                if not token_input:
                    st.info("⬅️ सुरू करण्यासाठी साईडबारमध्ये तुमचा Upstox Access Token टाका.")
                    return
                frames, journal = _live_bundle(hashlib.sha1(token_input.encode()).hexdigest()[:8], token_input, symbol, days)
        if journal is None:
            st.warning("या कालावधीचा डेटा मिळाला नाही.")
            return
        price = float(frames["15m"]["close"].iloc[-1]) if len(frames.get("15m", [])) else float(frames["5m"]["close"].iloc[-1])
        result = build_levels(journal, frames, symbol, price, fine=frames.get("5m"))
        ctx = build_context(journal, levels=result["levels"], daily_df=frames.get("1d"), price=price, flips=result["rejected"])
        tab_state, tab_bias, tab_chart, tab_events, tab_quality, tab_bt, tab_visual = st.tabs(
            ["🧭 Structure वही", "🎯 Bias / Gate", "📊 चार्ट + Levels", "📋 Events / CSV", "🔎 डेटा गुणवत्ता", "🧪 Backtest", "👁️ Visual Audit"])

        with tab_state:
            sub_header("प्रत्येक Timeframe चा सद्य trend state", HDR_TEAL)
            st.dataframe(R.state_rows(journal), width="stretch", hide_index=True)
            st.caption(
                "State: Uptrend/Downtrend (HH-HL / LH-LL), Pullback (नवीन high नंतर खाली, protected अबाधित), कमजोर = CHoCH (protected level खाली/वर **close**), "
                "Reversal confirm = CHoCH नंतर LH + CHoCH low खाली close, Range = अडकलेले swings. सर्व break फक्त CLOSE ने; wick = SWEEP."
            )
            swing_tf = st.radio("Swings दाखवा", CHART_TFS[:4], index=1, horizontal=True, key="oe_swing_tf", format_func=lambda t: TF_LABEL[t])
            st.dataframe(R.swings_table(journal, swing_tf), width="stretch", hide_index=True)

        with tab_bias:
            _render_bias_tab(ctx, symbol, price)

        with tab_chart:
            tf = st.radio("चार्ट Timeframe", CHART_TFS, index=2, horizontal=True, key="oe_chart_tf", format_func=lambda t: TF_LABEL[t])
            m1, m2, m3 = st.columns(3)
            max_levels = int(m1.number_input("जास्तीत जास्त levels", min_value=2, max_value=30, value=12, step=1, key="oe_max_levels"))
            max_dist = float(m2.number_input("कमाल अंतर %", min_value=0.5, max_value=10.0, value=3.0, step=0.5, key="oe_max_dist"))
            grades = m3.multiselect("Grades", ["A", "B", "C"], default=["A", "B"], key="oe_grades")
            lines, near = R.chart_lines(result["levels"], price, max_levels, max_dist, tuple(grades) or ("A", "B"))
            bars = {"1d": 250, "4h": 300, "1h": 400, "15m": 500, "5m": 500}[tf]
            html = build_lightweight_chart_html(_chart_df(frames, tf, bars), symbol=symbol, timeframe_label=TF_LABEL[tf], height=600, trade_lines=lines)
            st.components.v1.html(html, height=650, scrolling=False)
            st.caption("रेषा: **L#** (क्रमांक खालच्या तक्त्याशी जुळतो) + Grade + TF + प्रकार (DEM/SUP/SR-S/SR-R/KEY/RND/GAP) + Freshness. जाड = A, ठिपक्यांची = B/C. "
                       "रुंद zones ची दुसरी किनार ('↔ outer') बारीक ठिपक्यांत.")
            sub_header("📋 Levels (किंमतीजवळचे, चार्टवर दाखवलेले)", HDR_PURPLE)
            st.dataframe(R.levels_table(near, price), width="stretch", hide_index=True)
            with st.expander("सर्व गुणांकित levels", expanded=False):
                st.dataframe(R.levels_table(result["levels"], price), width="stretch", hide_index=True)
            with st.expander(f"नाकारलेले levels ({len(result['rejected'])}) — का नाकारले", expanded=False):
                st.dataframe(R.levels_table(result["rejected"], price), width="stretch", hide_index=True)
            if result["sweeps"]:
                with st.expander(f"SWEEP (spike wicks) — {len(result['sweeps'])}", expanded=False):
                    st.dataframe(pd.DataFrame(result["sweeps"]), width="stretch", hide_index=True)
            st.download_button("⬇️ Levels CSV", data=R.levels_table(result["levels"] + result["rejected"], price).to_csv(index=False),
                               file_name=f"opportunity_levels_{symbol}.csv", mime="text/csv", key="oe_dl_levels")

        with tab_events:
            sub_header("Structure accuracy CSV (Daily / 4H / 1H)", HDR_ORANGE)
            st.caption("प्रत्येक structure बदल: तारीख (bar_end), TF, event, नवीन state, किंमत, `trigger_bar` (प्रत्यक्ष trigger झालेला bar; reversal मध्ये confirmation bar पेक्षा आधीचा असू शकतो). हे चार्टवर पडताळा.")
            ev_tfs = st.multiselect("TF", ["1d", "4h", "1h", "15m"], default=["1d", "4h", "1h"], key="oe_ev_tfs", format_func=lambda t: TF_LABEL[t])
            table = journal.structure_table(tuple(ev_tfs))
            table = table[table["event"] != "SWEEP"].sort_values("time", ascending=False)
            st.dataframe(table.head(300), width="stretch", hide_index=True)
            st.download_button("⬇️ Structure CSV (Daily/4H/1H)", data=R.structure_csv(journal), file_name=f"opportunity_structure_{symbol}.csv", mime="text/csv", key="oe_dl_structure")

        with tab_bt:
            _render_backtest_tab(symbol)

        with tab_visual:
            _render_visual_tab(symbol)

        with tab_quality:
            sub_header("डेटा गुणवत्ता", HDR_TEAL)
            per_tf, short = R.quality_report(frames)
            st.dataframe(per_tf, width="stretch", hide_index=True)
            st.caption("अपूर्ण (bar_is_full=False) bars: 15:15 चा 30M/1H bar, 13:15 चा 4H bar, आणि लहान/अपूर्ण session चा शेवट — हे ref_range/ADR मध्ये धरले जात नाहीत, पण structure मध्ये सामान्य candle.")
            if len(short):
                st.warning(f"लहान/अपूर्ण sessions ({len(short)}): ADR/ref_range मधून वगळले.")
                st.dataframe(short, width="stretch", hide_index=True)
    except Exception as e:
        st.error(f"Opportunity Engine मध्ये चूक: {type(e).__name__}: {e}")
