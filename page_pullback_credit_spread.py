"""
page_pullback_credit_spread.py
------------------------------
🎓 "Pullback Credit Spread" — settings + live preview पान (वापरकर्त्याचं spec docs/PULLBACK_CREDIT_SPREAD_PROMPT.md §7).
  • 11 विभाग (expanders), प्रत्येक setting: मराठी label, ⓘ मदत, min/max validation, डीफॉल्ट दाखवलेला.
  • Presets (Conservative / Balanced / Aggressive), per-symbol (NIFTY / BANKNIFTY / SENSEX) + "सगळ्यांना लागू करा", Save, Reset, बदलांचा इतिहास.
  • Live preview — "आत्ता signal आला तर": expiry, short/long strike, credit, max loss, lots, आणि ✅/❌ checklist. **फक्त वाचन, order नाही.**
  • एका column चा layout (mobile).
हे पान कुठलाही order पाठवत नाही. Mode डीफॉल्ट OFF; पर्याय फक्त OFF / PAPER (LIVE फक्त वापरकर्त्याच्या स्पष्ट मंजुरीने — G3).
"""
import datetime as dt

import pandas as pd
import streamlit as st

from pullback_credit_spread import preview as PV
from pullback_credit_spread import settings as S
from pullback_credit_spread import store as ST

WK = "pcs_w_"                                                     # widget keys
VALS = "pcs_values"                                               # widget-बाहेरचा प्रत (पान बदलल्यावर Streamlit widget state पुसतो)
PER_SYMBOL_ONLY = ("mode", "symbol_enabled")                      # "सगळ्यांना लागू करा" मध्ये कॉपी होत नाहीत (चुकून BANKNIFTY/SENSEX चालू नको)


def _wkey(k):
    return f"{WK}{k}"


def _load_into_state(sym, values):
    for k, v in values.items():
        st.session_state[_wkey(k)] = v
    st.session_state[VALS] = dict(values)
    st.session_state["pcs_loaded_symbol"] = sym


def _restore_missing_widgets():
    """review (High): दुसऱ्या पानावर जाऊन परत आल्यावर Streamlit `pcs_w_*` widget state पुसतो — VALS मधून परत भरतो, नाहीतर widgets
    चुकीच्या (पहिल्या पर्यायाच्या) मूल्यांवर येतात आणि Save त्या साठवतो."""
    vals = st.session_state.get(VALS) or {}
    for k in S.DEFAULTS:
        if _wkey(k) not in st.session_state:
            st.session_state[_wkey(k)] = vals.get(k, S.DEFAULTS[k])


def _current():
    return {k: st.session_state.get(_wkey(k), S.DEFAULTS[k]) for k in S.DEFAULTS}


def _widget(spec):
    k, label, help_ = spec["key"], spec["label"], f"{spec['help']}  \n(डीफॉल्ट: {spec['default']})"
    key = _wkey(k)
    if spec["type"] == "bool":
        st.toggle(label, key=key, help=help_)
    elif spec["type"] == "choice":
        st.selectbox(label, spec["choices"], key=key, help=help_)
    elif spec["type"] in ("int", "float"):
        cast = int if spec["type"] == "int" else float
        cur = st.session_state.get(key, spec["default"])
        try:
            cur = cast(cur)
        except (TypeError, ValueError):
            cur = cast(spec["default"])
        st.session_state[key] = min(max(cur, cast(spec["min"])), cast(spec["max"]))
        st.number_input(label, min_value=cast(spec["min"]), max_value=cast(spec["max"]), step=cast(spec["step"] or 1), key=key, help=help_)
    else:
        st.text_input(label, key=key, help=help_ + ("  \nस्वरूप HH:MM" if spec["type"] == "time" else ""))


def _settings_ui():
    for sec, title in S.SECTIONS:
        specs = [s for s in S.SCHEMA if s["section"] == sec]
        with st.expander(title, expanded=(sec == "mode")):
            if sec == "mode":
                st.caption("Mode डीफॉल्ट **OFF**. PAPER मध्ये फक्त कागदावर trades. LIVE फक्त तुमच्या स्पष्ट मंजुरीनंतर (G3) उपलब्ध होईल.")
            for spec in specs:
                _widget(spec)


