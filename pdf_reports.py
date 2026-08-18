"""PDF report generation: Market Analysis Report and Signal Backtest Report — fonts, colors, charts, tables."""
import datetime
import io
import os
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak
from reportlab.lib.enums import TA_LEFT, TA_CENTER

from signals import add_price_action_overlays, describe_price_action, calculate_supertrend, calculate_rsi, analyze_chart_zones, check_price_action_strategy, find_swing_sr_levels_rolling, get_nearest_sr
from trading_engine import normalize_legs


_RPT_FONT = "Times-Roman"

_RPT_FONT_BOLD = "Times-Bold"

_RPT_TABLE_FONT = "Helvetica"

_RPT_TABLE_FONT_BOLD = "Helvetica-Bold"

_RPT_FONT_MISSING_WARNING = None

try:
    _font_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
    _reg_path = os.path.join(_font_dir, "DejaVuSans.ttf")
    _bold_path = os.path.join(_font_dir, "DejaVuSans-Bold.ttf")
    if os.path.exists(_reg_path) and os.path.exists(_bold_path):
        pdfmetrics.registerFont(TTFont("DejaVuSans", _reg_path))
        pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", _bold_path))
        _RPT_TABLE_FONT = "DejaVuSans"
        _RPT_TABLE_FONT_BOLD = "DejaVuSans-Bold"
    else:
        _RPT_FONT_MISSING_WARNING = (
            "WARNING: fonts/DejaVuSans.ttf and/or fonts/DejaVuSans-Bold.ttf not found — symbols "
            "(checkmarks, triangles, etc.) in this PDF will not render correctly. Add both font files "
            "to a 'fonts/' folder next to app.py in your repo."
        )
except Exception:
    _RPT_FONT_MISSING_WARNING = "WARNING: Error loading fonts — some symbols may not render correctly."


_C_BG_DARK = colors.HexColor("#131722")

_C_ACCENT = colors.HexColor("#2962FF")

_C_GREEN = colors.HexColor("#089981")

_C_GREEN_BG = colors.HexColor("#E3F6EF")

_C_RED = colors.HexColor("#F23645")

_C_RED_BG = colors.HexColor("#FDECEE")

_C_AMBER = colors.HexColor("#D68A00")

_C_AMBER_BG = colors.HexColor("#FDF3DC")

_C_GREY = colors.HexColor("#787B86")

_C_GREY_BG = colors.HexColor("#F2F2F2")

_C_ACCENT_BG = colors.HexColor("#E8EFFF")

_SECTION_COLORS = [colors.HexColor("#2962FF"), colors.HexColor("#7E57C2"), colors.HexColor("#00897B"),
                    colors.HexColor("#D68A00"), colors.HexColor("#E64A19")]

_rpt_styles = getSampleStyleSheet()

_rpt_h1 = ParagraphStyle("rpt_h1", fontName=_RPT_FONT_BOLD, fontSize=24, leading=28, textColor=colors.white)

_rpt_h1_sub = ParagraphStyle("rpt_h1_sub", fontName=_RPT_FONT, fontSize=12, leading=16, textColor=colors.HexColor("#B8BEC9"))

_rpt_h2 = ParagraphStyle("rpt_h2", fontName=_RPT_FONT_BOLD, fontSize=16, leading=19, textColor=colors.white, spaceBefore=0, spaceAfter=0)

_rpt_h2_bt = ParagraphStyle("rpt_h2_bt", fontName=_RPT_FONT_BOLD, fontSize=18, leading=22, textColor=colors.white, spaceBefore=0, spaceAfter=0)

_rpt_h3 = ParagraphStyle("rpt_h3", fontName=_RPT_FONT_BOLD, fontSize=12, leading=15, textColor=colors.HexColor("#333333"), spaceBefore=6, spaceAfter=3)

_rpt_normal = ParagraphStyle("rpt_normal", fontName=_RPT_FONT, fontSize=11.5, leading=15, alignment=TA_LEFT)

_rpt_meta = ParagraphStyle("rpt_meta", fontName=_RPT_FONT, fontSize=11.5, leading=15, textColor=colors.HexColor("#555555"))

_rpt_value_big = ParagraphStyle("rpt_value_big", fontName=_RPT_FONT_BOLD, fontSize=18, leading=22, textColor=_C_BG_DARK)

_rpt_footer = ParagraphStyle("rpt_footer", fontName=_RPT_FONT, fontSize=8, leading=11, textColor=colors.HexColor("#888888"))

_rpt_badge_green = ParagraphStyle("rpt_badge_green", fontName=_RPT_FONT_BOLD, fontSize=14, leading=18, textColor=_C_GREEN, alignment=TA_CENTER)

_rpt_badge_red = ParagraphStyle("rpt_badge_red", fontName=_RPT_FONT_BOLD, fontSize=14, leading=18, textColor=_C_RED, alignment=TA_CENTER)

_rpt_badge_grey = ParagraphStyle("rpt_badge_grey", fontName=_RPT_FONT_BOLD, fontSize=14, leading=18, textColor=_C_GREY, alignment=TA_CENTER)

