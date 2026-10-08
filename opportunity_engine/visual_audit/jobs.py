"""opportunity_engine/visual_audit/jobs.py — EOD run आणि historical backfill साठी एकच chart→audit साखळी + खर्चाचा अंदाज.

🎓 No-lookahead: audit_date D चे charts आणि levels फक्त D−1 च्या बंद bars पर्यंतचे (`cutoff`); swings सुद्धा `confirmed_time ≤ cutoff`.
खर्च: प्रत्येक chart = 2 calls (overlay + स्वतंत्र). Image ≈ (W×H)/784 tokens (28×28 patch; 1280×720 ⇒ ≈ 1,176) — अंदाज; अचूक आकडा `count_tokens` ने
(API key असल्यास) एका नमुन्यावर. Output tokens (thinking + JSON) अंदाज `out_tokens` (डीफॉल्ट 1,500) — पहिल्या खऱ्या runs च्या usage वरून दुरुस्त करा.
"""
import json
import os

import pandas as pd

from . import auditor as A
from . import render as R

CHART_TFS = ("1d", "1h", "15m")
TEXT_CHARS_PER_TOKEN = 4.0


def as_of(frame, cutoff):
    if frame is None or not len(frame):
        return frame
    d = frame[frame["bar_end"] <= pd.Timestamp(cutoff)]
    return d[d["bar_closed"]] if "bar_closed" in d.columns else d


def swings_asof(journal, tf, cutoff):
    tr = None if journal is None else journal.trackers.get(tf)
    if tr is None:
        return []
    cut = pd.Timestamp(cutoff)
    return [sw for sw in tr.swings if sw.confirmed_time is not None and pd.Timestamp(sw.confirmed_time) <= cut]


def prepare_chart(frames, journal, levels, tf, symbol, cutoff, bars=None, render=True):
    """एका TF चा chart: window, labels, PNG (overlay + plain), किंमत-पट्टा, labelled levels चे §2.6 components."""
    df = R.window(as_of(frames.get(tf), cutoff), tf, bars)
    if df is None or len(df) < 5:
        return None
    lo, hi = float(df["low"].min()), float(df["high"].max())
    labels = R.assign_labels(levels, tf, lo, hi, price=float(df["close"].iloc[-1]))
    by_id = {z.get("level_id"): z for z in levels}
    comps = {l["level_id"]: by_id[l["level_id"]].get("quality_components") for l in labels if by_id.get(l["level_id"], {}).get("quality_components")}
    swings = swings_asof(journal, tf if tf != "1h" else "1h", cutoff)
    out = {"tf": tf, "df": df, "labels": labels, "lo": lo, "hi": hi, "components": comps, "png_overlay": None, "png_plain": None}
    if render:
        out["png_overlay"] = R.render_png(df, tf, symbol, labels, swings, overlay=True) if labels else None
        out["png_plain"] = R.render_png(df, tf, symbol, None, None, overlay=False)
    return out


def audit_day(client, vcfg, symbol, audit_date, frames, journal, levels, pool, states, cutoff, tfs=CHART_TFS, fewshot=None, png_dir=None, log=None,
              allow=None, skipped=None, on_chart=None):
    """एका दिवसाचे सर्व TF charts audit. states = {tf: engine trend state}. रिटर्न records (JSON-योग्य).
    allow(tf) ⇒ (ok, कारण): प्रत्येक chart आधी (budget); नाही ⇒ तो chart वगळला, `skipped` यादीत (tf, कारण) — API call नाही.
    on_chart(rec): प्रत्येक audit झालेल्या chart नंतर **लगेच** (खर्च नोंद) ⇒ पुढच्या chart चा allow तो खर्च पाहतो (review PR #274)."""
    records = []
    for tf in tfs:
        if allow is not None:
            ok, why = allow(tf)
            if not ok:
                if skipped is not None:
                    skipped.append((tf, why))
                if log:
                    log(f"  ⏭️ {symbol} {tf}: वगळलं — {why}")
                continue
        ch = prepare_chart(frames, journal, levels, tf, symbol, cutoff)
        if ch is None:
            continue
        if png_dir:
            os.makedirs(png_dir, exist_ok=True)
            for kind in ("overlay", "plain"):
                if ch[f"png_{kind}"] is not None:
                    with open(os.path.join(png_dir, f"{symbol}_{tf}_{kind}.png"), "wb") as fh:
                        fh.write(ch[f"png_{kind}"])
        rec = A.audit_chart(client, vcfg, symbol, tf, audit_date, ch["png_overlay"], ch["png_plain"], ch["labels"], pool, states.get(tf if tf != "1h" else "1h"),
                            ch["lo"], ch["hi"], fewshot)
        rec["components"] = ch["components"]
        records.append(rec)
        if on_chart is not None:
            on_chart(rec)
        if log:
            log(f"  {symbol} {tf}: overlay {rec['overlay']['status']}, स्वतंत्र {rec['independent']['status']}, tokens {rec['usage']['input_tokens']}/{rec['usage']['output_tokens']}")
    return records


# ---------------------------------------------------------------------------------------------------------------------
# खर्च
# ---------------------------------------------------------------------------------------------------------------------
def image_tokens(width=R.WIDTH, height=R.HEIGHT):
    return int(round(width * height / 784.0))


def text_tokens(text):
    return int(round(len(text) / TEXT_CHARS_PER_TOKEN))


def per_call_input_estimate(n_labels=8, kind="overlay"):
    labels = [{"label": f"L{i}", "level_id": "x" * 16, "kind": "DEMAND", "tf": "1h", "core_low": 24000.0, "core_high": 24020.0,
               "outer_low": 23990.0, "outer_high": 24030.0, "grade": "B"} for i in range(n_labels)]
    txt = A.overlay_text("NIFTY", "1h", labels, "UPTREND") if kind == "overlay" else A.independent_text("NIFTY", "1h")
    schema = json.dumps(A.OVERLAY_SCHEMA if kind == "overlay" else A.INDEPENDENT_SCHEMA)
    return image_tokens() + text_tokens(A.SYSTEM_PROMPT) + text_tokens(txt) + text_tokens(schema)


def estimate(n_charts, price_in=None, price_out=None, out_tokens=1500, batch=False, n_labels=8):
    """n_charts (प्रत्येकी 2 calls) -> {calls, input_tokens, output_tokens, cost_usd (किंमत दिली असेल तर)}. price_* = $ per 1M tokens. batch ⇒ 50%."""
    calls = 2 * int(n_charts)
    tin = int(n_charts) * (per_call_input_estimate(n_labels, "overlay") + per_call_input_estimate(n_labels, "independent"))
    tout = calls * int(out_tokens)
    out = {"charts": int(n_charts), "calls": calls, "input_tokens": tin, "output_tokens": tout, "cost_usd": None, "batch": bool(batch)}
    if price_in is not None and price_out is not None:
        cost = tin / 1e6 * float(price_in) + tout / 1e6 * float(price_out)
        out["cost_usd"] = round(cost * (0.5 if batch else 1.0), 2)
    return out


def exact_input_tokens(client, params):
    """count_tokens (API key हवी; generation खर्च नाही) — एका नमुन्याचे अचूक input tokens. अपयश ⇒ None."""
    try:
        res = client.messages.count_tokens(model=params["model"], system=params["system"], messages=params["messages"])
        return int(res.input_tokens)
    except Exception:
        return None
