"""page_reader2_gallery.py — "Reader v2 Gallery" पान (Chart Reader v2, CR3, spec §5). **Research-only: फक्त chart दाखवणं + Abhi ची
marking.** Order / broker code नाही, paid API नाही, Vision call नाही; reader2 import करत नाही (tests/test_reader2_boundary.py).

🎓 कसं वापरायचं (≈ 10 मिनिटं / chart):
  1. वरून chart निवडा (manifest `gallery2/data/manifest.json` चे 40 charts; ✔ = marking जतन झालेली).
  2. Chart वर leg चे टोक **डावीकडून उजवीकडे क्रमाने** क्लिक करा (प्रत्येक candle च्या high / low वर छोटा ठिपका आहे). दोन लागोपाठचे
     बिंदू = एक leg. क्लिक चालत नसेल तर खाली bar क्रमांक + H / L टाकून "बिंदू जोडा".
  3. Legs तक्त्यात प्रत्येक leg ला impulse / correction / uncertain निवडा; trend state (कोणत्या bar पासून up / down / range /
     uncertain); demand / supply zones (low, high).
  4. "जतन करा" — तपासणी (क्रम, किंमत = bar चा high / low, holdout नाही) पास झाली तरच साठवते. पुन्हा उघडल्यावर तीच marking दिसते
     (edit करून पुन्हा जतन).
Chart वरचा मजकूर इंग्रजीत (impulse / correction / demand …); मदत मराठीत. साठवण: Supabase `reader2_gallery` (VPS), किंवा env
`READER2_GALLERY_STORE=<folder>` ⇒ JSON folder.
"""
import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from gallery2 import data as GD
from gallery2 import schema as SC
from gallery2 import store as GS

LEG_STYLE = {"impulse": ("#ff9800", "solid", 3), "correction": ("#42a5f5", "dash", 2), "uncertain": ("#9e9e9e", "dot", 2),
             None: ("#e0e0e0", "dot", 1)}
ZONE_FILL = {"demand": "rgba(38,166,154,0.18)", "supply": "rgba(239,83,80,0.18)"}
TREND_FILL = {"up": "rgba(38,166,154,0.35)", "down": "rgba(239,83,80,0.35)", "range": "rgba(255,193,7,0.35)",
              "uncertain": "rgba(158,158,158,0.35)"}
FILTERS = ("सगळे", "न केलेले", "केलेले")


@st.cache_data(show_spinner=False, max_entries=8)
def _bars(cand_json, data_dir):
    """data_dir फक्त cache key साठी (trade-data जागा बदलली तर पुन्हा वाचतो)."""
    return GD.load_window(json.loads(cand_json))


def _state(cid, rec):
    allst = st.session_state.setdefault("g2_state", {})
    if cid not in allst:
        rec = rec or {}
        pts, labels, broken = SC.to_points(rec.get("legs"))
        allst[cid] = {"points": pts, "labels": labels, "broken": broken, "nonce": 0,
                      "trend": [{"from_bar": t["from_bar"], "state": t["state"]} for t in rec.get("trend", [])] or [{"from_bar": 0, "state": None}],
                      "zones": [{"kind": z["kind"], "low": z["low"], "high": z["high"], "from_bar": z.get("from_bar")} for z in rec.get("zones", [])],
                      "notes": rec.get("notes", ""), "marker": rec.get("marker", "Abhi"), "rev": 0,
                      "revision": int(rec.get("revision", 0) or 0)}
    return allst[cid]


