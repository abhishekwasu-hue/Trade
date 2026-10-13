"""Level bots confirmation (Abhi §9) — 15M SRv2 आणि Classic SR: trend + बंद candle वर commitment नंतरच, आणि CONFIRMED सुद्धा थेट entry
नाही — vision.gate.entry_gate (✅ approval) मार्गेच. खरा gate (bots_common.level_gate_bot / level_reaction) synthetic bars वर; Daily trend,
candles, vision gate, broker — सगळे fakes. LIVE ⇒ gate कधीच नाही (जुनं touch वर्तन)."""
import pandas as pd
import pytest

import classic_sr_reversal_trader as csr
import cloud_db
import srv2_momentum_reversal_strategy as srv2
from bots_common import level_gate_bot as LGB
from bots_common import level_reaction as LR
from vision import config as VC
from vision import gate as VG

UP = {"ok": True, "trend": "UP", "sides": {LR.BULL}, "band": None, "reason": "Daily UP"}
DOWN = {"ok": True, "trend": "DOWN", "sides": {LR.BEAR}, "band": None, "reason": "Daily DOWN"}
LEVEL, TARGET_LEVEL = 995.0, 1095.0                       # demand area ≈ 990–1000 (gate_area_pad_pct 1%), पुढचा area ≈ 1090–1100

PULL = [(1030, 1031, 1024, 1025), (1025, 1027, 1018, 1019), (1019, 1021, 1012, 1013), (1013, 1015, 1006, 1007), (1007, 1009, 1001, 1002)]
TOUCH = (1002, 1003, 995, 999)
SWEEP = (999, 1000, 987, 997)
BULL_ENGULF = (996, 1009, 995, 1008)
CONFIRMED_ROWS = PULL + [TOUCH, SWEEP, BULL_ENGULF]                # शेवटचा बंद candle = commitment ⇒ entry
ARMED_ROWS = PULL + [TOUCH, SWEEP, (999, 1001, 996, 998)]          # area ला स्पर्श, प्रतिक्रिया नाही
DRIVE_ROWS = [(1030, 1031, 1012, 1013), (1013, 1014, 994, 995), (995, 996, 970, 971), (971, 972, 960, 961), (961, 962, 955, 957)]

TOUCH_1M = [{"timestamp": pd.Timestamp("2026-09-11 11:15"), "open": 996.0, "high": 1000.0, "low": 994.0, "close": 997.0}] * 2
AWAY_1M = [{"timestamp": pd.Timestamp("2026-09-11 11:15"), "open": 1008.0, "high": 1009.0, "low": 1007.0, "close": 1008.0}] * 2


def _bars(rows, tf):
    d = pd.Timestamp("2026-09-11 09:15")
    pre = [(1030.0, 1034.0, 1026.0, 1030.0)] * 30                  # आदल्या दिवसाचे शांत bars (median range साठी)
    ts = [d - pd.Timedelta(days=1) + pd.Timedelta(minutes=tf * i) for i in range(len(pre))]
    ts += [d + pd.Timedelta(minutes=tf * i) for i in range(len(rows))]
    df = pd.DataFrame(pre + [tuple(map(float, r)) for r in rows], columns=["open", "high", "low", "close"])
    df.insert(0, "timestamp", ts)
    return df


class Rec:
    def __init__(self, ret=None, exc=None):
        self.calls, self.ret, self.exc = [], ret, exc

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        if self.exc is not None:
            raise self.exc
        return self.ret(*a, **k) if callable(self.ret) else self.ret


def _hold(*a, **k):
    return VG.Gate("HOLD", status="SKIPPED_VISION_PENDING", signal_id="sid-1", note="vision / तुमच्या निर्णयाची वाट")


def _enter(*a, **k):
    return VG.Gate("ENTER", 1, 1, 1.0, "", "sid-1", "approved ×1.0")


BOTS = {
    "srv2": {"mod": srv2, "tf": 15, "setup_tf": "15M", "vision_bot": "srv2_momentum_reversal", "settings_key": "15m_dynamic_sr",
             "source": "srv2_momentum_reversal", "rsi": "check_instant_rsi_filter"},
    "classic": {"mod": csr, "tf": 5, "setup_tf": "5M", "vision_bot": "classic_sr", "settings_key": "classic_sr_reversal",
                "source": "classic_sr_reversal", "rsi": "check_classic_sr_rsi_filter"},
}


