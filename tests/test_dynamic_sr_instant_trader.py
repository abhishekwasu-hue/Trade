"""
tests/test_dynamic_sr_instant_trader.py
------------------------------------------------
dynamic_sr_instant_trader.py — वापरकर्त्याशी चर्चा करून बांधलेली, वाढीव High-Frequency 1-मिनिट S/R
रणनीती. Chart वर दाखवला जाणारा Dynamic S/R — 1-मिनिट candles च्या [low,high] रेंज मधून, किंवा
candles मधल्या gap मधून (Gap Up/Down वापरकर्त्याने विचारलेला प्रश्न), level cross झाला की तात्काळ
PAPER trade + zone mitigation + Telegram + **संपूर्ण Signal Log** (hit झाला किंवा नाही तरीही).
"""
import datetime
from unittest.mock import MagicMock, patch

import pandas as pd

import dynamic_sr_instant_trader as dsr
import cloud_db
from config import get_ist_now


class TestCheckLevelCrossed:
    """🎓 established 'फक्त सद्य LTP जवळ आहे का' या ऐवजी, candle-range + gap-through दोन्ही तपासणे."""

    def test_direct_touch_within_candle_range(self):
        candles = [
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24008, "low": 23895, "close": 23900},
        ]
        hit, hit_type, price = dsr.check_level_crossed(23900, candles)
        assert hit is True
        assert hit_type == "TOUCH"
        assert price == 23900

    def test_gap_down_crosses_level_without_touching(self):
        """🎓 वापरकर्त्याने विचारलेला Gap Down प्रश्न -- level ला कुठलाच candle स्पर्श करत नाही,
        पण दोन candles मधल्या gap मध्ये level सापडतो, म्हणजे उडी मारून ओलांडला गेला."""
        candles = [
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 23750, "high": 23820, "low": 23700, "close": 23780},
        ]
        hit, hit_type, price = dsr.check_level_crossed(23900, candles)
        assert hit is True
        assert hit_type == "GAP_THROUGH"
        assert price == 23750

    def test_gap_up_crosses_level_without_touching(self):
        candles = [
            {"open": 23800, "high": 23810, "low": 23790, "close": 23800},
            {"open": 24050, "high": 24080, "low": 24040, "close": 24060},
        ]
        hit, hit_type, price = dsr.check_level_crossed(23900, candles)
        assert hit is True
        assert hit_type == "GAP_THROUGH"
        assert price == 24050

    def test_no_hit_when_price_never_near_level(self):
        candles = [
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24008, "low": 23995, "close": 24000},
        ]
        hit, hit_type, price = dsr.check_level_crossed(23900, candles)
        assert hit is False
        assert hit_type is None

    def test_near_miss_within_0_01_pct_buffer_counts_as_touch(self):
        """🎓 वापरकर्त्याशी झालेला बदलांचा क्रम — आधी ±0.02% बफर होता, वापरकर्त्याने तो पूर्णपणे
        काढायला सांगितला (TOUCH_TOLERANCE_PCT=0), आणि लगेच पुढे "Keep level touch buffer 0.010% of
        spot" — म्हणजे आधीच्या निम्मा, छोटासा बफर परत ठेवला. candle ने level ला तंतोतंत स्पर्श केला
        नसला, तरी त्याच्या 0.01% च्या आत असेल तर अजूनही TOUCH धरला जायला हवा."""
        level = 24000.0
        buffer = level * 0.01 / 100  # = 2.4
        # दोन्ही candles level च्या **एकाच बाजूला** (खाली) ठेवलेले -- जेणेकरून GAP_THROUGH मार्ग
        # चुकून triggered होऊ नये, आणि खरंच फक्त TOUCH-बफरचा परिणाम तपासला जाईल.
        candles = [
            {"open": 23900, "high": 23910, "low": 23890, "close": 23895},
            # या candle चा high बफरच्या (2.4 च्या) आतच आहे, पण level ला प्रत्यक्ष स्पर्श केलेला नाही
            {"open": 23990, "high": level - buffer + 1, "low": 23985, "close": 23992},
        ]
        hit, hit_type, price = dsr.check_level_crossed(level, candles)
        assert hit is True
        assert hit_type == "TOUCH"

    def test_near_miss_beyond_0_01_pct_buffer_does_not_count_as_touch(self):
        """वरच्याच बफर (0.01%) च्याही पलीकडे (जुन्या 0.02% बफरच्या आत असला तरी) असलेला near-miss
        आता TOUCH धरला जाऊ नये."""
        level = 24000.0
        old_wider_buffer = level * 0.02 / 100  # = 4.8 -- सध्याच्या 0.01% (=2.4) पेक्षा जास्त
        candles = [
            {"open": 23900, "high": 23910, "low": 23890, "close": 23895},
            # या candle चा high जुन्या 0.02% बफरच्या आत असला तरी, सध्याच्या 0.01% बफरच्या बाहेर आहे
            {"open": 23990, "high": level - old_wider_buffer + 1, "low": 23985, "close": 23992},
        ]
        hit, hit_type, price = dsr.check_level_crossed(level, candles)
        assert hit is False
        assert hit_type is None

    def test_exact_touch_still_counts(self):
        """बफर कितीही असला तरी, candle च्या range मध्ये level तंतोतंत आला (even by exactly touching
        the high/low boundary) तर तो TOUCH अजूनही ओळखला जायलाच हवा."""
        level = 24000.0
        candles = [
            {"open": 24010, "high": 24015, "low": 24010, "close": 24012},
            {"open": 23990, "high": 24000, "low": 23985, "close": 23995},  # high == level, तंतोतंत स्पर्श
        ]
        hit, hit_type, price = dsr.check_level_crossed(level, candles)
        assert hit is True
        assert hit_type == "TOUCH"

    def test_stale_old_candle_in_10min_window_should_not_report_touch_if_only_last_2_checked(self):
        """🎓 वापरकर्त्याने Signal Log मधून सापडवलेली, खरी bug — 7-8 मिनिटांपूर्वीचा candle level ला
        स्पर्श करत होता, पण किंमत आता खूप दूर गेलीये. जुना recent_candles_count=10 वापरला असता, तर
        हा जुना candle अजूनही यादीत राहून खोटा TOUCH दाखवायचा. आता process_symbol() फक्त शेवटचे 2
        candles (recent_candles_count=2, नवीन डीफॉल्ट) वापरतो — म्हणजे हा जुना candle कधीच तपासलाच
        जात नाही, आणि योग्यरित्या NO_HIT मिळतो."""
        level = 23448.8
        # 8 मिनिटांपूर्वीचा candle -- level ला खरंच स्पर्श करत होता
        stale_touch_candle = {"open": 23450, "high": 23452, "low": 23447, "close": 23449}
        # शेवटचे 2 candles -- किंमत आता level पासून खूप दूर (~190 पॉइंट्स)
        recent_far_candles = [
            {"open": 23260, "high": 23262, "low": 23258, "close": 23261},
            {"open": 23252, "high": 23254, "low": 23249, "close": 23251.7},
        ]
        full_10min_window = [stale_touch_candle] + [
            {"open": 23300, "high": 23302, "low": 23298, "close": 23300}
        ] * 7 + recent_far_candles

        # established जुनी (bug असलेली) पद्धत -- संपूर्ण 10-candle विंडो दिली, तर खोटा TOUCH मिळायचा
        old_buggy_hit, _, _ = dsr.check_level_crossed(level, full_10min_window)
        assert old_buggy_hit is True  # हेच जुनं, चुकीचं वर्तन होतं

        # established नवीन (फिक्स केलेली) पद्धत -- फक्त शेवटचे 2 candles दिले, तर बरोबर NO_HIT
        new_correct_hit, _, _ = dsr.check_level_crossed(level, full_10min_window[-2:])
        assert new_correct_hit is False

    def test_beyond_buffer_still_no_hit(self):
        """बफर असला तरी त्याच्याही पलीकडे (खूप दूर) असलेला candle अजूनही NO_HIT च असायला हवं."""
        level = 24000.0
        candles = [
            {"open": 23980, "high": 23990, "low": 23975, "close": 23985},  # level पासून बरंच दूर
        ]
        hit, hit_type, price = dsr.check_level_crossed(level, candles)
        assert hit is False


