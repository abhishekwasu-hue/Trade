"""tests/test_completed_bars_1h_fix.py -- fix/completed-bars-1h.
(१) `_completed_bars_only` NSE 1H (label :00, bar :15 ला संपतो) -- आणि त्याचे वापरकर्ते: 5M Instant bot (dynamic_sr_instant_trader), Dashboard Bot view
    (bot_view), MCX bot (mcx_futures_trader). MCX चं वर्तन बदलू नये.
(२) Lookahead audit: backtest/multi_strategy_backtest/bot_view मधली HTF alignment -- HTF bar LTF ला फक्त त्याच्या bar_end नंतर."""
import datetime

import numpy as np
import pandas as pd
import pytest

import backtest as bt
import bot_view as bv
import dynamic_sr_instant_trader as dsr
import mcx_futures_trader as mcx
import multi_strategy_backtest as msb
from htf_alignment import bar_end_times
from signals import resample_to_1h

DAY = "2024-03-12"


def _bars(start, end, freq, day=DAY):
    ts = pd.date_range(f"{day} {start}", f"{day} {end}", freq=freq)
    close = 100 + np.arange(len(ts), dtype=float)
    return pd.DataFrame({"timestamp": ts, "open": close - .5, "high": close + 1, "low": close - 1, "close": close, "volume": 10, "oi": 0})


def _upto(df, now):
    """फक्त आधीच सुरू झालेले bars (चालू/अपूर्ण bar सकट) -- Upstox intraday API सारखं."""
    return df[df["timestamp"] <= pd.Timestamp(now)].reset_index(drop=True)


def _hm(ts):
    return ts.strftime("%H:%M") if ts is not None else None


# =============================== (१) _completed_bars_only ===============================
class TestCompletedBarsNse1H:
    def _h1(self, now):
        return resample_to_1h(_upto(_bars("09:15", "15:15", "30min"), now))

    def test_bar_forming_in_the_old_buggy_window_is_dropped(self):
        """11:05 -- 10:00-label चा bar (10:15–11:15) अजून चालू; आधी (label+60 = 11:00) तो पूर्ण मानला जायचा."""
        now = datetime.datetime(2024, 3, 12, 11, 5)
        out = dsr._completed_bars_only(self._h1(now), 60, now)
        assert _hm(out["timestamp"].iloc[-1]) == "09:00"

    def test_bar_is_included_exactly_when_it_ends(self):
        now = datetime.datetime(2024, 3, 12, 11, 15)
        assert _hm(dsr._completed_bars_only(self._h1(now), 60, now)["timestamp"].iloc[-1]) == "10:00"
        now = datetime.datetime(2024, 3, 12, 11, 14)
        assert _hm(dsr._completed_bars_only(self._h1(now), 60, now)["timestamp"].iloc[-1]) == "09:00"

    def test_first_hour_is_incomplete_until_10_15(self):
        for minute, expect_empty in ((10, True), (14, True), (15, False)):
            now = datetime.datetime(2024, 3, 12, 10, minute)
            out = dsr._completed_bars_only(self._h1(now), 60, now)
            assert out.empty == expect_empty, (minute, out)

    def test_old_rule_would_have_been_wrong(self):
        """दुरुस्तीचं औचित्य: जुनं सूत्र (timestamp + 60) 11:05 ला 10:00-label bar पूर्ण मानतं, पण bar_end 11:15."""
        now = pd.Timestamp("2024-03-12 11:05")
        h1 = self._h1(now)
        last = h1.iloc[-1]
        assert last["timestamp"] + pd.Timedelta(minutes=60) <= now < last["bar_end"]

    def test_raw_start_labelled_bars_unchanged_5m_15m_30m(self):
        for freq, minutes in (("5min", 5), ("15min", 15), ("30min", 30)):
            df = _bars("09:15", "12:00", freq)
            assert "bar_end" not in df.columns
            last = df["timestamp"].iloc[-1]
            just_before = (last + pd.Timedelta(minutes=minutes) - pd.Timedelta(seconds=1)).to_pydatetime()
            at_end = (last + pd.Timedelta(minutes=minutes)).to_pydatetime()
            assert len(dsr._completed_bars_only(df, minutes, just_before)) == len(df) - 1
            assert len(dsr._completed_bars_only(df, minutes, at_end)) == len(df)

    def test_empty_none_and_tz_aware(self):
        assert dsr._completed_bars_only(None, 60, datetime.datetime(2024, 3, 12, 11)) is None
        empty = pd.DataFrame(columns=["timestamp"])
        assert dsr._completed_bars_only(empty, 60, datetime.datetime(2024, 3, 12, 11)).empty
        aware = resample_to_1h(_upto(_bars("09:15", "15:15", "30min"), "2024-03-12 11:05"))
        aware = aware.assign(timestamp=aware["timestamp"].dt.tz_localize("Asia/Kolkata"), bar_end=aware["bar_end"].dt.tz_localize("Asia/Kolkata"))
        now = datetime.datetime(2024, 3, 12, 11, 5)
        assert _hm(dsr._completed_bars_only(aware, 60, now)["timestamp"].iloc[-1]) == "09:00"


