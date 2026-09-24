"""PDF report generation: Market Analysis Report and Signal Backtest Report — fonts, colors, charts, tables."""
import datetime
import io
import os
import re
from xml.sax.saxutils import escape as _xml_escape
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
from reportlab.pdfgen.canvas import Canvas as _BaseCanvas

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

# 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — EOD Market Report मध्ये मराठी मजकूर आहे, जो
# Times-Roman/Helvetica/DejaVuSans यापैकी कशातही दिसत नाही (काळे चौकोन दिसतात, glyphs नाहीत) —
# Noto Sans Devanagari या समर्पित font ने दुरुस्त केलं (फक्त Regular weight उपलब्ध आहे).
_DEVANAGARI_FONT = "Helvetica"  # सुरक्षित fallback, font सापडला नाही तर
try:
    _deva_path = os.path.join(_font_dir, "NotoSansDevanagari-Regular.ttf")
    if os.path.exists(_deva_path):
        pdfmetrics.registerFont(TTFont("NotoSansDevanagari", _deva_path))
        _DEVANAGARI_FONT = "NotoSansDevanagari"
except Exception:
    pass

# EOD Market Report साठी मराठी-सुसंगत styles (इतर, इंग्रजी reports च्या styles ना धक्का न लावता, वेगळे)
_deva_h1 = ParagraphStyle("deva_h1", fontName="Helvetica-Bold", fontSize=22, leading=26, textColor=colors.white)
_deva_h1_sub = ParagraphStyle("deva_h1_sub", fontName=_DEVANAGARI_FONT, fontSize=12, leading=16, textColor=colors.HexColor("#B8BEC9"))
_deva_h2 = ParagraphStyle("deva_h2", fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=colors.white)
_deva_h3 = ParagraphStyle("deva_h3", fontName=_DEVANAGARI_FONT, fontSize=12, leading=16, textColor=colors.HexColor("#333333"), spaceBefore=6, spaceAfter=3)
_deva_normal = ParagraphStyle("deva_normal", fontName=_DEVANAGARI_FONT, fontSize=11, leading=15, alignment=TA_LEFT)
_deva_footer = ParagraphStyle("deva_footer", fontName=_DEVANAGARI_FONT, fontSize=8, leading=11, textColor=colors.HexColor("#888888"))

# 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — EOD Market Report आता इंग्रजीत, आणि संपूर्ण मुख्य
# मजकूर Times New Roman, Bold, Italic, 18pt (वापरकर्त्याने स्पष्टपणे "सर्वत्र" म्हणून सांगितलं).
# reportlab चा बिल्ट-इन "Times-BoldItalic" वापरला — वेगळी font-file नोंदणी लागत नाही.
_EOD_FONT = "Times-BoldItalic"
_EOD_FONT_SIZE = 18
_eod_h1 = ParagraphStyle("eod_h1", fontName=_EOD_FONT, fontSize=_EOD_FONT_SIZE, leading=22, textColor=colors.white)
_eod_h1_sub = ParagraphStyle("eod_h1_sub", fontName=_EOD_FONT, fontSize=_EOD_FONT_SIZE, leading=22, textColor=colors.HexColor("#B8BEC9"))
_eod_h2 = ParagraphStyle("eod_h2", fontName=_EOD_FONT, fontSize=_EOD_FONT_SIZE, leading=22, textColor=colors.white)
_eod_h3 = ParagraphStyle("eod_h3", fontName=_EOD_FONT, fontSize=_EOD_FONT_SIZE, leading=22, textColor=colors.HexColor("#333333"), spaceBefore=6, spaceAfter=3)
_eod_normal = ParagraphStyle("eod_normal", fontName=_EOD_FONT, fontSize=_EOD_FONT_SIZE, leading=22, alignment=TA_LEFT)
_eod_footer = ParagraphStyle("eod_footer", fontName=_EOD_FONT, fontSize=_EOD_FONT_SIZE, leading=22, textColor=colors.HexColor("#888888"))


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

_rpt_kv_wrap = ParagraphStyle("rpt_kv_wrap", fontName=_RPT_FONT, fontSize=9.5, leading=12.5, textColor=colors.HexColor("#333333"))

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
    if "WEAKENING" in t:
        return _C_AMBER, _C_AMBER_BG  # 🎓 आधी BULLISH/BEARISH पेक्षा प्राधान्याने तपासणे — नाहीतर
        # "BULLISH (Weakening)" चुकून पूर्ण हिरवाच दिसायचं, कमजोर होत असल्याचा इशारा हरवायचा
    if "BEARISH" in t or "BEARS" in t or t == "WRONG" or t == "SL":
        return _C_RED, _C_RED_BG
    if "PAPER" in t:
        return _C_ACCENT, _C_ACCENT_BG
    if "BULLISH" in t or "BULLS" in t or "LIVE" in t or t.startswith("[OK]") or t == "OK" or t == "CORRECT" or t == "TARGET":
        return _C_GREEN, _C_GREEN_BG
    if "NO TRADE" in t or "[!]" in t or t == "OPEN":
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
        # 🎓 वापरकर्त्याने EOD Report मध्ये दाखवलेला खरा bug इथेही तितकाच लागू होतो — trendlines
        # (add_price_action_overlays मधल्या) अनेक दिवसांना जोडत असल्याने, शनि-रवि/बाजार-बंद वेळ
        # x-अक्षातून वगळला नाही तर त्या रेषा त्या रिकाम्या पट्ट्यावर सरळ (तिरकी) ओढल्या जाऊ शकतात.
        fig.update_xaxes(rangebreaks=[
            dict(bounds=["sat", "mon"]),
            dict(bounds=[15.5, 9.25], pattern="hour"),
        ])
        # 🎓 वापरकर्त्याने मागितलेली सुधारणा (PDF Report Optimize) — kaleido export scale आधी सर्वत्र
        # 3x होता (प्रत्येक chart साठी 9x जास्त pixels — छपाईसाठी अनावश्यक जास्त उच्च-रिझोल्यूशन).
        # आता 2x (standard "retina" दर्जा — print/screen दोन्हीसाठी पुरेसा तीक्ष्ण) — हाच बदल या
        # फाईलमधल्या सर्व chart-builder फंक्शन्समध्ये (कमी pixels = kaleido rendering वेळ लक्षणीय कमी).
        return fig.to_image(format="png", scale=2), description
    except Exception:
        return None, "Chart could not be generated."