def _section_header(text, idx, style=None):
    """Coloured full-width banner for each section heading — rotates through an accent palette."""
    color = _SECTION_COLORS[idx % len(_SECTION_COLORS)]
    tbl = Table([[Paragraph(text, style or _rpt_h2)]], colWidths=[18 * cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return tbl

def _signal_style(text):
    """Colour classification for a status string — used for both badges and table row tints."""
    t = str(text).upper()
    if "BEARISH" in t or "BEARS" in t or t == "WRONG" or t == "SL":
        return _C_RED, _C_RED_BG
    if "PAPER" in t:
        return _C_ACCENT, _C_ACCENT_BG
    if "BULLISH" in t or "BULLS" in t or "LIVE" in t or t.startswith("[OK]") or t == "OK" or t == "CORRECT" or t == "TARGET":
        return _C_GREEN, _C_GREEN_BG
    if "NO TRADE" in t or "WEAKENING" in t or "[!]" in t or t == "OPEN":
        return _C_AMBER, _C_AMBER_BG
    if t.startswith("[X]") or t.startswith("[NO]"):
        return _C_RED, _C_RED_BG
    return _C_GREY, _C_GREY_BG

def build_report_chart_image(df, title, zone_info=None, width=620, height=420):
    """
    Render a candlestick chart to PNG via kaleido, annotated with BOS/CHoCH break line, Demand/Supply
    zones, and price-action overlays (Support/Resistance, Trendlines, Swing High/Low markers).
    Returns (image_bytes_or_None, description_text). Image is None (gracefully) if kaleido/Chrome isn't available.
    """
    if df is None or df.empty:
        return None, "No data available for this timeframe."
    try:
        fig = go.Figure(data=[go.Candlestick(
            x=df["timestamp"], open=df["open"], high=df["high"], low=df["low"], close=df["close"],
            increasing_line_color="#089981", decreasing_line_color="#F23645",
            showlegend=False,
        )])
        if zone_info:
            demand = zone_info.get("demand_zone")
            supply = zone_info.get("supply_zone")
            bos = zone_info.get("bos_choch")
            if demand:
                fig.add_hrect(y0=demand[0], y1=demand[1], fillcolor="#089981", opacity=0.15, line_width=0,
                               annotation_text="Demand", annotation_position="bottom left", annotation_font_size=9)
            if supply:
                fig.add_hrect(y0=supply[0], y1=supply[1], fillcolor="#F23645", opacity=0.15, line_width=0,
                               annotation_text="Supply", annotation_position="top left", annotation_font_size=9)
            if bos:
                line_color = "#089981" if bos["direction"] == "bullish" else "#F23645"
                fig.add_hline(y=bos["level"], line_dash="dash", line_color=line_color, line_width=1.6,
                               annotation_text=f"{bos['type']} ({bos['direction']})",
                               annotation_position="right", annotation_font_size=10, annotation_font_color=line_color)

        sr_levels, trendline_support, trendline_resistance = add_price_action_overlays(fig, df)
        description = describe_price_action(sr_levels, trendline_support, trendline_resistance, lang="en")

        fig.update_layout(
            title=title, template="plotly_white", width=width, height=height,
            margin=dict(l=10, r=110, t=36, b=10), xaxis_rangeslider_visible=False,
        )
        return fig.to_image(format="png", engine="kaleido", scale=3), description
    except Exception:
        return None, "Chart could not be generated."


def build_price_action_chart_v2(df, direction, timeframe_label, rsi_series=None, sr_window=20,
                                  rsi_oversold=30, rsi_overbought=70, width=620, height=420):
    """
    नवीन Price Action रणनीतीनुसार (Support/Resistance + RSI + Candlestick Reversal + Breakout) चार्ट
    तयार करणे, सोबत त्याच निकालांवरून डायनॅमिक (हार्डकोड नाही) इंग्रजी स्पष्टीकरण.
    Returns (image_bytes_or_None, description_text_in_english).
    """
    if df is None or df.empty or len(df) < 10:
        return None, "Not enough data available for this timeframe to run Price Action analysis."

    entry_ok, detail = False, {}
    chart_bytes = None
    try:
        entry_ok, detail = check_price_action_strategy(
            df, direction, rsi_series=rsi_series, sr_window=sr_window,
            rsi_oversold=rsi_oversold, rsi_overbought=rsi_overbought,
        )
        sr_levels = find_swing_sr_levels_rolling(df, window=sr_window)
        current_price = float(df["close"].iloc[-1])
        nearest_support, nearest_resistance = get_nearest_sr(sr_levels, current_price)

        fig = go.Figure(data=[go.Candlestick(
            x=df["timestamp"], open=df["open"], high=df["high"], low=df["low"], close=df["close"],
            increasing_line_color="#089981", decreasing_line_color="#F23645", showlegend=False,
        )])

        if nearest_support:
            fig.add_hline(y=nearest_support, line_dash="dot", line_color="#089981", line_width=1.4,
                          annotation_text=f"Support {nearest_support:,.0f}", annotation_position="right",
                          annotation_font_size=9, annotation_font_color="#089981")
        if nearest_resistance:
            fig.add_hline(y=nearest_resistance, line_dash="dot", line_color="#F23645", line_width=1.4,
                          annotation_text=f"Resistance {nearest_resistance:,.0f}", annotation_position="right",
                          annotation_font_size=9, annotation_font_color="#F23645")

        rc = detail.get("reversal_candle")
        if rc:
            marker_color = "#089981" if direction == "BULLISH" else "#F23645"
            fig.add_annotation(
                text=rc["pattern"].replace("_", " "), x=df["timestamp"].iloc[rc["index"]],
                y=(rc["low"] if direction == "BULLISH" else rc["high"]),
                showarrow=True, arrowhead=2, arrowcolor=marker_color, font=dict(color=marker_color, size=10),
                ax=0, ay=(30 if direction == "BULLISH" else -30),
            )

        fig.update_layout(
            title=f"{timeframe_label} - Direction: {direction}", template="plotly_white", width=width, height=height,
            margin=dict(l=10, r=140, t=36, b=10), xaxis_rangeslider_visible=False,
        )
        chart_bytes = fig.to_image(format="png", engine="kaleido", scale=3)
    except Exception:
        chart_bytes = None

    rsi_val = detail.get("rsi_value")
    divergence = detail.get("divergence", "NONE")
    rc = detail.get("reversal_candle")
    trade_plan = detail.get("trade_plan")

    lines = [f"Structure & Direction: On the {timeframe_label} timeframe, the prevailing direction is {direction}."]
    if detail.get("sr_retest"):
        lines.append("Support/Resistance Retest: Price has retested a key Support/Resistance zone (Rolling Window swing-based).")
    elif detail.get("trendline_retest"):
        lines.append("Trendline Retest: Price is interacting with a Dynamic Trendline.")
    else:
        lines.append("No Support/Resistance or Trendline retest has been confirmed yet on this timeframe.")

    if rsi_val is not None:
        rsi_note = f"RSI(14) is currently {rsi_val:.1f}."
        if divergence != "NONE":
            rsi_note += f" A {divergence.replace('_', ' ').title()} is present."
        lines.append(rsi_note)
    else:
        lines.append("RSI(14) could not be computed (insufficient data).")

    if rc:
        lines.append(f"Reversal Candle: A {rc['pattern'].replace('_', ' ').title()} pattern was found in the recent lookback.")
        if detail.get("breakout_confirmed") and trade_plan:
            lines.append(
                f"Breakout Confirmed: Entry {trade_plan['entry']:,.2f}, Stop-Loss {trade_plan['sl']:,.2f}, "
                f"Target {trade_plan['target']:,.2f} (Risk:Reward 1:{trade_plan['rr']})."
            )
        else:
            lines.append("Breakout: Price has NOT yet broken past the reversal candle's high/low -- entry should wait for this.")
    else:
        lines.append("Reversal Candle: No qualifying Hammer/Engulfing/Star pattern was found in the recent lookback on this timeframe.")

    lines.append(
        "Overall: " + (
            "All Price Action conditions are currently aligned for an entry." if entry_ok
            else "Not all Price Action conditions are aligned yet -- this is analysis, not a live entry signal."
        )
    )
    return chart_bytes, " ".join(lines)


def build_backtest_chart_image(df, bt_result, width=680, height=520):
    """
    Candlestick + Supertrend overlay + RSI-14 subplot + backtest entry markers (हिरवा त्रिकोण = योग्य
    दिशेने हललेला सिग्नल, लाल त्रिकोण = चुकीच्या दिशेने) — Backtest PDF रिपोर्टसाठी.
    """
    if df is None or df.empty:
        return None
    try:
        st_line, _ = calculate_supertrend(df, period=10, multiplier=3)
        rsi_series = calculate_rsi(df, period=14)

        # किंमतीच्या subplot साठी स्पष्ट y-range देणे आवश्यक आहे — नाहीतर Plotly कधीकधी अक्ष शून्यापर्यंत
        # ताणतो, आणि खऱ्या (अरुंद) किंमत-श्रेणीतल्या कँडल्स जवळजवळ अदृश्य/सपाट दिसतात (चाचणीत सापडलेली चूक).
        price_min = min(df["low"].min(), df["close"].min())
        price_max = max(df["high"].max(), df["close"].max())
        price_pad = (price_max - price_min) * 0.08 or price_max * 0.01

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
        fig.add_trace(go.Candlestick(
            x=df["timestamp"], open=df["open"], high=df["high"], low=df["low"], close=df["close"],
            increasing_line_color="#089981", decreasing_line_color="#F23645", showlegend=False,
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=st_line, mode="lines", line=dict(color="#FF6D00", width=1.5), name="Supertrend",
        ), row=1, col=1)

        correct_signals = [s for s in bt_result["signals"] if s["correct"]]
        wrong_signals = [s for s in bt_result["signals"] if not s["correct"]]
        if correct_signals:
            fig.add_trace(go.Scatter(
                x=[s["entry_time"] for s in correct_signals], y=[s["entry_price"] for s in correct_signals],
                mode="markers", marker=dict(symbol="triangle-up", size=12, color="#089981", line=dict(width=1, color="white")),
                name="Correct Signal",
            ), row=1, col=1)
        if wrong_signals:
            fig.add_trace(go.Scatter(
                x=[s["entry_time"] for s in wrong_signals], y=[s["entry_price"] for s in wrong_signals],
                mode="markers", marker=dict(symbol="triangle-down", size=12, color="#F23645", line=dict(width=1, color="white")),
                name="Wrong Signal",
            ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=rsi_series, mode="lines", line=dict(color="#7E57C2", width=1.3), name="RSI-14",
        ), row=2, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color="#F23645", opacity=0.5, row=2, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="#089981", opacity=0.5, row=2, col=1)

        fig.update_yaxes(range=[price_min - price_pad, price_max + price_pad], row=1, col=1)
        fig.update_yaxes(range=[0, 100], row=2, col=1)
        fig.update_layout(
            title="Price + Supertrend + Entry Signals (top) / RSI-14 (bottom)",
            template="plotly_white", width=width, height=height,
            margin=dict(l=10, r=10, t=50, b=10), xaxis_rangeslider_visible=False,
            legend=dict(orientation="h", y=1.08),
        )
        return fig.to_image(format="png", engine="kaleido", scale=3)
    except Exception:
        return None

def build_backtest_chart_image_rr(df, bt_result, width=680, height=520):
    """
    build_backtest_chart_image() ची Risk:Reward आवृत्ती — मार्कर्स outcome नुसार रंगवले जातात:
    हिरवा त्रिकोण (वर) = Target लागला, लाल त्रिकोण (खाली) = SL लागला, राखाडी वर्तुळ = अजून Open.
    """
    if df is None or df.empty:
        return None
    try:
        st_line, _ = calculate_supertrend(df, period=10, multiplier=3)
        rsi_series = calculate_rsi(df, period=14)

        price_min = min(df["low"].min(), df["close"].min())
        price_max = max(df["high"].max(), df["close"].max())
        price_pad = (price_max - price_min) * 0.08 or price_max * 0.01

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
        fig.add_trace(go.Candlestick(
            x=df["timestamp"], open=df["open"], high=df["high"], low=df["low"], close=df["close"],
            increasing_line_color="#089981", decreasing_line_color="#F23645", showlegend=False,
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=st_line, mode="lines", line=dict(color="#FF6D00", width=1.5), name="Supertrend",
        ), row=1, col=1)

        target_signals = [s for s in bt_result["signals"] if s["outcome"] == "TARGET"]
        sl_signals = [s for s in bt_result["signals"] if s["outcome"] == "SL"]
        open_signals = [s for s in bt_result["signals"] if s["outcome"] == "OPEN"]
        if target_signals:
            fig.add_trace(go.Scatter(
                x=[s["entry_time"] for s in target_signals], y=[s["entry_price"] for s in target_signals],
                mode="markers", marker=dict(symbol="triangle-up", size=12, color="#089981", line=dict(width=1, color="white")),
                name="Target Hit",
            ), row=1, col=1)
        if sl_signals:
            fig.add_trace(go.Scatter(
                x=[s["entry_time"] for s in sl_signals], y=[s["entry_price"] for s in sl_signals],
                mode="markers", marker=dict(symbol="triangle-down", size=12, color="#F23645", line=dict(width=1, color="white")),
                name="SL Hit",
            ), row=1, col=1)
        if open_signals:
            fig.add_trace(go.Scatter(
                x=[s["entry_time"] for s in open_signals], y=[s["entry_price"] for s in open_signals],
                mode="markers", marker=dict(symbol="circle", size=9, color="#787B86", line=dict(width=1, color="white")),
                name="Still Open",
            ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=rsi_series, mode="lines", line=dict(color="#7E57C2", width=1.3), name="RSI-14",
        ), row=2, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color="#F23645", opacity=0.5, row=2, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="#089981", opacity=0.5, row=2, col=1)

        fig.update_yaxes(range=[price_min - price_pad, price_max + price_pad], row=1, col=1)
        fig.update_yaxes(range=[0, 100], row=2, col=1)
        fig.update_layout(
            title="Price + Supertrend + Entry Signals (top) / RSI-14 (bottom)",
            template="plotly_white", width=width, height=height,
            margin=dict(l=10, r=10, t=50, b=10), xaxis_rangeslider_visible=False,
            legend=dict(orientation="h", y=1.08),
        )
        return fig.to_image(format="png", engine="kaleido", scale=3)
    except Exception:
        return None

_MISSING_GLYPH_MAP = {
    # DejaVu Sans (used throughout this PDF) doesn't include these newer colour-emoji codepoints —
    # verified by checking its cmap directly rather than assuming. Substituted with symbols that
    # ARE in DejaVu Sans; actual colour comes from the cell/text colouring in _signal_style(), not the glyph.
    "\U0001F7E2": "\u25B2", "\U0001F534": "\u25BC", "\U0001F7E1": "\u25B2", "\U0001F7E0": "\u25BC",
    "\u2705": "\u2713", "\U0001F6AB": "\u2717", "\u274C": "\u2717",
    "\U0001F3AF": "", "\U0001F9EC": "", "\U0001F4CA": "", "\U0001F4C4": "",
}

def _fix_missing_glyphs(s):
    """Swap emoji codepoints that DejaVu Sans can't render for ones it can (checked via cmap, not guessed)."""
    if not isinstance(s, str):
        return s
    for bad, good in _MISSING_GLYPH_MAP.items():
        s = s.replace(bad, good)
    return s

def _table_font_size(ncols):
    if ncols <= 3:
        return 10
    if ncols <= 5:
        return 9
    return 7.5

def df_to_reportlab_table(df, empty_msg="No data available.", max_rows=40, color_columns=None):
    """
    Convert a pandas DataFrame to a reportlab Table (or a Paragraph if empty).
    color_columns: optional list of column names whose cells get a colour tint based on their
    text content (bullish/green, bearish/red, weakening/amber) — this is what makes the OI and
    signal tables visually informative rather than just black-on-white grids.
    """
    if df is None or df.empty:
        return Paragraph(empty_msg, _rpt_normal)
    display_df = df.head(max_rows)
    font_size = _table_font_size(len(display_df.columns))
    columns = list(display_df.columns)
    raw_rows = display_df.astype(str).values.tolist()
    data = [columns] + [[_fix_missing_glyphs(v) for v in row] for row in raw_rows]
    tbl = Table(data, repeatRows=1, hAlign="LEFT")
    style_cmds = [
        ("FONTNAME", (0, 0), (-1, -1), _RPT_TABLE_FONT),
        ("FONTNAME", (0, 0), (-1, 0), _RPT_TABLE_FONT_BOLD),
        ("BACKGROUND", (0, 0), (-1, 0), _C_BG_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f7f9")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if color_columns:
        for col_name in color_columns:
            if col_name not in columns:
                continue
            col_idx = columns.index(col_name)
            for row_idx, row_vals in enumerate(raw_rows, start=1):
                text_color, bg_color = _signal_style(row_vals[col_idx])
                style_cmds.append(("TEXTCOLOR", (col_idx, row_idx), (col_idx, row_idx), text_color))
                style_cmds.append(("BACKGROUND", (col_idx, row_idx), (col_idx, row_idx), bg_color))
                style_cmds.append(("FONTNAME", (col_idx, row_idx), (col_idx, row_idx), _RPT_TABLE_FONT_BOLD))
    tbl.setStyle(TableStyle(style_cmds))
    note = None
    if len(df) > max_rows:
        note = Paragraph(f"(showing first {max_rows} of {len(df)} rows)", _rpt_footer)
    return [tbl, note] if note else tbl

def _force_colors_by_label(rows, label_color_map):
    """
    rows मधील पहिल्या (label) column मध्ये दिलेला मजकूर शोधून त्याचा row-index काढणे, आणि त्यावरून
    _kv_table साठी force_colors dict तयार करणे — manual index मोजण्यापेक्षा (जिथे चूक होऊ शकते) सुरक्षित,
    कारण rows ची रचना बदलली तरी हे आपोआप योग्य row शोधतं.
    """
    label_to_idx = {r[0]: i for i, r in enumerate(rows)}
    force_colors = {}
    for label, color_pair in label_color_map.items():
        idx = label_to_idx.get(label)
        if idx is not None:
            force_colors[idx] = color_pair
    return force_colors

def _kv_table(rows, usable_width, key_ratio=0.35, color_value_rows=None, force_colors=None):
    """Two-column key/value table with a dark key column — colours specific value rows either by
    keyword (color_value_rows, via _signal_style) or explicitly (force_colors={row_idx: (text_color, bg_color)},
    for values like Max Profit/Max Loss whose text doesn't contain BULLISH/BEARISH for keyword matching)."""
    color_value_rows = color_value_rows or set()
    force_colors = force_colors or {}
    clean_rows = [[_fix_missing_glyphs(c) for c in row] for row in rows]
    tbl = Table(clean_rows, hAlign="LEFT", colWidths=[usable_width * key_ratio, usable_width * (1 - key_ratio)])
    style_cmds = [
        ("FONTNAME", (0, 0), (-1, -1), _RPT_TABLE_FONT),
        ("FONTNAME", (0, 0), (0, -1), _RPT_TABLE_FONT_BOLD),
        ("BACKGROUND", (0, 0), (0, -1), _C_BG_DARK), ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 11.5), ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for r in color_value_rows:
        text_color, bg_color = _signal_style(rows[r][1])
        style_cmds.append(("TEXTCOLOR", (1, r), (1, r), text_color))
        style_cmds.append(("BACKGROUND", (1, r), (1, r), bg_color))
        style_cmds.append(("FONTNAME", (1, r), (1, r), _RPT_TABLE_FONT_BOLD))
    for r, (text_color, bg_color) in force_colors.items():
        style_cmds.append(("TEXTCOLOR", (1, r), (1, r), text_color))
        style_cmds.append(("BACKGROUND", (1, r), (1, r), bg_color))
        style_cmds.append(("FONTNAME", (1, r), (1, r), _RPT_TABLE_FONT_BOLD))
        style_cmds.append(("FONTSIZE", (1, r), (1, r), 12.5))
    tbl.setStyle(TableStyle(style_cmds))
    return tbl

def generate_backtest_report_pdf_v2(symbol, strategy_name, interval, from_date, to_date, sl_pct, rr_ratio,
                                      ob_params, bt_df, bt_result):
    """
    नवीन Signal Engine (V2 — Price Action किंवा Indicator Based) च्या backtest निकालांचा PDF रिपोर्ट.
    दिशा दोन्ही रणनीतींसाठी 1H Supertrend वरून — Times-Bold 18pt Headers, Chart, Multi-color, No Wasted Space.
    """
    generated_at = (datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)).strftime("%d-%b-%Y %H:%M:%S IST")
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.4 * cm, rightMargin=1.4 * cm, topMargin=1.2 * cm, bottomMargin=1.2 * cm)
    usable_width = A4[0] - 2.8 * cm
    story = []
    sec = [0]

    def next_section(text):
        story.append(_section_header(text, sec[0], style=_rpt_h2_bt))
        sec[0] += 1
        story.append(Spacer(1, 8))

    title_tbl = Table(
        [[Paragraph("A1 TRADING SYSTEM", _rpt_h1)], [Paragraph(f"{strategy_name} — Signal Check Report", _rpt_h1_sub)]],
        colWidths=[18 * cm],
    )
    title_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _C_BG_DARK),
        ("LEFTPADDING", (0, 0), (-1, -1), 14), ("TOPPADDING", (0, 0), (-1, 0), 14),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 14), ("TOPPADDING", (0, 1), (-1, 1), 0),
    ]))
    story.append(title_tbl)
    story.append(Spacer(1, 10))

    meta_tbl = Table([[
        Paragraph(f"Symbol<br/><b>{symbol}</b>", _rpt_normal),
        Paragraph(f"Date Range<br/><b>{from_date} to {to_date}</b>", _rpt_normal),
        Paragraph(f"Timeframe<br/><b>{interval} (Direction: 1H)</b>", _rpt_normal),
        Paragraph(f"Generated<br/><b>{generated_at}</b>", _rpt_normal),
    ]], colWidths=[usable_width / 4] * 4)
    meta_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _C_GREY_BG), ("GRID", (0, 0), (-1, -1), 0.4, colors.white),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(meta_tbl)
    story.append(Spacer(1, 8))

    next_section("Methodology & Explanation")
    is_price_action = "Price Action" in strategy_name
    if is_price_action:
        story.append(Paragraph(
            "This check runs the new Price Action Signal Engine walk-forward (no lookahead): direction is "
            "determined by 1H Supertrend; an entry requires price to retest a Support/Resistance zone "
            "(Rolling Window swing-based) or a Dynamic Trendline; RSI(14) must be Oversold (&lt;30) or "
            "Overbought (&gt;70), or show a Bullish/Bearish Divergence; a 15-minute reversal candlestick "
            "(Hammer/Bullish Engulfing/Morning Star for bullish, Shooting Star/Bearish Engulfing/Evening Star "
            "for bearish) must close within the recent lookback; and finally price must break past that "
            "candle's high (Bullish) or low (Bearish) to confirm entry.",
            _rpt_normal,
        ))
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            f"Settings used: S/R Rolling Window={ob_params.get('sr_window')}, "
            f"RSI Oversold/Overbought={ob_params.get('rsi_oversold')}/{ob_params.get('rsi_overbought')}, "
            f"SL Buffer={ob_params.get('sl_buffer_pct')}%, Minimum Risk:Reward=1:{ob_params.get('min_rr')} "
            "— Target is the next Support/Resistance level, extended if needed to satisfy the minimum R:R.",
            _rpt_normal,
        ))
    else:
        story.append(Paragraph(
            "This check runs the new Indicator Based Signal Engine walk-forward (no lookahead): direction is "
            "determined by 1H Supertrend; an entry requires RSI(15-minute) to be between 25-55 (Bullish) or "
            "45-75 (Bearish), together with a 15-minute Rejection Bar (Hammer/Shooting Star), Engulfing, or "
            "Morning Star/Evening Star candlestick pattern.",
            _rpt_normal,
        ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"When a directional signal fires, a Stop-Loss ({sl_pct}% from entry) and a Target (Risk:Reward = "
        f"1:{rr_ratio}) are set, and the walk-forward check moves bar-by-bar to see which one gets touched first. "
        "If a single bar's range touches both, this is treated conservatively as an SL hit.",
        _rpt_normal,
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "IMPORTANT LIMITATION: This tests directional signal accuracy and SL/Target behaviour on the INDEX "
        "price only, NOT actual credit-spread P&L. Historical option premiums for expired contracts are not "
        "available via Upstox's API.",
        ParagraphStyle("limitation_v2", fontName=_RPT_FONT_BOLD, fontSize=11.5, leading=15, textColor=_C_RED),
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "OI DATA NOTE: This check uses index price data only — no historical OI-based gates are included.",
        ParagraphStyle("oi_note_v2", fontName=_RPT_FONT_BOLD, fontSize=11.5, leading=15, textColor=_C_AMBER),
    ))
    story.append(Spacer(1, 8))

    next_section("Summary")
    if bt_result["total"] == 0:
        story.append(Paragraph(
            f"No signals were found between {from_date} and {to_date} — this can genuinely happen (the "
            "market may not have presented a matching setup in this window), not necessarily an error.",
            _rpt_normal,
        ))
    else:
        win_rate_display = f"{bt_result['win_rate']}%" if bt_result["win_rate"] is not None else "N/A (no signals decided yet)"
        win_color = _C_GREEN if (bt_result["win_rate"] or 0) >= 50 else _C_RED
        win_bg = _C_GREEN_BG if (bt_result["win_rate"] or 0) >= 50 else _C_RED_BG
        summary_rows = [
            ["Total Signals", str(bt_result["total"])],
            ["Win Rate (Target vs SL)", win_rate_display],
            ["Target Hit / SL Hit / Still Open", f"{bt_result['target_count']} / {bt_result['sl_count']} / {bt_result['open_count']}"],
            ["Bullish / Bearish Signals", f"{bt_result['bullish_count']} / {bt_result['bearish_count']}"],
            ["SL % Used", f"{sl_pct}%"],
            ["Risk:Reward Used", f"1:{rr_ratio}"],
        ]
        force_colors = _force_colors_by_label(summary_rows, {"Win Rate (Target vs SL)": (win_color, win_bg)})
        story.append(_kv_table(summary_rows, usable_width, key_ratio=0.45, force_colors=force_colors))
    story.append(Spacer(1, 8))

    funnel = bt_result.get("funnel", {})
    if funnel:
        next_section("Funnel Diagnostic — Where Exactly Does It Stop?")
        bars_checked = funnel.get("bars_checked", 0)
        structure_directional = funnel.get("structure_directional", 0)
        entry_passed = funnel.get("entry_passed", 0)

        def _pct(part, whole):
            return f"{part/whole*100:.1f}%" if whole else "N/A"

        funnel_rows = [
            ["Bars Checked", str(bars_checked)],
            ["-> 1H Direction Available", f"{structure_directional} ({_pct(structure_directional, bars_checked)})"],
            ["-> Entry Conditions Matched", f"{entry_passed} ({_pct(entry_passed, structure_directional)})"],
        ]
        story.append(_kv_table(funnel_rows, usable_width, key_ratio=0.55))
        story.append(Spacer(1, 8))

    next_section("Chart: Price + Supertrend + Entry Signals + RSI-14")
    chart_bytes = build_backtest_chart_image_rr(bt_df, bt_result)
    if chart_bytes:
        img_w = usable_width
        img_h = img_w * 520 / 680
        story.append(RLImage(io.BytesIO(chart_bytes), width=img_w, height=img_h))
        if bt_result["total"] > 0:
            story.append(Paragraph(
                "Green triangle (up) = Target hit. Red triangle (down) = SL hit. Grey circle = still open. "
                "Orange line = Supertrend(10, 3) on the primary chart timeframe. Bottom panel = RSI-14 with "
                "70/30 overbought/oversold reference lines.",
                _rpt_footer,
            ))
        else:
            story.append(Paragraph(
                "No entry markers are shown since no signals fired in this window.",
                _rpt_footer,
            ))
    else:
        story.append(Paragraph(
            "Chart could not be generated (kaleido package unavailable or image export failed).", _rpt_normal,
        ))
    story.append(Spacer(1, 8))

    if bt_result["total"] > 0:
        next_section("Signal Log")
        sig_df = pd.DataFrame(bt_result["signals"])
        sig_df["entry_time"] = sig_df["entry_time"].astype(str)
        sig_df = sig_df.rename(columns={
            "entry_time": "Entry Time", "direction": "Direction", "entry_price": "Entry Price",
            "sl_price": "SL Price", "target_price": "Target Price", "outcome": "Outcome",
            "exit_price": "Exit Price", "bars_to_exit": "Bars to Exit",
        })
        t = df_to_reportlab_table(sig_df, color_columns=["Direction", "Outcome"])
        story.extend(t if isinstance(t, list) else [t])

    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Generated by the AMW A1 Trading System (app.py). This is a signal-accuracy check for research "
        "purposes, not investment advice.",
        _rpt_footer,
    ))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


