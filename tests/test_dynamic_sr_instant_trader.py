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
        candles = [{"close": 23880.0}, {"close": 23950.0}]
        assert dsr.check_breakout_candle_close(self.LEVEL, "BULLISH", candles) is True

    def test_bullish_breakout_not_confirmed_when_close_still_below(self):
        candles = [{"close": 23880.0}, {"close": 23895.0}]
        assert dsr.check_breakout_candle_close(self.LEVEL, "BULLISH", candles) is False

    def test_bearish_breakout_confirmed_when_close_below_level(self):
        candles = [{"close": 23920.0}, {"close": 23850.0}]
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

    def test_barely_beyond_level_within_default_buffer_not_confirmed(self):
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा ("5 minute candle close Breakout beyond
        0.10%") — नुसतं काठावर (level पासून buffer% पेक्षा कमी अंतरावर) close होणं पुरेसं नाही --
        डीफॉल्ट buffer_pct=0.10% म्हणजे 23900 साठी ≈23.9 पॉइंट्स, त्यापेक्षा कमी अंतर confirm नाही
        (0.010% वरून वाढवलेला, वापरकर्त्याशी चर्चा करून)."""
        candles = [{"close": 23910.0}]  # फक्त 10.0 पॉइंट पलीकडे (buffer ≈23.9 च्या आत)
        assert dsr.check_breakout_candle_close(self.LEVEL, "BULLISH", candles) is False
        candles_bearish = [{"close": 23890.0}]
        assert dsr.check_breakout_candle_close(self.LEVEL, "BEARISH", candles_bearish) is False

    def test_beyond_default_buffer_confirmed(self):
        """buffer_pct (डीफॉल्ट 0.10%, ≈23.9 पॉइंट्स 23900 साठी) पेक्षा जास्त अंतराने close झाला
        तर मात्र confirm व्हायला हवा."""
        candles = [{"close": 23930.0}]  # 30.0 पॉइंट पलीकडे, buffer (≈23.9) पेक्षा जास्त
        assert dsr.check_breakout_candle_close(self.LEVEL, "BULLISH", candles) is True

    def test_custom_buffer_pct_used_not_hardcoded(self):
        """buffer_pct Dashboard settings वरून घेतला जायला हवा (hardcoded नाही) -- buffer_pct=0
        दिलं की जुनं (कुठलाही buffer नसलेलं) strict > / < वर्तन परत यायला हवं."""
        candles = [{"close": 23900.5}]
        assert dsr.check_breakout_candle_close(self.LEVEL, "BULLISH", candles, buffer_pct=0.0) is True
        assert dsr.check_breakout_candle_close(self.LEVEL, "BULLISH", candles, buffer_pct=0.010) is False


class TestCheckBreakoutVolumeConfirmation:
    """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा ("5 minute Breakout candle + Volume ashi condition
    ठेवता yeil") — breakout-confirm करणाऱ्या candle चा volume, त्याआधीच्या lookback_candles च्या
    सरासरीपेक्षा किमान multiplier पट जास्त आहे का."""

    def _candles(self, prior_volumes, final_volume):
        return [{"volume": v} for v in prior_volumes] + [{"volume": final_volume}]

    def test_confirmed_when_volume_exceeds_multiplier(self):
        # मागचे 10 candles सरासरी volume 100, शेवटचा 200 (2x, 1.5x पेक्षा जास्त)
        candles = self._candles([100] * 10, 200)
        assert dsr.check_breakout_volume_confirmation(candles, lookback_candles=10, multiplier=1.5) is True

    def test_not_confirmed_when_volume_below_multiplier(self):
        # शेवटचा फक्त 120 (1.2x, 1.5x पेक्षा कमी)
        candles = self._candles([100] * 10, 120)
        assert dsr.check_breakout_volume_confirmation(candles, lookback_candles=10, multiplier=1.5) is False

    def test_exactly_at_multiplier_confirmed(self):
        # शेवटचा नेमका 150 (1.5x, >= असल्याने confirm)
        candles = self._candles([100] * 10, 150)
        assert dsr.check_breakout_volume_confirmation(candles, lookback_candles=10, multiplier=1.5) is True

    def test_insufficient_history_returns_false(self):
        """lookback_candles इतका इतिहासच नसेल (उदा. दिवसाच्या सुरुवातीला), तर fail-safe False."""
        candles = self._candles([100] * 5, 500)  # फक्त 5 prior, 10 हवेत
        assert dsr.check_breakout_volume_confirmation(candles, lookback_candles=10, multiplier=1.5) is False

    def test_empty_candles_returns_false(self):
        assert dsr.check_breakout_volume_confirmation([], lookback_candles=10, multiplier=1.5) is False

    def test_zero_average_volume_returns_false(self):
        """सरासरी volume शून्य (डेटा गहाळ/चुकीचा) असेल तर division-by-zero टाळून सुरक्षित False."""
        candles = self._candles([0] * 10, 500)
        assert dsr.check_breakout_volume_confirmation(candles, lookback_candles=10, multiplier=1.5) is False

    def test_only_prior_window_averaged_not_final_candle(self):
        """सरासरी फक्त breakout-candle च्या **आधीच्या** window मधूनच काढली जायला हवी, शेवटचा candle
        सरासरीत मोजला जाऊ नये (नाहीतर स्वतःच स्वतःशी तुलना होईल)."""
        # prior सगळे 100, शेवटचा प्रचंड मोठा (10000) -- सरासरी अजूनही फक्त prior च्या 100 वरच आधारित असावी
        candles = self._candles([100] * 10, 10000)
        assert dsr.check_breakout_volume_confirmation(candles, lookback_candles=10, multiplier=1.5) is True

    def test_missing_volume_key_treated_as_zero(self):
        """volume key नसेल तर 0 गृहीत धरून सुरक्षित False (crash नाही)."""
        candles = [{"close": 23900.0} for _ in range(10)] + [{"close": 23950.0}]
        assert dsr.check_breakout_volume_confirmation(candles, lookback_candles=10, multiplier=1.5) is False


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


class TestCountConsecutiveTouchMinutes:
    """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा ("Minimum Level-Hold Duration Before Entry" —
    signal_log backtest वरून सापडलेल्या "level हिट होताच SL उडणं" पॅटर्नवर) — सद्य क्षणापासून मागे
    मोजत, level च्या touch-tolerance बफरमध्ये सलग किती (1-मिनिट) candles आहेत, हे मोजणारं शुद्ध
    फंक्शन. candles: जुनं ते नवीन क्रमाने."""

    LEVEL = 23900.0

    def _candles(self, lows_highs):
        return [{"low": lo, "high": hi} for lo, hi in lows_highs]

    def test_zero_when_last_candle_does_not_touch(self):
        candles = self._candles([(23895.0, 23905.0), (24000.0, 24010.0)])
        assert dsr.count_consecutive_touch_minutes(self.LEVEL, candles) == 0

    def test_counts_single_fresh_touch_as_one(self):
        candles = self._candles([(24000.0, 24010.0), (23898.0, 23901.0)])
        assert dsr.count_consecutive_touch_minutes(self.LEVEL, candles) == 1

    def test_counts_back_from_most_recent_consecutive_touches(self):
        candles = self._candles([
            (24000.0, 24010.0),  # touch नाही -- इथेच थांबायला हवं
            (23898.0, 23901.0),  # touch
            (23897.7, 23902.0),  # touch
            (23898.5, 23901.8),  # touch (सद्य क्षण)
        ])
        assert dsr.count_consecutive_touch_minutes(self.LEVEL, candles) == 3

    def test_old_touches_before_a_gap_not_counted(self):
        # सुरुवातीचे दोन touch जुने आहेत, मध्ये एक non-touch candle आल्याने सलगपणा तुटतो
        candles = self._candles([
            (23898.0, 23901.0),  # touch (जुना, सलग नाही -- मोजू नये)
            (23898.0, 23901.0),  # touch (जुना, सलग नाही -- मोजू नये)
            (24000.0, 24010.0),  # touch नाही -- सलगपणा तुटला
            (23898.0, 23901.0),  # touch (सद्य क्षणापासून सलग)
        ])
        assert dsr.count_consecutive_touch_minutes(self.LEVEL, candles) == 1

    def test_empty_candles_returns_zero(self):
        assert dsr.count_consecutive_touch_minutes(self.LEVEL, []) == 0

    def test_respects_custom_tolerance_pct(self):
        # level पासून 50 points दूर -- 0.01% (2.39 pts) बाहेर, पण 0.30% (71.7 pts) आत
        candles = self._candles([(23950.0, 23951.0)])
        assert dsr.count_consecutive_touch_minutes(self.LEVEL, candles, tolerance_pct=0.01) == 0
        assert dsr.count_consecutive_touch_minutes(self.LEVEL, candles, tolerance_pct=0.30) == 1


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

    def test_level_type_in_log_follows_hysteresis_direction_not_stale_zone_type(self):
        """🎓 वापरकर्त्याने सापडवलेली bug ("SR flip साठी hysteresis 0.10% ठेवला, त्यानुसार हा level
        resistance व्हायलाच नको होता") — Signal Log चा level_type (आणि role, hit-counting/Breakout
        Entry साठी) आता hysteresis-संरक्षित `direction` वरून ठरतो, `row["zone_type"]` (raw, DB-साठवलेला,
        merge-cron ने वारंवार बदलणारा) वरून नाही. _fake_zones() मधला 23900 चा zone_type SUPPORT_5M
        आहे, पण किंमत आता निर्णायकपणे त्याच्या खाली गॅप-डाऊन झालीये (जसं वरच्या gap-through टेस्ट मध्ये)
        -- त्यामुळे level_type/role आता RESISTANCE असायला हवा, stale SUPPORT नाही."""
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
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")), \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_market_zones", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log:
            dsr.process_symbol("fake_token", "NIFTY")
            logged_entries = [c.args[0] for c in mock_log.call_args_list]
            level_23900_entries = [e for e in logged_entries if e["level_price"] == 23900.0]
            assert level_23900_entries
            assert all(e["level_type"] == "DYNAMIC_SR_RESISTANCE_5M" for e in level_23900_entries)

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
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_market_zones", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True):
            result = dsr.process_symbol("fake_token", "NIFTY")
            assert "TOUCH" in result
            # 🎓 वापरकर्त्याने मागितलेली सुधारणा — प्लेन S/R touch trades साठी entry_reason_tag
            # None च राहायला हवा (Breakout Entry/IV Breakout Directional सारखा विशेष टॅग फक्त
            # त्या-त्या विशेष केसेससाठीच).
            assert mock_trade.call_args.kwargs.get("entry_reason_tag") is None

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

    def test_max_hits_per_zone_configurable_higher_limit_allows_third_hit(self):
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — max_hits_per_zone आता डॅशबोर्डवरून
        बदलता येतो. इथे तो ३ ठेवला आहे, त्यामुळे आधीच्या (hardcoded २ असलेल्या) चाचणीत जो
        तिसरा hit नाकारला जायचा, तोच आता (hit_count_so_far=2 असतानाही) trade घ्यायला हवा."""
        settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
        settings["max_hits_per_zone"] = 3
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=self._touch_setup()), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(2, get_ist_now(), None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called

    def test_max_hits_per_zone_configurable_lower_limit_skips_second_hit(self):
        """🎓 max_hits_per_zone=1 ठेवल्यावर, आधीच्या डीफॉल्ट-२ लॉजिकमध्ये परवानगी असलेला दुसरा
        hit (hit_count_so_far=1) सुद्धा आता नाकारला जायला हवा."""
        settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
        settings["max_hits_per_zone"] = 1
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=self._touch_setup()), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr, "send_telegram_message") as mock_telegram, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(1, get_ist_now(), get_ist_now())):
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


