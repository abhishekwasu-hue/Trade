"""tests/test_pcs_dashboard.py — Pullback Credit Spread PCS-3: settings store (local fallback, इतिहास, reset, सगळ्यांना लागू), model premium,
offline preview (फक्त वाचन), आणि Streamlit पान (AppTest — render होतं, डीफॉल्ट mode OFF, order नाही). Network/DB नाही."""
import datetime as dt
import os

import numpy as np
import pandas as pd
import pytest

from pullback_credit_spread import preview as PV
from pullback_credit_spread import settings as S
from pullback_credit_spread import store as ST

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def local_store(tmp_path, monkeypatch):
    monkeypatch.setattr(ST, "LOCAL_PATH", str(tmp_path / "pcs.json"))
    monkeypatch.setattr(ST, "LOCAL_HISTORY", str(tmp_path / "pcs_hist.jsonl"))
    return lambda: None                                                   # conn_fn: Supabase नाही


def test_store_defaults_save_history_reset(local_store):
    s, src = ST.load("NIFTY", conn_fn=local_store)
    assert s == S.DEFAULTS and src == "default"
    clean, errs, changes, src = ST.save("NIFTY", {**S.DEFAULTS, "max_lots": 3, "mode": "PAPER"}, "test", conn_fn=local_store)
    assert src == "local" and dict((k, n) for k, _, n in changes) == {"max_lots": 3, "mode": "PAPER"}
    s, src = ST.load("NIFTY", conn_fn=local_store)
    assert s["max_lots"] == 3 and src == "local"
    assert ST.load("BANKNIFTY", conn_fn=local_store)[0]["max_lots"] == S.DEFAULTS["max_lots"]     # per-symbol वेगळे
    h = ST.history("NIFTY", conn_fn=local_store)
    assert {r["key"] for r in h} == {"max_lots", "mode"} and h[0]["by"] == "test"
    ST.reset("NIFTY", conn_fn=local_store)
    assert ST.load("NIFTY", conn_fn=local_store)[0] == S.DEFAULTS


def test_store_rejects_invalid_and_live_mode(local_store):
    clean, errs, _, _ = ST.save("NIFTY", {**S.DEFAULTS, "mode": "LIVE", "width_points": -5}, conn_fn=local_store)
    assert clean["mode"] == "OFF" and clean["width_points"] == S.DEFAULTS["width_points"] and errs


def test_bs_model_sane():
    c, dc = PV.bs(100, 100, 30 / 365, 0.2, "CE")
    p, dp = PV.bs(100, 100, 30 / 365, 0.2, "PE")
    assert abs(c - p) < 1e-9 and 0.45 < dc < 0.55 and -0.55 < dp < -0.45      # r = 0 ⇒ ATM put-call parity
    assert PV.bs(100, 90, 0, 0.2, "CE")[0] == 10
    ch = PV.model_chain(22000, 50, "2024-03-21", "2024-03-15 11:00", 0.12)
    far = ch[(ch["type"] == "PE") & (ch["strike"] < 21500)]["ltp"]
    assert far.is_monotonic_increasing                                     # strike वाढला तर put महाग


def test_offline_preview_read_only_and_holdout_cut():
    import real_nifty_data
    import leg_level_validation as T3
    try:
        d = real_nifty_data.load_nifty_1min()
    except Exception:
        pytest.skip("offline NIFTY डेटा नाही")
    d = d[(d["timestamp"] >= "2023-01-01") & (d["timestamp"] <= T3.VAL_END)]
    s = dict(S.DEFAULTS)
    inp = PV.offline_inputs(d, "2024-03-15 11:00", s)
    assert inp and all(f["timestamp"].max() + pd.Timedelta(minutes=60 if tf == "1h" else 1440) <= pd.Timestamp("2024-03-15 11:00")
                       for tf, f in inp["frames"].items() if len(f))
    r = PV.run_preview(inp, s, 1_000_000, "2024-03-15 11:00")
    assert [n for n, _, _ in r["steps"]][0].startswith("1.") and r["hypothetical"] and r["model_premium"]
    assert {h["side"] for h in r["hypothetical"]} <= {"PUT", "CALL"}


def test_page_renders_with_defaults_off(local_store, monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr(ST, "_conn", lambda: None)
    at = AppTest.from_string(
        "import sys; sys.path.insert(0, %r)\nimport page_pullback_credit_spread as P\nP.render()" % ROOT, default_timeout=60)
    at.run()
    assert not at.exception
    assert any(s.value == "OFF" for s in at.selectbox if s.label == "Mode")
    assert len(at.expander) >= 12                                          # Presets + 11 विभाग + इतिहास
    assert any("Preview" in b.label for b in at.button)


def test_page_registered_in_app_navigation():
    src = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
    assert "page_pullback_credit_spread.render" in src and 'url_path="pullback-credit-spread"' in src


# ---------- review नंतरचे tests ----------
class _FakeCur:
    def __init__(self, log, fail_on=None, row=None):
        self.log, self.fail_on, self.row = log, fail_on, row

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, args=()):
        self.log.append(" ".join(sql.split()))
        if self.fail_on and self.fail_on in sql:
            raise RuntimeError("relation does not exist")

    def fetchone(self):
        return self.row

    def fetchall(self):
        return []


