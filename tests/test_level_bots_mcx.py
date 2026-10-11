"""Level bots confirmation (Abhi §1/§3, L4) — MCX: trend = decision3 Daily (सध्याच्या contract चे Daily candles), areas = bot चे 30M/60M
levels, confirmation = contract चे बंद 15M candles, volume = contract चाच. खरा gate (bots_common.level_gate_bot / level_reaction) synthetic
bars वर; Upstox, DB, broker, Telegram — सगळे fakes. PAPER ⇒ CONFIRMED नंतरच PAPER order (MCX ला अजून Vision approval नाही); LIVE ⇒ जुनं touch."""
import pandas as pd
import pytest

import cloud_db
import mcx_futures_trader as mft
from bots_common import level_gate_bot as LGB
from bots_common import level_reaction as LR
from tests.test_level_bots_classic_srv2 import (ARMED_ROWS, CONFIRMED_ROWS, DOWN, DRIVE_ROWS, LEVEL, TARGET_LEVEL, UP, Rec, _bars,
                                                _would_have)
from tests.test_mcx_futures_trader import _fake_resolved

SYMBOL = "CRUDEOIL"
_DEFAULT_SETTINGS = {**cloud_db.STRATEGY_SETTINGS_DEFAULTS["mcx_futures"], "symbol_enabled": True, "trading_mode": "PAPER",
                     "gate_area_pad_pct": 1.0, "supertrend_filter_mode": "off", "sl_points": 50, "target_points": 40}


def _c30(day, last_close):
    """bot चे 30M candles (touch candidates / सद्य भाव): आदल्या दिवसाचे + आजचे, शेवटचा close = सद्य भाव."""
    d = pd.Timestamp(day).normalize()
    ts = [d - pd.Timedelta(days=1) + pd.Timedelta(hours=9, minutes=30 * i) for i in range(14)]
    ts += [d + pd.Timedelta(hours=9, minutes=30 * i) for i in range(4)]
    closes = [1030.0] * 17 + [float(last_close)]
    return pd.DataFrame({"timestamp": ts, "open": closes, "high": [c + 2 for c in closes], "low": [c - 2 for c in closes],
                         "close": closes, "volume": 0, "oi": 0})


class Harness:
    def __init__(self, monkeypatch, tmp_path, rows, ctx=UP, settings=None, price=1008.0, daily=None, hits=(0, None, None)):
        self.bars15 = _bars(rows, 15)
        self.now = (self.bars15["timestamp"].iloc[-1] + pd.Timedelta(minutes=16)).to_pydatetime()
        s = dict(_DEFAULT_SETTINGS)
        s.update(settings or {})
        self.settings = s
        mp = monkeypatch
        mp.setattr(LGB, "entry_mode", LGB._entry_mode_orig)          # खरा default (PAPER ⇒ confirmation; LIVE ⇒ touch)
        mp.setattr(LGB, "_TOUCH_SEEN", set())
        mp.setattr(LR, "_cache_path", lambda sym, day, cache_dir=None: str(tmp_path / f"trend_{sym}_{day}.json"))
        self.trend = Rec(ctx)
        if ctx is not None:
            mp.setattr(LR, "daily_trend", self.trend)
        mp.setattr(LGB, "_default_futures_candles", Rec(exc=AssertionError("MCX ला NSE futures resolver नको")))
        self.c30 = _c30(self.now, price)
        self.daily = daily
        self.fetch = Rec(self._fetch)
        mp.setattr(mft, "fetch_mcx_candles", self.fetch)
        mp.setattr(mft, "CONTRACT_STATE", str(tmp_path / "contract.json"))
        mp.setattr(mft, "CANDLE_STATE", str(tmp_path / "candle.json"))
        mp.setattr(mft, "GATE_USED_STATE", str(tmp_path / "level_gate" / "mcx_confirm_used.json"))
        mp.setattr(mft, "MCX_NO_NEW_ENTRY_AFTER", (24, 0))
        mp.setattr(mft, "get_closed_trades_on_date", lambda *a, **k: [])
        mp.setattr(mft, "get_ist_now", lambda: self.now)
        mp.setattr(mft.cloud_db, "get_strategy_settings", lambda *a, **k: dict(s))
        mp.setattr(mft.mcx_resolver, "resolve_symbol", lambda *a, **k: _fake_resolved())
        zones = pd.DataFrame([
            {"symbol": SYMBOL, "zone_type": "DYNAMIC_SR_SUPPORT_30M", "zone_low": LEVEL, "zone_high": LEVEL, "strength": 3.0,
             "formed_date": "2026-09-01", "status": "ACTIVE"},
            {"symbol": SYMBOL, "zone_type": "DYNAMIC_SR_RESISTANCE_30M", "zone_low": TARGET_LEVEL, "zone_high": TARGET_LEVEL,
             "strength": 2.0, "formed_date": "2026-09-01", "status": "ACTIVE"}])
        mp.setattr(mft.cloud_db, "get_market_zones", lambda *a, **k: zones)
        mp.setattr(mft.cloud_db, "get_zone_hits_today", lambda *a, **k: hits)
        self.logs = []
        mp.setattr(mft.cloud_db, "save_signal_log", lambda e: self.logs.append(dict(e)) or True)
        mp.setattr(mft, "has_open_trade_from_source", lambda *a, **k: False)
        self.rsi = Rec((True, 30.0))
        mp.setattr(mft, "check_instant_rsi_filter", self.rsi)
        self.trade = Rec(({"trade_id": "T1"}, "OPENED"))
        mp.setattr(mft, "open_multi_leg_trade", self.trade)
        self.tg = Rec(True)
        mp.setattr(mft, "send_telegram_message", self.tg)
        self.breakout = Rec(True)
        mp.setattr(mft, "check_breakout_price_consolidation", self.breakout)

    def _fetch(self, tok, key, interval="30minute", lookback_days=None):
        assert key == "MCX_FO|12345"                                       # नेहमी resolve झालेला contract
        if interval == "15minute":
            return self.bars15.copy()
        if interval == "30minute":
            return self.c30.copy()
        if interval == "day":
            if isinstance(self.daily, Exception):
                raise self.daily
            return self.daily
        return None

    def run(self):
        return mft._process_symbol_core("fake_token", SYMBOL, {})

    def level_logs(self):
        return [e for e in self.logs if abs(float(e["level_price"]) - LEVEL) < 1e-6]

    def statuses(self):
        return [e["trade_status"] for e in self.level_logs()]


