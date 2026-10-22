"""decision3/chart_reading_vision.py — Vision's part of the Chart Reading Report (Abhi's order, owner-orders DECISIONS 35): the EXISTING
Dual-Eye audit (opportunity_engine/visual_audit: the same prompts, JSON schemas, retry / validation, chart renderer and — through the
caller — the same Vision budget caps of run_visual_audit.py) pointed at the decision3 reader's ALIVE areas per timeframe (band as the
reader keeps it, K4 lifecycle state, area id) instead of the old Opportunity Engine §2.6 levels.

Information only — never a gate: nothing here reaches the engine, an entry, an order or a setting. Per area it gives VALID / SPURIOUS /
SHIFT (↑ / ↓) with Vision's one-line reason; the zones Vision sees that the reader does not (its "missing" list + its own independent
read, minus the bands that overlap an alive area of that timeframe); the duplicates (alive areas of one timeframe and role overlapping
each other = one place, a concept C / Z-1u reading check); and one line each for trend / structure agreement.
Rule (the order): an area outside the chart's visible price window is "not visible on this chart" — it is never sent as a label and
never reported SPURIOUS (a SPURIOUS for an area outside the window is turned into "not visible" as well).
Disagreements become reading-check lines against a named concept (`reading_checks`) for OPEN_QUESTIONS — never a rule from one chart.
The client is injected (tests use a fake; no model is ever called by a test)."""
import pandas as pd

from . import chart_reading as CR

TFS = ("1d", "1h")                                                        # the same default timeframes as run_visual_audit.py (cost)
TF_AREA = {"1d": "D", "1h": "1H", "15m": "1H"}
ENGINE_TREND = {("trending up", None): "UPTREND", ("trending down", None): "DOWNTREND", ("correction in progress", "UP"): "UPTREND_PULLBACK",
                ("correction in progress", "DOWN"): "DOWNTREND_PULLBACK", ("range", None): "RANGE", ("unclear", None): "UNCLEAR"}


def engine_state(facts, tf):
    st = (((facts.get("big_picture") or {}).get("tfs") or {}).get({"1d": "D", "1h": "1H", "15m": "15M"}[tf]) or {})
    return ENGINE_TREND.get((st.get("state"), st.get("trend"))) or ENGINE_TREND.get((st.get("state"), None)) or "UNCLEAR"


def direction(state):
    s = str(state or "")
    return "UP" if s.startswith("UPTREND") else "DOWN" if s.startswith("DOWNTREND") else "RANGE" if s == "RANGE" else None


def frame(V, sym, tf, t):
    """The chart frame of the audit (bars ≤ t): Daily (NIFTY: after the sealed holdout dates) or 1H (the running hour only up to t)."""
    from . import history as HI
    if tf == "1d":
        d = V.daily_df.reset_index(drop=True)
        st0 = HI.display_start(pd.to_datetime(d["timestamp"]), None, HI.sealed_fn(sym), sessions=len(d))
        d = d.iloc[st0:].reset_index(drop=True)
        out = d[["timestamp", "open", "high", "low", "close"]].copy()
        out["bar_end"] = pd.to_datetime(out["timestamp"]).dt.normalize() + pd.Timedelta(hours=15, minutes=30)
        return out
    lv = V.levels
    j_end = int(lv.h1_of[t])
    h1 = lv.h1.iloc[: j_end + 1].reset_index(drop=True)[["timestamp", "open", "high", "low", "close"]].copy()
    h1.loc[len(h1) - 1, ["open", "high", "low", "close"]] = list(lv._h1_upto(j_end, t))
    h1["bar_end"] = pd.to_datetime(h1["timestamp"]) + pd.Timedelta(hours=1)
    return h1


