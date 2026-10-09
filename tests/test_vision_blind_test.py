"""Vision blind test (Abhi 2026-10-09): decision bar नंतरचा data नाही, खुणांच्या किंमती खऱ्या OHLC वरून, निर्णय नियम (4/5/6/9/10/12),
caption मर्यादा, review प्रकार vision_test, चाचणी replies 'test'."""
import numpy as np
import pandas as pd
import pytest

from backtest_review import store as BS
from backtest_review import telegram as RT
from vision_led import blind_test as BT


def _m1(days=40, start="2026-08-03"):
    rows = []
    rng = np.random.default_rng(0)
    px = 24000.0
    for d in pd.bdate_range(start, periods=days):
        for t in pd.date_range(f"{d:%Y-%m-%d} 09:15", f"{d:%Y-%m-%d} 15:29", freq="1min"):
            o = px
            px += rng.normal(0, 3)
            rows.append((t, o, max(o, px) + 1, min(o, px) - 1, px))
    return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close"]).assign(volume=0.0)


@pytest.fixture(scope="module")
def m1():
    return _m1()


def test_frames_have_no_bar_after_decision_close(m1):
    dec = pd.Timestamp("2026-09-23 13:00")
    fr, asof = BT.frames(m1, dec)
    assert asof == pd.Timestamp("2026-09-23 13:15")
    for tf in BT.TFS:
        assert pd.Timestamp(fr[tf]["bar_end"].max()) <= asof
    assert fr["15M"]["timestamp"].iloc[-1] == dec                               # decision bar हा शेवटचा
    assert fr["D"]["timestamp"].iloc[-1] == pd.Timestamp("2026-09-22")          # decision दिवस (अर्धवट) नाही
    assert pd.Timestamp(fr["W"]["bar_end"].iloc[-1]).dayofweek == 4             # पूर्ण आठवडे फक्त
    fr2, _ = BT.frames(m1[m1["timestamp"] < pd.Timestamp("2026-09-23 13:15")], dec)
    for tf in BT.TFS:
        pd.testing.assert_frame_equal(fr[tf], fr2[tf])                          # नंतरचा data काढला तरी तेच


def _v(fr, side="bear", fail=None):
    t15 = BT.fmt_time(fr["15M"]["timestamp"].iloc[-1], "15M")
    t15b = BT.fmt_time(fr["15M"]["timestamp"].iloc[-10], "15M")
    t1h = BT.fmt_time(fr["1H"]["timestamp"].iloc[-5], "1H")
    ck = [{"n": n, "status": "✘" if n == fail else "✔", "evidence": "पुरावा", "bar_times": [t15]} for n in range(1, 13)]
    ref = lambda tf, t, f: {"tf": tf, "time": t, "field": f}                      # noqa: E731
    return {"trend": {"weekly": "मंदी", "daily": "मंदी", "h1": "मंदी", "m15": "correction"}, "checklist": ck,
            "pattern": {"name": "zigzag ABC", "complete": True},
            "labels": [{"text": "C", "at": ref("15M", t15b, "high")}],
            "areas": [{"name": "seller area", "a": ref("1H", t1h, "high"), "b": ref("1H", t1h, "low")}],
            "trendlines": [{"name": "C trendline", "a": ref("15M", t15b, "high"), "b": ref("15M", t15, "high")}],
            "decision": {"side": side, "entry": ref("15M", t15, "close"), "invalidation": ref("15M", t15b, "high"),
                         "target": ref("1H", t1h, "low")},
            "wrong_if": "high वर close"}


def test_prices_come_from_ohlc_and_bad_refs_listed(m1):
    fr, _ = BT.frames(m1, pd.Timestamp("2026-09-23 13:00"))
    v = _v(fr)
    r = BT.resolve(v, fr)
    assert r["entry"] == round(float(fr["15M"]["close"].iloc[-1]), 2)
    assert r["labels"][0]["price"] == round(float(fr["15M"]["high"].iloc[-10]), 2)
    v["labels"].append({"text": "X", "at": {"tf": "15M", "time": "2030-01-01 09:15", "field": "high"}})
    assert any("label X" in b for b in BT.resolve(v, fr)["bad_refs"])


@pytest.mark.parametrize("n,blocks", [(4, True), (5, True), (6, True), (9, True), (10, True), (12, True), (7, False), (11, False)])
def test_gating_items_block_trade(m1, n, blocks):
    fr, _ = BT.frames(m1, pd.Timestamp("2026-09-23 13:00"))
    v = _v(fr, fail=n)
    v["decision"]["target"] = {"tf": "15M", "time": BT.fmt_time(fr["15M"]["timestamp"].iloc[-1], "15M"), "field": "close"}
    r = BT.resolve(v, fr)
    assert (n in r["gate_fail"]) == blocks and r["first_fail"] == n
    if blocks:
        assert not r["trade"]