def build_eod_report_chart_image(df, sr_levels=None, supertrend_line=None, symbol="NIFTY",
                                    timeframe_label="15M", max_bars=60, width=680, height=380):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — EOD Market Report मध्ये फक्त मजकूर/तक्ते होते, प्रत्यक्ष
    chart नव्हता (वापरकर्त्याने निदर्शनास आणलं). इथे established plotly+kaleido पद्धतीनेच (जुन्या
    build_report_chart_image प्रमाणे) — candlestick + S/R रेषा + Supertrend रेषा असलेला chart image
    तयार करणे. फक्त शेवटचे max_bars bars दाखवले जातात (जास्त bars candle बॉडी दिसेनाशी करतात).
    Returns: image_bytes किंवा None (डेटा नसेल/kaleido अपयशी झालं तर, गोंधळ न होता).
    """
    if df is None or df.empty:
        return None
    try:
        df_recent = df.tail(max_bars).reset_index(drop=True)
        fig = go.Figure(data=[go.Candlestick(
            x=df_recent["timestamp"], open=df_recent["open"], high=df_recent["high"],
            low=df_recent["low"], close=df_recent["close"],
            increasing_line_color="#089981", decreasing_line_color="#F23645", showlegend=False,
        )])

        if supertrend_line is not None and not supertrend_line.empty:
            st_recent = supertrend_line.tail(max_bars).reset_index(drop=True)
            fig.add_trace(go.Scatter(
                x=df_recent["timestamp"], y=st_recent, mode="lines",
                line=dict(color="#00bcd4", width=2), showlegend=False,
            ))

        if sr_levels:
            for r in sr_levels.get("resistance", [])[:2]:
                fig.add_hline(y=r["level"], line_dash="dash", line_color="#F23645", line_width=1.4,
                              annotation_text=f"R {r['level']:,.0f}", annotation_position="right",
                              annotation_font_size=9, annotation_font_color="#F23645")
            for s in sr_levels.get("support", [])[:2]:
                fig.add_hline(y=s["level"], line_dash="dash", line_color="#089981", line_width=1.4,
                              annotation_text=f"S {s['level']:,.0f}", annotation_position="right",
                              annotation_font_size=9, annotation_font_color="#089981")

        fig.update_layout(
            title=f"{symbol} — {timeframe_label} Chart", template="plotly_white", width=width, height=height,
            margin=dict(l=10, r=90, t=36, b=10), xaxis_rangeslider_visible=False,
        )
        # 🎓 वापरकर्त्याने प्रत्यक्ष PDF मध्ये दाखवलेला खरा bug — शनि-रवि आणि रोजचा बाजार-बंद वेळ
        # (15:30 ते 9:15) x-अक्षातून वगळलेला नव्हता, त्यामुळे Supertrend रेषा त्या मोठ्या रिकाम्या
        # पट्ट्यावर सरळ (तिरकी) ओढली जायची — candles स्वतः बरोबर दिसत असल्या तरी. rangebreaks ने
        # ही रिकामी जागा x-अक्षातूनच काढून टाकली — आता सलग trading bars एकमेकांना खेटूनच दिसतात.
        fig.update_xaxes(rangebreaks=[
            dict(bounds=["sat", "mon"]),               # शनि-रवि वगळणे
            dict(bounds=[15.5, 9.25], pattern="hour"),  # रोजचा बाजार-बंद वेळ (15:30-9:15) वगळणे
        ])
        return fig.to_image(format="png", scale=2)
    except Exception:
        return None


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
        # 🎓 वापरकर्त्याने EOD Report मध्ये दाखवलेला खरा bug इथेही तितकाच लागू होतो (Full Market
        # Analysis Report च्याच 1D/1H/15M Direction charts मध्ये) — S/R रेषा/trendlines अनेक
        # trading-days ना जोडत असल्याने, शनि-रवि/बाजार-बंद वेळ वगळला नाही तर तिरकी रेषा तयार होते.
        fig.update_xaxes(rangebreaks=[
            dict(bounds=["sat", "mon"]),
            dict(bounds=[15.5, 9.25], pattern="hour"),
        ])
        chart_bytes = fig.to_image(format="png", scale=2)
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
        # 🎓 वापरकर्त्याने EOD Report मध्ये दाखवलेला खरा bug इथेही तितकाच लागू होतो -- backtest
        # कालावधी अनेक trading-days पसरलेला असल्याने, शनि-रवि/बाजार-बंद वेळ वगळला नाही तर रेषा त्या
        # रिकाम्या पट्ट्यांवर तिरकी ओढली जाऊ शकते.
        fig.update_xaxes(rangebreaks=[
            dict(bounds=["sat", "mon"]),
            dict(bounds=[15.5, 9.25], pattern="hour"),
        ])
        return fig.to_image(format="png", scale=2)
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
        # 🎓 वापरकर्त्याने EOD Report मध्ये दाखवलेला खरा bug इथेही तितकाच लागू होतो -- backtest
        # कालावधी अनेक trading-days पसरलेला असल्याने, शनि-रवि/बाजार-बंद वेळ वगळला नाही तर रेषा त्या
        # रिकाम्या पट्ट्यांवर तिरकी ओढली जाऊ शकते.
        fig.update_xaxes(rangebreaks=[
            dict(bounds=["sat", "mon"]),
            dict(bounds=[15.5, 9.25], pattern="hour"),
        ])
        return fig.to_image(format="png", scale=2)
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
    """Swap emoji codepoints that DejaVu Sans can't render for ones it can (checked via cmap, not guessed).
    🎓 वापरकर्त्याने सापडवलेली bug (PDF generation क्रॅश — AttributeError: 'float' object has no
    attribute 'replace') — df.astype(str) पांडासमध्ये NaN ला स्ट्रिंग बनवत नाही (float('nan') तसाच
    राहतो), फक्त इतर सेल्स स्ट्रिंग होतात — काही cells NaN/None असलेल्या (उदा. Fixed-Rs strategy
    trades साठी Overshoot % रिकामं) DataFrame मधून हे function raw float घेऊन पुढे xml escape ला
    द्यायचं, जे crash व्हायचं. आता str() कोणत्याही non-string इनपुटला आधीच बदलतो."""
    if not isinstance(s, str):
        return str(s)
    for bad, good in _MISSING_GLYPH_MAP.items():
        s = s.replace(bad, good)
    return s


def _fix_devanagari_glyphs(s):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — NotoSansDevanagari मध्ये → आणि ↑ सारखी बाण-चिन्हं
    नाहीत (काळे चौकोन दिसतात) — EOD Market Report मध्ये ही चिन्हं PDF-specific साध्या ASCII-रूपाने
    बदलतो (मूळ स्रोत मजकूर, जो Telegram साठीही वापरला जातो, तसाच अबाधित राहतो).
    """
    if not isinstance(s, str):
        return s
    return s.replace("→", "->").replace("↑", "^").replace("↓", "v")

def _table_font_size(ncols):
    if ncols <= 3:
        return 10
    if ncols <= 5:
        return 9
    return 7.5

def df_to_reportlab_table(df, empty_msg="No data available.", max_rows=40, color_columns=None, font_name=None, font_size=None):
    """
    Convert a pandas DataFrame to a reportlab Table (or a Paragraph if empty).
    color_columns: optional list of column names whose cells get a colour tint based on their
    text content (bullish/green, bearish/red, weakening/amber) — this is what makes the OI and
    signal tables visually informative rather than just black-on-white grids.
    font_name/font_size — पर्यायी, custom-styled reports साठी — दिलं नाही तर जुनाच डीफॉल्ट, backward-compatible.
    """
    if df is None or df.empty:
        return Paragraph(empty_msg, _rpt_normal)
    display_df = df.head(max_rows)
    computed_font_size = font_size or _table_font_size(len(display_df.columns))
    table_font = font_name or _RPT_TABLE_FONT
    table_font_bold = font_name or _RPT_TABLE_FONT_BOLD
    columns = list(display_df.columns)
    raw_rows = display_df.astype(str).values.tolist()
    data = [columns] + [[_fix_missing_glyphs(v) for v in row] for row in raw_rows]
    tbl = Table(data, repeatRows=1, hAlign="LEFT")
    style_cmds = [
        ("FONTNAME", (0, 0), (-1, -1), table_font),
        ("FONTNAME", (0, 0), (-1, 0), table_font_bold),
        ("BACKGROUND", (0, 0), (-1, 0), _C_BG_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), computed_font_size),
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


