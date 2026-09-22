"""
tests/test_cloud_db_numpy_adapters.py
--------------------------------------------
🎓 वापरकर्त्याने प्रत्यक्ष VPS वर सापडवलेली, गंभीर bug — MCX Level Hit Log (आणि तोच कोड-मार्ग
वापरणारे NIFTY/BANKNIFTY/SENSEX bots) कायम रिकामेच दिसायचे, कारण pandas/numpy मधून येणारे
numpy.float64/int64/bool_ मूल्यं (उदा. zone_low/level_price) psycopg2 ला दिली की, NumPy 2.x
(requirements.txt: numpy~=2.4) च्या बदललेल्या repr मुळे SQL मध्ये अक्षरशः "np.float64(1416.2)"
असा मजकूर embed व्हायचा — प्रत्येक असा INSERT/UPDATE शांतपणे (except Exception मध्ये) अयशस्वी
व्हायचा, `data/app.log` शिवाय कुठेही न दिसता.

cloud_db.py import केल्यावरच (module-level) योग्य psycopg2 adapters नोंदवले जातात, त्यामुळे इथे
फक्त cloud_db import करून, प्रत्यक्ष (mocked नाही) psycopg2.extensions.adapt() वापरून पडताळणी —
जेणेकरून खरा regression (mocked connection मागे लपून राहणारा) पुन्हा कधीच परत येणार नाही.
"""
import psycopg2.extensions
import pytest

import cloud_db  # noqa: F401 -- फक्त import केल्यानेच adapters नोंदवले जावेत, हेच तपासायचं आहे

np = pytest.importorskip("numpy")


class TestNumpyPsycopg2Adapters:
    def test_numpy_float64_adapts_to_plain_numeric_literal(self):
        """खरा bug — आधी हे 'np.float64(1416.2)' असं (चुकीचं) यायचं."""
        adapted = psycopg2.extensions.adapt(np.float64(1416.2))
        assert adapted.getquoted() == b"1416.2"

    def test_numpy_float32_adapts_to_plain_numeric_literal(self):
        adapted = psycopg2.extensions.adapt(np.float32(23.5))
        assert adapted.getquoted() == b"23.5"

    def test_numpy_int64_adapts_to_plain_integer_literal(self):
        adapted = psycopg2.extensions.adapt(np.int64(42))
        assert adapted.getquoted() == b"42"

    def test_numpy_int32_adapts_to_plain_integer_literal(self):
        adapted = psycopg2.extensions.adapt(np.int32(7))
        assert adapted.getquoted() == b"7"

    def test_numpy_bool_adapts_to_sql_boolean_literal(self):
        assert psycopg2.extensions.adapt(np.bool_(True)).getquoted() == b"True"
        assert psycopg2.extensions.adapt(np.bool_(False)).getquoted() == b"False"

    def test_pandas_series_derived_value_adapts_correctly(self):
        """वास्तविक bug नेमकी इथूनच सुरू व्हायची -- DataFrame column मधून काढलेलं मूल्य numpy.float64
        असतं (dynamic_sr_instant_trader.py/mcx_futures_trader.py चं row['zone_low']/zrow['zone_low'])."""
        pd = pytest.importorskip("pandas")
        df = pd.DataFrame({"zone_low": [23404.2, 23901.123456]})
        level_price = df.iloc[0]["zone_low"]
        assert isinstance(level_price, np.float64)
        adapted = psycopg2.extensions.adapt(level_price)
        assert adapted.getquoted() == b"23404.2"

    def test_negative_and_zero_floats(self):
        assert psycopg2.extensions.adapt(np.float64(-5.5)).getquoted() == b"-5.5"
        assert psycopg2.extensions.adapt(np.float64(0.0)).getquoted() == b"0.0"
