"""tests/test_pcs_signal.py — Pullback Credit Spread signal pipeline: पूर्ण bars, trend bias, level निवड, breakout वर entry नाही, reversal नसेल
तर entry नाही, blackout, checklist क्रम, आणि MCX code अबाधित. Network/DB नाही."""
import os
import re

import numpy as np
import pandas as pd

from opportunity_engine.structure import DN, RANGE, UP, UP_PB, UP_WEAK
from pullback_credit_spread import settings as S
from pullback_credit_spread import signal as SG

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = S.DEFAULTS


def cfg(**kw):
    return {**D, **kw}


def _bars(closes, start="2024-01-01 09:15", freq="60min"):
    ts = pd.date_range(start, periods=len(closes), freq=freq)
    c = np.asarray(closes, float)
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({"timestamp": ts, "open": o, "high": np.maximum(o, c) + 2, "low": np.minimum(o, c) - 2, "close": c})


def test_completed_drops_forming_bar():
    df = _bars([100, 101, 102])
    out = SG.completed(df, "1h", "2024-01-01 11:30")                   # 11:15 चा bar 12:15 ला संपतो ⇒ वगळला
    assert list(out["close"]) == [100, 101]


def test_bias_mapping():
    assert SG.bias_of(UP, D)[0] == "LONG" and SG.bias_of(UP_PB, D)[0] == "LONG" and SG.bias_of(DN, D)[0] == "SHORT"
    assert SG.bias_of(UP_WEAK, cfg(skip_on_weak=True))[0] is None and SG.bias_of(UP_WEAK, cfg(skip_on_weak=False))[0] == "LONG"
    assert SG.bias_of(RANGE, D)[0] is None


def test_pick_level_trend_direction_and_distance():
    lv = [{"price": 23900, "low": 23880, "high": 23920, "role": "SUPPORT"},
          {"price": 24300, "low": 24280, "high": 24320, "role": "RESISTANCE"},
          {"price": 23000, "low": 22980, "high": 23020, "role": "SUPPORT"}]                         # खूप दूर
    assert SG.pick_level(lv, "LONG", 24000, D)["price"] == 23900
    assert SG.pick_level(lv, "SHORT", 24000, D)["price"] == 24300
    assert SG.pick_level(lv, "LONG", 24000, cfg(require_role_reversal=True)) is None


def _frames_with_breakdown():
    up = list(np.linspace(23500, 24100, 80)) + [24050, 24000, 23950, 23900, 23860, 23850, 23840, 23830, 23820, 23810]   # support 23880–23920 खाली तुटला (3+ bars reclaim नाही)
    df = _bars(up)
    return {"1h": df, "1d": None, "15m": df}


LEVEL = [{"price": 23900, "low": 23880, "high": 23920, "role": "SUPPORT", "role_reversal": True}]


def test_breakout_never_enters(monkeypatch):
    monkeypatch.setattr(SG, "trend_state", lambda df, tf: UP)              # trend/pullback वेगळे करून फक्त guard तपासतो
    monkeypatch.setattr(SG, "pullback_quality", lambda df, bias, s: (True, "ok"))
    fr = _frames_with_breakdown()
    r = SG.evaluate_entry(fr, LEVEL, cfg(htf_veto_tf="none", skip_on_weak=False, skip_on_range=False), "2024-01-08 00:00", spot=23950.0,
                          full=True)
    guard = dict((n, (s, d)) for n, s, d in r["steps"])["6. Breakout guard"]
    assert guard[0] == SG.FAIL and not r["ok"]
    # break नसेल तर guard ✅ (बाकी पायऱ्या स्वतंत्र)
    ok_frames = {"1h": _bars(list(np.linspace(23500, 24100, 80)) + [24050, 24000, 23960, 23940])}
    r2 = SG.evaluate_entry(ok_frames, LEVEL, cfg(htf_veto_tf="none"), "2024-01-08 00:00", spot=23950.0, full=True)
    assert dict((n, s) for n, s, _ in r2["steps"])["6. Breakout guard"] == SG.OK


