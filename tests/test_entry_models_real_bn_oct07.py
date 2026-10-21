"""Abhi's BANKNIFTY 07–21 Oct review (deployed da7cbbc) — the two real cases, read live-equivalently on the private trade-data export
(skips cleanly without it; nothing from it is stored in this repo):

  • 07 Oct 09:15 E2 (bear call, the 1H supply 54,886–55,193): the commitment candle closed BELOW the area — beyond it, not inside it
    — so it must not fire (RC3);
  • 07 Oct 10:00 E1 on that area: its invalidation was the cluster's far edge 55,201 (the union of overlapping areas) — the invalidation
    must come from the area itself (RC1); with the refined 15M base (RC2, research default) it waits for price to reach the base;
  • every entry that day: the trigger close inside its own area and no invalidation from a cluster's union.
The day's inputs are cut exactly as engine3_live cuts them at that session's close (15M / Daily / 5M / FUT windows)."""
import glob
import os

import numpy as np
import pandas as pd
import pytest

TD = "/home/user/trade-data"
BN = f"{TD}/banknifty"
DAY = "2026-10-07"
BAND = (54886.2, 55192.65)


def _naive(s):
    t = pd.to_datetime(s)
    if getattr(t.dt, "tz", None) is not None:
        t = t.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    return t.astype("datetime64[ns]")


def _rd(p, cols):
    d = pd.read_parquet(p) if p.endswith(".parquet") else pd.read_csv(p)
    d["timestamp"] = _naive(d["timestamp"])
    return d[cols]


def _merge(frames):
    fr = [f.assign(_k=k) for k, f in enumerate(frames) if f is not None and len(f)]
    d = pd.concat(fr, ignore_index=True).sort_values(["timestamp", "_k"]).drop_duplicates("timestamp", keep="last")
    return d.drop(columns="_k").reset_index(drop=True)


def _inputs():
    sp = sorted(glob.glob(f"{BN}/vps_spot_history/*/"))
    vh = sorted(glob.glob(f"{BN}/vps_history/*/"))
    fut_pq = f"{TD}/futures_volume/oe_futures_5min_BANKNIFTY.parquet"
    if not sp or not vh or not os.path.exists(fut_pq) or not os.path.exists(f"{BN}/BANKNIFTY_15M.csv.gz"):
        pytest.skip("private trade-data (BANKNIFTY export) not present")
    sp, vh = sp[-1], vh[-1]
    c5 = ["timestamp", "open", "high", "low", "close"]
    m15 = _merge([_rd(f"{BN}/BANKNIFTY_15M.csv.gz", c5), _rd(f"{sp}BANKNIFTY_15m.csv.gz", c5)])
    m5 = _merge([_rd(f"{vh}BANKNIFTY_5M.csv.gz", c5), _rd(f"{sp}BANKNIFTY_5m.csv.gz", c5)])
    m1 = _merge([_rd(f"{vh}BANKNIFTY_1M.csv.gz", c5), _rd(f"{sp}BANKNIFTY_1m.csv.gz", c5)])
    cf = c5 + ["volume", "contract"]
    fut = _merge([_rd(p, cf) for p in (fut_pq, f"{TD}/live_export/2026-10-13-fut45/oe_futures_5min_BANKNIFTY.parquet",
                                         f"{vh}BANKNIFTY_FUT_5M.csv.gz") if os.path.exists(p)])
    from legs2 import volume as LVOL
    fut["expiry"] = LVOL.expiry_of(fut)
    from decision3 import history as HI
    dh = _merge([HI._ohlc_daily(HI._read(p)) for p in sorted(glob.glob(f"{BN}/BANKNIFTY_daily_*.csv")) +
                 sorted(glob.glob(f"{BN}/BANKNIFTY_D.csv*"))])
    return m15, m5, m1, fut, dh


