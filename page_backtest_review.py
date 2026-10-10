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
    """gallery_index.json ⇒ {G: [examples]} (G1–G9 क्रमाने)."""
    from backtest_review import gallery as GL
    out = {g: [] for g in GL.SETUPS}
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
    from backtest_review import gallery as GL
    names = dict(GL.SETUPS)
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
                    cs = st.selectbox("हा वेगळा G आहे?", ["—"] + [f"G{i}" for i in range(1, 10)] + ["none"])
                    reason = st.text_area("कारण", value=cur.get("reason") or "", height=70)
                    if st.form_submit_button("जतन करा"):
                        try:
                            ok = BS.save_gallery(e["id"], g, e["bar_start"], side, v, None if cs == "—" else cs, reason)
                            st.success("जतन झालं") if ok else st.error("Supabase मध्ये साठवता आलं नाही")
                        except ValueError as exc:
                            st.error(str(exc))


def render():
    st.title("🔎 Backtest Review")
    tab_days, tab_gal, tab_exec, tab_cc = st.tabs(["दिवस / trades", "⭐ Golden Gallery", "⚙ Simple Core execution settings",
                                                   "🗺 Chart संकल्पना (MTF)"])
    with tab_exec:
        render_exec_settings()
    with tab_cc:
        render_chart_concepts()
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


EXEC_HELP = {
    "sl_mode": "SL कुठे: structural_invalidation (area / pause चं टोक) · commitment_extreme · fixed_points · percent · none",
    "target_mode": "Target: next_opposite_area · impulse_end · r_multiple (× risk) · premium_pct (option premium) · none",
    "instrument": "credit_spread / futures / naked_buy / naked_sell",
    "strike_mode": "offset_points (trigger ± value) · beyond_sl_points (SL ± value) · sigma (trigger ± value × σ)",
}


def exec_form_values(prev, choose):
    """फॉर्मचे values (Streamlit बाहेर test करता येतं): choose(field, options_or_kind, current) ⇒ value / None. None ⇒ निवडलेलं नाही."""
    from simple_core import settings as SS
    out = {}
    for k, kind in SS.EXEC_FIELDS.items():
        v = choose(k, kind, prev.get(k))
        if v is not None and v != "":
            out[k] = v
    return out


def render_exec_settings():
    """प्रति profile execution settings (Abhi 2026-10-08): engine काहीच गृहीत धरत नाही — इथे निवडलं नसेल तर trade नाही."""
    import streamlit as st
    from simple_core import settings as SS
    st.caption("Simple Core फक्त ENTRY SIGNAL देतो (area + pause + commitment). SL / target / R:R / instrument / strike / lots / expiry "
               "इथून. काही निवडलं नसेल ⇒ trade नाही, स्पष्ट संदेशासह. PAPER फक्त.")
    profs = SS.load_profiles()
    name = st.text_input("Profile (bot / backtest)", value=next(iter(profs), SS.PAPER_PROFILE), key="sc_prof")
    prev = SS.load_profile(name)                                       # paper_core store मध्ये नसेल ⇒ Abhi चे PAPER मूल्य (23:48)
    if name == SS.PAPER_PROFILE and name not in profs:
        st.info("PAPER profile: Abhi चे निर्णय (target_mode impulse_end, g9_tier full, SL structural + 0.25 MR, R:R ≥ 3) — Save केल्यावर store "
                "मध्ये. Instrument / strike / lots निवडा. LIVE ला लागू नाही.")

    def choose(k, kind, cur):
        lab = f"{k}" + (f" — {EXEC_HELP[k]}" if k in EXEC_HELP else "")
        if isinstance(kind, tuple):
            opts = ["(निवडलेलं नाही)"] + list(kind)
            v = st.selectbox(lab, opts, index=opts.index(cur) if cur in opts else 0, key=f"sc_{name}_{k}")
            return None if v == "(निवडलेलं नाही)" else v
        if kind == "bool":
            v = st.selectbox(lab, ["(निवडलेलं नाही)", "on", "off"], index={True: 1, False: 2}.get(cur, 0), key=f"sc_{name}_{k}")
            return None if v.startswith("(") else v == "on"
        if kind == "number":
            v = st.text_input(lab, value="" if cur is None else str(cur), key=f"sc_{name}_{k}")
            try:
                return float(v) if v.strip() else None
            except ValueError:
                st.error(f"{k}: '{v}' हा आकडा नाही — निवडलेलं नाही असं धरलं")
                return None
        return st.text_input(lab, value=cur or "", key=f"sc_{name}_{k}") or None
    with st.form(f"sc_form_{name}"):
        vals = exec_form_values(prev, choose)
        ok = st.form_submit_button("Save")
    if ok:
        try:
            h = SS.save_profile(name, vals)
            st.success(f"Saved · settings hash {h}")
        except ValueError as exc:
            st.error(str(exc))
    st.write(f"सध्याचा hash: `{SS.settings_hash(prev)}` · निवडलेले: {', '.join(sorted(prev)) or '—'}")


def concepts_form_values(cfg, choose):
    """फॉर्मचे values (Streamlit बाहेर test करता येतं): choose(kind, key, current) ⇒ value. रिटर्न पूर्ण chart_concepts dict."""
    from mtf import concepts as CC
    out = {"mode": choose("mode", None, cfg["mode"]), "concepts": {}, "window": {}}
    for k in CC.CONCEPTS:
        cur = cfg["concepts"].get(k) or {}
        out["concepts"][k] = {"show": bool(choose("show", k, cur.get("show", True))), "tier": choose("tier", k, cur.get("tier", CC.CONCEPTS[k][2]))}
    for tf, n in cfg["window"].items():
        out["window"][tf] = int(choose("window", tf, n))
    return out


def render_chart_concepts():
    """MTF CHECK charts वर कोणत्या संकल्पना (Abhi): show / tier, mode all | primary, प्रत्येक TF ची chart खिडकी. फक्त दाखवणं."""
    import streamlit as st
    from mtf import concepts as CC
    st.caption("🗺 MTF CHECK (W / D / 1H / 15M) charts वर काय दिसावं. Default: सगळं दाखवा (mode all). mode primary ⇒ फक्त primary tier. "
               "Layer ला output नसेल तर legend मध्ये 'NA (अजून नाही)'. नियम / निर्णय बदलत नाहीत.")
    cfg = CC.load()

    def choose(kind, key, cur):
        if kind == "mode":
            return st.selectbox("mode", list(CC.MODES), index=list(CC.MODES).index(cur), key="cc_mode")
        if kind == "show":
            return st.checkbox(f"{CC.CONCEPTS[key][0]} ({CC.CONCEPTS[key][1]})", value=cur, key=f"cc_show_{key}")
        if kind == "tier":
            return st.selectbox(f"tier · {key}", list(CC.TIERS), index=list(CC.TIERS).index(cur), key=f"cc_tier_{key}",
                                label_visibility="collapsed")
        return st.number_input(f"chart खिडकी {key} (candles)", min_value=10, max_value=400, value=int(cur), step=5, key=f"cc_win_{key}")
    with st.form("cc_form"):
        vals = concepts_form_values(cfg, choose)
        ok = st.form_submit_button("Save")
    if ok:
        try:
            st.success(f"Saved · {CC.save(vals)}")
        except ValueError as exc:
            st.error(str(exc))