class TestMinHoldDurationGate:
    """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा ("Minimum Level-Hold Duration Before Entry" —
    Performance Report वरून सापडलेल्या "level हिट होताच SL उडणं" या शंकेवरून, 3-दिवसांचा signal_log
    backtest केल्यावर) — RSI/PCR Gate दोन्ही मुद्दामच बंद ठेवून, फक्त या नवीन गेटचंच वर्तन तपासलं जातं."""

    def _base_settings(self, **overrides):
        settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
        settings["entry_rsi_gate_enabled"] = False
        settings["entry_pcr_gate_enabled"] = False
        settings.update(overrides)
        return settings

    def test_fresh_single_touch_skipped_when_gate_enabled(self):
        # शेवटचाच candle touch करतो (held=1 मिनिट), किमान 3 हवीत -- गेट skip करेल.
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        settings = self._base_settings(entry_min_hold_gate_enabled=True, entry_min_hold_minutes=3)
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
            assert "SKIPPED_MIN_HOLD_DURATION" in statuses

    def test_sufficiently_held_touch_allows_entry_when_gate_enabled(self):
        # शेवटचे 3 candles सलग touch करतात (held=3 मिनिटं), किमान 3 हवीत -- गेट पास होईल.
        candles_touch = _candles_with_rsi([
            {"open": 23899.0, "high": 23901.0, "low": 23898.0, "close": 23900.0},
            {"open": 23900.0, "high": 23902.0, "low": 23897.8, "close": 23899.0},
            {"open": 23899.0, "high": 23901.5, "low": 23898.2, "close": 23900.5},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        settings = self._base_settings(entry_min_hold_gate_enabled=True, entry_min_hold_minutes=3)
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23900.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called

    def test_disabled_by_default_does_not_block_fresh_touch(self):
        # गेट डीफॉल्ट-बंद असल्याने, held=1 मिनिट असूनही (वरच्या पहिल्या test सारखाच touch) trade होतो.
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        settings = self._base_settings()  # entry_min_hold_gate_enabled डीफॉल्ट False च राहतो
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called

    def test_gap_through_also_blocked_when_held_zero(self):
        """🎓 वापरकर्त्याशी चर्चा करून ठरवलेला निर्णय — सकाळी बाजार उघडताच gap-down/gap-up होऊन
        आधीच साठवलेल्या level च्या पार गेलं, तर तो सगळ्यात अस्थिर, अपुष्ट क्षण असतो — त्याला सूट न देता
        TOUCH प्रमाणेच held_minutes ची अट लावायला हवी. GAP_THROUGH साठी held कायम 0 राहतो (hit candle
        स्वतःच tolerance बफरमध्ये कधीच overlap होत नाही), त्यामुळे गेट चालू असताना threshold>=1 असेल
        तर असा gap entry ला नेहमीच अडवायला हवा — जोपर्यंत किंमत level जवळ खरोखर टिकून (TOUCH होऊन)
        राहत नाही तोपर्यंत."""
        candles_gap = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 23750, "high": 23820, "low": 23700, "close": 23780},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        settings = self._base_settings(entry_min_hold_gate_enabled=True, entry_min_hold_minutes=5)
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
            assert "SKIPPED_MIN_HOLD_DURATION" in statuses


class TestMinHoldFirstTradeOnly:
    """🎓 "level ला आज पहिल्यांदा touch झाल्यावर 3 मिनिट hold अट, त्याच level च्या 2ऱ्या trade साठी नको" —
    गेट फक्त त्या level (+role) वर आज पहिला खरा trade होईपर्यंत; नाकारलेला touch 'पहिला trade' नाही."""

    NOW = datetime.datetime(2026, 9, 11, 10, 0, 0)
    EARLIER_TRADE = datetime.datetime(2026, 9, 11, 9, 20, 0)  # 40 मिनिटं आधी (30-मिनिट cooldown पार)

    def _run(self, hits, **setting_overrides):
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=self.NOW)  # held=1 मिनिट
        settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
        settings.update(entry_rsi_gate_enabled=False, entry_pcr_gate_enabled=False,
                        entry_min_hold_gate_enabled=True, entry_min_hold_minutes=3)
        settings.update(setting_overrides)
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=self.NOW), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=hits):
            dsr.process_symbol("fake_token", "NIFTY")
        statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
        return mock_trade, statuses

    def test_default_is_first_trade_only(self):
        assert cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"]["entry_min_hold_first_trade_only"] is True

    def test_first_trade_on_level_still_gated(self):
        mock_trade, statuses = self._run((0, None, None))
        assert not mock_trade.called
        assert "SKIPPED_MIN_HOLD_DURATION" in statuses

    def test_rejected_touch_is_not_a_first_trade(self):
        # touch झाला (hit_count=1) पण खरा trade कधीच झाला नाही (last_trade_time=None) -> गेट अजूनही लागू
        mock_trade, statuses = self._run((1, self.EARLIER_TRADE, None))
        assert not mock_trade.called
        assert "SKIPPED_MIN_HOLD_DURATION" in statuses

    def test_second_trade_on_same_level_bypasses_gate(self):
        mock_trade, statuses = self._run((1, self.EARLIER_TRADE, self.EARLIER_TRADE))
        assert mock_trade.called
        assert "SKIPPED_MIN_HOLD_DURATION" not in statuses

    def test_flag_off_gates_second_trade_too(self):
        mock_trade, statuses = self._run((1, self.EARLIER_TRADE, self.EARLIER_TRADE), entry_min_hold_first_trade_only=False)
        assert not mock_trade.called
        assert "SKIPPED_MIN_HOLD_DURATION" in statuses


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

    def test_naked_option_uses_its_own_itm_depth_independent_of_credit_spread(self):
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा ("Credit Spread income strategy साठी ITM
        श्रेयस्कर, Naked Option स्वस्त 'lottery' buy साठी बरेचदा OTM श्रेयस्कर — दोन्हीसाठी एकच
        setting चुकीचं") — Credit Spread ITM (धन) आणि Naked Option त्याच वेळी OTM (ऋण) असं वेगवेगळं
        सेट केलं तरी, प्रत्येक select_*() फंक्शनला त्याचाच स्वतंत्र itm_depth_points मिळायला हवा."""
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        custom_settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
        custom_settings["itm_depth_points"] = 100          # Credit Spread -- ITM
        custom_settings["naked_itm_depth_points"] = -50    # Naked Option -- OTM
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr.cloud_db, "get_strategy_settings", return_value=custom_settings), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "fetch_option_expiries", return_value=[]), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}) as mock_spread_select, \
             patch.object(dsr, "select_naked_option_itm", return_value={"strategy": "NAKED_CALL", "buy_leg": {"strike": 23850, "instrument_key": "CE1", "ltp": 60}, "net_credit": -60}) as mock_naked_select, \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T72"}, "OPENED")), \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_spread_select.call_args.kwargs.get("itm_depth_points") == 100
            assert mock_naked_select.call_args.kwargs.get("itm_depth_points") == -50

    def test_naked_option_falls_back_to_credit_spread_itm_depth_when_unset(self):
        """जुनी (अजून customize न केलेली) settings नोंद — naked_itm_depth_points की नसेल, तर
        backward-compatible fallback म्हणून जुनाच itm_depth_points वापरला जायला हवा (वर्तन बदलत नाही)."""
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        legacy_settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
        legacy_settings["itm_depth_points"] = 75
        del legacy_settings["naked_itm_depth_points"]
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr.cloud_db, "get_strategy_settings", return_value=legacy_settings), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "fetch_option_expiries", return_value=[]), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "select_naked_option_itm", return_value={"strategy": "NAKED_CALL", "buy_leg": {"strike": 23850, "instrument_key": "CE1", "ltp": 60}, "net_credit": -60}) as mock_naked_select, \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T73"}, "OPENED")), \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_naked_select.call_args.kwargs.get("itm_depth_points") == 75

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
            # naked चा खरा निकाल signal_log मध्ये (cooldown/hit मोजणीसाठी), 'SKIPPED_*' शिक्का नाही
            assert "OPENED" in statuses
            assert "SKIPPED_CREDIT_SPREAD_DISABLED" not in statuses

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


class TestOtmShadowTrade:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा (OTM Shadow — "आधी 5-Min Instant Trader वर सुरू करा") —
    otm_shadow_enabled चालू असेल आणि टच "5M" चा असेल तरच, खऱ्या ITM trade सोबतच, एक स्वतंत्र निव्वळ
    PAPER trade (वेगळ्याच source ने) समांतर लॉग व्हायला हवा — डीफॉल्ट बंद असल्याने आणि 1M touches वर
    कधीच न फिरल्याने, हे मूळ ITM trade च्या (LIVE/PAPER) वर्तनावर कधीच परिणाम करता कामा नये."""

    def _settings_with_shadow(self, strikes_count=2):
        settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
        settings["otm_shadow_enabled"] = True
        settings["otm_shadow_strikes_count"] = strikes_count
        return settings

    def test_shadow_disabled_by_default_does_not_fire(self):
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
             patch.object(dsr, "select_credit_spread_fixed_strikes") as mock_otm_select, \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_otm_select.called
            assert mock_trade.call_count == 1  # फक्त खरा ITM trade, शॅडो नाही

    def test_shadow_enabled_5m_touch_fires_paper_shadow_trade(self):
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=self._settings_with_shadow()), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones_5m_only()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "fetch_option_expiries", return_value=[]), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "select_credit_spread_fixed_strikes",
                          return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}) as mock_otm_select, \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_otm_select.called
            assert mock_otm_select.call_args.kwargs.get("strikes_otm") == 2
            assert mock_trade.call_count == 2  # खरा ITM trade + शॅडो OTM trade

            shadow_call = mock_trade.call_args_list[-1]
            assert shadow_call.kwargs.get("source") == "dynamic_sr_instant_otm_shadow"
            assert shadow_call.kwargs.get("trading_mode") == "PAPER"
            assert shadow_call.kwargs.get("entry_timeframe") == "5M"

    def test_shadow_enabled_but_1m_touch_does_not_fire(self):
        """वापरकर्त्याच्या स्पष्ट सूचनेनुसार — सुरुवातीला फक्त "5-Min Instant Trader" (5M touches),
        1M touches वर शॅडो कधीच फिरता कामा नये."""
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        settings = self._settings_with_shadow()
        settings["timeframe_choice"] = "1M"
        zones_1m = pd.DataFrame([
            {"symbol": "NIFTY", "zone_type": "DYNAMIC_SR_SUPPORT_1M", "zone_low": 23900.0, "zone_high": 23900.0,
             "strength": 3.0, "formed_date": "2026-09-01", "status": "ACTIVE"},
        ])
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=zones_1m), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "fetch_option_expiries", return_value=[]), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "select_credit_spread_fixed_strikes") as mock_otm_select, \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_otm_select.called
            assert mock_trade.call_count == 1  # फक्त खरा ITM trade

    def test_shadow_exception_does_not_break_real_trade(self):
        """शॅडो trade मध्ये अपवाद (उदा. select_credit_spread_fixed_strikes क्रॅश) आला, तरी मूळ खरा
        ITM trade (आधीच यशस्वीपणे उघडलेला) प्रभावित होता कामा नये — फक्त शॅडो अयशस्वी व्हावा."""
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=self._settings_with_shadow()), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones_5m_only()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "fetch_option_expiries", return_value=[]), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "select_credit_spread_fixed_strikes", side_effect=RuntimeError("boom")), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            result = dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.call_count == 1  # खरा ITM trade फक्त एकदाच, अपवादामुळे थांबला नाही
            assert "OPENED" in result or "T1" in result

    def test_shadow_does_not_fire_when_real_trade_fails(self):
        """🎓 code-review द्वारे सापडवलेली bug — शॅडो आधी फक्त strike-selection यशस्वी झालं की पुरे
        मानायचा, खऱ्या ITM trade चा प्रत्यक्ष broker-निकाल (यश/अपयश) कधीच तपासायचा नाही. आता real_
        trade_succeeded तपासल्याशिवाय शॅडो फिरणारच नाही — खरा trade (उदा. Kill Switch मुळे) अयशस्वी
        झाला, तर शॅडोही थांबायला हवा."""
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=self._settings_with_shadow()), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones_5m_only()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "fetch_option_expiries", return_value=[]), \
             patch.object(dsr, "check_pcr_gate", return_value=(True, 0.95, "PCR गेट पास")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "select_credit_spread_fixed_strikes") as mock_otm_select, \
             patch.object(dsr, "open_multi_leg_trade",
                          return_value=(False, {"status": "error", "reason": "Kill Switch सक्रिय"})) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.call_count == 1  # फक्त खरा (अयशस्वी) प्रयत्न
            assert not mock_otm_select.called  # शॅडो कधीच फिरला नाही


