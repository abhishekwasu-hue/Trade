"""
tests/test_pdf_reports.py
--------------------------------
🎓 वापरकर्त्याने विचारलेली तक्रार ("charges खूप जास्त वाटतायत, कशाचं बनलंय दाखवा") — Performance
Report PDF च्या Summary मध्ये आता "Total Charges" सोबत order-संख्या आणि brokerage/STT/Exchange/
SEBI/Stamp/GST चा ब्रेकडाऊनही दाखवला जातो (आधी फक्त एक निव्वळ बेरीज होती). लांब ब्रेकडाऊन-ओळ Table
column च्या रुंदीबाहेर overflow होऊ नये म्हणून Paragraph मध्ये wrap करून दिली आहे -- ती अजिबात न
दाखवल्यास/चुकीच्या प्रकाराने दिल्यास PDF तयार होताना क्रॅश होईल, हेच इथे पडताळलं आहे.
"""
import pandas as pd
from reportlab.platypus import Paragraph

from pdf_reports import _fix_missing_glyphs, _rpt_kv_wrap, df_to_reportlab_table, generate_performance_report_pdf

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
