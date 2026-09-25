"""
tests/test_pdf_reports.py
--------------------------------
🎓 वापरकर्त्याने विचारलेली तक्रार ("charges खूप जास्त वाटतायत, कशाचं बनलंय दाखवा") — Performance
Report PDF च्या Summary मध्ये आता "Total Charges" सोबत order-संख्या आणि brokerage/STT/Exchange/
SEBI/Stamp/GST चा ब्रेकडाऊनही दाखवला जातो (आधी फक्त एक निव्वळ बेरीज होती). लांब ब्रेकडाऊन-ओळ Table
column च्या रुंदीबाहेर overflow होऊ नये म्हणून Paragraph मध्ये wrap करून दिली आहे -- ती अजिबात न
दाखवल्यास/चुकीच्या प्रकाराने दिल्यास PDF तयार होताना क्रॅश होईल, हेच इथे पडताळलं आहे.
"""
from unittest.mock import patch

import pandas as pd
from reportlab.platypus import Paragraph

from pdf_reports import (
    _fix_missing_glyphs, _rpt_kv_wrap, build_trade_entry_exit_chart_image,
    df_to_reportlab_table, generate_performance_report_pdf,
)

_SUMMARY = {
    "total_trades": 20, "win_rate": 31.2, "win_rate_all_exits": 30.0,
    "roi_pct": 0.17, "margin_used": 515239.0, "total_pnl": 878, "avg_pnl": 44,
    "best_trade": 3932, "worst_trade": -2486, "profit_factor": 1.05,
}


class TestGeneratePerformanceReportPdfChargesBreakdown:
    def test_with_charges_breakdown_produces_valid_pdf(self):
        pnl_totals = {
            "gross_pnl": 878, "total_charges": 4490, "net_pnl": -3613, "total_orders": 80,
            "charges_breakdown": {
                "brokerage": 1600, "stt": 320, "exchange_txn": 280,
                "sebi_fee": 5, "stamp_duty": 15, "gst": 400,
            },
        }
        pdf_bytes = generate_performance_report_pdf(
            "NIFTY", "All", "2026-09-17", "2026-09-18", _SUMMARY, pnl_totals,
            None, None, None, None, [],
        )
        assert pdf_bytes[:4] == b"%PDF"
        assert len(pdf_bytes) > 1000

    def test_without_charges_breakdown_still_works(self):
        """जुन्या callers कडून charges_breakdown/total_orders नसतील (किंवा शुल्कच शून्य असेल)
        तरी क्रॅश होता कामा नये -- फक्त तो ब्रेकडाऊन-ओळ गाळली जाते."""
        pnl_totals = {"gross_pnl": 400, "total_charges": 0, "net_pnl": 400}
        pdf_bytes = generate_performance_report_pdf(
            "NIFTY", "All", "2026-09-01", "2026-09-05", _SUMMARY, pnl_totals,
            None, None, None, None, [],
        )
        assert pdf_bytes[:4] == b"%PDF"

    def test_zero_trades_no_crash(self):
        pdf_bytes = generate_performance_report_pdf(
            "NIFTY", "All", "2026-09-01", "2026-09-05", {"total_trades": 0},
            {"gross_pnl": 0, "total_charges": 0, "net_pnl": 0}, None, None, None, None, [],
        )
        assert pdf_bytes[:4] == b"%PDF"


