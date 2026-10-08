"""Vision-led टप्पा 0 (V-L0): candidates (सैल नियम), vision_led_v1 request/parse, code validation (ohlc_ref, R:R, नियम), hindsight, charts,
Telegram निवड, आणि fake client सह पूर्ण नमुना run (API / Telegram नाही)."""
import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from chart_reader import settings as CS
from vision_led import candidates as CA
from vision_led import charts as CH
from vision_led import prompt as PR
from vision_led import validate as VA

S = CS.load()


def _rs():
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "research"))
    import vision_led_sample
    return vision_led_sample


def bars15(closes, start="2026-09-28 09:15", wick=2.0):
    c = np.asarray(closes, float)
    o = np.r_[c[0], c[:-1]]
    ts, t = [], pd.Timestamp(start)
    while len(ts) < len(c):                                              # 09:15–15:15 sessions, weekdays
        if t.weekday() < 5 and pd.Timestamp("09:15").time() <= t.time() <= pd.Timestamp("15:15").time():
            ts.append(t)
        t += pd.Timedelta(minutes=15)
        if t.time() > pd.Timestamp("15:15").time():
            t = (t + pd.Timedelta(days=1)).normalize() + pd.Timedelta(hours=9, minutes=15)
    df = pd.DataFrame({"timestamp": ts, "open": o, "high": np.maximum(o, c) + wick, "low": np.minimum(o, c) - wick, "close": c})
    df["bar_end"] = df["timestamp"] + pd.Timedelta(minutes=15)
    return df


# ------------------------------------------------------------------------------------------------ candidates
def test_rejection_mark_wick_or_close_location():
    assert CA.rejection(100, 101, 95, 100.5, 1, CA.DEFAULTS)[0]                       # lower wick ≥ 0.4 (bull)
    assert CA.rejection(100, 104, 99.8, 103.8, 1, CA.DEFAULTS)[0]                     # CL ≥ 0.6
    assert not CA.rejection(103, 104, 96, 97, 1, CA.DEFAULTS)[0]
    assert CA.rejection(100, 106, 99, 99.5, -1, CA.DEFAULTS)[0]                       # bear: upper wick


def test_impulse_from_market_state():
    """F1: candidates चा impulse market_state मधून (ad-hoc finder नाही); origin तुटलेला / correction नसेल ⇒ None."""
    t = bars15(list(np.linspace(100, 160, 30)) + list(np.linspace(160, 140, 8)))
    ms = {"impulse": {"dir": 1, "from": 100.0, "to": 160.0, "from_ts": t["timestamp"].iloc[0], "to_ts": t["timestamp"].iloc[29],
                      "size_mr": 12.0},
          "correction": {"status": "correction", "retrace": 0.4, "extreme": 136.0, "labels": [{"label": "A"}]},
          "side": "bull_put", "side_reasons": []}
    imp = CA.impulse_from_state(ms, t)
    assert imp["side"] == 1 and imp["e_bar"] == 29 and imp["retrace"] == 0.4 and imp["state_side"] == "bull_put"
    assert CA.impulse_from_state({**ms, "correction": {"status": "origin_broken"}}, t) is None
    assert CA.impulse_from_state({**ms, "impulse": None}, t) is None


def test_near_areas_trade_side_only():
    bar = pd.Series({"open": 101.0, "high": 102.0, "low": 99.5, "close": 101.5})
    zs = [{"id": "S", "low": 98.0, "high": 99.0, "state": "ACTIVE"}, {"id": "R", "low": 103.0, "high": 104.0, "state": "ACTIVE"},
          {"id": "FAR", "low": 90.0, "high": 91.0, "state": "ACTIVE"}]
    assert [z["id"] for z in CA.near_areas(bar, zs, 1, 2.0, CA.DEFAULTS)] == ["S"]
    assert [z["id"] for z in CA.near_areas(bar, zs, -1, 2.0, CA.DEFAULTS)] == ["R"]


# ------------------------------------------------------------------------------------------------ prompt
def test_request_temperature_zero_without_thinking_and_schema():
    p = PR.build_request(b"png", "txt", "m")
    assert p["temperature"] == 0.0 and p["system"][0]["cache_control"] and p["output_config"]["format"]["schema"] is PR.SCHEMA
    assert "temperature" not in PR.build_request(b"png", "txt", "m", thinking="enabled")
    with pytest.raises(ValueError):
        PR.build_request(b"png", "txt", None)
    from vision_led.playbook import PLAYBOOK
    assert len(PLAYBOOK) / 4 < 4000                                                    # ≤ 4k tokens (≈ 4 chars/token)


def msg(obj, stop="end_turn"):
    return SimpleNamespace(stop_reason=stop, content=[SimpleNamespace(type="text", text=json.dumps(obj))],
                           usage=SimpleNamespace(input_tokens=9000, output_tokens=900, cache_read_input_tokens=0, cache_creation_input_tokens=0))