def generate_backtest_report_pdf_rr(symbol, trading_style_name, interval, from_date, to_date, sl_pct, rr_ratio, bt_df, bt_result):
    """
    Risk:Reward आधारित Signal Check चा PDF रिपोर्ट — Times-Bold 18pt Headers, Supertrend/RSI/Entry चार्ट
    (Target/SL/Open नुसार रंगवलेले मार्कर्स), स्पष्टीकरण, Multi-color Highlighting, No Wasted Space.
    """
    generated_at = (datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)).strftime("%d-%b-%Y %H:%M:%S IST")
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.4 * cm, rightMargin=1.4 * cm, topMargin=1.2 * cm, bottomMargin=1.2 * cm)
    usable_width = A4[0] - 2.8 * cm
    story = []
    sec = [0]

    def next_section(text):
        story.append(_section_header(text, sec[0], style=_rpt_h2_bt))
        sec[0] += 1
        story.append(Spacer(1, 8))

    title_tbl = Table(
        [[Paragraph("A1 TRADING SYSTEM", _rpt_h1)], [Paragraph(f"{trading_style_name.title()} Signal Check Report", _rpt_h1_sub)]],
        colWidths=[18 * cm],
    )
    title_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _C_BG_DARK),
        ("LEFTPADDING", (0, 0), (-1, -1), 14), ("TOPPADDING", (0, 0), (-1, 0), 14),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 14), ("TOPPADDING", (0, 1), (-1, 1), 0),
    ]))
    story.append(title_tbl)
    story.append(Spacer(1, 10))

    meta_tbl = Table([[
        Paragraph(f"Symbol<br/><b>{symbol}</b>", _rpt_normal),
        Paragraph(f"Date Range<br/><b>{from_date} to {to_date}</b>", _rpt_normal),
        Paragraph(f"Timeframe<br/><b>{interval}</b>", _rpt_normal),
        Paragraph(f"Generated<br/><b>{generated_at}</b>", _rpt_normal),
    ]], colWidths=[usable_width / 4] * 4)
    meta_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _C_GREY_BG), ("GRID", (0, 0), (-1, -1), 0.4, colors.white),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(meta_tbl)
    story.append(Spacer(1, 8))

    # --- Explanation ---
    next_section("Methodology & Explanation")
    story.append(Paragraph(
        "This check runs the Direction Engine's core structural logic (Market Structure -> Break -> "
        "Pullback -> Retest) walk-forward across historical index price data for the selected date range, "
        "using only data available up to each point in time (no lookahead bias). When a directional signal "
        f"fires, a Stop-Loss ({sl_pct}% from entry) and a Target (Risk:Reward = 1:{rr_ratio}, i.e. Target "
        f"distance = SL distance x {rr_ratio}) are set, and the walk-forward check moves bar-by-bar to see "
        "which one gets touched first.",
        _rpt_normal,
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "ASSUMPTION: If a single bar's high-low range touches both the SL and the Target, this is treated "
        "conservatively as an SL hit (OHLC data alone cannot tell which was touched first within that bar).",
        _rpt_normal,
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "IMPORTANT LIMITATION: This tests directional signal accuracy and SL/Target behaviour on the INDEX "
        "price only, NOT actual credit-spread P&L. Historical option premiums for expired contracts are not "
        "available via Upstox's API (only the current/live option chain can be fetched).",
        ParagraphStyle("limitation", fontName=_RPT_FONT_BOLD, fontSize=11.5, leading=15, textColor=_C_RED),
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "OI DATA NOTE: This check uses index price data only. Historical Put-Call OI snapshots are only "
        "available from whenever this app started recording them — there is no historical OI data before "
        "that point, so OI-based gates (OI Confirmation Gate, OI-Price Matrix, PCR, Max Pain, Rollover) "
        "could NOT be included and are not reflected in the results above.",
        ParagraphStyle("oi_note", fontName=_RPT_FONT_BOLD, fontSize=11.5, leading=15, textColor=_C_AMBER),
    ))
    story.append(Spacer(1, 8))

    # --- Summary ---
    next_section("Summary")
    if bt_result["total"] == 0:
        story.append(Paragraph(
            f"No signals were found between {from_date} and {to_date} — this can genuinely happen (the "
            "market may not have presented a clean Break + Pullback + Retest setup in this window), not "
            "necessarily an error. The price chart below is still shown so you can visually check what the "
            "market actually did.",
            _rpt_normal,
        ))
    else:
        win_rate_display = f"{bt_result['win_rate']}%" if bt_result["win_rate"] is not None else "N/A (no signals decided yet)"
        win_color = _C_GREEN if (bt_result["win_rate"] or 0) >= 50 else _C_RED
        win_bg = _C_GREEN_BG if (bt_result["win_rate"] or 0) >= 50 else _C_RED_BG
        summary_rows = [
            ["Total Signals", str(bt_result["total"])],
            ["Win Rate (Target vs SL)", win_rate_display],
            ["Target Hit / SL Hit / Still Open", f"{bt_result['target_count']} / {bt_result['sl_count']} / {bt_result['open_count']}"],
            ["Bullish / Bearish Signals", f"{bt_result['bullish_count']} / {bt_result['bearish_count']}"],
            ["SL % Used", f"{sl_pct}%"],
            ["Risk:Reward Used", f"1:{rr_ratio}"],
        ]
        force_colors = _force_colors_by_label(summary_rows, {"Win Rate (Target vs SL)": (win_color, win_bg)})
        story.append(_kv_table(summary_rows, usable_width, key_ratio=0.45, force_colors=force_colors))
    story.append(Spacer(1, 8))

    # --- Funnel Diagnostic (नेहमी दाखवणे, सिग्नल्स नसले तरी — "एकही सिग्नल का आला नाही" इथे कळतं) ---
    funnel = bt_result.get("funnel", {})
    breakdown = bt_result.get("structure_breakdown", {})
    if funnel:
        next_section("Funnel Diagnostic — Where Exactly Does It Stop?")
        bars_checked = funnel.get("bars_checked", 0)
        structure_directional = funnel.get("structure_directional", 0)
        broke = funnel.get("broke", 0)
        pulled_back = funnel.get("pulled_back_and_retested", 0)
        pattern_rsi_passed = funnel.get("pattern_rsi_passed", 0)

        def _pct(part, whole):
            return f"{part/whole*100:.0f}%" if whole else "N/A"

        funnel_rows = [
            ["Bars Checked", str(bars_checked)],
            ["-> Directional Structure", f"{structure_directional} ({_pct(structure_directional, bars_checked)})"],
            ["-> Broke (of Directional)", f"{broke} ({_pct(broke, structure_directional)})"],
            ["-> Pullback+Retest (of Broke)", f"{pulled_back} ({_pct(pulled_back, broke)})"],
        ]
        if pattern_rsi_passed or "pattern_rsi_passed" in funnel:
            funnel_rows.append(["-> Pattern+RSI Gate (of Pullback+Retest)", f"{pattern_rsi_passed} ({_pct(pattern_rsi_passed, pulled_back)})"])
        story.append(_kv_table(funnel_rows, usable_width, key_ratio=0.55))
        story.append(Spacer(1, 6))

        if breakdown:
            story.append(Paragraph(
                f"Structure breakdown — HH/HL (Bullish): {breakdown.get('HH/HL', 0)} &nbsp;|&nbsp; "
                f"LH/LL (Bearish): {breakdown.get('LH/LL', 0)} &nbsp;|&nbsp; "
                f"Ranging/Mixed: {breakdown.get('RANGING_or_MIXED', 0)} &nbsp;|&nbsp; "
                f"Insufficient Data: {breakdown.get('INSUFFICIENT_DATA', 0)}",
                _rpt_footer,
            ))
        if bars_checked > 0 and structure_directional / bars_checked < 0.15:
            story.append(Spacer(1, 4))
            story.append(Paragraph(
                "NOTE: The market was RANGING/MIXED most of the time (Directional Structure rarely matched). "
                "Consider lowering structure_order or lookback_swings for more opportunities.",
                ParagraphStyle("funnel_note", fontName=_RPT_FONT_BOLD, fontSize=11, leading=14, textColor=_C_AMBER),
            ))
        story.append(Spacer(1, 8))

    # --- Chart (always shown, even with 0 signals) ---
    next_section("Chart: Price + Supertrend + Entry Signals + RSI-14")
    chart_bytes = build_backtest_chart_image_rr(bt_df, bt_result)
    if chart_bytes:
        img_w = usable_width
        img_h = img_w * 520 / 680
        story.append(RLImage(io.BytesIO(chart_bytes), width=img_w, height=img_h))
        if bt_result["total"] > 0:
            story.append(Paragraph(
                "Green triangle (up) = Target hit. Red triangle (down) = SL hit. Grey circle = still open "
                "(neither hit within the hold window). Orange line = Supertrend(10, 3). Bottom panel = "
                "RSI-14 with 70/30 overbought/oversold reference lines.",
                _rpt_footer,
            ))
        else:
            story.append(Paragraph(
                "No entry markers are shown since no signals fired in this window. Orange line = "
                "Supertrend(10, 3). Bottom panel = RSI-14 with 70/30 overbought/oversold reference lines.",
                _rpt_footer,
            ))
    else:
        story.append(Paragraph(
            "Chart could not be generated (kaleido package unavailable or image export failed). "
            "Add 'kaleido==0.2.1' to requirements.txt.", _rpt_normal,
        ))
    story.append(Spacer(1, 8))

    # --- Signal log (only when there are signals to show) ---
    if bt_result["total"] > 0:
        next_section("Signal Log")
        sig_df = pd.DataFrame(bt_result["signals"])
        sig_df["entry_time"] = sig_df["entry_time"].astype(str)
        sig_df = sig_df.rename(columns={
            "entry_time": "Entry Time", "direction": "Direction", "entry_price": "Entry Price",
            "sl_price": "SL Price", "target_price": "Target Price", "outcome": "Outcome",
            "exit_price": "Exit Price", "bars_to_exit": "Bars to Exit",
        })
        t = df_to_reportlab_table(sig_df, color_columns=["Direction", "Outcome"])
        story.extend(t if isinstance(t, list) else [t])

    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Generated by the AMW A1 Trading System (app.py). This is a signal-accuracy check for research "
        "purposes, not investment advice.",
        _rpt_footer,
    ))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()