def _legacy_rows(name="mcx_futures"):
    return [x for x in _would_have() if x["bot"] == f"{name}_touch_legacy"]


def test_no_reaction_no_entry_and_no_telegram(monkeypatch, tmp_path):
    h = Harness(monkeypatch, tmp_path, ARMED_ROWS, price=1008.0)
    h.run()
    assert not h.trade.calls and not h.tg.calls
    assert h.statuses() == ["SKIPPED_GATE_WAITING_COMMITMENT"]
    assert h.level_logs()[0]["hit_type"] == "NO_HIT" and h.level_logs()[0]["reason"].startswith("[GATE] Watching demand")


def test_confirmed_places_paper_order_with_gate_side_and_structural_sl(monkeypatch, tmp_path):
    h = Harness(monkeypatch, tmp_path, CONFIRMED_ROWS, price=1008.0)
    out = h.run()
    assert len(h.trade.calls) == 1, out
    a, k = h.trade.calls[0]
    leg = a[2]["legs"][0]
    assert leg["transaction_type"] == "BUY" and k["trading_mode"] == "PAPER" and k["source"] == "mcx_futures"
    assert k["lots"] == 1 and k["entry_level_price"] == LEVEL and k["entry_timeframe"] == "30M"
    # gate plan: SL = sweep low च्या पलीकडे, target = पुढचा area (TARGET_LEVEL − 1% pad) — points सद्य भावापासून
    sl_pts, tgt_pts = a[2]["max_loss"], a[2]["max_profit"]
    assert 15 < sl_pts < 30 and tgt_pts == pytest.approx(TARGET_LEVEL * 0.995 - 1008.0, abs=0.01) and tgt_pts / sl_pts >= 3
    log = [e for e in h.level_logs() if e["hit_type"] == "CONFIRMED"]
    assert len(log) == 1 and log[0]["direction"] == "BULLISH" and log[0]["level_type"] == "SUPPORT"
    assert "[GATE] CONFIRMED demand" in log[0]["reason"] and "🎯 Gate: SL" in log[0]["reason"]
    assert not h.rsi.calls                                                 # confirmation ⇒ RSI threshold gate default बंद
    assert len(h.tg.calls) == 1 and "15M commitment" in h.tg.calls[0][0][0] and "inside demand" in h.tg.calls[0][0][0]
    # trend: decision3 Daily — contract चं trading_symbol (cache key, NSE शी टक्कर नाही), fetch = त्याच contract चे "day" candles
    ta, tk = h.trend.calls[0]
    assert ta[0] == "CRUDEOIL26SEPFUT" and tk["fetch"] is not None
    h.daily = pd.DataFrame()
    tk["fetch"]("fake_token", ta[0])
    assert h.fetch.calls[-1][1]["interval"] == "day" and h.fetch.calls[-1][1]["lookback_days"] == mft.MCX_TREND_LOOKBACK_DAYS
    assert not _legacy_rows()


