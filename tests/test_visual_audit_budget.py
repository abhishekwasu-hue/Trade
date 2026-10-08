"""Visual audit (EOD): अपयशाचं कारण (कोणता chart, का), खर्च vision च्याच budget मध्ये, symbols setting (default फक्त NIFTY)."""
import json

import pandas as pd
import pytest

import run_visual_audit as RVA
from opportunity_engine.visual_audit import render as R
from vision import config as VC
from vision import store as VUS


@pytest.fixture
def vdb(tmp_path, monkeypatch):
    p = str(tmp_path / "vision.db")
    monkeypatch.setenv("VISION_DB_PATH", p)
    return p


def rec(tf="1d", ov="OK", ind="OK", err=None, calls=2, tin=3000, tout=700):
    return {"run_id": "r1", "symbol": "NIFTY", "tf": tf, "overlay": {"status": ov, "error": err}, "independent": {"status": ind, "error": err},
            "usage": {"input_tokens": tin, "output_tokens": tout, "calls": calls}}


def test_failures_name_chart_kind_and_reason():
    assert RVA.failures_of(rec()) == []
    assert RVA.failures_of(rec(ov="SKIPPED")) == []                                       # labels नाहीत ⇒ अपयश नाही
    f = RVA.failures_of(rec(tf="1h", ov="FAILED", err="verdict नाही: ['B']"))
    assert f == ["NIFTY 1h overlay: FAILED — verdict नाही: ['B']"]
    assert any("Supabase" in x for x in RVA.failures_of(rec(), saved=False))


def test_symbols_default_nifty_env_and_cli_override(vdb, monkeypatch):
    monkeypatch.delenv("VISUAL_AUDIT_SYMBOLS", raising=False)
    assert RVA.symbols_setting() == ["NIFTY"]
    assert VC.load("_global")["visual_audit_daily_cap"] == 0.10 and VC.load("_global")["signals_daily_reserve_usd"] == 0.20
    VC.save("_global", {"visual_audit_symbols": ["NIFTY", "BANKNIFTY"]}, "test")
    assert RVA.symbols_setting() == ["NIFTY", "BANKNIFTY"]
    monkeypatch.setenv("VISUAL_AUDIT_SYMBOLS", "banknifty")
    assert RVA.symbols_setting() == ["BANKNIFTY"]
    assert RVA.symbols_setting("nifty") == ["NIFTY"]
    with pytest.raises(ValueError):
        VC.save("_global", {"visual_audit_symbols": ["SENSEX"]}, "test")


def test_usage_goes_into_vision_budget_and_blocks_when_over(vdb):
    model = "claude-opus-test"
    c = RVA.record_usage(model, rec(tin=19403, tout=4982, calls=7))
    assert abs(c - (19403 * 4.0 + 4982 * 20.0) / 1e6) < 1e-9                              # opus-family दर ⇒ ≈ $0.177
    day, month = VUS.spent()
    assert abs(day - c) < 1e-9
    by = VUS.spent_by_task()
    assert set(by) == {"visual_audit"} and by["visual_audit"][2] == 1
    assert abs(RVA.chart_estimate(model) - c) < 1e-9                                       # अंदाज = खऱ्या नोंदींची सरासरी


G = {"vision_daily_budget_usd": 0.30, "vision_monthly_budget_usd": 5.0, "visual_audit_daily_cap": 0.10, "signals_daily_reserve_usd": 0.20}


def test_signals_priority_cap_and_reserve():
    """Abhi 2026-10-08: audit ची दैनिक उप-मर्यादा $0.10, signals साठी $0.20 राखीव, महिना $5 — audit signals चा budget कधीच संपवत नाही."""
    assert RVA.audit_allowed(0.045, G, {}) == (True, "")
    ok, why = RVA.audit_allowed(0.045, G, {"visual_audit": (0.06, 0.5, 1)})                 # 0.06 + 0.045 > 0.10
    assert not ok and "उप-मर्यादा" in why
    ok, why = RVA.audit_allowed(0.045, {**G, "visual_audit_daily_cap": 0.50}, {"visual_audit": (0.06, 0.5, 1)})
    assert not ok and "राखीव" in why                                                       # cap मोठा तरी 0.30 − 0.20 = 0.10 च
    ok, why = RVA.audit_allowed(0.045, G, {"signal": (0.27, 1.0, 9)})                       # signals नी दिवस वापरला ⇒ audit नाही
    assert not ok and "दैनिक" in why
    ok, why = RVA.audit_allowed(0.045, G, {"signal": (0.0, 4.98, 0)})
    assert not ok and "मासिक" in why


def test_per_chart_skip_is_not_a_failure(vdb, monkeypatch):
    """Budget मुळे वगळलेला chart: API call नाही, अपयश नाही, सारांशात कारण."""
    from opportunity_engine.visual_audit import jobs as J
    called = []
    monkeypatch.setattr(J, "prepare_chart", lambda *a, **k: called.append(a[3]) or None)
    skipped = []
    out = J.audit_day(None, None, "NIFTY", "2026-10-09", {}, None, [], [], {}, None, ("1d", "1h"),
                      allow=lambda tf: (tf == "1d", "उप-मर्यादा"), skipped=skipped)
    assert out == [] and called == ["1d"] and skipped == [("1h", "उप-मर्यादा")]


