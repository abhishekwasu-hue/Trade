"""Volume pane (Abhi: "the volume test is not visible on these charts") — प्रत्येक setup / proposal chart मध्ये volume pane किंवा स्पष्ट
"volume: NA"; mirror (up / down) समान; setup bar नंतरचा volume कधीच नाही. Synthetic data, network नाही."""
import numpy as np
import pandas as pd
import pytest

from decision3 import volume_pane as VP

SUP = (100.0, 102.0)


def zone_bars(mirror=False):
    """Demand area 100–102 (UP trend): वरून arrival, आत 4 candles (counter-side = selling), मग मोठी bullish commitment. mirror ⇒ किंमती
    200 − p (supply, DOWN)."""
    rows = [(110, 111, 108, 108.5), (108.5, 109, 106, 106.2), (106.2, 106.5, 103, 103.5),           # approach (area च्या वर)
            (103.5, 104, 101.0, 101.5), (101.5, 102.2, 100.6, 101.8), (101.8, 102.0, 100.4, 100.6),  # arrival + आतल्या candles
            (100.6, 101.5, 100.2, 101.2), (101.2, 105.5, 100.9, 105.2)]                              # commitment
    vol = [500, 520, 480, 900, 300, 700, 260, 1200]
    t0 = pd.Timestamp("2026-10-06 09:15")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], dtype=float)
    if mirror:
        df = pd.DataFrame({"open": 200 - df["open"], "high": 200 - df["low"], "low": 200 - df["high"], "close": 200 - df["close"]})
    df["timestamp"] = [t0 + pd.Timedelta(minutes=15 * k) for k in range(len(df))]
    df["bar_end"] = df["timestamp"] + pd.Timedelta(minutes=15)
    return df, np.array(vol, dtype=float)


def test_study_window_sides_and_line_mirror():
    up, v = zone_bars()
    dn, _ = zone_bars(mirror=True)
    a = VP.study(up, vol=v, area=SUP, d="BULLISH")
    b = VP.study(dn, vol=v, area=(98.0, 100.0), d="BEARISH")
    assert a["arm"] == b["arm"] == 3 and a["commit"] == b["commit"] == 7
    assert a["side"] == b["side"]                                          # trend-side / counter-side तेच (रंग उलटा नाही)
    assert a["side"][7] == 1 and a["side"][5] == -1
    avg = np.mean(v[3:7])
    assert a["avg"] == pytest.approx(avg) and a["commit_mult"] == pytest.approx(round(1200 / avg, 2))
    assert a["line"] == b["line"] and a["line"].startswith("volume: counter-side candles")
    assert "→ trend-side" in a["line"] and a["line"].endswith("avg")
    assert any("arrival" in c for c in a["computed"])                      # engine window नाही ⇒ helper ने काढलं (नोंद)


def test_study_uses_engine_window_and_vol_mult():
    up, v = zone_bars()
    info = {"area": SUP, "side": "BULLISH", "arm_ts": str(up["timestamp"].iloc[4]), "confirm_ts": str(up["timestamp"].iloc[7]),
            "vol_mult": 1.9}
    st = VP.study(up, vol=v, info={"tags": {"gate": info}})
    assert (st["arm"], st["commit"], st["commit_mult"]) == (4, 7, 1.9) and not st["computed"]
    ev = {"arm_bar": 4, "confirm_bar": 7, "area": SUP, "side": "BULLISH"}  # level_reaction.evaluate सारखा dict (ts नाही)
    st2 = VP.study(up, vol=v, info=ev)
    assert (st2["arm"], st2["commit"]) == (4, 7)


def test_na_line_when_volume_missing():
    up, _ = zone_bars()
    st = VP.study(up, vol=np.full(len(up), np.nan), area=SUP, d=1)
    assert st["line"] == VP.NA_LINE == "volume: NA (grade cap B)" and not st["pane"]
    v = np.r_[np.full(7, np.nan), 100.0]
    assert VP.study(up, vol=v, area=SUP, d=1)["line"] == VP.NA_LINE    # window मध्ये volume नाही ⇒ NA


def test_bar_volume_never_uses_rows_after_asof():
    starts = pd.date_range("2026-10-06 09:15", periods=3, freq="15min")
    fut = pd.DataFrame({"timestamp": pd.date_range("2026-10-06 09:15", periods=12, freq="5min"), "volume": [10.0] * 9 + [1e9] * 3})
    v = VP.bar_volume(starts, starts + pd.Timedelta(minutes=15), fut, asof=pd.Timestamp("2026-10-06 09:55"))
    assert list(v) == [30.0, 30.0, 20.0]                                   # 09:45 bar: 09:45, 09:50 पूर्ण; 09:55 row (10:00 ला संपते) नाही