def test_confirmed_but_structural_sl_wider_than_settings_sl_skips(monkeypatch, tmp_path):
    h = Harness(monkeypatch, tmp_path, CONFIRMED_ROWS, settings={"sl_points": 10}, price=1008.0)
    h.run()
    assert not h.trade.calls and not h.tg.calls
    assert "SKIPPED_GATE_SL_TOO_WIDE" in h.statuses()


def test_against_trend_ignored(monkeypatch, tmp_path):
    h = Harness(monkeypatch, tmp_path, CONFIRMED_ROWS, ctx=DOWN, price=1008.0)
    h.run()
    assert not h.trade.calls and not h.tg.calls
    assert h.statuses() == ["SKIPPED_GATE_AGAINST_TREND"]


def test_breakout_entry_off_in_confirmation(monkeypatch, tmp_path):
    """उलट role वर 2 hits + consolidation ⇒ touch mode मध्ये breakout trade; confirmation ⇒ breakout तपासणीच नाही, trade नाही."""
    h = Harness(monkeypatch, tmp_path, DRIVE_ROWS, settings={"entry_breakout_gate_enabled": True}, price=957.0, hits=(2, None, None))
    h.run()
    assert not h.breakout.calls and not h.trade.calls and not h.tg.calls
    assert all(s.startswith("SKIPPED_GATE_") for s in h.statuses())


@pytest.mark.parametrize("daily, why", [(RuntimeError("upstox down"), "SKIPPED_GATE_ERROR"),
                                         (None, "SKIPPED_GATE_NO_TREND"),
                                         ("short", "SKIPPED_GATE_NO_TREND")])
def test_trend_unavailable_fail_closed(monkeypatch, tmp_path, daily, why):
    """Daily fetch अपयशी / रिकामा / gate च्या किमान 30 bars पेक्षा कमी (एकाच contract चा इतिहास) ⇒ entry नाही, कारण नोंदीत."""
    if daily == "short":
        daily = pd.DataFrame({"timestamp": pd.date_range("2026-08-20", periods=12, freq="D"), "open": 1000.0, "high": 1010.0,
                              "low": 990.0, "close": 1000.0, "volume": 1, "oi": 0})
    h = Harness(monkeypatch, tmp_path, CONFIRMED_ROWS, ctx=None, daily=daily, price=1008.0)
    h.run()
    assert not h.trade.calls and not h.tg.calls
    assert h.statuses() == [why]
    assert any(c[1].get("interval") == "day" for c in h.fetch.calls)
    if why == "SKIPPED_GATE_NO_TREND" and daily is not None:
        assert "Daily data अपुरा: 12 bars" in h.level_logs()[0]["reason"]
    assert not [p for p in tmp_path.glob("trend_*.json") if not p.name.endswith("_fail.json")]   # अपयशी / अपूर्ण fetch दिवसाचा cache नाही
    assert len(list(tmp_path.glob("trend_*_fail.json"))) == 1             # … फक्त negative cache (trend_retry_min, fail-closed)


def test_gate_exception_fail_closed(monkeypatch, tmp_path):
    h = Harness(monkeypatch, tmp_path, CONFIRMED_ROWS, price=1008.0)
    monkeypatch.setattr(LGB, "cycle_gate", Rec(exc=RuntimeError("boom")))
    h.run()
    assert not h.trade.calls and h.statuses() == ["SKIPPED_GATE_ERROR"]


def test_live_unchanged_touch_mode_no_gate(monkeypatch, tmp_path):
    h = Harness(monkeypatch, tmp_path, CONFIRMED_ROWS, settings={"trading_mode": "LIVE"}, price=995.5)
    gate = Rec(exc=AssertionError("LIVE ⇒ gate नको"))
    monkeypatch.setattr(LGB, "cycle_gate", gate)
    h.run()
    assert not gate.calls and not h.trend.calls
    assert len(h.trade.calls) == 1 and h.trade.calls[0][1]["trading_mode"] == "LIVE"
    a = h.trade.calls[0][0]
    assert a[2]["max_loss"] == 50 and a[2]["max_profit"] == 40               # settings SL / target (जुनं)
    assert h.rsi.calls                                                     # touch mode ⇒ RSI gate जसा होता
    assert [e["hit_type"] for e in h.level_logs()] == ["TOUCH"] and not _legacy_rows()


