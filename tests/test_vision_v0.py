"""Vision V0 (shadow / notify) — settings, hook (reduce-only, LIVE off), no-lookahead chart, verdict नियम, budget, reuse, exit मार्ग वेगळा."""
import ast
import datetime as dt
import json
import os
import types

import numpy as np
import pandas as pd
import pytest

from vision import chart as CH
from vision import config as VC
from vision import hook as VH
from vision import signal_audit as SA
from vision import store as VS
from vision import worker as VW

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def db(tmp_path, monkeypatch):
    p = str(tmp_path / "vision.db")
    monkeypatch.setenv("VISION_DB_PATH", p)
    monkeypatch.setenv("VISION_IMAGE_DIR", str(tmp_path / "img"))
    return p


def m1_frame(days=("2026-10-05", "2026-10-06"), spike_after=None):
    rows = []
    rng = np.random.default_rng(0)
    px = 25000.0
    for d in days:
        for k in range(375):
            t = pd.Timestamp(d) + pd.Timedelta(hours=9, minutes=15 + k)
            o = px
            px += rng.normal(0, 3)
            hi, lo = max(o, px) + 2, min(o, px) - 2
            if spike_after is not None and t >= spike_after:
                hi += 900                                                    # भविष्यातला मोठा spike — chart मध्ये कधीच दिसू नये
            rows.append((t.tz_localize("Asia/Kolkata"), o, hi, lo, px))
    return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close"])


def sig(**kw):
    s = {"signal_id": "x", "bot": "dynamic_sr_instant", "symbol": "NIFTY", "direction": "BULLISH", "level": 25000.0, "role": "SUPPORT",
         "setup_tf": "5M", "signal_ts": "2026-10-06T10:42:20", "spot": 25010.0, "mode": "notify", "trading_mode": "PAPER"}
    s.update(kw)
    return s


# ------------------------------------------------------------------------------------------------ settings
def test_defaults_v0_nifty_notify_others_off(db):
    assert VC.load("dynamic_sr_instant")["vision_mode"] == "notify"
    assert VC.load("srv2_momentum_reversal")["vision_mode"] == "notify"
    assert VC.load("mcx_futures")["vision_mode"] == "off"
    assert VC.load("pullback_credit_spread")["vision_mode"] == "off"
    g = VC.load("_global")
    assert g["vision_daily_budget_usd"] == 0.30 and g["vision_monthly_budget_usd"] == 5.0


def test_v1_modes_rejected_in_v0_and_live_always_off(db):
    for m in ("auto_veto", "human_confirm", "veto_then_confirm"):
        with pytest.raises(ValueError):
            VC.save("dynamic_sr_instant", {"vision_mode": m}, "t")
    s = VC.load("dynamic_sr_instant")
    assert VC.effective_mode(s, "LIVE") == "off"
    assert VC.effective_mode(s, None) == "off"
    assert VC.effective_mode(s, "PAPER") == "notify"
    assert VC.effective_mode({"vision_mode": "human_confirm"}, "PAPER") == "off"   # V0 मध्ये लागू नाही


def test_settings_validation_and_history(db):
    with pytest.raises(ValueError):
        VC.save("dynamic_sr_instant", {"vision_timeout_sec": 500}, "t")
    with pytest.raises(ValueError):
        VC.save("dynamic_sr_instant", {"nonsense": 1}, "t")
    with pytest.raises(ValueError):
        VC.save("no_such_bot", {"vision_mode": "off"}, "t")
    VC.save("dynamic_sr_instant", {"vision_mode": "shadow"}, "abhishek")
    VC.save("_global", {"vision_daily_budget_usd": 0.2}, "abhishek")
    assert VC.load("dynamic_sr_instant")["vision_mode"] == "shadow"
    h = VC.history()
    assert [x["bot"] for x in h] == ["dynamic_sr_instant", "_global"] and h[0]["by"] == "abhishek"
    assert json.loads(h[0]["old_json"])["vision_mode"] == "notify" and json.loads(h[0]["new_json"])["vision_mode"] == "shadow"


# ------------------------------------------------------------------------------------------------ hook (reduce-only)
def test_hook_paper_queues_live_and_off_do_nothing(db):
    now = dt.datetime(2026, 10, 6, 10, 42, 20)
    assert VH.submit_signal("dynamic_sr_instant", "NIFTY", "PAPER", "BULLISH", 25000, "SUPPORT", "5M", now, 25010) is None
    assert VH.submit_signal("dynamic_sr_instant", "NIFTY", "LIVE", "BULLISH", 25000, "SUPPORT", "5M", now, 25010) is None
    assert VH.submit_signal("dynamic_sr_instant", "BANKNIFTY", "PAPER", "BULLISH", 52000, "SUPPORT", "5M", now) is None
    assert VH.submit_signal("mcx_futures", "NIFTY", "PAPER", "BULLISH", 25000, "SUPPORT", "5M", now) is None
    rows = VS.list_signals()
    assert len(rows) == 1 and rows[0]["trading_mode"] == "PAPER" and rows[0]["status"] == "QUEUED" and rows[0]["mode"] == "notify"