def test_no_reversal_no_entry_and_checklist_order():
    df = _bars(list(np.linspace(23500, 24300, 120)))                 # सरळ वर — level पर्यंत pullback/reversal नाही
    r = SG.evaluate_entry({"1h": df}, LEVEL, cfg(htf_veto_tf="none"), "2024-01-10 00:00", spot=24300.0, full=True)
    names = [n for n, _, _ in r["steps"]]
    assert names[0].startswith("1.") and names[1].startswith("2.") and "5. Logical reversal" in names
    assert not r["ok"] and dict((n, s) for n, s, _ in r["steps"])["5. Logical reversal"] == SG.FAIL


def test_blackout_blocks_and_skips_rest():
    df = _bars(list(np.linspace(23500, 24300, 120)))
    r = SG.evaluate_entry({"1h": df}, LEVEL, cfg(event_dates="2024-01-10"), "2024-01-10 11:00", spot=24300.0)
    assert r["steps"][0][1] == SG.FAIL and all(s == SG.SKIP for _, s, _ in r["steps"][1:]) and not r["ok"]


def test_mcx_code_untouched_by_pcs():
    """MCX वर्तन बदललं नाही: PCS package MCX modules import करत नाही आणि MCX modules PCS import करत नाहीत."""
    pcs = os.path.join(ROOT, "pullback_credit_spread")
    for f in os.listdir(pcs):
        if f.endswith(".py"):
            assert not re.search(r"^\s*(from|import)\s+mcx", open(os.path.join(pcs, f), encoding="utf-8").read(), re.M)
    for f in os.listdir(ROOT):
        if f.startswith("mcx") and f.endswith(".py"):
            assert "pullback_credit_spread" not in open(os.path.join(ROOT, f), encoding="utf-8").read()


def test_pick_level_inside_wide_zone_and_never_opposite_role():
    wide = [{"price": 24050, "low": 24000, "high": 24100, "role": "ZONE"}]
    assert SG.pick_level(wide, "LONG", 24050, D) is not None
    res = [{"price": 24020, "low": 24000, "high": 24040, "role": "RESISTANCE"}]
    assert SG.pick_level(res, "LONG", 24060, D) is None                  # resistance कधीच LONG साठी नाही


def test_approach_from_wrong_side_is_breakout_no_entry(monkeypatch):
    monkeypatch.setattr(SG, "trend_state", lambda df, tf: UP)
    monkeypatch.setattr(SG, "pullback_quality", lambda df, bias, s: (True, "ok"))
    from_below = _bars(list(np.linspace(23500, 23870, 80)) + [23880, 23900, 23930, 23950])    # खालून वर level मध्ये (breakout), वरून नाही
    r = SG.evaluate_entry({"1h": from_below}, LEVEL, cfg(htf_veto_tf="none"), "2024-01-08 00:00", spot=23950.0, full=True)
    g = dict((n, (s, d)) for n, s, d in r["steps"])["6. Breakout guard"]
    assert g[0] == SG.FAIL and "trend च्या बाजूने" in g[1]


def test_forming_bar_inside_evaluate_entry_is_ignored(monkeypatch):
    seen = {}
    real = SG.trend_state
    monkeypatch.setattr(SG, "trend_state", lambda df, tf: (seen.setdefault("n", len(df)), real(df, tf))[1])
    df = _bars(list(np.linspace(23500, 24300, 120)))
    SG.evaluate_entry({"1h": df}, LEVEL, cfg(htf_veto_tf="none"), df["timestamp"].iloc[-1] + pd.Timedelta(minutes=30), spot=24300.0)
    assert seen["n"] == len(df) - 1                                      # शेवटचा (अर्धवट) bar वगळला


def test_expiry_morning_blackout_through_evaluate_entry():
    df = _bars(list(np.linspace(23500, 24300, 120)))
    r = SG.evaluate_entry({"1h": df}, LEVEL, D, "2024-01-11 09:45", spot=24300.0, expiries=["2024-01-11", "2024-01-18"])
    assert r["steps"][0][1] == SG.FAIL and "expiry" in r["steps"][0][2]