class TestDetermineDirectionWithHysteresis:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा ("क्षणभर एखाद्या level च्या खाली/वरती गेल्यानंतर ताबडतोब
    support चा resistance किंवा resistance चा support असं नोंदवणं कितपत योग्य आहे... hysteresis
    लागू कर, 0.10% buffer") — किंमत level पासून ±0.10% च्या आतच wobble करत असेल, तर आधीचीच निश्चित
    दिशा कायम राहायला हवी, प्रत्येक candle ला उगाच फ्लिप होता कामा नये."""

    LEVEL = 23353.1  # वापरकर्त्याने दाखवलेल्या खऱ्या उदाहरणातलाच level

    def test_sticky_bullish_when_dip_stays_within_buffer(self):
        """किंमत आधी स्पष्टपणे level च्या वर होती (confirmed BULLISH), नंतर level च्या किंचित खाली
        (पण buffer च्या आतच) गेली — जुनी (raw तुलना) पद्धत इथे चुकून BEARISH दाखवायची, आता निश्चित
        BULLISH च राहायला हवं (खऱ्या केसमध्ये नेमकं हेच 09:56 ला व्हायला हवं होतं)."""
        closes = [23400.0, 23350.0]  # 23350 < level(23353.1) पण lower buffer(23329.75) च्या वरच
        assert dsr.determine_direction_with_hysteresis(self.LEVEL, closes) == "BULLISH"

    def test_flips_to_bearish_only_when_clearly_beyond_buffer(self):
        """किंमत खरंच buffer च्या पलीकडे (स्पष्टपणे) खाली गेली, तरच दिशा खऱ्या अर्थाने फ्लिप व्हायला हवी."""
        closes = [23400.0, 23300.0]  # 23300 < lower buffer (23329.75) -- खरा breakdown
        assert dsr.determine_direction_with_hysteresis(self.LEVEL, closes) == "BEARISH"

    def test_falls_back_to_raw_comparison_when_never_left_band(self):
        """आजचा संपूर्ण इतिहास कधीच buffer च्या बाहेर गेलाच नसेल (उदा. दिवसाची सुरुवात, नवीनच
        level), तर सद्य किमतीची raw तुलनाच (जुनं वर्तन) सुरक्षित fallback म्हणून वापरली जायला हवी."""
        closes = [23353.1]  # बरोबर level वरच, buffer बाहेर कधीच नाही
        assert dsr.determine_direction_with_hysteresis(self.LEVEL, closes) == "BULLISH"

    def test_real_world_scenario_stays_bullish_through_momentary_dip(self):
        """🎓 वापरकर्त्याने दाखवलेलं खरं उदाहरण — किंमत स्पष्टपणे support च्या वर असतानाच, एका
        candle साठी किंचित खाली डोकावली (0.10% च्या आतच) आणि परत वर आली. hysteresis शिवाय (जुनी
        raw तुलना) मधल्या candle ला direction चुकून BEARISH व्हायचं (RSI Gate चुकीच्या rule कडे —
        Resistance>60 — पडताळायचा). आता संपूर्ण काळात BULLISH च राहायला हवं."""
        closes = [23400.0, 23370.0, 23350.0, 23365.0]  # सगळेच buffer (23329.75-23376.45) च्या आत/वर
        for i in range(1, len(closes) + 1):
            assert dsr.determine_direction_with_hysteresis(self.LEVEL, closes[:i]) == "BULLISH"


class TestCheckBreakoutCandleClose:
    """🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा (Breakout Entry — "Breakout buildup and 5 minute
    candle closed happen then take entry in the same direction") — नुकताच पूर्ण झालेला 5-मिनिट
    candle level च्या पलीकडे निर्णायकपणे close झाला आहे का (नुसता touch नाही)."""

    LEVEL = 23900.0

    def test_bullish_breakout_confirmed_when_close_above_level(self):
        candles = [{"close": 23880.0}, {"close": 23920.0}]
        assert dsr.check_breakout_candle_close(self.LEVEL, "BULLISH", candles) is True

    def test_bullish_breakout_not_confirmed_when_close_still_below(self):
        candles = [{"close": 23880.0}, {"close": 23895.0}]
        assert dsr.check_breakout_candle_close(self.LEVEL, "BULLISH", candles) is False

    def test_bearish_breakout_confirmed_when_close_below_level(self):
        candles = [{"close": 23920.0}, {"close": 23880.0}]
        assert dsr.check_breakout_candle_close(self.LEVEL, "BEARISH", candles) is True

    def test_bearish_breakout_not_confirmed_when_close_still_above(self):
        candles = [{"close": 23920.0}, {"close": 23905.0}]
        assert dsr.check_breakout_candle_close(self.LEVEL, "BEARISH", candles) is False

    def test_only_last_candle_matters(self):
        """आधीचे candles पलीकडे गेलेले असले तरी, शेवटचाच (सर्वात अलीकडचा, पूर्ण झालेला) candle बघायचा."""
        candles = [{"close": 23920.0}, {"close": 23930.0}, {"close": 23895.0}]
        assert dsr.check_breakout_candle_close(self.LEVEL, "BULLISH", candles) is False

    def test_empty_candles_returns_false(self):
        assert dsr.check_breakout_candle_close(self.LEVEL, "BULLISH", []) is False
        assert dsr.check_breakout_candle_close(self.LEVEL, "BULLISH", None) is False

    def test_exactly_at_level_is_not_a_close_beyond(self):
        """नेमकं level वरच close (पलीकडे नाही) -- confirm नाही, > / < strict."""
        candles = [{"close": self.LEVEL}]
        assert dsr.check_breakout_candle_close(self.LEVEL, "BULLISH", candles) is False
        assert dsr.check_breakout_candle_close(self.LEVEL, "BEARISH", candles) is False


class TestCheckBreakoutPriceConsolidation:
    """🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा (Breakout Entry — "buildup" साठी वेगळं, trade-
    outcome/live_trades-independent logic — "A" (touch-count, आधीच hit_count_so_far>=2 वरून
    established) सोबत "C" — price consolidation, breakout-candle च्या आधीच्या काही 5-मिनिट candles
    मध्ये price level च्या जवळच राहिला होता का, याचा शुद्ध price-action पुरावा) — डीफॉल्ट
    lookback_candles=12 (1 तास, "kiman 12 candle chi range" — वापरकर्त्याने कडवलेलं),
    tolerance_pct=0.30 (वापरकर्त्याने कडवलेले). ही function-level tests खालच्या generic लॉजिकसाठी
    वेगवेगळे lookback_candles पॅरामीटर वापरतात, डीफॉल्टवर अवलंबून नाहीत."""

    LEVEL = 23900.0

    def _candles(self, closes):
        """closes: [.., .., last] -- शेवटचा close breakout-confirm candle (या function मध्ये तो
        बघितला जात नाही, फक्त त्याआधीचा window)."""
        return [{"close": c} for c in closes]

    def test_consolidation_confirmed_when_all_window_closes_within_tolerance(self):
        window = [23895.0, 23905.0, 23898.0, 23903.0, 23897.0, 23901.0]
        candles = self._candles(window + [23860.0])  # शेवटचा = breakout candle, इथे अप्रस्तुत
        assert dsr.check_breakout_price_consolidation(self.LEVEL, candles, lookback_candles=6, tolerance_pct=0.30) is True

    def test_consolidation_not_confirmed_when_one_close_outside_tolerance(self):
        # 0.30% of 23900 ≈ 71.7 points -- 23800 हा त्याबाहेर
        window = [23895.0, 23905.0, 23800.0, 23903.0, 23897.0, 23901.0]
        candles = self._candles(window + [23860.0])
        assert dsr.check_breakout_price_consolidation(self.LEVEL, candles, lookback_candles=6, tolerance_pct=0.30) is False

    def test_not_enough_candles_for_window_returns_false(self):
        window = [23895.0, 23905.0, 23898.0]  # फक्त 3, 6 हवेत
        candles = self._candles(window + [23860.0])
        assert dsr.check_breakout_price_consolidation(self.LEVEL, candles, lookback_candles=6, tolerance_pct=0.30) is False

    def test_last_candle_excluded_from_window_check(self):
        """शेवटचा (breakout-confirm) candle हा consolidation window मध्ये मोजला जात नाही -- तो
        level पासून लांब असला (जसं breakout candle असायलाच हवं) तरी consolidation check pass व्हायला
        हवा, फक्त त्याआधीचेच 6 बघितले जातात."""
        window = [23895.0, 23905.0, 23898.0, 23903.0, 23897.0, 23901.0]
        candles = self._candles(window + [23700.0])  # शेवटचा खूप लांब
        assert dsr.check_breakout_price_consolidation(self.LEVEL, candles, lookback_candles=6, tolerance_pct=0.30) is True

    def test_empty_candles_returns_false(self):
        assert dsr.check_breakout_price_consolidation(self.LEVEL, [], lookback_candles=6, tolerance_pct=0.30) is False

    def test_just_inside_tolerance_boundary_is_within(self):
        # tolerance_points च्या अगदी आत (floating-point exact-boundary edge-case टाळण्यासाठी थोडं
        # आत) -- <= (strict < नाही) वापरलं जातंय याची खात्री.
        tolerance_points = self.LEVEL * 0.30 / 100
        window = [self.LEVEL + tolerance_points - 0.01] * 6
        candles = self._candles(window + [23860.0])
        assert dsr.check_breakout_price_consolidation(self.LEVEL, candles, lookback_candles=6, tolerance_pct=0.30) is True

    def test_custom_lookback_and_tolerance_respected(self):
        window = [23790.0, 24010.0]  # level पासून 110 points -- 0.50% (119.5 pts) च्या आत, 0.10% (23.9 pts) च्या बाहेर
        candles = self._candles(window + [23800.0])
        assert dsr.check_breakout_price_consolidation(self.LEVEL, candles, lookback_candles=2, tolerance_pct=0.50) is True
        assert dsr.check_breakout_price_consolidation(self.LEVEL, candles, lookback_candles=2, tolerance_pct=0.10) is False


def _fake_zones():
    """🎓 वापरकर्त्याने सांगितलेला निर्णय — 1M touches profitable नाहीत, त्यामुळे 1m_instant चा
    डीफॉल्ट timeframe_choice आता "BOTH" ऐवजी "5M" आहे. हे fixture बहुतेक टेस्ट्समध्ये
    (settings mock न करता, म्हणजे डीफॉल्ट settings सहच) वापरलं जातं, त्यामुळे ते आता 5M zone_type
    वापरतं — 1M असतं तर डीफॉल्ट settings सोबत हे कधीच touch झालंच नसतं (active_timeframes=["5M"])."""
    return pd.DataFrame([
        {"symbol": "NIFTY", "zone_type": "DYNAMIC_SR_SUPPORT_5M", "zone_low": 23900.0, "zone_high": 23900.0,
         "strength": 3.0, "formed_date": "2026-09-01", "status": "ACTIVE"},
        {"symbol": "NIFTY", "zone_type": "DYNAMIC_SR_RESISTANCE_5M", "zone_low": 24500.0, "zone_high": 24500.0,
         "strength": 2.0, "formed_date": "2026-09-01", "status": "ACTIVE"},
    ])


def _candles_with_rsi(touch_rows, declining=True, today_ist=None):
    """RSI(14) साठी किमान 15 candles लागतात. touch_rows (शेवटचे, टच घडवणारे) च्या आधी घसरणारा
    (declining=True, Support/BULLISH साठी RSI<40) किंवा चढणारा (declining=False, Resistance/BEARISH
    साठी RSI>60) trend prepend करतो.

    🎓 वापरकर्त्याने सापडवलेली bug (lookback_days=1 मुळे कालचे candles मिसळणे) फिक्स केल्यानंतर —
    process_symbol() आता candles_df["timestamp"] वापरून आजचाच दिवस फिल्टर करतो, त्यामुळे सर्व test
    fixtures ना आता timestamp column हवा. 🎓 पुढे सापडलेली दुसरी bug — जर हा helper `with
    patch.object(dsr, "get_ist_now", ...)` सुरू होण्याआधी कॉल केला, तर तो खऱ्या (mock न केलेल्या)
    आजच्या तारखेने candles बनवतो — आणि नंतर process_symbol() च्या आत mock केलेल्या तारखेशी विसंगती
    येते (विशेषतः रोज मध्यरात्रीनंतर test चालवल्यास). म्हणून आता `today_ist` explicit पॅरामीटर —
    जो test स्वतःच्या get_ist_now mock शी जुळणारा द्यायला हवा (न दिल्यास डीफॉल्ट dsr.get_ist_now()
    — जुनं, कमी सुरक्षित वर्तन)."""
    n = 25
    if declining:
        trend = [{"open": 24200 - i * 10, "high": 24210 - i * 10, "low": 24190 - i * 10, "close": 24195 - i * 10} for i in range(n)]
    else:
        trend = [{"open": 23600 + i * 10, "high": 23610 + i * 10, "low": 23590 + i * 10, "close": 23605 + i * 10} for i in range(n)]
    all_rows = trend + touch_rows
    # 🎓 pd.Timestamp.now() सर्व्हरच्या local (शक्यतो UTC) वेळेवर अवलंबून असतो — production code च्या
    # get_ist_now() शी दिवस-सीमेवर (विशेषतः संध्याकाळी UTC नुसार) न जुळण्याचा धोका आहे, म्हणून तेच
    # (dsr.get_ist_now, जेणेकरून mock केल्यास दोन्ही ठिकाणी तीच वेळ वापरली जाईल) वापरून सुसंगत ठेवतो.
    today_ist = (today_ist or dsr.get_ist_now()).replace(hour=10, minute=0, second=0, microsecond=0)
    timestamps = pd.date_range(end=today_ist, periods=len(all_rows), freq="1min")
    df = pd.DataFrame(all_rows)
    df["timestamp"] = timestamps
    return df


def _fake_chain(spot):
    return [{"underlying_spot_price": spot, "strike_price": 24000, "expiry": "2026-09-10",
             "call_options": {"instrument_key": "CE1", "market_data": {"ltp": 50}, "option_greeks": {}},
             "put_options": {"instrument_key": "PE1", "market_data": {"ltp": 45}, "option_greeks": {}}}]


class TestCollectPooledLevels:
    """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — timeframe_choice setting (Bot Dynamic SR Algo
    पानावरून) नुसार वापरकर्त्याला फक्त 1M, फक्त 5M, किंवा दोन्ही (डीफॉल्ट) touch levels तपासता यायला हवेत."""

    def _zones_1m_and_5m(self):
        return pd.DataFrame([
            {"symbol": "NIFTY", "zone_type": "DYNAMIC_SR_SUPPORT_1M", "zone_low": 23900.0, "zone_high": 23900.0,
             "strength": 3.0, "formed_date": "2026-09-01", "status": "ACTIVE"},
            {"symbol": "NIFTY", "zone_type": "DYNAMIC_SR_SUPPORT_5M", "zone_low": 23850.0, "zone_high": 23850.0,
             "strength": 3.0, "formed_date": "2026-09-01", "status": "ACTIVE"},
        ])

    def test_default_pools_both_timeframes(self):
        pooled = dsr._collect_pooled_levels(self._zones_1m_and_5m())
        suffixes = sorted(s for _, s in pooled)
        assert suffixes == ["1M", "5M"]

    def test_1m_only(self):
        pooled = dsr._collect_pooled_levels(self._zones_1m_and_5m(), ["1M"])
        assert [s for _, s in pooled] == ["1M"]

    def test_5m_only(self):
        pooled = dsr._collect_pooled_levels(self._zones_1m_and_5m(), ["5M"])
        assert [s for _, s in pooled] == ["5M"]


class TestProcessSymbol:
    def test_timeframe_choice_1m_ignores_5m_levels(self):
        """🎓 settings मध्ये timeframe_choice="1M" असेल तर 5M zone touch झाला तरी दुर्लक्षित व्हायला हवा."""
        zones_5m_only_touch = pd.DataFrame([
            {"symbol": "NIFTY", "zone_type": "DYNAMIC_SR_SUPPORT_5M", "zone_low": 23900.0, "zone_high": 23900.0,
             "strength": 3.0, "formed_date": "2026-09-01", "status": "ACTIVE"},
        ])
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        settings_1m_only = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
        settings_1m_only["timeframe_choice"] = "1M"
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=zones_5m_only_touch), \
             patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings_1m_only), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade:
            result = dsr.process_symbol("fake_token", "NIFTY")
            assert "कुठलेही ACTIVE Dynamic S/R levels (1M) नाहीत" in result
            assert not mock_trade.called

    def test_gap_through_executes_trade_and_logs_all_levels(self):
        """🎓 वापरकर्त्याने विचारलेला Gap Down प्रश्न + मागितलेला संपूर्ण Signal Log -- दोन्ही एकत्र.

        🎓 वापरकर्त्याशी चर्चा करून जोडलेल्या सुधारणेनंतर (दिशा आता row["zone_type"] च्या साठवलेल्या
        label वरून नाही, सद्य किमतीच्या level च्या सापेक्ष स्थितीवरून ठरते) — किंमत support level
        (23900) च्या खालीच गॅप-डाऊन होऊन स्थिरावली, त्यामुळे दिशा आता BEARISH (level आता resistance
        सारखा वागतो). हा टेस्ट gap-through detection + संपूर्ण Signal Log याचीच पडताळणी करतो,
        RSI ची नाही -- म्हणून check_instant_rsi_filter थेट pass होईल असा mock केला आहे."""
        candles_gap = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 23750, "high": 23820, "low": 23700, "close": 23780},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_gap), \
             patch.object(dsr, "check_instant_rsi_filter", return_value=(True, 65.0)), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23780.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy_type": "BEAR_CALL_SPREAD", "legs": []}), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True) as mock_telegram, \
             patch.object(dsr.cloud_db, "save_market_zones", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log:
            result = dsr.process_symbol("fake_token", "NIFTY")
            assert "GAP_THROUGH" in result
            assert mock_trade.called
            assert mock_telegram.called
            # 🎓 दोन्ही levels (एक hit, एक no-hit) साठी log व्हायलाच हवं -- संपूर्ण Signal Log, अधिक
            # naked trade साठीचा diagnostic entry (select_naked_option_itm इथे mock केलेला नाही,
            # आणि _fake_chain मध्ये आवश्यक ITM strike नसल्याने ती None परत देते).
            assert mock_log.call_count == 3
            logged_entries = [c.args[0] for c in mock_log.call_args_list]
            logged_types = [e["hit_type"] for e in logged_entries]
            assert "GAP_THROUGH" in logged_types
            assert "NO_HIT" in logged_types
            naked_diag = [e for e in logged_entries if e.get("trade_status") == "SKIPPED_NAKED_STRIKE_NOT_FOUND"]
            assert len(naked_diag) == 1

    def test_short_leg_uses_itm_depth_from_settings(self):
        """वापरकर्त्याशी चर्चा करून सुधारित (Bot Dynamic SR Algo -- नवीन नियम-संच) -- Short leg
        आता ITM दिशेने (settings मधल्या itm_depth_points इतका, डीफॉल्ट 50) -- जुना ATM-आधारित
        strikes_otm नाही."""
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "fetch_option_expiries", return_value=[]), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}) as mock_select, \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")), \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_select.called
            assert mock_select.call_args.kwargs.get("itm_depth_points") == 50
            assert mock_select.call_args.kwargs.get("hedge_width_points") == 150

    def test_atm_strike_rounds_to_symbol_own_strike_step_not_always_50(self):
        """🎓 पूर्व-live रिव्ह्यूत सापडवलेली bug — atm_strike कायम round(price/50)*50 वापरत होता,
        NIFTY (strike step 50) साठी बरोबर, पण BANKNIFTY/SENSEX (strike step 100) साठी अनेकदा चुकीचा
        (राऊंड-ऑफ ग्रिडवर strike येतो, जो त्या symbol साठी प्रत्यक्षात अस्तित्वातच नसतो — raw_chain मध्ये
        सापडतच नाही, त्यामुळे strike-निवड निम्म्या वेळा उगाचच अयशस्वी होते). आता symbol च्या
        cloud_db.STRIKE_STEP नुसार राऊंड होतो, आणि तोच step select_credit_spread_itm()/
        select_naked_option_itm() ला ITM-depth राऊंडिंगसाठी दिला जातो."""
        touch_rows = [
            {"open": 51960, "high": 51970, "low": 51950, "close": 51955},
            {"open": 51950, "high": 51955, "low": 51920, "close": 51930},
        ]
        candles_touch = _candles_with_rsi(touch_rows, declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        banknifty_zones = pd.DataFrame([
            {"symbol": "BANKNIFTY", "zone_type": "DYNAMIC_SR_SUPPORT_5M", "zone_low": 51930.0, "zone_high": 51930.0,
             "strength": 3.0, "formed_date": "2026-09-01", "status": "ACTIVE"},
        ])
        settings_banknifty = dsr.cloud_db.get_strategy_settings("1m_instant", "BANKNIFTY")
        settings_banknifty["symbol_enabled"] = True
        settings_banknifty["naked_enabled"] = False
        settings_banknifty["entry_rsi_gate_enabled"] = False
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings_banknifty), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=banknifty_zones), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(51930.0), "SUCCESS")), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}) as mock_select, \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")), \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "BANKNIFTY")
            assert mock_select.called
            # round(51930/100)*100 = 51900 -- जुनी बग round(51930/50)*50 = 51950 देत होती
            assert mock_select.call_args.args[2] == 51900
            assert mock_select.call_args.kwargs.get("step") == 100

    def test_direct_touch_executes_trade(self):
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy_type": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")), \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_market_zones", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True):
            result = dsr.process_symbol("fake_token", "NIFTY")
            assert "TOUCH" in result

    def test_direction_follows_current_price_not_stored_label(self):
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — "All levels above LTP will act as
        resistance and levels below LTP will act as support" — दिशा आता row["zone_type"] च्या
        साठवलेल्या (मागच्या cron cycle च्या) label वरून नाही, तर सद्य किमतीच्या level च्या सापेक्ष
        स्थितीवरून ठरते. इथे zone साठवलेला RESISTANCE_1M असला, तरी सद्य किंमत (23902) त्या level
        (23900) च्या वर आहे (support सारखी स्थिती) -- त्यामुळे दिशा BULLISH व्हायला हवी, साठवलेला
        RESISTANCE label असूनही (srv2_momentum_reversal_strategy.py मध्ये आधीच वापरलेल्याच
        नियमाप्रमाणे)."""
        def _fake_resistance_labeled_zone():
            return pd.DataFrame([
                {"symbol": "NIFTY", "zone_type": "DYNAMIC_SR_RESISTANCE_5M", "zone_low": 23900.0, "zone_high": 23900.0,
                 "strength": 3.0, "formed_date": "2026-09-01", "status": "ACTIVE"},
            ])
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_resistance_labeled_zone()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy_type": "BULL_PUT_SPREAD", "legs": []}) as mock_select, \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_market_zones", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called
            assert mock_select.call_args.args[1] == "BULLISH"  # साठवलेला RESISTANCE label असूनही

    def test_yesterdays_candle_never_causes_false_touch_at_market_open(self):
        """🎓 वापरकर्त्याने सापडवलेली, खरी bug (केवळ candle-window छोटा करून सुटणारी नाही) —
        fetch_candles(..., lookback_days=1) कालच्या दिवसाचे शेवटचे candles सुद्धा (आजच्या सोबतच)
        परत करतो. बाजार उघडून अगदी काही मिनिटंच झालेली असताना, जुना कोड आपोआप कालचा (gap-पूर्वीचा)
        candle घ्यायचा — आणि आज बाजारात कधीच न आलेल्या किमतीवर खोटा TOUCH दाखवायचा. आता
        candles_df["timestamp"] वरून आजचाच दिवस आधी फिल्टर करतो, त्यामुळे कालचा candle कधीच
        या तपासणीत येतच नाही."""
        today_ist = get_ist_now()
        yesterday_ist = today_ist - datetime.timedelta(days=1)

        # कालचे 25 candles (RSI(14) साठी पुरेसा इतिहास) — यातला शेवटचा level (23448.8) ला
        # प्रत्यक्ष स्पर्श करतो (जुन्या कोड मध्ये हाच candle खोटा TOUCH दाखवायचा)
        yesterdays_candles = [
            {"timestamp": yesterday_ist.replace(hour=15, minute=max(0, i)), "open": 23450, "high": 23452, "low": 23447, "close": 23449}
            for i in range(1, 26)
        ]
        # आजचा पहिलाच candle — level पासून खूप दूर (मोठा gap-down)
        todays_first_candle = {"timestamp": today_ist.replace(hour=9, minute=15, second=0, microsecond=0), "open": 23260, "high": 23262, "low": 23258, "close": 23261}

        candles_df = pd.DataFrame(yesterdays_candles + [todays_first_candle])

        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "fetch_candles", return_value=candles_df), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23261.0), "SUCCESS")), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade:
            result = dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            assert "cross झाला नाही" in result  # आजचा candle level पासून दूर -- खरा NO_HIT, कालच्या candle चा प्रभाव नाही

    def test_no_hit_logs_but_does_not_trade(self):
        candles_no_hit = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24008, "low": 23995, "close": 24000},
        ], declining=True)
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "fetch_candles", return_value=candles_no_hit), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(24000.0), "SUCCESS")), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log:
            result = dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            assert mock_log.called  # तरीही log व्हायलाच हवं
            assert "cross झाला नाही" in result

    def test_zone_stays_active_after_hit_not_filled(self):
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Multi-Hit) — established आता cross झाल्यावरही
        zone कायमचं FILLED होत नाही (जुनं वर्तन) — save_market_zones() ला कॉलच होत नाही, कारण
        gating आता established hit_count/cooldown (signal_log वरून) वरून होते, zone-status वरून नाही."""
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True)
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")), \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)), \
             patch.object(dsr.cloud_db, "save_market_zones") as mock_save:
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_save.called


class TestMultiHitGating:
    """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — established एकाच zone ला दिवसातून जास्तीत जास्त
    २ वेळा trade करता येतो, established अटींसह: (अ) established आधीच्या hit पासून किमान ३० मिनिटांचं
    अंतर (cooldown), (ब) established आधीची position आधीच बंद (CLOSED) झालेली असावी."""

    def _touch_setup(self):
        touch_rows = [
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ]
        return _candles_with_rsi(touch_rows, declining=True)  # 🎓 Support/BULLISH -> RSI<40 हवा

    def test_no_new_entry_after_1445(self):
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — 14:45 नंतर नवीन entry घ्यायचीच नाही."""
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 14, 50, 0)), \
             patch.object(dsr, "fetch_candles", return_value=self._touch_setup()), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_TOO_LATE_FOR_NEW_ENTRY" in statuses

    def test_entry_allowed_just_before_1445(self):
        """14:44 ला (कटऑफच्या आधी), entry नेहमीसारखीच व्हायला हवी."""
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 14, 44, 0)), \
             patch.object(dsr, "fetch_candles", return_value=self._touch_setup()), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T40"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called

    def test_first_hit_of_the_day_trades_normally(self):
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=self._touch_setup()), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called

    def test_get_zone_hits_today_called_with_role_from_zone_type(self):
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेला role-split max-2 counter — _fake_zones() मधला touch
        होणारा level DYNAMIC_SR_SUPPORT_5M आहे, त्यामुळे role="SUPPORT" इतकाच पास व्हायला हवा
        (resistance च्या counter मध्ये मिसळू नये)."""
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=self._touch_setup()), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")), \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)) as mock_hits:
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_hits.called
            assert mock_hits.call_args.kwargs.get("role") == "SUPPORT"

    def test_third_hit_of_day_skipped_max_2_reached(self):
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=self._touch_setup()), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr, "send_telegram_message") as mock_telegram, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(2, get_ist_now(), get_ist_now())):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            assert not mock_telegram.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_MAX_2_HITS_REACHED" in statuses

    def test_second_hit_within_30min_cooldown_skipped(self):
        recent_hit_time = get_ist_now() - datetime.timedelta(minutes=10)
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=self._touch_setup()), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(1, recent_hit_time, recent_hit_time)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_COOLDOWN_30MIN" in statuses

    def test_second_hit_after_30min_but_previous_position_still_open_skipped(self):
        old_hit_time = datetime.datetime(2026, 9, 11, 10, 0, 0) - datetime.timedelta(minutes=45)
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=self._touch_setup()), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(1, old_hit_time, old_hit_time)), \
             patch.object(dsr, "has_open_trade_from_source", return_value=True):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_PREVIOUS_POSITION_STILL_OPEN" in statuses

    def test_first_hit_of_level_still_skipped_if_any_other_position_open(self):
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेली, महत्त्वाची सुधारणा — वापरकर्त्याने Order Log मधून
        सापडवलेली bug — established आधी ही तपासणी फक्त hit_count_so_far>=1 (म्हणजे "याच specific
        level ला आज दुसऱ्यांदा hit") असेल तरच चालायची. म्हणजे established एका वेगळ्या level वर आधीच
        उघडी असलेली position असतानाही, established दुसऱ्या (आजचा पहिलाच hit, hit_count_so_far=0)
        level वर established नवीन trade उघडली जायची. आता established कुठल्याही level साठी, established
        हा check बिनशर्त — established position उघडी असेल तर established कुठलाही (नवा असो वा जुना)
        level असो, entry होणारच नाही."""
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=self._touch_setup()), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)), \
             patch.object(dsr, "has_open_trade_from_source", return_value=True):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_PREVIOUS_POSITION_STILL_OPEN" in statuses

    def test_second_hit_after_30min_and_previous_closed_trades_again(self):
        old_hit_time = datetime.datetime(2026, 9, 11, 10, 0, 0) - datetime.timedelta(minutes=45)
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=self._touch_setup()), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T2"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(1, old_hit_time, old_hit_time)), \
             patch.object(dsr, "has_open_trade_from_source", return_value=False):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called

    def test_symbol_disabled_skips_entirely(self):
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (symbol_enabled) — उपलब्ध भांडवलानुसार
        वापरकर्ता BANKNIFTY/SENSEX बंद ठेवू शकतो; बंद असल्यास zones/candles काहीही न वाचता थेट थांबायला हवं."""
        disabled_settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
        disabled_settings["symbol_enabled"] = False
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=disabled_settings), \
             patch.object(dsr.cloud_db, "get_market_zones") as mock_zones:
            result = dsr.process_symbol("fake_token", "BANKNIFTY")
            assert "बंद आहे" in result
            assert not mock_zones.called

    def test_no_active_zones_handled_gracefully(self):
        empty_zones = pd.DataFrame(columns=["symbol", "zone_type", "zone_low", "zone_high", "strength", "formed_date", "status"])
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=empty_zones):
            result = dsr.process_symbol("fake_token", "NIFTY")
            assert "सापडले नाहीत" in result or "नाहीत" in result

    def test_none_from_supabase_handled_gracefully(self):
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=None):
            result = dsr.process_symbol("fake_token", "NIFTY")
            assert "सापडले नाहीत" in result or "नाहीत" in result

    def test_no_candles_handled_gracefully(self):
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "fetch_candles", return_value=pd.DataFrame()):
            result = dsr.process_symbol("fake_token", "NIFTY")
            assert "मिळाले नाहीत" in result


class TestBullishBearishEntryToggle:
    """🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("Bullish and Bearish Entry off करण्याचे Button
    सुद्धा पाहिजे") — अंतिम (IV/Breakout-flip नंतरच्याही) direction वरच तपासलं जातं, फक्त नवीन
    trades थांबतात."""

    def test_bullish_entry_disabled_skips_bullish_touch(self):
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
        settings["bullish_entry_enabled"] = False
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_BULLISH_ENTRY_DISABLED" in statuses

    def test_bearish_entry_disabled_skips_bearish_touch(self):
        # gap-through, level (support 23900) च्या स्पष्टपणे खाली स्थिरावली -> direction=BEARISH
        candles_gap = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 23750, "high": 23820, "low": 23700, "close": 23780},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
        settings["bearish_entry_enabled"] = False
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_gap), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr.cloud_db, "save_market_zones", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_BEARISH_ENTRY_DISABLED" in statuses

    def test_defaults_both_enabled_allows_trade(self):
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called


class TestProcessSymbolMultiAccount:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा (per-strategy Broker Selection) — आता "कुठलेही broker_accounts
    नोंदवलेले असतील तर सर्व सक्रिय accounts" ऐवजी, settings मधल्याच broker_account_ids (वापरकर्त्याने
    याच strategy+symbol साठी स्पष्ट निवडलेले) असतील तरच execute_trade_on_all_accounts() (replicated)
    वापरलं जातं."""

    def test_uses_multi_account_when_broker_account_ids_selected(self):
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        settings_with_broker = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
        settings_with_broker["symbol_enabled"] = True
        settings_with_broker["broker_account_ids"] = ["A1"]
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy_type": "BULL_PUT_SPREAD", "legs": [], "net_credit": 35.0}), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings_with_broker), \
             patch("trading_engine.execute_trade_on_all_accounts", return_value=([{"account_id": "A1", "ok": True, "result": "OPENED"}], [])) as mock_multi, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "save_market_zones", return_value=True):
            result = dsr.process_symbol("fake_token", "NIFTY")
            assert mock_multi.called
            assert mock_multi.call_args.kwargs["account_ids"] == ["A1"]
            assert "A1" in result

    def test_uses_single_upstox_trade_when_no_broker_account_ids(self):
        """डीफॉल्ट (broker_account_ids रिकामी) — जुनंच शुद्ध Upstox, single trade वर्तन कायम."""
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy_type": "BULL_PUT_SPREAD", "legs": [], "net_credit": 35.0}), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch("trading_engine.execute_trade_on_all_accounts") as mock_multi, \
             patch.object(dsr, "open_multi_leg_trade", return_value=(True, "trade_id_123")) as mock_single, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "save_market_zones", return_value=True):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_multi.called
            assert mock_single.called
            assert mock_single.call_args.kwargs["trading_mode"] == "PAPER"


class TestInstantRsiFilter:
    """🎓 वापरकर्त्याशी चर्चा करून जोडलेला RSI फिल्टर — Support touch + RSI<40 -> Bull Put Spread,
    Resistance touch + RSI>60 -> Bear Call Spread."""

    def test_bullish_passes_with_low_rsi(self):
        df = _candles_with_rsi([], declining=True)
        passed, rsi_value = dsr.check_instant_rsi_filter(df, "BULLISH")
        assert passed is True
        assert rsi_value < 40

    def test_bullish_fails_with_high_rsi(self):
        df = _candles_with_rsi([], declining=False)
        passed, rsi_value = dsr.check_instant_rsi_filter(df, "BULLISH")
        assert passed is False
        assert rsi_value > 60

    def test_bearish_passes_with_high_rsi(self):
        df = _candles_with_rsi([], declining=False)
        passed, rsi_value = dsr.check_instant_rsi_filter(df, "BEARISH")
        assert passed is True
        assert rsi_value > 60

    def test_bearish_fails_with_low_rsi(self):
        df = _candles_with_rsi([], declining=True)
        passed, rsi_value = dsr.check_instant_rsi_filter(df, "BEARISH")
        assert passed is False
        assert rsi_value < 40

    def test_entry_skipped_when_rsi_wrong_direction(self):
        """गाभा टेस्ट — Support ला स्पर्श झाला, पण RSI जास्त (चढता trend) असल्यामुळे entry
        दुर्लक्षित व्हायला हवी."""
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=False, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))  # entry च्या उलट दिशा
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log:
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_RSI_FILTER" in statuses