def test_hook_never_raises_and_returns_none(db, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db down")
    monkeypatch.setattr(VS, "insert_signal", boom)
    assert VH.submit_signal("dynamic_sr_instant", "NIFTY", "PAPER", "BULLISH", 25000, "SUPPORT", "5M", dt.datetime(2026, 10, 6, 10, 0)) is None


def _vision_calls(path):
    tree = ast.parse(open(os.path.join(ROOT, path), encoding="utf-8").read())
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "_vision_submit"]
    parents = {id(c) for n in ast.walk(tree) if isinstance(n, ast.Expr) for c in [n.value]}
    return calls, parents


@pytest.mark.parametrize("path", ["dynamic_sr_instant_trader.py", "srv2_momentum_reversal_strategy.py"])
def test_bots_ignore_hook_result(path):
    """Reduce-only (V0 मध्ये शून्य परिणाम): hook चा परिणाम bot कुठेच वापरत नाही — call हे फक्त statement आहे."""
    calls, expr_ids = _vision_calls(path)
    assert calls, "hook जोडलेला नाही"
    assert all(id(c) in expr_ids for c in calls)


def test_vision_package_never_touches_orders_and_exits_never_touch_vision():
    banned = ("trading_engine", "order_execution", "order_safety", "broker_factory", "broker_adapter", "trade_monitor")
    for f in os.listdir(os.path.join(ROOT, "vision")):
        if f.endswith(".py"):
            src = open(os.path.join(ROOT, "vision", f), encoding="utf-8").read()
            for b in banned:
                assert f"import {b}" not in src and f"from {b}" not in src, (f, b)
    for exit_mod in ("trade_monitor.py", "trading_engine.py", "engine_service.py"):
        p = os.path.join(ROOT, exit_mod)
        if os.path.exists(p):
            src = open(p, encoding="utf-8").read()
            assert "vision" not in src.replace("visual", ""), exit_mod     # exit मार्गात vision / human call नाही


# ------------------------------------------------------------------------------------------------ chart: no-lookahead
def test_chart_cut_at_signal_no_future_bars():
    t = pd.Timestamp("2026-10-06 10:42:20")
    df = m1_frame(spike_after=pd.Timestamp("2026-10-06 10:42"))
    setup, higher, tfs = CH.panels(df, t, "5M")
    assert tfs == (5, 15)
    assert setup["last_ts"].max() == pd.Timestamp("2026-10-06 10:41")       # 10:42 चा चालू bar नाही
    assert higher["last_ts"].max() <= pd.Timestamp("2026-10-06 10:41")
    assert setup["high"].max() < 25000 + 500 and higher["high"].max() < 25000 + 500   # spike (भविष्य) कुठेच नाही
    assert setup["start"].iloc[-1] == pd.Timestamp("2026-10-06 10:40")      # 09:15 anchored 5m bucket, अर्धवट (फक्त 10:40, 10:41)


def test_resample_session_anchor_and_daily_panel():
    df = CH.norm_1m(m1_frame())
    h = CH.resample(df, 60)
    starts = set(h["start"].dt.strftime("%H:%M"))
    assert "09:15" in starts and "15:15" in starts and h["end"].max().strftime("%H:%M") == "15:30"
    setup, higher, tfs = CH.panels(m1_frame(), "2026-10-06 11:00", "60M")
    assert tfs == (60, "D") and len(higher) == 2 and higher["last_ts"].max() < pd.Timestamp("2026-10-06 11:00")


def test_render_png_or_none_without_kaleido():
    png, meta = CH.render(m1_frame(), sig())
    assert meta["setup_last"] == "2026-10-06 10:41:00"
    assert png is None or png[:4] == b"\x89PNG"


# ------------------------------------------------------------------------------------------------ verdict नियम / audit
GOOD = {"level_real": "yes", "trend_context": "with", "reversal_valid": "yes", "is_breakout_entry": "no", "false_break_risk": "low",
        "elliott_note": "", "verdict": "agree", "reason": "level खरा, reversal स्पष्ट", "confidence": 0.8}


