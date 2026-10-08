"""Vision V2 (signal_check_v2): chart v2 संदर्भ no-lookahead, PDH / PWH आधीच्या पूर्ण दिवस / आठवड्याचे, verdict नियम (प्रत्येक disagree /
gray नियम, vision agree असला तरी), schema अवैध ⇒ unavailable ⇒ skip, v1 records वेगळे, overlay labels एकत्र, signal text मध्ये अचूक किंमती."""
import datetime as dt
import json

import numpy as np
import pandas as pd
import pytest

from tests.test_vision_v0 import GOOD, msg
from vision import chart as CH
from vision import config as VC
from vision import context as CX
from vision import signal_audit as SA
from vision import store as VS
from vision import worker as VW


def bars(days=("2026-09-28", "2026-09-29", "2026-09-30", "2026-10-01", "2026-10-05", "2026-10-06"), base=25000.0, seed=1):
    """अनेक दिवसांचे 1m bars (09:15–15:29), random walk. 2026-10-05 सोमवार ⇒ आधीचा आठवडा 28 Sep – 1 Oct."""
    rng = np.random.default_rng(seed)
    rows, p = [], base
    for d in days:
        for k in range(375):
            t = pd.Timestamp(d) + pd.Timedelta(hours=9, minutes=15 + k)
            o = p
            p = p + rng.normal(0, 4)
            rows.append((t, o, max(o, p) + abs(rng.normal(0, 2)), min(o, p) - abs(rng.normal(0, 2)), p))
    return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close"])


SIG_TS = pd.Timestamp("2026-10-06 11:01")


def sig(**k):
    return {"bot": "dynamic_sr_instant", "symbol": "NIFTY", "direction": "BULLISH", "role": "SUPPORT", "level": 24990.0, "setup_tf": "5M",
            "signal_ts": SIG_TS, "spot": 25000.0, "tags": {}, **k}


def ctx_for(df, s=None):
    s = s or sig()
    setup, higher, tfs, cut = CH.panels(df, s["signal_ts"], s["setup_tf"], return_cut=True)
    return CX.build(cut, setup, s)


# ------------------------------------------------------------------------------------------------ no-lookahead
def test_context_is_causal_future_spike_changes_nothing():
    df = bars()
    s = sig(spot=float(df[df.timestamp < SIG_TS].close.iloc[-1]))
    base = ctx_for(df[df.timestamp < SIG_TS], s)
    fut = df.copy()
    after = fut.timestamp >= SIG_TS
    fut.loc[after, "high"] = fut.loc[after, "high"] + 900                       # भविष्यातला मोठा spike
    fut.loc[after, "low"] = fut.loc[after, "low"] - 900
    full = ctx_for(fut, s)
    assert json.dumps(full, default=str, sort_keys=True) == json.dumps(base, default=str, sort_keys=True)
    assert all(abs(o["price"] - s["spot"]) < 800 for o in full["overlays"])         # spike चा कुठलाही level नाही