@pytest.fixture(scope="module")
def day_rows():
    import engine3_live as L
    import instruments as INS
    from bots_common import level_reaction as LR
    from decision3 import engine as E3, history as HI
    m15_all, m5_all, m1_all, fut_all, daily_all = _inputs()
    INS.set_current("BANKNIFTY")
    S = L.DEFAULTS
    D = pd.Timestamp(DAY)
    now = D + pd.Timedelta(hours=15, minutes=31)

    def cut(df, days, minutes):
        x = df[(df["timestamp"] >= D - pd.Timedelta(days=days)) & (df["timestamp"] < D + pd.Timedelta(days=1))]
        return L.closed_session_bars(x, minutes, now)
    m15 = cut(m15_all, S["engine3_m15_days"], 15)
    dd = daily_all[(daily_all["timestamp"] <= D) & (daily_all["timestamp"] >= D - pd.Timedelta(days=S["engine3_daily_days"]))]
    daily = LR.prepare_daily(L._naive(dd)[["timestamp", "open", "high", "low", "close"]], now.normalize())
    ltf = cut(m5_all, S["engine3_ltf_days"], 5)
    fut = cut(fut_all, S["engine3_fut_days"], 5)
    m1 = m1_all[(m1_all["timestamp"] >= m15["timestamp"].iloc[0]) & (m1_all["timestamp"] + pd.Timedelta(minutes=1) <= m15["bar_end"].iloc[-1])]
    V = E3.V22(m15.drop(columns=["volume"], errors="ignore"), m1.reset_index(drop=True), daily, sealed=HI.sealed_fn("BANKNIFTY"),
               ltf=ltf, futures=fut)
    ts = pd.to_datetime(V.m15["timestamp"]).reset_index(drop=True)
    bars = [i for i in range(len(ts)) if ts[i].normalize() == D]
    return V, ts, {str(ts[t])[11:16]: V.decide(t) for t in bars}


def _on_band(e):
    a = e.get("area") or {}
    return a.get("lo") is not None and abs(float(a["lo"]) - BAND[0]) < 0.01 and abs(float(a["hi"]) - BAND[1]) < 0.01


def test_oct07_0915_e2_commitment_closed_below_the_area_does_not_fire(day_rows):
    V, ts, rows = day_rows
    r = rows["09:15"]
    assert not [e for e in r["entries"] if e["model"] == "E2" and _on_band(e)]
    c = float(V.levels.A["close"][int(np.flatnonzero(ts.astype(str).str.startswith(f"{DAY} 09:15"))[0])])
    assert c < BAND[0]                                                     # the bar closed below the area (beyond it, trade side)
    arm = [a for a in r["armed"] if a.get("lo") is not None and abs(float(a["lo"]) - BAND[0]) < 0.01]
    assert arm and ("price has left the area" in str(arm[0]["models"]["E2"].get("waiting")) or arm[0].get("disarmed"))


def test_oct07_1000_e1_never_uses_the_cluster_union(day_rows):
    _V, _ts, rows = day_rows
    r = rows["10:00"]
    for e in r["entries"]:
        assert "cluster" not in str(e["invalidation_rule"])
    e1 = [e for e in r["entries"] if e["model"] == "E1" and _on_band(e)]
    assert not e1 or e1[0]["invalidation"] != 55201.0                     # never the union's far edge
    arm = [a for a in r["armed"] if a.get("lo") is not None and abs(float(a["lo"]) - BAND[0]) < 0.01]
    if not e1 and arm:                                                     # RC2 default: waits for the refined base
        assert "refined" in str(arm[0]["models"]["E1"].get("waiting"))


def test_oct07_every_entry_triggers_inside_its_own_area(day_rows):
    V, ts, rows = day_rows
    A = V.levels.A
    for hm, r in rows.items():
        for e in r["entries"]:
            assert "cluster" not in str(e["invalidation_rule"]) and "lo" not in (e.get("cluster") or {})
            if e["object"] == "area":
                c = float(A["close"][e["trigger_bar"]])
                assert float(e["area"]["lo"]) <= c <= float(e["area"]["hi"]), (hm, e["model"], c, e["area"])
                inv = float(e["invalidation"])
                assert (c - inv) * e["direction"] >= 0, (hm, e["model"], c, inv)   # not beyond its invalidation
