"""v2.2 chart → Vision audit → Telegram (Abhi): mock provider; budget hard stop; report ≤ 12 ओळी; JSON PNG शेजारी; सारांश; decision
कधीच बदलत नाही. Network / API call नाही."""
import copy
import json
from types import SimpleNamespace

from decision3 import vision_audit as VA

GOOD = {"verdict": "partly_agree", "issues": ["protected line one swing late", "tags crowded near top"],
        "missing_or_clutter": "too many minor pivots",
        "sections": {"zones": {"status": "na", "reason": "no zones on this chart"},
                     "structure": {"status": "warn", "reason": "LH tag at a minor swing"},
                     "pullback_trigger": {"status": "na", "reason": "not shown"},
                     "entry_sl_target": {"status": "na", "reason": "not shown"}}}


class FakeClient:
    def __init__(self, payload, log):
        self.payload, self.log = payload, log
        self.messages = self

    def create(self, **params):
        self.log.append(("vision", params["model"]))
        assert "FACTS" in params["messages"][0]["content"][1]["text"]
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(self.payload))], stop_reason="end_turn",
                               usage=SimpleNamespace(input_tokens=1500, output_tokens=200, cache_read_input_tokens=0,
                                                     cache_creation_input_tokens=0))


def _run_dir(tmp_path):
    d = tmp_path / "run"
    (d / "BANKNIFTY").mkdir(parents=True)
    (d / "BANKNIFTY" / "daily_swings.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 200)
    js = {"symbol": "BANKNIFTY", "window": {"from": "a", "to": "b"}, "pivots": [], "minor": {"trend": "DOWN"}, "q15": {"trend": "UP"}}
    (d / "BANKNIFTY" / "daily_swings.json").write_text(json.dumps(js))
    cap = "BANKNIFTY · Daily\nline2\nVision audit: pending (runs before Telegram send)\nVisual review only — no trade, no order"
    m = {"run_id": "v22_daily_swings", "title": "v2.2 Daily swings", "items": [
        {"symbol": "BANKNIFTY", "date": "d", "item": "v22_daily_swings|BANKNIFTY|d", "reading": "r", "caption": cap,
         "kind": "v22_daily_swings", "files": ["BANKNIFTY/daily_swings.png"], "json": "BANKNIFTY/daily_swings.json"}]}
    (d / "manifest.json").write_text(json.dumps(m))
    return d


def _tg(log):
    def call(method, data=None, files=None, timeout=60):
        log.append((method, dict(data or {})))
        return {"ok": True, "result": {"message_id": 101 if method == "sendPhoto" else 102}}
    return call


def test_send_path_audits_before_telegram_and_replies_report(tmp_path):
    from backtest_review import telegram as RT
    d, log = _run_dir(tmp_path), []
    aud = VA.make_auditor(model="m-test", client=FakeClient(GOOD, log), budget=lambda m: (True, 0.1, 2.0))
    out = RT.send_run(str(d), call=_tg(log), creds=lambda: ("t", "c"), sent=str(tmp_path / "sent.json"), sleep=lambda s: None,
                      auditor=aud)
    assert out["sent"] == 1 and [x[0] for x in log] == ["vision", "sendPhoto", "sendMessage"]          # audit आधी, मग chart, मग report
    cap = log[1][1]["caption"]
    assert "Vision audit: partly agree — 1 issue, see report" in cap and len(cap.splitlines()) <= 7
    rep = log[2][1]
    assert rep["reply_to_message_id"] == 101 and rep["text"].startswith("Vision report")
    sj = json.load(open(d / "BANKNIFTY" / "daily_swings.vision.json"))
    assert sj["status"] == "done" and sj["verdict"] == "partly_agree" and sj["cost_usd"] > 0          # audit JSON PNG शेजारी


def test_budget_exhausted_chart_still_sent_with_note(tmp_path):
    from backtest_review import telegram as RT
    d, log = _run_dir(tmp_path), []
    aud = VA.make_auditor(model="m-test", client=FakeClient(GOOD, log), budget=lambda m: (False, 2.0, 2.0))
    out = RT.send_run(str(d), call=_tg(log), creds=lambda: ("t", "c"), sent=str(tmp_path / "sent.json"), sleep=lambda s: None,
                      auditor=aud)
    assert out["sent"] == 1 and "vision" not in [x[0] for x in log]                                   # provider call नाही (hard stop)
    assert "Vision audit skipped: daily budget reached" in log[0][1]["caption"]


def test_provider_failure_never_blocks(tmp_path):
    from backtest_review import telegram as RT

    class Boom:
        messages = SimpleNamespace(create=lambda **k: (_ for _ in ()).throw(RuntimeError("down")))
    d, log = _run_dir(tmp_path), []
    out = RT.send_run(str(d), call=_tg(log), creds=lambda: ("t", "c"), sent=str(tmp_path / "sent.json"), sleep=lambda s: None,
                      auditor=VA.make_auditor(model="m", client=Boom(), budget=lambda m: (True, 0, 2.0)))
    assert out["sent"] == 1 and "Vision audit failed" in log[0][1]["caption"]


def test_daily_cap_default_is_two_dollars_and_hard_stop():
    from vision import config as VC
    assert VC.GLOBAL_DEFAULTS["vision_daily_budget_usd"] == 2.0
    g = dict(VC.GLOBAL_DEFAULTS)
    ok, day, cap, why = VA._budget("m", g=g, spent_fn=lambda: (1.99, 3.0), estimate_fn=lambda m: 0.02)
    assert not ok and cap == 2.0 and why == "daily budget reached"
    assert VA._budget("m", g=g, spent_fn=lambda: (1.0, 3.0), estimate_fn=lambda m: 0.02)[0]
    ok, _, _, why = VA._budget("m", g=g, spent_fn=lambda: (0.5, 4.99), estimate_fn=lambda m: 0.02)
    assert not ok and why == "monthly budget reached"                                          # कारण बरोबर cap चं


def test_report_at_most_12_lines_with_four_sections():
    a = {"status": "done", "cost_usd": 0.01, "spent_today": 0.2, "cap": 2.0, **VA.validate(GOOD)[0]}
    a["issues"] = [f"issue {i}" for i in range(9)]
    txt = VA.report_text(a, "BANKNIFTY daily")
    ls = txt.splitlines()
    assert len(ls) <= 12 and ls[-1] == VA.FOOTER
    for name in VA.SECTION_NAMES.values():
        assert any(x.startswith(name + ":") for x in ls)


def test_summary_appended(tmp_path):
    p = str(tmp_path / "VISION_AUDIT.md")
    rows = [{"status": "done", "verdict": "agree", "issues": [], "cost_usd": 0.01},
            {"status": "done", "verdict": "disagree", "issues": ["stop inside zone"], "cost_usd": 0.02},
            {"status": "skipped", "why": "daily budget reached", "cost_usd": 0}]
    VA.append_summary(p, "D1", rows)
    VA.append_summary(p, "D2", rows[:1])
    s = open(p, encoding="utf-8").read()
    assert s.count("## D") == 2 and "charts audited: 2 / 3" in s and "stop inside zone ×1" in s and "$0.0300" in s


def test_vision_never_alters_decision():
    """Disagree verdict नंतरही decision object (deep) तसाच; audit निकालात decision / order field नाही."""
    dec = {"decision": "setup", "level": {"lo": 1.0, "hi": 2.0}, "risk": {"rr": 3.2}}
    before = copy.deepcopy(dec)
    log = []
    a = VA.audit_chart(b"png", "facts", model="m", client=FakeClient({**GOOD, "verdict": "disagree"}, log),
                       budget=lambda m: (True, 0, 2.0), decision=dec)
    assert a["status"] == "done" and a["verdict"] == "disagree" and dec == before
    assert not {"decision", "order", "level", "risk"} & set(a)


def test_auditor_exception_still_sends_chart(tmp_path):
    from backtest_review import telegram as RT
    d, log = _run_dir(tmp_path), []

    def bad(run_dir, it):
        raise RuntimeError("db locked")
    out = RT.send_run(str(d), call=_tg(log), creds=lambda: ("t", "c"), sent=str(tmp_path / "sent.json"), sleep=lambda s: None,
                      auditor=bad)
    assert out["sent"] == 1 and "Vision audit failed: auditor RuntimeError" in log[0][1]["caption"]


def test_audit_off_caption_and_dry_run_no_spend(tmp_path):
    from backtest_review import telegram as RT
    d, log = _run_dir(tmp_path), []
    out = RT.send_run(str(d), call=_tg(log), creds=lambda: ("t", "c"), sent=str(tmp_path / "sent.json"), sleep=lambda s: None)
    assert out["sent"] == 1 and "Vision audit skipped: off" in log[0][1]["caption"]
    calls = []
    d2 = _run_dir(tmp_path / "x")
    RT.send_run(str(d2), call=_tg(log), creds=lambda: ("t", "c"), sent=str(tmp_path / "s2.json"), sleep=lambda s: None, dry_run=True,
                auditor=lambda r, i: calls.append(1))
    assert calls == []                                                                          # dry-run ⇒ audit / खर्च नाही


def test_same_chart_audit_reused_no_second_spend(tmp_path):
    d, log = _run_dir(tmp_path), []
    aud = VA.make_auditor(model="m", client=FakeClient(GOOD, log), budget=lambda m: (True, 0, 2.0))
    it = json.load(open(d / "manifest.json"))["items"][0]
    a1, a2 = aud(str(d), it), aud(str(d), it)
    assert [x[0] for x in log] == ["vision"] and a2.get("reused") and a2["verdict"] == a1["verdict"]


def test_failed_report_reply_is_surfaced(tmp_path):
    from backtest_review import telegram as RT
    d, log = _run_dir(tmp_path), []

    def call(method, data=None, files=None, timeout=60):
        log.append((method, dict(data or {})))
        return {"ok": True, "result": {"message_id": 7}} if method == "sendPhoto" else {"ok": False, "error_code": 400}
    out = RT.send_run(str(d), call=call, creds=lambda: ("t", "c"), sent=str(tmp_path / "sent.json"), sleep=lambda s: None,
                      auditor=VA.make_auditor(model="m", client=FakeClient(GOOD, []), budget=lambda m: (True, 0, 2.0)))
    assert out["sent"] == 1 and any("Vision report reply" in w for _, w in out["failed"])


def test_invalid_json_is_failed_not_crash():
    log = []
    a = VA.audit_chart(b"png", "facts", model="m", client=FakeClient({"verdict": "maybe"}, log), budget=lambda m: (True, 0, 2.0))
    assert a["status"] == "failed" and VA.caption_line(a).startswith("Vision audit failed")