def test_prev_day_and_week_are_complete_previous_periods():
    df = bars()
    cut = CH.cut_1m(df, SIG_TS)
    pd_ = CX.prev_day(cut, SIG_TS.normalize())
    y = df[df.timestamp.dt.normalize() == pd.Timestamp("2026-10-05")]
    assert pd_["day"] == "2026-10-05" and pd_["high"] == pytest.approx(y.high.max()) and pd_["close"] == pytest.approx(y.close.iloc[-1])
    pw = CX.prev_week(cut, SIG_TS.normalize())
    w = df[(df.timestamp >= "2026-09-28") & (df.timestamp < "2026-10-03")]
    assert pw["week"] == "2026-09-28" and pw["high"] == pytest.approx(w.high.max()) and pw["low"] == pytest.approx(w.low.min())
    spike = df.copy()
    k = spike.index[(spike.timestamp == SIG_TS - pd.Timedelta(minutes=30))][0]
    spike.loc[k, "high"] = 26500.0                                                 # आज (चालू आठवडा / दिवस) चा मोठा high, signal आधी
    cut2 = CH.cut_1m(spike, SIG_TS)
    assert CX.prev_week(cut2, SIG_TS.normalize())["high"] == pytest.approx(w.high.max())          # चालू आठवडा नाही
    assert CX.prev_day(cut2, SIG_TS.normalize())["high"] == pytest.approx(y.high.max())           # चालू दिवस नाही
    today = df[df.timestamp.dt.normalize() == SIG_TS.normalize()]
    op = CX.opening(cut, SIG_TS.normalize(), SIG_TS)
    first15 = today[today.timestamp < SIG_TS.normalize() + pd.Timedelta(hours=9, minutes=30)]
    assert op["or_complete"] and op["or_high"] == pytest.approx(first15.high.max()) and op["open"] == pytest.approx(today.open.iloc[0])
    early = CX.opening(CH.cut_1m(df, SIG_TS.normalize() + pd.Timedelta(hours=9, minutes=22)), SIG_TS.normalize(),
                       SIG_TS.normalize() + pd.Timedelta(hours=9, minutes=22))
    assert not early["or_complete"]


def test_swings_need_confirmation_bars():
    s = pd.DataFrame({"high": [1, 2, 5, 2, 1, 3, 9.0], "low": [0, 1, 4, 1, 0, 2, 8.0]})
    sw = CX.swings(s, r=2)
    assert (2, "H", 5.0) in sw and all(i <= len(s) - 1 - 2 for i, _, _ in sw)     # शेवटचा 9 (उजवीकडे bars नाहीत) pivot नाही


def test_time_flags_room_and_gap():
    df = bars()
    c = ctx_for(df)
    assert c["minutes_since_open"] == 106 and c["time_flag"] == "none"
    assert c["room"]["next_name"] and c["room"]["next_price"] > c["spot"]                 # bullish ⇒ वरचा विरोधी level
    c2 = ctx_for(df, sig(signal_ts=SIG_TS.normalize() + pd.Timedelta(hours=9, minutes=25)))
    assert c2["time_flag"] == "opening"
    c3 = ctx_for(df, sig(signal_ts=SIG_TS.normalize() + pd.Timedelta(hours=14, minutes=45)))
    assert c3["time_flag"] == "last_hour"
    assert CX.expiry_days(["2026-10-13", "2026-10-06", "2026-09-29"], SIG_TS.normalize()) == 0


def test_overlay_labels_merge_when_close():
    items = [{"name": "PDH", "price": 25100.0, "kind": "ref"}, {"name": "M1↑", "price": 25100.5, "kind": "major"},
             {"name": "L", "price": 24990.0, "kind": "L"}, {"name": "PDC", "price": 24990.8, "kind": "ref"}, {"name": "PWH", "price": 25300.0, "kind": "ref"}]
    out = CX.merge_labels(items, 10.0)                                                 # 0.1 × 10 = 1 point
    labels = [o["label"] for o in out]
    assert "M1↑+PDH" in labels and "L+PDC" in labels and "PWH" in labels and len(out) == 3
    assert [o for o in out if o["label"] == "L+PDC"][0]["price"] == 24990.0           # L ची किंमत


def test_chart_v2_renders_with_overlays(monkeypatch):
    df = bars()
    png, meta = CH.render(df, sig())
    assert meta["error"] is None and meta.get("ctx") and meta["ctx"]["prev_day"]["day"] == "2026-10-05"
    if png is None:
        pytest.skip("kaleido नाही")
    assert png[:4] == b"\x89PNG"