def _fake_zones_5m_only():
    """फक्त 5M level (1M नाही) -- pooling तपासण्यासाठी. Level आणि candles established
    working (_fake_zones()) पॅटर्नशी सुसंगत ठेवलेला (RSI दिशा योग्य राहावी म्हणून)."""
    return pd.DataFrame([
        {"symbol": "NIFTY", "zone_type": "DYNAMIC_SR_SUPPORT_5M", "zone_low": 23900.0, "zone_high": 23900.0,
         "strength": 3.0, "formed_date": "2026-09-01", "status": "ACTIVE"},
    ])


class TestPooled1MAnd5M:
    """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Bot Dynamic SR Algo -- नवीन नियम-संच) -- 1M आणि 5M
    दोन्ही levels एकत्र, first-touch-wins."""

    def test_5m_only_level_still_triggers_entry(self):
        """फक्त 5M level ला (1M नाही) touch झाला, तरी trade व्हायला हवा."""
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones_5m_only()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "fetch_option_expiries", return_value=[]), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T70"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            result = dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called
            assert "5M" in result
            assert mock_trade.call_args.kwargs.get("entry_timeframe") == "5M"

    def test_open_multi_leg_trade_receives_actual_entry_spot_not_level_price(self):
        """🎓 वापरकर्त्याने मागितलेली सुधारणा ("Break even TSL activation condition calculation
        respect to entry price, not to level price") — open_multi_leg_trade() ला entry_level_price
        (row["zone_low"], इथे 23900 — S/R zone) सोबतच, प्रत्यक्ष entry-वेळचा spot (option chain मधला
        underlying_spot_price, इथे 23902.0 — level पेक्षा वेगळा) entry_spot_price म्हणून वेगळा
        पाठवला जायलाच हवा."""
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones_5m_only()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "fetch_option_expiries", return_value=[]), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T71"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called
            assert mock_trade.call_args.kwargs.get("entry_level_price") == 23900.0  # row["zone_low"] (5M zone)
            assert mock_trade.call_args.kwargs.get("entry_spot_price") == 23902.0  # प्रत्यक्ष chain spot, level पेक्षा वेगळा


