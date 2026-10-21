"""Abhi (live switches): each finished Chart Reader layer is switchable from the dashboard (advanced, 15M SRv2 engine block) — the method
(default, empty) or its existing legacy what-if — without a deploy. No network.

  • empty / the method ⇒ V22 gets no settings (today's live behaviour byte-for-byte);
  • each legacy value reaches V22 (live decision and pre-open levels), together with the layer-1 swing scale;
  • an unknown value (or a legacy visit without the legacy commitment volume) is refused with a reason, before any data fetch or
    instrument switch;
  • the switches mirror decision3's own settings (default = the method, alternatives = the registered legacy what-ifs);
  • Abhi L1-c: the Daily pivot size N (`engine3_daily_pivot_n`, empty = the provisional 2) reaches V22 the same way as the swing scale;
  • the dashboard parsing (shown value, labels, what is saved) never breaks the page and never saves an incoherent combo.
"""
import os

import pandas as pd
import pytest

import engine3_live as L
import engine_signal as ES
from tests.test_engine3_1m import NOW, PRE, Feed1m, fake_v22_levels  # noqa: F401 — fixture

OFF = {"engine3_use_1m": False}
LEGACY = {"engine3_zone_visit_rule": ("close_away", "touch_window"), "engine3_commit_volume_rule": ("opposite",),
          "engine3_line_rule": ("sigma",), "engine3_div_degree_rule": ("all",), "engine3_verdict_rule": ("score",),
          "engine3_entry_gate": ("legacy_k",)}


def test_switches_mirror_decision3_settings():
    from decision3 import engine as E3
    from decision3 import settings as S3
    assert set(L.METHOD_SWITCHES) == set(LEGACY)
    for key, (v22_key, allowed, _label) in L.METHOD_SWITCHES.items():
        assert key.startswith("engine3_")                                # the only keys engine_signal.engine3_settings passes on
        assert allowed[0] == S3.DEFAULTS[v22_key]                        # default = the method = decision3's default
        assert set(allowed[1:]) == set(LEGACY[key])
        for v in allowed:
            assert v in S3.REGISTER[v22_key][1]                         # every value is a registered method / legacy what-if
    assert L.METHOD_SWITCHES["engine3_zone_visit_rule"][1] == E3.VISIT_RULES


def test_empty_or_the_method_means_no_v22_settings(fake_v22_levels):
    method = {k: a[0] for k, (_v, a, _l) in L.METHOD_SWITCHES.items()}
    for s in (None, {}, {k: "" for k in LEGACY}, {k: " " for k in LEGACY}, {k: None for k in LEGACY}, method,
              {k: v.upper() for k, v in method.items()}):
        assert L.method_switches(s) == {} and L.v22_settings(s) is None
        L.compute("BANKNIFTY", Feed1m(), NOW, {**OFF, **(s or {})})
        L.watched_levels("BANKNIFTY", Feed1m(), PRE, {**OFF, **(s or {})})
        assert fake_v22_levels["s"][-2:] == [None, None]                   # V22 on decision3's defaults, exactly as before
    assert L.v22_settings({"engine3_swing_k_d1": "5", "engine3_swing_k_d2": "8"}) == {"swing_k": {1: 5.0, 2: 8.0}}   # swing_scale unchanged


@pytest.mark.parametrize("key,value", [(k, v) for k, vs in LEGACY.items() for v in vs])
def test_each_legacy_value_reaches_v22_live_and_preopen(fake_v22_levels, key, value):
    v22_key = L.METHOD_SWITCHES[key][0]
    s = {key: f" {value.upper()} "}
    if key == "engine3_zone_visit_rule":                                  # a legacy visit has no approach leg ⇒ paired volume rule
        s["engine3_commit_volume_rule"] = "opposite"
    want = {v22_key: value, **({"commit_volume_rule": "opposite"} if key == "engine3_zone_visit_rule" else {})}
    assert L.v22_settings(s) == want
    L.compute("BANKNIFTY", Feed1m(), NOW, {**OFF, **s})
    assert fake_v22_levels["s"][-1] == want
    L.watched_levels("BANKNIFTY", Feed1m(), PRE, {**OFF, **s})
    assert fake_v22_levels["s"][-1] == want


