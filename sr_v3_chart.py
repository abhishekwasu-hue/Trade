"""sr_v3_chart.py — SR Levels V3 साठी UI-मुक्त मदतनीस: डेटा आणणे (5M/15M/30M/1H/Daily) आणि चार्टसाठी रेषा तयार करणे.
Dashboard चार्टचा "Bot view" dropdown (V3_VIEW) आणि page_sr_levels_v3.py दोन्ही हेच वापरतात — म्हणजे दोन्हीकडे सारखेच levels.
कुठलाही trade/DB write नाही; डेटा आणणारं फंक्शन (`fetch_fn`) बाहेरून दिलं जातं."""
from signals import resample_to_1h
from sr_levels_v3 import SRConfig, compute_sr_v3, select_display_levels, to_chart_lines

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


def v3_chart_lines(fetch_fn, token_input, symbol, price, cfg=None):
    """Dashboard चार्टसाठी: (chart_lines, note). डेटा/levels नसतील तर ([], कारण-सांगणारी note). exception बाहेर जात नाही."""
    cfg = cfg or SRConfig()
    try:
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
