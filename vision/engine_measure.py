"""vision/engine_measure.py — T-5 point 4 (DECISIONS 31, PROVISIONAL): for every closed engine trade, Vision's verdict vs Abhi's
decision vs the outcome — the outcome by STRUCTURE (REPORT_STANDARD §4: the next area reached first / a close beyond the invalidation
first / open at data end, followed forward across sessions with the data there is) and the trade's P&L. Read only; reuses the stored
data (vision_signals: verdict, human_decision, final_decision, vision_json.context.engine, outcome_json). Never an order, never a
setting, never a reading rule — a measurement for Abhi's review of the provisional engine audit.
"""
import json

import pandas as pd

from . import chart as CH

FIRST = ("next_area_first", "invalidation_first", "open_at_data_end")    # = reader_report.standard.OUTCOMES
NOT_MEASURED = "not_measured"
VERDICT_ROWS = ("agree", "gray", "disagree", "unavailable")


def _j(x):
    if isinstance(x, dict):
        return x
    try:
        v = json.loads(x or "{}")
    except (TypeError, ValueError):
        return {}
    return v if isinstance(v, dict) else {}


def tags_of(row):
    t = _j(row.get("setup_json")).get("tags")
    return t if isinstance(t, dict) else {}


def is_engine_row(row):
    return tags_of(row).get("engine") is True


def reading_of(row):
    """The engine reading the card showed (vision_json.context.engine); not stored (older row) ⇒ re-derived from the signal tags."""
    rd = (_j(row.get("vision_json")).get("context") or {}).get("engine")
    if isinstance(rd, dict):
        return rd
    from . import engine_audit as EA
    return EA.reading({"tags": tags_of(row), "direction": row.get("direction"), "spot": row.get("spot")})


def structure_outcome(df1m, row, start=None):
    """Which came first after `start` (the trade's entry; default the signal): price reaching the next area in the trade direction
    (a 1m bar trading into its near edge) or a completed 15M candle closing beyond the invalidation. Comparison only; the data's end
    is the only horizon. ⇒ {"result": one of FIRST | "not_measured", "at", "next_area", "invalidation", "note"}."""
    rd = reading_of(row)
    d = 1 if str(row.get("direction") or "").upper().startswith("BULL") else -1
    nx, inv = rd.get("next_area"), rd.get("invalidation")
    out = {"result": NOT_MEASURED, "at": None, "next_area": None if not nx else [nx.get("lo"), nx.get("hi")], "invalidation": inv,
           "note": None}
    if inv is None and not nx:
        out["note"] = "no invalidation and no next area in the signal"
        return out
    m = CH.norm_1m(df1m)
    t0 = pd.Timestamp(CH.to_ist_naive(start if start is not None else row["signal_ts"]))
    if len(m) and pd.Timestamp(m["timestamp"].iloc[0]) > t0:
        out["note"] = "the data does not reach back to the entry"
        return out
    m = m[m["timestamp"] >= t0].reset_index(drop=True)
    if not len(m):
        out.update(result="open_at_data_end", note="no data after the entry yet")
        return out
    t_touch = None
    if nx and nx.get("lo") is not None and nx.get("hi") is not None:
        hit = m[m["low"] <= float(nx["hi"])] if d < 0 else m[m["high"] >= float(nx["lo"])]
        t_touch = None if not len(hit) else pd.Timestamp(hit["timestamp"].iloc[0])
    t_inv = None
    if inv is not None:
        b = CH.resample(m, 15)
        done = b[b["last_ts"] + pd.Timedelta(minutes=1) >= b["end"]]          # completed 15M candles only (the close is final)
        hit = done[done["close"] > float(inv)] if d < 0 else done[done["close"] < float(inv)]
        t_inv = None if not len(hit) else pd.Timestamp(hit["end"].iloc[0])
    if t_touch is None and t_inv is None:
        out["result"] = "open_at_data_end"
    elif t_inv is None or (t_touch is not None and t_touch < t_inv):        # the touch happens inside the bar, before its close
        out.update(result="next_area_first", at=str(t_touch))
    else:
        out.update(result="invalidation_first", at=str(t_inv))
    if not nx:
        out["note"] = "next area unknown — only the invalidation is followed"
    return out