def test_switches_combine_with_the_swing_scale(fake_v22_levels):
    s = {**OFF, "engine3_swing_k_d1": 5, "engine3_swing_k_d2": 8, "engine3_line_rule": "sigma", "engine3_verdict_rule": "score"}
    L.compute("BANKNIFTY", Feed1m(), NOW, s)
    assert fake_v22_levels["s"][-1] == {"swing_k": {1: 5.0, 2: 8.0}, "line_rule": "sigma", "verdict_rule": "score"}


class CountingFeed(Feed1m):
    def __init__(self, **k):
        super().__init__(**k)
        self.calls = 0

    def index(self, sym, interval, days):
        self.calls += 1
        return super().index(sym, interval, days)


@pytest.mark.parametrize("bad,why", [
    ({"engine3_verdict_rule": "scores"}, "allowed: method / score"),
    ({"engine3_line_rule": 1}, "allowed: logic / sigma"),
    ({"engine3_zone_visit_rule": "time"}, "allowed: structure / close_away / touch_window"),
    ({"engine3_commit_volume_rule": "largest"}, "allowed: approach_and_opposite / opposite"),
    ({"engine3_div_degree_rule": "d2"}, "allowed: zone / all"),
    ({"engine3_daily_pivot_n": "0"}, "engine3_daily_pivot_n = '0' — a whole number 1..5"),
    ({"engine3_daily_pivot_n": "2.5"}, "a whole number 1..5"),
    ({"engine3_daily_pivot_n": "abc"}, "a whole number 1..5"),
    ({"engine3_daily_pivot_n": 6}, "engine3_daily_pivot_n = 6 — a whole number 1..5"),
    ({"engine3_zone_visit_rule": "close_away"}, "commit_volume_rule = 'opposite'"),
    ({"engine3_zone_visit_rule": "touch_window", "engine3_commit_volume_rule": "approach_and_opposite"}, "knows no approach leg"),
])
def test_bad_values_are_refused_before_any_fetch_and_the_instrument_switch(fake_v22_levels, bad, why):
    import instruments as INS
    prev = INS._current["name"]
    with pytest.raises(ValueError, match=why.replace("(", r"\(")):
        L.v22_settings(bad)
    for fn, now in ((L.compute, NOW), (L.watched_levels, PRE)):
        f = CountingFeed()
        with pytest.raises(ValueError, match=why.replace("(", r"\(")):
            fn("BANKNIFTY", f, now, {**OFF, **bad})
        assert f.calls == 0 and INS._current["name"] == prev and fake_v22_levels["s"] == []


def test_run3_fails_closed_on_a_bad_switch(monkeypatch):
    """The engine's error path: run3 raises (the run script writes an error row + a Telegram line); nothing is stored."""
    monkeypatch.setattr(L, "UpstoxFeed", lambda tok, today=None: CountingFeed())
    with pytest.raises(ValueError, match="engine3_verdict_rule"):
        ES.run3("BANKNIFTY", "tok", now=NOW, s={"engine3_verdict_rule": "bogus"}, dry_run=True)


@pytest.mark.parametrize("bad", [{"engine3_verdict_rule": "bogus"}, {"engine3_daily_pivot_n": 9}, {"engine3_swing_k_d1": "abc"}])
def test_every_bad_setting_is_a_setting_error(bad):
    with pytest.raises(L.SettingError) as e:
        L.v22_settings(bad)
    assert e.value.setting_error is True and isinstance(e.value, ValueError)
    assert not getattr(L.EngineDataError("x"), "setting_error", False)