# ------------------------------------------------------------------------------------------------ renderers (parametrized)
def _setup_data(mirror=False, with_volume=True, with_ltf=True):
    from decision3 import daily as DD
    from decision3 import setup_chart as SC
    days = pd.bdate_range("2026-08-03", periods=30)
    rng = np.random.default_rng(1)
    px = np.cumsum(rng.normal(0, 1, 30)) + 120
    d = pd.DataFrame({"timestamp": days, "open": px, "high": px + 1.5, "low": px - 1.5, "close": px + rng.normal(0, 0.5, 30)})
    sd = days[-1]
    m15 = []
    for k, day in enumerate(days[-3:]):
        for j in range(25):
            t = day + pd.Timedelta(hours=9, minutes=15 + 15 * j)
            b = 104 + 0.1 * j + k
            m15.append((t, b, b + 0.6, b - 0.6, b + 0.2))
    m15 = pd.DataFrame(m15, columns=["timestamp", "open", "high", "low", "close"])
    zb, zv = zone_bars()
    keep = m15[m15["timestamp"] < sd + pd.Timedelta(hours=9, minutes=15)]
    zb["timestamp"] = [sd + pd.Timedelta(hours=9, minutes=15 + 15 * k) for k in range(len(zb))]
    after = pd.DataFrame([(zb["timestamp"].iloc[-1] + pd.Timedelta(minutes=15 * (k + 1)), 130.0, 190.0, 129.0, 131.0) for k in range(4)],
                         columns=["timestamp", "open", "high", "low", "close"])   # setup bar नंतरच्या (भविष्य) मोठ्या candles
    m15 = pd.concat([keep, zb[["timestamp", "open", "high", "low", "close"]], after], ignore_index=True)
    if mirror:
        for fr in (m15, d):
            o, h, l_, c = fr["open"].copy(), fr["high"].copy(), fr["low"].copy(), fr["close"].copy()
            fr["open"], fr["high"], fr["low"], fr["close"] = 200 - o, 200 - l_, 200 - h, 200 - c
    m15["bar_end"] = m15["timestamp"] + pd.Timedelta(minutes=15)
    d["bar_end"] = d["timestamp"] + pd.Timedelta(hours=15, minutes=30)
    st = DD.DState(bar=29, day=sd, known_at=sd, trend="DOWN" if mirror else "UP", phase="impulse")
    fut = None
    if with_volume:
        rows = []
        for t, v in zip(m15["timestamp"], [400.0] * len(keep) + list(zv) + [1e9] * 4):
            rows += [(t + pd.Timedelta(minutes=5 * q), v / 3) for q in range(3)]
        fut = pd.DataFrame(rows, columns=["timestamp", "volume"])
    m1 = None
    if with_ltf:
        r1 = []
        for t, o, h, l_, c in m15[["timestamp", "open", "high", "low", "close"]].itertuples(index=False):
            for q in range(15):
                r1.append((t + pd.Timedelta(minutes=q), o, h, l_, c))
        m1 = pd.DataFrame(r1, columns=["timestamp", "open", "high", "low", "close"])
    D = SC.SetupData("NIFTY", m15, d, [st], m1=m1, fut=fut, sealed=lambda ts: False, state_at=lambda ts: st)
    lv = (98.0, 100.0) if mirror else SUP
    r = {"ts": str(zb["timestamp"].iloc[-1]), "bar_end": str(zb["timestamp"].iloc[-1] + pd.Timedelta(minutes=15)),
         "level": {"role": "resistance" if mirror else "support", "lo": lv[0], "hi": lv[1], "births": ["a:D2", "b"], "fresh": True,
                   "sweeps": 0, "tests": 0},
         "risk": {"entry": 94.8 if mirror else 105.2, "sl": 100.5 if mirror else 99.5, "target": 77.0 if mirror else 123.0, "rr": 3.1},
         "K": {"legs": 2}, "checklist": {"④": [True, "power shift 2/4"]}, "trend_notes": [], "weekly_trend": "UP", "trend_cap": None,
         "mature": False, "maturity_targets": [150.0], "conviction": "B", "conv_score": 0.5, "missing": [], "commit": {"form": "engulf"},
         "daily_trend": st.trend, "daily_phase": "impulse"}
    return D, r


def _render_setup(with_volume=True, mirror=False):
    import matplotlib.pyplot as plt
    from decision3 import setup_chart as SC
    D, r = _setup_data(mirror, with_volume)
    res = SC.render(D, r, header="test")
    fig = res["fig"]
    panes = [ax for ax in fig.axes if ax.get_gid() == VP.GID]
    ok = VP.mpl_has_pane(fig)
    plt.close(fig)
    return ok, res, panes


