"""
page_vision_human_eye.py
------------------------
🎓 "Vision & Human Eye" (docs/VISION_HUMAN_EYE.md, §11.4) — फक्त वाचन. प्रत्येक signal: vision ला पाठवलेली `_sent.png` आणि trade नंतरची
`_outcome.png` (POST-HOC) शेजारी-शेजारी, vision चं मत + कारण, (V1) माझा निर्णय, अंतिम निर्णय आणि निकाल. Filters: तारीख, bot, verdict,
win / loss. CSV export. Disk वापर. हे पान कुठलाही order पाठवत नाही, settings बदलत नाही.
"""
import datetime as dt
import json
import os
import shutil

import pandas as pd
import streamlit as st

from vision import images as IM
from vision import store as VS

COLS = ["signal_ts", "bot", "symbol", "direction", "level", "role", "setup_tf", "mode", "verdict", "confidence", "reason", "algo_decision",
        "human_decision", "final_decision", "result", "realized_pnl", "exit_reason", "cost_usd", "latency_ms", "model", "prompt_version",
        "image_path", "image_sha256", "outcome_path", "signal_id"]
V2_FIELDS = ["htf_trend", "setup_structure", "level_kind", "confluence", "wave_position", "correction_complete", "reversal_touch",
             "reversal_reclaim", "reversal_strength", "reversal_close_location", "room_to_next_level", "time_risk", "false_break_risk",
             "is_breakout_entry", "gap_behaviour", "gap_setup", "line_structure", "line_vs_candles", "rules"]


def flatten(rows):
    """vision_signals rows → तक्ता (reason, outcome उघडून)."""
    out = []
    for r in rows:
        vj = json.loads(r.get("vision_json") or "{}") if r.get("vision_json") else {}
        oj = json.loads(r.get("outcome_json") or "{}") if r.get("outcome_json") else {}
        a = (vj.get("audits") or [{}])[0] if vj.get("audits") else {}
        res = oj.get("result") or ("no_trade" if oj.get("no_trade") else (None if r.get("status") == "DONE" else "n/a"))
        hits = (vj.get("rule_hits") or [{}])[0] or {}
        out.append({**{k: r.get(k) for k in COLS if k in r}, "reason": a.get("reason") or vj.get("error"), "result": res,
                    "realized_pnl": oj.get("realized_pnl"), "exit_reason": oj.get("exit_reason"),
                    **{k: a.get(k) for k in V2_FIELDS if k != "rules"},
                    "rules": ", ".join((hits.get("disagree") or []) + (hits.get("gray") or [])) or None})
    return pd.DataFrame(out, columns=COLS + V2_FIELDS)


def apply_filters(df, start=None, end=None, bots=None, verdicts=None, results=None, versions=None, field=None, values=None):
    if df.empty:
        return df
    d = df["signal_ts"].astype(str).str[:10].map(dt.date.fromisoformat)
    m = pd.Series(True, index=df.index)
    if start is not None:
        m &= d >= start
    if end is not None:
        m &= d <= end
    if bots:
        m &= df["bot"].isin(bots)
    if verdicts:
        m &= df["verdict"].isin(verdicts)
    if results:
        m &= df["result"].fillna("open").isin(results)
    if versions:
        m &= df["prompt_version"].isin(versions)
    if field and values:
        m &= df[field].isin(values)
    return df[m].reset_index(drop=True)


def disk_usage(path):
    p = path if os.path.exists(path) else "/"
    u = shutil.disk_usage(p)
    size = 0
    for root, _, files in os.walk(path) if os.path.exists(path) else []:
        size += sum(os.path.getsize(os.path.join(root, f)) for f in files)
    return 100.0 * u.used / u.total, size / 1e6


def mode_options(bot, trading_mode):
    """UI मध्ये निवडता येणारे modes: LIVE / अज्ञात bot ⇒ फक्त off / shadow / notify (V1 modes दिसतच नाहीत)."""
    from vision import config as VC
    return list(VC.MODES) if str(trading_mode).upper() == "PAPER" else list(VC.V0_MODES)