def generate_backtest_report_pdf(symbol, bt_timeframe, bt_forward_bars, bt_min_move, bt_df, bt_result):
    """
    Signal Backtest चा PDF रिपोर्ट — Times-Bold 18pt Headers, Supertrend/RSI/Entry चार्ट, स्पष्टीकरण,
    Multi-color Highlighting, आणि जबरदस्तीने पेज-ब्रेक्स नाहीत (No Wasted Space).
    """
    generated_at = (datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)).strftime("%d-%b-%Y %H:%M:%S IST")
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.4 * cm, rightMargin=1.4 * cm, topMargin=1.2 * cm, bottomMargin=1.2 * cm)
    usable_width = A4[0] - 2.8 * cm
    story = []
    sec = [0]

    def next_section(text):
        story.append(_section_header(text, sec[0], style=_rpt_h2_bt))
        sec[0] += 1
        story.append(Spacer(1, 8))

    title_tbl = Table(
        [[Paragraph("A1 TRADING SYSTEM", _rpt_h1)], [Paragraph("Signal Backtest Report", _rpt_h1_sub)]],
        colWidths=[18 * cm],
    )
    title_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _C_BG_DARK),
        ("LEFTPADDING", (0, 0), (-1, -1), 14), ("TOPPADDING", (0, 0), (-1, 0), 14),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 14), ("TOPPADDING", (0, 1), (-1, 1), 0),
    ]))
    story.append(title_tbl)
    story.append(Spacer(1, 10))

    meta_tbl = Table([[
        Paragraph(f"Symbol<br/><b>{symbol}</b>", _rpt_normal),
        Paragraph(f"Timeframe<br/><b>{bt_timeframe}</b>", _rpt_normal),
        Paragraph(f"Forward Bars<br/><b>{bt_forward_bars}</b>", _rpt_normal),
        Paragraph(f"Generated<br/><b>{generated_at}</b>", _rpt_normal),
    ]], colWidths=[usable_width / 4] * 4)
    meta_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _C_GREY_BG), ("GRID", (0, 0), (-1, -1), 0.4, colors.white),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(meta_tbl)
    story.append(Spacer(1, 8))

    # --- Explanation ---
    next_section("Methodology & Explanation")
    story.append(Paragraph(
        "This backtest runs the Direction Engine's core structural logic (Market Structure -> Break -> "
        "Pullback -> Retest) walk-forward across historical index price data, using only data available "
        "up to each point in time (no lookahead bias — verified: each signal's entry price exactly matches "
        f"the actual close at that historical bar). When a directional signal fires, the index price "
        f"{bt_forward_bars} bar(s) later is checked against a minimum move threshold of {bt_min_move}% to "
        "determine whether the direction was correct.",
        _rpt_normal,
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "IMPORTANT LIMITATION: This tests directional signal accuracy only, NOT actual credit-spread P&L. "
        "Historical option premiums for expired contracts are not available via Upstox's API (only the "
        "current/live option chain can be fetched) — so an accurate historical P&L backtest of the actual "
        "options strategies is not possible with this data source.",
        ParagraphStyle("limitation", fontName=_RPT_FONT_BOLD, fontSize=11.5, leading=15, textColor=_C_RED),
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "OI DATA NOTE: This backtest uses index price data only. Historical Put-Call OI snapshots are only "
        "available from whenever this app started recording them (visible in the OI Diff Tracker) — there is "
        "no historical OI data available before that point, so OI-based gates (OI Confirmation Gate, "
        "OI-Price Matrix, PCR, Max Pain, Rollover) could NOT be included in this backtest and are not "
        "reflected in the results above.",
        ParagraphStyle("oi_note", fontName=_RPT_FONT_BOLD, fontSize=11.5, leading=15, textColor=_C_AMBER),
    ))
    story.append(Spacer(1, 8))

    # --- Summary ---
    next_section("Summary")
    if bt_result["total"] == 0:
        story.append(Paragraph(
            "No signals were found for these settings — this can genuinely happen (the market may not have "
            "presented a clean Break + Pullback + Retest setup in this window), not necessarily an error. "
            "The price chart below is still shown so you can visually check what the market actually did.",
            _rpt_normal,
        ))
    else:
        win_color = _C_GREEN if bt_result["win_rate"] >= 50 else _C_RED
        win_bg = _C_GREEN_BG if bt_result["win_rate"] >= 50 else _C_RED_BG
        summary_rows = [
            ["Total Signals", str(bt_result["total"])],
            ["Win Rate (Direction Correct)", f"{bt_result['win_rate']}%"],
            ["Bullish / Bearish Signals", f"{bt_result['bullish_count']} / {bt_result['bearish_count']}"],
            ["Avg Move %", f"{bt_result['avg_move_pct']}%"],
            ["Avg Win Move %", f"{bt_result['avg_win_move_pct']}%" if bt_result["avg_win_move_pct"] is not None else "N/A"],
            ["Avg Loss Move %", f"{bt_result['avg_loss_move_pct']}%" if bt_result["avg_loss_move_pct"] is not None else "N/A"],
        ]
        force_colors = _force_colors_by_label(summary_rows, {"Win Rate (Direction Correct)": (win_color, win_bg)})
        story.append(_kv_table(summary_rows, usable_width, key_ratio=0.45, force_colors=force_colors))
    story.append(Spacer(1, 8))

    # --- Chart (always shown, even with 0 signals, so you can see why nothing fired) ---
    next_section("Chart: Price + Supertrend + Entry Signals + RSI-14")
    chart_bytes = build_backtest_chart_image(bt_df, bt_result)
    if chart_bytes:
        img_w = usable_width
        img_h = img_w * 520 / 680
        story.append(RLImage(io.BytesIO(chart_bytes), width=img_w, height=img_h))
        if bt_result["total"] > 0:
            story.append(Paragraph(
                "Green triangle (up) = signal where price moved in the predicted direction. Red triangle "
                "(down) = signal where it did not. Orange line = Supertrend(10, 3). Bottom panel = RSI-14 "
                "with 70/30 overbought/oversold reference lines.",
                _rpt_footer,
            ))
        else:
            story.append(Paragraph(
                "No entry markers are shown since no signals fired in this window. Orange line = "
                "Supertrend(10, 3). Bottom panel = RSI-14 with 70/30 overbought/oversold reference lines.",
                _rpt_footer,
            ))
    else:
        story.append(Paragraph(
            "Chart could not be generated (kaleido package unavailable or image export failed). "
            "Add 'kaleido==0.2.1' to requirements.txt.", _rpt_normal,
        ))
    story.append(Spacer(1, 8))

    # --- Signal log (only when there are signals to show) ---
    if bt_result["total"] > 0:
        next_section("Signal Log")
        sig_df = pd.DataFrame(bt_result["signals"])
        sig_df["entry_time"] = sig_df["entry_time"].astype(str)
        sig_df["correct"] = sig_df["correct"].map({True: "Correct", False: "Wrong"})
        sig_df = sig_df.rename(columns={
            "entry_time": "Entry Time", "direction": "Direction", "entry_price": "Entry Price",
            "exit_price": "Exit Price", "move_pct": "Move %", "correct": "Result",
        })
        t = df_to_reportlab_table(sig_df, color_columns=["Direction", "Result"])
        story.extend(t if isinstance(t, list) else [t])

    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Generated by the AMW A1 Trading System (app.py). This is a signal-accuracy backtest for research "
        "purposes, not investment advice.",
        _rpt_footer,
    ))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()