# ------------------------------------------------------------------------------------------------ verdict नियम
@pytest.mark.parametrize("field,value,rule", [
    ("is_breakout_entry", "yes", "breakout"), ("reversal_valid", "no", "reversal_invalid"), ("level_kind", "mid_range", "weak_level"),
    ("level_kind", "magnet", "weak_level"), ("wave_position", "a_end", "bad_wave"), ("wave_position", "inside_b_or_triangle", "bad_wave"),
    ("reversal_close_location", "bad", "bad_close"), ("time_risk", "opening", "opening")])
def test_each_disagree_rule_overrides_agree(field, value, rule):
    a = SA.validate({**GOOD, field: value})[0]
    assert a["verdict"] == "agree" and SA.code_verdict(a) == "disagree"
    assert rule in SA.rule_hits(a)[0]
    off = [r for r in VC.RULE_IDS["v2_disagree_rules"] if r != rule]
    assert SA.code_verdict(a, disagree_rules=off) != "disagree"                                 # नियम बंद ⇒ लागू नाही


@pytest.mark.parametrize("field,value,rule", [
    ("level_real", "unclear", "unclear"), ("level_kind", "unclear", "unclear"), ("wave_position", "unclear", "unclear"),
    ("room_to_next_level", "unclear", "unclear"), ("correction_complete", "no", "correction_incomplete"),
    ("room_to_next_level", "tight", "tight_room"), ("reversal_close_location", "middle", "middle_close"),
    ("wave_position", "impulse_running", "impulse_running")])
def test_each_gray_rule_overrides_agree(field, value, rule):
    a = SA.validate({**GOOD, field: value})[0]
    assert SA.code_verdict(a) == "gray" and rule in SA.rule_hits(a)[1]
    off = [r for r in VC.RULE_IDS["v2_gray_rules"] if r != rule]
    assert SA.code_verdict(a, gray_rules=off) == "agree"


def test_htf_unclear_is_not_gray_and_vision_disagree_stays():
    assert SA.code_verdict(SA.validate({**GOOD, "htf_trend": "unclear"})[0]) == "agree"
    assert SA.code_verdict(SA.validate({**GOOD, "verdict": "disagree"})[0]) == "disagree"      # नियमांपेक्षा कडक मत तसंच
    assert SA.code_verdict(SA.validate({**GOOD, "verdict": "gray"})[0]) == "gray"
    assert SA.combine(["agree", "gray"]) == "gray"                                              # दोन audits असहमत


def test_invalid_enum_is_unavailable_and_auto_veto_skips():
    from vision import decide as VD
    assert SA.validate({**GOOD, "wave_position": "w3"})[1]
    assert SA.validate({k: v for k, v in GOOD.items() if k != "level_kind"})[1]                 # field गायब
    r = SA.audit(_Fake([msg({**GOOD, "reversal_touch": "maybe"})]), b"png", sig(), "test-sonnet-model")
    assert r["verdict"] == "unavailable"
    s = {**VC.BOT_DEFAULTS, "vision_gray_action": "skip", "vision_fail_action": "skip"}
    for v in ("gray", "disagree", "unavailable"):
        assert VD.decide("auto_veto", v, s).status == "REJECTED"                                  # तुमचा auto_veto: फक्त agree ⇒ entry
    assert VD.decide("auto_veto", "agree", s).status == "APPROVED"


class _Fake:
    def __init__(self, replies):
        self.replies, self.calls, self.messages = list(replies), [], self

    def create(self, **params):
        self.calls.append(params)
        return self.replies.pop(0)