def test_parse_missing_field_and_stop_reason():
    d, err, u = PR.parse(msg({"trade": False}))
    assert d is None and "field" in err and u["input_tokens"] == 9000
    assert PR.parse(msg({}, stop="max_tokens"))[1].startswith("stop_reason")


# ------------------------------------------------------------------------------------------------ validation
def _setup_validation():
    t = bars15([100 + i for i in range(30)] + [129 - 0.5 * i for i in range(10)], wick=1.0)
    j = len(t) - 1
    h1 = t.iloc[::4].reset_index(drop=True)
    area = {"id": "A1", "low": 120.0, "high": 121.0, "role": "SUPPORT", "kind": "solid", "tool": "a", "state": "ACTIVE"}
    cand = {"mr": 2.0, "bar_end": t["bar_end"].iloc[j], "bar_start": t["timestamp"].iloc[j], "side": 1, "all_areas": [area]}
    return t, h1, j, cand


def ref(t, i, f):
    return {"price": float(t[f].iloc[i]), "ohlc_ref": f"{pd.Timestamp(t['timestamp'].iloc[i]):%Y-%m-%d %H:%M} {f}"}


def test_validation_refs_rr_and_buffer():
    t, h1, j, cand = _setup_validation()
    v = {"trade": True, "side": "bull_put", "grade": "A", "area_id": "A1", "entry": ref(t, j, "close"), "invalidation": ref(t, j, "low"),
         "target": ref(t, 29, "high")}
    r = VA.validate(v, cand, [t, h1], cand["bar_start"], None, t, S)
    assert r["inv"] == pytest.approx(t["low"].iloc[j] - 0.25 * 2.0)                    # buffer पलीकडे
    assert r["rr"] == pytest.approx((t["high"].iloc[29] - t["close"].iloc[j]) / (t["close"].iloc[j] - r["inv"]), rel=1e-3)
    bad = {**v, "entry": {"price": float(t["close"].iloc[j]) + 5, "ohlc_ref": v["entry"]["ohlc_ref"]}}
    r2 = VA.validate(bad, cand, [t, h1], cand["bar_start"], None, t, S)
    assert r2["status"] == "REJECTED" and "≠ OHLC" in r2["reasons"][0]
    prev = {**v, "entry": ref(t, j - 1, "close")}
    assert any("decision bar" in x for x in VA.validate(prev, cand, [t, h1], cand["bar_start"], None, t, S)["reasons"])
    assert VA.validate({**v, "trade": False}, cand, [t, h1], cand["bar_start"], None, t, S)["status"] == "NO_TRADE"
    assert any("area_id" in x for x in VA.validate({**v, "area_id": "ZZ"}, cand, [t, h1], cand["bar_start"], None, t, S)["reasons"])
    wrong = {**v, "side": "bear_call"}
    assert "विसंगत" in VA.validate(wrong, cand, [t, h1], cand["bar_start"], None, t, S)["reasons"][0]
    assert VA.ref_value("7 Oct high", [t])[0] is None


def test_strike_info_beyond_invalidation_and_sigma():
    closes = 22000 * np.exp(np.cumsum(np.r_[0, np.full(25, 0.008) * np.resize([1, -1], 25)]))
    k = VA.strike_info(-1, 22680.0, 22740.0, 20.0, closes, pd.Timestamp("2026-10-07 14:45"), VA.DEFAULTS)
    assert k["strike"] > 22740 and k["strike"] % 50 == 0 and k["dte"] == 6                # बुधवार ⇒ पुढचा मंगळवार


def test_hindsight_target_sl_open_and_same_bar_is_sl():
    f = pd.DataFrame({"timestamp": pd.date_range("2026-10-08 09:15", periods=3, freq="15min"), "open": [100] * 3, "high": [101, 103, 104],
                      "low": [99, 98, 97], "close": [100, 101, 102]})
    assert VA.hindsight(f, 1, 100, 95, 103)["result"] == "TARGET"
    assert VA.hindsight(f, 1, 100, 98, 110)["result"] == "SL"
    assert VA.hindsight(f, 1, 100, 90, 110)["result"] == "OPEN"
    r = VA.hindsight(f, 1, 100, 98, 103)
    assert r["result"] == "SL" and r["both_same_bar"]


# ------------------------------------------------------------------------------------------------ charts / telegram
def test_label_spread_keeps_min_gap():
    ys = CH.spread([100.0, 100.2, 100.4, 110.0], span=100.0, min_frac=0.03)
    srt = sorted(ys)
    assert all(b - a >= 3.0 - 1e-9 for a, b in zip(srt, srt[1:])) and ys[3] == 110.0


