"""opportunity_engine/report.py — पान/CSV साठी UI-मुक्त मदतनीस (Streamlit/DB/network नाही): bundle बनवणं, state वही, levels तक्ता, चार्ट रेषा.

🎓 PR-1a: फक्त वाचन आणि प्रदर्शन. `page_opportunity_engine.py` हे वापरतं; गणित `structure/zones/level_quality` मध्ये.
"""
import pandas as pd

from . import sessions
from .adapters import to_engine_frame
from .config import EngineConfig, TF_LABEL, TF_ORDER
from .journal import Journal
from .zones import build_levels

STATE_LABEL = {
    "INIT": "सुरुवात (swings जमा होत आहेत)", "RANGE": "Range (बाजूची चाल)",
    "UPTREND": "Uptrend", "UPTREND_PULLBACK": "Uptrend — Pullback", "UPTREND_WEAK": "Uptrend कमजोर (CHoCH)",
    "DOWNTREND": "Downtrend", "DOWNTREND_PULLBACK": "Downtrend — Pullback", "DOWNTREND_WEAK": "Downtrend कमजोर (CHoCH)",
}
STATE_COLOR = {"UPTREND": "#00c853", "UPTREND_PULLBACK": "#66bb6a", "UPTREND_WEAK": "#ffb300", "DOWNTREND": "#ff1744",
               "DOWNTREND_PULLBACK": "#ef5350", "DOWNTREND_WEAK": "#ffb300", "RANGE": "#90a4ae", "INIT": "#90a4ae"}
ROLE_COLOR = {"SUPPORT": {"A": "#00c853", "B": "#26a69a", "C": "#81c784"}, "RESISTANCE": {"A": "#ff1744", "B": "#ef5350", "C": "#e57373"},
              "ZONE": {"A": "#ffa726", "B": "#ffb74d", "C": "#ffcc80"}}
KIND_SHORT = {"DEMAND": "DEM", "SUPPLY": "SUP", "SUPPORT": "SR-S", "RESISTANCE": "SR-R", "KEY": "KEY", "ROUND": "RND", "GAP": "GAP"}


def bundle_from_fine(df_fine, daily_extra=None, cfg=None, tfs=("1d", "4h", "1h", "15m", "5m")):
    """बारीक (1M/5M) डेटा -> (frames, journal). Upstox चे tz-aware candles adapter ने स्वच्छ होतात."""
    cfg = cfg or EngineConfig()
    fine = to_engine_frame(df_fine)
    frames = sessions.build_frames(fine, daily_extra)
    journal = Journal(cfg).run({tf: frames[tf] for tf in tfs if tf in frames})
    return frames, journal


def _ist_now():
    return pd.Timestamp.now(tz="Asia/Kolkata").tz_localize(None)


def bundle_from_live(df_5m, df_daily, cfg=None, tfs=("1d", "4h", "1h", "15m", "5m"), now=None):
    """Upstox 5M + Daily -> (frames, journal). Daily हे Upstox चेच (पूर्ण इतिहास), 5M वरून intraday TFs.
    🎓 no-lookahead: `now` (naive IST; डीफॉल्ट सध्याची वेळ) पर्यंत *बंद* झालेले 5M bars (start + 5 मि ≤ now) आणि बंद झालेला Daily bar फक्त वापरतो —
    Upstox चा सध्या चालू (forming) candle वगळला जातो."""
    cfg = cfg or EngineConfig()
    now = _ist_now() if now is None else pd.Timestamp(now)
    fine = to_engine_frame(df_5m)
    if len(fine):
        fine = fine[fine["timestamp"] + pd.Timedelta(minutes=5) <= now].reset_index(drop=True)
    frames = sessions.build_frames(fine)
    daily = to_engine_frame(df_daily)
    if len(daily):
        frames["1d"] = sessions.daily_from_daily_bars(daily.assign(volume=daily["volume"] if "volume" in daily.columns else 0.0), now=now)
    journal = Journal(cfg).run({tf: frames[tf] for tf in tfs if tf in frames})
    return frames, journal


def state_rows(journal):
    """प्रत्येक TF चा सद्य trend state, protected level, शेवटचे swings, ref_range, अद्ययावत वेळ (Structure वही)."""
    rows = []
    for tf in reversed(TF_ORDER):
        if tf not in journal.trackers or not journal.trackers[tf].c:
            continue
        s = journal.snapshot(tf)
        rows.append({
            "TF": TF_LABEL[tf], "State": STATE_LABEL.get(s["trend_state"], s["trend_state"]), "Protected level": s["protected_level"],
            "शेवटचा Swing High": s["last_sh"], "शेवटचा Swing Low": s["last_sl"], "Range High": s["range_high"], "Range Low": s["range_low"],
            "ref_range": None if s["ref_range"] is None else round(s["ref_range"], 2), "Bars": s["bars"], "अद्ययावत": s["updated_at"],
        })
    return pd.DataFrame(rows)


