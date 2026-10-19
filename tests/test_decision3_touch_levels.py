"""v22 touch / levels lifecycle fixtures (docs/reports/v22_missed_levels_touch.md).

(5) 29 Sep 2026 shape (NIFTY 15M, Daily DOWN): rally from the day low into 1H supply, buying candles shrink, the 12:15 large red
    candle engulfs the last greens and closes back below the band. Read = touch + buyers exhausting (a2 counter side) + dominant
    bearish engulf (c0). Bug: decide() ranked a far untouched level's "wait / no touch" above the touched level's "no_trade (R:R)",
    so the bar logged "no touch". Fixed: the level price is at (③ ✔) carries the bar's verdict. Mirrored (bull put) as well.
    Abhi (rr-correction): no "skipped on R:R" outcome — by default the expected read is a valid bear-call read; the old
    `no_trade (R:R)` remains only under legacy `rr_step` = True.
(4) is in tests/test_decision3_level_death_side.py.
"""
import os
from pathlib import Path
from types import SimpleNamespace as NS

import numpy as np
import pandas as pd
import pytest

from decision3 import engine as E3
from decision3 import levels as LV
from decision3 import method as M
from decision3 import settings as S3
from tests.test_decision3 import P, m15_from, res_of

# 29 Sep 2026 NIFTY 15M (09:15 … 12:15), rounded — fixture data
SEP29 = [  # open, high, low, close
    (22732, 22753, 22624, 22625), (22624, 22638, 22570, 22613), (22614, 22619, 22591, 22604), (22604, 22609, 22572, 22579),
    (22578, 22605, 22573, 22600), (22599, 22615, 22581, 22613), (22612, 22629, 22592, 22617), (22616, 22701, 22591, 22684),
    (22684, 22697, 22663, 22697), (22696, 22734, 22694, 22720), (22720, 22729, 22707, 22728), (22728, 22753, 22726, 22742),
    (22742, 22744, 22673, 22677)]
T_1215, T_1100 = 12, 7
SUPPLY = {"id": 2, "role": LV.RES, "lo": 22725.45, "hi": 22809.9, "births": ["a:D-prior", "c"], "sweeps": 0, "fresh": False}
FAR = {"id": 3, "role": LV.RES, "lo": 22930.35, "hi": 23002.15, "births": ["a:D-prior", "c"], "sweeps": 0, "fresh": True}
X0 = 22700.0                                                              # mirror axis


def _A(rows, mirror=False):
    o, h, lo, c = (np.array([r[k] for r in rows], float) for k in range(4))
    if mirror:
        o, h, lo, c = 2 * X0 - o, 2 * X0 - lo, 2 * X0 - h, 2 * X0 - c
    return {"open": o, "high": h, "low": lo, "close": c}


def _lvl(lv, mirror=False):
    if not mirror:
        return dict(lv)
    return {**lv, "role": LV.SUP, "lo": round(2 * X0 - lv["hi"], 2), "hi": round(2 * X0 - lv["lo"], 2)}


@pytest.mark.parametrize("mirror", [False, True])
def test_sep29_read_is_touch_buyers_exhausting_dominant_engulf(mirror):
    A, s = _A(SEP29, mirror), S3.load()
    d = M.UP if mirror else M.DOWN
    lvl = _lvl(SUPPLY, mirror)
    assert M.at_level(A, T_1215, d, lvl, 1)[0]                                # 12:15 चा स्वतःचा high पट्ट्यात ⇒ स्पर्श (lo 22,725)
    ok3, why3 = M.at_level_or_confirm(A, T_1215, d, lvl, s)
    assert ok3, why3
    assert not M.at_level_or_confirm(A, T_1215, d, _lvl(FAR, mirror), s)[0]  # दूरचा level: स्पर्श नाही
    ok6, why6, cm = M.commitment(A, T_1215, d, lvl, s, None, win=T_1100)       # c0: study window 11:00 पासून
    assert ok6 and cm["form"] == "engulf" and cm["body_mult"] > 1.0, why6
    assert cm["vol_na"] and cm["grade"] == "B"                                # volume नाही (NA) ⇒ कमाल B
    zs = M.zone_study(A, T_1100, T_1215, d, s)
    assert zs["counter_weakening"] is True and not zs["absorption"]           # a2: buying (mirror: selling) candles दमल्या