def _xticks(bars, tf):
    n = len(bars)
    step = max(1, n // 10)
    idx = list(range(0, n, step))
    fmt = "%d %b %Y" if tf == "D" else "%d %b %H:%M"
    return idx, [f"{bars['timestamp'].iloc[i]:{fmt}}" for i in idx]


def figure(bars, cand, s):
    """Candles + क्लिकसाठी high / low ठिपके + legs / zones / trend (इंग्रजी मजकूर)."""
    x = list(range(len(bars)))
    when = [f"{t:%Y-%m-%d %H:%M}" if cand["timeframe"] != "D" else f"{t:%Y-%m-%d}" for t in bars["timestamp"]]
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=x, open=bars["open"], high=bars["high"], low=bars["low"], close=bars["close"], name="price",
                                 increasing_line_color="#26a69a", decreasing_line_color="#ef5350", hoverinfo="skip", showlegend=False))
    for kind, col in (("H", "high"), ("L", "low")):
        fig.add_trace(go.Scatter(x=x, y=bars[col], mode="markers", name=f"click {col}", customdata=when, showlegend=False,
                                 marker={"size": 5, "color": "#90a4ae", "opacity": 0.45},
                                 hovertemplate=f"bar %{{x}} · %{{customdata}} · {col} %{{y:.2f}}<extra></extra>"))
    legs = SC.from_points(bars, s["points"], s["labels"])
    for i, lg in enumerate(legs, 1):
        col, dash, w = LEG_STYLE.get(lg["label"], LEG_STYLE[None])
        fig.add_trace(go.Scatter(x=[lg["start_bar"], lg["end_bar"]], y=[lg["start_price"], lg["end_price"]], mode="lines",
                                 line={"color": col, "dash": dash, "width": w}, showlegend=False, hoverinfo="skip"))
        fig.add_annotation(x=(lg["start_bar"] + lg["end_bar"]) / 2, y=(lg["start_price"] + lg["end_price"]) / 2,
                           text=f"{i} {lg['label'] or '?'}", showarrow=False, font={"color": col, "size": 12}, bgcolor="rgba(0,0,0,0.55)")
    if s["points"]:
        h, lo = bars["high"].to_numpy(float), bars["low"].to_numpy(float)
        px = [b for b, _ in s["points"]]
        py = [h[b] if k == "H" else lo[b] for b, k in s["points"]]
        fig.add_trace(go.Scatter(x=px, y=py, mode="markers+text", text=[f"P{i}" for i in range(len(px))], textposition="top center",
                                 marker={"size": 10, "color": "#ffeb3b", "symbol": "diamond"}, showlegend=False, hoverinfo="skip",
                                 textfont={"color": "#ffeb3b"}))
    for z in s["zones"]:
        if z.get("kind") in ZONE_FILL and _num(z.get("low")) is not None and _num(z.get("high")) is not None:
            x0 = int(z["from_bar"]) if _num(z.get("from_bar")) is not None else 0
            fig.add_shape(type="rect", x0=x0, x1=len(bars) - 1, y0=float(z["low"]), y1=float(z["high"]), line={"width": 0},
                          fillcolor=ZONE_FILL[z["kind"]], layer="below")
            fig.add_annotation(x=len(bars) - 1, y=float(z["high"]), text=z["kind"], showarrow=False, xanchor="right", yanchor="bottom",
                               font={"size": 11, "color": "#cfd8dc"})
    tr = sorted([t for t in s["trend"] if _num(t.get("from_bar")) is not None and t.get("state") in TREND_FILL], key=lambda t: t["from_bar"])
    for j, t in enumerate(tr):
        x0 = int(t["from_bar"])
        x1 = int(tr[j + 1]["from_bar"]) if j + 1 < len(tr) else len(bars) - 1
        fig.add_shape(type="rect", xref="x", yref="paper", x0=x0 - 0.5, x1=x1 + 0.5, y0=0.97, y1=1.0, line={"width": 0},
                      fillcolor=TREND_FILL[t["state"]])
        fig.add_annotation(x=x0, y=1.0, yref="paper", text=f"trend: {t['state']}", showarrow=False, xanchor="left", yanchor="bottom",
                           font={"size": 11, "color": "#cfd8dc"})
    tv, tt = _xticks(bars, cand["timeframe"])
    fig.update_layout(height=620, margin={"l": 10, "r": 10, "t": 50, "b": 10}, template="plotly_dark", dragmode="pan",
                      xaxis={"rangeslider": {"visible": False}, "tickvals": tv, "ticktext": tt},
                      title=f"{cand['symbol']} · {GD.TF_NAME[cand['timeframe']]} · {cand['start'][:16]} → {cand['end'][:16]} · {cand['split']}",
                      clickmode="event+select", hovermode="closest")
    return fig


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else f


def add_point(s, bars, b, kind):
    """नवा बिंदू (क्रमाने). चुकीचा क्रम ⇒ कारण (str); ठीक ⇒ None."""
    b = int(b)
    if not 0 <= b < len(bars):
        return f"bar {b} window बाहेर (0–{len(bars) - 1})"
    if s["points"] and s["points"][-1] == (b, kind):
        return None
    if s["points"] and b <= s["points"][-1][0]:
        return f"बिंदू क्रमाने हवेत (डावीकडून उजवीकडे): शेवटचा bar {s['points'][-1][0]}, नवा {b}"
    s["points"].append((b, kind))
    return None