def test_a_setting_error_alert_says_fix_it_on_the_dashboard(tmp_path, monkeypatch):
    """The run script: a bad engine3_* setting ⇒ error row + Telegram "setting error — fix it on the dashboard" (the key named); a data
    error keeps "until the data is back"."""
    from scripts import engine_signal_run as ESR
    monkeypatch.setenv("ENGINE_SIGNAL_DB", str(tmp_path / "es.db"))
    sent = []

    def bad(sym, tok):
        return L.v22_settings({"engine3_daily_pivot_n": 9})

    def data(sym, tok):
        raise L.EngineDataError(f"{sym}: 5M spot (LTF) data नाही")
    for fn, al in ((bad, "a.json"), (data, "b.json")):
        assert ESR.main(["--symbols", "BANKNIFTY"], token_fn=lambda: "tok", run_fn=fn, market_fn=lambda: True, send=sent.append,
                        alert_path=str(tmp_path / al), now=pd.Timestamp("2030-01-07 10:16"), symbols_fn=lambda: ["BANKNIFTY"]) == 1
    assert len(sent) == 2
    assert "engine3_daily_pivot_n = 9" in sent[0] and "setting error — fix it on the dashboard" in sent[0]
    assert "until the data is back" not in sent[0]
    assert "until the data is back" in sent[1] and "setting error" not in sent[1]
    assert ES.latest("BANKNIFTY", "2030-01-07 10:17")["decision"] == ES.ERROR


def test_cloud_db_defaults_and_engine3_settings_pass_the_switches():
    import cloud_db
    d = cloud_db.STRATEGY_SETTINGS_DEFAULTS[ES.ENGINE3_SETTINGS_KEY]
    assert all(d[k] == "" for k in L.METHOD_SWITCHES) and d["engine3_daily_pivot_n"] == ""   # empty = the method / provisional N
    assert L.v22_settings(d) is None                                      # the stored defaults ⇒ V22 on decision3's defaults
    stored = {**{k: a[-1] for k, (_v, a, _l) in L.METHOD_SWITCHES.items()}, "engine3_daily_pivot_n": 3,
              "verdict_rule": "score", "daily_pivot_n": 5, "lots": 1}
    got = ES.engine3_settings("nifty", lambda k, s: stored)
    assert got == {k: v for k, v in stored.items() if k.startswith("engine3_")} and len(got) == len(L.METHOD_SWITCHES) + 1


# ------------------------------------------------------------------------------------------------ Abhi L1-c: Daily pivot size N
def test_daily_pivot_n_empty_or_two_means_no_v22_settings(fake_v22_levels):
    from decision3 import settings as S3
    assert S3.DEFAULTS["daily_pivot_n"] == 2                              # provisional N (L1-c)
    for v in (None, "", " ", 2, "2", 2.0, " 2 "):
        assert L.daily_pivot_n({"engine3_daily_pivot_n": v}) is None
        assert L.v22_settings({"engine3_daily_pivot_n": v}) is None
        L.compute("BANKNIFTY", Feed1m(), NOW, {**OFF, "engine3_daily_pivot_n": v})
        L.watched_levels("BANKNIFTY", Feed1m(), PRE, {**OFF, "engine3_daily_pivot_n": v})
        assert fake_v22_levels["s"][-2:] == [None, None]


@pytest.mark.parametrize("v,n", [("3", 3), (1, 1), (" 4 ", 4), (3.0, 3), ("5.0", 5), (L.DAILY_PIVOT_N_MAX, 5)])
def test_daily_pivot_n_reaches_v22_live_and_preopen(fake_v22_levels, v, n):
    s = {**OFF, "engine3_daily_pivot_n": v}
    assert L.v22_settings(s) == {"daily_pivot_n": n}
    L.compute("BANKNIFTY", Feed1m(), NOW, s)
    assert fake_v22_levels["s"][-1] == {"daily_pivot_n": n}
    L.watched_levels("BANKNIFTY", Feed1m(), PRE, s)
    assert fake_v22_levels["s"][-1] == {"daily_pivot_n": n}


def test_daily_pivot_n_combines_with_the_scale_and_the_switches(fake_v22_levels):
    s = {**OFF, "engine3_swing_k_d1": 5, "engine3_swing_k_d2": 8, "engine3_daily_pivot_n": "3", "engine3_div_degree_rule": "all"}
    want = {"swing_k": {1: 5.0, 2: 8.0}, "daily_pivot_n": 3, "div_degree_rule": "all"}
    L.compute("BANKNIFTY", Feed1m(), NOW, s)
    assert fake_v22_levels["s"][-1] == want
    L.watched_levels("BANKNIFTY", Feed1m(), PRE, s)
    assert fake_v22_levels["s"][-1] == want


