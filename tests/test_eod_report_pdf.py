"""
tests/test_eod_report_pdf.py
---------------------------------
generate_eod_market_report_pdf — दररोज दुपारी ४ वाजताचा EOD Market Report चा PDF भाग (आता इंग्रजीत,
Times New Roman Bold-Italic 18pt — वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा).
"""
import pandas as pd
import numpy as np

import market_report
from pdf_reports import generate_eod_market_report_pdf, _DEVANAGARI_FONT, _fix_devanagari_glyphs, _EOD_FONT, _EOD_FONT_SIZE


def _make_df(n=80):
    np.random.seed(9)
    walk = 24000 + np.cumsum(np.random.randn(n) * 15)
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-08-27 09:15", periods=n, freq="15min"),
        "open": walk, "close": walk + 2, "high": walk + 8, "low": walk - 8, "volume": 1000,
    })


class TestDevanagariFontRegistration:
    """Devanagari font अजूनही नोंदलेला आहे (भविष्यात कुठे लागला तर) — फक्त EOD Report आता वापरत नाही."""
    def test_devanagari_font_registers_successfully(self):
        assert _DEVANAGARI_FONT == "NotoSansDevanagari"


class TestFixDevanagariGlyphs:
    def test_arrow_replaced_with_ascii(self):
        assert "->" in _fix_devanagari_glyphs("VIX=18 → Iron Condor")
        assert "→" not in _fix_devanagari_glyphs("VIX=18 → Iron Condor")

    def test_up_arrow_replaced(self):
        assert "^" in _fix_devanagari_glyphs("Writing ↑ (वाढतेय)")

    def test_non_string_passthrough(self):
        assert _fix_devanagari_glyphs(123) == 123


class TestEODReportStyling:
    """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — संपूर्ण report Times New Roman, Bold, Italic, 18pt."""
    def test_font_is_times_bold_italic(self):
        assert _EOD_FONT == "Times-BoldItalic"

    def test_font_size_is_18pt(self):
        assert _EOD_FONT_SIZE == 18


class TestGenerateEODMarketReportPDF:
    def test_single_symbol_produces_valid_pdf(self):
        df = _make_df()
        outlook = market_report.generate_symbol_outlook(
            "fake_token", "NIFTY", df_15m=df, df_1h=df, df_1d=df, india_vix=17.5, trading_mode="PAPER",
        )
        pdf_bytes = generate_eod_market_report_pdf([outlook])
        assert pdf_bytes[:4] == b"%PDF"
        assert len(pdf_bytes) > 1000

    def test_three_symbols_produces_valid_pdf(self):
        df = _make_df()
        outlooks = [
            market_report.generate_symbol_outlook("fake_token", sym, df_15m=df, df_1h=df, df_1d=df, india_vix=14.0, trading_mode="PAPER")
            for sym in ["NIFTY", "BANKNIFTY", "SENSEX"]
        ]
        pdf_bytes = generate_eod_market_report_pdf(outlooks)
        assert pdf_bytes[:4] == b"%PDF"

    def test_missing_optional_sections_do_not_crash(self):
        """S/R levels, OI summary, chart patterns, Greeks — सर्व None/रिकामे असतानाही PDF तयार व्हायलाच हवा."""
        outlook = {
            "symbol": "NIFTY",
            "multi_tf_outlook": {"outlook": "INSUFFICIENT DATA", "daily_dir": None, "hourly_dir": None, "min15_dir": None},
            "sr_levels": None, "chart_patterns": [], "oi_summary": None,
            "india_vix": None, "recommendation": "VIX data unavailable — cannot make a recommendation.",
            "open_positions_greeks": [],
        }
        pdf_bytes = generate_eod_market_report_pdf([outlook])
        assert pdf_bytes[:4] == b"%PDF"