class TestNakedOptionTrade:
    """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Naked Option Trade / "Long With Hedge") --
    Credit Spread सोबतच, समांतर, डीफॉल्ट सक्रिय."""

    def test_naked_trade_fires_alongside_spread_by_default(self):
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "fetch_option_expiries", return_value=[]), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "select_naked_option_itm", return_value={"strategy": "NAKED_CALL", "buy_leg": {"strike": 23850, "instrument_key": "CE1", "ltp": 60}, "net_credit": -60}) as mock_naked_select, \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T71"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_naked_select.called
            assert mock_trade.call_count == 2  # स्प्रेड + Naked दोन्ही

    def test_naked_trade_skipped_when_disabled_in_settings(self):
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        disabled_settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
        disabled_settings["naked_enabled"] = False
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr.cloud_db, "get_strategy_settings", return_value=disabled_settings), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "fetch_option_expiries", return_value=[]), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "select_naked_option_itm") as mock_naked_select, \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T72"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_naked_select.called
            assert mock_trade.call_count == 1  # फक्त स्प्रेड, Naked नाही

    def test_naked_lots_used_independently_from_spread_lots(self):
        """🎓 वापरकर्त्याने मागितलेली सुधारणा — Naked Option Trade आधी नेहमी Credit Spread च्याच
        "lots" इतकेच lots घ्यायचा (वेगळं सेटिंगच नव्हतं). आता स्वतंत्र "naked_lots" — दोन्ही वेगळे
        असतानाही प्रत्येक trade त्याच्याच स्वतःच्या lots सह उघडायला हवा."""
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        custom_settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
        custom_settings["symbol_enabled"] = True
        custom_settings["lots"] = 2
        custom_settings["naked_lots"] = 5
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=custom_settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "fetch_option_expiries", return_value=[]), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "select_naked_option_itm", return_value={"strategy": "NAKED_CALL", "buy_leg": {"strike": 23850, "instrument_key": "CE1", "ltp": 60}, "net_credit": -60}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T73"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.call_count == 2
            spread_call, naked_call = mock_trade.call_args_list
            assert spread_call.kwargs.get("lots") == 2
            assert naked_call.kwargs.get("lots") == 5


