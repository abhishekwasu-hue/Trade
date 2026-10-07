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


def flatten(rows):
    """vision_signals rows → तक्ता (reason, outcome उघडून)."""
    out = []
    for r in rows:
        vj = json.loads(r.get("vision_json") or "{}") if r.get("vision_json") else {}
        oj = json.loads(r.get("outcome_json") or "{}") if r.get("outcome_json") else {}
        a = (vj.get("audits") or [{}])[0] if vj.get("audits") else {}
        res = oj.get("result") or ("no_trade" if oj.get("no_trade") else (None if r.get("status") == "DONE" else "n/a"))
        out.append({**{k: r.get(k) for k in COLS if k in r}, "reason": a.get("reason") or vj.get("error"), "result": res,
                    "realized_pnl": oj.get("realized_pnl"), "exit_reason": oj.get("exit_reason")})
    return pd.DataFrame(out, columns=COLS)


def apply_filters(df, start=None, end=None, bots=None, verdicts=None, results=None):
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
    return df[m].reset_index(drop=True)


def disk_usage(path):
    p = path if os.path.exists(path) else "/"
    u = shutil.disk_usage(p)
    size = 0
    for root, _, files in os.walk(path) if os.path.exists(path) else []:
        size += sum(os.path.getsize(os.path.join(root, f)) for f in files)
    return 100.0 * u.used / u.total, size / 1e6


def render():
    st.title("👁 Vision & Human Eye")
    st.caption("V0: vision फक्त माहिती — trade निर्णयावर परिणाम नाही. डावीकडे vision ला पाठवलेली image (signal पर्यंतच), उजवीकडे trade नंतरचा "
               "POST-HOC chart (vision कडे कधीच नाही).")
    try:
        df = flatten(VS.list_signals())
    except Exception as exc:
        st.error(f"vision DB वाचता आली नाही: {exc}")
        return
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
    start, end = (rng if isinstance(rng, (list, tuple)) and len(rng) == 2 else (None, None))
    v = apply_filters(df, start, end, bots, verdicts, results)
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
            st.write(f"**Algo:** {r['algo_decision']} · **माझा निर्णय:** {r['human_decision'] or '— (V1)'} · **अंतिम:** {r['final_decision']} · "
                     f"**P&L:** {r['realized_pnl']} {r['exit_reason'] or ''}")
            st.caption(f"sha256 {r['image_sha256']} · {r['model']} · {r['prompt_version']} · ${r['cost_usd'] or 0:.4f}")