def _wide_df_table_wrapped(df, usable_width, max_rows=40, font_size=7):
    """🎓 वापरकर्त्याने मागितलेली सुधारणा (LIVE+PAPER slippage PDF मध्ये) — df_to_reportlab_table()
    रुंद (10 स्तंभांच्या) DataFrame साठी वापरलं, तर colWidths न दिल्याने नैसर्गिक (auto) रुंदी पानाच्या
    रुंदीपेक्षा जास्त होऊन उजवीकडचे स्तंभ कापले जातात/दिसतच नाहीत — इथे प्रत्येक सेल Paragraph म्हणून
    wrap केलेला (लांब मजकूर पुढच्या ओळीत जातो) आणि colWidths=usable_width/स्तंभ-संख्या — त्यामुळे
    टेबल कधीच पानाबाहेर जात नाही. फक्त याच (रुंद) टेबलसाठी वापरलेलं — df_to_reportlab_table() इतर
    सर्व existing कॉल्ससाठी जसंच्या तसं (बदल नाही)."""
    if df is None or df.empty:
        return Paragraph("No data available.", _rpt_normal)
    display_df = df.head(max_rows)
    columns = list(display_df.columns)
    cell_style = ParagraphStyle("wide_cell", fontName=_RPT_TABLE_FONT, fontSize=font_size, leading=font_size + 2)
    header_style = ParagraphStyle(
        "wide_header", fontName=_RPT_TABLE_FONT_BOLD, fontSize=font_size, leading=font_size + 2, textColor=colors.white,
    )
    data = [[Paragraph(_xml_escape(_fix_missing_glyphs(str(c))), header_style) for c in columns]]
    for row in display_df.astype(str).values.tolist():
        data.append([Paragraph(_xml_escape(_fix_missing_glyphs(v)), cell_style) for v in row])
    col_width = usable_width / len(columns)
    tbl = Table(data, colWidths=[col_width] * len(columns), repeatRows=1, hAlign="LEFT")
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _C_BG_DARK),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f7f9")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
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

def _kv_table(rows, usable_width, key_ratio=0.35, color_value_rows=None, force_colors=None, font_name=None, font_size=None):
    """Two-column key/value table with a dark key column — colours specific value rows either by
    keyword (color_value_rows, via _signal_style) or explicitly (force_colors={row_idx: (text_color, bg_color)},
    for values like Max Profit/Max Loss whose text doesn't contain BULLISH/BEARISH for keyword matching).
    font_name/font_size — पर्यायी, custom-styled reports साठी — दिलं नाही तर जुनाच डीफॉल्ट, backward-compatible."""
    color_value_rows = color_value_rows or set()
    force_colors = force_colors or {}
    table_font = font_name or _RPT_TABLE_FONT
    table_font_bold = font_name or _RPT_TABLE_FONT_BOLD
    table_font_size = font_size or 11.5
    clean_rows = [[_fix_missing_glyphs(c) for c in row] for row in rows]
    tbl = Table(clean_rows, hAlign="LEFT", colWidths=[usable_width * key_ratio, usable_width * (1 - key_ratio)])
    style_cmds = [
        ("FONTNAME", (0, 0), (-1, -1), table_font),
        ("FONTNAME", (0, 0), (0, -1), table_font_bold),
        ("BACKGROUND", (0, 0), (0, -1), _C_BG_DARK), ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), table_font_size), ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for r in color_value_rows:
        text_color, bg_color = _signal_style(rows[r][1])
        style_cmds.append(("TEXTCOLOR", (1, r), (1, r), text_color))
        style_cmds.append(("BACKGROUND", (1, r), (1, r), bg_color))
        style_cmds.append(("FONTNAME", (1, r), (1, r), table_font_bold))
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
        total_pnl = bt_result.get("total_pnl_points")
        pnl_display = f"{total_pnl:+,.1f} points" if total_pnl is not None else "N/A"
        pnl_color = _C_GREEN if (total_pnl or 0) >= 0 else _C_RED
        pnl_bg = _C_GREEN_BG if (total_pnl or 0) >= 0 else _C_RED_BG
        summary_rows = [
            ["Total Signals", str(bt_result["total"])],
            ["Win Rate (Target vs SL)", win_rate_display],
            ["Target Hit / SL Hit / Still Open", f"{bt_result['target_count']} / {bt_result['sl_count']} / {bt_result['open_count']}"],
            ["Bullish / Bearish Signals", f"{bt_result['bullish_count']} / {bt_result['bearish_count']}"],
            ["Total P&L (Index Points)", pnl_display],
            ["SL % Used", f"{sl_pct}%"],
            ["Risk:Reward Used", f"1:{rr_ratio}"],
        ]
        force_colors = _force_colors_by_label(summary_rows, {
            "Win Rate (Target vs SL)": (win_color, win_bg),
            "Total P&L (Index Points)": (pnl_color, pnl_bg),
        })
        story.append(_kv_table(summary_rows, usable_width, key_ratio=0.45, force_colors=force_colors))
        story.append(Paragraph(
            "P&L is based on INDEX price point-distance only -- not actual option premium P&L, which "
            "depends on delta, theta, and IV changes not modelled here.",
            ParagraphStyle("pnl_note", fontName=_RPT_FONT, fontSize=9, textColor=colors.HexColor("#666666")),
        ))
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
            "exit_price": "Exit Price", "bars_to_exit": "Bars to Exit", "pnl_points": "P&L (Points)",
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


