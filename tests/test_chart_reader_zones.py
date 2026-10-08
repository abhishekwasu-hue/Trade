"""chart_reader/zones.py — selling / buying zones (TRADE_KB_FULL_IMPLEMENTATION_PROMPT §2): जन्मावरून भूमिका, lifecycle (flip), reaction,
labels, आणि window-invariance (मोठ्या lookback वर गणना, मग crop)."""
import numpy as np
import pandas as pd

from chart_reader import zones as ZN

MR = 1.0


def frame(closes, start="2026-03-02 09:15"):
    c = np.asarray(closes, float)
    o = np.concatenate([[c[0]], c[:-1]])
    ts = pd.date_range(start, periods=len(c), freq="15min")
    return pd.DataFrame({"timestamp": ts, "open": o, "high": np.maximum(o, c) + 0.2, "low": np.minimum(o, c) - 0.2, "close": c})


def eqh(level, bar):
    return {"id": f"EQH-{bar}", "tool": "e", "kind": "solid", "low": level - 0.1, "high": level + 0.1, "pool": "equal_highs",
            "level": level, "bar": bar, "state": "ACTIVE", "role": "SUPPORT"}


def test_role_from_birth_not_price():
    z = {"id": "PDH", "tool": "k", "kind": "solid", "low": 99.0, "high": 99.5}
    assert ZN.birth_role(z, price=105.0) == "RESISTANCE"                                  # किंमत वर असली तरी PDH = selling जन्म
    assert ZN.birth_role({**z, "id": "PDL"}, price=90.0) == "SUPPORT"
    assert ZN.birth_role(eqh(100, 3), price=120.0) == "RESISTANCE"
    assert ZN.birth_role({"tool": "c", "role": "RESISTANCE", "low": 1, "high": 2}, price=0.5) == "RESISTANCE"   # supply base


def test_broken_supply_retested_from_above_flips_to_buying_zone():
    closes = [95, 97, 99.5, 98, 96, 97, 99.5, 98, 97, 101, 103, 104, 102, 100.3, 101.5, 103, 104]
    zs = ZN.annotate([eqh(100.0, 6)], frame(closes), {}, MR)
    z = zs[0]
    assert z["birth_role"] == "RESISTANCE" and z["state"] == "FLIPPED" and z["role"] == "SUPPORT" and z["side"] == "buy"
    assert z["type"].startswith("flip") and z["zid"] == "B1" and z["label"].startswith("B1 · flip")


def test_untouched_supply_is_fresh_active_selling_zone():
    closes = [100, 103, 106, 104, 100, 97, 95, 96, 95.5]
    zs = ZN.annotate([eqh(106.0, 2)], frame(closes), {}, MR)
    z = zs[0]
    assert (z["side"], z["state"], z["fresh"], z["tests"]) == ("sell", "ACTIVE", "fresh", 0)
    assert z["label"] == "S1 · liquidity · 15M · ACTIVE · 0 touches"


def test_reaction_strength_in_mr_after_touch():
    closes = [100, 103, 105.9, 103, 100, 97, 98, 99, 98, 96]
    z = {"id": "S", "tool": "c", "kind": "solid", "low": 105.5, "high": 106.5, "role": "RESISTANCE", "bar": 0}
    out = ZN.annotate([z], frame(closes), {}, MR)[0]
    assert out["reaction_mr"] >= 8.0 and out["tests"] == 1 and out["fresh"] == "tested"


def test_rulers_are_not_zones_and_numbering_by_distance():
    price_path = [100, 101, 100.5, 100.8]
    cands = [{"id": "FIB0.618", "tool": "h", "kind": "ruler", "low": 99, "high": 99.5},
             {"id": "RN110", "tool": "j", "kind": "solid", "low": 109.8, "high": 110.2},
             {"id": "RN105", "tool": "j", "kind": "solid", "low": 104.8, "high": 105.2},
             {"id": "RN95", "tool": "j", "kind": "solid", "low": 94.8, "high": 95.2}]
    zs = {z["id"]: z for z in ZN.annotate(cands, frame(price_path), {}, MR)}
    assert "FIB0.618" not in zs
    assert zs["RN105"]["zid"] == "S1" and zs["RN110"]["zid"] == "S2" and zs["RN95"]["zid"] == "B1"


def test_zone_attributes_do_not_depend_on_chart_window():
    rng = np.random.default_rng(7)
    closes = 100 + np.cumsum(rng.normal(0, 0.8, 300))
    df = frame(closes)
    birth = 220
    lvl = float(df["high"].iloc[birth])
    z = {"id": "S", "tool": "c", "kind": "solid", "low": lvl - 0.5, "high": lvl, "role": "RESISTANCE", "bar": birth}
    full = ZN.annotate([z], df, {}, MR)[0]
    crop = ZN.annotate([{**z, "bar": birth - 100}], df.iloc[100:].reset_index(drop=True), {}, MR)[0]
    for k in ("state", "role", "tests", "reaction_mr", "fresh", "side"):
        assert full[k] == crop[k], k


def test_nearest_trade_side_zones_skip_dead():
    zs = [{"side": "sell", "state": "ACTIVE", "low": 105, "high": 106}, {"side": "sell", "state": "BROKEN", "low": 101, "high": 102},
          {"side": "buy", "state": "ACTIVE", "low": 95, "high": 96}]
    near = ZN.nearest(zs, -1, 100.0)
    assert len(near) == 1 and near[0]["low"] == 105