class TestCreditSpreadToggle:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा ("नेकेड ऑप्शन बाय हे ऑप्शनल आहे... क्रेडिट स्प्रेड सुद्धा
    ऑप्शनल ठेवा — कमी कॅपिटल असलेला user फक्त naked करणं पसंत करतो") — Credit Spread आता Naked
    Option प्रमाणेच स्वतंत्रपणे on/off करता येतो, डीफॉल्ट सक्रिय (backward-compatible)."""

    def test_credit_spread_disabled_only_naked_fires(self):
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        custom_settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
        custom_settings["credit_spread_enabled"] = False
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=custom_settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "fetch_option_expiries", return_value=[]), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "select_credit_spread_itm") as mock_spread_select, \
             patch.object(dsr, "select_naked_option_itm", return_value={"strategy": "NAKED_CALL", "buy_leg": {"strike": 23850, "instrument_key": "CE1", "ltp": 60}, "net_credit": -60}) as mock_naked_select, \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T80"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_save_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_spread_select.called
            assert mock_naked_select.called
            assert mock_trade.call_count == 1  # फक्त Naked, Spread नाही
            statuses = [c.args[0].get("trade_status") for c in mock_save_log.call_args_list]
            assert "SKIPPED_CREDIT_SPREAD_DISABLED" in statuses

    def test_both_disabled_no_trade_fires(self):
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        custom_settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
        custom_settings["credit_spread_enabled"] = False
        custom_settings["naked_enabled"] = False
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=custom_settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "fetch_option_expiries", return_value=[]), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "select_credit_spread_itm") as mock_spread_select, \
             patch.object(dsr, "select_naked_option_itm") as mock_naked_select, \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T81"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_spread_select.called
            assert not mock_naked_select.called
            assert not mock_trade.called

    def test_credit_spread_enabled_by_default(self):
        """डीफॉल्ट settings मध्ये credit_spread_enabled नसेल (जुनं stored settings row) तरी True
        गृहीत धरलं जावं — backward-compatible."""
        settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
        assert settings.get("credit_spread_enabled", True) is True


class TestSlTslCooldown:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा ("Same level war pahilya trade cha sl tsl hit jhalyas
    kiman 15 minute same level war trade ghewu naye, cooldown") — established generic 30-मिनिट
    cooldown (कुठल्याही exit-प्रकारावर, entry-वेळेवर आधारित) च्या पलीकडचा, थेट exit-वेळेवर
    (live_trades.exit_time) आधारित, फक्त SL/TSL exits साठीच लागू होणारा स्वतंत्र गेट."""

    def test_recent_sl_exit_on_same_level_blocks_trade(self):
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        recent_sl_exit = datetime.datetime(2026, 9, 11, 10, 0, 0) - datetime.timedelta(minutes=1)
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(1, None, None)), \
             patch.object(dsr, "get_last_sl_tsl_exit_time", return_value=recent_sl_exit) as mock_sl_exit:
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            assert mock_sl_exit.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_SL_TSL_COOLDOWN" in statuses

    def test_sl_exit_older_than_cooldown_allows_trade(self):
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        old_sl_exit = datetime.datetime(2026, 9, 11, 10, 0, 0) - datetime.timedelta(minutes=20)
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "fetch_option_expiries", return_value=[]), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "select_naked_option_itm", return_value={"strategy": "NAKED_CALL", "buy_leg": {"strike": 23850, "instrument_key": "CE1", "ltp": 60}, "net_credit": -60}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T90"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(1, None, None)), \
             patch.object(dsr, "get_last_sl_tsl_exit_time", return_value=old_sl_exit):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called

    def test_no_prior_sl_exit_allows_trade(self):
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "fetch_option_expiries", return_value=[]), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "select_naked_option_itm", return_value={"strategy": "NAKED_CALL", "buy_leg": {"strike": 23850, "instrument_key": "CE1", "ltp": 60}, "net_credit": -60}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T91"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(1, None, None)), \
             patch.object(dsr, "get_last_sl_tsl_exit_time", return_value=None):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called

    def test_zero_cooldown_setting_disables_gate(self):
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        recent_sl_exit = datetime.datetime(2026, 9, 11, 10, 0, 0) - datetime.timedelta(minutes=1)
        custom_settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
        custom_settings["sl_tsl_cooldown_minutes"] = 0
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=custom_settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "fetch_option_expiries", return_value=[]), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "select_naked_option_itm", return_value={"strategy": "NAKED_CALL", "buy_leg": {"strike": 23850, "instrument_key": "CE1", "ltp": 60}, "net_credit": -60}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T92"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(1, None, None)), \
             patch.object(dsr, "get_last_sl_tsl_exit_time", return_value=recent_sl_exit) as mock_sl_exit:
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called
            assert not mock_sl_exit.called  # gate बंद असल्याने query सुद्धा केली जाऊ नये