class Harness:
    """एका bot चा एक cycle — सगळ्या बाह्य dependencies fakes."""

    def __init__(self, monkeypatch, name, rows, ctx=UP, settings=None, forced=(), vg=_hold, legacy_touch=True, gate_exc=None):
        b = BOTS[name]
        self.b, self.m, self.name = b, b["mod"], name
        bars = _bars(rows, b["tf"])
        self.now = (bars["timestamp"].iloc[-1] + pd.Timedelta(minutes=b["tf"] + 1)).to_pydatetime()
        s = dict(cloud_db.STRATEGY_SETTINGS_DEFAULTS[b["settings_key"]])
        s.update(symbol_enabled=True, gate_area_pad_pct=1.0, trading_mode="PAPER", naked_enabled=False)
        s.update(settings or {})
        self.settings = s
        mp, m = monkeypatch, self.m
        mp.setattr(LGB, "entry_mode", LGB._entry_mode_orig)          # खरा default (PAPER ⇒ confirmation; LIVE ⇒ touch)
        mp.setattr(LGB, "_TOUCH_SEEN", set())
        mp.setattr(LR, "daily_trend", lambda *a, **k: ctx)
        orig_cycle_gate = LGB.cycle_gate

        def _cycle_gate(bot, symbol, tok, st, areas, now, **k):
            if gate_exc is not None:
                raise gate_exc
            return orig_cycle_gate(bot, symbol, tok, st, areas, now, fetch_bars=lambda *_: bars.copy())
        self.cycle_gate = Rec(_cycle_gate)
        mp.setattr(LGB, "cycle_gate", self.cycle_gate)
        self.entry_gate = Rec(vg)
        mp.setattr(VG, "entry_gate", self.entry_gate)
        mp.setattr(VG, "forced_levels", lambda *a, **k: list(forced))
        mp.setattr(m.cloud_db, "get_strategy_settings", lambda *a, **k: dict(s))
        mp.setattr(m.cloud_db, "get_zone_hits_today", lambda *a, **k: (0, None, None))
        self.logs = []
        mp.setattr(m.cloud_db, "save_signal_log", lambda e: self.logs.append(dict(e)) or True)
        mp.setattr(m, "get_ist_now", lambda: self.now)
        mp.setattr(m, "get_last_sl_tsl_exit_time", lambda *a, **k: None)
        mp.setattr(m, "has_open_trade_from_source", lambda *a, **k: False)
        self.rsi = Rec(lambda *a, **k: (True, 30.0))
        mp.setattr(m, b["rsi"], self.rsi)
        mp.setattr(m, "fetch_option_expiries", lambda *a, **k: [])
        mp.setattr(m, "fetch_upstox_option_chain", lambda *a, **k: ([{"underlying_spot_price": 1008.0}], "SUCCESS"))
        mp.setattr(m, "select_credit_spread_itm", lambda *a, **k: {"strategy": "BULL_PUT_SPREAD", "legs": []})
        mp.setattr(m, "select_naked_option_itm", lambda *a, **k: None)
        self.trade = Rec(({"trade_id": "T1"}, "OPENED"))
        mp.setattr(m, "open_multi_leg_trade", self.trade)
        mp.setattr(m, "send_telegram_message", lambda *a, **k: True)
        if name == "srv2":
            self.pcr = Rec((True, 1.0, "PCR ok"))
            mp.setattr(m, "check_pcr_gate", self.pcr)
            mp.setattr(m.cloud_db, "get_srv2_state", lambda *a, **k: {"last_tested_level": None, "last_sl_hit_time": None})
            mp.setattr(m.cloud_db, "get_market_zones", lambda *a, **k: pd.DataFrame([{"zone_type": "DYNAMIC_SR_SUPPORT_15M"}]))
            mp.setattr(m.cloud_db, "save_srv2_state", lambda *a, **k: True)
            mp.setattr(m, "_yield_open_5m_positions", lambda *a, **k: (True, []))
            cands = [(LEVEL, "15M", bars, 1008.0, [980.0]),                    # hysteresis ⇒ BEARISH (gate ची बाजू वेगळी हे दाखवायला)
                     (TARGET_LEVEL, "15M", bars, 1008.0, [1008.0])]
            mp.setattr(m, "_collect_touch_candidates", lambda *a, **k: cands)
            mp.setattr(m, "_fetch_todays_1m_candles", lambda *a, **k: list(TOUCH_1M if legacy_touch else AWAY_1M))
        else:
            self.pcr = Rec()
            zones = pd.DataFrame([
                {"symbol": "NIFTY", "zone_type": "DYNAMIC_SR_SUPPORT_5M", "zone_low": LEVEL, "zone_high": LEVEL, "strength": 3.0,
                 "formed_date": "2026-09-01", "status": "ACTIVE"},
                {"symbol": "NIFTY", "zone_type": "DYNAMIC_SR_RESISTANCE_15M", "zone_low": TARGET_LEVEL, "zone_high": TARGET_LEVEL,
                 "strength": 2.0, "formed_date": "2026-09-01", "status": "ACTIVE"}])
            mp.setattr(m.cloud_db, "get_market_zones", lambda *a, **k: zones)
            cdf = bars.copy()
            if not legacy_touch:                                          # शेवटचे 2 5M candles level पासून दूर (जुना touch नाही)
                cdf.loc[cdf.index[-2:], ["open", "high", "low", "close"]] = [1008.0, 1009.0, 1007.0, 1008.0]
            mp.setattr(m, "fetch_candles", lambda *a, **k: cdf.copy())

    def run(self, symbol="NIFTY"):
        return self.m.process_symbol("fake_token", symbol)

    def level_logs(self):
        return [e for e in self.logs if abs(float(e["level_price"]) - LEVEL) < 1e-6]

    def statuses(self):
        return [e["trade_status"] for e in self.level_logs()]