def labels_for(areas, lo, hi):
    """Alive areas ⇒ (labels in the auditor's format for the VISIBLE ones, the ids NOT visible on this chart's price window)."""
    labels, not_visible = [], []
    for a in sorted(areas, key=lambda a: -a["hi"]):
        if a["hi"] < lo or a["lo"] > hi:
            not_visible.append(a["id"])
            continue
        labels.append({"label": f"A{a['id']}", "level_id": str(a["id"]), "kind": "SUPPLY" if a["kind"] == "supply" else "DEMAND",
                       "tf": a["tf"], "core_low": a["lo"], "core_high": a["hi"], "outer_low": a["lo"], "outer_high": a["hi"],
                       "grade": a["state"]})
    return labels, not_visible


def audit_tf(client, cfg, V, sym, facts, tf, audit_date=None, render_fn=None, allow=None, on_usage=None):
    """One timeframe: render (overlay + plain) with the existing renderer, call the existing auditor, read back per area. Returns a
    plain dict {tf, status, areas: [{id, tf, lo, hi, state, verdict, reason}], not_visible, missing, duplicates, trend, structure}."""
    from opportunity_engine.visual_audit import auditor as AU
    from opportunity_engine.visual_audit import render as RD
    render_fn = render_fn or RD.render_png
    t = int(facts["t"])
    df = RD.window(frame(V, sym, tf, t), tf)
    lo, hi = float(df["low"].min()), float(df["high"].max())
    alive = [a for a in ((facts.get("areas") or {}).get("alive") or ()) if a["tf"] == TF_AREA[tf]]
    labels, not_visible = labels_for(alive, lo, hi)
    out = {"tf": tf, "status": "skipped", "areas": [], "not_visible": not_visible, "missing": [], "duplicates": [], "trend": None,
           "structure": None, "why": None}
    vis = [a for a in alive if a["id"] not in set(not_visible)]
    out["duplicates"] = [{"tf": g["tf"], "kind": g["kind"], "ids": g["ids"]} for g in CR.duplicate_groups(vis)]
    if allow is not None:
        ok, why = allow(tf)
        if not ok:
            out["why"] = why
            return out
    png_o = render_fn(df, tf, sym, labels, None, overlay=True) if labels else None
    png_p = render_fn(df, tf, sym, None, None, overlay=False)
    est = engine_state(facts, tf)
    rec = AU.audit_chart(client, cfg, sym, tf, audit_date, png_o, png_p, labels, [], est, lo, hi)
    if on_usage is not None:
        on_usage(rec)
    out["usage"] = rec.get("usage")
    ov, ind = rec.get("overlay") or {}, rec.get("independent") or {}
    by = {str(a["id"]): a for a in vis}
    for v in ((ov.get("data") or {}).get("verdicts") or ()):
        a = by.get(v["label"][1:])
        if a is None:
            continue
        verdict = v["verdict"]
        if verdict == "SPURIOUS" and (a["hi"] < lo or a["lo"] > hi):        # belt and braces: outside the window is never SPURIOUS
            out["not_visible"].append(a["id"])
            continue
        out["areas"].append({"id": a["id"], "tf": a["tf"], "lo": a["lo"], "hi": a["hi"], "state": a["state"],
                             "verdict": {"SHIFT_UP": "SHIFT ↑", "SHIFT_DOWN": "SHIFT ↓"}.get(verdict, verdict),
                             "reason": str(v.get("reason") or "")[:160]})
    zones = [(m, "overlay") for m in ((ov.get("data") or {}).get("missing") or ())]
    zones += [(z, "independent") for z in ((ind.get("data") or {}).get("zones") or ())]
    for z, src in zones:
        b = {"lo": float(z["approx_low"]), "hi": float(z["approx_high"])}
        if any(CR.overlaps(b, a) for a in alive) or any(CR.overlaps(b, m) for m in out["missing"]):
            continue
        out["missing"].append({"lo": round(b["lo"], 2), "hi": round(b["hi"], 2), "kind": z.get("kind"), "tf": tf, "src": src,
                               "reason": str(z.get("reason") or "")[:160]})
    if ov.get("status") == "OK":
        d = ov["data"]
        out["trend"] = {"agrees": bool(d.get("agrees_with_engine_state")), "vision": d.get("trend_state"), "engine": est}
    if ind.get("status") == "OK":
        vs = ind["data"].get("trend_state")
        out["structure"] = {"agrees": direction(vs) == direction(est), "vision": vs, "engine": est}
    out["status"] = "ok" if ov.get("status") in ("OK", "SKIPPED") or ind.get("status") == "OK" else "failed"
    if out["status"] == "failed":
        out["why"] = ov.get("error") or ind.get("error")
    return out