def test_request_is_v2_cached_and_text_has_exact_prices():
    df = bars()
    s = sig()
    png, meta = CH.render(df, s)
    s["ctx"] = meta["ctx"]
    c = _Fake([msg(GOOD)])
    r = SA.audit(c, b"png", s, "test-sonnet-model")
    p = c.calls[0]
    assert r["prompt_version"] == "signal_check_v2_1" and p["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "ELLIOTT WAVE" in p["system"][0]["text"] and p["max_tokens"] == 1200
    assert set(p["output_config"]["format"]["schema"]["required"]) >= {"level_kind", "wave_position", "reversal_close_location"}
    text = p["messages"][0]["content"][1]["text"]
    pdh = meta["ctx"]["prev_day"]["high"]
    assert f"{pdh:,.2f}" in text and "PDH" in text and "Room:" in text and "minutes since the 09:15 open" in text
    assert r["rule_hits"][0] == {"disagree": [], "gray": ["unclear"]}                         # 11:01 ⇒ 11:00 चा bar बंद नाही ⇒ reversal unclear
    assert any("बंद नाही" in x for x in r["audits"][0]["code_overrides"]) and "NOT CLOSED" in text


def test_config_rule_lists_validated_and_match_audit_rules():
    assert set(VC.RULE_IDS["v2_disagree_rules"]) == set(SA.DISAGREE_RULES)
    assert set(VC.RULE_IDS["v2_gray_rules"]) == set(SA.GRAY_RULES)
    assert VC.validate("dynamic_sr_instant", {"v2_gray_rules": "unclear,tight_room"})["v2_gray_rules"] == ["unclear", "tight_room"]
    with pytest.raises(ValueError):
        VC.validate("dynamic_sr_instant", {"v2_disagree_rules": ["no_such_rule"]})


# ------------------------------------------------------------------------------------------------ v1 records / caption
@pytest.fixture
def vdb(tmp_path, monkeypatch):
    monkeypatch.setenv("VISION_DB_PATH", str(tmp_path / "vision.db"))
    monkeypatch.setenv("VISION_IMAGE_DIR", str(tmp_path / "img"))
    return str(tmp_path / "vision.db")


def test_v1_records_not_reused_for_v2(vdb):
    row = {"bot": "dynamic_sr_instant", "symbol": "NIFTY", "trading_mode": "PAPER", "mode": "notify", "signal_ts": dt.datetime(2026, 10, 6, 10, 0),
           "direction": "BULLISH", "level": 25000.0, "role": "SUPPORT", "setup_tf": "5M", "spot": 25010.0, "algo_decision": "ENTER"}
    old = VS.insert_signal(row)
    VS.finish(old, "DONE", verdict="agree", prompt_version="signal_check_v1")
    new = {**row, "signal_ts": dt.datetime(2026, 10, 6, 10, 5), "setup_json": "{}"}
    assert VS.find_reusable(new, 15) is not None
    assert VS.find_reusable(new, 15, prompt_version=SA.PROMPT_VERSION) is None
    assert VS.get_signal(old)["prompt_version"] == "signal_check_v1"                          # जुनं record तसंच


def test_caption_v2_lines():
    a = SA.validate({**GOOD, "room_to_next_level": "tight"})[0]
    res = {"verdict": "gray", "audits": [a], "rule_hits": [{"disagree": [], "gray": ["tight_room"]}], "confidence": 0.8}
    row = {"bot": "dynamic_sr_instant", "symbol": "NIFTY", "direction": "BULLISH", "level": 25000.0, "role": "SUPPORT", "setup_tf": "5M",
           "signal_ts": "2026-10-06T10:00:00"}
    cap = VW.caption(row, res, "auto_veto")
    for s in ("Trend: HTF up", "Level: flip", "Wave: w4_end", "touch ✓", "close ✓", "Room tight", "🟡 tight_room", "कारण:"):
        assert s in cap


def test_dashboard_v2_fields_and_version_filter(vdb):
    import page_vision_human_eye as P
    row = {"bot": "dynamic_sr_instant", "symbol": "NIFTY", "trading_mode": "PAPER", "mode": "auto_veto", "signal_ts": dt.datetime(2026, 10, 6, 10, 0),
           "direction": "BULLISH", "level": 25000.0, "role": "SUPPORT", "setup_tf": "5M", "spot": 25010.0, "algo_decision": "ENTER"}
    a = SA.validate({**GOOD, "room_to_next_level": "tight"})[0]
    s2 = VS.insert_signal(row)
    VS.finish(s2, "SHADOWED", verdict="gray", prompt_version="signal_check_v2",
              vision_json={"audits": [a], "rule_hits": [{"disagree": [], "gray": ["tight_room"]}]})
    s1 = VS.insert_signal({**row, "signal_ts": dt.datetime(2026, 10, 5, 10, 0)})
    VS.finish(s1, "DONE", verdict="agree", prompt_version="signal_check_v1", vision_json={"audits": [{"reason": "जुनं"}]})
    df = P.flatten(VS.list_signals())
    assert set(df["prompt_version"]) == {"signal_check_v1", "signal_check_v2"}
    v2 = P.apply_filters(df, versions=["signal_check_v2"])
    assert len(v2) == 1 and v2["level_kind"].iloc[0] == "flip" and v2["rules"].iloc[0] == "tight_room"
    assert len(P.apply_filters(df, field="room_to_next_level", values=["tight"])) == 1


def test_samples_script_reaudits_without_touching_signals(vdb, monkeypatch, capsys):
    import importlib.util
    import os
    from vision import tg as TG
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec = importlib.util.spec_from_file_location("vsamp", os.path.join(root, "scripts", "vision_v2_samples.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    df = bars()
    monkeypatch.setattr(VW, "default_fetch", lambda sym, daily: (df[df.timestamp < SIG_TS], None))
    monkeypatch.setattr(VW, "fetch_expiries", lambda sym: ["2026-10-13"])
    monkeypatch.setattr(CH, "render", lambda m1, s, daily=None: (b"\x89PNGfake", {"error": None, "ctx": ctx_for(df, {**sig(), **s})}))
    monkeypatch.setenv("VISION_SIGNAL_MODEL", "test-sonnet-model")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    fake = _Fake([msg(GOOD), msg({**GOOD, "is_breakout_entry": "yes"}), msg(GOOD)])
    monkeypatch.setattr(SA, "make_client", lambda t=20: fake)
    sent = []
    monkeypatch.setattr(TG, "send_photo", lambda png, cap, buttons=None, chat_id=None: sent.append(cap) or 1)
    row = {"bot": "dynamic_sr_instant", "symbol": "NIFTY", "trading_mode": "PAPER", "mode": "notify", "signal_ts": dt.datetime(2026, 10, 6, 10, 40),
           "direction": "BULLISH", "level": 24990.0, "role": "SUPPORT", "setup_tf": "5M", "spot": 25000.0, "algo_decision": "ENTER"}
    sid = VS.insert_signal(row)
    before = VS.get_signal(sid)
    assert mod.main(["--n", "3"]) == 0
    out = capsys.readouterr().out
    assert out.count("vision JSON (v2)") == 3 and "code verdict: disagree" in out and "PDH" in out
    assert len(VS.list_signals()) == 1 and VS.get_signal(sid) == before                      # vision_signals ला हात नाही
    assert len(sent) == 3 and all("trade नाही" in c for c in sent)
    assert VS.usage_summary(VS.now_ist().strftime("%Y-%m-%d"))["calls"] == 3


def test_samples_script_fails_when_vision_never_answers(vdb, monkeypatch):
    import importlib.util
    import os
    from vision import tg as TG
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec = importlib.util.spec_from_file_location("vsamp2", os.path.join(root, "scripts", "vision_v2_samples.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    df = bars()
    monkeypatch.setattr(VW, "default_fetch", lambda sym, daily: (df[df.timestamp < SIG_TS], None))
    monkeypatch.setattr(VW, "fetch_expiries", lambda sym: [])
    monkeypatch.setattr(CH, "render", lambda m1, s, daily=None: (b"\x89PNGfake", {"error": None, "ctx": None}))
    monkeypatch.setenv("VISION_SIGNAL_MODEL", "test-sonnet-model")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr(SA, "make_client", lambda t=20: _Fake([msg(GOOD, stop="refusal")] * 3))
    monkeypatch.setattr(TG, "send_photo", lambda *a, **k: 1)
    assert mod.main(["--n", "3"]) == 2                                                         # deploy block auto_veto चालू करत नाही


# ------------------------------------------------------------------------------------------------ review fixes
def gap_bars(gap=-80.0, fill=False):
    df = bars()
    today = df.timestamp.dt.normalize() == SIG_TS.normalize()
    for c in ("open", "high", "low", "close"):
        df.loc[today, c] = df.loc[today, c] + gap
    if fill:
        k = df.index[df.timestamp == SIG_TS - pd.Timedelta(minutes=20)][0]
        prev_close = float(df[df.timestamp.dt.normalize() < SIG_TS.normalize()].close.iloc[-1])
        df.loc[k, "high" if gap < 0 else "low"] = prev_close + (5 if gap < 0 else -5)
    return df


@pytest.mark.parametrize("gap,fill", [(-80.0, False), (-80.0, True), (80.0, True)])
def test_gap_day_context_is_json_safe_and_agree_stays_agree(vdb, monkeypatch, gap, fill):
    """Review B1: gap दिवशी numpy bool ⇒ JSON चूक ⇒ agree चा unavailable (auto_veto skip) होत होता."""
    df = gap_bars(gap, fill)
    c = ctx_for(df)
    assert c["gap"]["pct"] != 0 and c["gap"]["filled"] is fill and type(c["gap"]["filled"]) is bool
    json.dumps(c)                                                                            # default शिवाय
    VC.save("dynamic_sr_instant", {"vision_mode": "auto_veto", "vision_gray_action": "skip", "vision_fail_action": "skip"}, "t",
            trading_mode_fn=lambda b, s: "PAPER")
    row = {"bot": "dynamic_sr_instant", "symbol": "NIFTY", "trading_mode": "PAPER", "mode": "auto_veto", "signal_ts": SIG_TS,
           "direction": "BULLISH", "level": float(df[df.timestamp < SIG_TS].low.tail(30).min()), "role": "SUPPORT", "setup_tf": "5M",
           "spot": float(df[df.timestamp < SIG_TS].close.iloc[-1]), "algo_decision": "ENTER"}
    sid = VS.insert_signal(row)
    r = VS.claim_one(sid)
    monkeypatch.setenv("VISION_SIGNAL_MODEL", "test-sonnet-model")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    fake = _Fake([msg({**GOOD, "room_to_next_level": "enough"})])
    from vision import tg as TG
    monkeypatch.setattr(TG, "send_photo", lambda *a, **k: 1)
    monkeypatch.setattr(SA, "apply_facts", lambda a, ctx, direction=None: (a, []))           # room / time तथ्यं वेगळ्या test मध्ये
    monkeypatch.setattr(SA, "code_facts", lambda ctx, direction=None: {})                      # gap नियम वेगळ्या tests मध्ये
    out = VW.process_row(r, fetch_fn=lambda sym, daily: (df[df.timestamp < SIG_TS], None), client_factory=lambda t: fake)
    got = VS.get_signal(sid)
    assert out["verdict"] == "agree" and got["verdict"] == "agree" and got["status"] == "APPROVED", got["error"]
    vj = json.loads(got["vision_json"])
    assert vj["context"]["gap"]["filled"] is fill
    text = fake.calls[0]["messages"][0]["content"][1]["text"]
    assert "Gap today" in text and "PDH" in text                                             # worker ने ctx request मध्ये पाठवला


def test_code_facts_override_model_opening_tight_room_and_missing_context():
    """Review S4 / S2: नियम model ने तथ्य पुन्हा लिहिण्यावर अवलंबून नाहीत; संदर्भ नसेल तर room unclear (gray)."""
    a = SA.validate(GOOD)[0]
    b, ch = SA.apply_facts(a, {"time_flag": "opening", "room": {"next_mr": 3.0}})
    assert b["time_risk"] == "opening" and SA.code_verdict(b) == "disagree" and ch
    b, ch = SA.apply_facts(a, {"time_flag": "none", "room": {"next_mr": 0.4}})
    assert b["room_to_next_level"] == "tight" and SA.code_verdict(b) == "gray"
    b, ch = SA.apply_facts(a, None)
    assert b["room_to_next_level"] == "unclear" and SA.code_verdict(b) == "gray"
    b, ch = SA.apply_facts(a, {"time_flag": "none", "room": {"next_mr": 2.5}})
    assert not ch and SA.code_verdict(b) == "agree"
    assert "Context unavailable" in SA.signal_text(sig()) and "Room: no opposing" not in SA.signal_text(sig())
    r = SA.audit(_Fake([msg(GOOD)]), b"png", {**sig(), "ctx": {"time_flag": "opening", "room": {}}}, "test-sonnet-model")
    assert r["verdict"] == "disagree" and r["audits"][0]["code_overrides"] == ["time_risk=opening"]


def test_failed_second_audit_does_not_turn_low_confidence_agree_into_entry():
    """Review S5."""
    c = _Fake([msg({**GOOD, "confidence": 0.4}), msg(GOOD, stop="refusal")])
    r = SA.audit(c, b"png", {**sig(), "ctx": {"time_flag": "none", "room": {"next_mr": 3.0}}}, "test-sonnet-model", second_below=0.6)
    assert len(c.calls) == 2 and r["verdict"] == "gray"


def test_tz_aware_signal_ts_and_crowded_labels_render(monkeypatch):
    """Review S3 / S1 / nit: tz-aware signal_ts, 10+ एकत्र labels, "L+PDL+PWL" label."""
    df = bars()
    c = ctx_for(df, sig(signal_ts=pd.Timestamp("2026-10-06 11:01", tz="Asia/Kolkata")))
    assert c["minutes_since_open"] == 106
    crowded = {"overlays": [{"price": 25000.0 + k * 0.3, "label": f"X{k}", "kinds": ["ref"]} for k in range(14)]
               + [{"price": 24990.0, "label": "L+PDL+PWL", "kinds": ["L", "ref"]}], "opening": {}, "swings": []}
    setup, higher, tfs = CH.panels(df, SIG_TS, "5M")
    fig = CH.build_figure(setup, higher, sig(), tfs, crowded)
    texts = [a.text for a in fig.layout.annotations]
    assert any("(PDL+PWL)" in t for t in texts) and not any("PDPWL" in t for t in texts)


def test_v1_caption_keeps_decision_line_when_long():
    from vision import decide as VD
    a = SA.validate({**GOOD, "reason": "क" * 160, "elliott_note": "e" * 100, "is_breakout_entry": "yes"})[0]
    res = {"verdict": "disagree", "audits": [a, a], "verdicts": ["disagree", "disagree"],
           "rule_hits": [{"disagree": list(SA.DISAGREE_RULES), "gray": list(SA.GRAY_RULES)}], "confidence": 0.5, "cost_usd": 0.01}
    row = {"bot": "dynamic_sr_instant", "bot_label": "B" * 120, "symbol": "NIFTY", "direction": "BULLISH", "level": 25000.0,
           "role": "SUPPORT", "setup_tf": "5M", "signal_ts": "2026-10-06T10:00:00", "mode": "auto_veto"}
    cap = VW.v1_caption(row, res, VD.decide("auto_veto", "disagree", {**VC.BOT_DEFAULTS}))
    assert len(cap) <= 1024 and "<b>❌ ENTRY नाकारली</b>" in cap and cap.count("<b>") == cap.count("</b>")
    assert cap.split("\n")[1].startswith("<b>❌ ENTRY नाकारली")
