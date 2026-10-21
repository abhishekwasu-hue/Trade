"""Abhi (live switches): each finished Chart Reader layer is switchable from the dashboard (advanced, 15M SRv2 engine block) — the method
(default, empty) or its existing legacy what-if — without a deploy. No network.

  • empty / the method ⇒ V22 gets no settings (today's live behaviour byte-for-byte);
  • each legacy value reaches V22 (live decision and pre-open levels), together with the layer-1 swing scale;
  • an unknown value (or a legacy visit without the legacy commitment volume) is refused with a reason, before any data fetch or
    instrument switch;
  • the switches mirror decision3's own settings (default = the method, alternatives = the registered legacy what-ifs).
"""
import os

import pytest

import engine3_live as L
import engine_signal as ES
from tests.test_engine3_1m import NOW, PRE, Feed1m, fake_v22_levels  # noqa: F401 — fixture

OFF = {"engine3_use_1m": False}
LEGACY = {"engine3_zone_visit_rule": ("close_away", "touch_window"), "engine3_commit_volume_rule": ("opposite",),
          "engine3_line_rule": ("sigma",), "engine3_verdict_rule": ("score",)}


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


def test_cloud_db_defaults_and_engine3_settings_pass_the_switches():
    import cloud_db
    d = cloud_db.STRATEGY_SETTINGS_DEFAULTS[ES.ENGINE3_SETTINGS_KEY]
    assert all(d[k] == "" for k in L.METHOD_SWITCHES)                     # empty = the method
    got = ES.engine3_settings("nifty", lambda k, s: {"engine3_verdict_rule": "score", "verdict_rule": "score", "lots": 1})
    assert got == {"engine3_verdict_rule": "score"}


def test_dashboard_block_uses_the_same_switch_table():
    src = open(os.path.join(os.path.dirname(L.__file__), "page_bot_dynamic_sr_algo.py"), encoding="utf-8").read()
    assert "_L3.METHOD_SWITCHES" in src and "_L3.method_switches(engine3_switches)" in src
    assert "Advanced: method layers (legacy fallback)" in src
    for k in L.METHOD_SWITCHES:                                           # a one-line caption per switch
        assert f'"{k}": "Layer' in src
