"""page_backtest_review.py — "Backtest Review" पान (TRADE_BACKTEST_VISUAL_REVIEW_PROMPT §3). फक्त वाचन + Abhi च्या review नोंदी; bot / orders
ला हात नाही.

Images आणि `run_index.json` VPS archive मध्ये (`BACKTEST_REVIEW_DIR`, default /root/trade-data/backtest_review) — प्रत्येक run एक folder
(2026_q3, 2024_q1). तारीख निवडा ⇒ दिवसाचे 1H + 15M charts आणि त्या दिवसाचे trades (प्रत्येकी 1H context, 15M entry, hindsight).
प्रत्येक दिवस / trade: ✔ बरोबर / ✘ चूक / ? अस्पष्ट + कारण; दिवसासाठी "सुटलेला trade" (वेळ + side). Supabase `backtest_review`.
Filters: फक्त trades / फक्त ✘ / फक्त न तपासलेले; प्रगती "x/y दिवस तपासले". Mobile: एक column, मोठी images.
"""
import json
import os

import pandas as pd
import streamlit as st

from backtest_review import store as BS

BASE = os.environ.get("BACKTEST_REVIEW_DIR", "/root/trade-data/backtest_review")
MARK = {"OK": "✔", "WRONG": "✘", "UNCLEAR": "?"}
STATUS = {"ENTRY": "✅", "C": "🟡", "REJECTED": "✖"}


def runs(base=BASE):
    if not os.path.isdir(base):
        return []
    return sorted(d for d in os.listdir(base) if os.path.exists(os.path.join(base, d, "run_index.json")))


def load_index(run, base=BASE):
    with open(os.path.join(base, run, "run_index.json"), encoding="utf-8") as fh:
        return json.load(fh)


def filter_days(index, reviews, mode):
    """mode: "सगळे" / "फक्त trades" / "फक्त ✘" / "फक्त न तपासलेले"."""
    out = []
    for d in index.get("days", []):
        ids = [d["item_id"]] + [t["item_id"] for t in d.get("trades", [])]
        if mode == "फक्त trades" and not d.get("trades"):
            continue
        if mode == "फक्त ✘" and not any((reviews.get(i) or {}).get("verdict") == "WRONG" for i in ids):
            continue
        if mode == "फक्त न तपासलेले" and all(i in reviews for i in ids):
            continue
        out.append(d)
    return out


def review_form(item, date, kind, reviews, settings_hash, key, allow_missed=False):
    cur = reviews.get(item) or {}
    st.caption(f"सध्याचं उत्तर: {MARK.get(cur.get('verdict'), '—')} {cur.get('reason') or ''}"
               + (f" · सुटलेला: {cur['missed_trade']['time']} {cur['missed_trade']['side']}" if cur.get("missed_trade") else ""))
    with st.form(key):
        verdict = st.radio("निकाल", ["OK", "WRONG", "UNCLEAR"], index=["OK", "WRONG", "UNCLEAR"].index(cur.get("verdict", "OK")),
                           format_func=lambda v: {"OK": "✔ बरोबर", "WRONG": "✘ चूक", "UNCLEAR": "? अस्पष्ट"}[v], horizontal=True)
        reason = st.text_area("कारण", value=cur.get("reason") or "", height=80)
        missed = None
        if allow_missed:
            c1, c2 = st.columns(2)
            mt = c1.text_input("सुटलेला trade: वेळ (HH:MM)", value=((cur.get("missed_trade") or {}).get("time") or ""))
            ms = c2.selectbox("side", ["—", "bull_put", "bear_call"])
            if mt.strip() and ms != "—":
                missed = {"time": mt.strip(), "side": ms}
        if st.form_submit_button("जतन करा"):
            try:
                ok = BS.save_review(item, date, kind, verdict, reason, missed, settings_hash)
                st.success("जतन झालं") if ok else st.error("Supabase मध्ये साठवता आलं नाही (log पाहा)")
            except ValueError as exc:
                st.error(str(exc))


def _img(run, date, name, base=BASE):
    if name:
        p = os.path.join(base, run, date, name)
        if os.path.exists(p):
            st.image(p, use_container_width=True)
            return
    st.caption("image नाही")


GALLERY_DIR = os.environ.get("GOLDEN_GALLERY_DIR", "/root/trade-data/golden_gallery")
GMARK = {"GOLDEN": "⭐", "OK": "✔", "WRONG": "✘"}


def gallery_groups(index):
    """gallery_index.json ⇒ {G: [examples]} (G1–G6 क्रमाने)."""
    out = {g: [] for g in ("G1", "G2", "G3", "G4", "G5", "G6")}
    for e in index.get("examples", []):
        out.setdefault(e["setup"], []).append(e)
    return out


