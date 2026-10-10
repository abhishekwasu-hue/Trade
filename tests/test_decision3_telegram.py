"""थर v2.2 पायरी D — Telegram trader view: manifest backtest_review format मध्ये वैध (item मध्ये run id, kind store मध्ये मान्य),
caption 5–7 ओळी + शेवटी disclaimer, chart files (font मध्ये नसलेला glyph नाही), B1 / B2 दिशा (merged signal-bar सकट), debug वेगळा."""
import json
import os

import numpy as np
import pytest

from backtest_review import store as BS
from backtest_review import telegram as RT
from decision3 import charts as CH
from decision3 import engine as E3
from decision3 import method as M
from decision3 import telegram_view as TV
from tests.test_decision3_method import _abc_m15


def _V_rows():
    V = E3.V22(_abc_m15())
    return V, V.run()


@pytest.mark.filterwarnings("error:Glyph:UserWarning")                         # chart वर font मध्ये नसलेला glyph (emoji / मराठी) नाही
def test_build_run_manifest_valid_and_captions(tmp_path):
    V, rows = _V_rows()
    man = TV.build_run(V, rows, str(tmp_path), "NIFTY", "t1", moments=[rows[300]["ts"][:10]])
    assert man and len(man["items"]) >= 2                                        # setup + खुणेचा दिवस
    m = RT.load_manifest(str(tmp_path))                                          # sender चीच तपासणी
    for it in m["items"]:
        cap = RT.caption(m, it)
        lines = cap.splitlines()
        assert cap == it["caption"] and 5 <= len(lines) <= 7 and lines[-1].startswith("Shadow / PAPER")
        assert it["item"].startswith("t1|v22:NIFTY:") and it["kind"] in BS.KINDS and it["kind"] in BS.NOT_MEASURED
        assert len(it["files"]) == 3 and all(os.path.getsize(os.path.join(str(tmp_path), f)) > 1000 for f in it["files"])
    dbg = json.load(open(os.path.join(str(tmp_path), "debug.json"), encoding="utf-8"))
    assert len(dbg) == len(m["items"]) and "①" in dbg[0]["checklist"]


def test_caption_keeps_disclaimer_when_story_is_long():
    V, rows = _V_rows()
    r = next(x for x in rows if x["decision"] == "setup")
    long = {**r, "liquidity": {"sweeps": [{"src": "PDH", "price": 1.0, "side": "buy"}]},
            "evidence": {**(r["evidence"] or {}), "power_shift": True, "trap_sweep": True, "tl_break": True}}
    lines = TV.caption(V, long, "NIFTY").splitlines()
    assert len(lines) <= 7 and lines[-1].startswith("Shadow / PAPER")


def test_b_plans_both_directions_and_merged_signal_bar():
    rk = {"entry": 100.0, "sl": 106.0, "target": 70.0, "rr": 5.0}
    A = {"high": np.array([103.0, 101.5]), "low": np.array([98.0, 99.0])}
    S = {"entry_tick": 0.05, "min_rr": 3.0}
    one = M.b_plans(A, 1, M.DOWN, rk, 1, S)["B2"]
    two = M.b_plans(A, 1, M.DOWN, rk, 2, S)["B2"]
    assert one["trigger"] == 98.95 and two["trigger"] == 97.95                   # merged ⇒ दोन्ही bars चा low
    assert one["rr"] == round((98.95 - 70) / (106 - 98.95), 2)
    up = M.b_plans(A, 1, M.UP, {"entry": 100.0, "sl": 95.0, "target": 130.0, "rr": 6.0}, 2, S)["B2"]
    assert up["trigger"] == 103.05 and up["rr"] == round((130 - 103.05) / (103.05 - 95), 2) and up["ok"]
    assert M.b_plans(A, 1, M.DOWN, None, 1, S) is None
    assert M.b_plans(A, 1, M.DOWN, {**rk, "target": None}, 1, S) is None


def test_select_setups_and_moment_days_no_duplicates():
    _, rows = _V_rows()
    day = rows[300]["ts"][:10]
    sel = TV.select(rows, moments=[day, day])
    bars = [r["bar"] for r in sel]
    assert bars == sorted(set(bars)) and any(r["ts"][:10] == day for r in sel)
    assert all(r["decision"] == "setup" for r in sel if r["ts"][:10] != day)


def test_engine_trendline_is_grade_only_and_chart_draws_break(monkeypatch):
    """⑤ engine मार्ग: तुटलेली रेघ ⇒ tl_break True, conviction score वाढतो, decision कधीच setup ⇒ wait/no_trade होत नाही;
    अखंड रेघ ⇒ NA (score तसाच). Chart रेघ + break खूण काढतो."""
    from decision3 import trendline as TL
    V, rows = _V_rows()
    r = next(x for x in rows if x["decision"] == "setup")
    t = r["bar"]
    base = V.decide(t)
    k = V.pb.at(t, M._dir(base["daily_trend"], base["level"]["role"]))
    line = {"p1": [k["i_end_bar"], k["i_end"]], "p2": [t - 3, k["i_end"]], "slope": 0.0, "touches": 2, "value_t": k["i_end"]}
    monkeypatch.setattr(TL, "k_line", lambda *a, **kw: {**line, "broken": True, "break_bar": t - 1})
    br = V.decide(t)
    monkeypatch.setattr(TL, "k_line", lambda *a, **kw: {**line, "broken": False, "break_bar": None})
    intact = V.decide(t)
    assert br["evidence"]["tl_break"] is True and br["checklist"]["⑤"][0] is True and br["conv_score"] >= base["conv_score"]
    assert intact["evidence"]["tl_break"] is None and intact["conv_score"] == base["conv_score"]
    assert br["decision"] == intact["decision"] == base["decision"] == "setup"
    png = CH.m15_png(V, t, "NIFTY", r=br)
    assert png[:4] == b"\x89PNG"


def test_no_trade_caption_says_where_it_stopped_and_has_5_lines():
    V, rows = _V_rows()
    r = next(x for x in rows if x["daily_trend"] in ("NEUTRAL", "UNKNOWN"))
    lines = TV.caption(V, r, "NIFTY").splitlines()
    assert any(x.startswith("अडलं: ①") for x in lines) and 5 <= len(lines) <= 7 and lines[-1].startswith("Shadow / PAPER")
    assert TV.stop_reason({**r, "checklist": {**r["checklist"], "①": [True, "x"], "②": [True, "y"],
                                              "③": [True, "z"], "④": [False, "ev"], "⑥": [False, "candle नाही"]}}).startswith("⑥")


def test_caption_at_most_7_lines_for_every_row_incl_wait_with_risk():
    V, rows = _V_rows()
    assert any(r["decision"] != "setup" and r.get("risk") for r in rows)          # non-vacuous: risk असलेली wait / no_trade row आहे
    for r in rows:
        lines = TV.caption(V, r, "NIFTY").splitlines()
        assert 4 <= len(lines) <= 7 and lines[-1].startswith("Shadow / PAPER"), r["ts"]
        assert any(x.startswith("B1:") for x in lines) == (r["decision"] == "setup" and bool((r.get("risk") or {}).get("target")))