def _preview_ui(sym, settings):
    st.markdown("### 🔍 Live preview — \"आत्ता signal आला तर\"")
    st.caption("फक्त वाचन — कुठलाही order पाठवत नाही. Live डेटा नसेल तर NIFTY offline डेटा (2015 → 2024-03) वर निवडलेल्या वेळी, "
               "premium = Black-Scholes **अंदाज** (IV ≈ σ20).")
    token = st.session_state.get("token_input")
    source = "Offline (ऐतिहासिक)" if not token or sym != "NIFTY" else st.radio(
        "डेटा स्रोत", ("Offline (ऐतिहासिक)",), key="pcs_prev_src", help="Live (Upstox) preview PAPER runner सोबत (PCS-4) जोडला जाईल.")
    st.caption(f"स्रोत: {source}" + ("" if sym == "NIFTY" else f" — {sym} साठी offline डेटा नाही; NIFTY वर दाखवतो."))
    d = st.date_input("तारीख", value=dt.date(2024, 3, 15), min_value=dt.date(2015, 3, 1), max_value=dt.date(2024, 3, 28), key="pcs_prev_date")
    t = st.time_input("वेळ", value=dt.time(11, 0), key="pcs_prev_time")
    capital = st.number_input("Capital (₹)", min_value=50_000, max_value=100_000_000, value=1_000_000, step=50_000, key="pcs_prev_cap",
                              help="Lots मोजण्यासाठी (risk % × capital).")
    lot = st.number_input("Lot size (त्या काळचा)", min_value=1, max_value=1000, value=PV.nifty_lot_size(d), step=1, key=f"pcs_prev_lot_{d}",
                          help="NIFTY lot काळानुसार बदलला (उदा. 2021-07 → 2024-04: 50). अंदाजे डीफॉल्ट; गरज असल्यास बदला.")
    st.caption("ℹ️ 2019 पूर्वी NIFTY weekly options नव्हते; offline expiries = गुरुवार-अंदाज (सुट्टी-बदल नाहीत).")
    if not st.button("Preview मोजा", key="pcs_prev_go", type="primary"):
        return
    now = pd.Timestamp.combine(d, t)
    try:
        with st.spinner("मोजत आहे…"):
            df1m = _offline_1m()
            if df1m is None:
                st.warning("Offline डेटा उपलब्ध नाही.")
                return
            inp = PV.offline_inputs(df1m, now, settings)
            if inp is None:
                st.warning("त्या वेळेपूर्वीचा डेटा नाही.")
                return
            inp["lot_size"] = int(lot)
            r = PV.run_preview(inp, settings, capital, now)
    except Exception as e:                                           # noqa: BLE001 — preview चूक पानाला क्रॅश करू नये
        st.error(f"Preview मोजता आला नाही: {type(e).__name__}: {e}")
        return
    st.markdown(f"**Spot {inp['spot']:,.2f}** · IV≈{inp['iv'] * 100:.1f}% · lot {inp['lot_size']} · {now:%d %b %Y %H:%M}" +
                (" · premium = model अंदाज" if r.get("model_premium") else ""))
    for h in r["hypothetical"]:
        st.markdown(f"#### {h['label']}")
        rows = [("Expiry", f"{h['expiry']:%d %b %Y}" if h.get("expiry") else "—"),
                ("Level", f"{h['level']['low']:,.1f} – {h['level']['high']:,.1f} ({h['level']['role']})" if h.get("level") else "—"),
                ("Short strike", f"{h['short_k']:g}" if h.get("short_k") else f"— ({h.get('note') or ''})"),
                ("Long (hedge) strike", f"{h['long_k']:g}" if h.get("long_k") else "—"),
                ("Net credit (प्रति unit)", f"₹{h['credit']:.2f}" if h.get("credit") is not None else "—"),
                ("Max loss (प्रति lot)", f"₹{h['max_loss_per_lot']:,.0f}" if h.get("max_loss_per_lot") else "—"),
                ("Lots", str(h.get("lots")) if h.get("lots") is not None else "—"),
                ("टीप", " · ".join(x for x in (h.get("credit_note"), h.get("lots_note")) if x) or "—")]
        st.table(pd.DataFrame(rows, columns=["", "मूल्य"]).set_index(""))
    st.markdown("#### ✅/❌ Checklist (क्रमाने)")
    st.table(pd.DataFrame(r["steps"], columns=["पायरी", "", "तपशील"]).set_index("पायरी"))
    st.success("सर्व अटी पूर्ण — signal आला असता.") if r["ok"] else st.info("सर्व अटी पूर्ण नाहीत — entry झाली नसती.")


@st.cache_data(show_spinner=False, ttl=30)
def _history_cached(sym):
    return ST.history(sym, limit=30)


@st.cache_data(show_spinner=False, ttl=3600)
def _offline_1m_cached():
    import leg_level_validation as T3
    import real_nifty_data
    d = real_nifty_data.load_nifty_1min()
    return d[d["timestamp"] <= T3.VAL_END].reset_index(drop=True)              # sealed holdout कधीच नाही


def _offline_1m():
    try:
        return _offline_1m_cached()                                  # अपयश cache होत नाही (exception cache होत नाही)
    except Exception:
        return None