def test_annotated_rejected_has_no_lines_and_ok_has_labels():
    t, h1, j, cand = _setup_validation()
    fig = CH.annotated_figure(t, {"status": "REJECTED", "reasons": ["R:R 1:1.2 < 1:3"]}, cand, "x")
    assert not fig.layout.shapes and any("REJECTED" in a.text for a in fig.layout.annotations)
    ok = {"status": "OK", "side": 1, "entry": 129.5, "inv": 120.0, "target": 160.0, "rr": 3.3, "grade": "A", "area": cand["all_areas"][0],
          "strike": {"strike": 115}}
    fig = CH.annotated_figure(t, ok, cand, "x")
    texts = " ".join(a.text for a in fig.layout.annotations)
    assert "ENTRY" in texts and "SL" in texts and "TARGET" in texts and "R:R 1:3.3" in texts and "short strike" in texts


def test_pick_for_telegram_caps_and_prioritises_ab():
    RS = _rs()
    recs = [{"bar_start": f"2026-10-0{1 + i % 9} 10:00", "result": {"status": "OK" if i < 3 else "REJECTED"}, "vision": {"grade": "A" if i < 3 else "C"}}
            for i in range(25)]
    chosen, rest = RS.pick_for_telegram(recs, cap=20)
    assert len(chosen) == 20 and len(rest) == 5 and sum((r["vision"]["grade"] == "A") for r in chosen) == 3
    assert RS.pick_for_telegram(recs[:5], cap=20) == (recs[:5], [])