def _from_click(points, bars):
    out = []
    h, lo = bars["high"].to_numpy(float), bars["low"].to_numpy(float)
    for p in points or []:
        try:
            b, y = int(round(float(p["x"]))), float(p["y"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= b < len(bars):
            out.append((b, "H" if abs(y - h[b]) <= abs(y - lo[b]) else "L"))
    return sorted(set(out))                                           # box / lasso निवड ⇒ डावीकडून उजवीकडे


def _rows(df, cols):
    out = []
    for r in df.to_dict("records"):
        if all(r.get(c) is None or (isinstance(r.get(c), float) and r.get(c) != r.get(c)) for c in cols):
            continue
        out.append({c: (None if isinstance(r.get(c), float) and r.get(c) != r.get(c) else r.get(c)) for c in cols})
    return out


def record_from_state(cand, bars, s, now=None):
    """Session state ⇒ record. Trend ओळी from_bar ने क्रमाने; state नसलेली ओळ (bar 0 / रिकामा — default placeholder) वगळली; इतर
    state नसलेल्या ओळी ठेवल्या (validation कारण सांगते). किमान एक state नसेल तर validation ची स्पष्ट चूक."""
    legs = SC.from_points(bars, s["points"], s["labels"])
    rows = [t for t in s["trend"] if not (t.get("state") is None and _num(t.get("from_bar")) in (None, 0.0))]
    rows.sort(key=lambda t: (_num(t.get("from_bar")) is None, _num(t.get("from_bar")) or 0))
    trend = [{"from_bar": int(t["from_bar"]), "from_ts": SC.ts_str(bars["timestamp"].iloc[int(t["from_bar"])]), "state": t["state"]}
             if _num(t.get("from_bar")) is not None and 0 <= int(t["from_bar"]) < len(bars) else dict(t) for t in rows]
    zones = []
    for z in s["zones"]:
        q = {"kind": z.get("kind"), "low": _num(z.get("low")), "high": _num(z.get("high"))}
        if _num(z.get("from_bar")) is not None:
            q["from_bar"] = int(z["from_bar"])
        zones.append(q)
    return SC.new_record(cand, legs, trend, zones, marker=s.get("marker") or "Abhi", notes=s.get("notes", ""), now=now)


def render():
    st.title("📐 Reader v2 Gallery — chart marking (प्रयोगिक)")
    st.caption("Chart Reader v2 चं मोजमाप तुमच्या marking विरुद्ध (spec §5). फक्त research — bot / orders ला हात नाही. "
               "Leg टोक क्रमाने क्लिक करा ⇒ प्रत्येक leg ला impulse / correction / uncertain ⇒ trend ⇒ zones ⇒ जतन. ≈ 10 मिनिटं / chart.")
    try:
        manifest = GS.load_manifest()
    except (OSError, ValueError) as exc:
        st.error(f"Manifest वाचता आला नाही: {exc} — `python3 scripts/reader2_gallery_candidates.py` चालवा.")
        return
    cs = GS.charts(manifest)
    store = GS.default_store()
    try:
        recs = store.load_all()
    except GS.StoreError as exc:
        st.error(f"साठवलेली marking वाचता आली नाही — Save बंद (जुनी marking पुसली जाऊ नये म्हणून): {exc}")
        return
    pr = GS.progress(manifest, recs)
    c1, c2, c3 = st.columns(3)
    c1.metric("Marked", f"{pr['marked']}/{pr['total']}")
    c2.metric("dev", f"{pr['dev'][0]}/{pr['dev'][1]}")
    c3.metric("test (sealed)", f"{pr['test'][0]}/{pr['test'][1]}")
    st.caption(f"साठवण: {store.describe()}"
               + (" · data नाही: " + ", ".join(f"{m['symbol']}/{m['timeframe']}" for m in manifest.get("missing", [])) if manifest.get("missing") else ""))
    with st.expander("सगळ्या charts ची यादी"):
        st.dataframe(pd.DataFrame([{"#": c["n"], "id": c["id"], "symbol": c["symbol"], "TF": c["timeframe"], "split": c["split"],
                                    "marked": "✔" if (recs.get(c["id"]) or {}).get("legs") else "", "tags": ", ".join(c.get("tags", [])),
                                    "start": c["start"][:16], "end": c["end"][:16]} for c in cs.values()]),
                     hide_index=True, width="stretch")
    flt = st.radio("दाखवा", FILTERS, horizontal=True, key="g2_filter")
    ids = [k for k, c in cs.items() if flt == "सगळे" or ((recs.get(k) or {}).get("legs") and flt == "केलेले")
           or (not (recs.get(k) or {}).get("legs") and flt == "न केलेले")]
    if not ids:
        st.info("या filter मध्ये chart नाही.")
        return
    cid = st.selectbox("Chart", ids, key="g2_chart", format_func=lambda k: f"{'✔' if (recs.get(k) or {}).get('legs') else '·'} "
                       f"{cs[k]['n']:02d} · {cs[k]['symbol']} {GD.TF_NAME[cs[k]['timeframe']]} · {cs[k]['start'][:10]} → {cs[k]['end'][:10]} · {cs[k]['split']}")
    cand = cs[cid]
    if cand.get("note"):
        st.caption(f"📝 {cand['note']}")
    try:
        bars = _bars(json.dumps(cand, sort_keys=True), GD.trade_data_dir())
    except GD.DataMissing as exc:
        st.error(f"Candles नाहीत: {exc}")
        return
    except GD.DP.HoldoutError as exc:
        st.error(f"Holdout — दाखवत नाही: {exc}")
        return
    if bars is None or not len(bars):
        st.error(f"{cid}: या window मध्ये एकही candle नाही ({cand['start']} → {cand['end']}, source {cand['source']}) — data / manifest तपासा.")
        return
    s = _state(cid, recs.get(cid))
    if st.session_state.get("g2_last") != cid:                         # chart बदलला ⇒ तक्ते साठवलेल्या state वरून पुन्हा (जुने widgets नाहीत)
        st.session_state["g2_last"] = cid
        s["rev"] += 1
        s["nonce"] += 1
    split_err = GS.split_mismatch(recs.get(cid), cand)
    if split_err:
        st.error(split_err + " — Save बंद.")
    if s.get("broken"):
        st.warning("जतन केलेले legs सलग नव्हते — मधल्या gap साठी नवा leg (label रिकामा) तयार केला; label निवडा किंवा बिंदू काढा.")
    for k in ("g2_msg", "g2_ok"):
        if st.session_state.get(k):
            (st.warning if k == "g2_msg" else st.success)(st.session_state.pop(k))
    chart_slot = st.container()                                      # chart शेवटी भरतो ⇒ याच run मधले बदल लगेच दिसतात

    st.markdown("**बिंदू (क्लिक चालत नसेल तर इथे)**")
    a1, a2, a3, a4, a5 = st.columns([2, 1, 1, 1, 1])
    nb = a1.number_input("bar क्रमांक", min_value=0, max_value=len(bars) - 1, value=0, step=1, key=f"g2_bar_{cid}")
    nk = a2.radio("टोक", ["H", "L"], horizontal=True, key=f"g2_hl_{cid}")
    if a3.button("➕ बिंदू जोडा", key=f"g2_add_{cid}"):
        msg = add_point(s, bars, nb, nk)
        if msg:
            st.session_state["g2_msg"] = msg
        s["nonce"] += 1
        st.rerun()
    if a4.button("↩️ शेवटचा काढा", key=f"g2_undo_{cid}") and s["points"]:
        s["points"].pop()
        s["nonce"] += 1
        st.rerun()
    if a5.button("🗑️ सगळे काढा", key=f"g2_clear_{cid}"):
        s["points"], s["labels"], s["broken"] = [], [], False
        s["nonce"] += 1
        st.rerun()
    st.caption(f"bar {int(nb)} = {bars['timestamp'].iloc[int(nb)]} · H {bars['high'].iloc[int(nb)]:.2f} · L {bars['low'].iloc[int(nb)]:.2f}")

    legs = SC.from_points(bars, s["points"], s["labels"])
    s["labels"] = (s["labels"] + [None] * len(legs))[: len(legs)]
    if legs:
        st.markdown("**Legs** — प्रत्येकाला label")
        df = pd.DataFrame([{"#": i, "from": lg["start_ts"][:16], "to": lg["end_ts"][:16], "dir": "up" if lg["end_price"] > lg["start_price"] else "down",
                            "start": round(lg["start_price"], 2), "end": round(lg["end_price"], 2), "bars": lg["end_bar"] - lg["start_bar"],
                            "label": lg["label"]} for i, lg in enumerate(legs, 1)])
        ed = _editor(s, "legs", f"g2_legs_{cid}_{s['nonce']}", df, disabled=["#", "from", "to", "dir", "start", "end", "bars"],
                     column_config={"label": st.column_config.SelectboxColumn("label", options=list(SC.LEG_LABELS), required=True)})
        s["labels"] = [None if (v is None or v != v) else v for v in ed["label"].tolist()]
    else:
        st.info("अजून legs नाहीत — chart वर पहिले दोन बिंदू क्लिक करा.")

    st.markdown("**Trend state** — कोणत्या bar पासून (पुढच्या ओळीपर्यंत लागू)")
    tdf = _editor(s, "trend", f"g2_trend_{cid}_{s['rev']}", pd.DataFrame(s["trend"], columns=["from_bar", "state"]), num_rows="dynamic",
                  column_config={"from_bar": st.column_config.NumberColumn("from_bar", min_value=0, max_value=len(bars) - 1, step=1),
                                 "state": st.column_config.SelectboxColumn("state", options=list(SC.TREND_STATES))})
    s["trend"] = _rows(tdf, ["from_bar", "state"])
    st.markdown("**Demand / supply zones**")
    zdf = _editor(s, "zones", f"g2_zones_{cid}_{s['rev']}", pd.DataFrame(s["zones"], columns=["kind", "low", "high", "from_bar"]),
                  num_rows="dynamic",
                  column_config={"kind": st.column_config.SelectboxColumn("kind", options=list(SC.ZONE_KINDS)),
                                 "low": st.column_config.NumberColumn("low", format="%.2f"),
                                 "high": st.column_config.NumberColumn("high", format="%.2f"),
                                 "from_bar": st.column_config.NumberColumn("from_bar (optional)", min_value=0, step=1)})
    s["zones"] = _rows(zdf, ["kind", "low", "high", "from_bar"])
    n1, n2 = st.columns([3, 1])
    s["notes"] = n1.text_area("Notes", value=s.get("notes", ""), height=70, key=f"g2_notes_{cid}_{s['rev']}")
    s["marker"] = n2.text_input("Marker", value=s.get("marker") or "Abhi", key=f"g2_marker_{cid}_{s['rev']}")
    b1, b2 = st.columns([1, 1])
    if b1.button("💾 जतन करा", type="primary", key=f"g2_save_{cid}", disabled=bool(split_err)):
        rec = record_from_state(cand, bars, s)
        try:
            GS.save_record(store, rec, cand, bars, expected_revision=s["revision"])
        except ValueError as exc:
            st.error("जतन केलं नाही — दुरुस्त करा:\n\n- " + "\n- ".join(str(exc).split("; ")))
        except GS.ConflictError as exc:
            st.error(f"जतन केलं नाही — मधेच दुसरीकडे (tab / device) बदल झाला: {exc}. तुमचे बदल लिहून ठेवा, मग 🔄 पुन्हा उघडा.")
        except GS.StoreError as exc:
            st.error(f"साठवता आलं नाही: {exc}")
        else:
            s["revision"] += 1
            st.session_state["g2_ok"] = f"जतन झालं ({cid}) — {len(rec['legs'])} legs, {len(rec['trend'])} trend, {len(rec['zones'])} zones"
            st.rerun()
    if b2.button("🔄 जतन केलेली marking पुन्हा उघडा", key=f"g2_reload_{cid}"):
        rev, nonce = s["rev"] + 1, s["nonce"] + 1
        st.session_state["g2_state"].pop(cid, None)
        fresh = _state(cid, recs.get(cid))
        fresh["rev"], fresh["nonce"] = rev, nonce
        st.rerun()

    with chart_slot:
        ev = st.plotly_chart(figure(bars, cand, s), key=f"g2_fig_{cid}_{s['nonce']}", on_select="rerun", selection_mode="points",
                             width="stretch", config={"scrollZoom": True})
        sel = ev.get("selection") if isinstance(ev, dict) else getattr(ev, "selection", None)
        raw = (sel.get("points") if isinstance(sel, dict) else getattr(sel, "points", None)) if sel is not None else None
        pts = _from_click(raw, bars)
        if pts:
            msg = None
            for b, k in pts:
                msg = add_point(s, bars, b, k) or msg
            if msg:
                st.session_state["g2_msg"] = msg
            s["nonce"] += 1
            st.rerun()


def _editor(s, name, key, df, **kw):
    """data_editor ला दर run तोच base (key बदलेपर्यंत) — नाहीतर नव्या rows / बदल दुप्पट लागतात."""
    bases = s.setdefault("bases", {})
    if name not in bases or bases[name][0] != key:
        bases[name] = (key, df.copy())
    return st.data_editor(bases[name][1], key=key, hide_index=True, width="stretch", **kw)