def audit(client, cfg, V, sym, facts, tfs=TFS, audit_date=None, render_fn=None, allow=None, on_usage=None):
    """Every timeframe (each independent: one failing never stops the others). Returns [per-tf dict]."""
    res = []
    for tf in tfs:
        try:
            res.append(audit_tf(client, cfg, V, sym, facts, tf, audit_date, render_fn, allow, on_usage))
        except Exception as exc:                                           # noqa: BLE001 — information only
            res.append({"tf": tf, "status": "failed", "why": f"{type(exc).__name__}: {str(exc)[:160]}", "areas": [], "not_visible": [],
                        "missing": [], "duplicates": [], "trend": None, "structure": None})
    return res


def summarise(results):
    """The per-tf results ⇒ the report section's dict (bots_common.chart_reading_text.sec_vision)."""
    ok = [r for r in results or () if r.get("status") == "ok"]
    if not ok:
        why = "; ".join(f"{r['tf']}: {r.get('why') or r.get('status')}" for r in results or ()) or "no timeframe audited"
        return {"status": "not_run", "why": why}
    counts = {"audited": 0, "VALID": 0, "SPURIOUS": 0, "SHIFT": 0}
    disagree, nv, missing, dups = [], [], [], []
    for r in ok:
        for a in r["areas"]:
            counts["audited"] += 1
            k = "SHIFT" if a["verdict"].startswith("SHIFT") else a["verdict"]
            counts[k] = counts.get(k, 0) + 1
            if a["verdict"] != "VALID":
                disagree.append(a)
        nv += r.get("not_visible") or []
        missing += r.get("missing") or []
        dups += r.get("duplicates") or []
    agr = {}
    for k in ("trend", "structure"):
        xs = [(r["tf"], r[k]) for r in ok if r.get(k)]
        if xs:
            agr[k] = {"agrees": all(x["agrees"] for _, x in xs), "vision": ", ".join(f"{tf} {x['vision']}" for tf, x in xs)}
    return {"status": "ok", "counts": counts, "disagree": disagree, "not_visible": sorted(set(nv)), "missing": missing,
            "duplicates": dups, "agreement": agr}


def reading_checks(sym, results):
    """Vision's disagreements as reading checks against a NAMED concept (for docs/reports/v22/OPEN_QUESTIONS.md) — never a rule."""
    out = []
    for r in results or ():
        if r.get("status") != "ok":
            continue
        for a in r["areas"]:
            if a["verdict"] != "VALID":
                out.append(f"{sym} {r['tf']}: Vision {a['verdict']} on area #{a['id']} {a['lo']:,.0f}–{a['hi']:,.0f} ({a['state']}) — "
                           f"concept C (area construction / K4 lifecycle) reading check: {a['reason']}")
        for z in r.get("missing") or ():
            out.append(f"{sym} {r['tf']}: Vision sees a zone the reader does not, {z['lo']:,.0f}–{z['hi']:,.0f} ({z.get('kind')}) — "
                       f"concept C (area births) reading check: {z.get('reason')}")
        for g in r.get("duplicates") or ():
            out.append(f"{sym} {r['tf']}: overlapping {g['kind']} areas {g['ids']} = one place — concept C / Z-1u reading check")
        for k, concept in (("trend", "§1 MTF state"), ("structure", "§2 A structure")):
            x = r.get(k)
            if x and not x["agrees"]:
                out.append(f"{sym} {r['tf']}: Vision {k} {x['vision']} vs the reader {x['engine']} — {concept} reading check")
    return out