class TestGeneratePerformanceReportPdfBrokerWiseCharges:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा ("Performance report मध्ये या सर्व ब्रोकर नुसार charges
    साठी एक table टाका, कोणता ब्रोकर परवडण्याजोगा आहे") — Broker-wise Charges section.
    🎓 वापरकर्त्याने निदर्शनास आणलेली त्रुटी ("सर्व ब्रोकरचा तुलनात्मक तक्ता आपण दिलेला नाही, फक्त
    Upstox चा दिलेला आहे") — pnl_totals ची key आता charges_by_broker (प्रत्यक्ष वापरलेल्या
    ब्रोकरनुसार) ऐवजी charges_by_broker_comparison (hypothetical, सर्व ब्रोकरसाठी)."""

    def test_multi_broker_charges_produces_valid_pdf(self):
        pnl_totals = {
            "gross_pnl": 878, "total_charges": 4490, "net_pnl": -3613, "total_orders": 80,
            "charges_by_broker_comparison": {
                "upstox": {"orders": 40, "charge": 2200.0},
                "fyers": {"orders": 40, "charge": 1950.0},
                "shoonya": {"orders": 40, "charge": 620.0},
                "stocko": {"orders": 40, "charge": 1420.0},
            },
        }
        pdf_bytes = generate_performance_report_pdf(
            "NIFTY", "All", "2026-09-17", "2026-09-18", _SUMMARY, pnl_totals,
            None, None, None, None, [],
        )
        assert pdf_bytes[:4] == b"%PDF"
        assert len(pdf_bytes) > 1000

    def test_without_charges_by_broker_still_works(self):
        """charges_by_broker_comparison key नसेल (जुना caller, किंवा या कालावधीत कुठलेही orders
        नाहीत) तरी क्रॅश होता कामा नये -- फक्त हा संपूर्ण section गाळला जातो."""
        pnl_totals = {"gross_pnl": 400, "total_charges": 0, "net_pnl": 400, "charges_by_broker_comparison": {}}
        pdf_bytes = generate_performance_report_pdf(
            "NIFTY", "All", "2026-09-01", "2026-09-05", _SUMMARY, pnl_totals,
            None, None, None, None, [],
        )
        assert pdf_bytes[:4] == b"%PDF"


class TestFixMissingGlyphsNonString:
    """🎓 वापरकर्त्याने सापडवलेली bug (PDF generation क्रॅश — AttributeError: 'float' object has no
    attribute 'replace', pdf_reports.py:611) — df.astype(str) पांडासमध्ये फक्त non-NaN सेल्स स्ट्रिंग
    बनवतं, NaN float('nan') म्हणूनच राहतं — तेच पुढे xml escape ला जाऊन क्रॅश व्हायचं.
    🎓 वापरकर्त्याने सापडवलेली regression (पहिल्या फिक्सचीच, CRUDEOIL Performance Report PDF मध्ये) —
    (1) "Charges Breakdown" ओळीतला Paragraph object raw Python repr म्हणून छापला गेला (आधीचा फिक्स
    सरसकट सर्व non-string इनपुटला str() लावायचा — Paragraph सकट), आणि (2) एकही शुद्ध SL/Target trade
    नसलेल्या group चा "Win Rate %" literal "nan"/"None" म्हणून दिसायचा (Dashboard वर आधीच "N/A" असतं,
    PDF मध्ये कधीच नव्हतं). आता दोन्ही फिक्स — NaN/None "N/A" दाखवतात, Paragraph सारखे flowables
    जसेच्या तसे राहतात."""

    def test_nan_float_becomes_na_string(self):
        assert _fix_missing_glyphs(float("nan")) == "N/A"

    def test_none_becomes_na_string(self):
        assert _fix_missing_glyphs(None) == "N/A"

    def test_regular_float_becomes_plain_string(self):
        assert _fix_missing_glyphs(3.5) == "3.5"

    def test_regular_string_unaffected(self):
        assert _fix_missing_glyphs("hello") == "hello"

    def test_paragraph_object_passes_through_unchanged(self):
        """Charges Breakdown ओळीत _kv_table() मुद्दामच Paragraph cell values पाठवतं (लांब मजकूर
        wrap व्हावा म्हणून) — _fix_missing_glyphs() ने ते बदलता/स्ट्रिंगमध्ये convert करता कामा नयेत."""
        para = Paragraph("Brokerage Rs 100", _rpt_kv_wrap)
        assert _fix_missing_glyphs(para) is para


class TestGeneratePerformanceReportPdfOvershootDf:
    """overshoot_df मध्ये NaN सेल्स (उदा. Fixed-Rs strategy trades साठी Overshoot % रिकामं) असल्यावरही
    PDF क्रॅश होता कामा नये — आधी `_wide_df_table_wrapped()` मध्ये हेच क्रॅश व्हायचं."""

    def test_overshoot_df_with_nan_cells_does_not_crash(self):
        overshoot_df = pd.DataFrame([
            {"Trade ID": "T1", "Exit Time": "2026-09-24 11:00:00", "Exit Reason": "SL",
             "Basis": "Fixed Rs", "Overshoot (pts)": None, "Overshoot (%)": None,
             "Overshoot (Rs)": 150.0, "Realized P&L": -1500.0, "Mode": "LIVE"},
            {"Trade ID": "T2", "Exit Time": "2026-09-24 11:05:00", "Exit Reason": "TRAILING_SL",
             "Basis": "Spot %", "Overshoot (pts)": 1.5, "Overshoot (%)": 0.05,
             "Overshoot (Rs)": None, "Realized P&L": 800.0, "Mode": "LIVE"},
        ])
        pdf_bytes = generate_performance_report_pdf(
            "NIFTY", "All", "2026-09-24", "2026-09-24", _SUMMARY,
            {"gross_pnl": -700, "total_charges": 0, "net_pnl": -700},
            None, None, None, None, [], overshoot_df=overshoot_df,
        )
        assert pdf_bytes[:4] == b"%PDF"


class TestGeneratePerformanceReportPdfCrudeoilRegression:
    """🎓 वापरकर्त्याने अपलोड केलेल्या खऱ्या CRUDEOIL PDF मध्ये सापडवलेल्या दोन्ही bugs (एकाच वेळी) —
    (1) Charges Breakdown ओळीत Paragraph चा raw repr, (2) एकही शुद्ध SL/Target trade नसलेल्या group
    (दोन्ही trades Trailing SL ने बंद) चा Win Rate % literal "nan" — दोन्ही एकत्र reproduce करून
    फिक्स झाल्याची खात्री."""

    def test_by_source_df_win_rate_none_shows_na_not_nan(self):
        by_source_df = pd.DataFrame([
            {"Group": "mcx_futures", "Trades": 2, "Win Rate %": None, "SL/Target Trades": 0,
             "Win Rate % (All Exits)": 0.0, "ROI %": -0.01, "Total P&L": -3800.0, "Avg P&L": -1900.0},
        ])
        tbl = df_to_reportlab_table(by_source_df)
        # Header row + 1 data row; columns are Group/Trades/Win Rate %/... — "Win Rate %" is index 2.
        assert tbl._cellvalues[1][2] == "N/A"
        assert "nan" not in str(tbl._cellvalues[1][2]).lower()

    def test_charges_breakdown_with_nan_win_rate_group_does_not_crash(self):
        pnl_totals = {
            "gross_pnl": -3800, "total_charges": 100, "net_pnl": -3900, "total_orders": 4,
            "charges_breakdown": {"brokerage": 100, "stt": 0, "exchange_txn": 0, "sebi_fee": 0, "stamp_duty": 0, "gst": 0},
        }
        by_source_df = pd.DataFrame([
            {"Group": "mcx_futures", "Trades": 2, "Win Rate %": None, "SL/Target Trades": 0,
             "Win Rate % (All Exits)": 0.0, "ROI %": -0.01, "Total P&L": -3800.0, "Avg P&L": -1900.0},
        ])
        pdf_bytes = generate_performance_report_pdf(
            "CRUDEOIL", "All", "2026-09-24", "2026-09-24",
            {"total_trades": 2, "win_rate": None, "win_rate_all_exits": 0.0, "roi_pct": -0.01,
             "margin_used": 27612125.0, "total_pnl": -3800, "avg_pnl": -1900,
             "best_trade": -1800, "worst_trade": -2000, "profit_factor": 0.0},
            pnl_totals, by_source_df, by_source_df, by_source_df, None, [],
        )
        assert pdf_bytes[:4] == b"%PDF"


class TestGeneratePerformanceReportPdfTradeLogLegsColumn:
    """🎓 वापरकर्त्याने स्पष्टपणे मागितलेली सुधारणा ("actual strike price, entry price, exit price
    Performance Report मध्ये दिसायला हवं") — नवीन "Legs (Strike/Entry/Exit Price)" स्तंभासकट Trade Log
    (आणि त्यातला एक None cell, जुन्या legs_json नसलेल्या trades साठी) क्रॅश न होता render होतो का."""

    def test_trade_log_with_legs_column_and_none_cell_does_not_crash(self):
        trade_log_df = pd.DataFrame([
            {"Trade ID": "T1", "Entry Time": "2026-09-24 10:00:00", "Entry Reason": "dynamic_sr_instant - 5M S/R level",
             "Legs (Strike/Entry/Exit Price)": "short_leg 24400PE (SELL) Entry ₹38.00 → Exit ₹15.00",
             "Exit Time": "2026-09-24 14:00:00", "Exit Reason": "Target", "Exit Reason Detail": "Target hit",
             "Realized P&L": 500.0, "Mode": "PAPER", "Entry Timeframe": "5M"},
            {"Trade ID": "T2", "Entry Time": "2026-09-24 11:00:00", "Entry Reason": "dynamic_sr_instant - 5M S/R level",
             "Legs (Strike/Entry/Exit Price)": "N/A",  # जुना trade, legs_json शिवाय
             "Exit Time": "2026-09-24 12:00:00", "Exit Reason": "SL", "Exit Reason Detail": "SL hit",
             "Realized P&L": -200.0, "Mode": "PAPER", "Entry Timeframe": "5M"},
        ])
        pdf_bytes = generate_performance_report_pdf(
            "NIFTY", "All", "2026-09-24", "2026-09-24", _SUMMARY,
            {"gross_pnl": 300, "total_charges": 0, "net_pnl": 300},
            None, None, None, trade_log_df, [],
        )
        assert pdf_bytes[:4] == b"%PDF"


class TestBuildTradeEntryExitChartImage:
    """🎓 वापरकर्त्याने स्पष्टपणे मागितलेली सुधारणा ("संबंधित चार्ट सुद्धा प्रिंट झाला पाहिजे, एन्ट्री-
    एक्झिट लेवल त्यावर दिसायला हवं, cross-verify करण्यासाठी मदत व्हावी") — kaleido/Chrome हे
    environment-specific असल्याने (काही CI/sandbox मध्ये उपलब्ध नसतं) प्रत्यक्ष bytes ऐवजी "क्रॅश होत
    नाही, आणि graceful fallback (None) व्यवस्थित काम करतो" हेच इथे पडताळलं आहे — बाकी सर्व chart-builder
    functions (build_group_pnl_bar_chart इ.) याच established पद्धतीने test-केलेले नाहीत."""

    def _candles(self):
        return pd.DataFrame({
            "timestamp": pd.date_range("2026-09-24 09:30", periods=20, freq="5min"),
            "open": [23900 + i for i in range(20)], "high": [23905 + i for i in range(20)],
            "low": [23895 + i for i in range(20)], "close": [23902 + i for i in range(20)],
        })

    def test_empty_candles_returns_none(self):
        assert build_trade_entry_exit_chart_image(pd.DataFrame(), entry_time="2026-09-24 10:00:00") is None
        assert build_trade_entry_exit_chart_image(None, entry_time="2026-09-24 10:00:00") is None

    def test_full_trade_does_not_raise(self):
        result = build_trade_entry_exit_chart_image(
            self._candles(), entry_time="2026-09-24 10:00:00", exit_time="2026-09-24 10:30:00",
            entry_level_price=23920.0, exit_reason="TARGET", realized_pnl=500.0,
        )
        assert result is None or result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_open_trade_without_exit_does_not_raise(self):
        result = build_trade_entry_exit_chart_image(self._candles(), entry_time="2026-09-24 10:00:00")
        assert result is None or result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_image_export_failure_is_logged_not_silently_swallowed(self):
        """🎓 वापरकर्त्याने सापडवलेली bug ("candle data unavailable" — candle डेटा प्रत्यक्ष उपलब्ध
        असूनही कायम) — मूळ कारण होतं VPS वर kaleido>=1.0 ला लागणारा वेगळा Chrome install नसणं, पण जुना
        `except Exception: return None` ती चूक कुठेच लॉग न करता गिळायचा. आता `fig.to_image()` अपयशी
        झाला (इथे मुद्दाम mock करून) तरी `_logger.error` ला कळवलं जातं, आणि तरीही graceful None."""
        with patch("plotly.graph_objects.Figure.to_image", side_effect=RuntimeError("Kaleido requires Google Chrome to be installed.")), \
             patch("pdf_reports._logger") as mock_logger:
            result = build_trade_entry_exit_chart_image(self._candles(), entry_time="2026-09-24 10:00:00")
        assert result is None
        assert mock_logger.error.called
        logged_msg = mock_logger.error.call_args.args[0]
        assert "chart image export failed" in logged_msg
        assert "Kaleido requires Google Chrome" in logged_msg


class TestGeneratePerformanceReportPdfTradeCharts:
    """🎓 वापरकर्त्याने स्पष्टपणे मागितलेली सुधारणा ("Trade one सोबत चा चार्ट, त्याचे एन्ट्री आणि त्याचे
    एक्झिट असा एक नवीन मॉडेल PDF मध्ये ऍड करा") — नवीन trade_charts विभाग असलेला/नसलेला PDF दोन्ही
    क्रॅश न होता तयार होतो का, candle data असलेल्या आणि नसलेल्या (graceful fallback) trade सकट."""

    def test_trade_charts_with_and_without_candle_data_does_not_crash(self):
        candles = pd.DataFrame({
            "timestamp": pd.date_range("2026-09-24 09:30", periods=20, freq="5min"),
            "open": [23900] * 20, "high": [23905] * 20, "low": [23895] * 20, "close": [23902] * 20,
        })
        trade_charts = [
            {"trade_id": "T1", "entry_time": "2026-09-24 10:00:00", "exit_time": "2026-09-24 14:00:00",
             "entry_level_price": 23920.0, "realized_pnl": 500.0, "exit_reason": "TARGET",
             "legs_text": "short_leg 24400PE Entry Rs38 -> Exit Rs15", "candles_df": candles},
            {"trade_id": "T2", "entry_time": "2026-09-24 11:00:00", "exit_time": "2026-09-24 11:30:00",
             "entry_level_price": None, "realized_pnl": -200.0, "exit_reason": "SL",
             "legs_text": None, "candles_df": pd.DataFrame()},  # candle data unavailable -> fallback text
        ]
        pdf_bytes = generate_performance_report_pdf(
            "NIFTY", "All", "2026-09-24", "2026-09-24", _SUMMARY,
            {"gross_pnl": 300, "total_charges": 0, "net_pnl": 300},
            None, None, None, None, [], trade_charts=trade_charts,
        )
        assert pdf_bytes[:4] == b"%PDF"

    def test_no_trade_charts_still_works(self):
        """trade_charts=None (established callers, backward-compatible) — विभागच दिसत नाही, क्रॅश नाही."""
        pdf_bytes = generate_performance_report_pdf(
            "NIFTY", "All", "2026-09-24", "2026-09-24", _SUMMARY,
            {"gross_pnl": 300, "total_charges": 0, "net_pnl": 300},
            None, None, None, None, [],
        )
        assert pdf_bytes[:4] == b"%PDF"

    def test_more_than_max_charts_shows_truncation_note_and_does_not_crash(self):
        candles = pd.DataFrame({
            "timestamp": pd.date_range("2026-09-24 09:30", periods=20, freq="5min"),
            "open": [23900] * 20, "high": [23905] * 20, "low": [23895] * 20, "close": [23902] * 20,
        })
        trade_charts = [
            {"trade_id": f"T{i}", "entry_time": "2026-09-24 10:00:00", "exit_time": "2026-09-24 10:30:00",
             "entry_level_price": 23920.0, "realized_pnl": 100.0, "exit_reason": "TARGET",
             "legs_text": "leg", "candles_df": candles}
            for i in range(15)
        ]
        pdf_bytes = generate_performance_report_pdf(
            "NIFTY", "All", "2026-09-24", "2026-09-24", _SUMMARY,
            {"gross_pnl": 1500, "total_charges": 0, "net_pnl": 1500},
            None, None, None, None, [], trade_charts=trade_charts,
        )
        assert pdf_bytes[:4] == b"%PDF"
