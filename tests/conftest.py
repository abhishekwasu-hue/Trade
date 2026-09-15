"""
tests/conftest.py
--------------------
🎓 Production-readiness फिक्स — tests/test_strategy_selection.py ला `sample_option_chain` fixture
हवा होता, पण तो कुठेही परिभाषित (define) केलेला नव्हता (या रिपॉझिटरीच्या संपूर्ण इतिहासात कधीच
conftest.py अस्तित्वातच नव्हता) — त्यामुळे pytest ने ती फाईल पहिल्यांदाच प्रत्यक्ष चालवल्यावर (आधी
tests/ फोल्डरच नसल्याने ती कधीच चालतच नव्हती) १५ tests "fixture not found" म्हणून अयशस्वी झाले.

raw_chain चा आकार strategy.py च्या फंक्शन्सनी प्रत्यक्ष वापरलेल्या shape शी जुळणारा:
[{"strike_price": X, "call_options": {...}, "put_options": {...}}, ...]

Premium मॉडेल साधं पण वास्तववादी — intrinsic value (ITM असेल तितकी) + अंतरानुसार कमी होणारं
time value — जेणेकरून ITM strikes OTM पेक्षा जास्त महाग असतील (strategy.py च्या ITM-आधारित
strike-selection ची चाचणी अर्थपूर्ण व्हावी म्हणून आवश्यक — फक्त 'सर्व strikes समान किंमत' असं
साधेपणाने केलं असतं तर select_credit_spread_itm/select_naked_option_itm च्या net_credit/net_debit
गणितानुसार चुकीचे (किंवा नेहमी None) निकाल आले असते).
"""
import pytest

SPOT = 24500
STEP = 50


def _synthetic_premium(strike, option_type, spot=SPOT):
    """साधं पण सुसंगत ऑप्शन प्रीमियम मॉडेल — intrinsic value + ATM पासूनच्या अंतरानुसार कमी होणारं
    time value (किमान १०, जेणेकरून कुठलाही premium कधीच शून्य/ऋण होणार नाही)."""
    distance = abs(strike - spot)
    time_value = max(10.0, 100.0 - distance * 0.15)
    if option_type == "CE":
        intrinsic = max(0, spot - strike)
    else:  # PE
        intrinsic = max(0, strike - spot)
    return round(intrinsic + time_value, 2)


@pytest.fixture
def sample_option_chain():
    """SPOT (24500) भोवती ±1000 पॉइंट्स (step 50, म्हणजे 24000 ते 25000) च्या सर्व strikes साठी
    CE/PE दोन्ही — वास्तववादी (ITM जास्त महाग) premium, आणि सर्वांसाठी एकसमान PoP=0.6
    (option_greeks.pop) — टेस्ट फाईलमधल्याच अपेक्षेप्रमाणे ("सर्व pop=0.6 आहे")."""
    chain = []
    for strike in range(SPOT - 1000, SPOT + 1000 + STEP, STEP):
        chain.append({
            "strike_price": strike,
            "call_options": {
                "instrument_key": f"NSE_FO|TEST-CE-{strike}",
                "market_data": {"ltp": _synthetic_premium(strike, "CE")},
                "option_greeks": {"pop": 0.6},
            },
            "put_options": {
                "instrument_key": f"NSE_FO|TEST-PE-{strike}",
                "market_data": {"ltp": _synthetic_premium(strike, "PE")},
                "option_greeks": {"pop": 0.6},
            },
        })
    return chain
