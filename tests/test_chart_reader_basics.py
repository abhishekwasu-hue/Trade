"""Chart Reader — candle psychology, HTF trend, risk (invalidation / targets / R:R) आणि पक्के नियम."""
import pandas as pd

from chart_reader import candles as CC
from chart_reader import risk as RK
from chart_reader import rules as RU
from chart_reader import settings as CS
from chart_reader import trend as TR

S = dict(CS.DEFAULTS)


# ------------------------------------------------------------------------------------------------ candle psychology
def test_candle_read_control_and_line():
    r = CC.read(100, 101, 90, 100.8, mr=8.0)                                               # लांब lower wick, close top ⇒ buyers
    assert r["control"] == "buyers" and r["lower_wick"] > 0.7 and r["size_mr"] == 1.38 and "buyers" in r["line"]
    r = CC.read(110, 110.5, 99, 99.3, mr=8.0)                                              # मोठी bearish body, close तळाशी
    assert r["control"] == "sellers" and r["body"] > 0.9 and "sellers" in r["line"]
    assert CC.read(100, 104, 96, 100.1, mr=8.0)["control"] == "indecision"                 # CL ≈ 0.5
    assert CC.read(100, 100, 100, 100, mr=8.0)["control"] == "indecision"                  # range 0 guard


# ------------------------------------------------------------------------------------------------ trend
def _bars(prices, tf="60min"):
    ts = pd.date_range("2021-01-04 09:15", periods=len(prices), freq=tf)
    o = [prices[0]] + prices[:-1]
    return pd.DataFrame({"timestamp": ts, "open": o, "high": [max(a, b) + 1 for a, b in zip(o, prices)],
                         "low": [min(a, b) - 1 for a, b in zip(o, prices)], "close": prices})


def _zig(start, legs, step=4.0):
    out, p = [], start
    for target in legs:
        while abs(target - p) > step / 2:
            p += step if target > p else -step
            out.append(p)
    return out


def test_htf_trend_up_down():
    up = _bars(_zig(100, [140, 120, 170, 150, 200, 180, 230]))
    r = TR.read({"1h": up}, ["1h"])
    assert r["htf"] == "up" and r["trend_strength"] in ("strong", "weakening")
    dn = _bars(_zig(300, [260, 280, 230, 250, 200, 220, 170]))
    assert TR.read({"1h": dn}, ["1h"])["htf"] == "down"


# ------------------------------------------------------------------------------------------------ risk
def test_risk_bull_put_invalidation_is_farther_of_area_and_candle():
    area = {"id": "H1", "low": 99.0, "high": 101.0}
    rk = RK.compute(1, entry=103.0, area=area, rev_comp=(100, 104, 97.5, 103), targets=[(115.0, "R1"), (125.0, "R2")], mr=2.0, s=S)
    assert rk["invalidation"] == 97.5 - S["inv_buffer_mr"] * 2.0                         # candle low (97.5) area low (99) पेक्षा खाली
    assert rk["targets"][0] == {"price": 115.0, "id": "R1"} and abs(rk["rr"] - 12.0 / (103 - rk["invalidation"])) < 1e-9


def test_risk_bear_call_mirror_and_no_target():
    area = {"id": "TL3", "low": 22700.0, "high": 22730.0}
    rk = RK.compute(-1, entry=22690.0, area=area, rev_comp=(22700, 22745, 22660, 22690), targets=[], mr=20.0, s=S)
    assert rk["invalidation"] == 22745 + S["inv_buffer_mr"] * 20.0 and rk["rr"] is None


# ------------------------------------------------------------------------------------------------ पक्के नियम
def _ctx(**kw):
    base = {"side": 1, "bar_closed": True, "bar_end": pd.Timestamp("2021-03-01 11:00"), "approach_ok": True, "area_role": "SUPPORT",
            "invalidation": 97.0, "entry": 103.0, "rr": 4.0, "gap_chase": False, "risk_ok": True}
    base.update(kw)
    return base


def test_hard_rules_each_one_blocks():
    assert RU.check(_ctx(), S) == []
    assert "बंद candle नाही" in RU.check(_ctx(bar_closed=False), S)[0]
    assert "chase" in RU.check(_ctx(approach_ok=False), S)[0]
    assert "chase" in RU.check(_ctx(side=-1, area_role="SUPPORT", invalidation=110.0), S)[0]      # support वर bear call
    assert "chase" in RU.check(_ctx(gap_chase=True), S)[0]
    assert "09:15" in RU.check(_ctx(bar_end=pd.Timestamp("2021-03-01 09:30")), S)[0]
    assert "invalidation" in RU.check(_ctx(invalidation=None), S)[0]
    assert "invalidation" in RU.check(_ctx(invalidation=104.0), S)[0]                              # चुकीच्या बाजूला
    assert "R:R" in RU.check(_ctx(rr=2.9), S)[0] and "R:R" in RU.check(_ctx(rr=None), S)[0]
    assert "risk" in RU.check(_ctx(risk_ok=False), S)[0]


def test_risk_invalidation_beyond_correction_extreme_too():
    area = {"id": "TL", "low": 8540.6, "high": 8545.9}
    rk = RK.compute(-1, entry=8545.8, area=area, rev_comp=(8540, 8546.0, 8539, 8545.8), targets=[(8291.7, "H1")], mr=10.0, s=S,
                    extreme=8574.0)
    assert rk["invalidation"] == 8574.0 + S["inv_buffer_mr"] * 10.0 and rk["rr"] < 10
