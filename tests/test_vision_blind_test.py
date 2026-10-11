"""Vision blind test (Abhi 2026-10-09): decision bar नंतरचा data नाही, खुणांच्या किंमती खऱ्या OHLC वरून, निर्णय नियम (gates 5/6/9/10/12 + entry 09:30; Abhi 2026-10-09),
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


@pytest.mark.parametrize("n,blocks", [(5, True), (6, True), (9, True), (10, True), (12, True),
                                      (1, False), (4, False), (7, False), (8, False), (11, False)])
def test_gating_items_block_trade(m1, n, blocks):
    fr, _ = BT.frames(m1, pd.Timestamp("2026-09-23 13:00"))
    v = _v(fr, fail=n)
    v["decision"]["target"] = {"tf": "15M", "time": BT.fmt_time(fr["15M"]["timestamp"].iloc[-1], "15M"), "field": "close"}
    r = BT.resolve(v, fr)
    assert (n in r["gate_fail"]) == blocks
    assert r["first_fail"] == (n if blocks else None)                           # "पहिला ✘" फक्त gate मुद्द्यांतून
    if blocks:
        assert not r["trade"] and r["outcome"] == "no_trade"


def test_gates_are_exactly_abhis_list():
    assert BT.GATING == (5, 6, 9, 10, 12) and BT.ENTRY_START == "09:30"


@pytest.mark.parametrize("state,outcome", [("final_leg_in_progress", "wait"), ("forming", "no_trade"), (None, "no_trade")])
def test_wait_is_separate_from_no_trade(m1, state, outcome):
    fr, _ = BT.frames(m1, pd.Timestamp("2026-09-23 13:00"))
    v = _v(fr, fail=6)
    v["pattern"]["state"] = state
    r = BT.resolve(v, fr)
    assert not r["trade"] and r["outcome"] == outcome
    cap = BT.caption(1, 9, pd.Timestamp("2026-09-23 13:00"), v, r)
    assert ("थांबा" in cap) == (outcome == "wait") and ("trade नाही" in cap) == (outcome == "no_trade")


def test_decision_bar_before_entry_start_blocks(m1):
    fr, _ = BT.frames(m1, pd.Timestamp("2026-09-23 09:15"))
    r = BT.resolve(_v(fr), fr)
    assert "entry_start" in r["gate_fail"] and r["first_fail"] == "entry_start" and not r["trade"]
    cap = BT.caption(1, 9, pd.Timestamp("2026-09-23 09:15"), _v(fr), r)
    assert "09:30 आधी" in cap and "entry_start" not in cap
    fr2, _ = BT.frames(m1, pd.Timestamp("2026-09-23 09:30"))
    assert "entry_start" not in BT.resolve(_v(fr2), fr2)["gate_fail"]


def test_impulse_prices_from_ohlc_and_missing_impulse_listed(m1):
    fr, _ = BT.frames(m1, pd.Timestamp("2026-09-23 13:00"))
    v = _v(fr)
    t0, t1 = (BT.fmt_time(fr["1H"]["timestamp"].iloc[i], "1H") for i in (-30, -20))
    v["impulse"] = {"origin": {"tf": "1H", "time": t0, "field": "high"}, "end": {"tf": "1H", "time": t1, "field": "low"}}
    r = BT.resolve(v, fr)
    assert r["impulse"]["origin"]["price"] == round(float(fr["1H"]["high"].iloc[-30]), 2)
    assert r["impulse"]["end"]["price"] == round(float(fr["1H"]["low"].iloc[-20]), 2) and not r["bad_refs"]
    v["impulse"]["end"]["time"] = "2030-01-01 09:15"
    assert any("impulse end" in b for b in BT.resolve(v, fr)["bad_refs"])
    assert BT.figure(fr["1H"], "1H", "t", r) is not None
    assert {"impulse", "trendlines", "trendline_note"} <= set(BT.SCHEMA["required"])
    assert BT.SCHEMA["properties"]["pattern"]["properties"]["state"]["enum"] == list(BT.PATTERN_STATES)


def test_window_starts_before_impulse_origin(m1, monkeypatch):
    """Abhi 2026-10-09: 1H / 15M मध्ये impulse origin (आधीच्या swing पासून) आणि शेवट दिसायला हवा."""
    start = pd.Timestamp("2026-09-11 10:15")
    monkeypatch.setattr(BT, "window_from", lambda cut, asof: (start, "x"))
    fr, _, w = BT.frames(m1, pd.Timestamp("2026-09-23 13:00"), with_window=True)
    assert w["from"] == str(start) and w["origin_cut"] == []
    for tf in ("1H", "15M"):
        ts = pd.to_datetime(fr[tf]["timestamp"])
        assert ts.iloc[0] <= start and ts.iloc[-1] == ts.max()
        assert len(fr[tf]) <= BT.MAX_BARS[tf]
    monkeypatch.setattr(BT, "window_from", lambda cut, asof: (pd.Timestamp("2026-08-03 10:15"), "x"))
    _, _, w2 = BT.frames(m1, pd.Timestamp("2026-09-23 13:00"), with_window=True)
    assert w2["origin_cut"] == ["15M"] and "दिसत नाही" in w2["note"]           # कापलं तर लपवत नाही
    monkeypatch.setattr(BT, "window_from", lambda cut, asof: (None, "x"))
    fr2, _ = BT.frames(m1, pd.Timestamp("2026-09-23 13:00"))
    assert len(fr2["15M"]) == BT.BARS["15M"]


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


def test_duplicate_gating_item_blocks_and_entry_is_decision_close(m1):
    fr, _ = BT.frames(m1, pd.Timestamp("2026-09-23 13:00"))
    v = _v(fr)
    v["checklist"].append({"n": 5, "status": "✔", "evidence": "", "bar_times": []})          # 5 दोनदा ⇒ ग्राह्य नाही
    r = BT.resolve(v, fr)
    assert 5 in r["gate_fail"] and not r["trade"]
    v2 = _v(fr)
    v2["decision"]["entry"] = {"tf": "15M", "time": BT.fmt_time(fr["15M"]["timestamp"].iloc[-10], "15M"), "field": "high"}
    r2 = BT.resolve(v2, fr)
    assert r2["entry"] == round(float(fr["15M"]["close"].iloc[-1]), 2) and any("decision entry" in b for b in r2["bad_refs"])


def test_measurable_drops_test_and_vision_test():
    rv = {"a": {"item_type": "day"}, "b": {"item_type": "test"}, "c": {"item_type": "vision_test"}, "d": {"item_type": "trade"}}
    assert set(BS.measurable(rv)) == {"a", "d"}
    import page_backtest_review as PG
    idx = {"days": [{"item_id": "b", "trades": []}, {"item_id": "a", "trades": []}]}
    assert [d["item_id"] for d in PG.filter_days(idx, {"b": {"verdict": "WRONG", "item_type": "test"}}, "फक्त ✘")] == []
    import research.review_report as RR
    md = RR.review_md([{"days": [{"item_id": "b", "trades": []}]}], {"b": {"verdict": "WRONG", "item_type": "test", "reason": "x"}})
    assert "तपासले 0/1" in md


def test_album_with_same_chart_twice_is_refused(tmp_path):
    """केस 3 bug (map4): album मध्ये Weekly दोनदा ⇒ पाठवायच्या आधीच थांबवा."""
    import json
    from PIL import Image
    for name, col in (("w.png", "red"), ("d.png", "blue"), ("h.png", "green")):
        Image.new("RGB", (8, 8), col).save(tmp_path / name)
    (tmp_path / "w2.png").write_bytes((tmp_path / "w.png").read_bytes())
    base = {"title": "T", "run_id": "vision_test/x"}
    item = lambda files: {"n": 1, "item": "vision_test/x|case:1", "date": "2026-09-22", "reading": "r", "files": files}  # noqa: E731
    (tmp_path / "manifest.json").write_text(json.dumps({**base, "items": [item(["w.png", "d.png", "h.png"])]}))
    assert RT.load_manifest(str(tmp_path))
    for files in (["w.png", "d.png", "w.png"], ["w.png", "d.png", "w2.png"]):
        (tmp_path / "manifest.json").write_text(json.dumps({**base, "items": [item(files)]}))
        with pytest.raises(ValueError, match="दोनदा"):
            RT.load_manifest(str(tmp_path))
    assert RT._kind(b"\xff\xd8\xff\xe0x") == ("jpg", "image/jpeg") and RT._kind(b"\x89PNG") == ("png", "image/png")


def test_case_without_decision_bar_is_not_run(m1, tmp_path):
    """data decision दिवसाआधी संपला ⇒ चुकीच्या वेळेचा chart / call नाही (9 Oct केस, जुना CSV)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("vbt", __import__("os").path.join(
        __import__("os").path.dirname(__file__), "..", "scripts", "vision_blind_test.py"))
    VB = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(VB)
    late = pd.Timestamp(m1["timestamp"].max()) + pd.Timedelta(days=3)
    rec = VB.run_case(1, late.normalize() + pd.Timedelta(hours=14, minutes=30), m1, str(tmp_path), "m", None, {}, dry_run=True,
                      log=lambda *a: None)
    assert rec["status"] == "NO_DATA" and not (tmp_path / f"{late:%Y-%m-%d}_1430" / "input_15M.png").exists()
    ok = VB.run_case(1, pd.Timestamp("2026-09-23 13:00"), m1, str(tmp_path), "m", None, {}, dry_run=True, log=lambda *a: None)
    assert ok["status"] == "DRY_RUN"


