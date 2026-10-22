"""page_chart_reading.py — Chart Reading (Abhi's order, owner-orders DECISIONS 35): the dashboard page of the daily Chart Reading Report.

Shows, per symbol, what scripts/chart_reading_report.py stored (data/chart_reading/<SYM>/latest_close.json + PNGs, latest_preopen.json):
the Telegram message (MR / EN, short / full), the three charts, the FULL detail (every trade-side area the engine arms, every overlapping
group, every pattern, every concept's facts with its reader source), Vision's per-area verdicts and the reading checks, and the OLD
visual-audit data (its level-count message is off by default — the data stays here). Also the report's dashboard settings.
Display only — never an order, a gate or a reading."""
import json
import os

import streamlit as st

STORE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "chart_reading")
OLD_AUDIT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "oe_visual_audit.jsonl")


def load(sym, mode="close", root=None):
    try:
        with open(os.path.join(root or STORE, sym, f"latest_{mode}.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def old_audit_rows(path=OLD_AUDIT, last=12):
    """The old Opportunity Engine visual-audit records (data kept; its Telegram message is off by default)."""
    rows = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                ov = ((r.get("overlay") or {}).get("data") or {})
                vs = [v.get("verdict") for v in ov.get("verdicts") or ()]
                rows.append({"date": r.get("audit_date"), "symbol": r.get("symbol"), "tf": r.get("tf"), "levels": len(vs),
                             "VALID": vs.count("VALID"), "SPURIOUS": vs.count("SPURIOUS"),
                             "SHIFT": sum(1 for v in vs if str(v).startswith("SHIFT")), "missing": len(ov.get("missing") or ())})
    except OSError:
        return []
    return rows[-last:]


def area_rows(facts):
    A = (facts or {}).get("areas") or {}
    out = []
    for a in sorted(A.get("alive") or (), key=lambda a: a.get("dist") or 0):
        out.append({"id": a["id"], "tf": a["tf"], "kind": a["kind"], "low": a["lo"], "high": a["hi"], "state": a["state"],
                    "tests": a.get("tests"), "sweeps": a.get("sweeps"), "was": a.get("was"), "distance": a.get("dist"),
                    "trade side (engine)": a["id"] in {w["id"] for w in A.get("watch") or ()}, "confluence": a.get("confluence_label")})
    return out


def _settings_box():
    import cloud_db
    s = cloud_db.get_chart_reading_settings()
    with st.expander("⚙️ Report settings (dashboard)", expanded=False):
        c1, c2, c3 = st.columns(3)
        on = c1.selectbox("Report (after close + pre-open refresh)", ["off", "on"], index=["off", "on"].index(s["chart_reading_report"]))
        lang = c2.selectbox("Language", ["mr", "en"], index=["mr", "en"].index(s["chart_reading_language"]))
        det = c3.selectbox("Detail", ["short", "full"], index=["short", "full"].index(s["chart_reading_detail"]))
        c4, c5, c6 = st.columns(3)
        syms = c4.multiselect("Symbols (empty = signal_symbols)", list(cloud_db.SIGNAL_SYMBOLS_CHOICES), default=s["chart_reading_symbols"])
        vis = c5.selectbox("Vision second opinion (info only, Vision budget caps)", ["off", "on"],
                           index=["off", "on"].index(s["chart_reading_vision"]))
        old = c6.selectbox("Old visual-audit level-count message", ["off", "on"], index=["off", "on"].index(s["visual_audit_level_message"]))
        url = st.text_input("This page's link (printed at the end of the message; empty = 'dashboard → Chart Reading')",
                            value=s["chart_reading_page_url"])
        if st.button("Save report settings", key="crr_save"):
            try:
                ok = cloud_db.save_chart_reading_settings({"chart_reading_report": on, "chart_reading_language": lang,
                                                          "chart_reading_detail": det, "chart_reading_symbols": syms,
                                                          "chart_reading_vision": vis, "visual_audit_level_message": old,
                                                          "chart_reading_page_url": url})
                st.success("saved") if ok else st.error("database not reachable — not saved")
            except ValueError as exc:
                st.error(str(exc))
    return s


def render():
    st.title("📘 Chart Reading")
    st.caption("The decision3 reader's own reading per symbol (closed concept list A–L), the charts and Vision's second opinion — "
               "information only, never an order or a gate. Execution = your dashboard settings.")
    try:
        s = _settings_box()
    except Exception as exc:                                               # noqa: BLE001 — the page still shows the stored reports
        st.warning(f"settings not readable: {type(exc).__name__}")
        s = {"chart_reading_language": "mr", "chart_reading_detail": "short"}
    syms = sorted(d for d in os.listdir(STORE) if os.path.isdir(os.path.join(STORE, d))) if os.path.isdir(STORE) else []
    if not syms:
        st.info("No report stored yet (scripts/chart_reading_report.py writes data/chart_reading/).")
    for sym, tab in zip(syms, st.tabs(syms) if syms else []):
        with tab:
            rec = load(sym)
            if not rec:
                st.info("no close report stored")
                continue
            st.write(f"as of {rec.get('as_of')} · language {rec.get('language')} · detail {rec.get('detail')}")
            c1, c2 = st.columns(2)
            lang = c1.radio("Language", ["mr", "en"], horizontal=True, key=f"l_{sym}",
                            index=["mr", "en"].index(s.get("chart_reading_language", "mr")))
            det = c2.radio("Detail", ["short", "full"], horizontal=True, key=f"d_{sym}", index=1)
            st.code((rec.get("text") or {}).get(f"{lang}_{det}") or rec.get("send") or "", language=None)
            for name in ("WD", "1H", "15M"):
                p = os.path.join(STORE, sym, f"close_{name}.png")
                if os.path.exists(p):
                    st.image(p, caption=f"{sym} {name}")
            facts = rec.get("facts") or {}
            with st.expander("All areas (alive) — the engine's trade side marked", expanded=False):
                st.dataframe(area_rows(facts), use_container_width=True)
            with st.expander("Overlapping same-role areas (Z-1u: one place, counted once)", expanded=False):
                st.json((facts.get("areas") or {}).get("duplicates") or [])
            with st.expander("Every concept's facts (with the reader source)", expanded=False):
                st.json({k: facts.get(k) for k in ("big_picture", "structure", "liquidity", "lines", "patterns", "confluence", "volume",
                                                   "rsi", "breakout_range", "wave", "plan")})
            if facts.get("errors"):
                st.warning(f"reader errors (concept left out): {facts['errors']}")
            with st.expander("Vision (info only) and reading checks", expanded=False):
                st.json(rec.get("vision") or {"status": "not run"})
                for x in rec.get("reading_checks") or ():
                    st.write("• " + x)
            pre = load(sym, "preopen")
            if pre:
                with st.expander("Pre-open refresh", expanded=False):
                    st.code((pre.get("text") or {}).get(lang) or "", language=None)
    with st.expander("Old visual audit (Opportunity Engine levels — its Telegram message is off by default; data kept)", expanded=False):
        rows = old_audit_rows()
        st.dataframe(rows, use_container_width=True) if rows else st.info("no old visual-audit record")