class TestExpiryDayLogic:
    """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Expiry-Day Logic) -- आज expiry असेल, तर पुढच्या
    आठवड्याची expiry (expiry_index=1) वापरायला हवी."""

    def test_expiry_day_uses_next_expiry_index(self):
        today_str = datetime.datetime(2026, 9, 11, 10, 0, 0).strftime("%Y-%m-%d")
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_option_expiries", return_value=[today_str]), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")) as mock_chain, \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T73"}, "OPENED")), \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_chain.call_args.kwargs.get("expiry_index") == 1

    def test_is_todays_expiry_day_true(self):
        today_str = dsr.get_ist_now().strftime("%Y-%m-%d")
        with patch.object(dsr, "fetch_option_expiries", return_value=[today_str]):
            assert dsr.is_todays_expiry_day("fake_token", "NIFTY") is True

    def test_is_todays_expiry_day_false(self):
        with patch.object(dsr, "fetch_option_expiries", return_value=["2099-01-01"]):
            assert dsr.is_todays_expiry_day("fake_token", "NIFTY") is False

class TestPCRGate:
    """वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (PCR Gate) — दोन्ही trade-प्रकारांना (Spread+Naked)
    एकत्र लागू, RSI नंतर लगेच."""

    def test_pcr_gate_blocks_entry(self):
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "check_pcr_gate", return_value=(False, 0.72, "PCR 0.72 < 0.80")), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_PCR_GATE" in statuses

    def test_pcr_gate_allows_entry_when_passed(self):
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T90"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called