class TestMinHoldShadowTrade:
    """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा ("Shadow entry PDF मध्ये दिसायला पाहिजे, 10 दिवस
    forward test करतो" — Min-Hold Duration Gate प्रत्यक्ष वापरण्याआधी, OTM Shadow च्याच सुरक्षित
    पॅटर्नने forward-test) — min_hold_shadow_enabled चालू असेल आणि त्या क्षणी held_minutes आधीच
    entry_min_hold_minutes इतका असेल तरच, खऱ्या ITM trade सोबतच, एक स्वतंत्र निव्वळ PAPER trade
    (वेगळ्याच source ने) समांतर लॉग व्हायला हवा — मूळ trade च्या वर्तनावर (blocking gate बंद असो वा
    चालू) कधीच परिणाम करता कामा नये."""

    def _shadow_settings(self, **overrides):
        settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
        settings["entry_rsi_gate_enabled"] = False
        settings["entry_pcr_gate_enabled"] = False
        settings.update(overrides)
        return settings

    def _held_1_minute_touch(self):
        # शेवटचाच candle touch करतो (held=1 मिनिट)
        return _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))

    def _held_3_minutes_touch(self):
        # शेवटचे 3 candles सलग touch करतात (held=3 मिनिटं)
        return _candles_with_rsi([
            {"open": 23899.0, "high": 23901.0, "low": 23898.0, "close": 23900.0},
            {"open": 23900.0, "high": 23902.0, "low": 23897.8, "close": 23899.0},
            {"open": 23899.0, "high": 23901.5, "low": 23898.2, "close": 23900.5},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))

    def test_shadow_disabled_by_default_does_not_fire(self):
        settings = self._shadow_settings()  # min_hold_shadow_enabled डीफॉल्ट False च राहतो
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones_5m_only()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=self._held_3_minutes_touch()), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23900.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.call_count == 1  # फक्त खरा ITM trade, शॅडो नाही

    def test_shadow_enabled_but_insufficient_hold_does_not_fire(self):
        settings = self._shadow_settings(min_hold_shadow_enabled=True, entry_min_hold_minutes=3)
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones_5m_only()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=self._held_1_minute_touch()), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.call_count == 1  # held=1 < 3 -- शॅडो फिरला नाही

    def test_shadow_enabled_and_sufficient_hold_fires_paper_shadow(self):
        settings = self._shadow_settings(min_hold_shadow_enabled=True, entry_min_hold_minutes=3)
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones_5m_only()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=self._held_3_minutes_touch()), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23900.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.call_count == 2  # खरा ITM trade + शॅडो trade

            shadow_call = mock_trade.call_args_list[-1]
            assert shadow_call.kwargs.get("source") == "dynamic_sr_instant_min_hold_shadow"
            assert shadow_call.kwargs.get("trading_mode") == "PAPER"

    def test_shadow_fires_even_when_blocking_gate_also_enabled(self):
        """entry_min_hold_gate_enabled (blocking) आणि min_hold_shadow_enabled दोन्ही चालू असले, तरी
        शॅडो स्वतंत्रपणे काम करतो -- एकमेकांत हस्तक्षेप नाही."""
        settings = self._shadow_settings(
            min_hold_shadow_enabled=True, entry_min_hold_gate_enabled=True, entry_min_hold_minutes=3,
        )
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones_5m_only()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=self._held_3_minutes_touch()), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23900.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.call_count == 2
            assert mock_trade.call_args_list[-1].kwargs.get("source") == "dynamic_sr_instant_min_hold_shadow"

    def test_shadow_does_not_stack_when_already_open(self):
        settings = self._shadow_settings(min_hold_shadow_enabled=True, entry_min_hold_minutes=3)

        def _fake_has_open(symbol, source):
            return source == "dynamic_sr_instant_min_hold_shadow"

        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones_5m_only()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=self._held_3_minutes_touch()), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23900.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "has_open_trade_from_source", side_effect=_fake_has_open), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.call_count == 1  # शॅडो आधीच उघडा -- नवीन stack झाला नाही

    def test_shadow_exception_does_not_break_real_trade(self):
        settings = self._shadow_settings(min_hold_shadow_enabled=True, entry_min_hold_minutes=3)
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones_5m_only()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=self._held_3_minutes_touch()), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23900.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade",
                          side_effect=[({"trade_id": "T1"}, "OPENED"), RuntimeError("boom")]) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            result = dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.call_count == 2  # शॅडो call झाला (आणि क्रॅश झाला), पण खरा आधीच यशस्वी
            assert "OPENED" in result or "T1" in result

    def test_shadow_does_not_fire_when_real_trade_fails(self):
        """🎓 code-review द्वारे सापडवलेली bug — शॅडो आधी फक्त held_minutes थ्रेशोल्ड पूर्ण झाला की
        पुरे मानायचा, खऱ्या ITM trade चा प्रत्यक्ष broker-निकाल कधीच तपासायचा नाही."""
        settings = self._shadow_settings(min_hold_shadow_enabled=True, entry_min_hold_minutes=3)
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones_5m_only()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=self._held_3_minutes_touch()), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23900.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade",
                          return_value=(False, {"status": "error", "reason": "Kill Switch सक्रिय"})) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.call_count == 1  # फक्त खरा (अयशस्वी) प्रयत्न, शॅडो फिरला नाही

    def test_shadow_does_not_fire_on_gap_through_despite_real_trade_succeeding(self):
        """🎓 वापरकर्त्याशी चर्चा करून ठरवलेला निर्णय — GAP_THROUGH साठी held_minutes कायम 0 राहतो
        (hit candle स्वतःच tolerance बफरमध्ये कधीच overlap होत नाही), आणि आता शॅडोतही याला सूट नाही —
        मूळ (blocking गेट बंद असल्याने अप्रभावित) खरा trade GAP_THROUGH वर नेहमीप्रमाणे उघडतो, पण
        शॅडो (confirmed-entry comparison) साठी held>=threshold कधीच खरं न झाल्याने शॅडो फिरतच नाही —
        सकाळचा अस्थिर gap शॅडोतही "confirmed" मानला जाऊ नये."""
        candles_gap = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 23750, "high": 23820, "low": 23700, "close": 23780},
        ], declining=True, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
        settings = self._shadow_settings(min_hold_shadow_enabled=True, entry_min_hold_minutes=5)
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones_5m_only()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=candles_gap), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23780.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BEAR_CALL_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_market_zones", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.call_count == 1  # फक्त खरा trade (blocking गेट बंद), शॅडो फिरलाच नाही


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


def _breakout_5m_candles(prior_closes, final_close, today_ist=None, volumes=None):
    """5-मिनिट candles fixture (Breakout Entry च्या candle-close/volume तपासणीसाठी) -- फक्त शेवटचा
    (breakout-confirm) candle चाच close तपासला जातो, prior_closes फक्त filler/context आहेत.
    final_close: शेवटचा (breakout-confirm) candle चा close. volumes: दिलं नाही तर सगळे 100
    (Volume Confirmation डीफॉल्ट बंद असल्याने बहुतेक टेस्ट्ससाठी अप्रस्तुत)."""
    today_ist = (today_ist or dsr.get_ist_now()).replace(hour=10, minute=0, second=0, microsecond=0)
    all_closes = list(prior_closes) + [final_close]
    volumes = volumes or [100] * len(all_closes)
    rows = []
    prev = all_closes[0]
    for c, v in zip(all_closes, volumes):
        rows.append({"open": prev, "high": max(prev, c) + 5, "low": min(prev, c) - 5, "close": c, "volume": v})
        prev = c
    timestamps = pd.date_range(end=today_ist, periods=len(rows), freq="5min")
    df = pd.DataFrame(rows)
    df["timestamp"] = timestamps
    return df