# ===================== वापरकर्ते: प्रत्येक live/paper/display ठिकाणासाठी test =====================
class TestEveryUserOfCompletedBarsOnly:
    NOW = datetime.datetime(2024, 3, 12, 11, 5)

    @staticmethod
    def _recorder(monkeypatch, module):
        seen = []

        def fake(df, period, multiplier):
            seen.append(None if df is None or df.empty else df["timestamp"].iloc[-1])
            return "BULLISH"

        monkeypatch.setattr(module, "get_supertrend_direction", fake)
        return seen

    def test_5m_instant_bot_trend_filter_uses_only_completed_15m_and_1h(self, monkeypatch):
        """dynamic_sr_instant_trader.fetch_trend_filter_directions -- NSE (5M Instant `1m_instant`; paper/live bot)."""
        d30, d15 = _bars("09:15", "15:15", "30min"), _bars("09:15", "15:00", "15min")

        def fake_fetch(token, symbol, current_spot=0, interval="15minute", lookback_days=5):
            return _upto(d15 if interval == "15minute" else d30, self.NOW)

        monkeypatch.setattr(dsr, "fetch_candles", fake_fetch)
        seen = self._recorder(monkeypatch, dsr)
        dir_15m, dir_1h = dsr.fetch_trend_filter_directions("tok", "NIFTY", self.NOW)
        assert (dir_15m, dir_1h) == ("BULLISH", "BULLISH")
        assert _hm(seen[0]) == "10:45"            # 15M: 11:00 चा bar (11:00–11:15) अजून चालू
        assert _hm(seen[1]) == "09:00"            # 1H: 10:00-label चा bar (10:15–11:15) अजून चालू -- हीच दुरुस्ती

    def test_dashboard_bot_view_supertrend_directions(self, monkeypatch):
        """bot_view.supertrend_directions -- Dashboard चार्टचा 'Bot view' (5M Instant): फक्त दाखवतो, trade नाही."""
        d30, d15 = _bars("09:15", "15:15", "30min"), _bars("09:15", "15:00", "15min")
        frames = {"15M": _upto(d15, self.NOW), "1H": resample_to_1h(_upto(d30, self.NOW))}
        seen = self._recorder(monkeypatch, bv)
        specs = bv.supertrend_specs("5M Instant", {})
        assert [s["label"] for s in specs] == ["15M", "1H"]
        out = bv.supertrend_directions(frames, specs, self.NOW)
        assert out == {"15M": "BULLISH", "1H": "BULLISH"}
        assert (_hm(seen[0]), _hm(seen[1])) == ("10:45", "09:00")

    def test_mcx_bot_trend_filter_unchanged(self, monkeypatch):
        """mcx_futures_trader.fetch_mcx_trend_filter_directions -- MCX (09:00-anchored): 1H/4H bar_end == label + कालावधी, म्हणजे वर्तन तेच."""
        d30 = _bars("09:00", "22:30", "30min")

        monkeypatch.setattr(mcx, "fetch_mcx_candles", lambda token, key, interval="30minute", lookback_days=20: _upto(d30, self.NOW))
        seen = self._recorder(monkeypatch, mcx)
        assert mcx.fetch_mcx_trend_filter_directions("tok", "KEY", self.NOW) == ("BULLISH", "BULLISH")
        assert _hm(seen[0]) == "10:00"            # 1H: 10:00–11:00 पूर्ण (11:05)
        assert seen[1] is None                     # 4H: 09:00–13:00 अजून चालू ⇒ पूर्ण bar नाही
        late = datetime.datetime(2024, 3, 12, 13, 0)
        seen.clear()
        monkeypatch.setattr(mcx, "fetch_mcx_candles", lambda token, key, interval="30minute", lookback_days=20: _upto(d30, late))
        mcx.fetch_mcx_trend_filter_directions("tok", "KEY", late)
        assert (_hm(seen[0]), _hm(seen[1])) == ("12:00", "09:00")      # 13:00 ला 4H (09:00–13:00) पूर्ण

    def test_5m_candles_in_process_symbol_use_label_plus_5(self):
        """dynamic_sr_instant_trader मधला 5M वापर (`_completed_bars_only(todays_5m_df, 5, now)`): थेट Upstox bars, bar_end column नाही ⇒ जुनं वर्तन."""
        df = _bars("09:15", "11:00", "5min")
        assert len(dsr._completed_bars_only(df, 5, datetime.datetime(2024, 3, 12, 11, 4))) == len(df) - 1
        assert len(dsr._completed_bars_only(df, 5, datetime.datetime(2024, 3, 12, 11, 5))) == len(df)