def closed_rows(rows):
    """Every engine signal with a closed trade (EXECUTED after ✅, or the shadow trade of a rejected card): one record each."""
    out = []
    for r in rows or []:
        if not is_engine_row(r):
            continue
        oj = _j(r.get("outcome_json"))
        if not oj.get("trade_id"):
            continue
        t = tags_of(r)
        st = oj.get("structure") if isinstance(oj.get("structure"), dict) else {}
        out.append({"signal_ts": r.get("signal_ts"), "symbol": r.get("symbol"), "model": t.get("entry_label") or t.get("entry_model"),
                    "direction": r.get("direction"), "level": r.get("level"), "verdict": r.get("verdict") or "unavailable",
                    "abhi": r.get("human_decision") or "—", "final": r.get("final_decision"), "status": r.get("status"),
                    "structure": st.get("result") or NOT_MEASURED, "pnl": oj.get("realized_pnl"), "result": oj.get("result"),
                    "prompt_version": r.get("prompt_version"), "signal_id": r.get("signal_id")})
    return out


def table(records):
    """"Vision agreed / disagreed / gray × result": one row per Vision verdict — trades, the structure outcomes, wins / losses, P&L
    sum, and Abhi's ✅ / ❌ count. Empty input ⇒ an empty frame with the columns."""
    cols = ["verdict", "trades", "abhi_approve", "abhi_reject", *FIRST, NOT_MEASURED, "win", "loss", "pnl"]
    rows = []
    for v in VERDICT_ROWS:
        g = [x for x in records if x["verdict"] == v]
        if not g:
            continue
        pnl = [float(x["pnl"]) for x in g if x.get("pnl") is not None]
        rows.append({"verdict": v, "trades": len(g), "abhi_approve": sum(x["abhi"] == "approve" for x in g),
                     "abhi_reject": sum(x["abhi"] == "reject" for x in g),
                     **{k: sum(x["structure"] == k for x in g) for k in (*FIRST, NOT_MEASURED)},
                     "win": sum(x.get("result") == "win" for x in g), "loss": sum(x.get("result") == "loss" for x in g),
                     "pnl": round(sum(pnl), 2) if pnl else None})
    return pd.DataFrame(rows, columns=cols)


def refresh_open(fetch, path=None, since_day=None):
    """Engine rows whose structure outcome was still open at data end (or not measured): follow them forward with today's data and
    store the new result inside outcome_json["structure"]. ⇒ [(signal_id, result)]. One row's error never stops the others."""
    from . import store as VS
    out, cache = [], {}
    for r in VS.list_signals(None, path):
        if since_day is not None and str(r.get("signal_ts") or "")[:10] < str(since_day):
            continue
        if not is_engine_row(r):
            continue
        oj = _j(r.get("outcome_json"))
        st = oj.get("structure") if isinstance(oj.get("structure"), dict) else None
        if not oj.get("trade_id") or (st is not None and st.get("result") in ("next_area_first", "invalidation_first")):
            continue
        try:
            if r["symbol"] not in cache:
                cache[r["symbol"]] = fetch(r["symbol"])
            new = structure_outcome(cache[r["symbol"]], r, oj.get("entry_time"))
            if new != st:
                VS.set_outcome(r["signal_id"], path, outcome_json={**oj, "structure": new})
            out.append((r["signal_id"], new["result"]))
        except Exception as exc:                                         # noqa: BLE001 — measurement only
            out.append((r["signal_id"], f"error: {type(exc).__name__}: {str(exc)[:120]}"))
    return out
