"""Performance & Backtest page — trade analytics and the Risk:Reward signal checker."""
import datetime
import os
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import get_ist_now, get_ist_today
from database import (
    get_performance_summary, get_equity_curve_data, get_performance_by_group,
    get_closed_trades_detail, get_exit_reason_breakdown,
)
from backtest import run_signal_backtest_rr, run_signal_backtest_v2
from upstox_api import fetch_candles_date_range
from signals import resample_to_1h
from yfinance_source import fetch_yfinance_candles, get_yfinance_max_days
from pdf_reports import generate_backtest_report_pdf_rr, generate_backtest_report_pdf_v2, generate_performance_report_pdf
from pnl_reports import generate_pnl_report

# 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Trading Charges) — "आतापर्यंतचे एकूण" Charges/Net P&L
# साठी trades ची सुरुवात कधी झाली हे माहीत नसतं, त्यामुळे इथे एक व्यवहार्य, पुरेशी जुनी सुरुवात-तारीख
# (हे app अस्तित्वात येण्याआधीचीच) वापरली आहे — त्यामुळे "आतापर्यंतचा संपूर्ण इतिहास" कव्हर होतो.
_ALL_TIME_START = datetime.date(2020, 1, 1)

# 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — "कोणती रणनीती (algo) जास्त फायदेशीर आहे" हे कळावं म्हणून
# live_trades.source कोडला वाचनीय नाव — जेणेकरून टेबल/चार्टमध्ये कच्चा internal कोड ऐवजी नाव दिसेल.
_SOURCE_LABELS = {
    "dynamic_sr_instant": "1-Min Instant Trader (Dynamic S/R)",
    "srv2_momentum_reversal": "SRv2 Momentum Reversal (15/30/60M)",
    "credit_spread_auto_trader": "Credit Spread Auto Trader",
    "oi_signal_auto_trader": "OI Signal Auto Trader",
    "oi_greeks_vix_strategy": "OI + Greeks + VIX Strategy",
    "strategy_builder": "Strategy Builder (Custom)",
    "MANUAL": "Manual Entry",
    "DASHBOARD": "Dashboard (Manual)",
    "MULTI_ACCOUNT": "Multi-Account Copy",
    "UNKNOWN": "अज्ञात (जुने ट्रेड्स)",
}

# 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — "प्रत्येक trade चं Entry व Exit कारण दिसायला हवं" या
# मागणीसाठी — live_trades.exit_reason (आधीपासूनच साठवलेला) वाचनीय स्वरूपात दाखवण्यासाठी.
_EXIT_REASON_LABELS = {
    "SL": "🔴 Stop-Loss गाठला",
    "TRAILING_SL": "🟡 Trailing SL (ATR-आधारित)",
    "PCT_TRAILING_SL": "🟡 Trailing SL (%-आधारित)",
    "TSL_SL": "🟡 Trailing SL ला स्पर्श (Entry/Breakeven वर घट्ट)",
    "TARGET": "🟢 Target गाठला",
    "PREMIUM_TARGET": "🟢 Premium Target गाठला",
    "NEXT_LEVEL_EXIT": "🟢 पुढचा S/R Level गाठला (profit-booked)",
    "EOD_SQUAREOFF": "⚪ EOD Square-off (दिवसअखेर)",
    "CARRY_FORWARD_CHECK_INSUFFICIENT_PROFIT": "⚪ अपुरा नफा — carry न करता बंद",
    "OI_REVERSAL": "🔵 OI Reversal सिग्नल",
    "MANUAL_CLOSE": "✋ मॅन्युअली बंद केलं",
    "RECONCILED_EXTERNAL_CLOSE": "↔️ Broker कडून बाहेरून बंद (Reconciled)",
    "SL_HIT": "🔴 Stop-Loss गाठला (जुनी नोंद)",
    "TARGET_HIT": "🟢 Target गाठला (जुनी नोंद)",
    "UNKNOWN": "अज्ञात",
}
# PDF Report साठी — fonts/ फोल्डरमध्ये Devanagari font नसल्याने (फक्त DejaVu Sans आहे — ना इमोजी,
# ना मराठी script), पूर्णपणे इंग्रजी, इमोजी-विरहित समांतर लेबल्स — फक्त PDF मध्ये वापरण्यासाठी.
_EXIT_REASON_LABELS_PLAIN = {
    "SL": "Stop-Loss hit", "TRAILING_SL": "Trailing SL (ATR-based)",
    "PCT_TRAILING_SL": "Trailing SL (%-based)", "TSL_SL": "Trailing SL hit (locked to Entry/Breakeven)",
    "TARGET": "Target hit", "PREMIUM_TARGET": "Premium Target hit",
    "NEXT_LEVEL_EXIT": "Next S/R Level hit (profit-booked)", "EOD_SQUAREOFF": "EOD Square-off (end of day)",
    "CARRY_FORWARD_CHECK_INSUFFICIENT_PROFIT": "Insufficient profit — closed without carrying forward",
    "OI_REVERSAL": "OI Reversal signal", "MANUAL_CLOSE": "Closed manually",
    "RECONCILED_EXTERNAL_CLOSE": "Closed externally by broker (Reconciled)",
    "SL_HIT": "Stop-Loss hit (legacy record)", "TARGET_HIT": "Target hit (legacy record)", "UNKNOWN": "Unknown",
}
# SL/TSL प्रकारचे exit_reason "जोखीम-नियंत्रण" (जोखीम मर्यादित करण्यासाठी बंद) म्हणून एकत्र मोजण्यासाठी.
_SL_TYPE_EXIT_REASONS = {"SL", "TRAILING_SL", "PCT_TRAILING_SL", "TSL_SL", "SL_HIT"}
_TARGET_TYPE_EXIT_REASONS = {"TARGET", "PREMIUM_TARGET", "NEXT_LEVEL_EXIT", "TARGET_HIT"}


def _exit_basis_tag(exit_reason, detail):
    """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (PDF मध्ये SL/Target चा प्रकार लगेच दिसावा) —
    exit_reason_detail च्या मजकुरावरून (trading_engine.evaluate_point_spot_exit() ने आधीच लिहिलेला,
    "via Spot move"/"via Premium points"/"both ... simultaneously" इ.) SL/Target नेमका Spot%,
    Premium Points, दोन्ही, की निव्वळ ₹ P&L वर आधारित होता हे लहान टॅगमध्ये काढणे — Exit Reason
    स्तंभातच दिसावं म्हणून (नुसत्या लांब Detail स्तंभात दडलेला मजकूर वाचायला लागू नये)."""
    if not detail or not isinstance(detail, str):
        return None
    if "via Spot move" in detail:
        return "Spot %-based"
    if "via Premium points" in detail:
        return "Premium pts-based"
    if exit_reason in ("SL", "TARGET") and "simultaneously" in detail:
        return "Spot %+Premium pts"
    if exit_reason == "TSL_SL":
        return "Premium pts-based"
    if exit_reason == "PREMIUM_TARGET":
        return "Premium %-based"
    if exit_reason in ("SL", "TRAILING_SL", "PCT_TRAILING_SL", "TARGET") and "total P&L" in detail:
        return "Fixed Rs P&L-based"
    return None


def _exit_reason_label_with_tag(exit_reason, detail):
    """_EXIT_REASON_LABELS_PLAIN चं लेबल + (शक्य असल्यास) _exit_basis_tag() चा टॅग — फक्त PDF च्या
    Exit Reason स्तंभासाठी (जुन्या, या feature आधीच्या trades साठी detail नसल्याने टॅगशिवायच राहतं)."""
    label = _EXIT_REASON_LABELS_PLAIN.get(exit_reason, exit_reason)
    tag = _exit_basis_tag(exit_reason, detail)
    return f"{label} ({tag})" if tag else label


def _entry_reason_text(row):
    """source/entry_timeframe/entry_level_price/strategy या आधीपासूनच साठवलेल्या स्तंभांवरून, प्रत्येक
    trade साठी वाचनीय 'Entry Reason' मजकूर तयार करणे (कारण एकच स्वतंत्र मजकूर-स्तंभ आधी साठवलेला नव्हता)."""
    src = _SOURCE_LABELS.get(row["source"], row["source"])
    tf = row["entry_timeframe"] if row["entry_timeframe"] and row["entry_timeframe"] != "UNKNOWN" else "N/A"
    lvl = f"₹{row['entry_level_price']:,.1f}" if pd.notna(row.get("entry_level_price")) else "N/A"
    return f"{src} — {tf} S/R level ({lvl}) touch; रचना: {row['strategy']}"