def msg(d, stop="end_turn", tin=1900, tout=120, cr=0, cw=0):
    return types.SimpleNamespace(stop_reason=stop, content=[types.SimpleNamespace(type="text", text=json.dumps(d, ensure_ascii=False))],
                                 usage=types.SimpleNamespace(input_tokens=tin, output_tokens=tout, cache_read_input_tokens=cr,
                                                             cache_creation_input_tokens=cw))


class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
        self.messages = self

    def create(self, **params):
        self.calls.append(params)
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def test_code_verdict_rules():
    v = lambda **k: SA.code_verdict(SA.validate({**GOOD, **k})[0])  # noqa: E731
    assert v() == "agree"
    assert v(is_breakout_entry="yes") == "disagree"
    assert v(reversal_valid="no") == "disagree"
    assert v(level_real="unclear") == "gray" and v(trend_context="unclear") == "gray"
    assert v(verdict="disagree") == "disagree"
    assert SA.validate({**GOOD, "verdict": "maybe"})[1] is not None              # enum अवैध ⇒ unavailable
    assert SA.validate({**GOOD, "confidence": "x"})[1] is not None
    assert SA.validate({**GOOD, "reason": "क" * 400})[0]["reason"] == "क" * 160
    assert SA.validate({**GOOD, "elliott_note": ""})[0]["elliott_note"] is None
    assert SA.combine(["agree", "disagree"]) == "gray" and SA.combine(["agree", "unavailable"]) == "agree"
    assert SA.combine(["unavailable"]) == "unavailable" and SA.combine(["gray", "gray"]) == "gray"