class TestBreakoutEntry:
    """🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा (Breakout Entry) — मूळ touch-signal (support, 23900)
    BULLISH आहे -- breakout confirm झाला तर BEARISH.

    🎓 वापरकर्त्याशी चर्चा करून सुधारलेला निर्णय ("Tya level war previous day che touches aahet, kiwa
    level Breakout jhali mhanun trade hit jhala pahije, ashi simple condition Breakout trade ka lagu
    kra, jast complex karu nka") — आधीची "आजचे दोन्ही touch (hit_count_so_far>=2) आधीच झालेले
    असावेत" ही पूर्वअट काढली — breakout आता कुठल्याही hit_count वर स्वतंत्र, फक्त candle-close या
    एकाच अटीवरच तपासला जातो. बहुतेक टेस्ट्स अजूनही hit_count_so_far=2 सह लिहिलेल्या आहेत (established
    max-2-hits वर्तन breakout-नसलेल्या touches साठी अजूनही तसंच आहे हे दाखवण्यासाठी) — त्याशिवाय खाली
    hit_count_so_far=0 सहचे स्वतंत्र टेस्ट्स (breakout hit-count-independent आहे हे स्पष्टपणे सिद्ध
    करण्यासाठी).

    🎓 वापरकर्त्याशी चर्चा करून सुधारलेला निर्णय ("Breakout sathi consolidation chi condition pn
    remove kra") — price consolidation ("buildup") ही अट सुद्धा काढली — आता फक्त candle-close
    buffer% (डीफॉल्ट 0.010%) हाच एकमेव निकष उरला आहे."""

    LEVEL = 23900.0
    # फक्त filler/context candles -- यांचं मूल्य आता तपासलं जात नाही, फक्त शेवटचा (final_close) candle बघितला जातो.
    PRIOR_CANDLES = [
        23880.0, 23910.0, 23895.0, 23905.0, 23890.0, 23900.0,
        23885.0, 23915.0, 23898.0, 23902.0, 23890.0, 23900.0,
    ]

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

    def _fetch_candles_side_effect(self, prior_closes, final_close):
        def _fake(token, symbol, current_spot=0, interval="1minute", lookback_days=1):
            if interval == "5minute":
                return _breakout_5m_candles(prior_closes, final_close, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
            return self._touch_candles()
        return _fake

    def _fetch_candles_side_effect_with_volume(self, prior_closes, final_close, prior_volumes, final_volume):
        def _fake(token, symbol, current_spot=0, interval="1minute", lookback_days=1):
            if interval == "5minute":
                return _breakout_5m_candles(
                    prior_closes, final_close, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0),
                    volumes=list(prior_volumes) + [final_volume],
                )
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

    def test_candle_not_closed_beyond_buffer_skips(self):
        """शेवटचा candle level च्या पलीकडे (buffer% इतका) निर्णायकपणे close झाला नाही -- skip."""
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=self._breakout_gate_settings()), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", side_effect=self._fetch_candles_side_effect(self.PRIOR_CANDLES, 23905.0)), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(2, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_MAX_2_HITS_REACHED" in statuses

    def test_candle_close_confirmed_fires_breakout_trade(self):
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=self._breakout_gate_settings()), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", side_effect=self._fetch_candles_side_effect(self.PRIOR_CANDLES, 23800.0)), \
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
             patch.object(dsr, "fetch_candles", side_effect=self._fetch_candles_side_effect(self.PRIOR_CANDLES, 23800.0)), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23800.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BEAR_CALL_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T96"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(2, None, recent_trade_time)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called

    def test_breakout_trade_tagged_in_entry_reason(self):
        """🎓 वापरकर्त्याने मागितलेली सुधारणा ("trade entry reason same disat aahe, actually trade
        3 ha Breakout trade aahe") — Breakout Entry trade open_multi_leg_trade() ला
        entry_reason_tag="BREAKOUT_ENTRY" सकट पास व्हायला हवा (Performance Report च्या Entry Reason
        स्तंभात दाखवण्यासाठी)."""
        recent_trade_time = datetime.datetime(2026, 9, 11, 9, 55, 0)
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=self._breakout_gate_settings()), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", side_effect=self._fetch_candles_side_effect(self.PRIOR_CANDLES, 23800.0)), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23800.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BEAR_CALL_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T97"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(2, None, recent_trade_time)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called
            assert mock_trade.call_args.kwargs.get("entry_reason_tag") == "BREAKOUT_ENTRY"

    def test_breakout_trade_still_blocked_when_position_already_open(self):
        """established has_open_trade_from_source() सुरक्षा-तपासणी breakout trade लाही लागू व्हायला
        हवी (कुठल्याही overlapping position ला)."""
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=self._breakout_gate_settings()), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", side_effect=self._fetch_candles_side_effect(self.PRIOR_CANDLES, 23800.0)), \
             patch.object(dsr, "has_open_trade_from_source", return_value=True), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(2, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_PREVIOUS_POSITION_STILL_OPEN" in statuses

    def test_uses_settings_close_buffer_pct(self):
        """breakout_close_buffer_pct Dashboard settings वरून घेतला जायला हवा (hardcoded नाही) --
        मोठा buffer (5%) दिला की, आधी पास होणारा close आता buffer च्या आत पडून skip व्हायला हवा."""
        settings = self._breakout_gate_settings()
        settings["breakout_close_buffer_pct"] = 5.0  # खूप मोठा -- 23800 (level 23900 पासून फक्त ~0.42%) आता buffer च्या आत
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", side_effect=self._fetch_candles_side_effect(self.PRIOR_CANDLES, 23800.0)), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(2, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_MAX_2_HITS_REACHED" in statuses

    def test_fires_even_when_hit_count_is_zero(self):
        """🎓 वापरकर्त्याशी चर्चा करून सुधारलेला निर्णय ("... ashi simple condition Breakout trade
        ka lagu kra, jast complex karu nka") — आजचा या level वर पहिलाच touch (hit_count_so_far=0)
        असला तरी, candle-close अट पूर्ण असेल तर breakout trade घेतला जायला हवा --
        hit_count_so_far>=2 ची जुनी पूर्वअट आता लागू नाही."""
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=self._breakout_gate_settings()), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", side_effect=self._fetch_candles_side_effect(self.PRIOR_CANDLES, 23800.0)), \
             patch.object(dsr, "check_instant_rsi_filter") as mock_rsi_gate, \
             patch.object(dsr, "check_pcr_gate") as mock_pcr_gate, \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23800.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BEAR_CALL_SPREAD", "legs": []}) as mock_select, \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T98"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called
            assert not mock_rsi_gate.called
            assert not mock_pcr_gate.called
            assert mock_select.call_args.args[1] == "BEARISH"

    def test_no_breakout_and_hit_count_below_two_falls_through_normally_not_skipped(self):
        """🎓 hit_count_so_far < 2 असेल आणि candle-close अट पूर्णही झाली नसेल, तर max-2-hits skip
        लागू होता कामा नये (established behavior फक्त hit_count>=2 साठीच) — trade साधा (नेहमीच्या
        RSI/PCR gate मार्गे जाणारा) reversal touch म्हणून पुढे प्रोसेस व्हायला हवा."""
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=self._breakout_gate_settings()), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", side_effect=self._fetch_candles_side_effect(self.PRIOR_CANDLES, 23905.0)), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_MAX_2_HITS_REACHED" not in statuses

    def test_volume_confirm_disabled_by_default_ignores_low_volume(self):
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा ("5 minute Breakout candle + Volume ashi
        condition ठेवता yeil") — breakout_volume_confirm_enabled डीफॉल्ट बंद असल्याने, breakout
        candle चा volume कमी असला तरी trade अडायला नको (established candle-close-only वर्तन कायम)."""
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=self._breakout_gate_settings()), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", side_effect=self._fetch_candles_side_effect_with_volume(
                 self.PRIOR_CANDLES, 23800.0, [100] * len(self.PRIOR_CANDLES), 50)), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23800.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BEAR_CALL_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T99"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(2, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called

    def test_volume_confirm_enabled_blocks_low_volume_breakout(self):
        """Volume Confirmation चालू असेल आणि breakout candle चा volume सरासरीच्या multiplier पटीपेक्षा
        कमी असेल, तर candle-close अट पूर्ण असूनही breakout trade घेतला जायला नको."""
        settings = self._breakout_gate_settings()
        settings["breakout_volume_confirm_enabled"] = True
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", side_effect=self._fetch_candles_side_effect_with_volume(
                 self.PRIOR_CANDLES, 23800.0, [100] * len(self.PRIOR_CANDLES), 120)), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(2, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_MAX_2_HITS_REACHED" in statuses

    def test_volume_confirm_enabled_fires_with_sufficient_volume(self):
        """Volume Confirmation चालू असेल आणि breakout candle चा volume सरासरीच्या multiplier पटीपेक्षा
        जास्त असेल, तर candle-close + volume दोन्ही अटी पूर्ण -- breakout trade घेतला जायला हवा."""
        settings = self._breakout_gate_settings()
        settings["breakout_volume_confirm_enabled"] = True
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", side_effect=self._fetch_candles_side_effect_with_volume(
                 self.PRIOR_CANDLES, 23800.0, [100] * len(self.PRIOR_CANDLES), 200)), \
             patch.object(dsr, "check_instant_rsi_filter") as mock_rsi_gate, \
             patch.object(dsr, "check_pcr_gate") as mock_pcr_gate, \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23800.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BEAR_CALL_SPREAD", "legs": []}) as mock_select, \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T100"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(2, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called
            assert not mock_rsi_gate.called
            assert not mock_pcr_gate.called
            assert mock_select.call_args.args[1] == "BEARISH"
            assert mock_trade.call_args.kwargs.get("entry_reason_tag") == "BREAKOUT_ENTRY"

    def test_volume_confirm_uses_settings_lookback_and_multiplier(self):
        """breakout_volume_lookback_candles/breakout_volume_multiplier Dashboard settings वरून
        घेतले जायला हवेत (hardcoded नाहीत) -- खूप सैल multiplier (1.0) दिला की, आधी अडणारा
        कमी-volume breakout आता पास व्हायला हवा."""
        settings = self._breakout_gate_settings()
        settings["breakout_volume_confirm_enabled"] = True
        settings["breakout_volume_multiplier"] = 1.0  # सरासरी इतकाही volume पुरेसा
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", side_effect=self._fetch_candles_side_effect_with_volume(
                 self.PRIOR_CANDLES, 23800.0, [100] * len(self.PRIOR_CANDLES), 105)), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23800.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BEAR_CALL_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T101"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(2, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called

    def test_oi_confirm_disabled_by_default_ignores_mismatched_signal(self):
        """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा ("option chain analysis oi snapshot every 5
        minute save kele जातात tech yethe use krta yeil") — breakout_oi_confirm_enabled डीफॉल्ट
        बंद असल्याने, OI signal breakout दिशेशी जुळत नसला तरी trade अडायला नको (established
        candle-close/volume-only वर्तन कायम)."""
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=self._breakout_gate_settings()), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", side_effect=self._fetch_candles_side_effect(self.PRIOR_CANDLES, 23800.0)), \
             patch.object(dsr, "get_latest_oi_signal", return_value="BULLISH") as mock_oi_signal, \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23800.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BEAR_CALL_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T102"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(2, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called
            assert not mock_oi_signal.called

    def test_oi_confirm_enabled_blocks_mismatched_signal(self):
        """Breakout दिशा BEARISH आहे (role=SUPPORT); OI signal 'BULLISH' (जुळत नाही, weakening
        सुद्धा नाही) असेल, तर candle-close अट पूर्ण असूनही breakout trade घेतला जायला नको."""
        settings = self._breakout_gate_settings()
        settings["breakout_oi_confirm_enabled"] = True
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", side_effect=self._fetch_candles_side_effect(self.PRIOR_CANDLES, 23800.0)), \
             patch.object(dsr, "get_latest_oi_signal", return_value="BULLISH"), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(2, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_MAX_2_HITS_REACHED" in statuses

    def test_oi_confirm_enabled_fires_with_matching_signal(self):
        """Breakout दिशा BEARISH आहे; OI signal 'BEARISH' (established check_oi_diff_entry_gate नुसार
        जुळतो) असेल, तर candle-close + OI दोन्ही अटी पूर्ण -- breakout trade घेतला जायला हवा."""
        settings = self._breakout_gate_settings()
        settings["breakout_oi_confirm_enabled"] = True
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", side_effect=self._fetch_candles_side_effect(self.PRIOR_CANDLES, 23800.0)), \
             patch.object(dsr, "get_latest_oi_signal", return_value="BEARISH") as mock_oi_signal, \
             patch.object(dsr, "check_instant_rsi_filter") as mock_rsi_gate, \
             patch.object(dsr, "check_pcr_gate") as mock_pcr_gate, \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23800.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BEAR_CALL_SPREAD", "legs": []}) as mock_select, \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T103"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(2, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called
            assert mock_oi_signal.called
            assert mock_oi_signal.call_args.args[0] == "NIFTY"
            assert not mock_rsi_gate.called
            assert not mock_pcr_gate.called
            assert mock_select.call_args.args[1] == "BEARISH"
            assert mock_trade.call_args.kwargs.get("entry_reason_tag") == "BREAKOUT_ENTRY"

    def test_oi_confirm_enabled_fires_when_opposite_direction_weakening(self):
        """established check_oi_diff_entry_gate चा 'Weakening' नियम -- BEARISH breakout ला
        'BULLISH (Weakening)' signal (bulls मागे हटतायत) सुद्धा वैध मानला जायला हवा."""
        settings = self._breakout_gate_settings()
        settings["breakout_oi_confirm_enabled"] = True
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", side_effect=self._fetch_candles_side_effect(self.PRIOR_CANDLES, 23800.0)), \
             patch.object(dsr, "get_latest_oi_signal", return_value="BULLISH (Weakening)"), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23800.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BEAR_CALL_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T104"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(2, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called

    def test_not_applied_to_1m_level_even_when_timeframe_choice_is_both(self):
        """🎓 वापरकर्त्याशी चर्चा करून सापडवलेली/सुधारलेली विसंगती ("5minute dynamic sr Breakout
        jhalyanantr ch Breakout trade ghenyat yenar") — breakout confirm करणारे candles कायमच
        5-मिनिट असतात, त्यामुळे timeframe_choice="BOTH" असतानाही pooled झालेल्या 1M level च्या
        touch वर Breakout Entry लागूच व्हायला नको -- candle-close अट (buffer% सह) पूर्ण असूनही,
        max-2-hits skip established behavior प्रमाणेच लागू व्हायला हवं."""
        zones_1m = pd.DataFrame([
            {"symbol": "NIFTY", "zone_type": "DYNAMIC_SR_SUPPORT_1M", "zone_low": self.LEVEL, "zone_high": self.LEVEL,
             "strength": 3.0, "formed_date": "2026-09-01", "status": "ACTIVE"},
        ])
        settings = self._breakout_gate_settings()
        settings["timeframe_choice"] = "BOTH"
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=zones_1m), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", side_effect=self._fetch_candles_side_effect(self.PRIOR_CANDLES, 23800.0)), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(2, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
            assert "SKIPPED_MAX_2_HITS_REACHED" in statuses

    def test_applied_to_5m_level_when_timeframe_choice_is_both(self):
        """वरच्याच टेस्टच्या उलट -- timeframe_choice="BOTH" असतानाही, 5M level च्या touch वर
        Breakout Entry नेहमीप्रमाणेच लागू व्हायला हवं (फक्त 1M साठी वगळलेलं आहे, 5M साठी नाही)."""
        zones_both = pd.concat([
            _fake_zones(),
            pd.DataFrame([{"symbol": "NIFTY", "zone_type": "DYNAMIC_SR_RESISTANCE_1M", "zone_low": 24700.0, "zone_high": 24700.0,
                            "strength": 1.0, "formed_date": "2026-09-01", "status": "ACTIVE"}]),
        ], ignore_index=True)
        settings = self._breakout_gate_settings()
        settings["timeframe_choice"] = "BOTH"
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=zones_both), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", side_effect=self._fetch_candles_side_effect(self.PRIOR_CANDLES, 23800.0)), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23800.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BEAR_CALL_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T105"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(2, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called

    def test_reason_includes_actual_candle_close_pct(self):
        """🎓 वापरकर्त्याने मागितलेली सुधारणा ("candle-close %, volume ratio, OI signal Signal Log
        मध्ये स्वतंत्रपणे दाखवायचे") — फक्त gate चा bool निकाल नाही, तर प्रत्यक्ष मोजलेलं % अंतर
        Signal Log च्या reason मध्ये दिसायला हवं. LEVEL=23900, final_close=23800 (support break,
        BEARISH) -- (23900-23800)/23900*100 = 0.4184%."""
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=self._breakout_gate_settings()), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", side_effect=self._fetch_candles_side_effect(self.PRIOR_CANDLES, 23800.0)), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23800.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BEAR_CALL_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T106"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(2, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called
            entries = [c.args[0] for c in mock_log.call_args_list]
            breakout_entries = [e for e in entries if e.get("direction") == "BEARISH" and "Breakout Entry" in (e.get("reason") or "")]
            assert len(breakout_entries) == 1
            assert "candle close +0.418%" in breakout_entries[0]["reason"]
            assert "Volume" not in breakout_entries[0]["reason"]
            assert "OI Signal" not in breakout_entries[0]["reason"]

    def test_reason_includes_volume_ratio_when_enabled(self):
        """volume confirm enabled असताना, प्रत्यक्ष मोजलेला ratio (किमान multiplier सकट) reason मध्ये
        दिसायला हवा."""
        settings = self._breakout_gate_settings()
        settings["breakout_volume_confirm_enabled"] = True
        settings["breakout_volume_multiplier"] = 1.5
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", side_effect=self._fetch_candles_side_effect_with_volume(
                 self.PRIOR_CANDLES, 23800.0, [100] * len(self.PRIOR_CANDLES), 200)), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23800.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BEAR_CALL_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T107"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(2, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called
            entries = [c.args[0] for c in mock_log.call_args_list]
            breakout_entries = [e for e in entries if e.get("direction") == "BEARISH" and "Breakout Entry" in (e.get("reason") or "")]
            assert len(breakout_entries) == 1
            assert "Volume 2.00x (किमान 1.5x हवं)" in breakout_entries[0]["reason"]

    def test_reason_includes_oi_signal_when_enabled(self):
        """OI confirm enabled असताना, वापरलेला OI signal reason मध्ये दिसायला हवा."""
        settings = self._breakout_gate_settings()
        settings["breakout_oi_confirm_enabled"] = True
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", side_effect=self._fetch_candles_side_effect(self.PRIOR_CANDLES, 23800.0)), \
             patch.object(dsr, "get_latest_oi_signal", return_value="BEARISH"), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23800.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BEAR_CALL_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T108"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(2, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called
            entries = [c.args[0] for c in mock_log.call_args_list]
            breakout_entries = [e for e in entries if e.get("direction") == "BEARISH" and "Breakout Entry" in (e.get("reason") or "")]
            assert len(breakout_entries) == 1
            assert "OI Signal: BEARISH" in breakout_entries[0]["reason"]


class TestBreakoutEntryCatchup:
    """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा (Breakout Entry — "missed window" catch-up) —
    वापरकर्त्याने प्रत्यक्ष उदाहरणासह (28 सप्टें सकाळी 9:15-9:20 चा NIFTY candle, level 23038.1)
    दाखवलेली स्थिती: 1-मिनिट touch (09:16/09:17) लवकर मिळाला, candle अजून बंदच झालेला नव्हता म्हणून
    breakout तपासताच आला नाही -- आणि candle बंद (09:20) होईपर्यंत किंमत level पासून इतकी दूर
    निघून गेली की नवीन 1-मिनिट touch-eventच मिळाला नाही -- खरा breakout कायमचा हुकला. आता,
    1-मिनिट touch न सापडल्यास (फक्त 5M levels, entry_breakout_gate_enabled असेल तरच), शेवटच्या
    दोन 5-मिनिट candles वरून स्वतंत्रपणे "level ओलांडला का" तपासलं जातं -- established
    reversal-touch/max-hits मार्गाला अजिबात स्पर्श न करता (LEVEL/PRIOR_CANDLES/
    _breakout_gate_settings() वरच्या TestBreakoutEntry सारखेच, इथे स्वतंत्रपणे — inherit केलं नाही,
    जेणेकरून त्या class च्या चाचण्या इथे पुन्हा चालणार नाहीत)."""

    LEVEL = 23900.0
    PRIOR_CANDLES = [
        23880.0, 23910.0, 23895.0, 23905.0, 23890.0, 23900.0,
        23885.0, 23915.0, 23898.0, 23902.0, 23890.0, 23900.0,
    ]

    def _breakout_gate_settings(self):
        settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
        settings["entry_breakout_gate_enabled"] = True
        return settings

    def _no_1min_touch_candles(self, today_ist=None):
        """शेवटचे दोन 1-मिनिट candles मुद्दामच LEVEL (तंतोतंत, ±0.01% touch-buffer, ~2.4 पॉइंट्स)
        पासून थोडे दूर, तरीही hysteresis च्या रुंद बँड (±0.10%, ~24 पॉइंट्स) च्या आतच ठेवले आहेत --
        established check_level_crossed() नुसार यांच्यावर hit=False (touch किंवा gap-through
        नाही), आणि हे दोन्ही candles hysteresis साठी अनिश्चित (ambiguous) असल्याने ती आधीच्या
        (prepend केलेल्या declining trend च्या शेवटच्या, स्पष्टपणे LEVEL च्या वर असलेल्या) close
        वरून दिशा ठरवते -- म्हणजे role अजूनही SUPPORT/BULLISH च राहतो (existing TestBreakoutEntry
        च्याच LEVEL=23900 SUPPORT पॅटर्नशी सुसंगत — support level "तुटून" resistance मध्ये आधीच
        role-flip व्हायच्या आतचीच स्थिती, जी वापरकर्त्याने दाखवलेल्या प्रत्यक्ष उदाहरणाशी जुळते)."""
        touch_rows = [
            {"open": 23895, "high": 23896, "low": 23880, "close": 23885},
            {"open": 23885, "high": 23890, "low": 23878, "close": 23882},
        ]
        return _candles_with_rsi(touch_rows, declining=True, today_ist=today_ist or datetime.datetime(2026, 9, 11, 10, 0, 0))

    def _fetch_candles_side_effect_catchup(self, prior_5m_closes, final_5m_close):
        def _fake(token, symbol, current_spot=0, interval="1minute", lookback_days=1):
            if interval == "5minute":
                return _breakout_5m_candles(prior_5m_closes, final_5m_close, today_ist=datetime.datetime(2026, 9, 11, 10, 0, 0))
            return self._no_1min_touch_candles()
        return _fake

    def test_no_1min_touch_confirms_no_hit(self):
        """🎓 sanity check -- वरचा _no_1min_touch_candles() fixture खरंच 1-मिनिट touch देत नाही,
        हे स्वतंत्रपणे सिद्ध करण्यासाठी (breakout catch-up बंद असताना)."""
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=self._no_1min_touch_candles()) as mock_fetch, \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(2, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            assert all(c.kwargs.get("interval", "1minute") != "5minute" for c in mock_fetch.call_args_list)
            entries = [c.args[0] for c in mock_log.call_args_list]
            level_entries = [e for e in entries if e["level_price"] == self.LEVEL]
            assert level_entries and all(e["hit_type"] == "NO_HIT" for e in level_entries)

    def test_catchup_fires_breakout_trade_when_5m_candle_crossed_and_closed_beyond_buffer(self):
        """मुख्य केस -- 1-मिनिट touch नाही, पण शेवटचा 5-मिनिट candle LEVEL ओलांडून buffer% पलीकडे
        निर्णायकपणे close झालेला आहे -- Breakout Entry trade घेतला जायला हवा."""
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=self._breakout_gate_settings()), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", side_effect=self._fetch_candles_side_effect_catchup(self.PRIOR_CANDLES, 23640.0)) as mock_fetch, \
             patch.object(dsr, "check_instant_rsi_filter") as mock_rsi_gate, \
             patch.object(dsr, "check_pcr_gate") as mock_pcr_gate, \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23640.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BEAR_CALL_SPREAD", "legs": []}) as mock_select, \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "TCU1"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(2, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert mock_trade.called
            assert not mock_rsi_gate.called
            assert not mock_pcr_gate.called
            # मूळ दिशा (support, 23900) BULLISH होती -- breakout confirm झाल्याने BEARISH
            assert mock_select.call_args.args[1] == "BEARISH"
            assert mock_trade.call_args.kwargs.get("entry_reason_tag") == "BREAKOUT_ENTRY"
            # 🎓 5-मिनिट candles आता प्रति-symbol एकदाच आणले जायला हवेत (दोन्ही _fake_zones()
            # levels साठी मिळून), प्रत्येक level साठी वेगळे नाही (कार्यक्षमता सुधारणा).
            five_min_calls = [c for c in mock_fetch.call_args_list if c.kwargs.get("interval") == "5minute"]
            assert len(five_min_calls) == 1

    def test_catchup_does_not_fire_when_5m_candle_close_within_buffer(self):
        """5-मिनिट candle level ओलांडून गेला, पण buffer% इतका निर्णायक close झाला नाही -- trade
        घेतला जायला नको, आणि साध्या reversal trade मध्येही (max-hits मार्गे) पडता कामा नये."""
        settings = self._breakout_gate_settings()
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", side_effect=self._fetch_candles_side_effect_catchup(self.PRIOR_CANDLES, 23899.0)), \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(2, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            entries = [c.args[0] for c in mock_log.call_args_list]
            level_entries = [e for e in entries if e["level_price"] == self.LEVEL]
            assert level_entries
            assert level_entries[0]["trade_status"] == "SKIPPED_BREAKOUT_CATCHUP_CONDITIONS_NOT_MET"
            statuses = [e["trade_status"] for e in level_entries]
            assert "SKIPPED_MAX_2_HITS_REACHED" not in statuses

    def test_catchup_disabled_when_breakout_gate_off(self):
        """entry_breakout_gate_enabled=False (डीफॉल्ट) असेल तर catch-up कधीच चालायला नको -- 1-मिनिट
        touch नसेल तर established NO_HIT वर्तनच कायम, 5-मिनिट candles साठी fetch_candles अजिबात
        call व्हायला नको."""
        with patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", return_value=self._no_1min_touch_candles()) as mock_fetch, \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(2, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            assert all(c.kwargs.get("interval", "1minute") != "5minute" for c in mock_fetch.call_args_list)

    def test_catchup_disabled_for_1m_only_levels(self):
        """timeframe_choice="1M" असेल (zone_type मध्ये _5M ऐवजी _1M) तर catch-up कधीच चालायला नको
        -- established "Breakout Entry फक्त 5M levels साठीच" निर्बंध इथेही लागू."""
        settings = self._breakout_gate_settings()
        settings["timeframe_choice"] = "1M"
        zones_1m = pd.DataFrame([
            {"symbol": "NIFTY", "zone_type": "DYNAMIC_SR_SUPPORT_1M", "zone_low": self.LEVEL, "zone_high": self.LEVEL,
             "strength": 3.0, "formed_date": "2026-09-01", "status": "ACTIVE"},
        ])
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=zones_1m), \
             patch.object(dsr, "get_ist_now", return_value=datetime.datetime(2026, 9, 11, 10, 0, 0)), \
             patch.object(dsr, "fetch_candles", side_effect=self._fetch_candles_side_effect_catchup(self.PRIOR_CANDLES, 23640.0)) as mock_fetch, \
             patch.object(dsr, "open_multi_leg_trade") as mock_trade, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True), \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(2, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
            assert not mock_trade.called
            # entry_breakout_gate_enabled=True असला तरी timeframe_choice="1M" असल्याने
            # todays_5m_candles_all fetch सुद्धा होता कामा नये (active_timeframes मध्ये "5M" नाहीच).
            assert all(c.kwargs.get("interval", "1minute") != "5minute" for c in mock_fetch.call_args_list)


class TestDetermineBreakoutDirectionFromClose:
    LEVEL = 23900.0  # 0.010% buffer = 2.39 pts

    def _c(self, closes):
        return [{"close": c} for c in closes]

    def test_support_broken_downwards_is_bearish(self):
        # मागे level च्या वर (23915) होतो, आता 23868 -> BEARISH
        assert dsr.determine_breakout_direction_from_close(self.LEVEL, self._c([23930, 23915, 23890, 23868]), 0.010, 3) == "BEARISH"

    def test_resistance_broken_upwards_is_bullish(self):
        assert dsr.determine_breakout_direction_from_close(self.LEVEL, self._c([23870, 23885, 23895, 23935]), 0.010, 3) == "BULLISH"

    def test_no_cross_when_previous_closes_all_on_same_side(self):
        # आधीपासूनच खाली होता, आता पुन्हा खाली -> ओलांडलेलं नाही (साधं reversal/retest)
        assert dsr.determine_breakout_direction_from_close(self.LEVEL, self._c([23850, 23860, 23870, 23868]), 0.010, 3) is None

    def test_lookback_excludes_older_candles(self):
        # 23930 (वर) फक्त lookback=2 च्या बाहेर -> None; lookback=3 मध्ये आलं तर BEARISH
        closes = self._c([23930, 23880, 23870, 23868])
        assert dsr.determine_breakout_direction_from_close(self.LEVEL, closes, 0.010, 2) is None
        assert dsr.determine_breakout_direction_from_close(self.LEVEL, closes, 0.010, 3) == "BEARISH"

    def test_last_close_within_buffer_is_none(self):
        assert dsr.determine_breakout_direction_from_close(self.LEVEL, self._c([23930, 23915, 23901, 23899]), 0.010, 3) is None

    def test_too_few_candles(self):
        assert dsr.determine_breakout_direction_from_close(self.LEVEL, [], 0.010, 3) is None
        assert dsr.determine_breakout_direction_from_close(self.LEVEL, self._c([23868]), 0.010, 3) is None


class TestBreakdownMissedBecauseOfRoleFlip:
    """🎓 "22538 support Breakout trade ka execute jhala nahi" (01-Oct, 12:11-12:15) — किंमत support (वरून) खाली गेल्यावर
    १-मिनिट hysteresis ने level ची भूमिका RESISTANCE झाली, म्हणून breakout ची दिशा BULLISH शोधली गेली आणि खरा breakdown
    हुकला (SKIPPED_BREAKOUT_CATCHUP_CONDITIONS_NOT_MET). LEVEL=23900 (support), 1-मिनिट close 23868 (< 23876.1 = hysteresis
    खालची मर्यादा) => भूमिका RESISTANCE/BEARISH; 5M: मागचे candles 23915/23905 वर, शेवटचा 23868."""

    LEVEL = 23900.0
    NOW = datetime.datetime(2026, 9, 11, 10, 0, 0)
    PRIOR_5M = [23930.0, 23915.0, 23905.0, 23890.0]

    def _one_min(self):
        rows = [
            {"open": 23880, "high": 23885, "low": 23868, "close": 23872},
            {"open": 23872, "high": 23878, "low": 23865, "close": 23868},
        ]
        return _candles_with_rsi(rows, declining=True, today_ist=self.NOW)

    def _run(self, from_close, prior_5m=None, final_close=23868.0, extra_settings=None, directions=None):
        settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
        settings.update(entry_breakout_gate_enabled=True, breakout_close_buffer_pct=0.010,
                        breakout_direction_from_close=from_close, naked_enabled=False)
        settings.update(extra_settings or {})

        def _fetch(token, symbol, current_spot=0, interval="1minute", lookback_days=1):
            if interval == "5minute":
                return _breakout_5m_candles(prior_5m or self.PRIOR_5M, final_close, today_ist=self.NOW)
            return self._one_min()

        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=self.NOW), \
             patch.object(dsr, "fetch_candles", side_effect=_fetch), \
             patch.object(dsr, "fetch_trend_filter_directions", return_value=directions or (None, None)), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23868.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BEAR_CALL_SPREAD", "legs": []}) as mock_select, \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "TB1"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
        level_entries = [c.args[0] for c in mock_log.call_args_list if c.args[0]["level_price"] == self.LEVEL]
        return mock_trade, mock_select, level_entries

    def test_default_off_reproduces_the_missed_breakdown(self):
        mock_trade, _, entries = self._run(from_close=False)
        assert not mock_trade.called
        assert any(e["trade_status"] == "SKIPPED_BREAKOUT_CATCHUP_CONDITIONS_NOT_MET" for e in entries)

    def test_enabled_takes_the_bearish_breakdown_trade(self):
        mock_trade, mock_select, entries = self._run(from_close=True)
        assert mock_trade.called
        assert mock_select.call_args.args[1] == "BEARISH"
        assert mock_trade.call_args.kwargs.get("entry_reason_tag") == "BREAKOUT_ENTRY"

    def test_supertrend_filter_does_not_block_breakout_trades(self):
        # Bearish breakdown, पण 15M+1H दोन्ही BULLISH (फिल्टर साध्या Bearish reversal ला अडवला असता) -> breakout वगळलेला
        mock_trade, _, entries = self._run(
            from_close=True, extra_settings={"entry_supertrend_filter_enabled": True}, directions=("BULLISH", "BULLISH"))
        assert mock_trade.called
        assert mock_trade.call_args.kwargs.get("entry_reason_tag") == "BREAKOUT_ENTRY"
        assert all(e["trade_status"] != "SKIPPED_TREND_FILTER" for e in entries)

    def test_breakout_supertrend_filter_allows_when_both_agree(self):
        mock_trade, _, entries = self._run(
            from_close=True, extra_settings={"breakout_supertrend_filter_enabled": True}, directions=("BEARISH", "BEARISH"))
        assert mock_trade.called
        opened = [e for e in entries if e.get("breakout_eval")]
        assert opened and "=> BREAKOUT]" in opened[-1]["breakout_eval"]
        assert "S✓(15M=BEARISH,1H=BEARISH)" in opened[-1]["breakout_eval"]

    def test_breakout_supertrend_filter_blocks_when_only_one_agrees(self):
        mock_trade, _, entries = self._run(
            from_close=True, extra_settings={"breakout_supertrend_filter_enabled": True}, directions=("BEARISH", "BULLISH"))
        assert not mock_trade.called
        blocked = [e for e in entries if e["trade_status"] == "SKIPPED_BREAKOUT_CATCHUP_CONDITIONS_NOT_MET"]
        assert blocked and "S✗(15M=BEARISH,1H=BULLISH)" in blocked[-1]["breakout_eval"]
        assert "=> NO]" in blocked[-1]["breakout_eval"]

    def test_breakout_supertrend_filter_blocks_when_data_missing(self):
        mock_trade, _, entries = self._run(
            from_close=True, extra_settings={"breakout_supertrend_filter_enabled": True}, directions=(None, "BEARISH"))
        assert not mock_trade.called
        assert any("S✗(15M=N/A,1H=BEARISH)" in e.get("breakout_eval", "") for e in entries)

    def test_breakout_supertrend_filter_off_by_default_and_does_not_fetch(self):
        assert cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"]["breakout_supertrend_filter_enabled"] is False
        mock_trade, _, entries = self._run(from_close=True, directions=("BULLISH", "BULLISH"))
        assert mock_trade.called
        assert any("S-" in e.get("breakout_eval", "") for e in entries)

    def test_every_breakout_evaluation_is_described_in_the_log(self):
        # candle-close अट अपूर्ण असतानाही (breakout झालाच नाही) नोंदीत कारण दिसतं
        _, _, entries = self._run(from_close=True, extra_settings={"breakout_close_buffer_pct": 5.0})
        notes = [e["breakout_eval"] for e in entries if e.get("breakout_eval")]
        assert notes and all(n.startswith("[BRK:") and "=> NO]" in n for n in notes)

    def test_enabled_but_price_was_already_below_does_not_trigger(self):
        # मागचे सर्व close आधीच level च्या खाली -> ओलांडलेलं नाही -> जुनं वर्तन (breakout नाही)
        mock_trade, _, entries = self._run(from_close=True, prior_5m=[23860.0, 23870.0, 23880.0, 23890.0])
        assert not mock_trade.called


def _trend_df(start, step, n=60, bar_minutes=15, end=None):
    """सतत चढणारा (step>0) किंवा उतरणारा (step<0) OHLC series — Supertrend दिशेची चाचणी."""
    end = end or datetime.datetime(2026, 9, 11, 12, 0, 0)
    stamps = pd.date_range(end=end, periods=n, freq=f"{bar_minutes}min")
    closes = [start + step * i for i in range(n)]
    return pd.DataFrame({
        "timestamp": stamps, "open": [c - step for c in closes],
        "high": [max(c, c - step) + 2 for c in closes], "low": [min(c, c - step) - 2 for c in closes],
        "close": closes, "volume": 100, "oi": 0,
    })


class TestSupertrendTrendFilterHelpers:
    def test_direction_of_rising_and_falling_series(self):
        assert dsr.get_supertrend_direction(_trend_df(23000, 10), 10, 3.0) == "BULLISH"
        assert dsr.get_supertrend_direction(_trend_df(24000, -10), 10, 3.0) == "BEARISH"

    def test_direction_none_when_too_few_bars(self):
        assert dsr.get_supertrend_direction(_trend_df(23000, 10, n=5), 10, 3.0) is None
        assert dsr.get_supertrend_direction(pd.DataFrame(), 10, 3.0) is None

    def test_incomplete_last_bar_is_dropped(self):
        df = _trend_df(23000, 10, n=10, bar_minutes=15, end=datetime.datetime(2026, 9, 11, 12, 0, 0))  # शेवटचा bar 12:00-12:15
        assert len(dsr._completed_bars_only(df, 15, datetime.datetime(2026, 9, 11, 12, 10, 0))) == 9   # अजून चालू
        assert len(dsr._completed_bars_only(df, 15, datetime.datetime(2026, 9, 11, 12, 15, 0))) == 10  # पूर्ण झाला

    def test_check_blocks_bullish_only_when_both_bearish(self):
        assert dsr.check_supertrend_trend_filter("BULLISH", "BEARISH", "BEARISH")[0] is False
        assert dsr.check_supertrend_trend_filter("BULLISH", "BEARISH", "BULLISH")[0] is True
        assert dsr.check_supertrend_trend_filter("BULLISH", "BULLISH", "BEARISH")[0] is True
        assert dsr.check_supertrend_trend_filter("BULLISH", "BULLISH", "BULLISH")[0] is True

    def test_check_blocks_bearish_only_when_both_bullish(self):
        assert dsr.check_supertrend_trend_filter("BEARISH", "BULLISH", "BULLISH")[0] is False
        assert dsr.check_supertrend_trend_filter("BEARISH", "BULLISH", "BEARISH")[0] is True
        assert dsr.check_supertrend_trend_filter("BEARISH", "BEARISH", "BEARISH")[0] is True

    def test_check_fails_open_when_data_missing(self):
        assert dsr.check_supertrend_trend_filter("BULLISH", None, "BEARISH") == (True, None)
        assert dsr.check_supertrend_trend_filter("BULLISH", "BEARISH", None) == (True, None)

    def test_fetch_directions_end_to_end_with_synthetic_candles(self):
        now = datetime.datetime(2026, 9, 11, 12, 0, 0)

        def _fetch(token, symbol, current_spot=0, interval="15minute", lookback_days=5):
            if interval == "15minute":
                return _trend_df(24000, -10, n=80, bar_minutes=15, end=now)
            return _trend_df(23000, 10, n=120, bar_minutes=30, end=now)

        with patch.object(dsr, "fetch_candles", side_effect=_fetch):
            d15, d1h = dsr.fetch_trend_filter_directions("tok", "NIFTY", now)
        assert d15 == "BEARISH" and d1h == "BULLISH"

    def test_fetch_directions_failure_gives_none(self):
        with patch.object(dsr, "fetch_candles", side_effect=RuntimeError("boom")):
            assert dsr.fetch_trend_filter_directions("tok", "NIFTY", datetime.datetime(2026, 9, 11, 12, 0, 0)) == (None, None)


class TestSupertrendTrendFilterInProcessSymbol:
    """Support (23900) वर Bullish touch; फिल्टर चालू असताना 15M+1H दोन्ही BEARISH => SKIPPED_TREND_FILTER."""

    NOW = datetime.datetime(2026, 9, 11, 10, 0, 0)

    def _run(self, directions, enabled=True, breakout=False):
        candles_touch = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=self.NOW)
        settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
        settings.update(entry_rsi_gate_enabled=False, entry_pcr_gate_enabled=False, naked_enabled=False,
                        entry_supertrend_filter_enabled=enabled)
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=self.NOW), \
             patch.object(dsr, "fetch_candles", return_value=candles_touch), \
             patch.object(dsr, "fetch_trend_filter_directions", return_value=directions) as mock_dirs, \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
        statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
        return mock_trade, mock_dirs, statuses, mock_log

    def test_default_off_never_fetches_or_blocks(self):
        mock_trade, mock_dirs, statuses, _ = self._run(("BEARISH", "BEARISH"), enabled=False)
        assert mock_trade.called and not mock_dirs.called
        assert "SKIPPED_TREND_FILTER" not in statuses

    def test_both_bearish_blocks_bullish_trade(self):
        mock_trade, _, statuses, mock_log = self._run(("BEARISH", "BEARISH"))
        assert not mock_trade.called
        assert "SKIPPED_TREND_FILTER" in statuses
        reason = [c.args[0]["reason"] for c in mock_log.call_args_list if c.args[0]["trade_status"] == "SKIPPED_TREND_FILTER"][0]
        assert "15M: BEARISH" in reason and "1H: BEARISH" in reason

    def test_mixed_timeframes_allow_trade(self):
        mock_trade, _, statuses, _ = self._run(("BEARISH", "BULLISH"))
        assert mock_trade.called and "SKIPPED_TREND_FILTER" not in statuses

    def test_both_bullish_does_not_block_bullish_trade(self):
        mock_trade, _, _, _ = self._run(("BULLISH", "BULLISH"))
        assert mock_trade.called

    def test_missing_data_fails_open(self):
        mock_trade, _, _, _ = self._run((None, None))
        assert mock_trade.called

    def test_directions_fetched_once_per_cycle_for_all_levels(self):
        _, mock_dirs, _, _ = self._run(("BEARISH", "BULLISH"))
        assert mock_dirs.call_count <= 1


class TestGetBreakoutVolumeRatio:
    """🎓 वापरकर्त्याने मागितलेली सुधारणा — check_breakout_volume_confirmation() मधलाच ratio, फक्त
    bool ऐवजी नेमकं संख्यात्मक मूल्य (Signal Log मध्ये दाखवण्यासाठी)."""

    def test_computes_ratio(self):
        candles = [{"close": 100, "volume": 100}] * 10 + [{"close": 100, "volume": 250}]
        assert dsr.get_breakout_volume_ratio(candles, lookback_candles=10) == 2.5

    def test_not_enough_candles_returns_none(self):
        candles = [{"close": 100, "volume": 100}] * 5
        assert dsr.get_breakout_volume_ratio(candles, lookback_candles=10) is None

    def test_empty_candles_returns_none(self):
        assert dsr.get_breakout_volume_ratio([], lookback_candles=10) is None

    def test_zero_avg_volume_returns_none(self):
        candles = [{"close": 100, "volume": 0}] * 10 + [{"close": 100, "volume": 50}]
        assert dsr.get_breakout_volume_ratio(candles, lookback_candles=10) is None


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


class TestStopAfterTargetGate:
    """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा ("कोणताही एक सिग्नल ... टार्गेट गाठल्यास बॉटने पुढील
    ट्रेडिंग थांबवावे") — RSI/PCR Gate मुद्दामच बंद, फक्त या नवीन नियमाचंच वर्तन तपासलं जातं."""

    NOW = datetime.datetime(2026, 9, 11, 10, 0, 0)
    HIT = ("PAPER_T1", "NIFTY", "2026-09-11 09:50:12", 1234.0)

    def _settings(self, **overrides):
        settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
        settings["entry_rsi_gate_enabled"] = False
        settings["entry_pcr_gate_enabled"] = False
        settings.update(overrides)
        return settings

    def _run(self, settings, hit_row):
        candles = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=self.NOW)
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=_fake_zones()), \
             patch.object(dsr, "get_ist_now", return_value=self.NOW), \
             patch.object(dsr, "fetch_candles", return_value=candles), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "get_first_target_exit_today", return_value=hit_row) as mock_hit, \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
        return mock_trade, mock_log, mock_hit

    def test_blocks_new_entry_after_target_when_enabled(self):
        mock_trade, mock_log, mock_hit = self._run(self._settings(stop_after_target_enabled=True), self.HIT)
        assert not mock_trade.called
        entries = [c.args[0] for c in mock_log.call_args_list if c.args[0]["trade_status"] == "SKIPPED_TARGET_ALREADY_HIT_TODAY"]
        assert entries
        assert "PAPER_T1" in entries[0]["reason"] and "09:50" in entries[0]["reason"]

    def test_lookup_uses_bot_source_trading_mode_and_today(self):
        _, _, mock_hit = self._run(self._settings(stop_after_target_enabled=True, trading_mode="LIVE"), self.HIT)
        mock_hit.assert_called_with("dynamic_sr_instant", "LIVE", "2026-09-11")

    def test_allows_entry_when_no_target_yet(self):
        mock_trade, mock_log, _ = self._run(self._settings(stop_after_target_enabled=True), None)
        assert mock_trade.called
        statuses = [c.args[0]["trade_status"] for c in mock_log.call_args_list]
        assert "SKIPPED_TARGET_ALREADY_HIT_TODAY" not in statuses

    def test_disabled_by_default_ignores_target_and_skips_lookup(self):
        mock_trade, _, mock_hit = self._run(self._settings(), self.HIT)
        assert mock_trade.called
        assert not mock_hit.called

    def test_lookup_done_once_per_run_even_with_multiple_levels(self):
        _, _, mock_hit = self._run(self._settings(stop_after_target_enabled=True), None)
        assert mock_hit.call_count <= 1


def _zones_with_15m(level_15m, status="ACTIVE", suffix="SUPPORT"):
    zones = _fake_zones_5m_only()
    extra = pd.DataFrame([{"symbol": "NIFTY", "zone_type": f"DYNAMIC_SR_{suffix}_15M", "zone_low": level_15m,
                           "zone_high": level_15m, "strength": 4.0, "formed_date": "2026-09-01", "status": status}])
    return pd.concat([zones, extra], ignore_index=True)


class TestFindOverlapping15mLevel:
    """🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा ("5M आणि 15M levels ओव्हरलॅप/जवळ आले तर 15M strategy")."""

    def test_finds_15m_level_within_distance_and_same_direction(self):
        # 5M level 23900, 15M 23890 (0.042% खाली), किंमत 23902 (दोन्हीच्या वर -> दोन्ही Support/BULLISH)
        result = dsr.find_overlapping_15m_level(_zones_with_15m(23890.0), 23900.0, 0.10, 23902.0, "BULLISH")
        assert result is not None
        assert result[0] == 23890.0
        assert abs(result[1] - 10 / 23900 * 100) < 1e-9

    def test_none_when_farther_than_distance(self):
        assert dsr.find_overlapping_15m_level(_zones_with_15m(23850.0), 23900.0, 0.10, 23902.0, "BULLISH") is None

    def test_none_when_15m_direction_differs(self):
        # 15M level किमतीच्या वर (23910 > 23902) -> 15M दृष्टीने Resistance/BEARISH; 5M दिशा BULLISH -> जुळत नाही
        assert dsr.find_overlapping_15m_level(_zones_with_15m(23910.0), 23900.0, 0.10, 23902.0, "BULLISH") is None

    def test_ignores_non_active_15m_levels(self):
        assert dsr.find_overlapping_15m_level(_zones_with_15m(23890.0, status="STALE"), 23900.0, 0.10, 23902.0, "BULLISH") is None

    def test_ignores_non_15m_levels(self):
        assert dsr.find_overlapping_15m_level(_fake_zones_5m_only(), 23900.0, 0.10, 23902.0, "BULLISH") is None

    def test_picks_closest_of_multiple(self):
        zones = pd.concat([_zones_with_15m(23880.0), _zones_with_15m(23895.0).iloc[[-1]]], ignore_index=True)
        result = dsr.find_overlapping_15m_level(zones, 23900.0, 0.10, 23902.0, "BULLISH")
        assert result[0] == 23895.0

    def test_handles_empty_and_none(self):
        assert dsr.find_overlapping_15m_level(None, 23900.0, 0.10, 23902.0, "BULLISH") is None
        assert dsr.find_overlapping_15m_level(pd.DataFrame(columns=["zone_type", "zone_low", "status"]), 23900.0, 0.10, 23902.0, "BULLISH") is None


class TestIs15mStrategyReady:
    def _ready(self, s15, mode="PAPER", direction="BULLISH"):
        base = {"symbol_enabled": True, "trading_mode": "PAPER", "active_timeframes": ["15M"],
                "bullish_entry_enabled": True, "bearish_entry_enabled": True}
        base.update(s15)
        with patch.object(dsr.cloud_db, "get_strategy_settings", return_value=base):
            return dsr.is_15m_strategy_ready_for("NIFTY", direction, mode)

    def test_ready_when_all_conditions_met(self):
        assert self._ready({})[0] is True

    def test_not_ready_when_symbol_disabled(self):
        assert self._ready({"symbol_enabled": False})[0] is False

    def test_not_ready_when_mode_differs(self):
        assert self._ready({"trading_mode": "LIVE"}, mode="PAPER")[0] is False

    def test_not_ready_when_15m_timeframe_not_selected(self):
        assert self._ready({"active_timeframes": ["30M"]})[0] is False

    def test_not_ready_when_direction_disabled(self):
        assert self._ready({"bullish_entry_enabled": False}, direction="BULLISH")[0] is False
        assert self._ready({"bearish_entry_enabled": False}, direction="BEARISH")[0] is False
        assert self._ready({"bearish_entry_enabled": False}, direction="BULLISH")[0] is True

    def test_settings_read_failure_is_fail_open(self):
        with patch.object(dsr.cloud_db, "get_strategy_settings", side_effect=RuntimeError("db down")):
            assert dsr.is_15m_strategy_ready_for("NIFTY", "BULLISH", "PAPER")[0] is False


class TestDeferTo15mGate:
    NOW = datetime.datetime(2026, 9, 11, 10, 0, 0)

    def _run(self, s5, s15, zones):
        candles = _candles_with_rsi([
            {"open": 24010, "high": 24015, "low": 24000, "close": 24005},
            {"open": 24000, "high": 24005, "low": 23895, "close": 23902},
        ], declining=True, today_ist=self.NOW)

        def _settings(strategy_name, symbol):
            return s15 if strategy_name == "15m_dynamic_sr" else s5

        with patch.object(dsr.cloud_db, "get_strategy_settings", side_effect=_settings), \
             patch.object(dsr.cloud_db, "get_market_zones", return_value=zones), \
             patch.object(dsr, "get_ist_now", return_value=self.NOW), \
             patch.object(dsr, "fetch_candles", return_value=candles), \
             patch.object(dsr, "fetch_upstox_option_chain", return_value=(_fake_chain(23902.0), "SUCCESS")), \
             patch.object(dsr, "select_credit_spread_itm", return_value={"strategy": "BULL_PUT_SPREAD", "legs": []}), \
             patch.object(dsr, "open_multi_leg_trade", return_value=({"trade_id": "T1"}, "OPENED")) as mock_trade, \
             patch.object(dsr, "send_telegram_message", return_value=True), \
             patch.object(dsr, "get_open_trades_brief", return_value=self.open_trades), \
             patch.object(dsr, "close_trade_manually", side_effect=lambda *a, **k: (True, 0.0)) as mock_close, \
             patch.object(dsr.cloud_db, "save_signal_log", return_value=True) as mock_log, \
             patch.object(dsr.cloud_db, "get_zone_hits_today", return_value=(0, None, None)):
            dsr.process_symbol("fake_token", "NIFTY")
        self.mock_close = mock_close
        return mock_trade, mock_log

    open_trades = []

    def _s5(self, **overrides):
        settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["1m_instant"])
        settings["entry_rsi_gate_enabled"] = False
        settings["entry_pcr_gate_enabled"] = False
        settings.update(overrides)
        return settings

    def _s15(self, **overrides):
        settings = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS["15m_dynamic_sr"])
        settings["symbol_enabled"] = True
        settings.update(overrides)
        return settings

    def test_defers_to_15m_when_overlap_and_15m_ready(self):
        mock_trade, mock_log = self._run(self._s5(defer_to_15m_enabled=True), self._s15(), _zones_with_15m(23890.0))
        assert not mock_trade.called
        entries = [c.args[0] for c in mock_log.call_args_list if c.args[0]["trade_status"] == "SKIPPED_DEFERRED_TO_15M"]
        assert entries
        assert "23890.00" in entries[0]["reason"]

    def test_5m_trades_when_15m_strategy_disabled(self):
        mock_trade, mock_log = self._run(self._s5(defer_to_15m_enabled=True), self._s15(symbol_enabled=False), _zones_with_15m(23890.0))
        assert mock_trade.called

    def test_5m_trades_when_modes_differ(self):
        mock_trade, _ = self._run(self._s5(defer_to_15m_enabled=True), self._s15(trading_mode="LIVE"), _zones_with_15m(23890.0))
        assert mock_trade.called

    def test_5m_trades_when_15m_level_too_far(self):
        mock_trade, _ = self._run(self._s5(defer_to_15m_enabled=True), self._s15(), _zones_with_15m(23850.0))
        assert mock_trade.called

    def test_5m_trades_when_15m_level_has_opposite_direction(self):
        mock_trade, _ = self._run(self._s5(defer_to_15m_enabled=True), self._s15(), _zones_with_15m(23910.0, suffix="RESISTANCE"))
        assert mock_trade.called

    def test_disabled_by_default_ignores_overlap(self):
        mock_trade, _ = self._run(self._s5(), self._s15(), _zones_with_15m(23890.0))
        assert mock_trade.called

    def test_distance_setting_is_respected(self):
        # 0.03% मर्यादा -> 0.042% अंतरावरचा 15M level "जवळ" नाही -> 5M trade घेतो
        mock_trade, _ = self._run(self._s5(defer_to_15m_enabled=True, defer_to_15m_distance_pct=0.03), self._s15(), _zones_with_15m(23890.0))
        assert mock_trade.called