def generate_market_analysis_report_pdf(
    symbol, underlying_price, atm_strike,
    df_day, df_1h, df_style_tf, style_tf_label,
    structure_day, structure_1h, structure_style_tf,
    direction_final, sideways_info, last_st_dir_label, last_st_val, last_rsi,
    broke, broken_level, pulled_back, retested, rsi_check, confirmed_5m, zone,
    india_vix, vix_ok, vix_max_threshold,
    strategy_result, lots, lot_size, risk_amount, available_margin, risk_pct_per_trade, pop_threshold_pct,
    final_signal_text,
    chain_df, oi_hist_df, open_trades_df, closed_trades_df,
    news_data=None,
):
    """Full Market Analysis Report (OI data + multi-timeframe structure + BOS/CHoCH charts + news), in English, PDF bytes."""
    generated_at = (datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)).strftime("%d-%b-%Y %H:%M:%S IST")
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.4 * cm, rightMargin=1.4 * cm, topMargin=1.2 * cm, bottomMargin=1.2 * cm)
    usable_width = A4[0] - 2.8 * cm
    story = []
    sec = [0]  # rolling section-colour index

    def next_section(text):
        story.append(_section_header(text, sec[0]))
        sec[0] += 1
        story.append(Spacer(1, 8))

    # --- Title banner ---
    title_tbl = Table(
        [[Paragraph("A1 TRADING SYSTEM", _rpt_h1)], [Paragraph("Market Analysis Report", _rpt_h1_sub)]],
        colWidths=[18 * cm],
    )
    title_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _C_BG_DARK),
        ("LEFTPADDING", (0, 0), (-1, -1), 14), ("TOPPADDING", (0, 0), (-1, 0), 14),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 14), ("TOPPADDING", (0, 1), (-1, 1), 0),
    ]))
    story.append(title_tbl)
    story.append(Spacer(1, 10))

    meta_tbl = Table([[
        Paragraph(f"Symbol<br/><b>{symbol}</b>", _rpt_normal),
        Paragraph(f"Spot Price<br/><b>Rs {underlying_price:,.2f}</b>", _rpt_normal),
        Paragraph(f"ATM Strike<br/><b>{atm_strike:.0f}</b>", _rpt_normal),
        Paragraph(f"Generated<br/><b>{generated_at}</b>", _rpt_normal),
    ]], colWidths=[usable_width / 4] * 4)
    meta_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _C_GREY_BG), ("GRID", (0, 0), (-1, -1), 0.4, colors.white),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(meta_tbl)
    story.append(Spacer(1, 10))
    if _RPT_FONT_MISSING_WARNING:
        story.append(Paragraph(_RPT_FONT_MISSING_WARNING, ParagraphStyle("warn", fontName="Helvetica-Bold", fontSize=9, textColor=_C_RED)))
        story.append(Spacer(1, 6))

    # --- 0. News ---
    next_section("Market News (National & International)")
    if news_data:
        for src in news_data:
            story.append(Paragraph(_fix_missing_glyphs(src["source"]), _rpt_h3))
            for h in src["headlines"]:
                story.append(Paragraph(f"\u2022 {_fix_missing_glyphs(h['title'])}", _rpt_normal))
            story.append(Spacer(1, 4))
    else:
        story.append(Paragraph("News unavailable (feed unreachable or network error).", _rpt_normal))
    story.append(Spacer(1, 8))

    # --- 1. Multi-timeframe structure ---
    next_section(f"Multi-Timeframe Market Structure (Day / 1H / {style_tf_label})")
    structure_rows = [["Timeframe", "Structure", "Last Swing High", "Last Swing Low"]]
    tf_panels = [("1 Day", structure_day), ("1 Hour", structure_1h)]
    if style_tf_label not in ("Daily", "1 Hour"):
        tf_panels.append((style_tf_label, structure_style_tf))
    for label, s in tf_panels:
        structure_rows.append([label, s["structure"], str(s.get("last_swing_high") or "-"), str(s.get("last_swing_low") or "-")])
    st_tbl = df_to_reportlab_table(pd.DataFrame(structure_rows[1:], columns=structure_rows[0]), color_columns=["Structure"])
    story.extend(st_tbl if isinstance(st_tbl, list) else [st_tbl])
    story.append(Spacer(1, 8))

    # --- 2. Charts ---
    use_price_action_v2 = direction_final in ("BULLISH", "BEARISH")
    section_title = (
        "Charts: Support/Resistance, RSI & Candlestick Reversal (per timeframe)" if use_price_action_v2
        else "Charts: BOS/CHoCH, Support/Resistance, Trendlines & Demand-Supply Zones (per timeframe)"
    )
    next_section(section_title)
    any_chart = False
    chart_panels = [(df_day, "Daily"), (df_1h, "1 Hour")]
    if style_tf_label not in ("Daily", "1 Hour"):
        chart_panels.append((df_style_tf, style_tf_label))
    for df_c, label in chart_panels:
        if use_price_action_v2:
            rsi_for_chart = calculate_rsi(df_c, period=14) if df_c is not None and not df_c.empty else None
            img_bytes, price_action_desc = build_price_action_chart_v2(df_c, direction_final, label, rsi_series=rsi_for_chart)
        else:
            zone_info = analyze_chart_zones(df_c) if df_c is not None and not df_c.empty else None
            img_bytes, price_action_desc = build_report_chart_image(df_c, f"{symbol} - {label}", zone_info=zone_info)
        if img_bytes:
            img_w = usable_width
            img_h = img_w * 420 / 620
            story.append(RLImage(io.BytesIO(img_bytes), width=img_w, height=img_h))
            story.append(Paragraph(f"<i>{price_action_desc}</i>", ParagraphStyle("pa_desc", fontName=_RPT_FONT, fontSize=9, textColor=colors.HexColor("#555555"))))
            story.append(Spacer(1, 10))
            any_chart = True
    if not any_chart:
        story.append(Paragraph(
            "Charts could not be generated (kaleido package unavailable or image export failed). "
            "Add 'kaleido==0.2.1' to requirements.txt.", _rpt_normal,
        ))

    # --- 3. Direction Engine / Technical ---
    next_section("Direction Engine & Technical Analysis")
    rsi_str = f"{rsi_check['rsi']:.1f}" if rsi_check.get("rsi") is not None else "-"
    check = "\u2713"
    cross = "\u2717"
    rsi_zone_label = "Overbought" if (rsi_check.get("rsi") or 0) >= 70 else ("Oversold" if (rsi_check.get("rsi") or 100) <= 30 else "Neutral zone")
    tech_rows = [
        ["Direction Engine Output", direction_final or "NEUTRAL / insufficient data"],
        [f"Supertrend ({style_tf_label})", f"{last_st_dir_label} (Level: {last_st_val:,.2f})"],
        ["RSI-14", f"{last_rsi:.1f} ({rsi_zone_label})"],
        ["Break Detection", (f"{check} Broken" if broke else f"{cross} Not broken") + (f" (level: {broken_level:,.2f})" if broken_level else "")],
        ["Pullback / Retest", f"{check if pulled_back else cross} / {check if retested else cross}"],
        ["RSI Momentum", (f"{check} Aligned" if rsi_check['momentum_ok'] else f"{cross} Not aligned") + f" (RSI: {rsi_str})"],
        ["RSI Divergence", rsi_check["divergence"]],
        ["5M Confirmation", check if confirmed_5m else cross],
        ["Supply/Demand Zone", str(zone) if zone else "-"],
    ]
    if sideways_info is not None:
        tech_rows.append(["Sideways Range %", str(sideways_info.get("range_pct"))])
        tech_rows.append(["Sideways Qualified", (f"{check} " + sideways_info["strategy_type"]) if sideways_info["is_sideways"] else cross])

    tech_force_colors = _force_colors_by_label(tech_rows, {
        "RSI-14": (_C_AMBER, _C_AMBER_BG) if rsi_zone_label != "Neutral zone" else (_C_GREY, _C_GREY_BG),
    })
    story.append(_kv_table(tech_rows, usable_width, color_value_rows={0}, force_colors=tech_force_colors))
    story.append(Spacer(1, 8))

    # --- 4 & 5. OI data ---
    next_section("Option Chain OI Data (ATM +/- 6 strikes)")
    t = df_to_reportlab_table(chain_df, color_columns=["Dominance"])
    story.extend(t if isinstance(t, list) else [t])
    story.append(Spacer(1, 10))

    next_section("Put-Call OI Diff Tracker (today, every 10 minutes)")
    t = df_to_reportlab_table(oi_hist_df, color_columns=["Signal"])
    story.extend(t if isinstance(t, list) else [t])

    # --- 6. VIX & Strategy Selection ---
    next_section("India VIX Filter & Strategy Selection")
    vix_str = f"{india_vix:.2f}" if india_vix is not None else "unavailable"
    vix_status = "OK for trading" if vix_ok else "NO TRADE"
    vix_color = _C_GREEN if vix_ok else _C_RED
    vix_color_hex = "#089981" if vix_ok else "#F23645"
    story.append(Paragraph(
        f"India VIX: <b>{vix_str}</b> (max threshold: {vix_max_threshold}) &mdash; "
        f"<font color='{vix_color_hex}'><b>{vix_status}</b></font>", _rpt_value_big,
    ))
    story.append(Spacer(1, 8))

    if strategy_result:
        legs = normalize_legs(strategy_result)
        pop_display = strategy_result.get("short_pop_pct", strategy_result.get("combined_pop_pct"))
        strat_rows = [["Strategy", strategy_result["strategy"].replace("_", " ")]]
        for leg in legs:
            strat_rows.append([leg["role"].replace("_", " ").title(), f"{leg['strike']:.0f} ({leg['transaction_type']})"])
        strat_rows += [
            ["PoP (approx)", f"{pop_display}%"],
            ["Net Credit / unit", f"Rs {strategy_result['net_credit']:.2f}"],
            ["Max Profit / lot", f"Rs {strategy_result['max_profit'] * lot_size:,.0f}" if lot_size else f"Rs {strategy_result['max_profit']:.2f}"],
            ["Max Loss / lot", f"Rs {strategy_result['max_loss'] * lot_size:,.0f}" if lot_size else f"Rs {strategy_result['max_loss']:.2f}"],
            ["PoP Threshold used", f"{pop_threshold_pct}%"],
            ["Available Margin", f"Rs {available_margin:,.0f}" if available_margin is not None else "unavailable"],
            ["Risk % / Amount", f"{risk_pct_per_trade}% (Rs {risk_amount:,.0f})"],
            ["Position Size", f"{lots} lot(s)"],
        ]
        force_colors = _force_colors_by_label(strat_rows, {
            "PoP (approx)": (_C_GREEN, _C_GREEN_BG),
            "Max Profit / lot": (_C_GREEN, _C_GREEN_BG),
            "Max Loss / lot": (_C_RED, _C_RED_BG),
            "Position Size": (_C_ACCENT, _C_ACCENT_BG),
        })
        story.append(_kv_table(strat_rows, usable_width, key_ratio=0.4, force_colors=force_colors))
    else:
        story.append(Paragraph(
            "No strategy was selected at this time (gates incomplete, sideways conditions not met, or PoP threshold not met).",
            _rpt_normal,
        ))

    # --- 7. Final Signal ---
    story.append(Spacer(1, 10))
    next_section("Final A1 Signal")
    sig_color, sig_bg = _signal_style(final_signal_text)
    sig_tbl = Table([[Paragraph(_fix_missing_glyphs(final_signal_text),
                       ParagraphStyle("finalsig", fontName=_RPT_FONT_BOLD, fontSize=18, leading=22, textColor=sig_color))]],
                     colWidths=[usable_width])
    sig_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), sig_bg), ("BOX", (0, 0), (-1, -1), 1, sig_color),
        ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
    ]))
    story.append(sig_tbl)

    # --- 8. Live Trades ---
    next_section("Live Trades Log")
    story.append(Paragraph("Currently Open Trades", _rpt_h3))
    t = df_to_reportlab_table(open_trades_df, "No open trades right now.")
    story.extend(t if isinstance(t, list) else [t])
    story.append(Spacer(1, 8))
    story.append(Paragraph("Trades Closed Today", _rpt_h3))
    t = df_to_reportlab_table(closed_trades_df, "No trades closed yet today.")
    story.extend(t if isinstance(t, list) else [t])

    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "This report was generated automatically by the AMW A1 Trading System (app.py) for personal "
        "record-keeping and as an audit trail for trading decisions. This is not investment advice.",
        _rpt_footer,
    ))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()