def _would_have():
    from paper import journal as PJ
    return PJ.would_have_rows()


@pytest.mark.parametrize("name", list(BOTS))
def test_touch_without_reaction_no_entry_skipped_gate_and_legacy_would_have(monkeypatch, name):
    h = Harness(monkeypatch, name, ARMED_ROWS)
    h.run()
    assert h.cycle_gate.calls and h.cycle_gate.calls[0][0][0] == ("srv2" if name == "srv2" else "classic_sr")
    assert "SKIPPED_GATE_WAITING_COMMITMENT" in h.statuses()
    assert not h.entry_gate.calls and not h.trade.calls
    wh = [x for x in _would_have() if x["bot"] == f"{h.b['source']}_touch_legacy"]
    assert len(wh) == 1 and wh[0]["orig_lots"] == 0 and wh[0]["status"] == "TOUCH_LEGACY"
    assert wh[0]["setup_tf"] == h.b["setup_tf"] and abs(wh[0]["level"] - LEVEL) < 1e-6


@pytest.mark.parametrize("name", list(BOTS))
def test_confirmed_goes_to_vision_gate_with_gate_tags_and_side_no_trade_without_enter(monkeypatch, name):
    h = Harness(monkeypatch, name, CONFIRMED_ROWS)
    h.run()
    assert len(h.entry_gate.calls) == 1
    a, k = h.entry_gate.calls[0]
    assert a[0] == h.b["vision_bot"] and a[1] == "NIFTY" and a[2] == "PAPER"
    assert a[3] == "BULLISH" and a[5] == "SUPPORT" and a[6] == h.b["setup_tf"]   # srv2: hysteresis BEARISH होता — दिशा gate ची
    assert k["forced"] is False
    g = k["tags"]["gate"]
    assert g["side"] == "BULLISH" and g["mode"] == "confirmation" and g["rr"] is None and g["tf"] == f"{BOTS[name]['tf']}M"   # R:R gate default बंद
    assert g["trend"] == "Daily UP" and g["entry"] == 1008.0 and g["sl"] < 990
    assert k["tags"]["hit"] == "CONFIRMATION" and not k["tags"].get("breakout_entry")
    assert not h.trade.calls                                               # HOLD ⇒ entry नाही
    assert "SKIPPED_VISION_PENDING" in h.statuses()
    assert not h.rsi.calls and not h.pcr.calls                             # confirmation ⇒ RSI / PCR gates default बंद


@pytest.mark.parametrize("name", list(BOTS))
def test_confirmed_with_enter_from_vision_places_paper_trade(monkeypatch, name):
    h = Harness(monkeypatch, name, CONFIRMED_ROWS, vg=_enter)
    h.run()
    assert len(h.trade.calls) == 1
    k = h.trade.calls[0][1]
    assert k["direction"] == "BULLISH" and k["trading_mode"] == "PAPER" and k["source"] == h.b["source"] and k["lots"] == 1


@pytest.mark.parametrize("name", list(BOTS))
def test_conf_rsi_gate_explicitly_enabled_is_used(monkeypatch, name):
    h = Harness(monkeypatch, name, CONFIRMED_ROWS, settings={"conf_rsi_gate_enabled": True})
    h.rsi.ret = lambda *a, **k: (False, 70.0)
    h.run()
    assert h.rsi.calls and "SKIPPED_RSI_FILTER" in h.statuses() and not h.entry_gate.calls


@pytest.mark.parametrize("name", list(BOTS))
def test_against_trend_is_ignored(monkeypatch, name):
    h = Harness(monkeypatch, name, CONFIRMED_ROWS, ctx=DOWN)
    h.run()
    assert "SKIPPED_GATE_AGAINST_TREND" in h.statuses()
    assert not h.entry_gate.calls and not h.trade.calls


@pytest.mark.parametrize("name", list(BOTS))
def test_breakout_through_level_is_not_traded(monkeypatch, name):
    h = Harness(monkeypatch, name, DRIVE_ROWS)
    h.run()
    assert "SKIPPED_GATE_BROKEN" in h.statuses()
    assert not h.entry_gate.calls and not h.trade.calls


