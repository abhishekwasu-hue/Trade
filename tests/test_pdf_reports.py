"""
tests/test_pdf_reports.py
--------------------------------
🎓 वापरकर्त्याने विचारलेली तक्रार ("charges खूप जास्त वाटतायत, कशाचं बनलंय दाखवा") — Performance
Report PDF च्या Summary मध्ये आता "Total Charges" सोबत order-संख्या आणि brokerage/STT/Exchange/
SEBI/Stamp/GST चा ब्रेकडाऊनही दाखवला जातो (आधी फक्त एक निव्वळ बेरीज होती). लांब ब्रेकडाऊन-ओळ Table
column च्या रुंदीबाहेर overflow होऊ नये म्हणून Paragraph मध्ये wrap करून दिली आहे -- ती अजिबात न
दाखवल्यास/चुकीच्या प्रकाराने दिल्यास PDF तयार होताना क्रॅश होईल, हेच इथे पडताळलं आहे.
"""
from pdf_reports import generate_performance_report_pdf

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