class _FakeConn:
    def __init__(self, fail_on=None, row=None):
        self.log, self.fail_on, self.row, self.committed, self.rolled = [], fail_on, row, 0, 0

    def cursor(self):
        return _FakeCur(self.log, self.fail_on, self.row)

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled += 1

    def close(self):
        pass


def test_store_supabase_sql_path(local_store, monkeypatch):
    monkeypatch.setattr(ST, "_TABLE_READY", False)
    c = _FakeConn()
    clean, errs, changes, src = ST.save("NIFTY", {**S.DEFAULTS, "max_lots": 4}, "abhi", conn_fn=lambda: c)
    assert src == "supabase" and c.committed == 1 and not errs
    assert any(q.startswith("CREATE TABLE IF NOT EXISTS pcs_settings_history") for q in c.log)
    assert any("INSERT INTO strategy_settings" in q and "ON CONFLICT" in q for q in c.log)
    assert sum("INSERT INTO pcs_settings_history" in q for q in c.log) == len(changes) == 1
    assert not os.path.exists(ST.LOCAL_PATH)                               # Supabase असताना स्थानिक फाईल नाही


def test_store_supabase_failure_is_error_not_silent_local(local_store, monkeypatch):
    monkeypatch.setattr(ST, "_TABLE_READY", False)
    c = _FakeConn(fail_on="CREATE TABLE")
    clean, errs, changes, src = ST.save("NIFTY", {**S.DEFAULTS, "max_lots": 4}, conn_fn=lambda: c)
    assert src == "error" and c.rolled == 1 and c.committed == 0 and changes == [] and "Supabase" in errs[-1]
    assert not os.path.exists(ST.LOCAL_PATH) and not os.path.exists(ST.LOCAL_HISTORY)
    assert ST._TABLE_READY is False                                       # rollback ⇒ DDL पण मागे; flag खोटा नको


def test_store_read_failure_blocks_save(local_store, monkeypatch):
    """Supabase वाचन फेल ⇒ load "error"; save खरी नोंद (डीफॉल्ट/जुन्या मूल्यांनी) overwrite करत नाही."""
    c = _FakeConn(fail_on="SELECT settings")
    assert ST.load("NIFTY", conn_fn=lambda: c)[1] == "error"
    _, errs, changes, src = ST.save("NIFTY", {**S.DEFAULTS, "max_lots": 4}, conn_fn=lambda: c)
    assert src == "error" and not any("INSERT" in q for q in c.log) and not os.path.exists(ST.LOCAL_PATH)


def _app():
    from streamlit.testing.v1 import AppTest
    return AppTest.from_string(
        "import sys; sys.path.insert(0, %r)\nimport page_pullback_credit_spread as P\nP.render()" % ROOT, default_timeout=60)


@pytest.fixture
def page_store(local_store, monkeypatch):
    monkeypatch.setattr(ST, "_conn", lambda: None)
    return local_store


def test_page_values_survive_navigation(page_store):
    """दुसऱ्या पानावर गेल्यावर (widgets render न झाल्याने) Streamlit `pcs_w_*` state पुसतो — परत आल्यावर (Save न करता)
    बदललेली मूल्यं टिकावीत. "away" run म्हणजे दुसरं पान."""
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_string(
        "import sys; sys.path.insert(0, %r)\nimport streamlit as st\nimport page_pullback_credit_spread as P\n"
        "if not st.session_state.get('away'):\n    P.render()\nelse:\n    st.write('other page')" % ROOT, default_timeout=60)
    at.run()
    at.number_input(key="pcs_w_max_lots").set_value(3).run()
    at.session_state["away"] = True
    at.run()
    at.run()                                                               # Streamlit न-render widgets चा state इथे पुसतो
    at.session_state["away"] = False
    at.run()
    assert not at.exception and at.number_input(key="pcs_w_max_lots").value == 3


def test_page_symbol_survives_navigation(page_store):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_string(
        "import sys; sys.path.insert(0, %r)\nimport streamlit as st\nimport page_pullback_credit_spread as P\n"
        "if not st.session_state.get('away'):\n    P.render()\nelse:\n    st.write('other page')" % ROOT, default_timeout=60)
    at.run()
    at.selectbox(key="pcs_symbol").set_value("BANKNIFTY").run()
    at.number_input(key="pcs_w_max_lots").set_value(7).run()
    at.session_state["away"] = True
    at.run()
    at.run()
    at.session_state["away"] = False
    at.run()
    assert not at.exception
    assert at.selectbox(key="pcs_symbol").value == "BANKNIFTY" and at.number_input(key="pcs_w_max_lots").value == 7