def render_settings():
    from vision import config as VC
    with st.expander("⚙️ Vision settings (bot-निहाय, बदल-इतिहासासह)"):
        st.caption("V1 modes (auto_veto / human_confirm / veto_then_confirm) फक्त PAPER bots वर — LIVE ला हात नाही. "
                   "Exits नेहमी automatic.")
        for bot, (label, _syms, _d) in VC.BOTS.items():
            cur = VC.load(bot)
            tm = VC.bot_trading_mode(bot)
            opts = mode_options(bot, tm)
            c1, c2, c3 = st.columns([3, 3, 2])
            c1.write(f"**{label}** · `{bot}` · trading mode: {tm}")
            pick = c2.selectbox("vision_mode", opts, index=opts.index(cur["vision_mode"]) if cur["vision_mode"] in opts else 0,
                                key=f"vmode_{bot}", label_visibility="collapsed")
            if c3.button("Save", key=f"vsave_{bot}") and pick != cur["vision_mode"]:
                try:
                    VC.save(bot, {"vision_mode": pick}, "dashboard")
                    st.success(f"{bot}: {pick}")
                except ValueError as exc:
                    st.error(str(exc))
            if cur["vision_mode"] != "off":                               # v2 verdict नियम on / off
                r1, r2, r3 = st.columns([3, 3, 2])
                dis = r1.multiselect("disagree नियम", list(VC.RULE_IDS["v2_disagree_rules"]), default=cur["v2_disagree_rules"],
                                     key=f"vdis_{bot}")
                gry = r2.multiselect("gray नियम", list(VC.RULE_IDS["v2_gray_rules"]), default=cur["v2_gray_rules"], key=f"vgry_{bot}")
                if r3.button("नियम Save", key=f"vrsave_{bot}") and (dis != cur["v2_disagree_rules"] or gry != cur["v2_gray_rules"]):
                    VC.save(bot, {"v2_disagree_rules": dis, "v2_gray_rules": gry}, "dashboard")
                    st.success(f"{bot}: नियम बदलले")
                gcols = st.columns(len(VC.CTX_KEYS) + 1)                  # v2.1 gap / chart सीमा (ATR / median range च्या पटीत)
                vals = {k: gcols[i].number_input(k, value=float(cur[k]), key=f"vg_{bot}_{k}") for i, k in enumerate(VC.CTX_KEYS)}
                if gcols[-1].button("Gap Save", key=f"vgsave_{bot}"):
                    try:
                        VC.save(bot, {k: (int(v) if isinstance(VC.BOT_DEFAULTS[k], int) else v) for k, v in vals.items()}, "dashboard")
                        st.success(f"{bot}: gap सीमा साठवल्या")
                    except ValueError as exc:
                        st.error(str(exc))
        g = VC.load("_global")
        e1, e2 = st.columns([6, 2])
        ev = e1.text_input("Event दिवस (YYYY-MM-DD:नाव; …) — त्या दिवशी vision gray (gap नियम)", "; ".join(g.get("event_days") or []),
                           key="v_event_days")
        if e2.button("Events Save", key="v_event_save"):
            try:
                VC.save("_global", {"event_days": ev}, "dashboard")
                st.success("event दिवस साठवले")
            except ValueError as exc:
                st.error(str(exc))
        hist = VC.history()
        if hist:
            st.dataframe(pd.DataFrame(hist)[["ts", "bot", "by", "new_json"]].tail(20), use_container_width=True, hide_index=True)