def generate_eod_market_report_pdf(symbol_outlooks, generated_at=None):
    """
    🎓 वापरकर्त्याशी चर्चा करून बांधलेली सुधारणा — दररोज दुपारी ४ वाजताचा, दुसऱ्या दिवसाच्या Intraday +
    Positional Option Selling साठी संक्षिप्त, कृतीयोग्य PDF अहवाल (आता इंग्रजीत, Times New Roman
    Bold-Italic 18pt — वापरकर्त्याशी चर्चा करून ठरवलेलं). जुन्या "Full Market Analysis Report" प्रमाणे
    कच्चा डेटा (संपूर्ण Option Chain, संपूर्ण OI इतिहास, संपूर्ण Trades Log) इथे नाही — फक्त सारांशित,
    निर्णय-उपयुक्त माहिती, प्रति symbol एक विभाग. BULLISH/BEARISH आणि Strong/Weakening सारखे keywords
    रंगीत (हिरवा/लाल/अंबर) दाखवले जातात — color_value_rows द्वारे, _signal_style वापरून.
    symbol_outlooks: [market_report.generate_symbol_outlook(...) चे निकाल, प्रत्येक symbol साठी एक]
    """
    generated_at = generated_at or (datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)).strftime("%d-%b-%Y %H:%M:%S IST")
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.4 * cm, rightMargin=1.4 * cm, topMargin=1.2 * cm, bottomMargin=1.2 * cm)
    usable_width = A4[0] - 2.8 * cm
    story = []
    sec = [0]

    def next_section(text):
        story.append(_section_header(text, sec[0], style=_eod_h2))
        sec[0] += 1
        story.append(Spacer(1, 8))

    title_tbl = Table(
        [[Paragraph("AMW A1 TRADING SYSTEM", _eod_h1)], [Paragraph("EOD Market Report for Tomorrow's Option Selling", _eod_h1_sub)]],
        colWidths=[usable_width],
    )
    title_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _C_BG_DARK),
        ("LEFTPADDING", (0, 0), (-1, -1), 14), ("TOPPADDING", (0, 0), (-1, 0), 14),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 14), ("TOPPADDING", (0, 1), (-1, 1), 0),
    ]))
    story.append(title_tbl)
    story.append(Spacer(1, 6))
    story.append(Paragraph(_fix_missing_glyphs(f"Generated: {generated_at}"), _eod_footer))
    story.append(Spacer(1, 10))

    for outlook in symbol_outlooks:
        symbol = outlook["symbol"]
        next_section(f"{symbol}")

        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — फक्त मजकूर/तक्ते नाही, प्रत्यक्ष candlestick
        # chart (S/R + Supertrend सह) — established plotly+kaleido पद्धतीने.
        chart_bytes = build_eod_report_chart_image(
            outlook.get("chart_df"), sr_levels=outlook.get("sr_levels"),
            supertrend_line=outlook.get("chart_supertrend_line"), symbol=symbol, timeframe_label="15M",
        )
        if chart_bytes:
            img_w = usable_width
            img_h = img_w * (380 / 680)  # मूळ aspect ratio राखणे
            story.append(RLImage(io.BytesIO(chart_bytes), width=img_w, height=img_h))
            story.append(Spacer(1, 10))
        else:
            story.append(Paragraph("Chart could not be generated (data unavailable or export failed).", _eod_footer))
            story.append(Spacer(1, 8))

        mtf = outlook["multi_tf_outlook"]
        outlook_rows = [
            ["Tomorrow's Outlook", _fix_missing_glyphs(mtf["outlook"])],
            ["1D Supertrend", _fix_missing_glyphs(mtf.get("daily_dir") or "N/A")],
            ["1H Supertrend", _fix_missing_glyphs(mtf.get("hourly_dir") or "N/A")],
            ["15M Supertrend", _fix_missing_glyphs(mtf.get("min15_dir") or "N/A")],
            ["India VIX", str(outlook["india_vix"]) if outlook["india_vix"] is not None else "N/A"],
        ]
        story.append(_kv_table(outlook_rows, usable_width, color_value_rows={0, 1, 2, 3}, font_name=_EOD_FONT, font_size=_EOD_FONT_SIZE))
        story.append(Spacer(1, 8))

        story.append(Paragraph("Recommendation (Intraday + Positional)", _eod_h3))
        story.append(Paragraph(_fix_missing_glyphs(outlook["recommendation"]), _eod_normal))
        story.append(Spacer(1, 8))

        if outlook["sr_levels"]:
            story.append(Paragraph("Key S/R Levels", _eod_h3))
            sr_rows = []
            for r in outlook["sr_levels"].get("resistance", [])[:3]:
                sr_rows.append(["Resistance", f"{r['level']:.2f}  ({r['touches']}x touches)"])
            for s in outlook["sr_levels"].get("support", [])[:3]:
                sr_rows.append(["Support", f"{s['level']:.2f}  ({s['touches']}x touches)"])
            if sr_rows:
                story.append(_kv_table(sr_rows, usable_width, font_name=_EOD_FONT, font_size=_EOD_FONT_SIZE))
            story.append(Spacer(1, 8))

        if outlook["oi_summary"]:
            story.append(Paragraph("Today's OI Buildup Trend", _eod_h3))
            oi = outlook["oi_summary"]
            oi_rows = [
                ["Put Trend", _fix_missing_glyphs(oi["day_put_trend"])],
                ["Call Trend", _fix_missing_glyphs(oi["day_call_trend"])],
                ["Overall Direction", _fix_missing_glyphs(oi["day_direction"])],
            ]
            story.append(_kv_table(oi_rows, usable_width, color_value_rows={2}, font_name=_EOD_FONT, font_size=_EOD_FONT_SIZE))
            story.append(Spacer(1, 8))

        if outlook["chart_patterns"]:
            story.append(Paragraph("Today's Notable Chart Patterns", _eod_h3))
            pattern_rows = [[p["time"].strftime("%H:%M"), p["pattern"], f"{p['price']:.2f}"] for p in outlook["chart_patterns"]]
            pattern_df = pd.DataFrame(pattern_rows, columns=["Time", "Pattern", "Price"])
            t = df_to_reportlab_table(pattern_df, font_name=_EOD_FONT, font_size=_EOD_FONT_SIZE)
            story.extend(t if isinstance(t, list) else [t])
            story.append(Spacer(1, 8))

        if outlook["open_positions_greeks"]:
            story.append(Paragraph("Open Positions — Greeks Health", _eod_h3))
            for p in outlook["open_positions_greeks"]:
                story.append(Paragraph(
                    _fix_missing_glyphs(f"{p['trade_id']} ({p['strategy']}): Delta={p['net_delta']}  {p['health_emoji']}"),
                    _eod_normal,
                ))
            story.append(Spacer(1, 8))

        story.append(Spacer(1, 10))

    story.append(Paragraph(
        "This report was generated automatically by the AMW A1 Trading System — for informational purposes only, not investment advice.",
        _eod_footer,
    ))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


# =========================================================
# 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — Performance टॅबवरचा नवीन "संपूर्ण Performance Report"
# PDF — Summary + Strategy/Timeframe-wise P&L (चार्ट्ससह) + प्रत्येक बंद Trade चं Entry व Exit
# (नेमक्या Spot%/Premium-Points कारणासकट) कारण + rule-based शिफारसी, एकाच, प्रिंट-योग्य PDF मध्ये.
# Entry Reason/Exit Reason मराठी (Devanagari) मजकूर असल्याने, या संपूर्ण report मध्ये कुठेही इमोजी
# वापरलेला नाही (DejaVu Sans/NotoSansDevanagari या दोन्ही PDF-fonts मध्ये सर्व इमोजी glyphs नाहीत) —
# त्याऐवजी रंगीत बॅनर/पट्ट्या आणि [!]/[+]/[~] सारखे साधे चिन्ह वापरले आहेत.
# =========================================================

def build_group_pnl_bar_chart(df, title, width=680, height=300):
    """Group (Strategy/Timeframe) नुसार Total P&L चा साधा, रंगीत (नफा=हिरवा, तोटा=लाल) bar chart."""
    if df is None or df.empty:
        return None
    try:
        bar_colors = ["#089981" if v >= 0 else "#F23645" for v in df["Total P&L"]]
        fig = go.Figure(go.Bar(
            x=df["Group"].astype(str), y=df["Total P&L"], marker_color=bar_colors,
            text=[f"₹{v:,.0f}" for v in df["Total P&L"]], textposition="outside",
        ))
        fig.update_layout(
            title=title, template="plotly_white", width=width, height=height,
            margin=dict(l=10, r=10, t=40, b=10), yaxis_title="Total P&L (₹)",
        )
        return fig.to_image(format="png", scale=2)
    except Exception:
        return None


_REC_HEX = {"red": "#F23645", "green": "#089981", "amber": "#D68A00", "grey": "#787B86"}