def test_kaleido_session_reuses_one_server_and_cleans_up(monkeypatch):
    import kaleido
    ev = []
    monkeypatch.setattr(kaleido, "start_sync_server", lambda **k: ev.append("start"))
    monkeypatch.setattr(kaleido, "stop_sync_server", lambda **k: ev.append("stop"))
    with pytest.raises(RuntimeError):
        with R.KaleidoSession():
            raise RuntimeError("audit मध्ये चूक")
    assert ev == ["start", "stop"]                                                          # चुकीतही cleanup


def test_zero_call_record_is_not_written(vdb):
    assert RVA.record_usage("claude-opus-test", rec(calls=0, tin=0, tout=0)) == 0.0
    assert VUS.spent() == (0.0, 0.0)


def test_render_failure_reason_is_logged(capsys, monkeypatch):
    df = pd.DataFrame({"timestamp": pd.date_range("2026-10-01", periods=10, freq="h"), "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5})

    def boom(*a, **k):
        raise RuntimeError("kaleido नाही")
    monkeypatch.setattr(R, "build_figure", boom)
    assert R.render_png(df, "1h", "NIFTY", overlay=False, sleep=lambda s: None) is None
    out = capsys.readouterr().out
    assert "render NIFTY 1h plain (प्रयत्न 1/2): RuntimeError: kaleido नाही" in out and "(प्रयत्न 2/2)" in out


def test_render_retries_once_after_transient_failure(monkeypatch):
    """2026-10-08 चं अपयश: overlay यशस्वी, त्याच frame चा plain अयशस्वी (kaleido तात्पुरतं) ⇒ दुसऱ्या प्रयत्नात यश."""
    df = pd.DataFrame({"timestamp": pd.date_range("2026-10-01", periods=10, freq="h"), "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5})
    n = []

    class Fig:
        def to_image(self, **k):
            n.append(1)
            if len(n) == 1:
                raise RuntimeError("Chrome timeout")
            return b"png"
    monkeypatch.setattr(R, "build_figure", lambda *a, **k: Fig())
    assert R.render_png(df, "1h", "NIFTY", overlay=False, sleep=lambda s: None) == b"png" and len(n) == 2


def test_main_reports_failed_charts_in_error_and_records_cost(vdb, monkeypatch, tmp_path):
    """main: एका chart चं अपयश ⇒ बाकींचा अहवाल जातो, error संदेशात chart + कारण; खर्च vision_usage मध्ये."""
    sent, errs = [], []
    monkeypatch.setenv("VISUAL_AUDIT_ENABLED", "1")
    monkeypatch.setenv("VISUAL_AUDIT_MODEL", "claude-opus-test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.delenv("VISUAL_AUDIT_SYMBOLS", raising=False)
    monkeypatch.setattr(RVA.cloud_db, "get_effective_upstox_token", lambda t: "tok")
    monkeypatch.setattr(RVA, "send_telegram_message", lambda m: sent.append(m))
    monkeypatch.setattr(RVA, "notify_error", lambda who, m: errs.append(m))
    seen = []

    def fake_run(sym, *a, on_record=None, allow=None, **k):
        assert allow is not None and allow("1d")[0]
        seen.append(sym)
        r1, r2 = rec("1d"), rec("1h", ov="FAILED", err="verdict नाही: ['C']")
        cost = sum(on_record(r) for r in (r1, r2))
        fails = RVA.failures_of(r2)
        return False, [f"{sym} 1d ok", f"{sym} 1h"], {"input_tokens": 6000, "output_tokens": 1400, "calls": 4, "cost_usd": cost, "failures": fails}
    monkeypatch.setattr(RVA, "run_symbol", fake_run)
    assert RVA.main([], client_factory=lambda: object()) == 1
    assert seen == ["NIFTY"]                                                               # default फक्त NIFTY
    assert sent and "NIFTY 1d ok" in sent[0] and "NIFTY 1h overlay: FAILED — verdict नाही: ['C']" in sent[0] and "Vision एकूण" in sent[0] and "cap" in sent[0]
    assert errs and "NIFTY 1h overlay" in errs[0]
    assert VUS.spent_by_task()["visual_audit"][2] == 2


def test_dashboard_spend_rows_sum_signal_and_visual():
    import page_vision_human_eye as P
    day, month, rows = P.spend_rows({"signal": (0.04, 1.2, 3), "visual_audit": (0.09, 0.9, 4)}, {})
    assert round(day, 3) == 0.13 and round(month, 2) == 2.1 and rows[-1]["काम"] == "एकूण" and rows[-1]["आज calls"] == 7
    assert json.dumps(rows, ensure_ascii=False)