def render():
    st.title("👁 Vision & Human Eye")
    st.caption("notify / shadow: vision फक्त माहिती. V1 modes (फक्त PAPER): vision entry थांबवू / अर्धी करू शकतो, वाढवत नाही; exits नेहमी "
               "automatic. डावीकडे vision ला पाठवलेली image (signal पर्यंतच), उजवीकडे trade नंतरचा POST-HOC chart (vision कडे कधीच नाही).")
    try:
        df = flatten(VS.list_signals())
    except Exception as exc:
        st.error(f"vision DB वाचता आली नाही: {exc}")
        return
    render_settings()
    pct, mb = disk_usage(IM.base_dir())
    c1, c2, c3 = st.columns(3)
    c1.metric("Signals (एकूण)", len(df))
    c2.metric("Disk वापर", f"{pct:.0f}%", help="80% वर Telegram इशारा (रात्रीचा archive)")
    c3.metric("visual_audit आकार", f"{mb:.1f} MB")
    if df.empty:
        st.info("अजून कुठलाही signal नोंदलेला नाही.")
        return
    from config import get_ist_today
    today = get_ist_today()
    f1, f2 = st.columns(2)
    rng = f1.date_input("तारीख", (today - dt.timedelta(days=7), today))
    bots = f2.multiselect("Bot", sorted(df["bot"].dropna().unique()))
    f3, f4 = st.columns(2)
    verdicts = f3.multiselect("Verdict", ["agree", "gray", "disagree", "unavailable"])
    results = f4.multiselect("निकाल", ["win", "loss", "open", "no_trade", "n/a"])
    f5, f6, f7 = st.columns(3)
    versions = f5.multiselect("Prompt version", sorted(df["prompt_version"].dropna().unique()))
    field = f6.selectbox("v2 field", [""] + [x for x in V2_FIELDS if x != "rules"])
    values = f7.multiselect("मूल्य", sorted(df[field].dropna().unique()) if field else [])
    start, end = (rng if isinstance(rng, (list, tuple)) and len(rng) == 2 else (None, None))
    v = apply_filters(df, start, end, bots, verdicts, results, versions, field or None, values)
    if not v.empty and v["prompt_version"].notna().any():               # prompt_version नुसार गट (evaluation v1 / v2 वेगळे)
        g = v.groupby(v["prompt_version"].fillna("—")).agg(signals=("signal_id", "count"),
                                                          agree=("verdict", lambda s: int((s == "agree").sum())),
                                                          win=("result", lambda s: int((s == "win").sum())),
                                                          loss=("result", lambda s: int((s == "loss").sum())))
        st.dataframe(g, use_container_width=True)
    st.dataframe(v.drop(columns=["image_path", "outcome_path", "image_sha256"]), use_container_width=True, hide_index=True)
    st.download_button("⬇️ CSV", v.to_csv(index=False).encode("utf-8"), file_name=f"vision_signals_{today}.csv", mime="text/csv")
    for _, r in v.sort_values("signal_ts", ascending=False).head(30).iterrows():
        with st.expander(f"{str(r['signal_ts'])[:16]} · {r['bot']} · {r['symbol']} {r['direction']} · {r['verdict']} · {r['result'] or 'open'}"):
            a, b = st.columns(2)
            if r["image_path"] and os.path.exists(r["image_path"]):
                a.image(r["image_path"], caption="vision ला पाठवलेली (_sent.png)")
            else:
                a.info("_sent.png नाही (chart अपयश / archive नंतर delete)")
            if r["outcome_path"] and os.path.exists(r["outcome_path"]):
                b.image(r["outcome_path"], caption="POST-HOC (_outcome.png) — vision कडे नाही")
            else:
                b.info("Outcome अजून नाही (trade चालू / सापडला नाही)")
            st.write(f"**मत:** {r['verdict']} ({r['confidence']}) — {r['reason'] or ''}")
            if r.get("level_kind"):
                st.caption(f"HTF {r['htf_trend']} · setup {r['setup_structure']} · level {r['level_kind']} · wave {r['wave_position']} · "
                           f"reversal {r['reversal_touch']}/{r['reversal_reclaim']}/{r['reversal_strength']}/{r['reversal_close_location']} · "
                           f"room {r['room_to_next_level']} · time {r['time_risk']} · नियम: {r['rules'] or '—'}")
            st.write(f"**Algo:** {r['algo_decision']} · **माझा निर्णय:** {r['human_decision'] or '— (V1)'} · **अंतिम:** {r['final_decision']} · "
                     f"**P&L:** {r['realized_pnl']} {r['exit_reason'] or ''}")
            st.caption(f"sha256 {r['image_sha256']} · {r['model']} · {r['prompt_version']} · ${r['cost_usd'] or 0:.4f}")
