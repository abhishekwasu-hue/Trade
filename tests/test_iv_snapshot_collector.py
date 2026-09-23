"""
tests/test_iv_snapshot_collector.py
--------------------------------------------------------------
iv_snapshot_collector.py — वापरकर्त्याने मागितलेली नवीन सुधारणा ("Record iv of option premium daily
for analysis"). ATM ± 5 strikes (CE+PE) चाच IV फक्त साठवला जातो (संपूर्ण chain नाही), आणि
fetch_option_greeks() कडून मिळालेला IV बरोबर strike/option_type शी जोडला जातो का, हे इथले सर्वात
महत्त्वाचे तपासणी-मुद्दे.
"""
from unittest.mock import patch

import iv_snapshot_collector as ivc


def _leg(instrument_key, ltp):
    return {"instrument_key": instrument_key, "market_data": {"ltp": ltp}}


def _fake_chain(atm=24000, step=50, n_strikes_each_side=8, underlying_price=24010.0, expiry="2026-09-25"):
    """ATM च्या दोन्ही बाजूंनी n_strikes_each_side strikes असलेला fake option chain — जेणेकरून
    ATM ± 5 च्या आत/बाहेर दोन्ही प्रकारचे strikes चाचणीत असतील."""
    chain = []
    for i in range(-n_strikes_each_side, n_strikes_each_side + 1):
        strike = atm + i * step
        chain.append({
            "strike_price": strike, "expiry": expiry, "underlying_spot_price": underlying_price,
            "call_options": _leg(f"CE{strike}", 100 + i), "put_options": _leg(f"PE{strike}", 100 - i),
        })
    return chain


def _fake_greeks_map(chain):
    """प्रत्येक leg साठी iv = instrument_key वरून काढलेली, वेगळी (predictable) किंमत."""
    result = {}
    for item in chain:
        for side in ("call_options", "put_options"):
            ik = item[side]["instrument_key"]
            result[ik] = {"iv": len(ik) * 1.0, "delta": 0.5, "gamma": 0.01, "theta": -1.0, "vega": 5.0}
    return result


class TestCollectSymbol:
    def test_no_chain_returns_false(self):
        with patch.object(ivc, "fetch_upstox_option_chain", return_value=(None, "टोकन अवैध")):
            ok, msg = ivc.collect_symbol("fake_token", "NIFTY")
            assert ok is False
            assert "मिळाला नाही" in msg

    def test_missing_underlying_price_returns_false(self):
        chain = [{"strike_price": 24000, "underlying_spot_price": 0,
                  "call_options": _leg("CE24000", 100), "put_options": _leg("PE24000", 100)}]
        with patch.object(ivc, "fetch_upstox_option_chain", return_value=(chain, "SUCCESS")):
            ok, msg = ivc.collect_symbol("fake_token", "NIFTY")
            assert ok is False
            assert "underlying price" in msg

    def test_only_atm_plus_minus_5_strikes_saved(self):
        chain = _fake_chain(atm=24000, step=50, n_strikes_each_side=8)
        greeks_map = _fake_greeks_map(chain)
        with patch.object(ivc, "fetch_upstox_option_chain", return_value=(chain, "SUCCESS")), \
             patch.object(ivc, "fetch_option_greeks", return_value=greeks_map), \
             patch.object(ivc.cloud_db, "save_iv_snapshot", return_value=True) as mock_save:
            ok, msg = ivc.collect_symbol("fake_token", "NIFTY")
            assert ok is True
            assert mock_save.called
            symbol, trade_date, snapshot_time, rows = mock_save.call_args.args
            assert symbol == "NIFTY"
            # ATM=24000, step=50, range=5 -> 23750 ते 24250 (11 strikes) x 2 (CE+PE) = 22 rows
            assert len(rows) == 22
            strikes_seen = {r["strike"] for r in rows}
            assert min(strikes_seen) == 23750
            assert max(strikes_seen) == 24250
            assert 23700 not in strikes_seen  # range च्या बाहेरचा strike कधीच जाऊ नये
            assert 24300 not in strikes_seen

    def test_iv_correctly_matched_to_strike_and_option_type(self):
        chain = _fake_chain(atm=24000, step=50, n_strikes_each_side=8)
        greeks_map = _fake_greeks_map(chain)
        with patch.object(ivc, "fetch_upstox_option_chain", return_value=(chain, "SUCCESS")), \
             patch.object(ivc, "fetch_option_greeks", return_value=greeks_map), \
             patch.object(ivc.cloud_db, "save_iv_snapshot", return_value=True) as mock_save:
            ivc.collect_symbol("fake_token", "NIFTY")
            _, _, _, rows = mock_save.call_args.args
            atm_ce_row = next(r for r in rows if r["strike"] == 24000 and r["option_type"] == "CE")
            assert atm_ce_row["iv"] == greeks_map["CE24000"]["iv"]
            assert atm_ce_row["ltp"] == 100  # i=0 वर _leg("CE24000", 100 + 0)
            assert atm_ce_row["expiry"] == "2026-09-25"
            assert atm_ce_row["underlying_price"] == 24010.0

    def test_save_failure_returns_false(self):
        chain = _fake_chain(atm=24000, step=50, n_strikes_each_side=8)
        greeks_map = _fake_greeks_map(chain)
        with patch.object(ivc, "fetch_upstox_option_chain", return_value=(chain, "SUCCESS")), \
             patch.object(ivc, "fetch_option_greeks", return_value=greeks_map), \
             patch.object(ivc.cloud_db, "save_iv_snapshot", return_value=False):
            ok, msg = ivc.collect_symbol("fake_token", "NIFTY")
            assert ok is False
            assert "साठवता आलं नाही" in msg

    def test_default_symbols_is_nifty_only(self):
        assert ivc.IV_SYMBOLS == ["NIFTY"]

    def test_strike_range_configurable(self):
        """strike_range पॅरामीटर बदलल्यास तेवढ्याच strikes पुरतं मर्यादित राहायला हवं."""
        chain = _fake_chain(atm=24000, step=50, n_strikes_each_side=8)
        greeks_map = _fake_greeks_map(chain)
        with patch.object(ivc, "fetch_upstox_option_chain", return_value=(chain, "SUCCESS")), \
             patch.object(ivc, "fetch_option_greeks", return_value=greeks_map), \
             patch.object(ivc.cloud_db, "save_iv_snapshot", return_value=True) as mock_save:
            ivc.collect_symbol("fake_token", "NIFTY", strike_range=2)
            _, _, _, rows = mock_save.call_args.args
            assert len(rows) == 10  # (2*2+1) strikes x 2 (CE+PE)