def _entry_reason_text_en(row):
    """_entry_reason_text() ची पूर्णपणे इंग्रजी आवृत्ती — फक्त Performance Report PDF साठी (PDF च्या
    fonts/ फोल्डरमध्ये Devanagari font नसल्याने, तिथे मराठी शब्द रिकाम्या चौकोनासारखे दिसतात)."""
    src = _SOURCE_LABELS.get(row["source"], row["source"])
    tf = row["entry_timeframe"] if row["entry_timeframe"] and row["entry_timeframe"] != "UNKNOWN" else "N/A"
    lvl = f"Rs {row['entry_level_price']:,.1f}" if pd.notna(row.get("entry_level_price")) else "N/A"
    return f"{src} - {tf} S/R level ({lvl}) touch; structure: {row['strategy']}"


def _render_group_breakdown(symbol, group_col, mode_filter, start_date, end_date, chart_title):
    """group_col (source/entry_timeframe/strategy/trading_style) नुसार कामगिरी — टेबल + बार चार्ट +
    विजेता/पराभूत caption. कोणती रणनीती/टाईमफ्रेम जास्त फायदेशीर आहे हे एका दृष्टिक्षेपात कळावं म्हणून."""
    df = get_performance_by_group(symbol, group_col, mode_filter=mode_filter, start_date=start_date, end_date=end_date)
    if df.empty:
        st.caption("या कालावधीत डेटा नाही.")
        return None
    if group_col == "source":
        df = df.copy()
        df["Group"] = df["Group"].map(lambda g: _SOURCE_LABELS.get(g, g))
    df_sorted = df.sort_values("Total P&L", ascending=False).reset_index(drop=True)
    best, worst = df_sorted.iloc[0], df_sorted.iloc[-1]
    if len(df_sorted) > 1:
        st.success(f"🏆 सर्वाधिक फायदेशीर: **{best['Group']}** — ₹{best['Total P&L']:,.0f} ({best['Trades']} trades, Win Rate {best['Win Rate %']}%)")
        st.error(f"📉 सर्वात कमी फायदेशीर: **{worst['Group']}** — ₹{worst['Total P&L']:,.0f} ({worst['Trades']} trades, Win Rate {worst['Win Rate %']}%)")
    else:
        st.info(f"फक्त एकच गट सापडला: **{best['Group']}** — ₹{best['Total P&L']:,.0f}")

    bar_colors = ["#26A69A" if v >= 0 else "#EF5350" for v in df_sorted["Total P&L"]]
    fig = go.Figure(go.Bar(
        x=df_sorted["Group"], y=df_sorted["Total P&L"], marker_color=bar_colors,
        text=df_sorted["Total P&L"].map(lambda v: f"₹{v:,.0f}"), textposition="outside",
    ))
    fig.update_layout(
        template="plotly_dark", height=300, margin=dict(l=10, r=10, t=30, b=30),
        paper_bgcolor="#131722", plot_bgcolor="#131722", title=chart_title, yaxis_title="Total P&L (₹)",
    )
    st.plotly_chart(fig, width="stretch")
    st.dataframe(df_sorted, width="stretch", hide_index=True)
    return df_sorted


def _build_recommendations(symbol, group_col, group_label, mode_filter, start_date, end_date, min_trades=5, english=False):
    """group_col (source/entry_timeframe) नुसार exit_reason वितरण तपासून, SL/Target/Trailing-SL
    सेटिंग्ज कशा optimize कराव्यात याबद्दल नियम-आधारित (rule-based), आकड्यांसकट शिफारशी तयार करणे.
    कमी trades (< min_trades) असलेले गट सांख्यिकीयदृष्ट्या अविश्वसनीय म्हणून वगळले जातात.
    english=True — Performance Report PDF साठी (fonts/ मध्ये Devanagari font नसल्याने PDF मध्ये फक्त
    इंग्रजी शिफारसी दाखवाव्या लागतात) — on-screen Streamlit साठी मात्र नेहमीचंच (english=False) मराठी."""
    exit_df = get_exit_reason_breakdown(symbol, group_col, mode_filter=mode_filter, start_date=start_date, end_date=end_date)
    if exit_df.empty:
        return []

    recs = []
    for grp, sub in exit_df.groupby("Group"):
        total_trades = sub["Trades"].sum()
        if total_trades < min_trades:
            continue
        total_pnl = sub["Total P&L"].sum()
        grp_label = _SOURCE_LABELS.get(grp, grp) if group_col == "source" else grp

        sl_sub = sub[sub["Exit Reason"].isin(_SL_TYPE_EXIT_REASONS)]
        target_sub = sub[sub["Exit Reason"].isin(_TARGET_TYPE_EXIT_REASONS)]
        eod_sub = sub[sub["Exit Reason"] == "EOD_SQUAREOFF"]

        sl_trades = sl_sub["Trades"].sum()
        sl_pct = sl_trades / total_trades * 100
        target_trades = target_sub["Trades"].sum()
        target_pct = target_trades / total_trades * 100
        eod_trades = eod_sub["Trades"].sum()
        eod_pct = eod_trades / total_trades * 100
        eod_pnl = eod_sub["Total P&L"].sum()

        if sl_pct >= 50 and total_pnl < 0:
            if english:
                recs.append(
                    f"⚠️ **{group_label}: {grp_label}** — {sl_pct:.0f}% of trades ({int(sl_trades)}/{int(total_trades)}) "
                    f"closed via SL/Trailing-SL, with a net loss of Rs {total_pnl:,.0f} overall. "
                    "Suggested fix: tighten entry gates (RSI/PCR) further, or widen the SL % — the current SL "
                    "looks too tight and is getting hit by normal price noise."
                )
            else:
                recs.append(
                    f"⚠️ **{group_label}: {grp_label}** — {sl_pct:.0f}% trades ({int(sl_trades)}/{int(total_trades)}) "
                    f"SL/Trailing-SL ला touch होऊन बंद झाले आणि एकूण निव्वळ तोटा ₹{total_pnl:,.0f} आहे. "
                    "सुचवलेली दुरुस्ती: Entry गेट्स (RSI/PCR) अजून कडक करा, किंवा SL % थोडं वाढवून बघा — "
                    "सध्याचा SL खूप घट्ट असून सामान्य चढ-उतारातच लागतोय असं दिसतंय."
                )
        if eod_pct >= 30 and eod_pnl < 0:
            if english:
                recs.append(
                    f"⚠️ **{group_label}: {grp_label}** — {eod_pct:.0f}% of trades ({int(eod_trades)}/{int(total_trades)}) "
                    f"close at EOD Square-off with a net loss (Rs {eod_pnl:,.0f}). "
                    "Suggested fix: bring the new-entry cutoff time earlier, or keep the Target closer so fewer "
                    "positions stay open until end of day."
                )
            else:
                recs.append(
                    f"⚠️ **{group_label}: {grp_label}** — {eod_pct:.0f}% trades ({int(eod_trades)}/{int(total_trades)}) "
                    f"EOD Square-off ला निव्वळ तोट्यात (₹{eod_pnl:,.0f}) बंद होतायत. "
                    "सुचवलेली दुरुस्ती: नवीन entry साठीची कट-ऑफ वेळ आधी आणा, किंवा Target अजून जवळ ठेवून "
                    "दिवसअखेरपर्यंत position उघडी राहण्याचं प्रमाण कमी करा."
                )
        if target_pct >= 50 and total_pnl > 0:
            if english:
                recs.append(
                    f"✅ **{group_label}: {grp_label}** — {target_pct:.0f}% of trades ({int(target_trades)}/{int(total_trades)}) "
                    f"close profitably by hitting Target/Next-Level (Rs {total_pnl:,.0f} total). "
                    "Current settings are working well — keep them as-is, and consider a modest lot-size increase if possible."
                )
            else:
                recs.append(
                    f"✅ **{group_label}: {grp_label}** — {target_pct:.0f}% trades ({int(target_trades)}/{int(total_trades)}) "
                    f"Target/पुढचा Level गाठून नफ्यात बंद होतायत (एकूण ₹{total_pnl:,.0f}). "
                    "सध्याची सेटिंग्ज चांगली काम करतायत — हीच कायम ठेवा, शक्य असल्यास lot size थोडी वाढवण्याचा विचार करा."
                )

        tsl_sub = sub[sub["Exit Reason"].isin(["TRAILING_SL", "PCT_TRAILING_SL"])]
        if not tsl_sub.empty and not target_sub.empty:
            tsl_avg = tsl_sub["Total P&L"].sum() / tsl_sub["Trades"].sum()
            target_avg = target_sub["Total P&L"].sum() / target_sub["Trades"].sum()
            if tsl_avg > 0 and target_avg > 0 and tsl_avg < target_avg * 0.5:
                if english:
                    recs.append(
                        f"🟡 **{group_label}: {grp_label}** — the average profit on trades closed by Trailing SL "
                        f"(Rs {tsl_avg:,.0f}) is less than half the average profit on trades that hit Target directly "
                        f"(Rs {target_avg:,.0f}) — the Trailing SL appears to be locking in profit too early. "
                        "Suggested fix: loosen the Trailing SL's ATR multiplier (or % distance) to let profits run further."
                    )
                else:
                    recs.append(
                        f"🟡 **{group_label}: {grp_label}** — Trailing SL मुळे बंद झालेल्या trades चा सरासरी नफा "
                        f"(₹{tsl_avg:,.0f}) हा थेट Target गाठलेल्या trades च्या सरासरी नफ्यापेक्षा (₹{target_avg:,.0f}) "
                        "निम्म्याहून कमी आहे — Trailing SL लवकर घट्ट होऊन नफा वेळेआधी बुक होतोय असं दिसतंय. "
                        "सुचवलेली दुरुस्ती: Trailing SL चं ATR गुणक (किंवा % अंतर) थोडं सैल करून नफा जास्त वाढू द्या."
                    )
    return recs