@pytest.mark.parametrize("bad", [0, -1, "0", "2.5", 2.5, "abc", "nan", "inf", True, [3], 6, "10", 1000, "1e3"])
def test_daily_pivot_n_bad_values_are_refused(bad):
    """Bounded to the registered range (1/2/3, at most 5): a huge N would leave the Daily trend unknown and silently stop entries."""
    assert L.DAILY_PIVOT_N_MAX == 5
    with pytest.raises(ValueError, match="engine3_daily_pivot_n"):
        L.daily_pivot_n({"engine3_daily_pivot_n": bad})
    with pytest.raises(L.SettingError, match="engine3_daily_pivot_n"):   # the engine path: a setting error (not a data problem)
        L.v22_settings({"engine3_daily_pivot_n": bad})


def test_daily_pivot_n_reaches_the_daily_structure_and_its_cache_key():
    """V22 hands its settings to the Daily fold (L1-c: same as the scale) and the live fold cache keys on them — a changed N never reuses
    a fold made with another N."""
    import inspect

    import pandas as pd

    from decision3 import engine as E3
    from decision3 import settings as S3
    assert "DD.fold(self.daily_df, self.s)" in inspect.getsource(E3.V22.__init__)
    df = pd.DataFrame({"timestamp": pd.date_range("2030-01-01", periods=3), "close": [1.0, 2.0, 3.0]})
    assert L._fold_key(df, S3.load(None)) == L._fold_key(df, S3.load({"daily_pivot_n": 2}))
    assert L._fold_key(df, S3.load(None)) != L._fold_key(df, S3.load({"daily_pivot_n": 3}))


# ------------------------------------------------------------------------------------------------ dashboard parsing
def test_dashboard_switch_choice_and_labels():
    for key, (_v, allowed, _l) in L.METHOD_SWITCHES.items():
        assert L.switch_choice(key, None) == L.switch_choice(key, "") == L.switch_choice(key, "  ") == (allowed[0], None)
        for v in allowed:
            assert L.switch_choice(key, f" {v.upper()} ") == (v, None)
        shown, warn = L.switch_choice(key, "bogus")
        assert shown == allowed[0] and "unknown" in warn and key in warn
        assert L.switch_label(key, allowed[0]) == f"{allowed[0]} — method (default)"
        assert all(L.switch_label(key, v) == f"legacy what-if: {v}" for v in allowed[1:])


def test_dashboard_switches_to_save():
    empty = {k: "" for k in L.METHOD_SWITCHES}
    assert L.switches_to_save({}) == L.switches_to_save(None) == (empty, None)
    method = {k: a[0] for k, (_v, a, _l) in L.METHOD_SWITCHES.items()}
    assert L.switches_to_save(method) == (empty, None)                    # the method is stored as empty (today's default)
    assert L.switches_to_save({"engine3_line_rule": "bogus"}) == (empty, None)
    got, err = L.switches_to_save({"engine3_line_rule": "SIGMA", "engine3_div_degree_rule": "all", "engine3_verdict_rule": "score"})
    assert err is None and got == {**empty, "engine3_line_rule": "sigma", "engine3_div_degree_rule": "all", "engine3_verdict_rule": "score"}
    got, err = L.switches_to_save({"engine3_zone_visit_rule": "close_away", "engine3_commit_volume_rule": "opposite"})
    assert err is None and got == {**empty, "engine3_zone_visit_rule": "close_away", "engine3_commit_volume_rule": "opposite"}
    got, err = L.switches_to_save({"engine3_zone_visit_rule": "touch_window", "engine3_line_rule": "sigma"})   # incoherent
    assert "knows no approach leg" in err and got == {**empty, "engine3_line_rule": "sigma"}
    assert L.v22_settings(got) == {"line_rule": "sigma"}                  # what is saved always passes the engine's check