# ============================= (२) lookahead audit: alignment =============================
def _htf_dir_values(n):
    """प्रत्येक 1H bar ला आलटून पालटून +1/−1 -- lookahead असेल तर लगेच दिसतं."""
    return np.array([1 if i % 2 == 0 else -1 for i in range(n)])


def _fake_supertrend(monkeypatch, module):
    def fake(df, period=10, multiplier=3):
        return pd.Series(np.arange(len(df), dtype=float)), pd.Series(_htf_dir_values(len(df)))
    monkeypatch.setattr(module, "calculate_supertrend", fake)


def _expected_direction(ltf, htf):
    """स्वतंत्र (align_asof न वापरता) अपेक्षित: LTF bar च्या bar_end पर्यंत पूर्ण झालेला शेवटचा HTF bar."""
    ltf_end, htf_end = bar_end_times(ltf), bar_end_times(htf)
    dirs = _htf_dir_values(len(htf))
    out = []
    for t in ltf_end:
        done = [i for i, e in enumerate(htf_end) if e <= t]
        out.append(dirs[done[-1]] if done else None)
    return out


class TestAlignmentHasNoLookahead:
    def _frames(self):
        days = ("2024-03-11", "2024-03-12")
        l15 = pd.concat([_bars("09:15", "15:15", "15min", d) for d in days], ignore_index=True)
        h1 = resample_to_1h(pd.concat([_bars("09:15", "15:15", "30min", d) for d in days], ignore_index=True))
        return l15, h1

    def test_multi_strategy_backtest_1h_direction(self, monkeypatch):
        _fake_supertrend(monkeypatch, msb)
        l15, h1 = self._frames()
        got = [None if pd.isna(x) else x for x in msb._align_1h_direction(l15, h1).tolist()]       # जुन्या कोडप्रमाणेच अनुपलब्ध = NaN/None
        want = [None if e is None else ("LONG" if e == 1 else "SHORT") for e in _expected_direction(l15, h1)]
        assert got == want
        assert got[:3] == [None, None, None]                      # 09:15/09:30/09:45 -- कुठलाच 1H bar पूर्ण नाही (आधी: पहिल्या bar चा अंतिम निकाल)
        by = dict(zip([t.strftime("%d %H:%M") for t in l15["timestamp"]], got))
        assert by["11 10:00"] == "LONG" and by["11 10:15"] == "LONG"        # पहिला 1H bar (idx0=+1) 10:15 ला बंद; 10:15 चा 15M bar त्याला पाहतो
        assert by["11 10:30"] == "LONG" and by["11 11:00"] == "SHORT"      # दुसरा (idx1=−1) 11:15 ला बंद ⇒ 11:00 चा 15M bar (11:15 ला बंद)

    def test_multi_strategy_backtest_1h_sr_levels(self, monkeypatch):
        calls = []

        def fake_sr(window, top_n=3):
            calls.append(len(window))
            return {"support": [{"level": float(len(window)), "touches": 9}], "resistance": []}

        monkeypatch.setattr(msb, "find_support_resistance_levels", fake_sr)
        days = ("2024-03-11", "2024-03-12", "2024-03-13")
        l15 = pd.concat([_bars("09:15", "15:15", "15min", d) for d in days], ignore_index=True)
        h1 = resample_to_1h(pd.concat([_bars("09:15", "15:15", "30min", d) for d in days], ignore_index=True))
        got = msb._align_1h_sr_levels(l15, h1, min_touches=3)
        htf_end, ltf_end = bar_end_times(h1), bar_end_times(l15)
        for i, sr in enumerate(got):
            done = [k for k, e in enumerate(htf_end) if e <= ltf_end.iloc[i]]
            if not done or done[-1] + 1 < 10:                       # window < 10 bars ⇒ S/R नाही (जुनं वर्तन)
                assert sr is None or not done
            else:
                assert sr["support"][0]["level"] == float(min(done[-1] + 1, 100))
        # विशेषतः: 1H bar #k चे S/R (त्या bar च्या high/low/close सकट) त्या bar च्या bar_end च्या आधी कुठल्याही 15M bar ला नको
        first_with_sr = next(i for i, sr in enumerate(got) if sr is not None)
        assert ltf_end.iloc[first_with_sr] >= htf_end.iloc[9]

    def test_bot_view_align_supertrend(self, monkeypatch):
        _fake_supertrend(monkeypatch, bv)
        l15, h1 = self._frames()
        line, direction = bv.align_supertrend(l15, h1, 10, 3.0)
        # fake line = 0..n-1; पहिला 1H bar (line=0) पूर्ण झाल्यावरच दिसतो. dropna (line=0 ठीक) -- काहीही गाळलं जात नाही
        want = _expected_direction(l15, h1)
        assert [None if pd.isna(x) else int(x) for x in direction] == [None if w is None else int(w) for w in want]
        assert direction.iloc[:3].isna().all()

    def test_backtest_v2_and_rr_use_bar_end_alignment(self, monkeypatch):
        """backtest.run_signal_backtest_v2 / run_signal_backtest_rr: प्रत्येक bar ला मिळालेली दिशा = bar_end आधारित अपेक्षित."""
        _fake_supertrend(monkeypatch, bt)
        days = ("2024-03-11", "2024-03-12", "2024-03-13", "2024-03-14")
        l15 = pd.concat([_bars("09:15", "15:15", "15min", d) for d in days], ignore_index=True)
        h1 = resample_to_1h(pd.concat([_bars("09:15", "15:15", "30min", d) for d in days], ignore_index=True))
        want = _expected_direction(l15, h1)

        seen_v2 = {}
        monkeypatch.setattr(bt, "check_price_action_strategy",
                            lambda window, direction, **kw: (seen_v2.__setitem__(window["timestamp"].iloc[-1], direction), (False, ""))[1])
        bt.run_signal_backtest_v2(l15, h1, strategy="price_action", min_lookback=30)
        assert seen_v2, "काही bars तपासले गेले पाहिजेत"
        index_of = {t: i for i, t in enumerate(l15["timestamp"])}
        for t, d in seen_v2.items():
            w = want[index_of[t]]
            assert w is not None and d == ("BULLISH" if w == 1 else "BEARISH")

        seen_rr = {}
        monkeypatch.setattr(bt, "classify_market_structure", lambda window, **kw: {"structure": "HH/HL"})
        monkeypatch.setattr(bt, "detect_break", lambda window, structure, direction: (seen_rr.__setitem__(window["timestamp"].iloc[-1], direction), (False, None))[1])
        bt.run_signal_backtest_rr(l15, df_direction=h1, min_lookback=30)
        assert seen_rr
        for t, d in seen_rr.items():
            w = want[index_of[t]]
            assert w is not None and d == ("BULLISH" if w == 1 else "BEARISH")

    def test_alignment_is_robust_to_missing_bar_end_on_the_htf_frame(self, monkeypatch):
        """HTF df कडे bar_end नसेल (उदा. yfinance तासाचे bars: label = खरी सुरुवात) -- label + अनुमानित कालावधी, crash नाही."""
        _fake_supertrend(monkeypatch, msb)
        l15 = _bars("09:15", "15:15", "15min")
        h1 = _bars("09:15", "14:15", "60min")             # label = खरी सुरुवात, bar_end column नाही
        out = msb._align_1h_direction(l15, h1)
        assert out.iloc[:3].isna().all() or out.iloc[:3].tolist() == [None, None, None]
        assert out.iloc[-1] in ("LONG", "SHORT")