class _Stub(E3.V22):
    """decide() फक्त: ① DOWN / UP, ② दोन active levels (जवळचा स्पर्शलेला + दूरचा), प्रत्येकाचा ③ / ⑥ खरा method. ⑦ R:R (day low /
    high पर्यंत, engine सारखा: entry close, SL पट्ट्याची दूरची कडा) फक्त legacy `rr_step` = True — engine सारखंच (default ⑦ नाही)."""

    def __init__(self, A, levels, trend, rr_step=False):
        self.s, self.A, self.act, self.trend, self.sealed = S3.load({"rr_step": rr_step}), A, levels, trend, None
        n = len(A["close"])
        ts = pd.date_range("2030-01-07 09:15", periods=n, freq="15min")
        self.m15 = pd.DataFrame({"timestamp": ts})
        self.bar_end = pd.Series(ts + pd.Timedelta(minutes=15))

    def step1(self, t):
        st = NS(trend=self.trend, phase="impulse", wave=None, corr_label=None, mature=False, targets=(), protected=None, band=None)
        return True, "Daily", st, {"trend": self.trend, "resolution": "daily impulse", "cap": "B", "notes": [], "weekly": None,
                                   "band": None}

    def step2(self, t, trend, band=None):
        return True, "levels", list(self.act)

    def _level_eval(self, t, trend, lvl, cap=None, notes=None, *, step_down=False):
        A, d = self.A, M._dir(trend, lvl["role"])
        ok3, why3 = M.at_level_or_confirm(A, t, d, lvl, self.s)
        chk = {"③": [ok3, why3]}
        if not ok3:
            return E3.M_WAIT, chk, {}
        ok6, why6, cm = M.commitment(A, t, d, lvl, self.s, None)
        chk["⑥"] = [ok6, why6]
        if not ok6:
            return E3.M_WAIT, chk, {"why": f"commitment ची वाट ({why6})"}
        if not self.rr_step:                                                  # default (Abhi): R:R entry ची अट नाही
            return E3.M_SETUP, chk, {"commit": cm, "conviction": "B"}
        entry = float(A["close"][t])
        sl = lvl["hi"] if d == M.DOWN else lvl["lo"]
        tgt = float(min(A["low"][:t + 1])) if d == M.DOWN else float(max(A["high"][:t + 1]))
        rr = (entry - tgt) * -d / ((entry - sl) * -d)
        chk["⑦"] = [rr >= float(self.s["min_rr"]), f"R:R {rr:.2f}"]
        rk = {"entry": entry, "sl": sl, "target": tgt, "rr": round(rr, 2)}
        if rr < float(self.s["min_rr"]):
            return E3.M_NO, chk, {"risk": rk, "commit": cm, "why": "R:R < 3 ⇒ trade नाही"}
        return E3.M_SETUP, chk, {"risk": rk, "commit": cm, "conviction": "B"}


@pytest.mark.parametrize("mirror", [False, True])
def test_sep29_is_valid_bear_call_read_no_rr_skip(mirror):
    """Abhi (rr-correction): 29 Sep 12:15 = valid bear-call read (mirror: bull put) — "skipped on R:R" निकाल नाही (default ⑦ नाही)."""
    A = _A(SEP29, mirror)
    lv = [_lvl(SUPPLY, mirror), _lvl(FAR, mirror)]
    for order in (lv, lv[::-1]):                                              # active क्रम कोणताही ⇒ तोच निकाल
        r = _Stub(A, order, "UP" if mirror else "DOWN").decide(T_1215)
        assert r["level"]["id"] == SUPPLY["id"]
        assert r["decision"] == E3.SETUP and r["trade_side"] == (["bull_put"] if mirror else ["bear_call"])
        assert r["checklist"]["③"][0] is True and r["checklist"]["⑥"][0] is True and "⑦" not in r["checklist"]
        assert "R:R" not in str(r["why"] or "") and r["risk"] is None
        assert {e["id"]: e["decision"] for e in r["level_evals"]} == {SUPPLY["id"]: E3.SETUP, FAR["id"]: E3.WAIT}