@pytest.mark.parametrize("name", list(BOTS))
def test_gate_exception_fails_closed_even_for_forced_level(monkeypatch, name):
    h = Harness(monkeypatch, name, CONFIRMED_ROWS, gate_exc=RuntimeError("boom"),
                forced=[(LEVEL, BOTS[name]["setup_tf"], "SUPPORT")], vg=_enter)
    h.run()
    assert "SKIPPED_GATE_ERROR" in h.statuses()
    assert not h.entry_gate.calls and not h.trade.calls


@pytest.mark.parametrize("name", list(BOTS))
def test_forced_level_uses_recorded_direction_and_needs_fresh_approval(monkeypatch, name):
    forced = [(LEVEL, BOTS[name]["setup_tf"], "SUPPORT")]
    h = Harness(monkeypatch, name, ARMED_ROWS, forced=forced, vg=_enter, legacy_touch=False)
    h.run()
    assert len(h.entry_gate.calls) == 1
    a, k = h.entry_gate.calls[0]
    assert k["forced"] is True and a[3] == "BULLISH"                       # gate ARMED (entry नाही) — ✅ approval हीच confirmation
    assert len(h.trade.calls) == 1 and h.trade.calls[0][1]["direction"] == "BULLISH"
    assert h.level_logs()[-1]["hit_type"] == "VISION_FORCED"


@pytest.mark.parametrize("name", list(BOTS))
def test_forced_level_stale_holds(monkeypatch, name):
    forced = [(LEVEL, BOTS[name]["setup_tf"], "SUPPORT")]
    h = Harness(monkeypatch, name, ARMED_ROWS, forced=forced, legacy_touch=False,
                vg=lambda *a, **k: VG.Gate("HOLD", status="SKIPPED_VISION_FORCED_STALE", note="stale"))
    h.run()
    assert h.entry_gate.calls and not h.trade.calls and "SKIPPED_VISION_FORCED_STALE" in h.statuses()


@pytest.mark.parametrize("name", list(BOTS))
def test_forced_level_unknown_role_and_not_confirmed_no_entry(monkeypatch, name):
    h = Harness(monkeypatch, name, ARMED_ROWS, forced=[(LEVEL, BOTS[name]["setup_tf"], None)], vg=_enter, legacy_touch=False)
    h.run()
    assert not h.entry_gate.calls and not h.trade.calls
    assert "SKIPPED_GATE_WAITING_COMMITMENT" in h.statuses()


@pytest.mark.parametrize("name", list(BOTS))
def test_live_mode_unchanged_gate_never_called(monkeypatch, name):
    h = Harness(monkeypatch, name, ARMED_ROWS, settings={"trading_mode": "LIVE"}, vg=_enter)
    h.run()
    assert not h.cycle_gate.calls                                          # LIVE ⇒ touch (जुनं वर्तन), gate नाही
    assert len(h.trade.calls) == 1
    k = h.trade.calls[0][1]
    assert k["trading_mode"] == "LIVE" and k["lot_size"] == 65
    assert not [x for x in _would_have() if str(x["bot"]).endswith("_touch_legacy")]
    if name == "classic":
        assert not h.entry_gate.calls                                      # Classic: LIVE ला vision मार्ग नाही
    else:
        assert h.entry_gate.calls[0][0][2] == "LIVE" and "gate" not in h.entry_gate.calls[0][1]["tags"]


@pytest.mark.parametrize("name", list(BOTS))
def test_paper_explicit_touch_mode_keeps_legacy_path(monkeypatch, name):
    h = Harness(monkeypatch, name, ARMED_ROWS, settings={"entry_mode": "touch"}, vg=_enter)
    h.run()
    assert not h.cycle_gate.calls and len(h.entry_gate.calls) == 1 and len(h.trade.calls) == 1


def test_classic_sr_registered_as_vision_bot():
    assert VC.BOTS["classic_sr"] == ("NIFTY Classic SR", ("NIFTY",), "notify")
    assert VC.BOT_STRATEGY_KEY["classic_sr"] == "classic_sr_reversal"
    from paper import watch as PW
    assert PW.BOT_OF_SOURCE["classic_sr_reversal"] == "classic_sr"
    assert VC.load("classic_sr")["vision_mode"] == "notify"


def test_forced_direction_helper():
    f = [(995.0, "5M", "SUPPORT"), (1095.0, "5M", "RESISTANCE"), (900.0, "5M", None)]
    assert VG.forced_direction(f, 995.2, "5M") == "BULLISH"
    assert VG.forced_direction(f, 1095.0, "5M") == "BEARISH"
    assert VG.forced_direction(f, 900.0, "5M") is None
    assert VG.forced_direction(f, 995.0, "15M") is None
    assert VG.forced_direction(None, 995.0, "5M") is None
