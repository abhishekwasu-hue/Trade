"""mtf (W / D / 1H / 15M TF-native थर + charts), instruments, chart_concepts, dump scripts — synthetic data (खरा data नाही)."""
import json
import os
import re

import numpy as np
import pandas as pd
import pytest

import instruments as INS
from elliott import data_policy as DP
from mtf import adapter as MA
from mtf import charts as MC
from mtf import concepts as CC
from mtf import run as MR
from pivots import engine as PE

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(autouse=True)
def _reset_instrument():
    yield
    INS._current["name"] = None


def _walk(n, seed=3, base=40000.0, step=60.0):
    rng = np.random.default_rng(seed)
    drift = np.sin(np.arange(n) / 9.0) * step * 0.9                            # लाटा ⇒ swings / I / K
    c = base + np.cumsum(drift + rng.normal(0, step * 0.5, n))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + rng.uniform(0.1, 0.6, n) * step
    lo = np.minimum(o, c) - rng.uniform(0.1, 0.6, n) * step
    return o, h, lo, c


def tf_frame(tf, n, start, seed=3):
    """synthetic TF candles (खऱ्या दिसणाऱ्या वेळा): W सोमवार, D business days, 1H / 15M session मध्ये."""
    if tf == "W":
        ts = pd.date_range(start, periods=n, freq="W-MON")
    elif tf == "D":
        ts = pd.bdate_range(start, periods=n)
    else:
        step = 60 if tf == "1H" else 15
        per = 7 if tf == "1H" else 25
        days = pd.bdate_range(start, periods=n // per + 2)
        ts = pd.DatetimeIndex([d + pd.Timedelta(hours=9, minutes=15) + pd.Timedelta(minutes=step * k) for d in days for k in range(per)])[:n]
    o, h, lo, c = _walk(n, seed)
    return pd.DataFrame({"timestamp": ts, "open": o, "high": h, "low": lo, "close": c})


START = {"W": pd.Timestamp(DP.CONTAMINATED_START) - pd.Timedelta(weeks=170), "D": pd.Timestamp(DP.CONTAMINATED_START) - pd.Timedelta(days=330)}


def _frames():
    s15 = pd.Timestamp(DP.CONTAMINATED_START) + pd.Timedelta(days=7)
    return {"W": tf_frame("W", 160, START["W"]), "D": tf_frame("D", 220, START["D"]), "1H": tf_frame("1H", 210, s15, 5),
            "15M": tf_frame("15M", 500, s15 + pd.Timedelta(days=14), 7)}


@pytest.fixture(scope="module")
def built():
    INS.set_current("BANKNIFTY")
    fr = _frames()
    Cs = {tf: MA.build(fr[tf], tf, "BANKNIFTY") for tf in MA.TFS}
    INS._current["name"] = None
    return fr, Cs


# ---------------------------------------------------------------------------------------------------------------- instruments
def test_registry_both_instruments_and_default():
    assert set(INS.names()) >= {"NIFTY", "BANKNIFTY"}
    assert INS.current() == os.environ.get("TRADE_INSTRUMENT", "NIFTY").upper()
    assert INS.holdout("NIFTY") and not INS.holdout("BANKNIFTY")
    assert INS.get("BANKNIFTY")["futures"] is None and INS.label("banknifty") == "BANKNIFTY"
    with pytest.raises(ValueError):
        INS.get("XYZ")


def test_nifty_holdout_guard_and_banknifty_open():
    ts = pd.date_range(DP.HOLDOUT_START + pd.Timedelta(days=30), periods=4, freq="15min")
    df = pd.DataFrame({"timestamp": ts, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
    with pytest.raises(DP.HoldoutError):
        PE.guard(df, instrument="NIFTY")
    INS.set_current("NIFTY")
    with pytest.raises(DP.HoldoutError):
        PE.guard(df)                                                              # default / चालू = NIFTY ⇒ sealed
    assert len(PE.guard(df, instrument="BANKNIFTY")) == 4
    assert len(MA.guard_real(df, "NIFTY")) == 0 and len(MA.guard_real(df, "BANKNIFTY")) == 4
    shown = df.assign(display_only=True)
    with pytest.raises(DP.HoldoutError):
        PE.guard(shown, instrument="BANKNIFTY")                                  # display_only कधीच engine मध्ये नाही


def test_load_futures_none_without_futures():
    from scripts import leg_check as LC
    INS.set_current("BANKNIFTY")
    assert LC.load_futures("/nonexistent") is None


def test_chart_titles_follow_instrument():
    src = ["swings2/charts.py", "legs2/charts2.py", "legs2/charts.py", "patterns2/charts2.py", "patterns2/charts.py", "zones2/charts.py",
           "trendlines2/charts.py", "rsi2/charts.py", "review7/charts.py", "pivots/charts.py"]
    for f in src:
        s = open(os.path.join(ROOT, f), encoding="utf-8").read()
        assert "· NIFTY {tf}" not in s and "INS.label()" in s, f


# ---------------------------------------------------------------------------------------------------------------- adapter
def test_synthetic_sessions_one_candle_each_and_real_time_kept():
    d = tf_frame("D", 30, START["D"])
    m, syn = MA.pseudo15(d, "D")
    assert syn and m["timestamp"].dt.normalize().nunique() == 30                 # एक candle = एक session
    assert (m["real_ts"] == d["timestamp"]).all()
    assert (m["real_end"] == d["timestamp"].dt.normalize() + pd.Timedelta(hours=15, minutes=30)).all()
    w = tf_frame("W", 3, START["W"])
    assert (MA.real_end(w["timestamp"], "W").dt.weekday == 4).all()            # आठवड्याचा शुक्रवार 15:30
    q, syn15 = MA.pseudo15(tf_frame("15M", 30, pd.Timestamp(DP.CONTAMINATED_START) + pd.Timedelta(days=7)), "15M")
    assert not syn15 and (q["bar_end"] - q["timestamp"] == pd.Timedelta(minutes=15)).all()


def test_build_every_tf_and_k_atoms_off_for_synthetic(built):
    fr, Cs = built
    for tf, C in Cs.items():
        assert C.tf == tf and C.instrument == "BANKNIFTY" and len(C.real_ts) == len(fr[tf])
        assert C.synthetic == (tf != "15M")
        if C.synthetic:
            assert all(not z.get("k") for snap in C.Z.snap.values() for z in snap)     # PDH / PDL zones नाहीत
        assert len(C.D) == len(fr[tf])


def test_bar_at_is_closed_candles_only(built):
    _, Cs = built
    C = Cs["W"]
    t = 50
    assert MA.bar_at(C, C.real_end[t]) == t
    assert MA.bar_at(C, C.real_end[t] - pd.Timedelta(minutes=1)) == t - 1      # आठवडा बंद होण्याआधी ⇒ आधीचा
    assert MA.bar_at(C, C.real_ts[0] - pd.Timedelta(days=1)) is None


def test_truncation_layers_known_at(built):
    fr, Cs = built
    tf, cut = "D", 160
    Cc = MA.build(fr[tf].iloc[:cut], tf, "BANKNIFTY")
    Cf = Cs[tf]
    for t in (120, 140, cut - 1):
        assert MC.trend_rows(Cc, t) == MC.trend_rows(Cf, t)
        assert Cc.trk[1].state(t).get("state") == Cf.trk[1].state(t).get("state")
        assert sorted(z["id"] for z in Cc.Z.snap.get(t) or []) == sorted(z["id"] for z in Cf.Z.snap.get(t) or [])
        assert (Cc.D[t] or {}).get("decision") == (Cf.D[t] or {}).get("decision")


# ---------------------------------------------------------------------------------------------------------------- concepts
def test_concepts_defaults_store_and_validation(tmp_path):
    p = str(tmp_path / "cc.json")
    cfg = CC.load(p)
    assert cfg["mode"] == "all" and all(v["show"] for v in cfg["concepts"].values())
    cfg["concepts"]["abc"]["show"] = False
    cfg["mode"] = "primary"
    CC.save(cfg, p)
    back = CC.load(p)
    assert back["concepts"]["abc"]["show"] is False and back["mode"] == "primary"
    assert not CC.on(back, "sweep")                                              # secondary ⇒ primary mode मध्ये नाही
    assert CC.on(back, "zones", "अ")
    with pytest.raises(ValueError):
        CC.validate({"concepts": {"nope": {"show": True}}})
    with pytest.raises(ValueError):
        CC.validate({"mode": "x"})
    o = CC.load(p, CC.cli_overrides("zones", "all"))
    assert o["mode"] == "all" and o["concepts"]["zones"]["show"] is False


def test_dashboard_form_values_roundtrip():
    import page_backtest_review as PB
    cfg = CC.defaults()
    vals = PB.concepts_form_values(cfg, lambda kind, key, cur: (False if (kind == "show" and key == "b2") else cur))
    CC.validate(vals)
    assert vals["concepts"]["b2"]["show"] is False and vals["concepts"]["b1"]["show"] is True and vals["window"] == CC.WINDOW


def _legend(fig):
    return " ".join(a.text for a in fig.layout.annotations if a.text)


@pytest.mark.parametrize("key", list(CC.CONCEPTS))
def test_each_concept_toggle(built, key):
    _, Cs = built
    C = Cs["15M"]
    t = len(C.real_ts) - 1
    cfg = CC.merge(CC.defaults(), {"concepts": {key: {"show": False}}})
    td = MC.topdown(Cs, C.real_end[t])
    marks, pl, cache = MC.tf_review(C, t, cfg)
    for fig in (MC.structure_fig(C, t, cfg, td, None, "x"), MC.entry_fig(C, t, cfg, marks, pl, cache, td, None, "x")):
        if key in fig._mtf_used:
            assert fig._mtf_used[key] == 0
            assert f"✕ {CC.CONCEPTS[key][0]} (बंद)" in _legend(fig)


def test_legend_marks_na_concepts_and_core_concepts_draw(built):
    _, Cs = built
    C = Cs["D"]                                                                 # 220 candles ⇒ σ / warm-up नंतर pivots
    t = len(C.real_ts) - 1
    fig = MC.structure_fig(C, t, CC.defaults(), MC.topdown(Cs, C.real_end[t]), MC.upper_ctx(Cs["W"], C.real_end[t], None), "x")
    used = fig._mtf_used
    assert used["swings"] > 0 and used["trend"] > 0 and used["topdown"] > 0           # खरंच काढलं (mapping तुटलं तर NA दिसलं असतं)
    assert len(fig.data) > 2                                                    # candles + zigzag traces
    leg = _legend(fig)
    for k, n in used.items():
        nm = CC.CONCEPTS[k][0]
        assert (f"✓ {nm}" in leg) if n else (f"NA (अजून नाही) {nm}" in leg)


def test_zone_sweeps_causal_under_truncation(built):
    fr, Cs = built
    cut = 420
    Cc = MA.build(fr["15M"].iloc[:cut], "15M", "BANKNIFTY")
    Cf = Cs["15M"]
    for t in range(cut - 30, cut):
        assert MC.sweeps(Cc, 0, t) == MC.sweeps(Cf, 0, t)
    for t in range(cut - 6, cut):
        for m in MC.tf_review(Cc, t, CC.defaults())[0]:
            if m["final"]:
                assert m in MC.tf_review(Cf, t, CC.defaults())[0]


# ---------------------------------------------------------------------------------------------------------------- दिवस: 8 images + caption
def test_run_day_eight_images_caption_and_manifest(built, tmp_path, monkeypatch):
    _, Cs = built
    from backtest_review import telegram as TG
    from pivots import charts as PC
    monkeypatch.setattr(PC, "png", lambda fig: ("PNG" + fig.layout.title.text).encode())
    asof = Cs["15M"].real_end.iloc[-1]
    out = MR.run_day(Cs, asof, CC.defaults(), str(tmp_path / "d1"))
    assert sorted(out["files"]) == sorted(f"{tf}_{x}.png" for tf in MA.TFS for x in "ab")
    cap = out["caption"]
    assert len(cap.encode("utf-16-le")) // 2 <= MR.MAX_CAPTION
    for tf in MA.TFS:
        assert f"\n{tf}: " in cap                                                # top-down 4 ओळी
    assert "B1" in cap and "B2" in cap
    man = {"run_id": "t", "title": "MTF", "items": [{"date": "d1", "item": "mtf/t|day:d1", "reading": "r", "caption": cap,
                                                       "files": [f"d1/{f}" for f in out["files"]]}]}
    json.dump(man, open(tmp_path / "manifest.json", "w", encoding="utf-8"), ensure_ascii=False)
    m = TG.load_manifest(str(tmp_path))
    assert len(m["items"][0]["files"]) == 8 and TG.caption(m, m["items"][0]) == cap
    j = json.load(open(tmp_path / "d1" / "mtf_day.json", encoding="utf-8"))
    for tf in MA.TFS:
        for mk in j["tf"][tf]["marks"]:
            assert mk["known_at"] >= mk["bar"] and mk["type"] in ("✅", "🟡")


def test_caption_truncates_to_limit(built):
    _, Cs = built
    td = MC.topdown(Cs, Cs["15M"].real_end.iloc[-1])
    mk = {"type": "✅", "real_ts": "2000-01-03 10:00", "side": "bull put", "area": {"kind": "zone", "stars": 3, "self": True}, "c4": ["shrink"] * 40}
    per = {"15M": {"marks": [mk] * 30, "plan": {"items": [{"side": "bull put", "bot": 1.0, "top": 2.0, "sl": 0.5, "target": 9.0, "rr": 9}] * 3,
                                                   "invalid": "x" * 900}}}
    cap = MR.caption(Cs["15M"].real_end.iloc[-1], td, per)
    assert len(cap.encode("utf-16-le")) // 2 <= MR.MAX_CAPTION


def test_topdown_warns_on_mismatch():
    class FakeC:
        def __init__(self, tf, tr):
            self.tf, self.tr = tf, tr
            self.real_end = pd.Series([pd.Timestamp("2000-01-03 15:30")])
            st = {"state": "K चालू"}
            self.trk = {1: type("T", (), {"state": lambda _s, t: st})()}
    import review7.method as RM
    trends = {"W": ("DOWN", -1), "D": ("DOWN", -1), "1H": ("UP", 1), "15M": ("UP", 1)}
    orig = RM.trend
    try:
        RM.trend = lambda C, t: (2, trends[C.tf][0], trends[C.tf][1])
        td = MC.topdown({tf: FakeC(tf, trends[tf]) for tf in MA.TFS}, pd.Timestamp("2000-01-04"))
    finally:
        RM.trend = orig
    assert any(w.startswith("⚠ 1H ↑ पण D ↓") for w in td["warn"]) and "⚠" in td["strip"]


# ---------------------------------------------------------------------------------------------------------------- scripts
def _write_tf_dir(tmp_path, fr, ins="BANKNIFTY"):
    d = tmp_path / "tf"
    d.mkdir()
    for tf, df in fr.items():
        df.to_csv(d / f"{ins}_{tf}.csv.gz", index=False)
    return str(d)


def test_mtf_check_cli_banknifty(tmp_path, monkeypatch):
    from pivots import charts as PC
    from scripts import mtf_check as SM
    monkeypatch.setattr(PC, "png", lambda fig: ("PNG" + fig.layout.title.text).encode())
    fr = _frames()
    tfd = _write_tf_dir(tmp_path, fr)
    day = str(fr["15M"]["timestamp"].iloc[-1].date())
    early = str((fr["W"]["timestamp"].iloc[0] - pd.Timedelta(days=30)).date())  # data आधीचा दिवस ⇒ वगळला
    man = SM.main(["--instrument", "BANKNIFTY", "--tf-dir", tfd, "--dates", early, day, "--out-dir", str(tmp_path / "out"), "--run-id", "r1",
                   "--concepts-path", str(tmp_path / "cc.json"), "--concepts-off", "abc"])
    assert man["instrument"] == "BANKNIFTY" and len(man["items"]) == 1 and len(man["items"][0]["files"]) == 8
    assert man["concepts"]["concepts"]["abc"]["show"] is False
    from backtest_review import telegram as TG
    m = TG.load_manifest(str(tmp_path / "out" / "r1"))                         # sender जसाच्या तसा वाचतो
    assert m["items"][0]["n"] == 1 and TG.caption(m, m["items"][0]).startswith("🗺 MTF CHECK")
    with pytest.raises(SystemExit):
        SM.main(["--instrument", "BANKNIFTY", "--tf-dir", str(tmp_path / "nope"), "--dates", day, "--out-dir", str(tmp_path / "o2"),
                 "--run-id", "r2"])


def _nifty_1m(days):
    rows = []
    rng = np.random.default_rng(11)
    px = 24000.0
    for d in days:
        for k in range(375):
            ts = d + pd.Timedelta(hours=9, minutes=15 + k)
            o = px
            px = px + rng.normal(0, 4) + np.sin(k / 40.0) * 2
            rows.append({"timestamp": ts, "open": o, "high": max(o, px) + 2, "low": min(o, px) - 2, "close": px})
    return pd.DataFrame(rows)


def test_nifty_path_display_only_wd_and_full_intraday(tmp_path, monkeypatch):
    from pivots import charts as PC
    from scripts import mtf_check as SM
    monkeypatch.setattr(PC, "png", lambda fig: ("PNG" + fig.layout.title.text).encode())
    days = list(pd.bdate_range(pd.Timestamp(DP.CONTAMINATED_START) + pd.Timedelta(days=7), periods=30))
    p = tmp_path / "n1m.csv"
    _nifty_1m(days).to_csv(p, index=False)
    asof_day = days[-3]                                                          # बुधवार / मधला दिवस: पुढचे candles दिसू नयेत
    man = SM.main(["--instrument", "NIFTY", "--m1", str(p), "--dates", str(asof_day.date()), "--out-dir", str(tmp_path / "o"),
                   "--run-id", "n", "--asof-time", "13:00"])
    files = man["items"][0]["files"]
    assert any(f.endswith("W_display.png") for f in files) and any(f.endswith("D_display.png") for f in files)
    assert not any(f.endswith(("W_a.png", "D_a.png", "W_b.png", "D_b.png")) for f in files)
    assert any(f.endswith("15M_a.png") for f in files) and any(f.endswith("1H_b.png") for f in files)
    INS.set_current("NIFTY")
    fr, disp = SM.holdout_frames([str(p)])
    asof = asof_day + pd.Timedelta(hours=13)
    dd = MR.display_frame(disp["D"], "D", asof)
    assert pd.to_datetime(dd["timestamp"]).max() < asof_day                       # आजचा अपूर्ण दिवस नाही
    ww = MR.display_frame(disp["W"], "W", asof)
    assert (MA.real_end(pd.to_datetime(ww["timestamp"]), "W") <= asof).all()       # चालू आठवडा नाही


def test_holdout_side_epoch_and_wd_refusal():
    pre = tf_frame("1H", 70, pd.Timestamp(DP.HOLDOUT_START) - pd.Timedelta(days=20))
    post = tf_frame("1H", 70, pd.Timestamp(DP.CONTAMINATED_START) + pd.Timedelta(days=3))
    both = pd.concat([pre, post], ignore_index=True)
    g = MA.guard_real(both, "NIFTY", "1H")
    assert len(g) and (pd.to_datetime(g["timestamp"]) >= DP.HOLDOUT_START).all()   # gap ओलांडून जोडत नाही — फक्त नंतरची बाजू
    assert len(MA.guard_real(both, "BANKNIFTY", "1H")) == len(both)
    last = pd.Timestamp(DP.CONTAMINATED_START) - pd.Timedelta(days=1)
    wk = pd.DataFrame({"timestamp": [last - pd.to_timedelta(last.weekday(), unit="D")], "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
    assert len(MA.guard_real(wk, "NIFTY", "W")) == 0                               # holdout मधला आठवडा ⇒ नाही
    m, _ = MA.pseudo15(tf_frame("D", 20000, START["D"]), "D")
    assert pd.to_datetime(m["timestamp"]).max() < DP.IS_START                      # कृत्रिम sessions holdout / IS पर्यंत कधीच नाहीत
    with pytest.raises(DP.HoldoutError):
        MA.check_tf_allowed("NIFTY", "D")
    MA.check_tf_allowed("BANKNIFTY", "W")
    assert MA.tf_of_path("/x/BANKNIFTY_1H.csv.gz") == "1H"
    with pytest.raises(ValueError):
        MA.tf_of_path("/x/foo.csv")


def test_build_uses_given_instrument_not_global(monkeypatch):
    monkeypatch.setenv("TRADE_INSTRUMENT", "NIFTY")
    INS._current["name"] = None
    df = tf_frame("15M", 400, pd.Timestamp(DP.HOLDOUT_START) + pd.Timedelta(days=40), 9)
    C = MA.build(df, "15M", "BANKNIFTY")                                        # holdout तारखा, पण BANKNIFTY ⇒ चालतं
    assert len(C.real_ts) == 400 and INS.current() == "NIFTY"                    # global बदलला नाही
    with pytest.raises(DP.HoldoutError):
        MA.build(df.assign(display_only=True), "15M", "BANKNIFTY")


def test_1m_loader_refuses_non_holdout_instrument(tmp_path):
    from scripts import swing_check as SC
    INS.set_current("BANKNIFTY")
    with pytest.raises(ValueError):
        SC.load_1m([str(tmp_path / "x.csv")])


def test_daily_trend_probe_and_tf_csv_dumps(tmp_path):
    from scripts import daily_trend_probe as DTP
    from scripts import degree_diag as DD
    from scripts import zone_structural_death as ZSD
    fr = _frames()
    fr["D"] = tf_frame("D", 220, pd.Timestamp(fr["1H"]["timestamp"].iloc[-1]).normalize() - pd.Timedelta(days=300))
    tfd = _write_tf_dir(tmp_path, fr)
    s = DTP.main(["--instrument", "BANKNIFTY", "--tf-dir", tfd, "--out-dir", str(tmp_path / "p")])
    assert len(s["k_options"]) == 3 and any(k.startswith("default (D1 4 / D2 6)") for k in s["k_options"])
    assert s["vs_1h"]["days"] > 0 and s["vs_1h"]["हो"] + s["vs_1h"]["नाही"] + s["vs_1h"]["NA"] == s["vs_1h"]["days"]
    for f in ("daily_pivots_k.csv", "daily_trend_segments.csv", "daily_vs_1h.csv", "daily_trend_probe.md"):
        assert os.path.exists(tmp_path / "p" / f)
    seg = pd.read_csv(tmp_path / "p" / "daily_trend_segments.csv")
    assert seg["from"].min() >= str(fr["D"]["timestamp"].iloc[0].date())       # खऱ्या तारखा (कृत्रिम नाहीत)
    DD.main(["--instrument", "BANKNIFTY", "--tf-csv", os.path.join(tfd, "BANKNIFTY_D.csv.gz"), "--tf", "D", "--out-dir", str(tmp_path / "dd")])
    piv = pd.read_csv(tmp_path / "dd" / "degree_pivots.csv")
    assert piv["bar"].str[:4].astype(int).min() >= fr["D"]["timestamp"].iloc[0].year
    ZSD.main(["--instrument", "BANKNIFTY", "--tf-csv", os.path.join(tfd, "BANKNIFTY_D.csv.gz"), "--tf", "D", "--out-dir", str(tmp_path / "dd")])
    z = json.load(open(tmp_path / "dd" / "zone_structural_death.json", encoding="utf-8"))
    assert z["sigma_unit"].startswith("σ_D") and z["instrument"] == "BANKNIFTY"
    zs = pd.read_csv(tmp_path / "dd" / "zone_structural_death.csv")
    assert not zs["id"].astype(str).str.startswith("k").any()                   # कृत्रिम sessions ⇒ PDH / PDL zones नाहीत


# ---------------------------------------------------------------------------------------------------------------- स्रोत नियम
def test_sources_date_free_instrument_free_no_orders():
    files = ["mtf/adapter.py", "mtf/charts.py", "mtf/concepts.py", "mtf/run.py", "scripts/mtf_check.py", "scripts/daily_trend_probe.py",
             "instruments.py", "research/index_candles_fetch.py"]
    for f in files:
        s = open(os.path.join(ROOT, f), encoding="utf-8").read()
        assert not re.search(r"20\d\d-\d\d-\d\d", s), f
        assert "place_order" not in s and "LIVE" not in s, f
        if f.startswith("mtf/"):
            assert '"NIFTY"' not in s and "'NIFTY'" not in s, f