def test_dashboard_pivot_n_parsing():
    assert L.pivot_n_choice(None) == L.pivot_n_choice("") == L.pivot_n_choice("2") == (2, None)
    assert L.pivot_n_choice("3") == (3, None) and L.pivot_n_choice(4.0) == (4, None)
    n, warn = L.pivot_n_choice("abc")
    assert n == 2 and "engine3_daily_pivot_n" in warn
    assert L.pivot_n_to_save(2) == L.pivot_n_to_save("") == L.pivot_n_to_save(None) == L.pivot_n_to_save(0) == ""
    assert L.pivot_n_to_save(3) == 3 and L.pivot_n_to_save("1") == 1 and L.pivot_n_to_save(5) == 5
    n, warn = L.pivot_n_choice(9)                                         # out of range ⇒ shown as 2 with a warning, saved empty
    assert n == 2 and "1..5" in warn and L.pivot_n_to_save(9) == ""


def test_dashboard_block_uses_the_same_parsers():
    src = open(os.path.join(os.path.dirname(L.__file__), "page_bot_dynamic_sr_algo.py"), encoding="utf-8").read()
    for name in ("_L3.METHOD_SWITCHES", "_L3.switch_choice(", "_L3.switch_label(", "_L3.switches_to_save(engine3_switches)[1]", "_L3.switches_to_save(engine3_switches)[0]",
                 "_L3.pivot_n_choice(engine3_daily_pivot_n)", "_L3.pivot_n_to_save(engine3_daily_pivot_n)"):
        assert name in src, name
    assert "Advanced: method layers (legacy fallback)" in src and "Advanced: Daily swing size N (L1-c)" in src
    assert "Charts / replay नेहमी method वरच" in src and "charts / replay 2 वरच" in src
    assert "max_value=_L3.DAILY_PIVOT_N_MAX" in src and "Daily आणि Weekly (पालक) दोन्ही pivots बदलतात" in src
    for k in L.METHOD_SWITCHES:                                           # a one-line caption per switch
        assert f'"{k}": "Layer' in src


def _srv2_page_app():
    import builtins
    from unittest.mock import patch

    import streamlit as st

    import cloud_db
    import page_bot_dynamic_sr_algo as page
    real = cloud_db.get_strategy_settings

    def stored(strategy_name, symbol):
        return {**real(strategy_name, symbol), **builtins._SW_STORED}
    st.session_state.setdefault("symbol", "NIFTY")
    st.session_state.setdefault("token_input", "")
    st.session_state.setdefault("product_type", "D")
    st.session_state.setdefault("bdsr_strategy", "15m_dynamic_sr")
    with patch.object(cloud_db, "get_strategy_settings", side_effect=stored):
        page.render()


@pytest.mark.parametrize("stored,checked", [
    ({}, False),
    ({"engine3_line_rule": "sigma", "engine3_div_degree_rule": "all", "engine3_daily_pivot_n": 3}, True),
    ({"engine3_verdict_rule": "bogus", "engine3_daily_pivot_n": "abc"}, True),
])
def test_srv2_page_renders_the_switches(stored, checked):
    """The 15M SRv2 page: one control per switch (method (default) / legacy what-if labels), a bad stored value only warns."""
    import builtins

    from streamlit.testing.v1 import AppTest
    builtins._SW_STORED = stored
    at = AppTest.from_function(_srv2_page_app, default_timeout=60)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    boxes = {c.label: c.value for c in at.checkbox}
    assert boxes["Advanced: method layers (legacy fallback)"] is checked
    assert boxes["Advanced: Daily swing size N (L1-c)"] is checked
    if not checked:
        return
    sel = {s.label: s.value for s in at.selectbox}
    for key, (_v, allowed, label) in L.METHOD_SWITCHES.items():
        want = L.switch_choice(key, stored.get(key))[0]
        assert sel[f"Engine {label}"] == want
    if "engine3_line_rule" in stored:
        assert sel["Engine layer 4 lines"] == "sigma" and sel["Engine layer 5 RSI divergence"] == "all"
        assert [n.value for n in at.number_input if n.label.startswith("Engine Daily swing")] == [3]
    else:
        warns = " ".join(w.value for w in at.warning)
        assert "engine3_verdict_rule: stored 'bogus' unknown" in warns and "engine3_daily_pivot_n = 'abc'" in warns