def render():
    symbol = st.session_state["symbol"]
    token_input = st.session_state["token_input"]

    st.subheader("📈 Performance Analytics")
    perf_mode_choice = st.radio("दाखवा:", ["सर्व", "फक्त LIVE", "फक्त PAPER"], horizontal=True, key="perf_mode_filter")
    perf_mode_f = None if perf_mode_choice == "सर्व" else ("LIVE" if "LIVE" in perf_mode_choice else "PAPER")

    # =========================================================
    # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — आजची कामगिरी आपोआप, कुठलीही तारीख/फिल्टर
    # निवडण्याची गरज न पडता, पान उघडताक्षणीच दिसते. खालचा तारीख-रेंज फिल्टर फक्त ऐतिहासिक
    # विश्लेषणासाठी आहे — आजचा दिवस त्यामागे कधीच लपत नाही.
    # =========================================================
    today_d = get_ist_today()
    st.markdown(f"### 📌 आजची कामगिरी — {today_d.strftime('%d-%b-%Y')}")
    st.caption("हे नेहमी आपोआप आजच्या तारखेचं दिसतं — तारीख निवडायची गरज नाही.")
    _, today_totals = generate_pnl_report(symbol, "Daily", today_d, today_d, mode_filter=perf_mode_f)
    if today_totals["total_trades"] == 0:
        st.info("आज अजून कोणताही ट्रेड बंद झालेला नाही.")
    else:
        tcol1, tcol2, tcol3, tcol4 = st.columns(4)
        with tcol1:
            st.metric("आजचे बंद ट्रेड्स", today_totals["total_trades"])
        with tcol2:
            st.metric("Gross P&L", f"₹{today_totals['gross_pnl']:,.0f}")
        with tcol3:
            st.metric("एकूण Charges", f"₹{today_totals['total_charges']:,.0f}", f"{today_totals['total_orders']} orders")
        with tcol4:
            st.metric("Net P&L (आज)", f"₹{today_totals['net_pnl']:,.0f}")

        tacol1, tacol2 = st.columns(2)
        with tacol1:
            st.markdown("##### 🎯 आज — रणनीतीनुसार (Strategy)")
            _render_group_breakdown(symbol, "source", perf_mode_f, today_d, today_d, "आजचं Strategy-wise P&L")
        with tacol2:
            st.markdown("##### ⏱️ आज — टाईमफ्रेमनुसार")
            _render_group_breakdown(symbol, "entry_timeframe", perf_mode_f, today_d, today_d, "आजचं Timeframe-wise P&L")

    st.markdown("---")
    st.markdown("### 📊 एकूण (All-Time) कामगिरी")
    summary = get_performance_summary(symbol, mode_filter=perf_mode_f)
    if summary.get("total_trades", 0) == 0:
        st.info("अजून कोणतेही बंद झालेले ट्रेड्स नाहीत — Performance आकडे दिसण्यासाठी किमान एक ट्रेड बंद व्हायला हवा.")
    else:
        pcol1, pcol2, pcol3, pcol4 = st.columns(4)
        with pcol1:
            st.metric("Total Trades", summary["total_trades"])
        with pcol2:
            st.metric("Win Rate", f"{summary['win_rate']}%")
        with pcol3:
            st.metric("Total P&L", f"₹{summary['total_pnl']:,.0f}")
        with pcol4:
            pf_str = f"{summary['profit_factor']}" if summary["profit_factor"] is not None else "N/A"
            st.metric("Profit Factor", pf_str)

        pcol5, pcol6, pcol7, pcol8 = st.columns(4)
        with pcol5:
            st.metric("Avg P&L/Trade", f"₹{summary['avg_pnl']:,.0f}")
        with pcol6:
            st.metric("Avg Win", f"₹{summary['avg_win']:,.0f}" if summary["avg_win"] is not None else "N/A")
        with pcol7:
            st.metric("Avg Loss", f"₹{summary['avg_loss']:,.0f}" if summary["avg_loss"] is not None else "N/A")
        with pcol8:
            st.metric("Best / Worst", f"₹{summary['best_trade']:,.0f} / ₹{summary['worst_trade']:,.0f}")

        # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — वरचं "Total P&L" आतापर्यंत फक्त Gross होतं
        # (वास्तविक ब्रोकरेज शुल्क कुठेच दाखवलं जात नव्हतं). आता आतापर्यंतच्या संपूर्ण इतिहासाचं,
        # charges.py वापरून मोजलेलं वास्तविक शुल्क आणि त्यानंतरचा Net P&L इथेच दाखवला जातो.
        _, _all_time_totals = generate_pnl_report(symbol, "Monthly", _ALL_TIME_START, get_ist_today(), mode_filter=perf_mode_f)
        pcol9, pcol10 = st.columns(2)
        with pcol9:
            st.metric(
                "एकूण Charges (वास्तविक ब्रोकरेज)", f"₹{_all_time_totals['total_charges']:,.0f}",
                f"{_all_time_totals['total_orders']} orders",
            )
        with pcol10:
            st.metric("Net P&L (charges नंतर)", f"₹{_all_time_totals['net_pnl']:,.0f}")
        if _all_time_totals["charges_by_broker"]:
            _broker_lines = " · ".join(
                f"{b.upper()}: {v['orders']} orders / ₹{v['charge']:,.0f}"
                for b, v in _all_time_totals["charges_by_broker"].items()
            )
            st.caption(f"ब्रोकरनुसार: {_broker_lines}")

        st.markdown("##### 📉 Equity Curve (संचयी वास्तविक P&L)")
        curve_df = get_equity_curve_data(symbol, mode_filter=perf_mode_f)
        if not curve_df.empty:
            eq_fig = go.Figure()
            eq_fig.add_trace(go.Scatter(
                x=curve_df["exit_time"], y=curve_df["cumulative_pnl"],
                mode="lines+markers", line=dict(color="#2962FF", width=2),
                fill="tozeroy", fillcolor="rgba(41,98,255,0.08)",
            ))
            eq_fig.update_layout(
                template="plotly_dark", height=350, margin=dict(l=10, r=10, t=20, b=10),
                paper_bgcolor="#131722", plot_bgcolor="#131722", yaxis_title="Cumulative P&L (₹)",
            )
            st.plotly_chart(eq_fig, width="stretch")
        else:
            st.info("Equity Curve साठी पुरेसा डेटा नाही.")

        if perf_mode_f is None:
            st.markdown("##### 📝 PAPER वि LIVE तुलना")
            comp_rows = []
            for label in ("LIVE", "PAPER"):
                s = get_performance_summary(symbol, mode_filter=label)
                if s.get("total_trades", 0) > 0:
                    comp_rows.append({"Mode": label, "Trades": s["total_trades"], "Win Rate %": s["win_rate"], "Total P&L": s["total_pnl"], "Avg P&L": s["avg_pnl"]})
            if comp_rows:
                st.dataframe(pd.DataFrame(comp_rows), width="stretch", hide_index=True)

    st.markdown("---")
    st.markdown("### 🔍 रणनीती व टाईमफ्रेम विश्लेषण (तारीख/तारीख-रेंज निवडून)")
    st.caption(
        "कोणती रणनीती (Algo Strategy) आणि कोणता Entry Timeframe जास्त फायदेशीर आहे हे इथे कालावधी "
        "निवडून तपासा — त्याच आधारावर algo/strategy सेटिंग्ज बदलायच्या का हे ठरवता येईल."
    )
    quick_range = st.radio(
        "जलद निवड", ["आज", "गेले 7 दिवस", "गेला महिना", "गेले 3 महिने", "संपूर्ण इतिहास", "कस्टम रेंज"],
        horizontal=True, key="perf_analysis_quick_range", index=2,
    )
    if quick_range == "आज":
        an_from, an_to = today_d, today_d
    elif quick_range == "गेले 7 दिवस":
        an_from, an_to = today_d - datetime.timedelta(days=7), today_d
    elif quick_range == "गेला महिना":
        an_from, an_to = today_d - datetime.timedelta(days=30), today_d
    elif quick_range == "गेले 3 महिने":
        an_from, an_to = today_d - datetime.timedelta(days=90), today_d
    elif quick_range == "संपूर्ण इतिहास":
        an_from, an_to = _ALL_TIME_START, today_d
    else:
        acol1, acol2 = st.columns(2)
        with acol1:
            an_from = st.date_input("पासून", value=today_d - datetime.timedelta(days=30), key="perf_analysis_from")
        with acol2:
            an_to = st.date_input("पर्यंत", value=today_d, key="perf_analysis_to")

    if an_from > an_to:
        st.error("'पर्यंत' ही तारीख 'पासून' नंतरची असावी.")
    else:
        st.caption(f"निवडलेली रेंज: {an_from} ते {an_to}")
        an_tab1, an_tab2, an_tab3, an_tab4 = st.tabs(
            ["🎯 Algo Strategy नुसार", "⏱️ Timeframe नुसार", "🧩 Option Structure नुसार", "📐 Trading Style नुसार"]
        )
        with an_tab1:
            an_by_source = _render_group_breakdown(symbol, "source", perf_mode_f, an_from, an_to, "Strategy-wise P&L")
        with an_tab2:
            an_by_timeframe = _render_group_breakdown(symbol, "entry_timeframe", perf_mode_f, an_from, an_to, "Timeframe-wise P&L")
        with an_tab3:
            _render_group_breakdown(symbol, "strategy", perf_mode_f, an_from, an_to, "Option Structure-wise P&L")
        with an_tab4:
            _render_group_breakdown(symbol, "trading_style", perf_mode_f, an_from, an_to, "Trading Style-wise P&L")

        st.markdown("##### 📋 Trade Log — प्रत्येक Trade चं Entry व Exit कारण")
        trade_log_df = get_closed_trades_detail(symbol, mode_filter=perf_mode_f, start_date=an_from, end_date=an_to)
        trade_log_display = None
        trade_log_pdf_df = None
        if trade_log_df.empty:
            st.caption("या कालावधीत कोणतेही बंद ट्रेड्स नाहीत.")
        else:
            trade_log_display = trade_log_df.copy()
            trade_log_display["Entry Reason"] = trade_log_display.apply(_entry_reason_text, axis=1)
            trade_log_display["Exit Reason"] = trade_log_display["exit_reason"].map(lambda r: _EXIT_REASON_LABELS.get(r, r))
            trade_log_display["Exit Reason (नेमकं कारण)"] = trade_log_display["exit_reason_detail"].fillna("—")
            # PDF मध्ये embedded इमोजी सुरक्षित नाहीत (table font मध्ये सर्व glyphs नसतात) — त्यामुळे
            # PDF साठी वेगळा, इमोजी-विरहित (plain) DataFrame — on-screen table मात्र इमोजीसकटच राहतो.
            trade_log_pdf_df = trade_log_df.copy()
            trade_log_pdf_df["Entry Reason"] = trade_log_pdf_df.apply(_entry_reason_text_en, axis=1)
            # 🎓 Exit Reason स्तंभातच SL/Target चा नेमका प्रकार (Spot %-based / Premium pts-based /
            # दोन्ही / Fixed Rs P&L-based) दिसावा — फक्त लांब Detail स्तंभात दडलेला राहू नये.
            trade_log_pdf_df["Exit Reason"] = trade_log_pdf_df.apply(
                lambda r: _exit_reason_label_with_tag(r["exit_reason"], r["exit_reason_detail"]), axis=1,
            )
            trade_log_pdf_df["Exit Reason Detail"] = trade_log_pdf_df["exit_reason_detail"].fillna("-")
            # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — PDF च्या Trade Log मध्ये 1M आणि 5M S/R
            # touch trades एकाच मोठ्या टेबलमध्ये मिसळण्याऐवजी, प्रत्येक Entry Timeframe साठी वेगळं,
            # स्वतःच्या ठळक heading सकट उप-टेबल (generate_performance_report_pdf त्यावरून गट करतो).
            trade_log_pdf_df["Entry Timeframe"] = trade_log_pdf_df["entry_timeframe"].where(
                trade_log_pdf_df["entry_timeframe"].notna() & (trade_log_pdf_df["entry_timeframe"] != "UNKNOWN"), "N/A",
            )
            trade_log_pdf_df = trade_log_pdf_df[[
                "Trade ID", "Entry Time", "Entry Reason", "Exit Time", "Exit Reason",
                "Exit Reason Detail", "Realized P&L", "mode", "Entry Timeframe",
            ]].rename(columns={"mode": "Mode"})

            trade_log_display = trade_log_display[[
                "Trade ID", "Entry Time", "Entry Reason", "Exit Time", "Exit Reason",
                "Exit Reason (नेमकं कारण)", "Realized P&L", "mode",
            ]].rename(columns={"mode": "Mode"})
            st.dataframe(trade_log_display, width="stretch", height=350, hide_index=True)
            trade_log_csv = trade_log_display.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Trade Log CSV डाऊनलोड करा (Entry+Exit कारणांसकट)", data=trade_log_csv,
                file_name=f"{symbol}_TradeLog_Reasons_{an_from}_{an_to}.csv",
                mime="text/csv", key="trade_log_reasons_download",
            )

        st.markdown("##### 🧭 निष्कर्ष व शिफारसी (Conclusion & Recommendations)")
        st.caption(
            "खालील शिफारसी exit_reason च्या (SL/Target/Trailing-SL/EOD) ऐतिहासिक वितरणावर आधारित, "
            "नियम-आधारित (rule-based) automated निरीक्षणं आहेत — अंतिम निर्णय (SL%/Target/Trailing-SL "
            "अंतर बदलायचं का) नेहमी तुम्हीच घ्या. सांख्यिकीयदृष्ट्या अविश्वसनीय होऊ नये म्हणून किमान 5 "
            "trades असलेलेच गट इथे विचारात घेतले आहेत."
        )
        all_recs = (
            _build_recommendations(symbol, "source", "Strategy", perf_mode_f, an_from, an_to)
            + _build_recommendations(symbol, "entry_timeframe", "Timeframe", perf_mode_f, an_from, an_to)
        )
        if not all_recs:
            st.info("या कालावधीत निष्कर्ष काढण्याइतका पुरेसा डेटा नाही (किमान 5 trades/गट हवेत).")
        else:
            for rec in all_recs:
                st.markdown(rec)

        st.markdown("---")
        st.markdown("##### 📄 संपूर्ण Performance Report (PDF)")
        st.caption(
            "वरील संपूर्ण विश्लेषण (Summary, Strategy/Timeframe breakdown, प्रत्येक Trade चं Entry+Exit कारण, शिफारसी) "
            "एकाच, प्रिंट-योग्य PDF मध्ये (इंग्रजीत — PDF fonts मध्ये मराठी glyphs उपलब्ध नाहीत). Trade Log मधल्या "
            "प्रत्येक SL/Target साठी तो नेमका Spot% मुळे, Premium Points मुळे, दोन्ही मुळे, की निव्वळ ठराविक ₹ "
            "P&L level मुळे लागला हे Exit Reason स्तंभातच कंसात दाखवलं जातं."
        )
        if st.button("📄 Performance Report PDF तयार करा", key="perf_pdf_generate"):
            with st.spinner("PDF तयार होत आहे..."):
                an_summary = get_performance_summary(symbol, mode_filter=perf_mode_f, start_date=an_from, end_date=an_to)
                _, an_pnl_totals = generate_pnl_report(symbol, "Daily", an_from, an_to, mode_filter=perf_mode_f)
                all_recs_en = (
                    _build_recommendations(symbol, "source", "Strategy", perf_mode_f, an_from, an_to, english=True)
                    + _build_recommendations(symbol, "entry_timeframe", "Timeframe", perf_mode_f, an_from, an_to, english=True)
                )
                mode_label_en = {"सर्व": "All", "फक्त LIVE": "LIVE only", "फक्त PAPER": "PAPER only"}.get(perf_mode_choice, perf_mode_choice)
                perf_pdf_bytes = generate_performance_report_pdf(
                    symbol, mode_label_en, an_from, an_to, an_summary, an_pnl_totals,
                    an_by_source, an_by_timeframe, trade_log_pdf_df, all_recs_en,
                )
            st.session_state["perf_pdf_bytes"] = perf_pdf_bytes
            st.session_state["perf_pdf_filename"] = f"{symbol}_Performance_Report_{an_from}_{an_to}.pdf"
        if st.session_state.get("perf_pdf_bytes"):
            st.download_button(
                "📥 Performance Report PDF डाऊनलोड करा", data=st.session_state["perf_pdf_bytes"],
                file_name=st.session_state.get("perf_pdf_filename", f"{symbol}_Performance_Report.pdf"),
                mime="application/pdf", key="perf_pdf_download",
            )

    st.markdown("---")
    st.subheader("📅 Daily / Weekly / Monthly P&L Report (वास्तविक ब्रोकरेज शुल्कासहित)")
    st.caption(
        "Gross P&L (बंद झालेल्या trades वरून, exit च्या तारखेनुसार) − वास्तविक ब्रोकरेज (प्रत्येक ऑर्डरनुसार — "
        "Upstox/Fyers ₹20, Shoonya ₹5 प्रति ऑर्डर; Stocko निश्चित ₹1200/महिना — वापरलेल्या महिन्यातल्या "
        "दिवसांत सम-भागांनी वाटलेला, कारण तो प्लॅन per-order नाही) = Net P&L."
    )
    rep_period = st.radio("कालावधी", ["Daily", "Weekly", "Monthly"], horizontal=True, key="pnl_report_period")
    repcol1, repcol2 = st.columns(2)
    with repcol1:
        rep_from = st.date_input(
            "पासून", value=get_ist_today() - datetime.timedelta(days=30), key="pnl_report_from",
        )
    with repcol2:
        rep_to = st.date_input("पर्यंत", value=get_ist_today(), key="pnl_report_to")

    if rep_from > rep_to:
        st.error("'पर्यंत' ही तारीख 'पासून' नंतरची असावी.")
    else:
        report_df, report_totals = generate_pnl_report(symbol, rep_period, rep_from, rep_to, mode_filter=perf_mode_f)
        if report_df.empty:
            st.info("या कालावधीत कोणतेही बंद ट्रेड्स किंवा ऑर्डर्स सापडले नाहीत.")
        else:
            rcol1, rcol2, rcol3, rcol4 = st.columns(4)
            with rcol1:
                st.metric("Gross P&L", f"₹{report_totals['gross_pnl']:,.0f}")
            with rcol2:
                st.metric("एकूण Charges", f"₹{report_totals['total_charges']:,.0f}", f"{report_totals['total_orders']} orders")
            with rcol3:
                st.metric("Net P&L", f"₹{report_totals['net_pnl']:,.0f}")
            with rcol4:
                st.metric("बंद ट्रेड्स", report_totals["total_trades"])

            if report_totals["charges_by_broker"]:
                broker_lines = " · ".join(
                    f"{b.upper()}: {v['orders']} orders / ₹{v['charge']:,.0f}"
                    for b, v in report_totals["charges_by_broker"].items()
                )
                st.caption(f"ब्रोकरनुसार: {broker_lines}")

            st.dataframe(report_df, width="stretch", hide_index=True)

            report_csv = report_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                f"📥 {rep_period} P&L Report डाऊनलोड करा (CSV)", data=report_csv,
                file_name=f"{symbol}_{rep_period}_PnL_Report_{rep_from}_{rep_to}.csv",
                mime="text/csv", key="pnl_report_download",
            )

    st.markdown("---")
    st.subheader("🔬 Signal Check (Risk:Reward आधारित — Options P&L नाही)")
    st.warning(
        "⚠️ **मर्यादा**: हे फक्त Direction Engine + Market Structure सिग्नलची ऐतिहासिक अचूकता तपासतं "
        "(walk-forward, no lookahead) — दिलेल्या SL% व Risk:Reward गुणोत्तरावरून प्रत्येक सिग्नलनंतर "
        "आधी Target लागतो की Stop-Loss, हे बघितलं जातं. प्रत्यक्ष credit spread च्या पैशांचा backtest "
        "**नाही** (जुन्या option premium चा डेटा Upstox कडून मिळत नाही), आणि यात OI-आधारित गेट्सही "
        "नाहीत (जुना OI डेटा फक्त तुम्ही app वापरायला सुरुवात केल्यापासूनच साठलाय)."
    )

    bt_style_tab1, bt_style_tab2 = st.tabs(["⚡ Intraday (15M)", "🌙 Swing (Daily)"])

    for bt_style_tab, bt_style_name, bt_interval, bt_max_days, bt_key_prefix, default_lbs in [
        (bt_style_tab1, "INTRADAY", "15minute", 180, "bti", 3),
        (bt_style_tab2, "SWING", "day", 3650, "bts", 2),
    ]:
        with bt_style_tab:
            today_d = get_ist_today()

            data_source = st.radio(
                "डेटा स्रोत",
                ["📦 खरा साठवलेला डेटा (2015-2024, स्थानिक — शिफारस केलेली)",
                 "Upstox (Token आवश्यक)", "Yahoo Finance (Token लागत नाही)"],
                horizontal=True, key=f"{bt_key_prefix}_source",
            )
            use_stored_data = "साठवलेला" in data_source
            use_yfinance = "Yahoo" in data_source
            if use_stored_data:
                if bt_interval == "day":
                    st.caption(
                        "✅ हा तुम्ही दिलेला खरा NIFTY50 डेटा आहे — दैनिक (Swing) साठी **2015-01-09 ते 2026-08-20** "
                        "(1-मिनिट भाग 2024-03-27 पर्यंत + खरा दैनिक extension त्यापुढे, खऱ्या Volume सकट) — "
                        "यापुढे सर्व backtest डीफॉल्ट याच डेटावर चालतात, कुठलाही synthetic/random डेटा नाही."
                    )
                    dataset_max_date = datetime.date(2026, 8, 20)
                else:
                    st.caption(
                        "✅ हा तुम्ही दिलेला खरा NIFTY50 डेटा आहे (2015-01-09 ते 2024-03-27, 1-मिनिट मूळ granularity) "
                        "— यापुढे सर्व backtest डीफॉल्ट याच डेटावर चालतात, कुठलाही synthetic/random डेटा नाही. "
                        "⚠️ या डेटासेटमध्ये खरा Volume नाही — VWAP साधी सरासरी (TWAP सारखी) बनते, bb_squeeze चा "
                        "volume gate अर्थहीन ठरतो."
                    )
                    dataset_max_date = datetime.date(2024, 3, 27)
                effective_max_days = 3650  # पूर्ण साठवलेला range वापरता यावा म्हणून व्यावहारिक उच्च मर्यादा
                dataset_min_date = datetime.date(2015, 1, 9)
            else:
                effective_max_days = get_yfinance_max_days(bt_interval) if use_yfinance else bt_max_days
                dataset_min_date = None
                dataset_max_date = today_d
                if use_yfinance and bt_interval != "day":
                    st.caption(
                        f"⚠️ Yahoo Finance वर 15-मिनिटांचा डेटा फक्त गेल्या ~{effective_max_days} दिवसांपुरताच उपलब्ध असतो "
                        "(Yahoo चं स्वतःचं धोरण) — त्यामुळे इथे कमाल रेंज त्यानुसार मर्यादित केलेली आहे."
                    )

            default_from = (dataset_max_date - datetime.timedelta(days=min(60, effective_max_days))) if use_stored_data else today_d - datetime.timedelta(days=min(60, effective_max_days))
            dcol1, dcol2 = st.columns(2)
            with dcol1:
                bt_from = st.date_input(
                    "पासून", value=max(default_from, dataset_min_date) if dataset_min_date else default_from,
                    min_value=dataset_min_date, max_value=dataset_max_date, key=f"{bt_key_prefix}_from",
                )
            with dcol2:
                bt_to = st.date_input(
                    "पर्यंत", value=dataset_max_date, min_value=dataset_min_date, max_value=dataset_max_date,
                    key=f"{bt_key_prefix}_to",
                )

            range_days = (bt_to - bt_from).days
            if range_days <= 0:
                st.error("'पर्यंत' ही तारीख 'पासून' नंतरची असावी.")
            elif range_days > effective_max_days:
                st.error(f"जास्तीत जास्त {effective_max_days} दिवसांची रेंज निवडता येईल (सध्या {range_days} दिवस निवडले आहेत).")
            else:
                rcol1, rcol2 = st.columns(2)
                with rcol1:
                    bt_sl_pct = st.number_input("SL % (एंट्रीपासूनचं अंतर)", min_value=0.05, value=0.5, step=0.05, key=f"{bt_key_prefix}_sl")
                with rcol2:
                    bt_rr = st.number_input("Risk:Reward गुणोत्तर", min_value=0.5, value=2.0, step=0.5, key=f"{bt_key_prefix}_rr")

                if bt_style_name == "INTRADAY":
                    st.markdown("##### 🧬 Signal Engine — दोन स्वतंत्र रणनीती (दिशा दोन्हीसाठी 1H Supertrend)")
                    strategy_choice = st.radio(
                        "कोणती रणनीती वापरायची?",
                        ["1️⃣ Price Action (Support/Resistance + RSI + Candlestick)",
                         "2️⃣ Indicator Based (RSI 25-55/45-75 + Rejection/Engulfing)"],
                        key=f"{bt_key_prefix}_strategy",
                    )
                    strategy_mode = "price_action" if "1️⃣" in strategy_choice else "indicator"

                    sr_window = 20
                    rsi_oversold = 30
                    rsi_overbought = 70
                    sl_buffer_pct = 0.1
                    min_rr = 2.0
                    retest_tolerance_pct = 0.15
                    reversal_lookback = 3
                    if strategy_mode == "price_action":
                        st.caption(
                            "Support/Resistance (Rolling Window) जवळ RSI Oversold/Overbought/Divergence + "
                            "Reversal Candlestick (Hammer/Engulfing/Morning-Evening Star) + त्या candle च्या "
                            "high/low पलीकडे Breakout — हे सर्व जुळल्यावरच Entry."
                        )
                        pacol1, pacol2, pacol3 = st.columns(3)
                        with pacol1:
                            sr_window = st.number_input("S/R Rolling Window", min_value=6, value=20, step=2, key=f"{bt_key_prefix}_srwin")
                        with pacol2:
                            rsi_oversold = st.number_input("RSI Oversold <", min_value=5, max_value=45, value=30, step=1, key=f"{bt_key_prefix}_rsios")
                        with pacol3:
                            rsi_overbought = st.number_input("RSI Overbought >", min_value=55, max_value=95, value=70, step=1, key=f"{bt_key_prefix}_rsiob")
                        pacol4, pacol5, pacol6 = st.columns(3)
                        with pacol4:
                            sl_buffer_pct = st.number_input("SL Buffer %", min_value=0.01, value=0.1, step=0.05, key=f"{bt_key_prefix}_slbuf")
                        with pacol5:
                            min_rr = st.number_input("किमान Risk:Reward", min_value=1.0, value=2.0, step=0.5, key=f"{bt_key_prefix}_minrr")
                        with pacol6:
                            retest_tolerance_pct = st.number_input("Retest Tolerance %", min_value=0.05, value=0.15, step=0.05, key=f"{bt_key_prefix}_rtol")
                        reversal_lookback = st.number_input("Reversal Candle Lookback (bars)", min_value=1, max_value=10, value=3, step=1, key=f"{bt_key_prefix}_revlb")
                        slippage_pct = st.number_input(
                            "Slippage % (आर्थिक वास्तवता — प्रत्येक बाजूला, 0=बंद)", min_value=0.0, value=0.0, step=0.01,
                            key=f"{bt_key_prefix}_slip",
                            help="Bid-Ask Spread + Market Impact मुळे प्रत्यक्ष fill किंमत LTP पेक्षा किंचित वाईट असते — व्यापाऱ्याच्याच विरोधात.",
                        )
                        st.caption(
                            "S/R Rolling Window कमी असेल तर जास्त (पण कमी विश्वासार्ह) पातळ्या सापडतील. "
                            "Funnel मध्ये सिग्नल्स कमी दिसत असतील तर Retest Tolerance वाढवा किंवा RSI मर्यादा सैल करा."
                        )

                    if st.button(f"🔍 {range_days} दिवसांत किती सिग्नल्स आले ते तपासा", key=f"{bt_key_prefix}_run"):
                        yf_error = None
                        with st.spinner(f"{bt_from} ते {bt_to} चा {bt_interval} + 1H डेटा फेच करून तपासत आहे..."):
                            if use_stored_data:
                                from real_nifty_data import load_nifty_resampled
                                bt_df_range = load_nifty_resampled(15, bt_from, bt_to)
                                bt_df_1h = load_nifty_resampled(60, bt_from, bt_to)
                            elif use_yfinance:
                                bt_df_range, yf_err1 = fetch_yfinance_candles(symbol, bt_interval, bt_from, bt_to)
                                bt_df_1h, yf_err2 = fetch_yfinance_candles(symbol, "hour", bt_from, bt_to)
                                yf_error = yf_err1 or yf_err2
                            else:
                                bt_df_range = fetch_candles_date_range(token_input, symbol, bt_interval, bt_from, bt_to)
                                bt_df_1h_raw = fetch_candles_date_range(token_input, symbol, "30minute", bt_from, bt_to)
                                bt_df_1h = resample_to_1h(bt_df_1h_raw) if not bt_df_1h_raw.empty else bt_df_1h_raw

                            bt_result_range = run_signal_backtest_v2(
                                bt_df_range, bt_df_1h, strategy=strategy_mode, sl_pct=bt_sl_pct, rr_ratio=bt_rr,
                                max_bars=None, max_hold_bars=50,
                                sr_window=sr_window, rsi_oversold=rsi_oversold, rsi_overbought=rsi_overbought,
                                sl_buffer_pct=sl_buffer_pct, min_rr=min_rr,
                                retest_tolerance_pct=retest_tolerance_pct, reversal_lookback=reversal_lookback,
                                slippage_pct=slippage_pct,
                            )
                        if bt_df_range.empty or bt_df_1h.empty:
                            if yf_error:
                                st.error(f"❌ Yahoo Finance वरून डेटा मिळाला नाही — नेमकं कारण:\n\n{yf_error}")
                            else:
                                st.error(
                                    "❌ कोणताही डेटा मिळाला नाही (15M किंवा 1H) — " +
                                    ("Yahoo Finance वरून (नेटवर्क/चुकीचा सिम्बॉल तपासा)." if use_yfinance else "Upstox token तपासा.")
                                )
                        st.session_state[f"{bt_key_prefix}_df"] = bt_df_range
                        st.session_state[f"{bt_key_prefix}_result"] = bt_result_range
                        st.session_state[f"{bt_key_prefix}_meta"] = (bt_from, bt_to, bt_interval, bt_sl_pct, bt_rr)
                        st.session_state[f"{bt_key_prefix}_v2"] = True
                        st.session_state[f"{bt_key_prefix}_strategy_mode"] = strategy_mode
                        st.session_state[f"{bt_key_prefix}_ob_params"] = {
                            "sr_window": sr_window, "rsi_oversold": rsi_oversold, "rsi_overbought": rsi_overbought,
                            "sl_buffer_pct": sl_buffer_pct, "min_rr": min_rr,
                        }

                    if f"{bt_key_prefix}_result" in st.session_state and st.session_state.get(f"{bt_key_prefix}_v2"):
                        r_df = st.session_state[f"{bt_key_prefix}_df"]
                        r_result = st.session_state[f"{bt_key_prefix}_result"]
                        r_from, r_to, r_interval, r_sl, r_rr = st.session_state[f"{bt_key_prefix}_meta"]

                        funnel = r_result.get("funnel", {})
                        if r_result["total"] == 0:
                            st.info(f"📭 {r_from} ते {r_to} या कालावधीत कोणतेही सिग्नल्स सापडले नाहीत.")
                        else:
                            st.success(f"✅ {r_from} ते {r_to} या कालावधीत {r_result['total']} सिग्नल्स सापडले.")

                        if funnel:
                            st.markdown("##### 🔍 Funnel Diagnostic")
                            fc1, fc2, fc3 = st.columns(3)
                            with fc1:
                                st.metric("तपासलेले Bars", funnel["bars_checked"])
                            with fc2:
                                pct = f"{funnel['structure_directional']/funnel['bars_checked']*100:.0f}%" if funnel["bars_checked"] else "0%"
                                st.metric("1H दिशा उपलब्ध", funnel["structure_directional"], pct)
                            with fc3:
                                pct2 = f"{funnel['entry_passed']/funnel['structure_directional']*100:.1f}%" if funnel["structure_directional"] else "N/A"
                                st.metric("Entry जुळले", funnel["entry_passed"], pct2)

                        if r_result["total"] > 0:
                            mcol1, mcol2, mcol3, mcol4, mcol5 = st.columns(5)
                            with mcol1:
                                st.metric("एकूण सिग्नल्स", r_result["total"])
                            with mcol2:
                                win_rate_str = f"{r_result['win_rate']}%" if r_result["win_rate"] is not None else "N/A"
                                st.metric("Win Rate", win_rate_str)
                            with mcol3:
                                st.metric("Target / SL", f"{r_result['target_count']} / {r_result['sl_count']}")
                            with mcol4:
                                st.metric("अजून Open", r_result["open_count"])
                            with mcol5:
                                total_pnl = r_result.get("total_pnl_points")
                                pnl_display = f"{total_pnl:+,.1f}" if total_pnl is not None else "N/A"
                                st.metric("एकूण P&L (पॉइंट्स)", pnl_display)
                            st.caption("⚠️ P&L हा index किमतीतल्या पॉइंट्स-अंतरावर आधारित आहे — खरा Option Premium P&L नाही (तो पेक्षा वेगळा असू शकतो).")
                            sig_display_df = pd.DataFrame(r_result["signals"]).rename(columns={"pnl_points": "P&L (Points)"})
                            st.dataframe(sig_display_df, width="stretch", height=250)

                            if st.button("📄 Backtest PDF Report तयार करा", key=f"{bt_key_prefix}_pdf_v2"):
                                with st.spinner("PDF तयार होत आहे..."):
                                    saved_strategy_mode = st.session_state.get(f"{bt_key_prefix}_strategy_mode", "indicator")
                                    saved_ob_params = st.session_state.get(f"{bt_key_prefix}_ob_params", {})
                                    clean_strategy_name = "Price Action" if saved_strategy_mode == "price_action" else "Indicator Based"
                                    bt_pdf_bytes = generate_backtest_report_pdf_v2(
                                        symbol, clean_strategy_name, r_interval, r_from, r_to, r_sl, r_rr,
                                        saved_ob_params, r_df, r_result,
                                    )
                                bt_filename = f"A1_Backtest_{clean_strategy_name.replace(' ', '')}_{symbol}_{get_ist_now().strftime('%Y%m%d_%H%M%S')}.pdf"
                                st.download_button(
                                    "📥 Download Backtest PDF Report", data=bt_pdf_bytes,
                                    file_name=bt_filename, mime="application/pdf", key=f"{bt_key_prefix}_dl_v2",
                                )
                                st.success("✅ रिपोर्ट तयार झाला — वरील बटणावर क्लिक करून डाऊनलोड करा.")
                else:
                    bt_lookback_swings = st.slider(
                        "Structure Lookback Swings (कमी = जास्त सिग्नल्स)", min_value=2, max_value=5,
                        value=default_lbs, key=f"{bt_key_prefix}_lbs",
                    )
                    bt_tolerance = st.number_input(
                        "Pullback/Retest Tolerance %", min_value=0.1, value=0.4, step=0.1, key=f"{bt_key_prefix}_tol",
                    )

                    if st.button(f"🔍 {range_days} दिवसांत किती सिग्नल्स आले ते तपासा", key=f"{bt_key_prefix}_run"):
                        yf_error = None
                        with st.spinner(f"{bt_from} ते {bt_to} चा {bt_interval} डेटा फेच करून तपासत आहे..."):
                            if use_stored_data:
                                from real_nifty_data import load_nifty_resampled
                                bt_df_range = load_nifty_resampled("day", bt_from, bt_to)
                            elif use_yfinance:
                                bt_df_range, yf_error = fetch_yfinance_candles(symbol, bt_interval, bt_from, bt_to)
                            else:
                                bt_df_range = fetch_candles_date_range(token_input, symbol, bt_interval, bt_from, bt_to)
                            bt_result_range = run_signal_backtest_rr(
                                bt_df_range, sl_pct=bt_sl_pct, rr_ratio=bt_rr,
                                lookback_swings=bt_lookback_swings, tolerance_pct=bt_tolerance, max_bars=None,
                                max_hold_bars=20,
                            )
                        if bt_df_range.empty:
                            if yf_error:
                                st.error(f"❌ Yahoo Finance वरून डेटा मिळाला नाही — नेमकं कारण:\n\n{yf_error}")
                            else:
                                st.error(
                                    "❌ कोणताही डेटा मिळाला नाही — " +
                                    ("Yahoo Finance वरून (नेटवर्क/चुकीचा सिम्बॉल तपासा)." if use_yfinance else "Upstox token तपासा.")
                                )
                        st.session_state[f"{bt_key_prefix}_df"] = bt_df_range
                        st.session_state[f"{bt_key_prefix}_result"] = bt_result_range
                        st.session_state[f"{bt_key_prefix}_meta"] = (bt_from, bt_to, bt_interval, bt_sl_pct, bt_rr)
                        st.session_state[f"{bt_key_prefix}_v2"] = False

                    if f"{bt_key_prefix}_result" in st.session_state and not st.session_state.get(f"{bt_key_prefix}_v2", True):
                        r_df = st.session_state[f"{bt_key_prefix}_df"]
                        r_result = st.session_state[f"{bt_key_prefix}_result"]
                        r_from, r_to, r_interval, r_sl, r_rr = st.session_state[f"{bt_key_prefix}_meta"]

                        funnel = r_result.get("funnel", {})
                        breakdown = r_result.get("structure_breakdown", {})

                        if r_result["total"] == 0:
                            st.info(f"📭 {r_from} ते {r_to} या कालावधीत ({r_interval}, {bt_style_name}) कोणतेही सिग्नल्स सापडले नाहीत.")
                            st.caption(
                                "याचा अर्थ: या कालावधीत Break + Pullback + Retest ही सगळी परिस्थिती एकत्र कधीच जुळली नाही. "
                                "खाली नेमकं कोणत्या टप्प्यावर अडलं ते बघा (अंदाज नाही, प्रत्यक्ष आकडे)."
                            )

                        if funnel:
                            st.markdown("##### 🔍 Funnel Diagnostic — नेमकं कुठे अडतंय?")
                            fcol1, fcol2, fcol3, fcol4 = st.columns(4)
                            with fcol1:
                                st.metric("तपासलेले Bars", funnel["bars_checked"])
                            with fcol2:
                                pct = f"{funnel['structure_directional']/funnel['bars_checked']*100:.0f}%" if funnel["bars_checked"] else "0%"
                                st.metric("Directional Structure", funnel["structure_directional"], pct)
                            with fcol3:
                                pct2 = f"{funnel['broke']/funnel['structure_directional']*100:.0f}%" if funnel["structure_directional"] else "N/A"
                                st.metric("त्यातले Break झालेले", funnel["broke"], pct2)
                            with fcol4:
                                pct3 = f"{funnel['pulled_back_and_retested']/funnel['broke']*100:.0f}%" if funnel["broke"] else "N/A"
                                st.metric("Pullback+Retest जुळलेले", funnel["pulled_back_and_retested"], pct3)

                            if breakdown:
                                st.caption(
                                    f"Structure breakdown — HH/HL (तेजी): {breakdown.get('HH/HL',0)} · "
                                    f"LH/LL (मंदी): {breakdown.get('LH/LL',0)} · "
                                    f"RANGING/MIXED: {breakdown.get('RANGING_or_MIXED',0)} · "
                                    f"अपुरा डेटा: {breakdown.get('INSUFFICIENT_DATA',0)}"
                                )
                            if funnel["bars_checked"] > 0 and funnel["structure_directional"] / funnel["bars_checked"] < 0.15:
                                st.warning(
                                    "⚠️ बहुतांश वेळ बाजार RANGING/MIXED दिसतोय (Directional Structure फार कमी वेळा जुळतंय) — "
                                    "structure_order किंवा lookback_swings कमी केल्यास जास्त संधी मिळू शकतात."
                                )

                        if r_result["total"] > 0:
                            st.success(f"✅ {r_from} ते {r_to} या कालावधीत {r_result['total']} सिग्नल्स सापडले.")
                            mcol1, mcol2, mcol3, mcol4, mcol5 = st.columns(5)
                            with mcol1:
                                st.metric("एकूण सिग्नल्स", r_result["total"])
                            with mcol2:
                                win_rate_str = f"{r_result['win_rate']}%" if r_result["win_rate"] is not None else "N/A"
                                st.metric("Win Rate (Target vs SL)", win_rate_str)
                            with mcol3:
                                st.metric("Target / SL", f"{r_result['target_count']} / {r_result['sl_count']}")
                            with mcol4:
                                st.metric("अजून Open", r_result["open_count"])
                            with mcol5:
                                total_pnl = r_result.get("total_pnl_points")
                                pnl_display = f"{total_pnl:+,.1f}" if total_pnl is not None else "N/A"
                                st.metric("एकूण P&L (पॉइंट्स)", pnl_display)
                            st.caption("⚠️ P&L हा index किमतीतल्या पॉइंट्स-अंतरावर आधारित आहे — खरा Option Premium P&L नाही.")
                            sig_display_df = pd.DataFrame(r_result["signals"]).rename(columns={"pnl_points": "P&L (Points)"})
                            st.dataframe(sig_display_df, width="stretch", height=250)

                            if st.button("📄 Backtest PDF Report तयार करा", key=f"{bt_key_prefix}_pdf"):
                                with st.spinner("PDF तयार होत आहे..."):
                                    bt_pdf_bytes = generate_backtest_report_pdf_rr(
                                        symbol, bt_style_name, r_interval, r_from, r_to, r_sl, r_rr, r_df, r_result,
                                    )
                                bt_filename = f"A1_Backtest_{bt_style_name}_{symbol}_{get_ist_now().strftime('%Y%m%d_%H%M%S')}.pdf"
                                st.download_button(
                                    "📥 Download Backtest PDF Report", data=bt_pdf_bytes,
                                    file_name=bt_filename, mime="application/pdf", key=f"{bt_key_prefix}_dl",
                                )
                                st.success("✅ रिपोर्ट तयार झाला — वरील बटणावर क्लिक करून डाऊनलोड करा.")


    # =========================================================
    # नवीन — Multi-Strategy Orchestrator Backtest (ict_fvg, bb_squeeze, vwap)
    # जुन्या A1 Engine backtest पासून पूर्णपणे स्वतंत्र. oi_pcr इथे नाही (ऐतिहासिक Option OI
    # डेटा उपलब्ध नाही, त्यामुळे ती रणनीती backtest मध्ये कधीच चालवता येत नाही).
    # =========================================================
    st.markdown("---")
    st.subheader("🧩 Multi-Strategy Orchestrator Backtest (नवीन, प्रयोगिक)")
    st.caption(
        "फक्त futures_ohlcv वापरणाऱ्या रणनीती: ict_fvg, bb_squeeze, vwap. "
        "oi_pcr इथे चालत नाही — तिला ऐतिहासिक प्रत्येक-क्षणाचा Option OI इतिहास लागतो, जो साठवलेला नाही."
    )
    ms_symbol = st.session_state.get("symbol", "NIFTY")
    ms_style = st.radio("Trading Style", ["Intraday (15M, EOD square-off)", "Swing (Daily, EOD नाही — SL/Target लागेपर्यंत उघडं)"], key="ms_bt_style")
    ms_is_intraday = "Intraday" in ms_style
    ms_data_source = st.radio(
        "डेटा स्रोत",
        ["📦 खरा साठवलेला डेटा (2015-2024, स्थानिक — शिफारस केलेली)",
         "Upstox (Token आवश्यक)", "Yahoo Finance (Token लागत नाही)"],
        horizontal=True, key="ms_bt_source",
    )
    ms_use_stored_data = "साठवलेला" in ms_data_source
    ms_use_yfinance = "Yahoo" in ms_data_source
    if ms_use_stored_data:
        if ms_is_intraday:
            st.caption(
                "✅ खरा NIFTY50 डेटा (2015-01-09 ते 2024-03-27, 1-मिनिट) — synthetic नाही. ⚠️ यात खरा Volume "
                "नाही, त्यामुळे vwap साधी सरासरी बनते, bb_squeeze चा volume gate अर्थहीन ठरतो."
            )
            ms_min_date, ms_max_date = datetime.date(2015, 1, 9), datetime.date(2024, 3, 27)
        else:
            st.caption(
                "✅ खरा NIFTY50 दैनिक डेटा — **2015-01-09 ते 2026-08-20** (1-मिनिट भाग 2024-03-27 पर्यंत + खरा "
                "दैनिक extension त्यापुढे, खऱ्या Volume सकट) — synthetic नाही."
            )
            ms_min_date, ms_max_date = datetime.date(2015, 1, 9), datetime.date(2026, 8, 20)
    else:
        ms_min_date, ms_max_date = None, get_ist_today()
    ms_from = st.date_input(
        "पासून तारीख", value=(ms_max_date - datetime.timedelta(days=15)) if ms_use_stored_data else get_ist_today() - datetime.timedelta(days=15),
        min_value=ms_min_date, max_value=ms_max_date, key="ms_bt_from",
    )
    ms_to = st.date_input("पर्यंत तारीख", value=ms_max_date, min_value=ms_min_date, max_value=ms_max_date, key="ms_bt_to")
    ms_strategy_choice = st.selectbox("कोणती रणनीती?", ["vwap", "bb_squeeze", "ict_fvg"], key="ms_bt_strategy")

    st.markdown("##### 🎯 SL/Target स्वतः ठरवा (पॉइंट्स — Strategy च्या स्वतःच्या auto गणनेऐवजी)")
    ms_default_sl_target = {"vwap": (25, 40), "bb_squeeze": (40, 80), "ict_fvg": (30, 60)}
    ms_def_sl, ms_def_target = ms_default_sl_target.get(ms_strategy_choice, (40, 80))
    mscol1, mscol2 = st.columns(2)
    with mscol1:
        ms_sl_points = st.number_input("SL (पॉइंट्स)", min_value=1, value=ms_def_sl, step=1, key=f"ms_bt_sl_{ms_strategy_choice}")
    with mscol2:
        ms_target_points = st.number_input("Target (पॉइंट्स)", min_value=1, value=ms_def_target, step=1, key=f"ms_bt_target_{ms_strategy_choice}")

    if st.button("🔍 Multi-Strategy Backtest चालवा", key="ms_bt_run"):
        yf_error = None
        ms_data_interval = 15 if ms_is_intraday else "day"
        with st.spinner("डेटा फेच करून backtest चालवत आहे..."):
            if ms_use_stored_data:
                from real_nifty_data import load_nifty_resampled
                ms_df_raw = load_nifty_resampled(ms_data_interval, ms_from, ms_to)
            elif ms_use_yfinance:
                ms_df_raw, yf_error = fetch_yfinance_candles(ms_symbol, "15minute" if ms_is_intraday else "day", ms_from, ms_to)
            else:
                ms_token = st.session_state.get("token_input", "")
                ms_df_raw = fetch_candles_date_range(ms_token, ms_symbol, "15minute" if ms_is_intraday else "day", ms_from, ms_to)

            if ms_df_raw is None or ms_df_raw.empty:
                if yf_error:
                    st.error(f"❌ डेटा मिळाला नाही — नेमकं कारण:\n\n{yf_error}")
                else:
                    st.error("❌ कोणताही डेटा मिळाला नाही — Token किंवा तारीख-रेंज तपासा.")
            else:
                try:
                    from market_data_adapter import prepare_futures_ohlcv
                    from multi_strategy_backtest import run_strategy_backtest
                    from strategies import STRATEGY_REGISTRY
                    import yaml

                    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
                    with open(config_path, "r", encoding="utf-8") as f:
                        full_cfg = yaml.safe_load(f)
                    strat_cfg = full_cfg.get("strategies", {}).get(ms_strategy_choice, {})
                    strat_cls = STRATEGY_REGISTRY[ms_strategy_choice]
                    strat_obj = strat_cls(config=strat_cfg)

                    ms_df_prepared = prepare_futures_ohlcv(ms_df_raw)

                    ms_df_1h = None
                    if ms_strategy_choice == "vwap" and ms_is_intraday:
                        if ms_use_stored_data:
                            ms_df_1h = load_nifty_resampled(60, ms_from, ms_to)
                        elif ms_use_yfinance:
                            ms_df_1h, _ = fetch_yfinance_candles(ms_symbol, "hour", ms_from, ms_to)
                        else:
                            ms_df_1h_raw = fetch_candles_date_range(ms_token, ms_symbol, "30minute", ms_from, ms_to)
                            ms_df_1h = resample_to_1h(ms_df_1h_raw) if not ms_df_1h_raw.empty else ms_df_1h_raw

                    ms_result = run_strategy_backtest(
                        ms_df_prepared, strat_obj, df_1h=ms_df_1h,
                        min_lookback=30, max_hold_bars=(50 if ms_is_intraday else 30),
                        is_intraday=ms_is_intraday,
                        sl_points=ms_sl_points, target_points=ms_target_points,
                    )

                    st.success(f"✅ {ms_result['total']} सिग्नल्स सापडले (Funnel: {ms_result['funnel']})")
                    if ms_result["total"] > 0:
                        mscol1, mscol2, mscol3, mscol4 = st.columns(4)
                        with mscol1:
                            st.metric("एकूण सिग्नल्स", ms_result["total"])
                        with mscol2:
                            wr = f"{ms_result['win_rate']}%" if ms_result.get("win_rate") is not None else "N/A"
                            st.metric("Win Rate", wr)
                        with mscol3:
                            st.metric("Target / SL", f"{ms_result['target_count']} / {ms_result['sl_count']}")
                        with mscol4:
                            ms_total_pnl = ms_result.get("total_pnl_points")
                            ms_pnl_display = f"{ms_total_pnl:+,.1f}" if ms_total_pnl is not None else "N/A"
                            st.metric("एकूण P&L (पॉइंट्स)", ms_pnl_display)
                        st.caption("⚠️ P&L हा index किमतीतल्या पॉइंट्स-अंतरावर आधारित आहे — खरा Option Premium P&L नाही.")
                        ms_sig_display_df = pd.DataFrame(ms_result["signals"]).rename(columns={"pnl_points": "P&L (Points)"})
                        st.dataframe(ms_sig_display_df, width="stretch", height=300)
                except ModuleNotFoundError as e:
                    st.error(
                        f"चूक: {type(e).__name__}: {e}\n\n"
                        "**बहुतेक कारण**: `strategies/` फोल्डर किंवा `config.yaml` तुमच्या repo मध्ये गहाळ आहेत."
                    )
                except Exception as e:
                    st.error(f"Multi-Strategy Backtest मध्ये चूक: {type(e).__name__}: {e}")