def levels_table(levels, price=None):
    rows = []
    for i, z in enumerate(levels, start=1):
        mid = (z["core_low"] + z["core_high"]) / 2.0
        rows.append({
            "#": f"L{i}", "level_id": z["level_id"], "TF": TF_LABEL.get(z["tf"], z["tf"]), "प्रकार": z["kind"], "स्रोत": z.get("source", ""),
            "Grade": z["quality_grade"], "Score": round(z["quality_score"], 2), "भूमिका": z["role"],
            "Core": f"{z['core_low']:.2f} – {z['core_high']:.2f}", "Outer": f"{z['outer_low']:.2f} – {z['outer_high']:.2f}",
            "अंतर %": None if not price else round((mid - price) / price * 100.0, 2),
            "Freshness": z["freshness"], "Status": z["status"], "Touches": z["touches"], "Origin": z["origin_type"], "MTF": z["mtf_count"],
            "MINOR": "होय" if z["minor"] else "", "Gap": z.get("gap_status", ""),
            **{f"Q:{k}": v for k, v in z["quality_components"].items()},
            "नाकारण्याचं कारण": z.get("reject_reason") or "",
        })
    return pd.DataFrame(rows)


def chart_lines(levels, price, max_levels=12, max_distance_pct=3.0, grades=("A", "B")):
    """चार्टसाठी (tradingview_chart trade_lines): किंमतीजवळचे A/B levels, `L1…` क्रमांकासह. रुंद zones साठी outer किनार ठिपक्यांत."""
    if not price:
        return [], []
    near = [z for z in levels if z["quality_grade"] in grades and abs(((z["core_low"] + z["core_high"]) / 2.0 - price) / price * 100.0) <= max_distance_pct]
    chosen = []
    for z in near:
        z.pop("also_tfs", None)
    for z in sorted(near, key=lambda z: -z["quality_score"]):
        mid = (z["core_low"] + z["core_high"]) / 2.0
        twin = next((c for c in chosen if abs((c["core_low"] + c["core_high"]) / 2.0 - mid) <= mid * 0.0005), None)
        if twin is not None:                              # एकाच किंमतीवरचा दुसरा TF = confluence; वेगळी रेषा नाही, फक्त नावात जोडतो
            twin.setdefault("also_tfs", []).append(TF_LABEL.get(z["tf"], z["tf"]))
            continue
        if len(chosen) < max_levels:
            chosen.append(z)
    near = chosen
    lines = []
    for n, z in enumerate(near, start=1):
        mid = (z["core_low"] + z["core_high"]) / 2.0
        color = ROLE_COLOR.get(z["role"], ROLE_COLOR["ZONE"])[z["quality_grade"]]
        also = "".join(f"+{t}" for t in dict.fromkeys(z.get("also_tfs", [])))
        title = f"L{n} {z['quality_grade']} {TF_LABEL.get(z['tf'], z['tf'])}{also} {KIND_SHORT.get(z['kind'], z['kind'])} {z['freshness']}"
        lines.append({"price": float(mid), "title": title, "color": color, "dashed": z["quality_grade"] != "A", "width": 3 if z["quality_grade"] == "A" else 2})
        far = z["outer_high"] if abs(z["outer_high"] - mid) >= abs(z["outer_low"] - mid) else z["outer_low"]
        if abs(far - mid) >= mid * 0.0002:
            lines.append({"price": float(far), "title": f"L{n} ↔ outer", "color": color, "dashed": True, "width": 1})
    return lines, near


def structure_csv(journal, tfs=("1d", "4h", "1h")):
    """Structure accuracy CSV (अनिवार्य): तारीख, TF, event, नवीन state, किंमत, trigger_bar, तपशील — Daily/4H/1H."""
    table = journal.structure_table(tfs)
    return table[table["event"] != "SWEEP"].to_csv(index=False)


def swings_table(journal, tf, limit=60):
    tr = journal.trackers.get(tf)
    if tr is None:
        return pd.DataFrame()
    rows = [{"swing_time": s.time, "confirmed_at": s.confirmed_time, "प्रकार": "High" if s.kind == "H" else "Low", "किंमत": round(s.price, 2),
             "Label": s.label, "spike": "होय" if s.spike else ""} for s in tr.swings[-limit:]]
    return pd.DataFrame(rows).iloc[::-1].reset_index(drop=True)


def quality_report(frames):
    """डेटा गुणवत्ता: short sessions (Daily bar_is_full == False) ची यादी + प्रत्येक TF मधले bars आणि अपूर्ण bars."""
    rows = []
    for tf in reversed(TF_ORDER):
        df = frames.get(tf)
        if df is None or df.empty:
            continue
        rows.append({"TF": TF_LABEL[tf], "Bars": len(df), "अपूर्ण (bar_is_full=False)": int((~df["bar_is_full"]).sum()), "पहिला": df["bar_start"].min(), "शेवटचा bar_end": df["bar_end"].max()})
    short = pd.DataFrame()
    daily = frames.get("1d")
    if daily is not None and len(daily):
        short = daily.loc[~daily["bar_is_full"], ["timestamp", "open", "high", "low", "close"]].rename(columns={"timestamp": "तारीख"})
    return pd.DataFrame(rows), short