@pytest.mark.parametrize("mirror", [False, True])
def test_sep29_bar_logs_touched_level_reason_not_no_touch(mirror):
    """Legacy `rr_step` = True (setting ON) ⇒ जुना ⑦ अजून चालतो, आणि निकाल स्पर्शलेल्या level चा (no touch नाही)."""
    A = _A(SEP29, mirror)
    lv = [_lvl(SUPPLY, mirror), _lvl(FAR, mirror)]
    for order in (lv, lv[::-1]):                                              # active क्रम कोणताही ⇒ तोच निकाल
        r = _Stub(A, order, "UP" if mirror else "DOWN", rr_step=True).decide(T_1215)
        assert r["level"]["id"] == SUPPLY["id"]
        assert r["checklist"]["③"][0] is True and r["checklist"]["⑥"][0] is True and r["checklist"]["⑦"][0] is False
        assert r["decision"] == E3.NO_TRADE and "R:R" in r["why"]             # legacy ⑦ फक्त — "no touch" नाही
        assert {e["id"]: e["decision"] for e in r["level_evals"]} == {SUPPLY["id"]: E3.NO_TRADE, FAR["id"]: E3.WAIT}
    # कोणत्याच level ला स्पर्श नाही ⇒ जुना क्रम (wait)
    r = _Stub(A, lv, "UP" if mirror else "DOWN", rr_step=True).decide(T_1100 - 1)
    assert r["decision"] == E3.WAIT and r["checklist"]["③"][0] is False


# ------------------------------------------------------------------------------------------------ real data (private trade-data)
RECENT = Path(os.environ.get("TRADE_DATA_DIR", "/home/user/trade-data")) / "upstox" / "NIFTY_1m_2026-07-01_2026-10-08.csv.gz"


@pytest.mark.skipif(not RECENT.exists(), reason="Jul–Oct 2026 1m data (private trade-data) नाही — CI मध्ये skip")
def test_real_sep29_1215_touch_and_dominant_engulf():
    """Real 15M bars (1m ⇒ 15M) of 29 Sep 2026 against the engine's 1H supply 22,725.45–22,809.90 (that day's level list)."""
    raw = pd.read_csv(RECENT, parse_dates=["timestamp"])
    ts = pd.to_datetime(raw["timestamp"])
    raw["timestamp"] = ts.dt.tz_localize(None) if ts.dt.tz is not None else ts
    day = raw[(raw.timestamp >= "2026-09-29 09:15") & (raw.timestamp < "2026-09-29 12:30")].set_index("timestamp")
    m15 = day.resample("15min", label="left", closed="left").agg({"open": "first", "high": "max", "low": "min",
                                                                  "close": "last"}).dropna()
    assert str(m15.index[T_1215])[11:16] == "12:15"
    A = {k: m15[k].to_numpy(float) for k in ("open", "high", "low", "close")}
    s = S3.load()
    assert A["high"][T_1215] >= SUPPLY["lo"]                                  # 12:15 high पट्ट्यात
    assert M.at_level_or_confirm(A, T_1215, M.DOWN, SUPPLY, s)[0]
    ok6, _, cm = M.commitment(A, T_1215, M.DOWN, SUPPLY, s, None, win=T_1100)
    assert ok6 and cm["form"] == "engulf" and cm["body_mult"] > 1.0
    assert M.zone_study(A, T_1100, T_1215, M.DOWN, s)["counter_weakening"] is True