class TestIvGate:
    """🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा (Average IV Breakout Gate — "5 minute instant
    dynamic sr strategy work better in sideways, low iv or average iv market, but in trending when
    Breakout happen it books loss") — RSI/PCR च्याच established pattern ने, डीफॉल्ट बंद असल्याने
    इथेच explicitly entry_iv_gate_enabled=True settings override करूनच तपासलं जातं."""

    def _iv_gate_enabled_settings(self):
        settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
        settings["entry_iv_gate_enabled"] = True
        settings["iv_change_max_pct"] = 15.0
        settings["iv_lookback_days"] = 10
        return settings

    def test_disabled_by_default_never_calls_iv_gate(self):
        """डीफॉल्ट settings मध्ये entry_iv_gate_enabled=False -- check_iv_change_gate() अजिबात
        call व्हायला नको (उगाच iv_history query होऊ नये)."""
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "check_iv_change_gate") as mock_iv_gate, \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T91"}, "OPENED")), \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_iv_gate.called

    def test_iv_gate_blocks_entry_when_data_unavailable_fail_safe(self):
        """🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा (Directional Flip — "In trending I want to
        block reversals trade, but trending trade should be continue") — IV डेटाच उपलब्ध नाही/जुना
        आहे (change_pct is None, regime माहीतच नाही) तेव्हाच पूर्वीसारखं fail-safe skip -- flip नाही
        (अनिश्चित दिशेने directional bet घेणं धोकादायक)."""
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=self._iv_gate_enabled_settings()), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "check_iv_change_gate", return_value=(False, None, "IV डेटा उपलब्ध नाही")), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_IV_GATE" in statuses

    def test_iv_breakout_flips_direction_and_skips_rsi_pcr_instead_of_blocking(self):
        """🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा ("In trending I want to block reversals
        trade, but trending trade should be continue") — खरा IV breakout आढळला (change_pct दिलेला)
        तर trade skip न होता, उलट दिशेने (मूळ signal BULLISH होता -> BEARISH) directional trade
        घेतला जायला हवा, आणि RSI/PCR Gate मुद्दामच वगळले जायला हवेत (call च होता कामा नये)."""
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=self._iv_gate_enabled_settings()), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "check_instant_rsi_filter") as mock_rsi_gate, \
             patch.object(dsr, "check_pcr_gate") as mock_pcr_gate, \
             patch.object(dsr, "check_iv_change_gate", return_value=(False, 32.0, "IV breakout — entry थांबवली")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BEAR_CALL_SPREAD", "legs": []}) as mock_select, \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T94"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called
            assert not mock_rsi_gate.called
            assert not mock_pcr_gate.called
            # मूळ touch-signal दिशा BULLISH (support, घसरत खाली येऊन touch) होती -- flip नंतर BEARISH
            assert mock_select.call_args.args[1] == "BEARISH"
            entries = [c.args[0] for c in mock_log.call_args_list]
            directional_entries = [e for e in entries if e.get("direction") == "BEARISH" and "Directional" in (e.get("reason") or "")]
            assert len(directional_entries) == 1
            assert "32.0" in directional_entries[0]["reason"] or "+32.0" in directional_entries[0]["reason"]

    def test_iv_gate_allows_entry_when_enabled_and_passing(self):
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=self._iv_gate_enabled_settings()), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "check_iv_change_gate", return_value=(True, 5.0, "IV गेट पास")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T92"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called

    def test_iv_gate_checked_with_settings_threshold_and_lookback(self):
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        custom_settings = self._iv_gate_enabled_settings()
        custom_settings["iv_change_max_pct"] = 20.0
        custom_settings["iv_lookback_days"] = 5
        custom_settings["iv_marubozu_threshold"] = 0.65
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=custom_settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "check_iv_change_gate", return_value=(True, 5.0, "IV गेट पास")) as mock_iv_gate, \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T93"}, "OPENED")), \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            mock_iv_gate.assert_called_once_with("NIFTY", 20.0, 5, 0.65)


def _breakout_5m_candles(consolidation_closes, final_close, today_ist=None):
    """5-मिनिट candles fixture (Breakout Entry च्या consolidation (C) + candle-close तपासणीसाठी).
    consolidation_closes: शेवटच्या (breakout-confirm) candle च्या आधीच्या window closes (जुनं ते
    नवीन), final_close: शेवटचा (breakout-confirm) candle चा close."""
    today_ist = (today_ist or dsr.get_ist_now()).replace(hour=10, minute=0, second=0, microsecond=0)
    all_closes = list(consolidation_closes) + [final_close]
    rows = []
    prev = all_closes[0]
    for c in all_closes:
        rows.append({"open": prev, "high": max(prev, c) + 5, "low": min(prev, c) - 5, "close": c})
        prev = c
    timestamps = pd.date_range(end=today_ist, periods=len(rows), freq="5min")
    df = pd.DataFrame(rows)
    df["timestamp"] = timestamps
    return df