def test_each_chart_has_big_tf_badge_and_album_sends_files_in_manifest_order(m1, tmp_path):
    """Album bug (Abhi 2026-10-09, केस 3 "Weekly दोनदा"): files वेगळ्या होत्या; thumbnails मध्ये W / D सारखे दिसले. आता (1) प्रत्येक chart च्या
    मध्यात मोठी TF खूण, (2) album मध्ये manifest च्याच क्रमाने, प्रत्येक file एकदाच जाते — दोन्ही इथे तपासले."""
    import json
    fr, _ = BT.frames(m1, pd.Timestamp("2026-09-23 13:00"))
    run = tmp_path / "run"
    (run / "c").mkdir(parents=True)
    files = []
    for tf in ("1H", "15M", "W", "D"):
        fig = BT.figure(fr[tf], tf, f"t {tf}")
        assert any(a.text == BT.TF_NAME[tf] and a.font.size >= 100 for a in fig.layout.annotations)
        (run / "c" / f"{tf}.png").write_bytes(BT.png(fig))
        files.append(f"c/{tf}.png")
    (run / "manifest.json").write_text(json.dumps({"run_id": "vt", "title": "T", "items": [
        {"n": 1, "date": "d", "item": "vt|case:1", "reading": "r", "caption": "🧪 x", "kind": "vision_test", "files": files}]}))
    sent = []

    def call(method, data=None, files=None, timeout=60):
        media = json.loads(data["media"])
        sent.append([files[m["media"].split("://")[1]][1] for m in media])
        return {"ok": True, "result": [{"message_id": i} for i in range(len(media))]}
    out = RT.send_run(str(run), call=call, creds=lambda: ("t", "c"), sent=str(tmp_path / "s.json"), sleep=lambda s: None)
    assert out["sent"] == 1 and len(sent) == 1
    assert sent[0] == [(run / f).read_bytes() for f in files]                     # क्रम तोच, प्रत्येक एकदाच
    assert len({hash(b) for b in sent[0]}) == 4