# ------------------------------------------------------------------------------------------------ run (fake client, no API / Telegram)
def test_run_with_fake_client_budget_and_caption(tmp_path, monkeypatch):
    RS = _rs()
    t, h1, j, cand = _setup_validation()
    cands = [dict(cand, j=j, impulse={"s_px": 100.0, "e_px": 129.0, "size_mr": 14.5, "retrace": 0.4}, wick=0.5, cl=0.7, areas=cand["all_areas"])]
    monkeypatch.setattr(RS.CA, "scan", lambda *a, **k: cands)
    monkeypatch.setattr(RS.EV, "frame", lambda m1, tf, asof: t if tf == "15m" else h1)
    monkeypatch.setattr(RS.EV, "evaluate", lambda *a, **k: {"grade": "C", "total": 20, "story": ["s"], "lines": ["l"], "why_no_entry": ["x"]})
    monkeypatch.setattr(RS.CH, "png", lambda fig: b"png")
    m1 = pd.DataFrame({"timestamp": pd.date_range("2026-09-28 09:15", periods=10, freq="min"), "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
    v = {"trade": True, "side": "bull_put", "grade": "A", "setup_type": "G6", "area_id": "A1", "story": ["one", "two"], "entry": ref(t, j, "close"),
         "invalidation": ref(t, j, "low"), "invalidation_reason": "below the support area", "target": ref(t, 29, "high"),
         "evidence_for": [], "evidence_against": [], "wrong_if": "below 120"}
    seen = []
    client = SimpleNamespace(messages=SimpleNamespace(create=lambda **p: seen.append(p) or msg(v)))
    sent = []
    summary, recs = RS.run(m1, "claude-sonnet-test", client, str(tmp_path), 1.50, start="2026-09-01", end="2026-12-01",
                           send=lambda p, c: sent.append((p, c)) or True)
    assert summary["calls"] == 1 and summary["cost_usd"] > 0 and recs[0]["vision"]["grade"] == "A"
    imgs, cap = sent[0]
    assert len(imgs) == 2 and cap.startswith("🧪 SAMPLE — trade नाही") and "code side bull_put" in cap and "vision side bull_put" in cap
    text = seen[0]["messages"][0]["content"][-1]["text"]
    # anchoring नाही: code ची बाजू / grade / narrative vision ला नाही
    assert "implied side" not in text and "code grade" not in text.lower() and "code reading" not in text.lower()
    # no-lookahead: OHLC तक्त्यातली कुठलीही वेळ decision bar पलीकडे नाही
    import re
    times = [pd.Timestamp(x) for x in re.findall(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}),", text, re.M)]
    assert times and max(times) <= pd.Timestamp(cand["bar_start"])
    assert (tmp_path / "vision_led_sample.json").exists()
    s2, r2 = RS.run(m1, "claude-sonnet-test", client, str(tmp_path / "b"), 0.001, start="2026-09-01", end="2026-12-01")
    assert s2["calls"] == 0 and s2["stopped"] and r2[0]["status"] == "NOT_RUN_BUDGET"
    md = RS.report_md(summary, recs, "claude-sonnet-test")
    assert "V-L0" in md and "7 Oct golden" in md


def test_assert_no_lookahead_catches_future_bars():
    RS = _rs()
    t, h1, j, cand = _setup_validation()
    RS.assert_no_lookahead(cand, t, h1, t)
    with pytest.raises(AssertionError):
        RS.assert_no_lookahead({**cand, "bar_start": t["timestamp"].iloc[j - 1], "bar_end": t["bar_end"].iloc[j - 1]}, t, h1.iloc[:0], t.iloc[:0])
    late = h1.copy()
    late.loc[late.index[-1], "bar_end"] = cand["bar_end"] + pd.Timedelta(hours=1)
    with pytest.raises(AssertionError):
        RS.assert_no_lookahead(cand, t, late, t.iloc[:0])


def test_send_album_two_images_one_message():
    from vision_led import telegram as VT
    calls = []
    fake = lambda method, data=None, files=None, timeout=20: calls.append((method, data, files)) or {"ok": True}   # noqa: E731
    assert VT.send_album([b"a", b"b"], "cap", call=fake, chat_id="1")
    m, d, f = calls[-1]
    assert m == "sendMediaGroup" and len(f) == 2 and json.loads(d["media"])[0]["caption"] == "cap"
    assert VT.send_album([b"a", None], "cap", call=fake, chat_id="1") and calls[-1][0] == "sendPhoto"
    assert VT.send_album([], "only text", call=fake, chat_id="1") and calls[-1][0] == "sendMessage"


def test_report_table_columns_and_golden_section():
    RS = _rs()
    recs = [{"bar_start": "2026-10-07 14:00:00", "side": 1, "status": "OK", "vision": {"trade": True, "side": "bear_call", "grade": "A", "story": ["abc"]},
             "result": {"status": "OK", "rr": 4.5, "entry": 22680.0, "inv": 22740.0, "target": 22400.0}, "hindsight": {"result": "TARGET", "at": "2026-10-08 11:00"}}]
    summ = {"candidates": 1, "calls": 1, "cost_usd": 0.04, "stopped": None, "status": {"OK": 1}, "ab_ok": 1, "hindsight": {"TARGET": 1},
            "telegram_sent": 1, "golden": RS.golden_check(recs)}
    md = RS.report_md(summ, recs, "m")
    assert "| candidate | code side | vision side / grade | validation | R:R vision SL | R:R candle SL | R:R structural SL | hindsight |" in md
    assert "| 2026-10-07 14:00 | bull_put | bear_call / A | OK | 4.5 | — | — | TARGET" in md
    recs[0].update(code_side="bear_call", result=dict(recs[0]["result"], sl_defs={"candle": {"inv": 22652.0, "rr": 7.0},
                                                                                 "structural": {"inv": 22740.0, "rr": 1.8}}))
    md = RS.report_md(summ, recs, "m")
    assert "| 2026-10-07 14:00 | bear_call | bear_call / A | OK | 4.5 | 22,652 → 1:7.0 | 22,740 → 1:1.8 | TARGET" in md
    assert "## 7 Oct golden" in md and summ["golden"]["vision_bear_call"] == 1 and summ["golden"]["validated"] == 1


def test_vision_text_does_not_depend_on_code_side():
    """Anchoring नाही: code ची बाजू (+1 / −1) बदलली तरी vision ला जाणारा मजकूर तंतोतंत तोच."""
    t, h1, j, cand = _setup_validation()
    c1 = dict(cand, impulse={"s_px": 1, "e_px": 2, "size_mr": 3, "retrace": 0.5}, wick=0.4, cl=0.7)
    a = PR.user_text(dict(c1, side=1), t, h1, cand["all_areas"], ["fact"])
    b = PR.user_text(dict(c1, side=-1), t, h1, cand["all_areas"], ["fact"])
    assert a == b


def test_two_sl_definitions_7oct_like():
    """§4: reversal-candle SL (decision bar / आधीच्या bar चं high + buffer) वि. structural SL (active area / trendline पलीकडे)."""
    trig = pd.DataFrame({"timestamp": pd.date_range("2026-10-07 12:00", periods=11, freq="15min"),
                         "open": 22680.0, "high": [22717.65, 22684.8, 22675.0, 22668.7, 22629.3, 22599.4, 22604.6, 22606.8, 22578.6, 22648.8,
                                                   22646.8],
                         "low": 22550.0, "close": 22600.0})
    area = {"id": "TL", "tool": "f", "low": 22707.0, "high": 22724.0}
    sl = VA.sl_definitions(-1, 22620.3, 22400.0, trig, area, 43.0, VA.DEFAULTS)
    assert sl["candle"]["ref"] == 22648.8 and abs(sl["candle"]["inv"] - (22648.8 + 0.25 * 43)) < 0.01
    assert sl["structural"]["ref"] == 22724.0 and 22730 < sl["structural"]["inv"] < 22740
    assert sl["candle"]["rr"] > 5 and sl["structural"]["rr"] < 2.2
    assert VA.sl_definitions(-1, 22620.3, 22400.0, trig, None, 43.0, VA.DEFAULTS)["structural"] is None