def test_caption_limits_and_no_code_keys(m1):
    fr, _ = BT.frames(m1, pd.Timestamp("2026-09-23 13:00"))
    v = _v(fr)
    v["pattern"]["name"] = "x" * 900
    cap = BT.caption(1, 4, pd.Timestamp("2026-09-23 13:00"), v, BT.resolve(v, fr))
    assert len(cap) <= 1024 and len(cap.splitlines()) <= 8
    assert cap.startswith("🧪 VISION TEST 1/4") and "Reply: ✔ बरोबर · ✘ कारण" in cap
    for key in ("bear_call", "bull_put", "gate_fail", "n_ok", "{", "_"):
        assert key not in cap


def test_figure_with_marks_renders(m1):
    fr, _ = BT.frames(m1, pd.Timestamp("2026-09-23 13:00"))
    r = BT.resolve(_v(fr), fr)
    fig = BT.figure(fr["15M"], "15M", "t", r)
    texts = [a.text for a in fig.layout.annotations]
    assert any("①" in t for t in texts) and any("seller area" in t for t in texts)


def test_request_has_playbook_checklist_and_no_code_opinion(m1):
    fr, _ = BT.frames(m1, pd.Timestamp("2026-09-23 13:00"))
    text = BT.user_text(pd.Timestamp("2026-09-23 13:00"), fr)
    p = BT.build_request([b"x"] * 4, text, "m")
    sys_ = p["system"][0]["text"]
    assert sys_.startswith(BT.PLAYBOOK) and "BLIND TEST CHECKLIST" in sys_ and "12 पक्के नियम" in sys_
    assert sum(1 for c in p["messages"][0]["content"] if c["type"] == "image") == 4
    for word in ("area id", "candidate", "MAP CHECK", "Abhi says", "S1", "Gray"):
        assert word not in text


def test_manifest_caption_and_vision_test_reply_kind():
    assert RT.caption({"title": "T", "items": [1]}, {"n": 1, "date": "d", "reading": "r", "caption": "🧪 x"}) == "🧪 x"
    saved = []
    msg = {"reply_to_message": {"message_id": 5}, "text": "✘ B च्या आत", "from": {"id": 1}, "chat": {"id": 1}}
    import json
    import os
    import tempfile
    p = os.path.join(tempfile.mkdtemp(), "s.json")
    json.dump({"k": {"run": "vision_test/map4", "item": "vision_test/map4|case:2026-09-22 15:00", "date": "2026-09-22",
                     "message_ids": [5], "kind": "vision_test"}}, open(p, "w"))
    ok, why = RT.handle_reply(msg, lambda f, c: True, save=lambda *a: saved.append(a) or True, sent=p)
    assert ok and saved[0][2] == "vision_test" and saved[0][3] == "WRONG" and saved[0][5] is None


def test_test_replies_selected_and_excluded_from_progress():
    rv = {"r2|day:2026-10-08": {"review_date": "2026-10-08", "verdict": "OK", "reviewed_at": "2026-10-09 07:14:10", "item_type": "day"},
          "r2|day:2026-10-07": {"review_date": "2026-10-07", "verdict": "OK", "reviewed_at": "2026-10-09 07:14:30", "item_type": "day"},
          "r2|day:2026-10-06": {"review_date": "2026-10-06", "verdict": "WRONG", "reviewed_at": "2026-10-09 07:15:00", "item_type": "day"},
          "r2|day:2026-10-05": {"review_date": "2026-10-05", "verdict": "OK", "reviewed_at": "2026-10-09 07:15:00", "item_type": "day"},
          "r2|day:2026-10-08x": {"review_date": "2026-10-08", "verdict": "OK", "reviewed_at": "2026-10-09 11:00:00", "item_type": "day"}}
    ids = BS.test_candidates(rv, ["2026-10-06", "2026-10-07", "2026-10-08"], "2026-10-09 07:00", "2026-10-09 07:30")
    assert ids == ["r2|day:2026-10-06", "r2|day:2026-10-07", "r2|day:2026-10-08"]
    idx = {"days": [{"date": "2026-10-08", "trades": []}]}
    rv2 = {"day:2026-10-08": {"verdict": "OK", "item_type": "test"}}
    assert BS.progress(idx, rv2)["days"] == (0, 1)
    with pytest.raises(ValueError):
        BS.save_review("x", "2026-10-08", "weird", "OK")


def test_wrong_side_target_is_not_a_trade(m1):
    fr, _ = BT.frames(m1, pd.Timestamp("2026-09-23 13:00"))
    v = _v(fr)
    t = BT.fmt_time(fr["15M"]["timestamp"].iloc[-1], "15M")
    v["decision"].update(entry={"tf": "15M", "time": t, "field": "low"}, invalidation={"tf": "15M", "time": t, "field": "high"},
                         target={"tf": "15M", "time": t, "field": "close"})
    hi, lo, c = (float(fr["15M"][k].iloc[-1]) for k in ("high", "low", "close"))
    r = BT.resolve(v, fr)
    assert not r["order_ok"] and not r["trade"] and "चुकीच्या बाजूला" in r["code_why"]