def render():
    st.title("🧲 Pullback Credit Spread")
    st.caption("Directional credit spread — entry **फक्त pullback वर**, breakout वर कधीच नाही. सर्व settings इथून; code मध्ये hard-coded नाही. "
               "⚠️ हे पान order पाठवत नाही.")
    if "pcs_symbol" not in st.session_state:                         # पान बदलल्यावर widget state पुसतो ⇒ शेवटचा symbol परत
        last = st.session_state.get("pcs_loaded_symbol") or st.session_state.get("pcs_last_symbol") or st.session_state.get("symbol")
        st.session_state["pcs_symbol"] = last if last in ST.SYMBOLS else "NIFTY"
    sym = st.selectbox("Symbol", ST.SYMBOLS, key="pcs_symbol", help="प्रत्येक symbol चे settings वेगळे साठवले जातात.")
    st.session_state["pcs_last_symbol"] = sym
    if st.session_state.get("pcs_loaded_symbol") != sym:
        vals, src = ST.load(sym)
        _load_into_state(sym, vals)
        st.session_state["pcs_src"] = src
    _restore_missing_widgets()
    src_now = st.session_state.get("pcs_src")
    st.caption(f"Settings स्रोत: {src_now}")
    if src_now == "error":
        st.error("Supabase मधून settings वाचता आले नाहीत — डीफॉल्ट दाखवले आहेत. Save बंद (खरी नोंद overwrite होऊ नये). "
                 "पुन्हा प्रयत्न करा.")
        if st.button("पुन्हा वाचा", key="pcs_reload"):
            st.session_state["pcs_loaded_symbol"] = None
            st.rerun()

    with st.expander("⚡ Presets", expanded=False):
        p = st.selectbox("Preset", list(S.PRESETS), index=1, key="pcs_preset",
                         help="एका click ने सगळ्या settings भरतात (Mode आणि symbol चालू/बंद सोडून); नंतर हाताने बदलता येतात. Save केल्याशिवाय साठवत नाही.")
        if st.button("Preset भरा", key="pcs_preset_go"):
            keep = {k: st.session_state.get(_wkey(k)) for k in ("mode", "symbol_enabled")}
            _load_into_state(sym, {**S.preset(p), **keep})
            st.rerun()

    _settings_ui()
    cur = _current()
    st.session_state[VALS] = dict(cur)                              # पान बदललं तरी मूल्यं टिकावीत
    clean, errors = S.validate(cur)
    for e in errors:
        st.warning(e)

    st.markdown("### 💾 Save")
    who = st.text_input("तुमचं नाव (इतिहासात नोंदवण्यासाठी)", key="pcs_who", placeholder="उदा. Abhi")
    apply_all = st.checkbox("सगळ्या symbols ना लागू करा (NIFTY, BANKNIFTY, SENSEX)", key="pcs_apply_all",
                            help="Mode आणि 'हा symbol चालू' हे प्रत्येक symbol चे स्वतंत्रच राहतात — ते कॉपी होत नाहीत.")
    by = ((who or "").strip() or "dashboard")[:40]
    if errors:
        st.error("वरच्या चुका दुरुस्त केल्याशिवाय Save करता येणार नाही.")
    # review: Save नंतर widgets पुन्हा store मधून भरत नाही — ते आधीच `clean` इतके आहेत (चुका असताना Save बंद). पुन्हा भरल्याने
    # पुढचा बदल गुपचूप हरवायचा, आणि अयशस्वी save नंतरच्या retry मध्ये बदल पुसून "0 बदल साठवले" असं खोटं यश दिसायचं.
    if st.button("Save", key="pcs_save", type="primary", disabled=bool(errors) or src_now == "error"):
        targets = ST.SYMBOLS if apply_all else (sym,)
        for s_ in targets:
            vals = dict(clean)
            if s_ != sym:
                own, own_src = ST.load(s_)
                if own_src == "error":
                    st.error(f"{s_}: Supabase वाचता आलं नाही — save केलं नाही.")
                    continue
                vals.update({k: own[k] for k in PER_SYMBOL_ONLY})
            _, errs, changes, src = ST.save(s_, vals, changed_by=by)
            if src == "error":
                st.error(f"{s_}: {errs[-1]} — तुमचे बदल पानावर तसेच आहेत; पुन्हा Save करा.")
            else:
                st.success(f"{s_}: {len(changes)} बदल साठवले ({src}).")
                if s_ == sym:
                    st.session_state["pcs_src"] = src
        _history_cached.clear()
    confirm = st.checkbox("होय, या symbol चे settings डीफॉल्टवर न्यायचे आहेत", key="pcs_reset_ok")
    if st.button("Reset to defaults", key="pcs_reset", disabled=not confirm or src_now == "error"):
        _, errs, _, src = ST.reset(sym, changed_by=by)
        _history_cached.clear()
        if src == "error":
            st.error(f"Reset अयशस्वी: {errs[-1]}")
        else:
            st.session_state["pcs_loaded_symbol"] = None
            st.rerun()

    with st.expander("🕘 बदलांचा इतिहास", expanded=False):
        h = _history_cached(sym)
        if h:
            hd = pd.DataFrame(h)[["at", "key", "old", "new", "by"]]
            hd[["old", "new"]] = hd[["old", "new"]].astype(str)       # int/bool/str मिश्र column ⇒ Arrow चूक टाळतो
            st.dataframe(hd, use_container_width=True, hide_index=True)
        else:
            st.caption("अजून बदल नाहीत.")

    _preview_ui(sym, clean)