def test_wait_only_when_six_is_the_only_failed_gate(m1):
    fr, _ = BT.frames(m1, pd.Timestamp("2026-09-23 13:00"))
    v = _v(fr, fail=6)
    v["pattern"]["state"] = "final_leg_in_progress"
    for c in v["checklist"]:
        if c["n"] == 5:
            c["status"] = "✘"
    assert BT.resolve(v, fr)["outcome"] == "no_trade"                               # pattern सुद्धा ✘ ⇒ थांबा नव्हे
    v2 = _v(fr)
    v2["checklist"] = [c for c in v2["checklist"] if c["n"] != 6]
    v2["pattern"]["state"] = "final_leg_in_progress"
    assert BT.resolve(v2, fr)["outcome"] == "no_trade"                              # 6 गहाळ ⇒ थांबा नव्हे


def test_unpriced_model_refused_and_daily_impulse_not_on_intraday(tmp_path):
    import importlib.util
    import os
    spec = importlib.util.spec_from_file_location("vbt2", os.path.join(os.path.dirname(__file__), "..", "scripts", "vision_blind_test.py"))
    VB = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(VB)
    cases = tmp_path / "c.json"
    cases.write_text("[]")
    assert VB.main(["--out-dir", str(tmp_path), "--cases", str(cases), "--model", "claude-opus-5"]) == 1
    r = {"labels": [], "trendlines": [], "areas": [], "impulse": {"origin": {"tf": "D"}, "end": {"tf": "D"}}}
    assert VB.marks_for(r, ("1H", "15M"))["impulse"] == {} and VB.marks_for(r, ("W", "D"), areas_all=False)["impulse"]