def _rec_callout(rec_markdown, usable_width):
    """Performance टॅबवरच्या rule-based शिफारसींची इंग्रजी आवृत्ती (Streamlit markdown: **bold**,
    ⚠️/✅/🟡 emoji prefix) -> रंगीत डाव्या पट्टीसकट "callout box" (reportlab Table, तिचं Paragraph
    <b> tags सकट) — इमोजीऐवजी [!]/[+]/[~] चिन्ह (PDF fonts मध्ये इमोजी glyphs नसल्याने), प्लेन
    मजकुरापेक्षा अधिक ठळक/आकर्षक दिसावं म्हणून हलक्या tint background असलेला बॉक्स."""
    text = rec_markdown.strip()
    if text.startswith("⚠️"):
        key, color, bg, tag, text = "red", _C_RED, _C_RED_BG, "[!]", text[2:].strip()
    elif text.startswith("✅"):
        key, color, bg, tag, text = "green", _C_GREEN, _C_GREEN_BG, "[+]", text[2:].strip()
    elif text.startswith("🟡"):
        key, color, bg, tag, text = "amber", _C_AMBER, _C_AMBER_BG, "[~]", text[2:].strip()
    else:
        key, color, bg, tag = "grey", _C_GREY, _C_GREY_BG, "[-]"
    html_text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    body_style = ParagraphStyle(
        "perf_rec", fontName=_RPT_FONT, fontSize=10.5, leading=14, textColor=colors.HexColor("#222222"),
    )
    para = Paragraph(f"<b><font color='{_REC_HEX[key]}'>{tag}</font></b> {html_text}", body_style)
    bar_w = 0.3 * cm
    tbl = Table([["", para]], colWidths=[bar_w, usable_width - bar_w])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), color), ("BACKGROUND", (1, 0), (1, -1), bg),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (1, 0), (1, -1), 10), ("RIGHTPADDING", (1, 0), (1, -1), 10),
        ("LEFTPADDING", (0, 0), (0, -1), 0), ("RIGHTPADDING", (0, 0), (0, -1), 0),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return tbl


_STAT_CARD_STYLE = ParagraphStyle("stat_card", fontName=_RPT_FONT, leading=13, alignment=TA_LEFT)


def _stat_cards_row(items, usable_width):
    """items: [(label, value_str, hex_color_or_None), ...] -> एक रांग समान-रुंदीच्या "dashboard"
    कार्डांची (छोटं राखाडी लेबल वर, मोठा ठळक आकडा खाली) — Summary स्तंभात एका दृष्टिक्षेपात सर्वात
    महत्त्वाचे आकडे (Total Trades/Win Rate/Net P&L/Profit Factor) दिसावेत म्हणून, प्लेन टेबलपेक्षा
    जास्त आकर्षक/स्कॅन-करण्यायोग्य."""
    n = len(items)
    cell_w = usable_width / n
    cells = []
    for label, value, hex_color in items:
        value_color = hex_color or "#131722"
        cells.append(Paragraph(
            f'<font size=9 color="#666666">{label}</font><br/>'
            f'<font size=17 color="{value_color}"><b>{value}</b></font>',
            _STAT_CARD_STYLE,
        ))
    tbl = Table([cells], colWidths=[cell_w] * n)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _C_GREY_BG), ("GRID", (0, 0), (-1, -1), 0.75, colors.white),
        ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return tbl


def _exit_reason_color(label):
    """Trade Log च्या Exit Reason सेलला रंग देण्यासाठी — SL-प्रकार लाल, Target-प्रकार हिरवा, Trailing
    SL अंबर, EOD राखाडी — जेणेकरून लांब टेबलमध्येही नजर फिरवताच कोणता trade कसा बंद झाला दिसेल."""
    t = str(label)
    if "Trailing SL" in t:
        return _C_AMBER, _C_AMBER_BG
    if "Stop-Loss" in t:
        return _C_RED, _C_RED_BG
    if "Target" in t:
        return _C_GREEN, _C_GREEN_BG
    if "EOD" in t:
        return _C_GREY, _C_GREY_BG
    return None, None


class _NumberedCanvas(_BaseCanvas):
    """"Page X of Y" फूटर काढणारा canvas — reportlab च्या standard delayed-page-count pattern नुसार
    (एकूण पानसंख्या आधी माहीत नसते, त्यामुळे सर्व पानं आधी बफर करून, save() वेळी फूटर काढून लिहितो)."""

    def __init__(self, *args, **kwargs):
        _BaseCanvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_footer(total_pages)
            _BaseCanvas.showPage(self)
        _BaseCanvas.save(self)

    def _draw_footer(self, total_pages):
        self.setStrokeColor(colors.HexColor("#DDDDDD"))
        self.setLineWidth(0.5)
        self.line(1.4 * cm, 1.1 * cm, A4[0] - 1.4 * cm, 1.1 * cm)
        self.setFont(_RPT_TABLE_FONT, 8)
        self.setFillColor(colors.HexColor("#888888"))
        self.drawString(1.4 * cm, 0.65 * cm, "A1 TRADING SYSTEM — Performance Report")
        self.drawRightString(A4[0] - 1.4 * cm, 0.65 * cm, f"Page {self._pageNumber} of {total_pages}")


_TRADE_LOG_CELL_STYLE = ParagraphStyle("trade_log_cell", fontName=_RPT_TABLE_FONT, fontSize=7.5, leading=9.5)
_TRADE_LOG_HEADER_STYLE = ParagraphStyle("trade_log_header", fontName=_RPT_TABLE_FONT_BOLD, fontSize=7.5, leading=9.5, textColor=colors.white)


def _build_trade_log_table(df, usable_width, max_rows=250):
    """
    Trade Log चा टेबल — df_to_reportlab_table() (plain strings, कुठलंही column-width control नाही)
    वापरल्यास "Entry Reason"/"Exit Reason Detail" सारखे लांब मजकूराचे स्तंभ पानाच्या रुंदीबाहेर जाऊन
    कापले जातात (उजवीकडचे स्तंभ दिसतच नाहीत) — हे टाळण्यासाठी इथे प्रत्येक स्तंभाची निश्चित रुंदी
    आणि लांब स्तंभांसाठी Paragraph-wrapping (मजकूर अनेक ओळींत मावतो, रांग उंच होते पण कापली जात नाही).
    """
    display_df = df.head(max_rows)
    col_fracs = {
        "Trade ID": 0.11, "Entry Time": 0.095, "Entry Reason": 0.225, "Exit Time": 0.095,
        "Exit Reason": 0.115, "Exit Reason Detail": 0.225, "Realized P&L": 0.075, "Mode": 0.06,
    }
    columns = list(display_df.columns)
    col_widths = [usable_width * col_fracs.get(c, 1.0 / len(columns)) for c in columns]
    wrap_columns = {"Entry Reason", "Exit Reason", "Exit Reason Detail"}

    header_row = [Paragraph(_fix_missing_glyphs(str(c)), _TRADE_LOG_HEADER_STYLE) for c in columns]
    data = [header_row]
    pnl_col_idx = columns.index("Realized P&L") if "Realized P&L" in columns else None
    exit_col_idx = columns.index("Exit Reason") if "Exit Reason" in columns else None
    pnl_row_colors = {}
    exit_row_colors = {}
    for row_idx, row in enumerate(display_df.itertuples(index=False), start=1):
        row_cells = []
        for col_idx, (col_name, val) in enumerate(zip(columns, row)):
            if col_name == "Realized P&L":
                pnl_row_colors[row_idx] = _C_GREEN if val >= 0 else _C_RED
                row_cells.append(Paragraph(f"Rs {val:,.0f}", _TRADE_LOG_CELL_STYLE))
            elif col_name == "Exit Reason":
                text_color, bg_color = _exit_reason_color(val)
                if text_color is not None:
                    exit_row_colors[row_idx] = (text_color, bg_color)
                row_cells.append(Paragraph(_fix_missing_glyphs(str(val)), _TRADE_LOG_CELL_STYLE))
            elif col_name in wrap_columns:
                row_cells.append(Paragraph(_fix_missing_glyphs(str(val)), _TRADE_LOG_CELL_STYLE))
            else:
                row_cells.append(Paragraph(_fix_missing_glyphs(str(val)), _TRADE_LOG_CELL_STYLE))
        data.append(row_cells)

    tbl = Table(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), _C_BG_DARK),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f7f9")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]
    if pnl_col_idx is not None:
        for row_idx, color in pnl_row_colors.items():
            style_cmds.append(("TEXTCOLOR", (pnl_col_idx, row_idx), (pnl_col_idx, row_idx), color))
    if exit_col_idx is not None:
        for row_idx, (text_color, bg_color) in exit_row_colors.items():
            style_cmds.append(("TEXTCOLOR", (exit_col_idx, row_idx), (exit_col_idx, row_idx), text_color))
            style_cmds.append(("BACKGROUND", (exit_col_idx, row_idx), (exit_col_idx, row_idx), bg_color))
    tbl.setStyle(TableStyle(style_cmds))
    result = [tbl]
    if len(df) > max_rows:
        result.append(Paragraph(f"(showing first {max_rows} of {len(df)} rows)", _rpt_footer))
    return result