def test_legacy_touch_is_would_have_only(monkeypatch, tmp_path):
    h = Harness(monkeypatch, tmp_path, ARMED_ROWS, price=995.5)            # सद्य भाव level ला touch (जुना नियम) पण commitment नाही
    h.run()
    h.run()                                                                # दुसरा cycle ⇒ पुन्हा नोंद नाही
    assert not h.trade.calls and not h.tg.calls
    assert h.statuses() == ["SKIPPED_GATE_WAITING_COMMITMENT"] * 2
    assert h.level_logs()[0]["hit_type"] == "TOUCH"
    wh = _legacy_rows()
    assert len(wh) == 1 and wh[0]["orig_lots"] == 0 and wh[0]["status"] == "TOUCH_LEGACY" and wh[0]["symbol"] == SYMBOL
    assert wh[0]["setup_tf"] == "30M" and abs(wh[0]["level"] - LEVEL) < 1e-6


def test_gate_uses_contract_15m_bars_and_own_volume(monkeypatch, tmp_path):
    """_build_mcx_gate: 15M = resolve झालेल्या contract चे, volume = त्याच candles चा (NSE resolver नाही), trend fetch त्याच contract चा."""
    monkeypatch.setattr(LGB, "_default_futures_candles", Rec(exc=AssertionError("NSE resolver नको")))
    monkeypatch.setattr(LR, "daily_trend", lambda *a, **k: UP)
    bars = _bars(CONFIRMED_ROWS, 15)
    bars["volume"] = range(100, 100 + len(bars))
    calls = []

    def fake(tok, key, interval="30minute", lookback_days=None):
        calls.append((key, interval))
        return bars.copy()
    monkeypatch.setattr(mft, "fetch_mcx_candles", fake)
    now = bars["timestamp"].iloc[-1] + pd.Timedelta(minutes=16)
    g, err = mft._build_mcx_gate("tok", SYMBOL, _fake_resolved()[1], dict(_DEFAULT_SETTINGS),
                                 [mft._gate_area(LEVEL, _DEFAULT_SETTINGS), mft._gate_area(TARGET_LEVEL, _DEFAULT_SETTINGS)], now)
    assert err is None and g.err is None
    assert calls == [("MCX_FO|12345", "15minute")]                          # एकच fetch (volume साठी पुन्हा नाही)
    assert list(g.bars["volume"]) == list(bars["volume"].astype(float))
    r = g.result(*mft._gate_area(LEVEL, _DEFAULT_SETTINGS))
    assert r["entry"] and r["side"] == LR.BULL


# ------------------------------------------------------------------------------------------------ review 🟡2 / 🟡7
def test_same_confirmation_not_reentered_after_quick_exit(monkeypatch, tmp_path):
    """gate चा entry पूर्ण 15M bar भर True ⇒ लवकर exit नंतर (position उघडी नाही) पुढच्या मिनिटाच्या नव्या process मध्ये त्याच commitment
    candle वर पुन्हा entry नाही — वापरलेली confirmation file मध्ये (process पलीकडे टिकते)."""
    h = Harness(monkeypatch, tmp_path, CONFIRMED_ROWS, price=1008.0)
    h.run()
    assert len(h.trade.calls) == 1
    h.now = h.now + pd.Timedelta(minutes=1)                                # त्याच 15M bar मध्ये पुढचा cycle (bar अजून शेवटचा बंद candle)
    h.run()
    assert len(h.trade.calls) == 1 and len(h.tg.calls) == 1
    used = [e for e in h.level_logs() if e["trade_status"] == "SKIPPED_GATE_CONFIRM_USED"]
    assert len(used) == 1 and used[0]["hit_type"] == "CONFIRMED" and "आधीच entry झाली" in used[0]["reason"]
    assert (tmp_path / "level_gate" / "mcx_confirm_used.json").exists()


def test_failed_order_does_not_burn_the_confirmation(monkeypatch, tmp_path):
    h = Harness(monkeypatch, tmp_path, CONFIRMED_ROWS, price=1008.0)
    h.trade.ret = (False, {"status": "error", "reason": "rms"})
    h.run()
    h.trade.ret = ({"trade_id": "T2"}, "OPENED")
    h.run()                                                                # पुढच्या cycle ला पुन्हा प्रयत्न चालतो
    assert len(h.trade.calls) == 2