class TestBreakoutEntry:
    """🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा (Breakout Entry — "Max 2 trade on same level hit,
    he honar donhi sl or tsl hit jhalet, ani nantr jar Breakout buildup and 5 minute candle closed
    happen then take entry in the same direction") — established max-2-hits च्या पलीकडचा, तिसरा
    trade. मूळ touch-signal (support, 23900) BULLISH आहे -- breakout confirm झाला तर BEARISH.
    "buildup" ata purnpane price-data varun (A: hit_count_so_far>=2 आधीच given, C: price
    consolidation — confirmed lookback_candles=12 (1 तास, "kiman 12 candle chi range" — वापरकर्त्याने
    कडवलेलं), tolerance_pct=0.30)."""

    LEVEL = 23900.0
    # 12 candles (1 तास) -- सगळे ±0.30% (≈71.7 points) च्या आत
    CONSOLIDATED_WINDOW = [
        23880.0, 23910.0, 23895.0, 23905.0, 23890.0, 23900.0,
        23885.0, 23915.0, 23898.0, 23902.0, 23890.0, 23900.0,
    ]
    NOT_CONSOLIDATED_WINDOW = [
        23880.0, 23910.0, 23895.0, 23905.0, 23890.0, 23900.0,
        23885.0, 23700.0, 23898.0, 23902.0, 23890.0, 23900.0,
    ]  # 23700 बाहेर

    def _touch_candles(self):
        touch_rows = [
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ]
        return _candles_with_rsi(touch_rows, declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))

    def _breakout_gate_settings(self):
        settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
        settings["entry_breakout_gate_enabled"] = True
        return settings

    def _fetch_candles_side_effect(self, consolidation_closes, final_close):
        def _fake(token, symbol, current_spot=0, interval="1minute", lookback_days=1):
            if interval == "5minute":
                return _breakout_5m_candles(consolidation_closes, final_close, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
            return self._touch_candles()
        return _fake

    def test_disabled_by_default_still_skips_at_max_hits(self):
        """डीफॉल्ट settings मध्ये entry_breakout_gate_enabled=False -- established वर्तन (skip)
        तसंच राहायला हवं, 5-मिनिट candles साठी fetch_candles अजिबात call व्हायला नको."""
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=self._touch_candles()) as mock_fetch, \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(2, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            assert all(c.kwargs.get("interval", "1minute") != "5minute" for c in mock_fetch.call_args_list)
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_MAX_2_HITS_REACHED" in statuses

    def test_enabled_but_no_consolidation_skips(self):
        """Gate चालू, candle level च्या पलीकडे decisively close झाला तरी -- price आधी level जवळ
        consolidate न झाल्याने (C fails) buildup चा पुरावा नाही, skip व्हायला हवं."""
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=self._breakout_gate_settings()), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", side_effect=self._fetch_candles_side_effect(self.NOT_CONSOLIDATED_WINDOW, 23800.0)), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(2, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_MAX_2_HITS_REACHED" in statuses

    def test_consolidated_but_candle_not_closed_beyond_skips(self):
        """Price consolidate झाला (C pass), पण शेवटचा candle level च्या पलीकडे निर्णायकपणे close
        झाला नाही -- अजूनही skip."""
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=self._breakout_gate_settings()), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", side_effect=self._fetch_candles_side_effect(self.CONSOLIDATED_WINDOW, 23905.0)), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(2, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_MAX_2_HITS_REACHED" in statuses

    def test_consolidation_and_candle_close_confirmed_fires_breakout_trade(self):
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=self._breakout_gate_settings()), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", side_effect=self._fetch_candles_side_effect(self.CONSOLIDATED_WINDOW, 23800.0)), \
             patch.object(dsr, "check_instant_rsi_filter") as mock_rsi_gate, \
             patch.object(dsr, "check_pcr_gate") as mock_pcr_gate, \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23800.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BEAR_CALL_SPREAD", "legs": []}) as mock_select, \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T95"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(2, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called
            assert not mock_rsi_gate.called
            assert not mock_pcr_gate.called
            # मूळ दिशा (support, 23900) BULLISH होती -- breakout confirm झाल्याने BEARISH
            assert mock_select.call_args.args[1] == "BEARISH"
            entries = [c.args[0] for c in mock_log.call_args_list]
            breakout_entries = [e for e in entries if e.get("direction") == "BEARISH" and "Breakout Entry" in (e.get("reason") or "")]
            assert len(breakout_entries) == 1

    def test_breakout_trade_skips_30min_cooldown(self):
        """established cooldown (last_trade_time वरून) breakout trade ला अडवता कामा नये -- मुद्दामच
        लगेच यायला हवं (2ऱ्या SL/TSL नंतर लवकरच, 5-मिनिट candle close होताच)."""
        recent_trade_time = datetime.datetime(2026, 9, 11, 9, 55, 0)  # फक्त 5 मिनिटांपूर्वी
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=self._breakout_gate_settings()), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", side_effect=self._fetch_candles_side_effect(self.CONSOLIDATED_WINDOW, 23800.0)), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23800.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BEAR_CALL_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T96"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(2, None, recent_trade_time)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called

    def test_breakout_trade_still_blocked_when_position_already_open(self):
        """established has_open_trade_from_source() सुरक्षा-तपासणी breakout trade लाही लागू व्हायला
        हवी (कुठल्याही overlapping position ला)."""
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=self._breakout_gate_settings()), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", side_effect=self._fetch_candles_side_effect(self.CONSOLIDATED_WINDOW, 23800.0)), \
             patch.object(dsr, "has_open_trade_from_source", return_value=True), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(2, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_PREVIOUS_POSITION_STILL_OPEN" in statuses

    def test_uses_settings_lookback_and_tolerance(self):
        """breakout_lookback_candles/breakout_tolerance_pct Dashboard settings वरून घेतले जायला
        हवेत (hardcoded नाही) -- कमी lookback (2) + tight tolerance मुळे 12-candle consolidated
        window सुद्धा वेगळ्या पद्धतीने evaluate व्हायला हवा."""
        settings = self._breakout_gate_settings()
        settings["breakout_lookback_candles"] = 2
        settings["breakout_tolerance_pct"] = 0.05  # खूप कडक -- 23890/23900 (शेवटचे 2, breakout आधीचे) सुद्धा नापास होतील अशी अपेक्षा नाही कारण ते level च्या जवळच आहेत
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", side_effect=self._fetch_candles_side_effect(self.CONSOLIDATED_WINDOW, 23800.0)), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23800.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BEAR_CALL_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T97"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(2, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            # lookback=2 -> फक्त शेवटचे 2 (23890, 23900) window मध्ये, दोन्ही level च्या अगदी जवळ
            # (0.05% tolerance मध्येही) -- त्यामुळे तरीही trade व्हायला हवा.
            assert mock_trade.called


class TestRunAllSymbols:
    """🎓 पूर्व-live रिव्ह्यूत सापडवलेली bug — एका symbol मधल्या अनपेक्षित exception मुळे उरलेले
    symbols त्याच cycle मध्ये कधीच तपासलेच जायचे नाहीत (loop तिथेच थांबायचा), आणि heartbeat/अलर्टही
    कधीच पोहोचायचा नाही. आता प्रत्येक symbol स्वतंत्र, एकाची चूक बाकीच्यांना अडवत नाही."""

    def test_one_symbol_exception_does_not_block_the_rest(self, monkeypatch):
        calls = []

        def fake_process_symbol(token, symbol):
            calls.append(symbol)
            if symbol == "BANKNIFTY":
                raise RuntimeError("database is locked")
            return f"{symbol}: ok"

        monkeypatch.setattr(dsr, "process_symbol", fake_process_symbol)
        mock_notify = MagicMock()
        monkeypatch.setattr(dsr, "notify_error", mock_notify)

        result = dsr.run_all_symbols("fake_token", ["NIFTY", "BANKNIFTY", "SENSEX"])

        assert calls == ["NIFTY", "BANKNIFTY", "SENSEX"]  # तिन्ही तपासले गेले, BANKNIFTY च्या अपयशानंतरही
        assert result is True  # किमान एक (NIFTY/SENSEX) यशस्वी झाला
        assert mock_notify.called
        assert "BANKNIFTY" in mock_notify.call_args.args[1]

    def test_all_symbols_failing_returns_false(self, monkeypatch):
        def fake_process_symbol(token, symbol):
            raise RuntimeError("boom")

        monkeypatch.setattr(dsr, "process_symbol", fake_process_symbol)
        monkeypatch.setattr(dsr, "notify_error", MagicMock())

        result = dsr.run_all_symbols("fake_token", ["NIFTY", "BANKNIFTY"])
        assert result is False  # heartbeat लिहू नये
