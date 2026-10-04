"""sr_v3_chart.py — SR Levels V3 साठी UI-मुक्त मदतनीस: डेटा आणणे (5M/15M/30M/1H/Daily) आणि चार्टसाठी रेषा तयार करणे.
Dashboard चार्टचा "Bot view" dropdown (V3_VIEW) आणि page_sr_levels_v3.py दोन्ही हेच वापरतात — म्हणजे दोन्हीकडे सारखेच levels.
कुठलाही trade/DB write नाही; डेटा आणणारं फंक्शन (`fetch_fn`) बाहेरून दिलं जातं."""
import dataclasses

import pandas as pd

from signals import resample_to_1h, resample_to_4h
from sr_levels_v3 import TF_SHORT, SRConfig, compute_sr_v3, select_display_levels, to_chart_lines

V3_VIEW = "SR Levels V3 (नवीन)"
CHART_TFS = ["5minute", "15minute", "30minute"]
# Upstox मधून किती कॅलेंडर दिवस मागवायचे (pivot lookback + आठवड्याच्या शेवटचा/सुट्ट्यांचा फरक भरून काढायला जास्त)
FETCH_DAYS = {"5minute": 8, "15minute": 12, "30minute": 16, "day": 30}


def _with_extra_columns(df):
    out = df.copy()
    for col in ("volume", "oi"):
        if col not in out.columns:
            out[col] = 0
    return out


def load_frames(fetch_fn, token_input, symbol):
    """V3 इंजिनला हवे ते सर्व TF: ({tf: df}, daily_df|None). 1H हे 30M वरून resample (बाकी प्रोजेक्ट प्रमाणेच).
    `spot` हा fetch_candles मध्ये फक्त cache key आहे (वापरला जात नाही) — बदलत्या किंमतीमुळे प्रत्येक rerun ला cache चुकू नये म्हणून 0."""
    spot = 0
    frames = {}
    for tf in CHART_TFS:
        df = fetch_fn(token_input, symbol, spot, interval=tf, lookback_days=FETCH_DAYS[tf])
        if df is not None and not df.empty:
            frames[tf] = df
    if "30minute" in frames:
        frames["1hour"] = resample_to_1h(_with_extra_columns(frames["30minute"]))
    daily = fetch_fn(token_input, symbol, spot, interval="day", lookback_days=FETCH_DAYS["day"])
    return frames, (daily if daily is not None and not daily.empty else None)


# 🎓 वापरकर्त्याची मागणी: "chart चा timeframe बदलला की levels सुद्धा त्या TF नुसार बदलायला हवेत" -- chart TF ⇒ levels कुठल्या TF च्या pivots वरून.
# (chart TF दिला नाही ⇒ जुनं वर्तन: 5M+15M+30M+1H.) 1M chart ला 1M pivots नाहीत (फार गोंगाट) -- 5M पासून.
CHART_TF_SETS = {
    "1minute": ("5minute", "15minute", "30minute"),
    "5minute": ("5minute", "15minute", "30minute"),
    "15minute": ("15minute", "30minute", "1hour"),
    "30minute": ("30minute", "1hour", "4hour"),
    "1hour": ("1hour", "4hour", "day"),
    "day": ("day", "week"),
}
# मोठ्या TF च्या chart वर levels स्वाभाविकपणे किंमतीपासून दूर असतात -- दाखवण्याची अंतर-मर्यादा (%) त्यानुसार
DISPLAY_MAX_DISTANCE_PCT = {"30minute": 4.0, "1hour": 6.0, "day": 12.0}


def tf_set_label(chart_tf):
    tfs = CHART_TF_SETS.get(chart_tf)
    return "+".join(TF_SHORT[t] for t in tfs) if tfs else "5M+15M+30M+1H"


def _weekly(daily):
    d = _with_extra_columns(daily).copy()
    d["timestamp"] = pd.to_datetime(d["timestamp"])
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum", "oi": "last"}
    w = d.set_index("timestamp").resample("W-FRI", label="left", closed="right").agg(agg).dropna(subset=["open"]).reset_index()
    return w


def frames_for_chart_tf(fetch_fn, token_input, symbol, chart_tf):
    """chart TF प्रमाणे V3 इंजिनचे frames आणि daily (key levels साठी). 1H/4H हे 30M वरून, Weekly हे Daily वरून resample."""
    want = CHART_TF_SETS[chart_tf]
    spot, frames = 0, {}
    for tf in ("5minute", "15minute"):
        if tf in want:
            df = fetch_fn(token_input, symbol, spot, interval=tf, lookback_days=FETCH_DAYS[tf])
            if df is not None and not df.empty:
                frames[tf] = df
    if any(tf in want for tf in ("30minute", "1hour", "4hour")):
        days = 70 if "4hour" in want else FETCH_DAYS["30minute"]
        df30 = fetch_fn(token_input, symbol, spot, interval="30minute", lookback_days=days)
        if df30 is not None and not df30.empty:
            df30 = _with_extra_columns(df30)
            if "30minute" in want:
                frames["30minute"] = df30
            if "1hour" in want:
                frames["1hour"] = resample_to_1h(df30)
            if "4hour" in want:
                frames["4hour"] = resample_to_4h(df30)
    daily_days = 400 if ("day" in want or "week" in want) else FETCH_DAYS["day"]
    daily = fetch_fn(token_input, symbol, spot, interval="day", lookback_days=daily_days)
    daily = daily if daily is not None and not daily.empty else None
    if daily is not None:
        if "day" in want:
            frames["day"] = daily
        if "week" in want:
            frames["week"] = _weekly(daily)
    return frames, daily


def v3_chart_lines(fetch_fn, token_input, symbol, price, cfg=None, chart_tf=None):
    """Dashboard चार्टसाठी: (chart_lines, note). डेटा/levels नसतील तर ([], कारण-सांगणारी note). exception बाहेर जात नाही."""
    cfg = cfg or SRConfig()
    if chart_tf in DISPLAY_MAX_DISTANCE_PCT:
        cfg = dataclasses.replace(cfg, max_distance_pct=max(cfg.max_distance_pct, DISPLAY_MAX_DISTANCE_PCT[chart_tf]))
    try:
        if chart_tf in CHART_TF_SETS:
            frames, daily_df = frames_for_chart_tf(fetch_fn, token_input, symbol, chart_tf)
        else:
            frames, daily_df = load_frames(fetch_fn, token_input, symbol)
        if not frames:
            return [], "SR Levels V3: candle डेटा मिळाला नाही — levels दाखवता आले नाहीत."
        result = compute_sr_v3(frames, daily_df=daily_df, current_price=price, cfg=cfg)
        shown = select_display_levels(result["levels"], price, cfg)
        if not shown:
            return [], "SR Levels V3: सध्या किंमतीजवळ पात्र level सापडला नाही."
        return to_chart_lines(shown), None
    except Exception as e:  # चार्ट दिसत राहावा; कारण caption मध्ये
        return [], f"SR Levels V3 लोड करता आला नाही ({type(e).__name__}: {e})."