_TF_GROUP_ORDER = ["1M", "5M", "15M", "30M", "60M"]
_TF_GROUP_COLORS = {
    "1M": colors.HexColor("#2962FF"), "5M": colors.HexColor("#00897B"), "15M": colors.HexColor("#7E57C2"),
    "30M": colors.HexColor("#D68A00"), "60M": colors.HexColor("#E64A19"),
}


def _subsection_banner(text, usable_width, accent_color):
    """Trade Log आतल्या प्रत्येक Entry Timeframe गटासाठी स्वतःचं, ठळक (मुख्य section-header पेक्षा
    लहान) रंगीत heading — जेणेकरून 1M आणि 5M S/R touch trades एकाच मोठ्या टेबलमध्ये मिसळू नयेत,
    प्रत्येक गटाला स्वतःचं स्पष्ट शीर्षक मिळावं."""
    style = ParagraphStyle("tf_subheader", fontName=_RPT_FONT_BOLD, fontSize=11.5, leading=14, textColor=colors.white)
    tbl = Table([[Paragraph(text, style)]], colWidths=[usable_width])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), accent_color),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return tbl


def _trade_log_groups_by_timeframe(trade_log_df):
    """"Entry Timeframe" स्तंभानुसार trade_log_df चे गट पाडणे — 1M, 5M, 15M, 30M, 60M या क्रमाने,
    इतर कुठलंही/अज्ञात शेवटी — प्रत्येक गटासाठी (label, accent_color, sub_df_without_tf_column).
    "Entry Timeframe" स्तंभ नसेल (जुना कॉलर) तर एकच "All Trades" गट परत करणे — मोडणार नाही."""
    if "Entry Timeframe" not in trade_log_df.columns:
        return [("All Trades", _C_ACCENT, trade_log_df)]
    present = list(trade_log_df["Entry Timeframe"].unique())
    ordered = [tf for tf in _TF_GROUP_ORDER if tf in present] + sorted(tf for tf in present if tf not in _TF_GROUP_ORDER)
    groups = []
    for tf in ordered:
        sub_df = trade_log_df[trade_log_df["Entry Timeframe"] == tf].drop(columns=["Entry Timeframe"])
        label = f"{tf} S/R Touch Trades" if tf != "N/A" else "Other / Unknown Timeframe Trades"
        color = _TF_GROUP_COLORS.get(tf, _C_GREY)
        trade_word = "trade" if len(sub_df) == 1 else "trades"
        groups.append((f"{label} ({len(sub_df)} {trade_word})", color, sub_df))
    return groups