def test_request_cached_system_model_from_param_and_small_output():
    p = SA.build_request(b"\x89PNG", sig(), "m-test")
    assert p["model"] == "m-test" and p["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert p["output_config"]["format"]["type"] == "json_schema" and p["max_tokens"] <= 4000
    assert sum(1 for b in p["messages"][0]["content"] if b["type"] == "image") == 1
    assert "thinking" not in p and "effort" not in p["output_config"]
    with pytest.raises(ValueError):
        SA.build_request(b"x", sig(), None)


def test_second_audit_only_when_low_confidence_and_budget_allows():
    c = FakeClient([msg(GOOD)])
    r = SA.audit(c, b"png", sig(), "test-sonnet-model")
    assert len(c.calls) == 1 and r["verdict"] == "agree" and r["cost_usd"] > 0
    low = {**GOOD, "confidence": 0.4}
    c = FakeClient([msg(low), msg({**GOOD, "verdict": "disagree", "reversal_valid": "no"})])
    r = SA.audit(c, b"png", sig(), "test-sonnet-model")
    assert len(c.calls) == 2 and r["verdicts"] == ["agree", "disagree"] and r["verdict"] == "gray"
    c = FakeClient([msg(low)])
    r = SA.audit(c, b"png", sig(), "test-sonnet-model", budget_ok=lambda: False)
    assert len(c.calls) == 1 and r["verdict"] == "agree"


def test_api_failure_and_refusal_unavailable():
    r = SA.audit(FakeClient([RuntimeError("timeout")]), b"png", sig(), "test-sonnet-model")
    assert r["verdict"] == "unavailable" and "API" in r["error"]
    r = SA.audit(FakeClient([msg(GOOD, stop="refusal")]), b"png", sig(), "test-sonnet-model")
    assert r["verdict"] == "unavailable"
    r = SA.audit(FakeClient([msg({**GOOD, "level_real": "maybe"})]), b"png", sig(), "test-sonnet-model")
    assert r["verdict"] == "unavailable"


def test_cost_math_and_g_cost_estimate():
    assert SA.cost_usd("test-sonnet-model", {"input_tokens": 1_000_000}) == pytest.approx(2.0)
    assert SA.cost_usd("test-haiku-model", {"output_tokens": 1_000_000}) == pytest.approx(5.0)
    assert SA.cost_usd("test-sonnet-model", {"cache_read": 1_000_000}) == pytest.approx(0.2)
    assert SA.cost_usd("unknown-model", {"input_tokens": 1_000_000}) == pytest.approx(5.0)
    per = SA.estimate_usd("test-sonnet-model", output_tokens=300)               # नेहमीचा audit (लहान JSON)
    assert per < 0.01 and 22 * 10 * 1.3 * per < 5.0                             # 22 दिवस × 10 signals × 1.3 audits < $5
    worst = SA.estimate_usd("test-sonnet-model")                                # budget तपासणीचा सावध अंदाज (output = max_tokens)
    assert worst < 0.30 / 10                                                    # तरीही दैनिक मर्यादेत ≥ 10 audits


# ------------------------------------------------------------------------------------------------ worker
class Sent:
    def __init__(self):
        self.photos, self.texts = [], []

    def photo(self, png, cap):
        self.photos.append((png, cap))
        return True

    def text(self, t):
        self.texts.append(t)
        return True


def queue(db, **kw):
    VH.submit_signal(kw.get("bot", "dynamic_sr_instant"), "NIFTY", "PAPER", kw.get("direction", "BULLISH"), kw.get("level", 25000.0),
                     kw.get("role", "SUPPORT"), "5M", kw.get("ts", dt.datetime(2026, 10, 6, 10, 42, 20)), 25010.0,
                     tags={"breakout_entry": kw.get("breakout", False)})


def run(db, replies, monkeypatch, key=True, model="test-sonnet-model"):
    if key:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-real")
    else:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    if model:
        monkeypatch.setenv("VISION_SIGNAL_MODEL", model)
    else:
        monkeypatch.delenv("VISION_SIGNAL_MODEL", raising=False)
    monkeypatch.setattr(VS, "now_ist", lambda: dt.datetime(2026, 10, 6, 10, 43))
    monkeypatch.setattr(CH, "render", lambda df, s, daily=None: (b"\x89PNGfake", {"error": None}))   # Chrome शिवायही worker tests
    client = FakeClient(replies)
    sent = Sent()
    out = VW.run_once(fetch_fn=lambda sym, daily: (m1_frame(), None), client_factory=lambda t: client, send_photo=sent.photo,
                      send_text=sent.text)
    return out, client, sent


def test_worker_notify_records_and_sends_photo(db, monkeypatch):
    queue(db)
    out, client, sent = run(db, [msg(GOOD)], monkeypatch)
    assert len(out) == 1 and out[0][1]["verdict"] == "agree"
    r = VS.list_signals()[0]
    assert r["status"] == "DONE" and r["verdict"] == "agree" and r["cost_usd"] > 0 and r["notified"] in (0, 1)
    assert len(sent.photos) == 1 and "सहमत" in sent.photos[0][1] and "परिणाम नाही" in sent.photos[0][1]
    assert VS.usage_summary("2026-10-06")["calls"] == 1


def test_worker_shadow_no_telegram(db, monkeypatch):
    VC.save("dynamic_sr_instant", {"vision_mode": "shadow"}, "t")
    queue(db)
    out, client, sent = run(db, [msg(GOOD)], monkeypatch)
    assert out[0][1]["verdict"] == "agree" and not sent.photos and not sent.texts


def test_worker_no_key_or_model_unavailable_without_api_call(db, monkeypatch):
    queue(db)
    out, client, sent = run(db, [], monkeypatch, key=False)
    assert out[0][1]["verdict"] == "unavailable" and not client.calls
    queue(db, level=25200.0)
    out, client, sent = run(db, [], monkeypatch, model=None)
    assert out[0][1]["verdict"] == "unavailable" and "MODEL" in out[0][1]["error"] and not client.calls
    assert out[0][1]["fail_action"] == "ignore"


def test_worker_budget_exhausted_fail_action_and_single_warning(db, monkeypatch):
    VC.save("_global", {"vision_daily_budget_usd": 0.0}, "t")
    queue(db)
    queue(db, level=25300.0)
    out, client, sent = run(db, [], monkeypatch)
    assert [o[1]["verdict"] for o in out] == ["unavailable", "unavailable"] and not client.calls
    assert len(sent.texts) == 1 and "budget" in sent.texts[0]


def test_worker_reuses_verdict_within_15_min(db, monkeypatch):
    queue(db, ts=dt.datetime(2026, 10, 6, 10, 30))
    run(db, [msg(GOOD)], monkeypatch)
    queue(db, ts=dt.datetime(2026, 10, 6, 10, 42), level=25004.0)
    out, client, sent = run(db, [], monkeypatch)
    assert not client.calls and out[0][1]["verdict"] == "agree"
    rows = VS.list_signals()
    assert rows[1]["reused_from"] == rows[0]["signal_id"] and rows[1]["cost_usd"] == 0
    assert "आधीचं मत" in sent.photos[0][1]


def test_stale_signals_expire(db, monkeypatch):
    queue(db)
    monkeypatch.setattr(VS, "now_ist", lambda: dt.datetime.utcnow() + dt.timedelta(hours=5, minutes=30, seconds=VW.STALE_MIN * 60 + 120))
    assert VS.expire_stale(VW.STALE_MIN) == 1
    assert VS.list_signals()[0]["status"] == "EXPIRED"


def test_smoke_script_no_vision_end_to_end(db, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location("vsmoke", os.path.join(ROOT, "scripts", "vision_v0_smoke.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(VW, "default_fetch", lambda sym, daily: (m1_frame(), None))
    sent = Sent()
    import notifications
    monkeypatch.setattr(notifications, "send_telegram_photo", sent.photo)
    assert mod.main(["--no-vision"]) == 0
    r = VS.list_signals()[0]
    assert r["bot"] == "vision_smoke" and r["status"] == "DONE" and r["verdict"] == "unavailable" and r["cost_usd"] == 0
    assert len(sent.photos) == 1 and "TEST" in sent.photos[0][1]


def test_reuse_requires_same_role_and_setup_kind(db, monkeypatch):
    queue(db, ts=dt.datetime(2026, 10, 6, 10, 30))
    run(db, [msg(GOOD)], monkeypatch)
    queue(db, ts=dt.datetime(2026, 10, 6, 10, 40), breakout=True)                # तोच level, पण breakout ⇒ नवा audit
    queue(db, ts=dt.datetime(2026, 10, 6, 10, 41), role="RESISTANCE")            # role वेगळा ⇒ नवा audit
    out, client, sent = run(db, [msg({**GOOD, "is_breakout_entry": "yes"}), msg(GOOD)], monkeypatch)
    assert len(client.calls) == 2 and out[0][1]["verdict"] == "disagree"
    assert all(r["reused_from"] is None for r in VS.list_signals())
    assert "Breakout entry" in sent.photos[0][1]


def test_api_exception_counts_conservative_cost_in_budget(db, monkeypatch):
    queue(db)
    out, client, sent = run(db, [RuntimeError("timeout")], monkeypatch)
    assert out[0][1]["verdict"] == "unavailable"
    u = VS.usage_summary("2026-10-06")
    assert u["calls"] == 1 and u["cost_usd"] > 0.01                            # billed असू शकतो ⇒ सावध अंदाज budget मध्ये


def test_estimate_uses_max_tokens(monkeypatch):
    monkeypatch.setenv("VISION_SIGNAL_MAX_TOKENS", "1000")
    a = SA.estimate_usd("test-sonnet-model")
    monkeypatch.setenv("VISION_SIGNAL_MAX_TOKENS", "3000")
    assert SA.estimate_usd("test-sonnet-model") - a == pytest.approx(2000 * 10 / 1e6)


def test_last_bar_from_bot_shown_but_never_after_signal():
    t = pd.Timestamp("2026-10-06 10:42:20")
    df = m1_frame()
    lb = {"timestamp": "2026-10-06 10:42:00+05:30", "open": 25000.0, "high": 25001.0, "low": 24400.0, "close": 25000.5}
    setup, _, _ = CH.panels(df, t, "5M", last_bar=lb)
    assert setup["last_ts"].max() == pd.Timestamp("2026-10-06 10:42") and setup["low"].min() == 24400.0
    late = {**lb, "timestamp": "2026-10-06 10:43:00+05:30"}                      # signal नंतरची ⇒ नाकार
    setup2, _, _ = CH.panels(df, t, "5M", last_bar=late)
    assert setup2["last_ts"].max() == pd.Timestamp("2026-10-06 10:41") and setup2["low"].min() > 24400.0


def test_smoke_claims_only_its_own_row(db, monkeypatch):
    import importlib.util
    queue(db)                                                                   # खऱ्या bot ची row
    spec = importlib.util.spec_from_file_location("vsmoke2", os.path.join(ROOT, "scripts", "vision_v0_smoke.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(VW, "default_fetch", lambda sym, daily: (m1_frame(), None))
    import notifications
    monkeypatch.setattr(notifications, "send_telegram_photo", lambda png, cap: True)
    assert mod.main(["--no-vision"]) == 0
    st = {r["bot"]: r["status"] for r in VS.list_signals()}
    assert st == {"dynamic_sr_instant": "QUEUED", "vision_smoke": "DONE"}


def test_hook_passes_bot_last_bar(db):
    VH.submit_signal("dynamic_sr_instant", "NIFTY", "PAPER", "BULLISH", 25000, "SUPPORT", "5M", dt.datetime(2026, 10, 6, 10, 42, 20),
                     last_bar={"timestamp": pd.Timestamp("2026-10-06 10:42", tz="Asia/Kolkata"), "open": 1, "high": 2, "low": 0.5, "close": 1.5})
    setup = json.loads(VS.list_signals()[0]["setup_json"])
    assert setup["last_bar"]["low"] == 0.5 and "10:42" in setup["last_bar"]["timestamp"]