def render_gallery(base=GALLERY_DIR):
    p = os.path.join(base, "gallery_index.json")
    if not os.path.exists(p):
        st.info(f"Gallery अजून नाही ({base}). VPS वर research/golden_gallery.py चालवा.")
        return
    with open(p, encoding="utf-8") as fh:
        index = json.load(fh)
    rev = BS.load_gallery()
    ex = index.get("examples", [])
    st.metric("निवड", f"{sum(e['id'] in rev for e in ex)}/{len(ex)} तपासले · ⭐ {sum((rev.get(e['id']) or {}).get('verdict') == 'GOLDEN' for e in ex)}",
              help=f"सापडलेले: {index.get('counts')}")
    names = {"G1": "zigzag / ABC end", "G2": "expanded flat spring", "G3": "triangle E-end", "G4": "role flip retest",
             "G5": "ending diagonal C + trendline", "G6": "simple pullback on demand"}
    for g, items in gallery_groups(index).items():
        with st.expander(f"{g} · {names.get(g, '')} ({len(items)})"):
            for e in items:
                cur = rev.get(e["id"]) or {}
                side = {1: "bull_put", -1: "bear_call"}.get(e["side"], e["side"])
                st.markdown(f"**{e['bar_start'][:16]} · {side} · grade {e.get('grade')} ({e.get('total')})** · {GMARK.get(cur.get('verdict'), '·')} — {e['why']}")
                for k in ("1h", "15m", "hind"):
                    if e["pngs"].get(k):
                        st.image(os.path.join(base, e["dir"], e["pngs"][k]), use_container_width=True)
                with st.form(f"gal-{e['id']}"):
                    v = st.radio("निकाल", ["GOLDEN", "OK", "WRONG"], horizontal=True,
                                 index=["GOLDEN", "OK", "WRONG"].index(cur.get("verdict", "OK")),
                                 format_func=lambda x: {"GOLDEN": "⭐ golden", "OK": "✔ ठीक", "WRONG": "✘ चुकीचं ओळखलं"}[x])
                    cs = st.selectbox("हा वेगळा G आहे?", ["—", "G1", "G2", "G3", "G4", "G5", "G6", "none"])
                    reason = st.text_area("कारण", value=cur.get("reason") or "", height=70)
                    if st.form_submit_button("जतन करा"):
                        try:
                            ok = BS.save_gallery(e["id"], g, e["bar_start"], side, v, None if cs == "—" else cs, reason)
                            st.success("जतन झालं") if ok else st.error("Supabase मध्ये साठवता आलं नाही")
                        except ValueError as exc:
                            st.error(str(exc))


def render():
    st.title("🔎 Backtest Review")
    tab_days, tab_gal = st.tabs(["दिवस / trades", "⭐ Golden Gallery"])
    with tab_gal:
        render_gallery()
    with tab_days:
        render_days()


def render_days():
    st.caption("Code ने chart कसा वाचला ते प्रत्येक trade / दिवसासाठी. ✘ ⇒ golden test case. Contaminated / VAL काळ — फक्त logic पडताळणी, tuning नाही.")
    rs = runs()
    if not rs:
        st.info(f"Run सापडला नाही ({BASE}). VPS वर research/backtest_review_run.py चालवा.")
        return
    run = st.selectbox("Run", rs)
    index = load_index(run)
    reviews = BS.load_reviews()
    pg = BS.progress(index, reviews)
    st.metric("प्रगती", f"{pg['days'][0]}/{pg['days'][1]} दिवस · {pg['trades'][0]}/{pg['trades'][1]} trades तपासले",
              help=f"settings hash {index.get('settings_hash')} · {pg['verdicts']}")
    mode = st.radio("Filter", ["सगळे", "फक्त trades", "फक्त ✘", "फक्त न तपासलेले"], horizontal=True)
    days = filter_days(index, reviews, mode)
    if not days:
        st.info("या filter मध्ये दिवस नाहीत.")
        return
    labels = [f"{d['date']} · trades {len(d.get('trades', []))} · {MARK.get((reviews.get(d['item_id']) or {}).get('verdict'), '·')}" for d in days]
    k = st.selectbox("तारीख", range(len(days)), format_func=lambda i: labels[i])
    d = days[k]
    st.markdown(f"**code ची गोष्ट:** {d['story']}")
    _img(run, d["date"], d["pngs"].get("day_1h"))
    _img(run, d["date"], d["pngs"].get("day_15m"))
    with st.expander(f"Candidates ({d['n_candidates']})"):
        st.dataframe(pd.DataFrame([{**c, "status": STATUS.get(c["status"], c["status"]), "codes": ", ".join(c["codes"])}
                                   for c in d.get("candidates", [])]), use_container_width=True, hide_index=True)
    st.subheader("दिवसाचा review")
    review_form(d["item_id"], d["date"], "day", reviews, index.get("settings_hash"), f"day-{run}-{d['date']}", allow_missed=True)
    for t in d.get("trades", []):
        side = {1: "bull_put", -1: "bear_call"}.get(t["side"], t["side"])
        h = t.get("hindsight") or {}
        st.subheader(f"Trade {t['time']} · {side} · grade {t.get('grade')} ({t.get('total')}) · R:R {t.get('rr') and round(t['rr'], 1)} · "
                     f"hindsight {h.get('result')}")
        for kname in ("1h", "15m", "hind"):
            _img(run, d["date"], t["pngs"].get(kname))
        review_form(t["item_id"], d["date"], "trade", reviews, index.get("settings_hash"), f"tr-{run}-{t['item_id']}")