def generate_performance_report_pdf(symbol, mode_label, date_from, date_to, summary, pnl_totals,
                                      by_source_df, by_timeframe_df, by_structure_df, trade_log_df, recommendations,
                                      slippage_pairs_df=None, overshoot_df=None):
    """
    Performance टॅबवरचा संपूर्ण, प्रिंट-योग्य PDF रिपोर्ट — Summary, Strategy-wise, Timeframe-wise व
    Option Structure-wise (Credit Spread वि. Naked Option) P&L (बार चार्ट्ससह), प्रत्येक बंद Trade चं
    Entry व Exit कारण (Exit साठी — SL/Target नेमकं Spot% की Premium Points मुळे लागला, हे स्पष्ट
    सांगणारा detail), आणि rule-based शिफारसी.

    summary — database.get_performance_summary() चा dict (निवडलेल्या तारीख-रेंजसाठी).
    pnl_totals — pnl_reports.generate_pnl_report() च्या totals dict (charges-सकट Net P&L साठी).
    by_source_df/by_timeframe_df/by_structure_df — get_performance_by_group() च्या (Group/Trades/
    Win Rate %/Total P&L/Avg P&L स्तंभांसकट) sorted DataFrames, किंवा डेटा नसल्यास None.
    🎓 वापरकर्त्याने मागितलेली सुधारणा ("credit spread आणि naked option buy वेगळे दाखवा, त्यांचं
    विश्लेषण/निष्कर्ष वेगळे असावेत") — by_structure_df (database.OPTION_STRUCTURE_GROUP_SQL वापरून
    तयार केलेला, "Credit Spread"/"Naked Option Buy" असे दोन गट) आधी PDF मध्ये अजिबात नव्हता (on-screen
    "Option Structure नुसार" टॅबमध्येच फक्त दिसायचा) — आता by_source_df/by_timeframe_df सारखाच स्वतंत्र
    विभाग.
    trade_log_df — Trade ID/Entry Time/Entry Reason/Exit Time/Exit Reason/Exit Reason (नेमकं
    कारण)/Realized P&L/Mode स्तंभांसकट, इमोजी-विरहित (PDF-सुरक्षित) DataFrame, किंवा None.
    recommendations — Performance टॅबवरच्या rule-based शिफारसींची यादी (markdown स्ट्रिंग्स — यात आता
    Strategy/Timeframe सोबतच Option Structure-निहायही शिफारसी असतात, प्रत्येक स्वतंत्रपणे ओळखता येईल
    अशा "**Option Structure: Credit Spread**"/"**Option Structure: Naked Option Buy**" उपसर्गासकट).
    🎓 वापरकर्त्याने मागितलेली सुधारणा (LIVE+PAPER शॅडो मोड — slippage PDF मध्येही यायला हवं) —
    slippage_pairs_df (database.get_live_vs_shadow_paper_pairs()) — रिकामा/None असेल (म्हणजे या
    कालावधीत LIVE+PAPER मोड प्रत्यक्ष वापरलेलाच नाही) तर हा संपूर्ण विभाग (heading सकट) वगळला जातो —
    फक्त प्रत्यक्ष LIVE+PAPER trades असतील तरच PDF मध्ये दिसतो.
    🎓 वापरकर्त्याने मागितलेली सुधारणा ("review slipages after trade monitor update", नंतर PDF मध्येही
    हवं म्हणून) — overshoot_df (database.get_sl_tsl_overshoot()) — रिकामा/None असेल तर हा विभागही
    वगळला जातो (या कालावधीत SL/TSL exits नसतील, किंवा जुन्या detail-format आधीचे trades असतील तर).
    """
    generated_at = (datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)).strftime("%d-%b-%Y %H:%M:%S IST")
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.4 * cm, rightMargin=1.4 * cm, topMargin=1.2 * cm, bottomMargin=1.7 * cm)
    usable_width = A4[0] - 2.8 * cm
    story = []
    sec = [0]

    def next_section(text):
        story.append(_section_header(text, sec[0], style=_rpt_h2_bt))
        sec[0] += 1
        story.append(Spacer(1, 8))

    title_tbl = Table(
        [[Paragraph("A1 TRADING SYSTEM", _rpt_h1)], [Paragraph(f"Performance Report — {symbol}", _rpt_h1_sub)]],
        colWidths=[18 * cm],
    )
    title_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _C_BG_DARK),
        ("LEFTPADDING", (0, 0), (-1, -1), 14), ("TOPPADDING", (0, 0), (-1, 0), 14),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 14), ("TOPPADDING", (0, 1), (-1, 1), 0),
    ]))
    story.append(title_tbl)
    accent_bar = Table([[""]], colWidths=[18 * cm], rowHeights=[0.15 * cm])
    accent_bar.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), _C_ACCENT)]))
    story.append(accent_bar)
    story.append(Spacer(1, 10))

    meta_tbl = Table([[
        Paragraph(f"Symbol<br/><b>{symbol}</b>", _rpt_normal),
        Paragraph(f"Mode<br/><b>{mode_label}</b>", _rpt_normal),
        Paragraph(f"Date Range<br/><b>{date_from} to {date_to}</b>", _rpt_normal),
        Paragraph(f"Generated<br/><b>{generated_at}</b>", _rpt_normal),
    ]], colWidths=[usable_width / 4] * 4)
    meta_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _C_GREY_BG), ("GRID", (0, 0), (-1, -1), 0.4, colors.white),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(meta_tbl)
    story.append(Spacer(1, 8))

    next_section("Summary")
    if not summary or summary.get("total_trades", 0) == 0:
        story.append(Paragraph("No CLOSED trades in this period.", ParagraphStyle("no_data", fontName=_RPT_FONT, fontSize=11, leading=15)))
    else:
        pf_str = f"{summary['profit_factor']}" if summary.get("profit_factor") is not None else "N/A"
        gross_pnl = pnl_totals.get("gross_pnl", summary["total_pnl"]) if pnl_totals else summary["total_pnl"]
        total_charges = pnl_totals.get("total_charges", 0) if pnl_totals else 0
        net_pnl = pnl_totals.get("net_pnl", gross_pnl - total_charges) if pnl_totals else gross_pnl
        # 🎓 वापरकर्त्याने मागितलेली सुधारणा (Winning Rate — फक्त शुद्ध SL/Target, ROI — मार्जिन-
        # आधारित) — win_rate आता शुद्ध SL/Target trades नसतील तर None असू शकतो (आधी कधीच None
        # नसायचं) — इथे comparisons/formatting आधी None-गार्ड आवश्यक, नाहीतर PDF तयार करताना crash होईल.
        win_rate = summary.get("win_rate")
        win_rate_str = f"{win_rate}%" if win_rate is not None else "N/A"
        roi_pct = summary.get("roi_pct")
        roi_str = f"{roi_pct}%" if roi_pct is not None else "N/A"
        # 🎓 वापरकर्त्याने विचारलेली तक्रार ("charges खूप जास्त वाटतायत") — आधी फक्त "Total Charges"
        # ही एकच निव्वळ बेरीज दिसायची, नेमकं कशाचं बनलंय ते कुठेच नाही — वापरकर्त्याला स्वतः पडताळता
        # यावं म्हणून (web UI च्या _render_charges_breakdown_caption() सारखीच) order-संख्या आणि
        # brokerage/STT/Exchange/SEBI/Stamp/GST ब्रेकडाऊन आता इथेही.
        total_orders = pnl_totals.get("total_orders", 0) if pnl_totals else 0
        charges_breakdown = pnl_totals.get("charges_breakdown") if pnl_totals else None
        summary_rows = [
            ["Total Trades", str(summary["total_trades"])],
            ["Win Rate (pure SL/Target only)", win_rate_str],
            ["Win Rate (all exits, reference)", f"{summary['win_rate_all_exits']}%" if summary.get("win_rate_all_exits") is not None else "N/A"],
            ["ROI % (on margin used)", f"{roi_str} (margin Rs {summary.get('margin_used', 0):,.0f})"],
            ["Gross P&L", f"Rs {gross_pnl:,.0f}"],
            ["Total Charges", f"Rs {total_charges:,.0f} ({total_orders} orders)"],
        ]
        if charges_breakdown and any(charges_breakdown.values()):
            _cb_labels = {"brokerage": "Brokerage", "stt": "STT", "exchange_txn": "Exchange Txn",
                          "sebi_fee": "SEBI Fee", "stamp_duty": "Stamp Duty", "gst": "GST"}
            _cb_line = " / ".join(f"{_cb_labels[k]} Rs {v:,.0f}" for k, v in charges_breakdown.items() if v)
            # प्लेन string cells wrap होत नाहीत (Table column च्या रुंदीबाहेर overflow/clipped) — इथे
            # ओळ बरीच लांब असू शकते (सहा घटकांपर्यंत), त्यामुळे Paragraph मध्ये wrap करून दिली आहे.
            summary_rows.append(["  └ Charges Breakdown", Paragraph(_cb_line, _rpt_kv_wrap)])
        net_pnl_row_idx = len(summary_rows)
        summary_rows.append(["Net P&L (after charges)", f"Rs {net_pnl:,.0f}"])
        summary_rows.extend([
            ["Profit Factor", pf_str],
            ["Avg P&L / Trade", f"Rs {summary['avg_pnl']:,.0f}"],
            ["Best / Worst Trade", f"Rs {summary['best_trade']:,.0f} / Rs {summary['worst_trade']:,.0f}"],
        ])
        force_colors = {
            4: (_C_GREEN if gross_pnl >= 0 else _C_RED, _C_GREEN_BG if gross_pnl >= 0 else _C_RED_BG),
            net_pnl_row_idx: (_C_GREEN if net_pnl >= 0 else _C_RED, _C_GREEN_BG if net_pnl >= 0 else _C_RED_BG),
        }
        win_hex = "#089981" if (win_rate or 0) >= 50 else "#F23645"
        net_hex = "#089981" if net_pnl >= 0 else "#F23645"
        pf_hex = "#089981" if (summary.get("profit_factor") or 0) >= 1 else "#F23645"
        story.append(_stat_cards_row([
            ("TOTAL TRADES", str(summary["total_trades"]), None),
            ("WIN RATE (SL/TARGET)", win_rate_str, win_hex if win_rate is not None else None),
            ("ROI % (MARGIN)", roi_str, None),
            ("NET P&L (AFTER CHARGES)", f"Rs {net_pnl:,.0f}", net_hex),
            ("PROFIT FACTOR", pf_str, pf_hex),
        ], usable_width))
        story.append(Spacer(1, 6))
        story.append(_kv_table(summary_rows, usable_width, key_ratio=0.4, force_colors=force_colors))
    story.append(Spacer(1, 8))

    next_section("Strategy-wise Performance (which algo strategy is most profitable)")
    if by_source_df is None or by_source_df.empty:
        story.append(Paragraph("No data in this period.", ParagraphStyle("no_data2", fontName=_RPT_FONT, fontSize=11)))
    else:
        chart_bytes = build_group_pnl_bar_chart(by_source_df, "Strategy-wise Total P&L")
        if chart_bytes:
            img_w = usable_width
            img_h = img_w * 300 / 680
            story.append(RLImage(io.BytesIO(chart_bytes), width=img_w, height=img_h))
            story.append(Spacer(1, 6))
        t = df_to_reportlab_table(by_source_df)
        story.extend(t if isinstance(t, list) else [t])
    story.append(Spacer(1, 8))

    next_section("Timeframe-wise Performance (which entry timeframe is most profitable)")
    if by_timeframe_df is None or by_timeframe_df.empty:
        story.append(Paragraph("No data in this period.", ParagraphStyle("no_data3", fontName=_RPT_FONT, fontSize=11)))
    else:
        chart_bytes = build_group_pnl_bar_chart(by_timeframe_df, "Timeframe-wise Total P&L")
        if chart_bytes:
            img_w = usable_width
            img_h = img_w * 300 / 680
            story.append(RLImage(io.BytesIO(chart_bytes), width=img_w, height=img_h))
            story.append(Spacer(1, 6))
        t = df_to_reportlab_table(by_timeframe_df)
        story.extend(t if isinstance(t, list) else [t])
    story.append(Spacer(1, 8))

    next_section("Option Structure-wise Performance (Credit Spread vs Naked Option)")
    if by_structure_df is None or by_structure_df.empty:
        story.append(Paragraph("No data in this period.", ParagraphStyle("no_data4", fontName=_RPT_FONT, fontSize=11)))
    else:
        chart_bytes = build_group_pnl_bar_chart(by_structure_df, "Option Structure-wise Total P&L")
        if chart_bytes:
            img_w = usable_width
            img_h = img_w * 300 / 680
            story.append(RLImage(io.BytesIO(chart_bytes), width=img_w, height=img_h))
            story.append(Spacer(1, 6))
        t = df_to_reportlab_table(by_structure_df)
        story.extend(t if isinstance(t, list) else [t])
    story.append(Spacer(1, 8))

    if overshoot_df is not None and not overshoot_df.empty:
        next_section("SL/TSL Overshoot (Slippage) Tracker")
        story.append(Paragraph(
            "For every SL/Trailing-SL exit, how far past its threshold the bot found the price before "
            "catching it — an inherent gap from polling-based monitoring (trade_monitor.py / "
            "mcx_futures_trader.py). Tracking this over time shows whether polling-interval speedups "
            "actually reduced slippage.", ParagraphStyle("overshoot_note", fontName=_RPT_FONT, fontSize=10, leading=14),
        ))
        story.append(Spacer(1, 6))
        _os_pts = overshoot_df["Overshoot (pts)"].dropna()
        _os_rs = overshoot_df["Overshoot (Rs)"].dropna()
        overshoot_summary_rows = [
            ["SL/TSL Exits", str(len(overshoot_df))],
            ["Avg Overshoot (Points)", f"{_os_pts.mean():.2f} pts" if not _os_pts.empty else "N/A"],
            ["Avg Overshoot (Fixed Rs strategies)", f"Rs {_os_rs.mean():,.0f}" if not _os_rs.empty else "N/A"],
        ]
        story.append(_kv_table(overshoot_summary_rows, usable_width, key_ratio=0.4))
        story.append(Spacer(1, 6))
        t = _wide_df_table_wrapped(overshoot_df, usable_width)
        story.extend(t if isinstance(t, list) else [t])
        story.append(Spacer(1, 8))

    if slippage_pairs_df is not None and not slippage_pairs_df.empty:
        next_section("LIVE vs Shadow PAPER Slippage (LIVE+PAPER mode)")
        story.append(Paragraph(
            "For every pair opened in LIVE+PAPER mode (a real LIVE order plus a shadow PAPER trade "
            "on the same signal), this shows how much real execution (slippage/spread) differed from "
            "the pure simulation. A negative P&amp;L Slippage means the real LIVE result was worse "
            "than PAPER.", ParagraphStyle("slippage_note", fontName=_RPT_FONT, fontSize=10, leading=14),
        ))
        story.append(Spacer(1, 6))
        entry_slip_series = slippage_pairs_df["Entry Slippage (Rs)"].dropna()
        pnl_slip_series = slippage_pairs_df["P&L Slippage (Rs)"].dropna()
        avg_entry_slip = entry_slip_series.mean() if not entry_slip_series.empty else None
        avg_pnl_slip = pnl_slip_series.mean() if not pnl_slip_series.empty else None
        total_pnl_slip = pnl_slip_series.sum() if not pnl_slip_series.empty else 0
        slip_summary_rows = [
            ["LIVE+PAPER Pairs", str(len(slippage_pairs_df))],
            ["Avg Entry Slippage", f"Rs {avg_entry_slip:,.1f}" if avg_entry_slip is not None else "N/A"],
            ["Avg P&L Slippage / Trade", f"Rs {avg_pnl_slip:,.1f}" if avg_pnl_slip is not None else "N/A"],
            ["Total P&L Slippage", f"Rs {total_pnl_slip:,.0f}"],
        ]
        story.append(_kv_table(slip_summary_rows, usable_width, key_ratio=0.4))
        story.append(Spacer(1, 6))
        t = _wide_df_table_wrapped(slippage_pairs_df, usable_width)
        story.extend(t if isinstance(t, list) else [t])
        story.append(Spacer(1, 8))

    next_section("Conclusion & Recommendations")
    if not recommendations:
        story.append(Paragraph(
            "Not enough data in this period to draw conclusions (at least 5 trades/group needed).",
            ParagraphStyle("no_rec", fontName=_RPT_FONT, fontSize=11),
        ))
    else:
        for rec in recommendations:
            story.append(_rec_callout(rec, usable_width))
            story.append(Spacer(1, 4))
    story.append(Spacer(1, 8))

    story.append(PageBreak())
    next_section(f"Trade Log — Entry & Exit Reason for every trade ({len(trade_log_df) if trade_log_df is not None else 0} trades)")
    if trade_log_df is None or trade_log_df.empty:
        story.append(Paragraph("No closed trades in this period.", ParagraphStyle("no_trades", fontName=_RPT_FONT, fontSize=11)))
    else:
        story.append(Paragraph(
            "Every SL/Target Exit Reason below names the exact basis it was triggered on — "
            "<b>Spot %-based</b>, <b>Premium pts-based</b>, <b>Spot %+Premium pts</b> (both reached together), "
            "or <b>Fixed Rs P&amp;L-based</b> — so the exact cause of every win/loss is clear at a glance. "
            "Trades are grouped below by Entry Timeframe (1M S/R touch, 5M S/R touch, etc.) into their own tables.",
            ParagraphStyle("trade_log_note", fontName=_RPT_FONT, fontSize=9.5, leading=13, textColor=colors.HexColor("#555555"), spaceAfter=6),
        ))
        for group_label, group_color, group_df in _trade_log_groups_by_timeframe(trade_log_df):
            story.append(_subsection_banner(group_label, usable_width, group_color))
            story.append(Spacer(1, 4))
            story.extend(_build_trade_log_table(group_df, usable_width, max_rows=250))
            story.append(Spacer(1, 10))

    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "This report was generated automatically by the AMW A1 Trading System — for informational purposes only, not investment advice. "
        "The Recommendations section is a rule-based, data-driven starting point, not financial advice — the final decision is always yours.",
        _rpt_footer,
    ))

    doc.build(story, canvasmaker=_NumberedCanvas)
    buf.seek(0)
    return buf.getvalue()