def test_page_failed_save_then_retry_keeps_edit(page_store, monkeypatch):
    """review Medium: अयशस्वी save नंतर retry ने बदल पुसू नये आणि खोटं "0 बदल" यश दाखवू नये; यशस्वी save नंतरचा पुढचा बदल टिकावा."""
    real_save = ST.save
    fail = {"on": True}

    def flaky(symbol, new, changed_by="dashboard", conn_fn=None):
        if fail["on"]:
            return new, ["Supabase save अयशस्वी: RuntimeError"], [], "error"
        return real_save(symbol, new, changed_by, conn_fn)
    monkeypatch.setattr(ST, "save", flaky)
    at = _app()
    at.run()
    at.number_input(key="pcs_w_max_lots").set_value(4).run()
    at.button(key="pcs_save").click().run()
    assert at.error and at.number_input(key="pcs_w_max_lots").value == 4
    fail["on"] = False
    at.button(key="pcs_save").click().run()
    assert not at.exception and at.number_input(key="pcs_w_max_lots").value == 4
    assert ST.load("NIFTY", conn_fn=page_store)[0]["max_lots"] == 4 and any("1 बदल" in x.value for x in at.success)
    at.number_input(key="pcs_w_max_lots").set_value(5).run()                # save नंतरचा पहिला बदल हरवू नये
    assert at.number_input(key="pcs_w_max_lots").value == 5


def test_page_save_disabled_when_store_unreadable(page_store, monkeypatch):
    monkeypatch.setattr(ST, "load", lambda symbol, conn_fn=None: (dict(S.DEFAULTS), "error"))
    at = _app()
    at.run()
    assert not at.exception and at.button(key="pcs_save").disabled and at.button(key="pcs_reset").disabled


def test_page_apply_all_keeps_each_symbols_mode(page_store):
    ST.save("BANKNIFTY", {**S.DEFAULTS, "mode": "OFF", "symbol_enabled": False}, conn_fn=page_store)
    at = _app()
    at.run()
    at.selectbox(key="pcs_w_mode").set_value("PAPER")
    at.number_input(key="pcs_w_max_lots").set_value(2)
    at.checkbox(key="pcs_apply_all").check()
    at.run()
    at.button(key="pcs_save").click().run()
    assert not at.exception
    n, b, x = (ST.load(s, conn_fn=page_store)[0] for s in ("NIFTY", "BANKNIFTY", "SENSEX"))
    assert n["mode"] == "PAPER" and n["max_lots"] == 2
    assert b["mode"] == "OFF" and b["symbol_enabled"] is False and b["max_lots"] == 2      # mode/symbol_enabled स्वतःचे
    assert x["mode"] == "OFF" and x["max_lots"] == 2


def test_page_save_blocked_on_errors(page_store):
    at = _app()
    at.run()
    at.text_input(key="pcs_w_event_dates").set_value("2024-13-45").run()
    assert at.button(key="pcs_save").disabled and at.error
    assert ST.load("NIFTY", conn_fn=page_store)[1] == "default"


def test_preview_never_touches_orders(monkeypatch):
    """Preview/पान order पाठवत नाहीत: order functions ला हात लावला तर test फेल."""
    import upstox_api
    for fn in ("place_multi_leg_order", "place_stop_loss_order", "cancel_order", "execute_order_leg_set"):
        monkeypatch.setattr(upstox_api, fn, lambda *a, **k: (_ for _ in ()).throw(AssertionError("order call!")))
    for f in ("page_pullback_credit_spread.py", "pullback_credit_spread/preview.py", "pullback_credit_spread/levels_source.py"):
        src = open(os.path.join(ROOT, f), encoding="utf-8").read()
        assert "trading_engine" not in src and "upstox_api" not in src and "broker_factory" not in src
    idx = pd.date_range("2024-01-01 09:15", periods=375 * 60, freq="1min")
    idx = idx[(idx.time >= dt.time(9, 15)) & (idx.time <= dt.time(15, 29))]
    px = 21000 + np.cumsum(np.random.default_rng(1).normal(0, 3, len(idx)))
    d = pd.DataFrame({"timestamp": idx, "open": px, "high": px + 2, "low": px - 2, "close": px, "volume": 0})
    now = idx[-1] + pd.Timedelta(minutes=1)
    inp = PV.offline_inputs(d, now, dict(S.DEFAULTS))
    if inp:
        PV.run_preview(inp, dict(S.DEFAULTS), 1_000_000, now)


def test_nifty_lot_size_history():
    assert PV.nifty_lot_size(dt.date(2023, 6, 1)) == 50 and PV.nifty_lot_size(dt.date(2020, 6, 1)) == 75
    assert PV.nifty_lot_size(dt.date(2015, 3, 2)) == 25
    assert PV.nifty_lot_size(dt.date(2024, 3, 28)) == 50                  # offline preview फक्त ≤ 2024-03 (holdout बंद)