class TestYieldTo15mClosesFiveMinuteTrades:
    """🎓 वापरकर्त्याशी चर्चा करून ठरवलेली सुधारणा — 5M थांबतो तेव्हा त्याचे उघडे trades लगेच बंद (YIELDED_TO_15M),
    आणि 15M ची position उघडी असताना 5M नवीन entry घेत नाही ("एका वेळी एकच position")."""

    def test_deferral_closes_open_5m_family_trades(self):
        t = TestDeferTo15mGate()
        t.open_trades = [("T5", "dynamic_sr_instant", "PAPER"), ("SH1", "dynamic_sr_instant_otm_shadow", "PAPER")]
        mock_trade, _ = t._run(t._s5(defer_to_15m_enabled=True), t._s15(), _zones_with_15m(23890.0))
        assert not mock_trade.called
        closed = [c.args[1] for c in t.mock_close.call_args_list]
        assert closed == ["T5", "SH1"]
        assert all(c.kwargs["exit_reason"] == "YIELDED_TO_15M" for c in t.mock_close.call_args_list)

    def test_no_close_when_not_deferring(self):
        t = TestDeferTo15mGate()
        t.open_trades = [("T5", "dynamic_sr_instant", "PAPER")]
        mock_trade, _ = t._run(t._s5(defer_to_15m_enabled=True), t._s15(symbol_enabled=False), _zones_with_15m(23890.0))
        assert mock_trade.called
        assert not t.mock_close.called

    def test_no_close_when_feature_disabled(self):
        t = TestDeferTo15mGate()
        t.open_trades = [("T5", "dynamic_sr_instant", "PAPER")]
        t._run(t._s5(), t._s15(), _zones_with_15m(23890.0))
        assert not t.mock_close.called

    def test_5m_entry_blocked_while_15m_position_open(self):
        # 15M level जवळ नाही (5M निर्णय स्वतःचा), पण 15M ची position उघडी -> 5M entry नाही
        t = TestDeferTo15mGate()
        t.open_trades = [("T15", "srv2_momentum_reversal", "PAPER")]
        mock_trade, mock_log = t._run(t._s5(defer_to_15m_enabled=True), t._s15(), _zones_with_15m(23850.0))
        assert not mock_trade.called
        assert any(c.args[0]["trade_status"] == "SKIPPED_15M_POSITION_OPEN" for c in mock_log.call_args_list)

    def test_5m_entry_allowed_when_15m_position_is_other_mode(self):
        t = TestDeferTo15mGate()
        t.open_trades = [("T15", "srv2_momentum_reversal", "LIVE")]
        mock_trade, _ = t._run(t._s5(defer_to_15m_enabled=True), t._s15(), _zones_with_15m(23850.0))
        assert mock_trade.called

    def test_15m_position_does_not_block_5m_when_feature_disabled(self):
        t = TestDeferTo15mGate()
        t.open_trades = [("T15", "srv2_momentum_reversal", "PAPER")]
        mock_trade, _ = t._run(t._s5(), t._s15(), _zones_with_15m(23850.0))
        assert mock_trade.called

    def test_close_open_5m_positions_reports_failures(self):
        with patch.object(dsr, "get_open_trades_brief", return_value=[("A", "dynamic_sr_instant", "LIVE"), ("B", "dynamic_sr_instant", "LIVE")]), \
             patch.object(dsr, "close_trade_manually", side_effect=[(True, 10.0), (False, "LTP नाही")]):
            all_closed, closed, failed = dsr.close_open_5m_positions("tok", "NIFTY", "detail")
        assert all_closed is False and closed == ["A"] and failed == [("B", "LTP नाही")]

    def test_open_15m_position_exists_matches_mode(self):
        with patch.object(dsr, "get_open_trades_brief", return_value=[("T", "srv2_momentum_reversal", "PAPER")]):
            assert dsr.open_15m_position_exists("NIFTY", "PAPER") is True
            assert dsr.open_15m_position_exists("NIFTY", "LIVE") is False


class TestBreakoutSupertrendAlignmentHelper:
    def test_requires_both_to_match_direction(self):
        assert dsr.check_breakout_supertrend_alignment("BULLISH", "BULLISH", "BULLISH") == (True, None)
        assert dsr.check_breakout_supertrend_alignment("BEARISH", "BEARISH", "BEARISH") == (True, None)
        assert dsr.check_breakout_supertrend_alignment("BULLISH", "BULLISH", "BEARISH")[0] is False
        assert dsr.check_breakout_supertrend_alignment("BEARISH", "BULLISH", "BULLISH")[0] is False

    def test_missing_data_blocks(self):
        ok, reason = dsr.check_breakout_supertrend_alignment("BULLISH", None, "BULLISH")
        assert ok is False and "डेटा" in reason
        assert dsr.check_breakout_supertrend_alignment("BULLISH", "BULLISH", None)[0] is False