def _render_m15(with_volume=True, mirror=False):
    from decision3 import charts as CH
    D, r = _setup_data(mirror, with_volume, with_ltf=False)
    m = D.m15.copy()
    if with_volume:
        m["volume"] = VP.bar_volume(m["timestamp"], m["bar_end"], D.fut)
    t = int(np.flatnonzero(m["timestamp"] == pd.Timestamp(r["ts"]))[0])
    figs = []
    orig = CH._png
    CH._png = lambda fig: figs.append(fig) or b""
    try:
        CH.m15_png(type("V", (), {"m15": m})(), t, "NIFTY", r={**r, "decision": "setup"})
        CH.daily_png(D.daily_df.assign(volume=1000.0) if with_volume else D.daily_df, D.states * len(D.daily_df), "NIFTY")
    finally:
        CH._png = orig
    return all(VP.mpl_has_pane(f) for f in figs), figs, None


def _render_vision(with_volume=True, mirror=False):
    from bots_common import level_gate_bot as LGB
    from tests.test_vision_v0 import m1_frame, sig
    from vision import chart as CH
    s_ = sig(tags=LGB.gate_tags({"area": (24990.0, 25000.0), "side": "BULLISH", "entry_price": 25012.0, "sl": 24980.0,
                                 "target": 25120.0, "rr": 3.4, "confirm_ts": "2026-10-06 10:35:00", "arm_ts": "2026-10-06 10:10:00"},
                                {"reason": "UP"}, "5M"))
    df = m1_frame()
    setup, higher, tfs = CH.panels(df, s_["signal_ts"], s_["setup_tf"])
    fut = pd.DataFrame({"timestamp": pd.to_datetime(df["timestamp"]).dt.tz_convert("Asia/Kolkata").dt.tz_localize(None),
                        "volume": 100.0}) if with_volume else None
    vols = CH.panel_volumes(setup, higher, s_, s_["signal_ts"], df, fut)
    fig = CH.build_figure(setup, higher, s_, tfs, None, None, vols)
    return VP.plotly_has_pane(fig), fig, vols


RENDERERS = {"v22_setup_chart": _render_setup, "decision3_m15_daily": _render_m15, "vision_proposal": _render_vision}


@pytest.mark.parametrize("name", sorted(RENDERERS))
@pytest.mark.parametrize("with_volume", [True, False])
def test_every_renderer_has_volume_pane_or_na(name, with_volume):
    ok, out, _ = RENDERERS[name](with_volume)
    assert ok, name
    if name == "vision_proposal":
        texts = [str(a.text) for a in out.layout.annotations]
        bars = [t for t in out.data if t.type == "bar"]
        assert (len(bars) == 2) if with_volume else (sum("volume: NA" in t for t in texts) == 2)


@pytest.mark.parametrize("with_volume", [True, False])
def test_setup_chart_panes_no_future_and_one_caption_line(with_volume):
    from decision3 import setup_chart as SC
    ok, res, panes = _render_setup(with_volume)
    assert len(panes) == 3                                                  # Daily + 15M + 5M
    vs = res["vol"]
    assert vs["n"] == vs["commit"] + 1                                     # pane setup bar वर संपतो
    if with_volume:
        assert np.nanmax(vs["vol"]) < 1e6 and np.nanmax(res["ltf_vol"]["vol"]) < 1e6   # setup bar नंतरचा (1e9) volume कधीच नाही
        assert vs["ok"] and vs["commit"] == vs["n"] - 1 and vs["arm"] == vs["n"] - 5
    else:
        assert res["vline"] == VP.NA_LINE
    D, r = _setup_data(False, with_volume)
    _, cap = SC.caption(D, r, res["st"], res["short"], res["longst"], vline=res["vline"], vst=vs)
    assert sum(1 for x in cap.splitlines() if x.startswith("volume:")) == 1
    assert cap.splitlines()[0].startswith("What to look at:") and "Engine detail:" in cap
    assert cap.index("K leg") > cap.index("Engine detail:") and cap.index("Q44") > cap.index("Engine detail:")


def test_setup_chart_mirror_same_volume_read():
    _, up, _ = _render_setup(True, mirror=False)
    _, dn, _ = _render_setup(True, mirror=True)
    for k in ("arm", "commit", "commit_mult", "trend_mult", "counter_mult", "line"):
        assert up["vol"][k] == dn["vol"][k], k
    assert up["vol"]["side"] == dn["vol"]["side"]


def test_setup_chart_q44_not_on_15m_panel():
    import matplotlib.pyplot as plt
    from decision3 import setup_chart as SC
    D, r = _setup_data()
    res = SC.render(D, r)
    fig = res["fig"]
    m15_ax = next(ax for ax in fig.axes if ax.get_title(loc="left").startswith("15M"))
    texts = [t.get_text() for t in m15_ax.texts]
    assert not any("Q44" in t for t in texts)
    plt.close(fig)


def test_vision_volume_line_in_render_meta():
    from tests.test_vision_v0 import m1_frame, sig
    from vision import chart as CH
    png, meta = CH.render(m1_frame(), sig())
    assert meta["volume_line"] == VP.NA_LINE                               # futures volume दिला नाही ⇒ NA (spot volume कधीच नाही)