def test_confirm_used_is_per_level_and_commitment_candle(tmp_path):
    p = str(tmp_path / "u.json")
    r = {"confirm_ts": "2026-09-11 11:00:00"}
    assert not mft._gate_confirm_used(SYMBOL, "mcx_futures", LEVEL, r, p)
    mft._gate_mark_used(SYMBOL, "mcx_futures", LEVEL, r, p)
    assert mft._gate_confirm_used(SYMBOL, "mcx_futures", LEVEL, r, p)
    assert not mft._gate_confirm_used(SYMBOL, "mcx_futures", LEVEL, {"confirm_ts": "2026-09-11 11:15:00"}, p)   # नवी commitment ⇒ चालते
    assert not mft._gate_confirm_used(SYMBOL, mft.SRV3_SHADOW_SOURCE, LEVEL, r, p)                              # shadow स्वतंत्र
    assert not mft._gate_confirm_used(SYMBOL, "mcx_futures", TARGET_LEVEL, r, p)


def _plan(side):
    """BULLISH plan आणि त्याचा आरसा (किंमती 2000 − x): pts तेच, दिशा उलट."""
    bull = {"sl": 985.0, "target": 1085.0}
    return bull if side == "BULLISH" else {"sl": 2000 - bull["sl"], "target": 2000 - bull["target"]}


def _px(side, x):
    return x if side == "BULLISH" else 2000 - x


@pytest.mark.parametrize("side", ["BULLISH", "BEARISH"])
def test_gate_sl_target_mirror(side):
    s = dict(_DEFAULT_SETTINGS)                                            # sl_points 50 = कमाल, min_rr 3
    sl, tgt, skip = mft._gate_sl_target(_plan(side), _px(side, 1008.0), side, s)
    assert skip is None and sl == pytest.approx(23.0) and tgt == pytest.approx(77.0)
    assert mft._gate_sl_target(_plan(side), _px(side, 980.0), side, s)[2][0] == "SKIPPED_GATE_INVALIDATED"
    assert mft._gate_sl_target(_plan(side), _px(side, 1090.0), side, s)[2][0] == "SKIPPED_GATE_TARGET_PASSED"
    assert mft._gate_sl_target(_plan(side), _px(side, 1008.0), side, {**s, "sl_points": 20})[2][0] == "SKIPPED_GATE_SL_TOO_WIDE"
    assert mft._gate_sl_target(_plan(side), _px(side, 1025.0), side, s)[2][0] == "SKIPPED_GATE_RR"     # 60 / 40 < 3


def _shadow(monkeypatch, h):
    orig = mft._collect_touch_candidates
    monkeypatch.setattr(mft, "refresh_mcx_srv3_levels_if_due", lambda *a, **k: None)
    monkeypatch.setattr(mft, "_collect_srv3_candidates", lambda tok, key, zones, suf, now, grade_a_only=False: orig(tok, key, zones, suf, now))
    monkeypatch.setattr(mft, "count_entries_at_level_today", lambda *a, **k: 0)
    return mft._process_symbol_core("fake_token", SYMBOL, {}, level_source="SRV3", shadow=True)


def test_shadow_follows_paper_main_into_confirmation(monkeypatch, tmp_path):
    h = Harness(monkeypatch, tmp_path, CONFIRMED_ROWS, price=1008.0)
    real = LGB.cycle_gate
    calls = []
    monkeypatch.setattr(LGB, "cycle_gate", lambda *a, **k: calls.append(a) or real(*a, **k))
    _shadow(monkeypatch, h)
    assert calls and calls[0][0] == "mcx"                                  # PAPER main ⇒ shadow सुद्धा confirmation gate
    assert len(h.trade.calls) == 1
    a, k = h.trade.calls[0]
    assert k["source"] == mft.SRV3_SHADOW_SOURCE and k["trading_mode"] == "PAPER" and a[2]["legs"][0]["transaction_type"] == "BUY"
    assert not h.logs                                                      # shadow signal_log मध्ये लिहीत नाही


def test_shadow_stays_touch_when_main_is_live(monkeypatch, tmp_path):
    h = Harness(monkeypatch, tmp_path, CONFIRMED_ROWS, settings={"trading_mode": "LIVE"}, price=995.5)
    gate = Rec(exc=AssertionError("LIVE main ⇒ shadow ला gate नको"))
    monkeypatch.setattr(LGB, "cycle_gate", gate)
    _shadow(monkeypatch, h)
    assert not gate.calls and not h.trend.calls
    assert len(h.trade.calls) == 1
    a, k = h.trade.calls[0]
    assert k["source"] == mft.SRV3_SHADOW_SOURCE and k["trading_mode"] == "PAPER"
    assert a[2]["max_loss"] == 50 and a[2]["max_profit"] == 40               # touch: settings SL / target
